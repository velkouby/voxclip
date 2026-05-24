from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from vox_voice_paste.config import default_config_path
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
    ) -> None:
        super().__init__(parent)
        self._secrets = secret_service or KeyringSecretService()
        self._key_validator = key_validator or OpenAIHTTPKeyValidator()
        resolved_config_path = config_path or default_config_path()
        self.setWindowTitle("Vox Voice Paste - Parametres")
        self.setMinimumWidth(520)

        self.key_status = QLabel("Cle OpenAI stockee dans le keyring systeme.")
        self.configure_key_button = QPushButton("Configurer la cle OpenAI")
        self.configure_key_button.clicked.connect(self.configure_openai_key)

        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Vox Voice Paste"))
        layout.addWidget(QLabel(f"Configuration: {resolved_config_path}"))
        layout.addWidget(QLabel(f"Commande raccourci: {SHORTCUT_COMMAND}"))
        layout.addWidget(QLabel(f"Raccourci recommande: {RECOMMENDED_SHORTCUT}"))
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
