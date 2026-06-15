# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from vox_voice_paste.audio import AudioDeviceError, AudioInputDevice, list_input_devices
from vox_voice_paste.config import DEFAULT_UBUNTU_SHORTCUT, load_config, save_config
from vox_voice_paste.desktop import ClipboardError, ClipboardService, SystemClipboardService
from vox_voice_paste.desktop.shortcuts import DEFAULT_SHORTCUT_COMMAND
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    SONIOX_API_KEY_SECRET,
    OpenAIHTTPKeyValidator,
    OpenAIKeyValidator,
    SecretService,
    SonioxHTTPKeyValidator,
)

from .api_key_dialog import OpenAIKeyDialog

SHORTCUT_COMMAND = DEFAULT_SHORTCUT_COMMAND
RECOMMENDED_SHORTCUT = DEFAULT_UBUNTU_SHORTCUT


class OnboardingWindow(QDialog):
    def __init__(
        self,
        *,
        config_path: Path | None = None,
        secret_service: SecretService,
        key_validator: OpenAIKeyValidator | None = None,
        soniox_key_validator: OpenAIKeyValidator | None = None,
        clipboard_service: ClipboardService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._secrets = secret_service
        self._key_validator = key_validator or OpenAIHTTPKeyValidator()
        self._soniox_key_validator = soniox_key_validator or SonioxHTTPKeyValidator()
        self._clipboard = clipboard_service or SystemClipboardService()
        self._config = load_config(config_path)

        self.setWindowTitle("VoxClip - Setup")
        self.setMinimumWidth(560)
        self._build_ui()
        self._load_devices()
        self._sync_buttons()

    def _build_ui(self) -> None:
        self.pages = QStackedWidget()
        self.pages.addWidget(self._welcome_page())
        self.pages.addWidget(self._key_page())
        self.pages.addWidget(self._microphone_page())
        self.pages.addWidget(self._shortcut_page())
        self.pages.addWidget(self._finish_page())
        self.pages.currentChanged.connect(lambda _: self._sync_buttons())

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.back)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next)
        self.finish_button = QPushButton("Finish")
        self.finish_button.clicked.connect(self.finish)

        buttons = QHBoxLayout()
        buttons.addWidget(self.back_button)
        buttons.addStretch()
        buttons.addWidget(self.next_button)
        buttons.addWidget(self.finish_button)

        layout = QVBoxLayout()
        layout.addWidget(self.pages)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Welcome to VoxClip"))
        layout.addWidget(QLabel("VoxClip copies the final transcript; you paste it with Ctrl+V."))
        layout.addWidget(QLabel("Live transcription sends microphone audio to the selected API."))
        page.setLayout(layout)
        return page

    def _key_page(self) -> QWidget:
        page = QWidget()
        self.transcription_provider_combo = QComboBox()
        self.transcription_provider_combo.addItem("OpenAI", "openai")
        self.transcription_provider_combo.addItem("Soniox", "soniox")
        provider_index = self.transcription_provider_combo.findData(
            self._config.transcription_provider
        )
        self.transcription_provider_combo.setCurrentIndex(max(provider_index, 0))
        self.transcription_provider_combo.currentIndexChanged.connect(
            self._set_transcription_provider
        )
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText(f"{self._provider_label()} API key")
        self.key_status = QLabel("Key not verified")
        self.store_key_button = QPushButton("Save key")
        self.store_key_button.clicked.connect(self.store_key)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Transcription provider"))
        layout.addWidget(self.transcription_provider_combo)
        layout.addWidget(QLabel("API key"))
        layout.addWidget(self.key_input)
        layout.addWidget(self.store_key_button)
        layout.addWidget(self.key_status)
        page.setLayout(layout)
        return page

    def _microphone_page(self) -> QWidget:
        page = QWidget()
        self.microphone_combo = QComboBox()
        self.audio_status = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Microphone"))
        layout.addWidget(self.microphone_combo)
        layout.addWidget(self.audio_status)
        page.setLayout(layout)
        return page

    def _shortcut_page(self) -> QWidget:
        page = QWidget()
        self.shortcut_command = QLineEdit(SHORTCUT_COMMAND)
        self.shortcut_command.setReadOnly(True)
        self.copy_shortcut_button = QPushButton("Copy command")
        self.copy_shortcut_button.clicked.connect(self.copy_shortcut_command)
        self.shortcut_status = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Ubuntu shortcut"))
        layout.addWidget(QLabel("Create a custom keyboard shortcut with this command."))
        layout.addWidget(QLabel(f"Recommended shortcut: {RECOMMENDED_SHORTCUT}"))
        layout.addWidget(self.shortcut_command)
        layout.addWidget(self.copy_shortcut_button)
        layout.addWidget(self.shortcut_status)
        page.setLayout(layout)
        return page

    def _finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Setup complete"))
        page.setLayout(layout)
        return page

    def _load_devices(self) -> None:
        self.microphone_combo.clear()
        try:
            devices = list_input_devices()
        except AudioDeviceError as exc:
            devices = []
            self.audio_status.setText(str(exc))
        else:
            self.audio_status.setText("Select the microphone to use.")

        if not devices:
            self.microphone_combo.addItem("System default microphone", None)
            return

        for device in devices:
            self.microphone_combo.addItem(_device_label(device), device.id)

    @Slot()
    def store_key(self) -> None:
        value = self.key_input.text().strip()
        if not value:
            self.key_status.setText("Key is empty.")
            return
        provider = self._config.transcription_provider
        dialog = OpenAIKeyDialog(
            secret_service=self._secrets,
            key_validator=self._provider_validator(provider),
            provider_name=self._provider_label(),
            secret_name=_provider_secret_name(provider),
            parent=self,
        )
        dialog.key_input.setText(value)
        dialog.save_key()
        if dialog.result() == QDialog.DialogCode.Accepted:
            self.key_input.clear()
            self.key_status.setText("Key verified and stored in the keyring.")
        else:
            self.key_status.setText(dialog.status_label.text())

    @Slot()
    def copy_shortcut_command(self) -> None:
        try:
            self._clipboard.copy_text(SHORTCUT_COMMAND)
        except ClipboardError as exc:
            self.shortcut_status.setText(str(exc))
            return
        self.shortcut_status.setText("Command copied.")

    @Slot()
    def back(self) -> None:
        index = self.pages.currentIndex()
        if index > 0:
            self.pages.setCurrentIndex(index - 1)

    @Slot()
    def next(self) -> None:
        index = self.pages.currentIndex()
        if index < self.pages.count() - 1:
            self.pages.setCurrentIndex(index + 1)

    @Slot()
    def finish(self) -> None:
        self._config.onboarding_completed = True
        self._config.default_input_device_id = self.microphone_combo.currentData()
        save_config(self._config, self._config_path)
        self.accept()

    @Slot(int)
    def _set_transcription_provider(self, _index: int = -1) -> None:
        provider = self.transcription_provider_combo.currentData()
        if provider not in {"openai", "soniox"}:
            return
        self._config.transcription_provider = provider
        self.key_input.setPlaceholderText(f"{self._provider_label()} API key")
        self.key_status.setText("Key not verified")
        save_config(self._config, self._config_path)

    def _provider_label(self) -> str:
        return "Soniox" if self._config.transcription_provider == "soniox" else "OpenAI"

    def _provider_validator(self, provider: str) -> OpenAIKeyValidator:
        return self._soniox_key_validator if provider == "soniox" else self._key_validator

    def _sync_buttons(self) -> None:
        index = self.pages.currentIndex()
        last_index = self.pages.count() - 1
        self.back_button.setEnabled(index > 0)
        self.next_button.setVisible(index < last_index)
        self.finish_button.setVisible(index == last_index)


def _device_label(device: AudioInputDevice) -> str:
    marker = " (default)" if device.is_default else ""
    return f"{device.name}{marker}"


def _provider_secret_name(provider: str) -> str:
    return SONIOX_API_KEY_SECRET if provider == "soniox" else OPENAI_API_KEY_SECRET
