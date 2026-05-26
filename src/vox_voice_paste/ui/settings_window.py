# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vox_voice_paste.config import (
    DEFAULT_TRANSCRIPTION_DELAY,
    DEFAULT_TRANSCRIPTION_MODEL,
    EXPERT_TRANSCRIPTION_DELAY,
    OPENAI_TRANSCRIPTION_PROVIDER,
    SONIOX_TRANSCRIPTION_PROVIDER,
    default_config_path,
    load_config,
    save_config,
)
from vox_voice_paste.desktop import (
    ClipboardError,
    ClipboardService,
    ShortcutInstallError,
    SystemClipboardService,
    set_ubuntu_shortcut,
)
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    SONIOX_API_KEY_SECRET,
    APIKeyValidator,
    KeyringSecretService,
    OpenAIHTTPKeyValidator,
    OpenAIKeyValidator,
    SecretService,
    SonioxHTTPKeyValidator,
)

from .api_key_dialog import OpenAIKeyDialog
from .onboarding_window import RECOMMENDED_SHORTCUT, SHORTCUT_COMMAND


class SettingsWindow(QDialog):
    def __init__(
        self,
        *,
        config_path: Path | None = None,
        secret_service: SecretService | None = None,
        key_validator: OpenAIKeyValidator | None = None,
        parent: QWidget | None = None,
        clipboard_service: ClipboardService | None = None,
        startup_shortcut: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._clipboard = clipboard_service or SystemClipboardService()
        self._secrets = secret_service or KeyringSecretService()
        self._key_validator = key_validator or OpenAIHTTPKeyValidator()
        self._config_path = config_path
        self._config = load_config(config_path)
        resolved_config_path = config_path or default_config_path()
        shortcut_value = startup_shortcut or self._config.ubuntu_shortcut
        self._config.ubuntu_shortcut = shortcut_value
        self.setWindowTitle("VoxClip - Settings")
        self.setMinimumWidth(520)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("OpenAI", OPENAI_TRANSCRIPTION_PROVIDER)
        self.provider_combo.addItem("Soniox", SONIOX_TRANSCRIPTION_PROVIDER)
        self.provider_combo.setCurrentIndex(
            self.provider_combo.findData(self._config.transcription_provider)
        )
        self.provider_combo.currentIndexChanged.connect(self._set_transcription_provider)

        self.key_status = QLabel()
        self.configure_key_button = QPushButton()
        self.configure_key_button.clicked.connect(self.configure_api_key)

        self.shortcut_command = QLineEdit(SHORTCUT_COMMAND)
        self.shortcut_command.setReadOnly(True)
        self.copy_shortcut_button = QPushButton("Copy shortcut command")
        self.copy_shortcut_button.clicked.connect(self.copy_shortcut_command)
        self.shortcut_input = QLineEdit(shortcut_value)
        self.shortcut_input.setPlaceholderText(RECOMMENDED_SHORTCUT)
        self.install_shortcut_button = QPushButton("Install GNOME shortcut")
        self.install_shortcut_button.clicked.connect(self.apply_ubuntu_shortcut)
        self.shortcut_status = QLabel()
        self.transcription_expert_checkbox = QCheckBox("Prioritize transcription accuracy")
        self.transcription_expert_checkbox.setChecked(
            self._config.transcription_delay == EXPERT_TRANSCRIPTION_DELAY
        )
        self.transcription_expert_checkbox.toggled.connect(self._set_transcription_expert_mode)
        self.transcription_expert_warning = QLabel(
            "Higher accuracy can take longer before text appears."
        )
        self.transcription_expert_warning.setWordWrap(True)
        self.transcription_expert_warning.setVisible(
            self.transcription_expert_checkbox.isChecked()
        )
        self._sync_provider_ui()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("VoxClip"))
        layout.addWidget(QLabel(f"Configuration: {resolved_config_path}"))
        layout.addWidget(QLabel(f"Shortcut command: {SHORTCUT_COMMAND}"))
        layout.addWidget(QLabel(f"Recommended shortcut: {RECOMMENDED_SHORTCUT}"))
        layout.addWidget(QLabel("If Ctrl+Alt+N is already used, choose another shortcut."))
        layout.addWidget(QLabel("Transcription backend:"))
        layout.addWidget(self.provider_combo)
        layout.addWidget(QLabel("Active GNOME shortcut:"))
        layout.addWidget(self.shortcut_input)
        layout.addWidget(self.install_shortcut_button)
        layout.addWidget(self.shortcut_command)
        layout.addWidget(self.copy_shortcut_button)
        layout.addWidget(self.shortcut_status)
        layout.addWidget(self.configure_key_button)
        layout.addWidget(self.key_status)
        layout.addWidget(self.transcription_expert_checkbox)
        layout.addWidget(self.transcription_expert_warning)
        layout.addWidget(close_button)
        self.setLayout(layout)

    @Slot()
    def configure_api_key(self) -> None:
        provider = self._config.transcription_provider
        dialog = OpenAIKeyDialog(
            secret_service=self._secrets,
            key_validator=self._active_key_validator(provider),
            secret_name=_api_key_secret_name(provider),
            service_name=_provider_label(provider),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.key_status.setText(f"{_provider_label(provider)} key saved.")
        else:
            self.key_status.setText(f"{_provider_label(provider)} key unchanged.")

    @Slot()
    def configure_openai_key(self) -> None:
        self.configure_api_key()

    @Slot()
    def copy_shortcut_command(self) -> None:
        try:
            self._clipboard.copy_text(SHORTCUT_COMMAND)
        except ClipboardError as exc:
            self.shortcut_status.setText(str(exc))
            return
        self.shortcut_status.setText("Command copied.")

    @Slot()
    def apply_ubuntu_shortcut(self) -> None:
        shortcut = self.shortcut_input.text().strip()
        if not shortcut:
            self.shortcut_status.setText("Shortcut must not be empty.")
            return
        try:
            set_ubuntu_shortcut(shortcut=shortcut, command=SHORTCUT_COMMAND)
        except ShortcutInstallError as exc:
            self.shortcut_status.setText(str(exc))
            return
        self._config.ubuntu_shortcut = shortcut
        save_config(self._config, self._config_path)
        self.shortcut_status.setText(f"GNOME shortcut configured: {shortcut}")

    @Slot()
    def _set_transcription_expert_mode(self, enabled: bool) -> None:
        if self._config.transcription_provider == SONIOX_TRANSCRIPTION_PROVIDER:
            return
        self._config.transcription_model = DEFAULT_TRANSCRIPTION_MODEL
        self._config.transcription_delay = (
            EXPERT_TRANSCRIPTION_DELAY if enabled else DEFAULT_TRANSCRIPTION_DELAY
        )
        self.transcription_expert_warning.setVisible(enabled)
        save_config(self._config, self._config_path)

    @Slot(int)
    def _set_transcription_provider(self, index: int = -1) -> None:
        del index
        provider = self.provider_combo.currentData()
        if provider not in {OPENAI_TRANSCRIPTION_PROVIDER, SONIOX_TRANSCRIPTION_PROVIDER}:
            return
        self._config.transcription_provider = provider
        save_config(self._config, self._config_path)
        self._sync_provider_ui()

    def _sync_provider_ui(self) -> None:
        provider = self._config.transcription_provider
        label = _provider_label(provider)
        self.configure_key_button.setText(f"Configure {label} key")
        self.key_status.setText(f"{label} key is stored in the system keyring.")
        openai_selected = provider == OPENAI_TRANSCRIPTION_PROVIDER
        self.transcription_expert_checkbox.setVisible(openai_selected)
        self.transcription_expert_warning.setVisible(
            openai_selected and self.transcription_expert_checkbox.isChecked()
        )

    def _active_key_validator(self, provider: str) -> APIKeyValidator:
        if provider == SONIOX_TRANSCRIPTION_PROVIDER and isinstance(
            self._key_validator, OpenAIHTTPKeyValidator
        ):
            return SonioxHTTPKeyValidator()
        return self._key_validator


def _api_key_secret_name(provider: str) -> str:
    if provider == SONIOX_TRANSCRIPTION_PROVIDER:
        return SONIOX_API_KEY_SECRET
    return OPENAI_API_KEY_SECRET


def _provider_label(provider: str) -> str:
    if provider == SONIOX_TRANSCRIPTION_PROVIDER:
        return "Soniox"
    return "OpenAI"
