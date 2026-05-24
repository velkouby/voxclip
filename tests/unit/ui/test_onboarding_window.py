from __future__ import annotations

from vox_voice_paste.audio import AudioInputDevice
from vox_voice_paste.config import load_config
from vox_voice_paste.desktop import InMemoryClipboardService
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    InMemorySecretService,
    KeyValidationResult,
    StaticOpenAIKeyValidator,
)
from vox_voice_paste.ui.onboarding_window import SHORTCUT_COMMAND, OnboardingWindow


def test_onboarding_stores_openai_key_without_showing_it(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("vox_voice_paste.ui.onboarding_window.list_input_devices", lambda: [])
    secrets = InMemorySecretService()
    window = OnboardingWindow(
        config_path=tmp_path / "config.toml",
        secret_service=secrets,
        key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)

    window.key_input.setText("sk-test-secret")
    window.store_key()

    assert secrets.get_secret(OPENAI_API_KEY_SECRET) == "sk-test-secret"
    assert window.key_input.text() == ""
    assert "sk-test-secret" not in window.key_status.text()


def test_onboarding_does_not_store_invalid_openai_key(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("vox_voice_paste.ui.onboarding_window.list_input_devices", lambda: [])
    secrets = InMemorySecretService()
    window = OnboardingWindow(
        config_path=tmp_path / "config.toml",
        secret_service=secrets,
        key_validator=StaticOpenAIKeyValidator(KeyValidationResult(False, "Cle invalide.")),
    )
    qtbot.addWidget(window)

    window.key_input.setText("sk-test-secret")
    window.store_key()

    assert secrets.get_secret(OPENAI_API_KEY_SECRET) is None
    assert "Cle invalide" in window.key_status.text()


def test_onboarding_finish_persists_completed_config(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "vox_voice_paste.ui.onboarding_window.list_input_devices",
        lambda: [
            AudioInputDevice(
                id="2",
                name="Internal Mic",
                max_input_channels=1,
                default_sample_rate=24_000,
                is_default=True,
            )
        ],
    )
    config_path = tmp_path / "config.toml"
    window = OnboardingWindow(
        config_path=config_path,
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(window)

    window.finish()
    config = load_config(config_path)

    assert config.onboarding_completed is True
    assert config.default_input_device_id == "2"


def test_onboarding_copies_shortcut_command(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("vox_voice_paste.ui.onboarding_window.list_input_devices", lambda: [])
    clipboard = InMemoryClipboardService()
    window = OnboardingWindow(
        config_path=tmp_path / "config.toml",
        secret_service=InMemorySecretService(),
        key_validator=StaticOpenAIKeyValidator(),
        clipboard_service=clipboard,
    )
    qtbot.addWidget(window)

    window.copy_shortcut_command()

    assert clipboard.text == SHORTCUT_COMMAND
    assert "copiee" in window.shortcut_status.text()
