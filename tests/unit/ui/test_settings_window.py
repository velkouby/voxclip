from __future__ import annotations

from PySide6.QtWidgets import QDialog

from vox_voice_paste.config import (
    DEFAULT_TRANSCRIPTION_DELAY,
    DEFAULT_TRANSCRIPTION_MODEL,
    DEFAULT_TRANSLATION_TARGET_LANGUAGE,
    EXPERT_TRANSCRIPTION_DELAY,
    load_config,
)
from vox_voice_paste.desktop import InMemoryClipboardService
from vox_voice_paste.desktop.shortcuts import (
    DEFAULT_TRANSLATION_SHORTCUT_COMMAND,
    TRANSLATION_MANAGED_SHORTCUT_PATH,
    TRANSLATION_SHORTCUT_LABEL,
)
from vox_voice_paste.security import (
    SONIOX_API_KEY_SECRET,
    InMemorySecretService,
    StaticOpenAIKeyValidator,
)
from vox_voice_paste.ui.onboarding_window import SHORTCUT_COMMAND
from vox_voice_paste.ui.settings_window import SettingsWindow


def test_settings_window_has_openai_key_button(qtbot, tmp_path) -> None:
    window = SettingsWindow(
        config_path=tmp_path / "config.toml",
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)

    assert window.configure_key_button.text() == "Configure OpenAI key"


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

    assert window.key_status.text() == "OpenAI key saved."


def test_settings_window_persists_provider_selection(qtbot, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    window = SettingsWindow(
        config_path=config_path,
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
        soniox_key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)

    window.transcription_provider_combo.setCurrentIndex(
        window.transcription_provider_combo.findData("soniox")
    )

    assert load_config(config_path).transcription_provider == "soniox"
    assert window.configure_key_button.text() == "Configure Soniox key"
    assert "Soniox" in window.key_status.text()


def test_settings_window_configures_selected_soniox_key(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    recorded = {}

    class AcceptedDialog:
        def __init__(self, **kwargs) -> None:
            recorded.update(kwargs)

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("vox_voice_paste.ui.settings_window.OpenAIKeyDialog", AcceptedDialog)
    window = SettingsWindow(
        config_path=tmp_path / "config.toml",
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
        soniox_key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)
    window.transcription_provider_combo.setCurrentIndex(
        window.transcription_provider_combo.findData("soniox")
    )

    window.configure_api_key()

    assert recorded["provider_name"] == "Soniox"
    assert recorded["secret_name"] == SONIOX_API_KEY_SECRET
    assert window.key_status.text() == "Soniox key saved."


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
    assert "copied" in window.shortcut_status.text()


def test_settings_window_copies_translation_shortcut_command(qtbot, tmp_path) -> None:
    clipboard = InMemoryClipboardService()
    window = SettingsWindow(
        config_path=tmp_path / "config.toml",
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
        clipboard_service=clipboard,
    )
    qtbot.addWidget(window)

    window.copy_translation_shortcut_command()

    assert clipboard.text == DEFAULT_TRANSLATION_SHORTCUT_COMMAND
    assert "copied" in window.translation_shortcut_status.text()


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


def test_settings_window_installs_translation_shortcut_and_persists_choice(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    recorded = {}

    def fake_set_ubuntu_shortcut(
        *,
        shortcut: str,
        command: str,
        label: str,
        managed_path: str,
    ) -> None:
        recorded["shortcut"] = shortcut
        recorded["command"] = command
        recorded["label"] = label
        recorded["managed_path"] = managed_path

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

    window.translation_shortcut_input.setText("Ctrl+Alt+M")
    window.apply_translation_ubuntu_shortcut()

    config = load_config(tmp_path / "config.toml")
    assert recorded["shortcut"] == "Ctrl+Alt+M"
    assert recorded["command"] == DEFAULT_TRANSLATION_SHORTCUT_COMMAND
    assert recorded["label"] == TRANSLATION_SHORTCUT_LABEL
    assert recorded["managed_path"] == TRANSLATION_MANAGED_SHORTCUT_PATH
    assert config.translation_ubuntu_shortcut == "Ctrl+Alt+M"


def test_settings_window_persists_translation_language(qtbot, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    window = SettingsWindow(
        config_path=config_path,
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)

    assert (
        load_config(config_path).translation_target_language
        == DEFAULT_TRANSLATION_TARGET_LANGUAGE
    )

    window.translation_language_combo.setCurrentIndex(
        window.translation_language_combo.findData("de")
    )

    assert load_config(config_path).translation_target_language == "de"


def test_settings_window_toggles_transcription_delay(qtbot, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    window = SettingsWindow(
        config_path=config_path,
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)
    window.show()

    assert window.transcription_expert_checkbox.isChecked() is False
    config = load_config(config_path)
    assert config.transcription_model == DEFAULT_TRANSCRIPTION_MODEL
    assert config.transcription_delay == DEFAULT_TRANSCRIPTION_DELAY

    window.transcription_expert_checkbox.setChecked(True)

    assert window.transcription_expert_warning.isVisible()
    assert "longer" in window.transcription_expert_warning.text()
    config = load_config(config_path)
    assert config.transcription_model == DEFAULT_TRANSCRIPTION_MODEL
    assert config.transcription_delay == EXPERT_TRANSCRIPTION_DELAY

    window.transcription_expert_checkbox.setChecked(False)
    config = load_config(config_path)
    assert config.transcription_model == DEFAULT_TRANSCRIPTION_MODEL
    assert config.transcription_delay == DEFAULT_TRANSCRIPTION_DELAY
