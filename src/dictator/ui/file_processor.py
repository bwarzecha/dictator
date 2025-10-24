"""File processor UI for transcribing audio files.

Allows users to select audio files and process them through
the same pipeline as voice recordings.
"""

import logging
from pathlib import Path
from typing import Optional
import threading

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QFileDialog,
    QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
import AppKit

from dictator.services.audio_processor import AudioProcessor
from dictator.services.audio_converter import (
    convert_to_wav,
    get_supported_formats_string,
    is_supported_format,
)

logger = logging.getLogger(__name__)


class ProcessingSignals(QObject):
    """Signals for communicating from worker thread to UI."""

    status_updated = pyqtSignal(str)
    processing_complete = pyqtSignal(str, str, bool, bool)
    processing_failed = pyqtSignal(str)


class FileProcessorWindow(QWidget):
    """Window for processing audio files."""

    def __init__(self, audio_processor: AudioProcessor):
        """Initialize file processor window.

        Args:
            audio_processor: AudioProcessor instance for processing
        """
        super().__init__()
        self.audio_processor = audio_processor
        self.signals = ProcessingSignals()
        self.processing = False
        self.converted_file: Optional[Path] = None

        # Connect signals
        self.signals.status_updated.connect(self._on_status_update)
        self.signals.processing_complete.connect(self._on_processing_complete)
        self.signals.processing_failed.connect(self._on_processing_failed)

        self._init_ui()

    def _init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("Process Audio File")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        layout = QVBoxLayout()

        # Instructions
        instructions = QLabel(
            f"Select an audio file to transcribe.\n"
            f"Supported formats: {get_supported_formats_string()}"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # File selection button
        self.select_btn = QPushButton("Select Audio File...")
        self.select_btn.clicked.connect(self._select_file)
        layout.addWidget(self.select_btn)

        # Selected file label
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.file_label)

        # Process button
        self.process_btn = QPushButton("Process File")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self._process_file)
        layout.addWidget(self.process_btn)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Results section
        results_label = QLabel("Transcription Result:")
        results_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(results_label)

        # Text display
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText(
            "Transcription will appear here after processing..."
        )
        layout.addWidget(self.result_text)

        # Action buttons
        button_layout = QHBoxLayout()

        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        button_layout.addWidget(self.copy_btn)

        self.insert_btn = QPushButton("Insert Text")
        self.insert_btn.setEnabled(False)
        self.insert_btn.clicked.connect(self._insert_text)
        button_layout.addWidget(self.insert_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _select_file(self):
        """Open file dialog to select audio file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            str(Path.home()),
            "Audio Files (*.m4a *.mp3 *.wav *.ogg *.mp4 *.flac *.aac);;All Files (*)",
        )

        if file_path:
            self.selected_file = Path(file_path)

            # Validate format
            if not is_supported_format(self.selected_file):
                self.file_label.setText(
                    f"⚠️ Unsupported format: {self.selected_file.suffix}"
                )
                self.file_label.setStyleSheet("color: red;")
                self.process_btn.setEnabled(False)
                return

            # Update UI
            self.file_label.setText(f"📄 {self.selected_file.name}")
            self.file_label.setStyleSheet("color: black;")
            self.process_btn.setEnabled(True)
            self.result_text.clear()
            self.copy_btn.setEnabled(False)
            self.insert_btn.setEnabled(False)

            logger.info(f"File selected: {self.selected_file}")

    def _process_file(self):
        """Start processing the selected file."""
        if not hasattr(self, "selected_file"):
            return

        self.processing = True
        self._update_ui_processing_state(True)

        # Start processing in background thread
        thread = threading.Thread(target=self._process_in_background, daemon=True)
        thread.start()

    def _process_in_background(self):
        """Process audio file in background thread."""
        try:
            # Step 1: Convert to WAV if needed
            self.signals.status_updated.emit("Converting audio format...")

            wav_path, duration = convert_to_wav(
                self.selected_file,
                output_dir=self.audio_processor.storage.recordings_dir,
            )
            self.converted_file = wav_path

            # Step 2: Process through pipeline
            result = self.audio_processor.process(
                wav_path, duration, progress_callback=self.signals.status_updated.emit
            )

            # Step 3: Signal completion
            self.signals.processing_complete.emit(
                result.raw_text,
                result.cleaned_text,
                result.inserted,
                result.correction_failed,
            )

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            self.signals.processing_failed.emit(str(e))

    def _on_status_update(self, status: str):
        """Handle status update from worker thread.

        Args:
            status: Status message
        """
        self.status_label.setText(status)
        logger.info(f"Processing status: {status}")

    def _on_processing_complete(
        self, raw_text: str, cleaned_text: str, inserted: bool, correction_failed: bool
    ):
        """Handle successful processing completion.

        Args:
            raw_text: Raw transcription
            cleaned_text: Cleaned transcription
            inserted: Whether text was inserted
            correction_failed: Whether correction failed
        """
        self.processing = False
        self._update_ui_processing_state(False)

        # Show result
        self.result_text.setPlainText(cleaned_text)
        self.cleaned_text = cleaned_text

        # Update status
        if inserted:
            status = "✅ Processing complete - text inserted!"
        elif correction_failed:
            status = "⚠️ Processing complete (correction failed)"
        else:
            status = "✅ Processing complete!"

        self.status_label.setText(status)
        self.status_label.setStyleSheet("color: green; font-weight: bold;")

        # Enable action buttons
        self.copy_btn.setEnabled(True)
        self.insert_btn.setEnabled(True)

        logger.info("Processing completed successfully")

    def _on_processing_failed(self, error: str):
        """Handle processing failure.

        Args:
            error: Error message
        """
        self.processing = False
        self._update_ui_processing_state(False)

        self.status_label.setText(f"❌ Error: {error}")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")

        logger.error(f"Processing failed: {error}")

    def _update_ui_processing_state(self, processing: bool):
        """Update UI elements based on processing state.

        Args:
            processing: Whether processing is active
        """
        self.select_btn.setEnabled(not processing)
        self.process_btn.setEnabled(not processing)
        self.progress.setVisible(processing)

        if processing:
            self.progress.setRange(0, 0)  # Indeterminate progress
            self.status_label.setStyleSheet("color: blue;")
        else:
            self.progress.setVisible(False)

    def _copy_to_clipboard(self):
        """Copy result to clipboard."""
        if hasattr(self, "cleaned_text"):
            pasteboard = AppKit.NSPasteboard.generalPasteboard()
            pasteboard.clearContents()
            pasteboard.setString_forType_(
                self.cleaned_text, AppKit.NSPasteboardTypeString
            )

            self.status_label.setText("📋 Copied to clipboard!")
            self.status_label.setStyleSheet("color: blue; font-weight: bold;")
            logger.info("Text copied to clipboard")

    def _insert_text(self):
        """Insert result text into focused application."""
        if hasattr(self, "cleaned_text"):
            from dictator.insertion import TextInserter

            inserter = TextInserter()
            success = inserter.insert_text(self.cleaned_text)

            if success:
                self.status_label.setText("✅ Text inserted!")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                logger.info("Text inserted successfully")
            else:
                self.status_label.setText(
                    "⚠️ Insertion failed - copied to clipboard instead"
                )
                self.status_label.setStyleSheet("color: orange; font-weight: bold;")
                self._copy_to_clipboard()

    def closeEvent(self, event):
        """Handle window close event.

        Args:
            event: Close event
        """
        # Clean up converted file if it exists
        if self.converted_file and self.converted_file.exists():
            if self.converted_file != getattr(self, "selected_file", None):
                try:
                    # Only delete if it was a converted file, not the original
                    if "_converted" in self.converted_file.name:
                        logger.info(f"Cleaning up converted file: {self.converted_file}")
                        # Note: We keep the file for history - don't delete
                except Exception as e:
                    logger.warning(f"Failed to clean up converted file: {e}")

        event.accept()
