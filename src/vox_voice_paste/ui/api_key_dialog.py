# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    APIKeyValidator,
    OpenAIHTTPKeyValidator,
    SecretError,
    SecretService,
)


class OpenAIKeyDialog(QDialog):
    def __init__(
        self,
        *,
        secret_service: SecretService,
        key_validator: APIKeyValidator | None = None,
        secret_name: str = OPENAI_API_KEY_SECRET,
        service_name: str = "OpenAI",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._secrets = secret_service
        self._secret_name = secret_name
        self._service_name = service_name
        self._key_validator = key_validator or OpenAIHTTPKeyValidator()

        self.setWindowTitle(f"{service_name} Key")
        self.setMinimumWidth(460)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText(f"{service_name} API key")
        self.status_label = QLabel("The key will be stored in the system keyring.")

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_key)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Enter your {service_name} API key."))
        layout.addWidget(self.key_input)
        layout.addWidget(self.status_label)
        layout.addWidget(self.save_button)
        layout.addWidget(self.cancel_button)
        self.setLayout(layout)

    @Slot()
    def save_key(self) -> None:
        value = self.key_input.text().strip()
        if not value:
            self.status_label.setText("Key is empty.")
            return

        validation = self._key_validator.validate(value)
        if not validation.ok:
            self.status_label.setText(validation.message)
            return

        try:
            self._secrets.set_secret(self._secret_name, value)
        except SecretError as exc:
            self.status_label.setText(str(exc))
            return

        self.key_input.clear()
        self.accept()
