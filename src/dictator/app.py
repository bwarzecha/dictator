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
from dictator.hotkey import HotkeyListener
from dictator.ui.history import HistoryWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DictatorApp(rumps.App):
    """Main application class.

    Manages menubar UI and coordinates all components.
    """

    def __init__(self):
        """Initialize application and all components."""
        super().__init__("⚪", icon=None, quit_button=None)

        config_path = Path.home() / ".dictator" / "config.json"
        self.config = AppConfig.load(config_path)

        self.audio = AudioRecorder(
            sample_rate=16000,
            recordings_dir=self.config.recordings_dir,
        )
        self.transcriber = WhisperTranscriber(
            model_name=self.config.whisper_model,
            n_threads=self.config.whisper_threads,
        )
        self.inserter = TextInserter()
        self.storage = RecordingStorage(self.config.recordings_dir)

        # Initialize Qt application for history window
        self.qt_app = QApplication.instance()
        if self.qt_app is None:
            import sys
            self.qt_app = QApplication(sys.argv)

        self.history_window = None  # Lazy initialization

        self.status_item = rumps.MenuItem("Status: Ready")
        self.history_item = rumps.MenuItem("Show History")
        self.quit_item = rumps.MenuItem("Quit Dictator")
        self.menu = [self.status_item, None, self.history_item, None, self.quit_item]

        self.duration_timer = None

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
            rumps.notification(
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
            rumps.notification(
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
            text = self.transcriber.transcribe(audio_path)

            recording = self.storage.save(audio_path, text, duration)

            success = self.inserter.insert_text(text)

            if success:
                rumps.notification(
                    "Text Inserted",
                    "",
                    text[:100] + ("..." if len(text) > 100 else ""),
                )
            else:
                logger.info("Text insertion failed, copying to clipboard")
                # Copy to clipboard on main thread and show notification
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._copy_and_notify(text)
                )

            logger.info(f"Transcription complete: {len(text)} chars")

        except FileNotFoundError:
            logger.error("Audio file not found")
            rumps.notification(
                "Error",
                "",
                "Recording file not found. Please try again.",
            )

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            rumps.notification(
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
            self.history_window = HistoryWindow(self.storage)
        else:
            # Reload recordings if window already exists
            self.history_window.load_recordings()

        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()
        logger.info("History window opened")

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
        rumps.notification(
            "Text Copied to Clipboard",
            "",
            f"{text[:200]}\n\nGrant accessibility permissions in System Settings to auto-paste.",
        )
