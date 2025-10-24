"""Model download progress dialog."""

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QHBoxLayout,
)

from dictator.services.model_manager import WhisperModelManager, ModelInfo

logger = logging.getLogger(__name__)


class DownloadSignals(QObject):
    """Signals for model download completion.

    Qt signals must be defined on QObject subclass.
    """

    download_completed = pyqtSignal(bool, str)  # success, message


class ModelDownloadDialog(QDialog):
    """Dialog showing model download progress."""

    def __init__(
        self,
        model_name: str,
        model_info: Optional[ModelInfo] = None,
        parent=None,
    ):
        """Initialize download dialog.

        Args:
            model_name: Name of model being downloaded
            model_info: Optional model metadata
            parent: Parent widget
        """
        super().__init__(parent)
        self.model_name = model_name
        self.model_info = model_info
        self.model_manager = WhisperModelManager()
        self.download_thread = None
        self.signals = DownloadSignals()

        # Connect signal
        self.signals.download_completed.connect(self._on_completed)

        self._init_ui()

    def _init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("Downloading Model")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(150)

        layout = QVBoxLayout()
        layout.setSpacing(20)

        # Title
        if self.model_info:
            title = f"Downloading {self.model_info.display_name}"
            subtitle = f"This may take a few minutes depending on your connection"
        else:
            title = f"Downloading {self.model_name}"
            subtitle = "This may take a few minutes"

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.title_label.font()
        font.setPointSize(14)
        font.setBold(True)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        # Subtitle with size info
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_label)

        # Status label (simple text, no progress bar)
        self.status_label = QLabel("Downloading...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_font = self.status_label.font()
        status_font.setPointSize(12)
        self.status_label.setFont(status_font)
        layout.addWidget(self.status_label)

        # Spacer
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Run in Background")
        self.cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def start_download(self):
        """Start the model download."""
        logger.info("Starting download dialog", extra={"model": self.model_name})

        self.download_thread = self.model_manager.download_model_async(
            model_name=self.model_name,
            completion_callback=self._completion_callback,
        )

    def _completion_callback(self, success: bool, message: str):
        """Called from download thread when complete.

        Args:
            success: Whether download succeeded
            message: Status message
        """
        # Emit signal to update UI from main thread
        self.signals.download_completed.emit(success, message)

    def _on_completed(self, success: bool, message: str):
        """Handle download completion in main thread.

        Args:
            success: Whether download succeeded
            message: Status message
        """
        if success:
            self.status_label.setText("✓ Download complete!")
            logger.info("Download completed successfully", extra={"model": self.model_name})

            # Auto-close after successful download
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, self.accept)  # Close after 1 second
        else:
            self.status_label.setText(f"✗ Download failed")
            self.subtitle_label.setText(message)
            logger.error("Download failed", extra={"model": self.model_name, "error": message})

            # Change button to "Close" on failure
            self.cancel_button.setText("Close")
            self.cancel_button.clicked.disconnect()
            self.cancel_button.clicked.connect(self.reject)

    def _on_cancel(self):
        """Handle cancel/background button click."""
        logger.info("Download running in background", extra={"model": self.model_name})

        # Download continues in background, just close dialog
        self.reject()

    def closeEvent(self, event):
        """Handle dialog close.

        Args:
            event: Close event
        """
        # Allow closing - download continues in background
        logger.info("Dialog closed, download continues in background")
        event.accept()
