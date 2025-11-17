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
from dictator.services.model_manager import WhisperModelManager
from dictator.ui.model_download_dialog import ModelDownloadDialog

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
        self.model_manager = WhisperModelManager()
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

        # Silence Removal Settings
        silence_group = self._create_silence_removal_settings()
        layout.addWidget(silence_group)

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

        # Model selection with enhanced display
        model_layout = QHBoxLayout()

        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.setMinimumWidth(300)

        # Populate with models showing sizes and status
        all_models = self.model_manager.get_all_models()
        for model_info in all_models:
            is_downloaded = self.model_manager.is_model_downloaded(model_info.name)
            status_icon = "✓" if is_downloaded else "○"
            display_text = f"{status_icon} {model_info.display_name} - {model_info.description}"
            self.whisper_model_combo.addItem(display_text, model_info.name)

        # Set current selection
        current_index = self._find_model_index(self.config.whisper_model)
        if current_index >= 0:
            self.whisper_model_combo.setCurrentIndex(current_index)

        self.whisper_model_combo.setEditable(True)
        model_layout.addWidget(self.whisper_model_combo)

        # Download button
        self.download_model_button = QPushButton("Download")
        self.download_model_button.clicked.connect(self._download_selected_model)
        self.download_model_button.setToolTip("Download the selected model")
        model_layout.addWidget(self.download_model_button)

        layout.addRow("Model:", model_layout)

        # Model status info
        self.model_status_label = QLabel()
        self.model_status_label.setWordWrap(True)
        self._update_model_status()
        self.whisper_model_combo.currentIndexChanged.connect(self._update_model_status)
        layout.addRow("Status:", self.model_status_label)

        # Thread count
        self.whisper_threads_spin = QSpinBox()
        self.whisper_threads_spin.setMinimum(1)
        self.whisper_threads_spin.setMaximum(32)
        self.whisper_threads_spin.setValue(self.config.whisper_threads)
        self.whisper_threads_spin.setToolTip("More threads = faster transcription (uses more CPU)")
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

    def _create_silence_removal_settings(self) -> QGroupBox:
        """Create silence removal settings group."""
        group = QGroupBox("Silence Removal (Experimental)")
        layout = QFormLayout()

        # Enable/disable checkbox
        self.silence_removal_checkbox = QCheckBox("Remove silence from recordings")
        self.silence_removal_checkbox.setChecked(self.config.remove_silence_enabled)
        self.silence_removal_checkbox.setToolTip(
            "Removes long pauses to speed up processing. May reduce accuracy slightly."
        )
        self.silence_removal_checkbox.toggled.connect(self._on_silence_removal_toggled)
        layout.addRow(self.silence_removal_checkbox)

        # Threshold setting
        self.silence_threshold_spin = QSpinBox()
        self.silence_threshold_spin.setMinimum(1)
        self.silence_threshold_spin.setMaximum(100)
        self.silence_threshold_spin.setValue(int(self.config.silence_threshold * 1000))
        self.silence_threshold_spin.setSuffix(" (1/1000)")
        self.silence_threshold_spin.setToolTip("Lower = more sensitive to quiet sounds")
        self.silence_threshold_spin.setEnabled(self.config.remove_silence_enabled)
        layout.addRow("Silence threshold:", self.silence_threshold_spin)

        # Minimum duration setting
        self.min_silence_duration_spin = QSpinBox()
        self.min_silence_duration_spin.setMinimum(100)
        self.min_silence_duration_spin.setMaximum(2000)
        self.min_silence_duration_spin.setValue(int(self.config.min_silence_duration * 1000))
        self.min_silence_duration_spin.setSingleStep(100)
        self.min_silence_duration_spin.setSuffix(" ms")
        self.min_silence_duration_spin.setToolTip("Minimum silence duration to remove")
        self.min_silence_duration_spin.setEnabled(self.config.remove_silence_enabled)
        layout.addRow("Min silence duration:", self.min_silence_duration_spin)

        # Info label
        info_label = QLabel(
            "⚠️ Experimental: May speed up processing on slower machines.\n"
            "Test with your typical recordings to ensure accuracy."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addRow(info_label)

        group.setLayout(layout)
        return group

    def _on_silence_removal_toggled(self, checked: bool):
        """Handle silence removal checkbox toggle."""
        self.silence_threshold_spin.setEnabled(checked)
        self.min_silence_duration_spin.setEnabled(checked)

    def _find_model_index(self, model_name: str) -> int:
        """Find index of model in combo box by name.

        Args:
            model_name: Name of model to find

        Returns:
            Index in combo box, or -1 if not found
        """
        for i in range(self.whisper_model_combo.count()):
            if self.whisper_model_combo.itemData(i) == model_name:
                return i
        return -1

    def _get_selected_model_name(self) -> str:
        """Get the currently selected model name.

        Returns:
            Model name (e.g., "small", "large-v3")
        """
        # Try to get from itemData first
        index = self.whisper_model_combo.currentIndex()
        if index >= 0:
            model_name = self.whisper_model_combo.itemData(index)
            if model_name:
                return model_name

        # Fallback: parse from text (for custom entries)
        text = self.whisper_model_combo.currentText().strip()
        # Extract model name from display text (after status icon)
        if text.startswith("✓ ") or text.startswith("○ "):
            text = text[2:].strip()

        # Extract just the model name (before size in parentheses)
        if " (" in text:
            text = text.split(" (")[0].strip()

        # Extract before description dash
        if " - " in text:
            text = text.split(" - ")[0].strip()

        return text

    def _update_model_status(self):
        """Update the model status label."""
        model_name = self._get_selected_model_name()
        model_info = self.model_manager.get_model_info(model_name)
        is_downloaded = self.model_manager.is_model_downloaded(model_name)

        if is_downloaded:
            status = "✓ <b>Downloaded</b> - Ready to use"
            self.download_model_button.setEnabled(False)
            self.download_model_button.setText("Downloaded")
        else:
            if model_info:
                available_space = self.model_manager.get_available_disk_space()
                space_needed = model_info.size_mb

                if available_space < space_needed:
                    status = f"⚠ <b>Not downloaded</b> - Insufficient disk space (need {space_needed}MB, have {available_space}MB)"
                    self.download_model_button.setEnabled(False)
                else:
                    status = f"○ <b>Not downloaded</b> - Will download {model_info.size_mb}MB on first use or click Download"
                    self.download_model_button.setEnabled(True)
                    self.download_model_button.setText("Download")
            else:
                status = "○ <b>Not downloaded</b> - Custom model"
                self.download_model_button.setEnabled(True)
                self.download_model_button.setText("Download")

        self.model_status_label.setText(status)

    def _download_selected_model(self):
        """Download the currently selected model."""
        model_name = self._get_selected_model_name()
        model_info = self.model_manager.get_model_info(model_name)

        logger.info("User requested model download", extra={"model": model_name})

        # Show download dialog
        dialog = ModelDownloadDialog(
            model_name=model_name,
            model_info=model_info,
            parent=self,
        )

        # Start download
        dialog.start_download()

        # Show dialog (modal)
        result = dialog.exec()

        # Update status after dialog closes
        self._update_model_status()

        # Refresh combo box to update checkmarks
        current_model = self._get_selected_model_name()
        self._refresh_model_combo()

        # Restore selection
        new_index = self._find_model_index(current_model)
        if new_index >= 0:
            self.whisper_model_combo.setCurrentIndex(new_index)

    def _refresh_model_combo(self):
        """Refresh the model combo box with updated download status."""
        # Save current selection
        current_model = self._get_selected_model_name()

        # Clear and repopulate
        self.whisper_model_combo.clear()
        all_models = self.model_manager.get_all_models()
        for model_info in all_models:
            is_downloaded = self.model_manager.is_model_downloaded(model_info.name)
            status_icon = "✓" if is_downloaded else "○"
            display_text = f"{status_icon} {model_info.display_name} - {model_info.description}"
            self.whisper_model_combo.addItem(display_text, model_info.name)

        # Restore selection
        new_index = self._find_model_index(current_model)
        if new_index >= 0:
            self.whisper_model_combo.setCurrentIndex(new_index)

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

            # Get selected model name
            selected_model = self._get_selected_model_name()

            # Log what's being saved
            logger.info(
                "Saving settings",
                extra={
                    "whisper_model": selected_model,
                    "whisper_threads": self.whisper_threads_spin.value(),
                    "vocab_count": len(vocabulary),
                    "llm_enabled": self.llm_enabled_checkbox.isChecked(),
                }
            )

            # Create updated config
            updated_config = AppConfig(
                recordings_dir=self.config.recordings_dir,
                whisper_model=selected_model,
                whisper_threads=self.whisper_threads_spin.value(),
                custom_vocabulary=vocabulary,
                llm_correction_enabled=self.llm_enabled_checkbox.isChecked(),
                llm_provider="bedrock",
                aws_profile=self.aws_profile_edit.text().strip(),
                bedrock_model=self.bedrock_model_edit.text().strip(),
                bedrock_region=self.bedrock_region_combo.currentText().strip(),
                correction_prompt=self.correction_prompt_edit.toPlainText().strip(),
                remove_silence_enabled=self.silence_removal_checkbox.isChecked(),
                silence_threshold=self.silence_threshold_spin.value() / 1000.0,
                min_silence_duration=self.min_silence_duration_spin.value() / 1000.0,
            )

            logger.info(f"✓ Settings saved with Whisper model: {selected_model}")

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
