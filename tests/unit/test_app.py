from __future__ import annotations

from PySide6.QtWidgets import QDialog

from vox_voice_paste.app import (
    _api_key_or_prompt,
    _effective_sample_rate,
    _effective_soniox_model,
    _transcription_service,
)
from vox_voice_paste.config import SONIOX_REALTIME_TRANSCRIPTION_MODEL, AppConfig
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    SONIOX_API_KEY_SECRET,
    InMemorySecretService,
    StaticOpenAIKeyValidator,
)
from vox_voice_paste.transcription import (
    OPENAI_SAMPLE_RATE,
    SONIOX_SAMPLE_RATE,
    OpenAIRealtimeTranscriptionService,
    SonioxRealtimeTranscriptionService,
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
        def __init__(self, *, secret_service, key_validator=None, **kwargs) -> None:
            self._secret_service = secret_service

        def exec(self) -> QDialog.DialogCode:
            self._secret_service.set_secret(OPENAI_API_KEY_SECRET, "sk-new")
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("vox_voice_paste.app.OpenAIKeyDialog", AcceptedDialog)

    assert _api_key_or_prompt(
        secret_service=secrets,
        key_validator=StaticOpenAIKeyValidator(),
    ) == "sk-new"


def test_api_key_or_prompt_returns_none_when_dialog_is_cancelled(monkeypatch) -> None:
    secrets = InMemorySecretService()

    class RejectedDialog:
        def __init__(self, *, secret_service, key_validator=None, **kwargs) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("vox_voice_paste.app.OpenAIKeyDialog", RejectedDialog)

    assert _api_key_or_prompt(secret_service=secrets) is None


def test_api_key_or_prompt_uses_soniox_secret(monkeypatch) -> None:
    secrets = InMemorySecretService({SONIOX_API_KEY_SECRET: "soniox-existing"})

    def fail_dialog(**kwargs):
        raise AssertionError("dialog should not open when key exists")

    monkeypatch.setattr("vox_voice_paste.app.OpenAIKeyDialog", fail_dialog)

    assert _api_key_or_prompt(secret_service=secrets, provider="soniox") == "soniox-existing"


def test_api_key_or_prompt_opens_soniox_dialog_when_key_is_missing(monkeypatch) -> None:
    secrets = InMemorySecretService()
    recorded = {}

    class AcceptedDialog:
        def __init__(
            self,
            *,
            secret_service,
            key_validator=None,
            provider_name=None,
            secret_name=None,
        ) -> None:
            self._secret_service = secret_service
            self._secret_name = secret_name
            recorded["provider_name"] = provider_name

        def exec(self) -> QDialog.DialogCode:
            self._secret_service.set_secret(self._secret_name, "soniox-new")
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("vox_voice_paste.app.OpenAIKeyDialog", AcceptedDialog)

    assert (
        _api_key_or_prompt(
            secret_service=secrets,
            provider="soniox",
            key_validator=StaticOpenAIKeyValidator(),
        )
        == "soniox-new"
    )
    assert recorded["provider_name"] == "Soniox"


def test_transcription_service_uses_provider() -> None:
    openai_service = _transcription_service(AppConfig(), api_key="sk-test")
    soniox_service = _transcription_service(
        AppConfig(transcription_provider="soniox"),
        api_key="soniox-test",
    )

    assert isinstance(openai_service, OpenAIRealtimeTranscriptionService)
    assert isinstance(soniox_service, SonioxRealtimeTranscriptionService)
    assert openai_service._config.sample_rate == OPENAI_SAMPLE_RATE
    assert soniox_service._config.sample_rate == SONIOX_SAMPLE_RATE
    assert soniox_service._config.model == SONIOX_REALTIME_TRANSCRIPTION_MODEL


def test_effective_sample_rate_uses_provider_specific_rates() -> None:
    assert _effective_sample_rate(AppConfig()) == OPENAI_SAMPLE_RATE
    assert (
        _effective_sample_rate(AppConfig(transcription_provider="soniox"))
        == SONIOX_SAMPLE_RATE
    )


def test_effective_soniox_model_forces_realtime_v5() -> None:
    assert _effective_soniox_model("stt-rt-v5") == SONIOX_REALTIME_TRANSCRIPTION_MODEL
    assert _effective_soniox_model("stt-rt-v4") == SONIOX_REALTIME_TRANSCRIPTION_MODEL
    assert _effective_soniox_model("stt-async-v5") == SONIOX_REALTIME_TRANSCRIPTION_MODEL
    assert _effective_soniox_model("gpt-realtime-whisper") == SONIOX_REALTIME_TRANSCRIPTION_MODEL
    assert _effective_soniox_model("   ") == SONIOX_REALTIME_TRANSCRIPTION_MODEL
