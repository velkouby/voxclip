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
    DEFAULT_TRANSLATION_UBUNTU_SHORTCUT,
    EXPERT_TRANSCRIPTION_DELAY,
    default_config_path,
    load_config,
    normalize_language_code,
    save_config,
)
from vox_voice_paste.desktop import (
    ClipboardError,
    ClipboardService,
    ShortcutInstallError,
    SystemClipboardService,
    set_ubuntu_shortcut,
)
from vox_voice_paste.desktop.shortcuts import (
    DEFAULT_TRANSLATION_SHORTCUT_COMMAND,
    TRANSLATION_MANAGED_SHORTCUT_PATH,
    TRANSLATION_SHORTCUT_LABEL,
)
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    SONIOX_API_KEY_SECRET,
    KeyringSecretService,
    OpenAIHTTPKeyValidator,
    OpenAIKeyValidator,
    SecretService,
    SonioxHTTPKeyValidator,
)

from .api_key_dialog import OpenAIKeyDialog
from .onboarding_window import RECOMMENDED_SHORTCUT, SHORTCUT_COMMAND

TRANSLATION_LANGUAGE_OPTIONS = [
    ("English", "en"),
    ("French", "fr"),
    ("Spanish", "es"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Dutch", "nl"),
]


class SettingsWindow(QDialog):
    def __init__(
        self,
        *,
        config_path: Path | None = None,
        secret_service: SecretService | None = None,
        key_validator: OpenAIKeyValidator | None = None,
        soniox_key_validator: OpenAIKeyValidator | None = None,
        parent: QWidget | None = None,
        clipboard_service: ClipboardService | None = None,
        startup_shortcut: str | None = None,
        startup_translation_shortcut: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._clipboard = clipboard_service or SystemClipboardService()
        self._secrets = secret_service or KeyringSecretService()
        self._key_validator = key_validator or OpenAIHTTPKeyValidator()
        self._soniox_key_validator = soniox_key_validator or SonioxHTTPKeyValidator()
        self._config_path = config_path
        self._config = load_config(config_path)
        resolved_config_path = config_path or default_config_path()
        shortcut_value = startup_shortcut or self._config.ubuntu_shortcut
        translation_shortcut_value = (
            startup_translation_shortcut or self._config.translation_ubuntu_shortcut
        )
        self._config.ubuntu_shortcut = shortcut_value
        self._config.translation_ubuntu_shortcut = translation_shortcut_value
        self.setWindowTitle("VoxClip - Settings")
        self.setMinimumWidth(520)

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

        self.key_status = QLabel(self._key_status_text())
        self.configure_key_button = QPushButton()
        self.configure_key_button.clicked.connect(self.configure_api_key)
        self._sync_provider_controls()

        self.shortcut_command = QLineEdit(SHORTCUT_COMMAND)
        self.shortcut_command.setReadOnly(True)
        self.copy_shortcut_button = QPushButton("Copy shortcut command")
        self.copy_shortcut_button.clicked.connect(self.copy_shortcut_command)
        self.shortcut_input = QLineEdit(shortcut_value)
        self.shortcut_input.setPlaceholderText(RECOMMENDED_SHORTCUT)
        self.install_shortcut_button = QPushButton("Install GNOME shortcut")
        self.install_shortcut_button.clicked.connect(self.apply_ubuntu_shortcut)
        self.shortcut_status = QLabel()

        self.translation_shortcut_command = QLineEdit(DEFAULT_TRANSLATION_SHORTCUT_COMMAND)
        self.translation_shortcut_command.setReadOnly(True)
        self.copy_translation_shortcut_button = QPushButton(
            "Copy translation shortcut command"
        )
        self.copy_translation_shortcut_button.clicked.connect(
            self.copy_translation_shortcut_command
        )
        self.translation_shortcut_input = QLineEdit(translation_shortcut_value)
        self.translation_shortcut_input.setPlaceholderText(
            DEFAULT_TRANSLATION_UBUNTU_SHORTCUT
        )
        self.install_translation_shortcut_button = QPushButton(
            "Install GNOME translation shortcut"
        )
        self.install_translation_shortcut_button.clicked.connect(
            self.apply_translation_ubuntu_shortcut
        )
        self.translation_shortcut_status = QLabel()

        self.translation_language_combo = QComboBox()
        for label, language_code in TRANSLATION_LANGUAGE_OPTIONS:
            self.translation_language_combo.addItem(f"{label} ({language_code})", language_code)
        target_language = normalize_language_code(self._config.translation_target_language)
        language_index = self.translation_language_combo.findData(target_language)
        if target_language and language_index < 0:
            self.translation_language_combo.addItem(
                f"Custom ({target_language})",
                target_language,
            )
            language_index = self.translation_language_combo.findData(target_language)
        self.translation_language_combo.setCurrentIndex(max(language_index, 0))
        self.translation_language_combo.currentIndexChanged.connect(
            self._set_translation_target_language
        )

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

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("VoxClip"))
        layout.addWidget(QLabel(f"Configuration: {resolved_config_path}"))
        layout.addWidget(QLabel(f"Shortcut command: {SHORTCUT_COMMAND}"))
        layout.addWidget(QLabel(f"Recommended shortcut: {RECOMMENDED_SHORTCUT}"))
        layout.addWidget(QLabel("If Ctrl+Alt+N is already used, choose another shortcut."))
        layout.addWidget(QLabel("Active GNOME shortcut:"))
        layout.addWidget(self.shortcut_input)
        layout.addWidget(self.install_shortcut_button)
        layout.addWidget(self.shortcut_command)
        layout.addWidget(self.copy_shortcut_button)
        layout.addWidget(self.shortcut_status)
        layout.addWidget(QLabel(f"Translation command: {DEFAULT_TRANSLATION_SHORTCUT_COMMAND}"))
        layout.addWidget(QLabel("Recommended translation shortcut: Ctrl+Alt+M"))
        layout.addWidget(QLabel("Active GNOME translation shortcut:"))
        layout.addWidget(self.translation_shortcut_input)
        layout.addWidget(self.install_translation_shortcut_button)
        layout.addWidget(self.translation_shortcut_command)
        layout.addWidget(self.copy_translation_shortcut_button)
        layout.addWidget(self.translation_shortcut_status)
        layout.addWidget(QLabel("Translation target language:"))
        layout.addWidget(self.translation_language_combo)
        layout.addWidget(QLabel("Transcription provider:"))
        layout.addWidget(self.transcription_provider_combo)
        layout.addWidget(self.configure_key_button)
        layout.addWidget(self.key_status)
        layout.addWidget(self.transcription_expert_checkbox)
        layout.addWidget(self.transcription_expert_warning)
        layout.addWidget(close_button)
        self.setLayout(layout)

    @Slot()
    def configure_openai_key(self) -> None:
        self.configure_api_key()

    @Slot()
    def configure_api_key(self) -> None:
        provider = self._config.transcription_provider
        label = _provider_label(provider)
        dialog = OpenAIKeyDialog(
            secret_service=self._secrets,
            key_validator=self._provider_validator(provider),
            provider_name=label,
            secret_name=_provider_secret_name(provider),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.key_status.setText(f"{label} key saved.")
        else:
            self.key_status.setText(f"{label} key unchanged.")

    @Slot()
    def copy_shortcut_command(self) -> None:
        try:
            self._clipboard.copy_text(SHORTCUT_COMMAND)
        except ClipboardError as exc:
            self.shortcut_status.setText(str(exc))
            return
        self.shortcut_status.setText("Command copied.")

    @Slot()
    def copy_translation_shortcut_command(self) -> None:
        try:
            self._clipboard.copy_text(DEFAULT_TRANSLATION_SHORTCUT_COMMAND)
        except ClipboardError as exc:
            self.translation_shortcut_status.setText(str(exc))
            return
        self.translation_shortcut_status.setText("Translation command copied.")

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
    def apply_translation_ubuntu_shortcut(self) -> None:
        shortcut = self.translation_shortcut_input.text().strip()
        if not shortcut:
            self.translation_shortcut_status.setText("Shortcut must not be empty.")
            return
        try:
            set_ubuntu_shortcut(
                shortcut=shortcut,
                command=DEFAULT_TRANSLATION_SHORTCUT_COMMAND,
                label=TRANSLATION_SHORTCUT_LABEL,
                managed_path=TRANSLATION_MANAGED_SHORTCUT_PATH,
            )
        except ShortcutInstallError as exc:
            self.translation_shortcut_status.setText(str(exc))
            return
        self._config.translation_ubuntu_shortcut = shortcut
        save_config(self._config, self._config_path)
        self.translation_shortcut_status.setText(
            f"GNOME translation shortcut configured: {shortcut}"
        )

    @Slot()
    def _set_transcription_expert_mode(self, enabled: bool) -> None:
        self._config.transcription_model = DEFAULT_TRANSCRIPTION_MODEL
        self._config.transcription_delay = (
            EXPERT_TRANSCRIPTION_DELAY if enabled else DEFAULT_TRANSCRIPTION_DELAY
        )
        self.transcription_expert_warning.setVisible(enabled)
        save_config(self._config, self._config_path)

    @Slot(int)
    def _set_transcription_provider(self, _index: int = -1) -> None:
        provider = self.transcription_provider_combo.currentData()
        if provider not in {"openai", "soniox"}:
            return
        self._config.transcription_provider = provider
        save_config(self._config, self._config_path)
        self._sync_provider_controls()

    @Slot(int)
    def _set_translation_target_language(self, _index: int = -1) -> None:
        language = normalize_language_code(self.translation_language_combo.currentData())
        if language is None:
            return
        self._config.translation_target_language = language
        save_config(self._config, self._config_path)

    def _sync_provider_controls(self) -> None:
        label = _provider_label(self._config.transcription_provider)
        self.configure_key_button.setText(f"Configure {label} key")
        self.key_status.setText(self._key_status_text())

    def _key_status_text(self) -> str:
        label = _provider_label(self._config.transcription_provider)
        return f"{label} key is stored in the system keyring."

    def _provider_validator(self, provider: str) -> OpenAIKeyValidator:
        return self._soniox_key_validator if provider == "soniox" else self._key_validator


def _provider_label(provider: str) -> str:
    return "Soniox" if provider == "soniox" else "OpenAI"


def _provider_secret_name(provider: str) -> str:
    return SONIOX_API_KEY_SECRET if provider == "soniox" else OPENAI_API_KEY_SECRET
