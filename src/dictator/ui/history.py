"""Qt-based history window for viewing past recordings.

Shows recordings in a table with copy buttons.
"""

import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QApplication,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from dictator.storage import RecordingStorage
from dictator.services.llm_corrector import LLMCorrector

logger = logging.getLogger(__name__)


class HistoryWindow(QMainWindow):
    """Qt-based history window with table layout."""

    def __init__(self, storage: RecordingStorage, llm_corrector: Optional[LLMCorrector] = None):
        """Initialize history window.

        Args:
            storage: RecordingStorage instance
            llm_corrector: Optional LLM corrector for re-running corrections
        """
        super().__init__()
        self.storage = storage
        self.llm_corrector = llm_corrector
        self.setWindowTitle("Dictator History")
        self.setGeometry(100, 100, 1000, 600)

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Time", "Recording", "Status", ""])

        # Configure table
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 180)

        # Enable word wrap
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

        # Load recordings
        self.load_recordings()

    def load_recordings(self):
        """Load and display all recordings in table."""
        recordings = self.storage.load_all()

        if not recordings:
            self.table.setRowCount(1)
            item = QTableWidgetItem("No recordings yet. Press Option+Space to create your first recording!")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(0, 1, item)
            self.table.setSpan(0, 0, 1, 3)
            return

        # Sort newest first
        recordings = sorted(recordings, key=lambda r: r.timestamp, reverse=True)

        # Show last 50
        recordings = recordings[:50]
        self.table.setRowCount(len(recordings))

        # Populate table
        for row, rec in enumerate(recordings):
            # Time column
            time_item = QTableWidgetItem(self._format_timestamp(rec.timestamp))
            time_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, time_item)

            # Recording text column - show cleaned version if available
            display_text = rec.cleaned_transcription if rec.cleaned_transcription else rec.transcription
            text_item = QTableWidgetItem(display_text)
            text_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, text_item)

            # Status column
            if rec.cleaned_transcription:
                status_item = QTableWidgetItem("✓ Corrected")
            else:
                status_item = QTableWidgetItem("Raw")
            status_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 2, status_item)

            # Action buttons - centered in a container
            button_container = QWidget()
            button_layout = QHBoxLayout(button_container)
            button_layout.setContentsMargins(5, 5, 5, 5)
            button_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            button_layout.setSpacing(5)

            copy_btn = QPushButton("📋")
            copy_btn.setFixedSize(35, 30)
            copy_btn.setToolTip("Copy to clipboard")
            copy_btn.clicked.connect(lambda checked, text=display_text: self._copy_to_clipboard(text))
            button_layout.addWidget(copy_btn)

            # Add re-run correction button if LLM corrector is available
            if self.llm_corrector:
                rerun_btn = QPushButton("⟳")
                rerun_btn.setFixedSize(35, 30)
                rerun_btn.setToolTip("Re-run LLM correction")
                rerun_btn.clicked.connect(lambda checked, r=rec: self._rerun_correction(r))
                button_layout.addWidget(rerun_btn)

            button_layout.addStretch()

            self.table.setCellWidget(row, 3, button_container)

        logger.info(f"Loaded {len(recordings)} recordings into history window")

    def set_llm_corrector(self, corrector: Optional[LLMCorrector]):
        """Update the LLM corrector and reload recordings.

        Args:
            corrector: New LLM corrector instance
        """
        self.llm_corrector = corrector
        self.load_recordings()

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard.

        Args:
            text: Text to copy
        """
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        logger.info(f"Copied to clipboard: {text[:50]}...")

    def _rerun_correction(self, recording):
        """Re-run LLM correction on a recording.

        Args:
            recording: Recording object to correct
        """
        if not self.llm_corrector:
            QMessageBox.warning(
                self,
                "No LLM Corrector",
                "LLM correction is not enabled. Please enable it in Settings.",
            )
            return

        try:
            # Show progress
            QMessageBox.information(
                self,
                "Running Correction",
                "Correcting transcript...\n\nThis may take a few seconds.",
            )

            # Run correction
            cleaned_text = self.llm_corrector.correct(recording.transcription)

            # Update recording
            recording.cleaned_transcription = cleaned_text
            self.storage.update(recording)

            # Reload UI
            self.load_recordings()

            QMessageBox.information(
                self,
                "Correction Complete",
                "Transcript has been corrected successfully!",
            )

            logger.info(f"Re-ran correction for recording: {recording.audio_path}")

        except Exception as e:
            logger.error(f"Failed to re-run correction: {e}")
            QMessageBox.critical(
                self,
                "Correction Failed",
                f"Failed to correct transcript:\n\n{str(e)}",
            )

    def _format_timestamp(self, dt: datetime) -> str:
        """Format timestamp for display.

        Args:
            dt: Datetime to format

        Returns:
            Formatted string
        """
        now = datetime.now()

        if dt.date() == now.date():
            return dt.strftime("Today %H:%M")
        elif (now - dt).days == 1:
            return dt.strftime("Yesterday %H:%M")
        elif (now - dt).days < 7:
            return dt.strftime("%A %H:%M")
        else:
            return dt.strftime("%b %d, %H:%M")
