from __future__ import annotations

from PySide6.QtWidgets import QDialog

from vox_voice_paste.app import _api_key_or_prompt
from vox_voice_paste.config import SONIOX_TRANSCRIPTION_PROVIDER
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    SONIOX_API_KEY_SECRET,
    InMemorySecretService,
    StaticOpenAIKeyValidator,
)


def test_api_key_or_prompt_returns_existing_key(monkeypatch) -> None:
    secrets = InMemorySecretService({OPENAI_API_KEY_SECRET: "sk-existing"})

    def fail_dialog(**kwargs):
        raise AssertionError("dialog should not open when key exists")

    monkeypatch.setattr("vox_voice_paste.app.OpenAIKeyDialog", fail_dialog)

    assert _api_key_or_prompt(secret_service=secrets) == "sk-existing"


def test_api_key_or_prompt_opens_dialog_when_key_is_missing(monkeypatch) -> None:
    secrets = InMemorySecretService()

    class AcceptedDialog:
        def __init__(
            self,
            *,
            secret_service,
            key_validator=None,
            secret_name,
            service_name,
        ) -> None:
            del key_validator, service_name
            self._secret_service = secret_service
            self._secret_name = secret_name

        def exec(self) -> QDialog.DialogCode:
            self._secret_service.set_secret(self._secret_name, "sk-new")
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("vox_voice_paste.app.OpenAIKeyDialog", AcceptedDialog)

    assert _api_key_or_prompt(
        secret_service=secrets,
        key_validator=StaticOpenAIKeyValidator(),
    ) == "sk-new"


def test_api_key_or_prompt_returns_none_when_dialog_is_cancelled(monkeypatch) -> None:
    secrets = InMemorySecretService()

    class RejectedDialog:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("vox_voice_paste.app.OpenAIKeyDialog", RejectedDialog)

    assert _api_key_or_prompt(secret_service=secrets) is None


def test_api_key_or_prompt_uses_soniox_secret_when_provider_is_soniox(monkeypatch) -> None:
    secrets = InMemorySecretService({SONIOX_API_KEY_SECRET: "soniox-existing"})

    def fail_dialog(**kwargs):
        raise AssertionError("dialog should not open when key exists")

    monkeypatch.setattr("vox_voice_paste.app.OpenAIKeyDialog", fail_dialog)

    assert (
        _api_key_or_prompt(
            provider=SONIOX_TRANSCRIPTION_PROVIDER,
            secret_service=secrets,
        )
        == "soniox-existing"
    )
