from __future__ import annotations

import pytest

from vox_voice_paste.config import AppConfig, ConfigError, load_config, save_config


def test_missing_config_returns_default(tmp_path) -> None:
    config = load_config(tmp_path / "missing.toml")

    assert config == AppConfig()
    assert config.onboarding_completed is False


def test_save_and_load_config_without_secret_content(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config = AppConfig(
        onboarding_completed=True,
        default_input_device_id="mic-1",
        transcription_model="test-model",
    )

    save_config(config, config_path)

    assert load_config(config_path) == config
    assert "openai" not in config_path.read_text(encoding="utf-8").lower()
    assert not list(tmp_path.glob("*.tmp"))


def test_invalid_config_raises_config_error(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("unexpected = true\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_falls_back_to_legacy_app_id(monkeypatch, tmp_path) -> None:
    def fake_user_config_path(app_id: str, *, appauthor: bool = False):
        del appauthor
        return tmp_path / app_id

    legacy_config_path = tmp_path / "vox-voice-paste" / "config.toml"
    legacy_config_path.parent.mkdir()
    legacy_config_path.write_text("onboarding_completed = true\n", encoding="utf-8")
    monkeypatch.setattr("vox_voice_paste.config.user_config_path", fake_user_config_path)

    config = load_config()

    assert config.onboarding_completed is True
