from __future__ import annotations

from vox_voice_paste.config import AppConfig, save_config
from vox_voice_paste.desktop.diagnostics import build_diagnostic_lines, format_diagnostic_report
from vox_voice_paste.security import OPENAI_API_KEY_SECRET, InMemorySecretService


def test_diagnostic_report_shows_secret_presence_without_value(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    save_config(AppConfig(onboarding_completed=True), config_path)
    secrets = InMemorySecretService({OPENAI_API_KEY_SECRET: "sk-test-secret"})

    report = format_diagnostic_report(
        build_diagnostic_lines(config_path=config_path, secret_service=secrets)
    )

    assert "config: valid" in report
    assert "openai_api_key: present" in report
    assert "audio_devices:" in report
    assert "clipboard:" in report
    assert "notifications:" in report
    assert "sk-test-secret" not in report
