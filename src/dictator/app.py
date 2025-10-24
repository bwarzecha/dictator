"""Main application controller.

Orchestrates all components and manages menubar UI.
"""

import rumps
import threading
import logging
from pathlib import Path
import AppKit

from PyQt6.QtWidgets import QApplication

from dictator.models import AppConfig
from dictator.audio import AudioRecorder
from dictator.transcription import WhisperTranscriber
from dictator.insertion import TextInserter
from dictator.storage import RecordingStorage
from dictator.hotkey import HotkeyListener, check_input_monitoring_permission
from dictator.ui.history import HistoryWindow
from dictator.ui.settings import SettingsWindow
from dictator.ui.file_processor import FileProcessorWindow
from dictator.services.llm_corrector import BedrockLLMProvider
from dictator.services.audio_processor import AudioProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def safe_notification(title: str, subtitle: str = "", message: str = ""):
    """Show notification with error handling for missing Info.plist.

    When running from venv Python (not .app bundle), rumps.notification
    may fail due to missing CFBundleIdentifier in Info.plist.
    """
    try:
        rumps.notification(title, subtitle, message)
    except Exception as e:
        logger.warning(f"Could not show notification: {e}")


class DictatorApp(rumps.App):
    """Main application class.

    Manages menubar UI and coordinates all components.
    """

    def __init__(self):
        """Initialize application and all components."""
        super().__init__("🟢", icon=None, quit_button=None)

        config_path = Path.home() / ".dictator" / "config.json"
        self.config = AppConfig.load(config_path)

        self.audio = AudioRecorder(
            sample_rate=16000,
            recordings_dir=self.config.recordings_dir,
        )
        self.transcriber = WhisperTranscriber(
            model_name=self.config.whisper_model,
            n_threads=self.config.whisper_threads,
            custom_vocabulary=self.config.custom_vocabulary,
        )
        self.inserter = TextInserter()
        self.storage = RecordingStorage(self.config.recordings_dir)

        # Initialize LLM corrector if enabled
        self.llm_corrector = None
        if self.config.llm_correction_enabled:
            self._init_llm_corrector()

        # Initialize Qt application for history window
        self.qt_app = QApplication.instance()
        if self.qt_app is None:
            import sys
            self.qt_app = QApplication(sys.argv)

        self.history_window = None  # Lazy initialization
        self.settings_window = None  # Lazy initialization
        self.file_processor_window = None  # Lazy initialization
        self.config_path = config_path

        # Create audio processor for shared pipeline
        self.audio_processor = AudioProcessor(
            transcriber=self.transcriber,
            storage=self.storage,
            llm_corrector=self.llm_corrector,
            inserter=self.inserter,
        )

        self.status_item = rumps.MenuItem("Status: Ready")
        self.history_item = rumps.MenuItem("Show History")
        self.process_file_item = rumps.MenuItem("Process Audio File...")
        self.settings_item = rumps.MenuItem("Settings...")
        self.quit_item = rumps.MenuItem("Quit Dictator")
        self.menu = [
            self.status_item,
            None,
            self.history_item,
            self.process_file_item,
            self.settings_item,
            None,
            self.quit_item,
        ]

        self.duration_timer = None

        # Check Input Monitoring permission before starting hotkey listener
        if not check_input_monitoring_permission():
            logger.warning("Input Monitoring permission not granted")
            safe_notification(
                "Permission Required",
                "",
                "Grant Input Monitoring permission in System Settings → Privacy & Security to enable hotkey (Option+Space)",
            )

        self.hotkey = HotkeyListener(callback=self.toggle_recording)
        self.hotkey.start()

        threading.Thread(target=self.transcriber.load_model, daemon=True).start()

        logger.info("Dictator app initialized")

    def toggle_recording(self):
        """Handle hotkey press to toggle recording on/off."""
        if self.audio.is_recording:
            self._stop_and_transcribe()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start audio recording."""
        try:
            self.audio.start_recording()
            self.title = "🔴"
            self._update_status("Recording...")

            self.duration_timer = rumps.Timer(self._update_duration, 1)
            self.duration_timer.start()

            logger.info("Recording started")

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            safe_notification(
                "Recording Error",
                "",
                f"Failed to start: {e}",
            )
            self._update_status("Ready")

    def _stop_and_transcribe(self):
        """Stop recording and start transcription."""
        try:
            if self.duration_timer:
                self.duration_timer.stop()
                self.duration_timer = None

            audio_path, duration = self.audio.stop_recording()

            self.title = "🟡"
            self._update_status("Transcribing...")

            threading.Thread(
                target=self._transcribe_and_insert,
                args=(audio_path, duration),
                daemon=True,
            ).start()

            logger.info("Recording stopped, transcription started")

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            safe_notification(
                "Recording Error",
                "",
                f"Failed to stop: {e}",
            )
            self.title = "⚪"
            self._update_status("Ready")

    def _transcribe_and_insert(self, audio_path: Path, duration: float):
        """Transcribe audio and insert text (runs in background thread).

        Args:
            audio_path: Path to audio file
            duration: Recording duration in seconds
        """
        try:
            # Use audio processor for common pipeline
            result = self.audio_processor.process(
                audio_path, duration, progress_callback=self._update_status
            )

            # Handle insertion result
            if result.inserted:
                notification_text = result.cleaned_text
                if result.correction_failed:
                    notification_text += " (uncorrected)"
                    safe_notification(
                        "Text Inserted (Correction Failed)",
                        "",
                        "Using raw transcript. Check AWS settings and try again.",
                    )
                else:
                    safe_notification(
                        "Text Inserted",
                        "",
                        notification_text[:100]
                        + ("..." if len(notification_text) > 100 else ""),
                    )
            else:
                logger.info("Text insertion failed, copying to clipboard")
                # Copy to clipboard on main thread and show notification
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._copy_and_notify(result.cleaned_text)
                )

            logger.info(f"Transcription complete: {len(result.cleaned_text)} chars")

        except FileNotFoundError:
            logger.error("Audio file not found")
            safe_notification(
                "Error",
                "",
                "Recording file not found. Please try again.",
            )

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            safe_notification(
                "Transcription Failed",
                "",
                f"Error: {str(e)[:100]}",
            )

        finally:
            self._update_status("Ready")

    def _update_duration(self, timer):
        """Update menubar with current recording duration.

        Args:
            timer: rumps.Timer instance
        """
        duration = self.audio.get_duration()
        self.title = f"🔴 {duration:.1f}s"

    def _update_status(self, status: str):
        """Update status menu item.

        Args:
            status: Status text to display
        """
        self.status_item.title = f"Status: {status}"
        if status == "Ready":
            self.title = ""

    @rumps.clicked("Show History")
    def show_history(self, _):
        """Handle show history menu item."""
        if self.history_window is None:
            self.history_window = HistoryWindow(self.storage, self.llm_corrector)
        else:
            # Update LLM corrector and reload recordings
            self.history_window.set_llm_corrector(self.llm_corrector)

        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()
        logger.info("History window opened")

    @rumps.clicked("Process Audio File...")
    def show_file_processor(self, _):
        """Handle process audio file menu item."""
        if self.file_processor_window is None:
            self.file_processor_window = FileProcessorWindow(self.audio_processor)

        self.file_processor_window.show()
        self.file_processor_window.raise_()
        self.file_processor_window.activateWindow()
        logger.info("File processor window opened")

    @rumps.clicked("Settings...")
    def show_settings(self, _):
        """Handle settings menu item."""
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.config)
            self.settings_window.config_changed.connect(self._update_config)

        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()
        logger.info("Settings window opened")

    def _init_llm_corrector(self):
        """Initialize LLM corrector with current config."""
        try:
            if self.config.llm_provider == "bedrock":
                logger.info("Initializing Bedrock LLM corrector")
                self.llm_corrector = BedrockLLMProvider(
                    model_id=self.config.bedrock_model,
                    correction_prompt=self.config.correction_prompt,
                    aws_profile=self.config.aws_profile if self.config.aws_profile else None,
                    region=self.config.bedrock_region,
                    custom_vocabulary=self.config.custom_vocabulary,
                )
                logger.info("LLM corrector initialized successfully")
            else:
                logger.warning(f"Unsupported LLM provider: {self.config.llm_provider}")
                self.llm_corrector = None
        except Exception as e:
            logger.error(f"Failed to initialize LLM corrector: {e}")
            self.llm_corrector = None

    def _update_config(self, new_config: AppConfig):
        """Update application configuration.

        Args:
            new_config: New configuration to apply
        """
        try:
            # Save config to disk
            new_config.save(self.config_path)
            self.config = new_config

            # Update Whisper transcriber if model, threads, or vocabulary changed
            if (new_config.whisper_model != self.transcriber.model_name or
                new_config.whisper_threads != self.transcriber.n_threads or
                new_config.custom_vocabulary != self.transcriber.custom_vocabulary):
                logger.info(
                    "Whisper settings changed, reinitializing",
                    extra={
                        "old_model": self.transcriber.model_name,
                        "new_model": new_config.whisper_model,
                        "old_threads": self.transcriber.n_threads,
                        "new_threads": new_config.whisper_threads,
                        "vocab_count": len(new_config.custom_vocabulary),
                    }
                )
                self.transcriber = WhisperTranscriber(
                    model_name=new_config.whisper_model,
                    n_threads=new_config.whisper_threads,
                    custom_vocabulary=new_config.custom_vocabulary,
                )
                logger.info(
                    f"✓ Whisper transcriber initialized with model: {new_config.whisper_model}"
                )
                threading.Thread(target=self.transcriber.load_model, daemon=True).start()

            # Reinitialize LLM corrector if settings changed
            if new_config.llm_correction_enabled:
                self._init_llm_corrector()
            else:
                self.llm_corrector = None
                logger.info("LLM correction disabled")

            # Update audio processor with new corrector
            self.audio_processor.llm_corrector = self.llm_corrector

            # Update history window if it exists
            if self.history_window:
                self.history_window.set_llm_corrector(self.llm_corrector)

            logger.info("Configuration updated successfully")

        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")

    @rumps.clicked("Quit Dictator")
    def quit_app(self, _):
        """Handle quit menu item."""
        self.hotkey.stop()
        rumps.quit_application()

    def _copy_and_notify(self, text: str):
        """Copy text to clipboard and show notification (main thread only).

        Args:
            text: Text to copy
        """
        # Copy to clipboard
        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        pasteboard.clearContents()
        pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString)
        logger.info("Text copied to clipboard")

        # Show notification
        safe_notification(
            "Text Copied to Clipboard",
            "",
            f"{text[:200]}\n\nGrant accessibility permissions in System Settings to auto-paste.",
        )
