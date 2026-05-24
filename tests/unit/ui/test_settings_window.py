from __future__ import annotations

from PySide6.QtWidgets import QDialog

from vox_voice_paste.security import InMemorySecretService, StaticOpenAIKeyValidator
from vox_voice_paste.ui.settings_window import SettingsWindow


def test_settings_window_has_openai_key_button(qtbot, tmp_path) -> None:
    window = SettingsWindow(
        config_path=tmp_path / "config.toml",
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)

    assert window.configure_key_button.text() == "Configurer la cle OpenAI"


def test_settings_window_updates_status_after_key_dialog_accepts(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    class AcceptedDialog:
        def __init__(self, **kwargs) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("vox_voice_paste.ui.settings_window.OpenAIKeyDialog", AcceptedDialog)
    window = SettingsWindow(
        config_path=tmp_path / "config.toml",
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)

    window.configure_openai_key()

    assert window.key_status.text() == "Cle OpenAI enregistree."
