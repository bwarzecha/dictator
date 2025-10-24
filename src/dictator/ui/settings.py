"""Settings window for Dictator configuration."""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dictator.models import AppConfig
from dictator.services.llm_corrector import BedrockLLMProvider

logger = logging.getLogger(__name__)


class SettingsWindow(QWidget):
    """Settings window for app configuration."""

    config_changed = pyqtSignal(AppConfig)

    def __init__(self, config: AppConfig):
        """Initialize settings window.

        Args:
            config: Current application configuration
        """
        super().__init__()
        self.config = config
        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        self.setWindowTitle("Dictator Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)

        layout = QVBoxLayout()

        # Whisper Settings
        whisper_group = self._create_whisper_settings()
        layout.addWidget(whisper_group)

        # LLM Correction Settings
        llm_group = self._create_llm_settings()
        layout.addWidget(llm_group)

        # Buttons
        button_layout = self._create_buttons()
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_whisper_settings(self) -> QGroupBox:
        """Create Whisper settings group."""
        group = QGroupBox("Whisper Transcription")
        layout = QFormLayout()

        # Model selection
        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItems([
            "tiny",
            "base",
            "small",
            "medium",
            "large-v3-turbo",
            "large-v3",
        ])
        self.whisper_model_combo.setCurrentText(self.config.whisper_model)
        self.whisper_model_combo.setEditable(True)
        layout.addRow("Model:", self.whisper_model_combo)

        # Thread count
        self.whisper_threads_spin = QSpinBox()
        self.whisper_threads_spin.setMinimum(1)
        self.whisper_threads_spin.setMaximum(32)
        self.whisper_threads_spin.setValue(self.config.whisper_threads)
        layout.addRow("Threads:", self.whisper_threads_spin)

        # Custom Vocabulary
        vocab_label = QLabel("Custom Vocabulary:")
        vocab_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        vocab_label.setToolTip("One word per line. Technical terms, names, jargon.")

        self.vocabulary_edit = QTextEdit()
        self.vocabulary_edit.setPlainText("\n".join(self.config.custom_vocabulary))
        self.vocabulary_edit.setPlaceholderText("Docker\nKubernetes\nPostgreSQL\nAWS\nBedrock")
        self.vocabulary_edit.setMaximumHeight(100)
        self.vocabulary_edit.setToolTip("Words Whisper should recognize (one per line)")
        layout.addRow(vocab_label, self.vocabulary_edit)

        group.setLayout(layout)
        return group

    def _create_llm_settings(self) -> QGroupBox:
        """Create LLM correction settings group."""
        group = QGroupBox("LLM Transcript Correction")
        layout = QVBoxLayout()

        # Enable toggle
        self.llm_enabled_checkbox = QCheckBox("Enable LLM Correction")
        self.llm_enabled_checkbox.setChecked(self.config.llm_correction_enabled)
        self.llm_enabled_checkbox.stateChanged.connect(self._toggle_llm_settings)
        layout.addWidget(self.llm_enabled_checkbox)

        # Bedrock settings container
        self.bedrock_container = QWidget()
        bedrock_layout = QFormLayout()

        # AWS Profile
        self.aws_profile_edit = QLineEdit()
        self.aws_profile_edit.setText(self.config.aws_profile)
        self.aws_profile_edit.setPlaceholderText("default (leave empty for default AWS credentials)")
        bedrock_layout.addRow("AWS Profile:", self.aws_profile_edit)

        # AWS Region
        self.bedrock_region_combo = QComboBox()
        self.bedrock_region_combo.addItems([
            "us-east-1",
            "us-west-2",
            "eu-west-1",
            "eu-central-1",
            "ap-southeast-1",
            "ap-northeast-1",
        ])
        self.bedrock_region_combo.setCurrentText(self.config.bedrock_region)
        self.bedrock_region_combo.setEditable(True)
        bedrock_layout.addRow("AWS Region:", self.bedrock_region_combo)

        # Bedrock Model
        self.bedrock_model_edit = QLineEdit()
        self.bedrock_model_edit.setText(self.config.bedrock_model)
        self.bedrock_model_edit.setPlaceholderText("us.anthropic.claude-haiku-4-5-20251001-v1:0")
        bedrock_layout.addRow("Bedrock Model:", self.bedrock_model_edit)

        # Test connection button
        self.test_button = QPushButton("Test AWS Connection")
        self.test_button.clicked.connect(self._test_bedrock_connection)
        bedrock_layout.addRow("", self.test_button)

        # Correction Prompt
        prompt_label = QLabel("Correction Prompt:")
        prompt_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.correction_prompt_edit = QTextEdit()
        self.correction_prompt_edit.setPlainText(self.config.correction_prompt)
        self.correction_prompt_edit.setMinimumHeight(200)
        bedrock_layout.addRow(prompt_label, self.correction_prompt_edit)

        self.bedrock_container.setLayout(bedrock_layout)
        layout.addWidget(self.bedrock_container)

        # Enable/disable based on checkbox
        self._toggle_llm_settings()

        group.setLayout(layout)
        return group

    def _create_buttons(self) -> QHBoxLayout:
        """Create save/cancel buttons."""
        layout = QHBoxLayout()
        layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_settings)
        save_btn.setDefault(True)
        layout.addWidget(save_btn)

        return layout

    def _toggle_llm_settings(self):
        """Enable/disable LLM settings based on checkbox."""
        enabled = self.llm_enabled_checkbox.isChecked()
        self.bedrock_container.setEnabled(enabled)

    def _test_bedrock_connection(self):
        """Test AWS Bedrock connection with current settings."""
        try:
            # Get current values
            profile = self.aws_profile_edit.text().strip() or None
            model_id = self.bedrock_model_edit.text().strip()
            region = self.bedrock_region_combo.currentText().strip()
            prompt = self.correction_prompt_edit.toPlainText().strip()

            if not model_id:
                QMessageBox.warning(
                    self,
                    "Missing Model",
                    "Please enter a Bedrock model ID",
                )
                return

            # Get vocabulary
            vocab_text = self.vocabulary_edit.toPlainText()
            vocabulary = [
                word.strip()
                for word in vocab_text.split("\n")
                if word.strip()
            ]

            # Test connection
            self.test_button.setEnabled(False)
            self.test_button.setText("Testing...")

            provider = BedrockLLMProvider(
                model_id=model_id,
                correction_prompt=prompt,
                aws_profile=profile,
                region=region,
                custom_vocabulary=vocabulary,
            )

            success, message = provider.validate_credentials()

            if success:
                QMessageBox.information(
                    self,
                    "Connection Successful",
                    message,
                )
            else:
                QMessageBox.warning(
                    self,
                    "Connection Failed",
                    message,
                )

        except Exception as e:
            logger.error(f"Error testing Bedrock connection: {e}")
            QMessageBox.critical(
                self,
                "Test Failed",
                f"Unexpected error: {str(e)}",
            )

        finally:
            self.test_button.setEnabled(True)
            self.test_button.setText("Test AWS Connection")

    def _save_settings(self):
        """Save settings and emit signal."""
        try:
            # Parse vocabulary (one word per line, ignore empty lines)
            vocab_text = self.vocabulary_edit.toPlainText()
            vocabulary = [
                word.strip()
                for word in vocab_text.split("\n")
                if word.strip()
            ]

            # Create updated config
            updated_config = AppConfig(
                recordings_dir=self.config.recordings_dir,
                whisper_model=self.whisper_model_combo.currentText().strip(),
                whisper_threads=self.whisper_threads_spin.value(),
                custom_vocabulary=vocabulary,
                llm_correction_enabled=self.llm_enabled_checkbox.isChecked(),
                llm_provider="bedrock",
                aws_profile=self.aws_profile_edit.text().strip(),
                bedrock_model=self.bedrock_model_edit.text().strip(),
                bedrock_region=self.bedrock_region_combo.currentText().strip(),
                correction_prompt=self.correction_prompt_edit.toPlainText().strip(),
            )

            # Emit signal
            self.config_changed.emit(updated_config)

            # Show success message
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved successfully.",
            )

            self.close()

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Failed to save settings: {str(e)}",
            )
