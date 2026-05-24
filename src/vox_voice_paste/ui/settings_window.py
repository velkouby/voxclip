from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QDialog,
    QCheckBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vox_voice_paste.config import (
    DEFAULT_TRANSCRIPTION_MODEL,
    EXPERT_TRANSCRIPTION_MODEL,
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
    KeyringSecretService,
    OpenAIHTTPKeyValidator,
    OpenAIKeyValidator,
    SecretService,
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

        self.key_status = QLabel("OpenAI key is stored in the system keyring.")
        self.configure_key_button = QPushButton("Configure OpenAI key")
        self.configure_key_button.clicked.connect(self.configure_openai_key)

        self.shortcut_command = QLineEdit(SHORTCUT_COMMAND)
        self.shortcut_command.setReadOnly(True)
        self.copy_shortcut_button = QPushButton("Copy shortcut command")
        self.copy_shortcut_button.clicked.connect(self.copy_shortcut_command)
        self.shortcut_input = QLineEdit(shortcut_value)
        self.shortcut_input.setPlaceholderText(RECOMMENDED_SHORTCUT)
        self.install_shortcut_button = QPushButton("Install GNOME shortcut")
        self.install_shortcut_button.clicked.connect(self.apply_ubuntu_shortcut)
        self.shortcut_status = QLabel()
        self.transcription_expert_checkbox = QCheckBox("Transcription mode expert")
        self.transcription_expert_checkbox.setChecked(
            self._config.transcription_model == EXPERT_TRANSCRIPTION_MODEL
        )
        self.transcription_expert_checkbox.toggled.connect(self._set_transcription_expert_mode)
        self.transcription_expert_warning = QLabel(
            "Expert mode can cost up to 2x more than the default transcription mode."
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
        layout.addWidget(self.configure_key_button)
        layout.addWidget(self.key_status)
        layout.addWidget(self.transcription_expert_checkbox)
        layout.addWidget(self.transcription_expert_warning)
        layout.addWidget(close_button)
        self.setLayout(layout)

    @Slot()
    def configure_openai_key(self) -> None:
        dialog = OpenAIKeyDialog(
            secret_service=self._secrets,
            key_validator=self._key_validator,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.key_status.setText("OpenAI key saved.")
        else:
            self.key_status.setText("OpenAI key unchanged.")

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
        self._config.transcription_model = (
            EXPERT_TRANSCRIPTION_MODEL if enabled else DEFAULT_TRANSCRIPTION_MODEL
        )
        self.transcription_expert_warning.setVisible(enabled)
        save_config(self._config, self._config_path)
