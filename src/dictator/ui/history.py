"""Qt-based history window for viewing past recordings.

Shows recordings in a table with copy buttons.
"""

import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QApplication
)
from PyQt6.QtCore import Qt

from dictator.storage import RecordingStorage

logger = logging.getLogger(__name__)


class HistoryWindow(QMainWindow):
    """Qt-based history window with table layout."""

    def __init__(self, storage: RecordingStorage):
        """Initialize history window.

        Args:
            storage: RecordingStorage instance
        """
        super().__init__()
        self.storage = storage
        self.setWindowTitle("Dictator History")
        self.setGeometry(100, 100, 900, 600)

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Time", "Recording", ""])

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
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 100)

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

            # Recording text column (word-wrapped)
            text_item = QTableWidgetItem(rec.transcription)
            text_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, text_item)

            # Copy button - centered in a container to prevent stretching
            button_container = QWidget()
            button_layout = QVBoxLayout(button_container)
            button_layout.setContentsMargins(5, 5, 5, 5)
            button_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            copy_btn = QPushButton("📋 Copy")
            copy_btn.setFixedHeight(30)
            copy_btn.clicked.connect(lambda checked, text=rec.transcription: self._copy_to_clipboard(text))

            button_layout.addWidget(copy_btn)
            button_layout.addStretch()

            self.table.setCellWidget(row, 2, button_container)

        logger.info(f"Loaded {len(recordings)} recordings into history window")

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard.

        Args:
            text: Text to copy
        """
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        logger.info(f"Copied to clipboard: {text[:50]}...")

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
