from __future__ import annotations

import pytest

from vox_voice_paste.config import (
    DEFAULT_TRANSCRIPTION_MODEL,
    DEFAULT_TRANSCRIPTION_PROVIDER,
    DEFAULT_TRANSLATION_TARGET_LANGUAGE,
    DEFAULT_TRANSLATION_UBUNTU_SHORTCUT,
    DEFAULT_UBUNTU_SHORTCUT,
    NON_REALTIME_TRANSCRIPTION_MODELS,
    AppConfig,
    ConfigError,
    load_config,
    normalize_language_code,
    normalize_transcription_model,
    save_config,
)


def test_missing_config_returns_default(tmp_path) -> None:
    config = load_config(tmp_path / "missing.toml")

    assert config == AppConfig()
    assert config.onboarding_completed is False
    assert config.transcription_provider == DEFAULT_TRANSCRIPTION_PROVIDER
    assert config.ubuntu_shortcut == DEFAULT_UBUNTU_SHORTCUT
    assert config.translation_ubuntu_shortcut == DEFAULT_TRANSLATION_UBUNTU_SHORTCUT
    assert config.translation_target_language == DEFAULT_TRANSLATION_TARGET_LANGUAGE


def test_save_and_load_config_without_secret_content(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config = AppConfig(
        onboarding_completed=True,
        default_input_device_id="mic-1",
        transcription_model="test-model",
    )

    save_config(config, config_path)

    assert load_config(config_path) == config
    assert "sk-" not in config_path.read_text(encoding="utf-8").lower()
    assert not list(tmp_path.glob("*.tmp"))


def test_config_persists_soniox_provider(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config = AppConfig(transcription_provider="soniox")

    save_config(config, config_path)

    assert load_config(config_path).transcription_provider == "soniox"


def test_config_persists_translation_settings(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config = AppConfig(
        translation_ubuntu_shortcut="Ctrl+Alt+M",
        translation_target_language="DE",
    )

    save_config(config, config_path)
    loaded = load_config(config_path)

    assert loaded.translation_ubuntu_shortcut == "Ctrl+Alt+M"
    assert loaded.translation_target_language == "de"


def test_config_without_provider_keeps_openai_default(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("onboarding_completed = true\n", encoding="utf-8")

    config = load_config(config_path)

    assert config.transcription_provider == "openai"


def test_invalid_transcription_provider_raises_config_error(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('transcription_provider = "bad"\n', encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_path)


@pytest.mark.parametrize("model", sorted(NON_REALTIME_TRANSCRIPTION_MODELS))
def test_non_realtime_transcription_models_normalize_to_realtime_model(model: str) -> None:
    config = AppConfig(transcription_model=model)

    assert config.transcription_model == DEFAULT_TRANSCRIPTION_MODEL
    assert normalize_transcription_model(model) == DEFAULT_TRANSCRIPTION_MODEL


def test_blank_transcription_model_normalizes_to_default() -> None:
    assert normalize_transcription_model("   ") == DEFAULT_TRANSCRIPTION_MODEL


def test_language_code_normalizes_blank_to_none() -> None:
    assert normalize_language_code(" FR ") == "fr"
    assert normalize_language_code("   ") is None


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
