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
from dictator.health_monitor import HealthMonitor

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
        super().__init__("🟢", icon=None, quit_button=None)  # Green = ready

        config_path = Path.home() / ".dictator" / "config.json"
        self.config = AppConfig.load(config_path)

        self.audio = AudioRecorder(
            sample_rate=16000,
            recordings_dir=self.config.recordings_dir,
            remove_silence=self.config.remove_silence_enabled,
            silence_threshold=self.config.silence_threshold,
            min_silence_duration=self.config.min_silence_duration,
        )

        # Track silence detection state
        self._silence_detected = False

        # Set up silence detection callbacks for menubar warning
        self.audio.set_silence_callback(self._on_prolonged_silence)
        self.audio.set_voice_resumed_callback(self._on_voice_resumed)
        # You can adjust the voice threshold if needed (default is 0.01)
        # self.audio.set_voice_threshold(0.02)  # Increase if too sensitive

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
        self.mic_check_item = rumps.MenuItem("Mic Check")
        self.history_item = rumps.MenuItem("Show History")
        self.process_file_item = rumps.MenuItem("Process Audio File...")
        self.settings_item = rumps.MenuItem("Settings...")
        self.quit_item = rumps.MenuItem("Quit Dictator")
        self.menu = [
            self.status_item,
            self.mic_check_item,
            None,
            self.history_item,
            self.process_file_item,
            self.settings_item,
            None,
            self.quit_item,
        ]

        self.mic_check_timer = None
        self.volume_update_timer = None  # Timer for recording display updates

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

        # Initialize health monitor
        self.health_monitor = HealthMonitor()
        self._register_health_monitoring()
        self.health_monitor.start_monitoring(check_interval=5.0)

        threading.Thread(target=self.transcriber.load_model, daemon=True).start()

        logger.info("Dictator app initialized")

    def _update_ui_safe(self, callback):
        """Execute UI update on main thread safely.

        AppKit UI must only be updated from the main thread to avoid
        AutoLayout corruption and crashes. This helper ensures all UI
        updates are dispatched to the main thread.

        Args:
            callback: Function to execute on main thread
        """
        if threading.current_thread() is threading.main_thread():
            # Already on main thread, execute directly
            callback()
        else:
            # Dispatch to main thread to avoid AutoLayout corruption
            # Use DEBUG to avoid log spam from timer callbacks (10x/sec)
            logger.debug(f"[{threading.current_thread().name}] Dispatching UI update to main thread")
            AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(callback)

    def toggle_recording(self):
        """Handle hotkey press to toggle recording on/off."""
        if self.audio.is_recording:
            self._stop_and_transcribe()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start audio recording."""
        try:
            # Reset silence detection state
            self._silence_detected = False

            self.audio.start_recording()

            # Update UI from main thread to prevent AutoLayout corruption
            self._update_ui_safe(lambda: setattr(self, 'title', "  0s ⚫"))
            self._update_status("Recording...")

            # Start combined timer for both duration and volume (updates 10 times per second)
            self.volume_update_timer = rumps.Timer(self._update_recording_display, 0.1)
            self.volume_update_timer.start()

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
            # Stop the timer
            if self.volume_update_timer:
                self.volume_update_timer.stop()
                self.volume_update_timer = None

            audio_path, duration = self.audio.stop_recording()

            # Update UI from main thread to prevent AutoLayout corruption
            self._update_ui_safe(lambda: setattr(self, 'title', "🟡"))
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
            self._update_ui_safe(lambda: setattr(self, 'title', "🟢"))
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

    def _update_recording_display(self, timer):
        """Update menubar with recording status (duration and volume indicator).

        Note: Timer callbacks should run on main thread, but we use _update_ui_safe
        for consistency and defensive programming.

        Args:
            timer: rumps.Timer instance
        """
        duration = int(self.audio.get_duration())  # Whole seconds only
        volume = self.audio.get_volume_level()

        # Check if we should show warning for silence
        if self._silence_detected:
            # Show warning sign when no voice detected for 10+ seconds
            self._update_ui_safe(lambda: setattr(self, 'title', f"{duration:3d}s ⚠️"))
        else:
            # Get volume indicator (colored dot)
            volume_indicator = self._get_recording_volume_indicator(volume)
            # Put seconds first with fixed width, then dot - no jumping!
            self._update_ui_safe(lambda: setattr(self, 'title', f"{duration:3d}s {volume_indicator}"))

    def _get_recording_volume_indicator(self, volume: float) -> str:
        """Convert volume level to visual indicator for recording state.

        Args:
            volume: Volume level from 0.0 to 1.0

        Returns:
            Colored dot indicator based on volume level
        """
        # Simplified color scheme for recording:
        # Black (silent) -> Yellow (quiet) -> Orange (medium) -> Blue (loud)
        # No green during recording (green means ready)

        if volume < 0.05:
            # Very quiet/muted
            return "⚫"  # Black circle
        elif volume < 0.20:
            # Quiet
            return "🟡"  # Yellow circle
        elif volume < 0.50:
            # Medium
            return "🟠"  # Orange circle
        else:
            # Loud
            return "🔵"  # Blue circle

    def _get_volume_indicator(self, volume: float) -> str:
        """Convert volume level to visual indicator (for mic check).

        Args:
            volume: Volume level from 0.0 to 1.0

        Returns:
            Colored dot indicator based on volume level
        """
        # Full color scheme for mic check
        if volume < 0.05:
            return "⚫"  # Black
        elif volume < 0.20:
            return "🟡"  # Yellow
        elif volume < 0.50:
            return "🟠"  # Orange
        elif volume < 0.80:
            return "🟢"  # Green (good level)
        else:
            return "🔵"  # Blue (loud)

    def _update_status(self, status: str):
        """Update status menu item (thread-safe).

        Args:
            status: Status text to display
        """
        def update():
            self.status_item.title = f"Status: {status}"
            if status == "Ready":
                self.title = "🟢"  # Green dot when ready

        self._update_ui_safe(update)

    @rumps.clicked("Mic Check")
    def toggle_mic_check(self, sender):
        """Toggle microphone level monitoring."""
        if self.mic_check_timer and self.mic_check_timer.is_alive():
            # Stop mic check
            self.mic_check_timer.stop()
            self.mic_check_timer = None
            self.audio.stop_monitoring()
            self.mic_check_item.title = "Mic Check"
            # Rumps menu clicks run on main thread, but use _update_ui_safe for consistency
            self._update_ui_safe(lambda: setattr(self, 'title', "🟢"))
            self._update_status("Ready")
            logger.info("Mic check stopped")
        else:
            # Start mic check
            self.audio.start_monitoring()
            self.mic_check_item.title = "Stop Mic Check"
            self._update_status("Monitoring mic...")

            # Create timer to update mic level display
            self.mic_check_timer = rumps.Timer(self._update_mic_level, 0.1)  # Update 10 times per second
            self.mic_check_timer.start()
            logger.info("Mic check started")

    def _update_mic_level(self, timer):
        """Update menubar with current microphone level.

        Note: Timer callbacks should run on main thread, but we use _update_ui_safe
        for consistency and defensive programming.
        """
        volume = self.audio.get_volume_level()
        volume_bars = self._get_volume_indicator(volume)
        self._update_ui_safe(lambda: setattr(self, 'title', f"🎤 {volume_bars}"))

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

            # Update audio recorder silence removal settings
            self.audio.remove_silence = new_config.remove_silence_enabled
            self.audio.silence_removal_threshold = new_config.silence_threshold
            self.audio.min_silence_to_remove = new_config.min_silence_duration
            logger.info(
                f"Silence removal: {'enabled' if new_config.remove_silence_enabled else 'disabled'}"
            )

            # Update history window if it exists
            if self.history_window:
                self.history_window.set_llm_corrector(self.llm_corrector)

            logger.info("Configuration updated successfully")

        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")

    def _register_health_monitoring(self):
        """Register components for health monitoring."""
        # Monitor hotkey listener
        self.health_monitor.register_component(
            name="hotkey_listener",
            check_callback=lambda: self.hotkey.is_running,
            recovery_callback=lambda: self.hotkey.restart(),
        )

        # Monitor Whisper transcriber
        self.health_monitor.register_component(
            name="whisper_transcriber",
            check_callback=lambda: self.transcriber.is_ready,
            recovery_callback=lambda: self.transcriber.reload_model(),
        )

        # Monitor audio device availability
        self.health_monitor.register_component(
            name="audio_device",
            check_callback=self._check_audio_device,
            recovery_callback=self._recover_audio_device,
        )

        logger.info("Health monitoring registered for all components")

    def _check_audio_device(self) -> bool:
        """Check if audio device is available.

        Returns:
            True if audio device is working
        """
        try:
            import sounddevice as sd

            # Try to query devices
            devices = sd.query_devices()
            return len(devices) > 0
        except Exception as e:
            logger.error(f"Audio device check failed: {e}")
            return False

    def _recover_audio_device(self):
        """Recover audio device after failure."""
        logger.info("Recovering audio device")
        try:
            # Stop any existing monitoring/recording
            if self.audio._stream:
                self.audio._stream.stop()
                self.audio._stream.close()
                self.audio._stream = None

            # Reset sounddevice
            import sounddevice as sd
            sd._terminate()
            sd._initialize()

            logger.info("Audio device recovered")
        except Exception as e:
            logger.error(f"Audio device recovery failed: {e}")

    @rumps.clicked("Quit Dictator")
    def quit_app(self, _):
        """Handle quit menu item."""
        logger.info("Dictator app terminating")
        if self.hotkey:
            self.hotkey.stop()
        if self.health_monitor:
            self.health_monitor.stop_monitoring()
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

    def _on_prolonged_silence(self, silence_duration: float):
        """Handle prolonged silence detection during recording.

        Args:
            silence_duration: How long silence has been detected (seconds)
        """
        logger.warning(f"No voice detected for {silence_duration:.1f} seconds")

        # Set flag to show warning icon in menubar
        self._silence_detected = True

    def _on_voice_resumed(self):
        """Handle voice resuming after prolonged silence."""
        if self._silence_detected:
            logger.info("Voice detected again, clearing warning")
            self._silence_detected = False
