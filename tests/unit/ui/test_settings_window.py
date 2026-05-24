from __future__ import annotations

from PySide6.QtWidgets import QDialog

from vox_voice_paste.config import load_config
from vox_voice_paste.desktop import InMemoryClipboardService
from vox_voice_paste.security import InMemorySecretService, StaticOpenAIKeyValidator
from vox_voice_paste.ui.onboarding_window import SHORTCUT_COMMAND
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


def test_settings_window_copies_shortcut_command(qtbot, tmp_path) -> None:
    clipboard = InMemoryClipboardService()
    window = SettingsWindow(
        config_path=tmp_path / "config.toml",
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
        clipboard_service=clipboard,
    )
    qtbot.addWidget(window)

    window.copy_shortcut_command()

    assert clipboard.text == SHORTCUT_COMMAND
    assert "copiee" in window.shortcut_status.text()


def test_settings_window_installs_shortcut_and_persists_choice(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    recorded = {}

    def fake_set_ubuntu_shortcut(*, shortcut: str, command: str) -> None:
        recorded["shortcut"] = shortcut
        recorded["command"] = command

    monkeypatch.setattr(
        "vox_voice_paste.ui.settings_window.set_ubuntu_shortcut",
        fake_set_ubuntu_shortcut,
    )
    window = SettingsWindow(
        config_path=tmp_path / "config.toml",
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)

    window.shortcut_input.setText("Ctrl+Alt+K")
    window.apply_ubuntu_shortcut()

    assert recorded["shortcut"] == "Ctrl+Alt+K"
    assert recorded["command"] == SHORTCUT_COMMAND
    assert load_config(tmp_path / "config.toml").ubuntu_shortcut == "Ctrl+Alt+K"
