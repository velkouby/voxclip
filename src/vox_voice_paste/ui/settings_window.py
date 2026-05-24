from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from vox_voice_paste.config import default_config_path

from .onboarding_window import SHORTCUT_COMMAND


class SettingsWindow(QDialog):
    def __init__(self, *, config_path: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        resolved_config_path = config_path or default_config_path()
        self.setWindowTitle("Vox Voice Paste - Parametres")
        self.setMinimumWidth(520)

        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Vox Voice Paste"))
        layout.addWidget(QLabel(f"Configuration: {resolved_config_path}"))
        layout.addWidget(QLabel(f"Commande raccourci: {SHORTCUT_COMMAND}"))
        layout.addWidget(close_button)
        self.setLayout(layout)
