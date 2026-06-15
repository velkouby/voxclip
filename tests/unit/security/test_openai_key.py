from __future__ import annotations

import urllib.error

from vox_voice_paste.security import (
    KeyValidationResult,
    OpenAIHTTPKeyValidator,
    SonioxHTTPKeyValidator,
    StaticOpenAIKeyValidator,
)


def test_static_openai_key_validator_returns_configured_result() -> None:
    validator = StaticOpenAIKeyValidator(KeyValidationResult(False, "invalid"))

    result = validator.validate("sk-test")

    assert result == KeyValidationResult(False, "invalid")


def test_http_openai_key_validator_reports_auth_failure(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError(
            url="https://api.openai.com/v1/models",
            code=401,
            msg="unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fail)

    result = OpenAIHTTPKeyValidator().validate("sk-test")

    assert result.ok is False
    assert "Invalid OpenAI API key" in result.message


def test_http_soniox_key_validator_reports_auth_failure(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError(
            url="https://api.soniox.com/v1/models",
            code=403,
            msg="forbidden",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fail)

    result = SonioxHTTPKeyValidator().validate("soniox-test")

    assert result.ok is False
    assert "Invalid Soniox API key" in result.message
