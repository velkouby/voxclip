from __future__ import annotations

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
from vox_voice_paste.config import load_config, save_config
from vox_voice_paste.desktop import ClipboardError, ClipboardService, SystemClipboardService
from vox_voice_paste.security import OpenAIHTTPKeyValidator, OpenAIKeyValidator, SecretService

from .api_key_dialog import OpenAIKeyDialog

SHORTCUT_COMMAND = "vox-voice-paste --record-and-copy"
RECOMMENDED_SHORTCUT = "Ctrl+Alt+V"


class OnboardingWindow(QDialog):
    def __init__(
        self,
        *,
        config_path: Path | None = None,
        secret_service: SecretService,
        key_validator: OpenAIKeyValidator | None = None,
        clipboard_service: ClipboardService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._secrets = secret_service
        self._key_validator = key_validator or OpenAIHTTPKeyValidator()
        self._clipboard = clipboard_service or SystemClipboardService()
        self._config = load_config(config_path)

        self.setWindowTitle("Vox Voice Paste - Configuration")
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

        self.back_button = QPushButton("Retour")
        self.back_button.clicked.connect(self.back)
        self.next_button = QPushButton("Suivant")
        self.next_button.clicked.connect(self.next)
        self.finish_button = QPushButton("Terminer")
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
        layout.addWidget(QLabel("Bienvenue dans Vox Voice Paste"))
        layout.addWidget(QLabel("La dictee V1 copie le texte final, puis vous collez avec Ctrl+V."))
        layout.addWidget(QLabel("La transcription reelle envoie l'audio a l'API OpenAI."))
        page.setLayout(layout)
        return page

    def _key_page(self) -> QWidget:
        page = QWidget()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("Cle API OpenAI")
        self.key_status = QLabel("Cle non verifiee")
        self.store_key_button = QPushButton("Enregistrer la cle")
        self.store_key_button.clicked.connect(self.store_key)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Cle OpenAI"))
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
        self.copy_shortcut_button = QPushButton("Copier la commande")
        self.copy_shortcut_button.clicked.connect(self.copy_shortcut_command)
        self.shortcut_status = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Raccourci Ubuntu"))
        layout.addWidget(QLabel("Configurez un raccourci personnalise avec cette commande."))
        layout.addWidget(QLabel(f"Raccourci recommande : {RECOMMENDED_SHORTCUT}"))
        layout.addWidget(self.shortcut_command)
        layout.addWidget(self.copy_shortcut_button)
        layout.addWidget(self.shortcut_status)
        page.setLayout(layout)
        return page

    def _finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Configuration terminee"))
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
            self.audio_status.setText("Selectionnez le microphone a utiliser.")

        if not devices:
            self.microphone_combo.addItem("Micro systeme par defaut", None)
            return

        for device in devices:
            self.microphone_combo.addItem(_device_label(device), device.id)

    @Slot()
    def store_key(self) -> None:
        value = self.key_input.text().strip()
        if not value:
            self.key_status.setText("Cle vide.")
            return
        dialog = OpenAIKeyDialog(
            secret_service=self._secrets,
            key_validator=self._key_validator,
            parent=self,
        )
        dialog.key_input.setText(value)
        dialog.save_key()
        if dialog.result() == QDialog.DialogCode.Accepted:
            self.key_input.clear()
            self.key_status.setText("Cle valide et enregistree dans le keyring.")
        else:
            self.key_status.setText(dialog.status_label.text())

    @Slot()
    def copy_shortcut_command(self) -> None:
        try:
            self._clipboard.copy_text(SHORTCUT_COMMAND)
        except ClipboardError as exc:
            self.shortcut_status.setText(str(exc))
            return
        self.shortcut_status.setText("Commande copiee.")

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

    def _sync_buttons(self) -> None:
        index = self.pages.currentIndex()
        last_index = self.pages.count() - 1
        self.back_button.setEnabled(index > 0)
        self.next_button.setVisible(index < last_index)
        self.finish_button.setVisible(index == last_index)


def _device_label(device: AudioInputDevice) -> str:
    marker = " (defaut)" if device.is_default else ""
    return f"{device.name}{marker}"
