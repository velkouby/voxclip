from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vox_voice_paste.desktop import (
    ClipboardError,
    ClipboardService,
    ShortcutInstallError,
    SystemClipboardService,
    set_ubuntu_shortcut,
)
from vox_voice_paste.config import default_config_path, load_config, save_config
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
        self.setWindowTitle("Vox Voice Paste - Parametres")
        self.setMinimumWidth(520)

        self.key_status = QLabel("Cle OpenAI stockee dans le keyring systeme.")
        self.configure_key_button = QPushButton("Configurer la cle OpenAI")
        self.configure_key_button.clicked.connect(self.configure_openai_key)

        self.shortcut_command = QLineEdit(SHORTCUT_COMMAND)
        self.shortcut_command.setReadOnly(True)
        self.copy_shortcut_button = QPushButton("Copier la commande du raccourci")
        self.copy_shortcut_button.clicked.connect(self.copy_shortcut_command)
        self.shortcut_input = QLineEdit(shortcut_value)
        self.shortcut_input.setPlaceholderText(RECOMMENDED_SHORTCUT)
        self.install_shortcut_button = QPushButton("Installer le raccourci GNOME")
        self.install_shortcut_button.clicked.connect(self.apply_ubuntu_shortcut)
        self.shortcut_status = QLabel()

        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Vox Voice Paste"))
        layout.addWidget(QLabel(f"Configuration: {resolved_config_path}"))
        layout.addWidget(QLabel(f"Commande raccourci: {SHORTCUT_COMMAND}"))
        layout.addWidget(QLabel(f"Raccourci recommande: {RECOMMENDED_SHORTCUT}"))
        layout.addWidget(QLabel("Si Ctrl+Alt+N colle déjà, choisissez un autre raccourci."))
        layout.addWidget(QLabel("Raccourci GNOME actif:"))
        layout.addWidget(self.shortcut_input)
        layout.addWidget(self.install_shortcut_button)
        layout.addWidget(self.shortcut_command)
        layout.addWidget(self.copy_shortcut_button)
        layout.addWidget(self.shortcut_status)
        layout.addWidget(self.configure_key_button)
        layout.addWidget(self.key_status)
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
            self.key_status.setText("Cle OpenAI enregistree.")
        else:
            self.key_status.setText("Cle OpenAI non modifiee.")

    @Slot()
    def copy_shortcut_command(self) -> None:
        try:
            self._clipboard.copy_text(SHORTCUT_COMMAND)
        except ClipboardError as exc:
            self.shortcut_status.setText(str(exc))
            return
        self.shortcut_status.setText("Commande copiee.")

    @Slot()
    def apply_ubuntu_shortcut(self) -> None:
        shortcut = self.shortcut_input.text().strip()
        if not shortcut:
            self.shortcut_status.setText("Le raccourci ne peut pas etre vide.")
            return
        try:
            set_ubuntu_shortcut(shortcut=shortcut, command=SHORTCUT_COMMAND)
        except ShortcutInstallError as exc:
            self.shortcut_status.setText(str(exc))
            return
        self._config.ubuntu_shortcut = shortcut
        save_config(self._config, self._config_path)
        self.shortcut_status.setText(f"Raccourci GNOME configure: {shortcut}")
