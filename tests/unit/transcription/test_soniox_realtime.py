from __future__ import annotations

import asyncio

from vox_voice_paste.config import (
    SONIOX_ASYNC_TRANSCRIPTION_MODEL,
    SONIOX_REALTIME_TRANSCRIPTION_MODEL,
)
from vox_voice_paste.transcription import TranscriptionConfig, TranscriptionEventType
from vox_voice_paste.transcription.soniox_realtime import (
    SonioxAsyncTranscriptionService,
    SonioxEventParser,
    SonioxRealtimeTranscriptionService,
    build_safe_soniox_config,
    build_soniox_config,
    endpoint_delay_ms,
    safe_async_error_context,
    safe_realtime_error_context,
    send_audio,
)


def test_build_soniox_config_uses_realtime_shape() -> None:
    config = TranscriptionConfig(
        api_key="soniox-test",
        model=SONIOX_REALTIME_TRANSCRIPTION_MODEL,
        language="fr",
        delay="high",
    )

    payload = build_soniox_config(config)

    assert payload == {
        "api_key": "soniox-test",
        "model": "stt-rt-v4",
        "audio_format": "pcm_s16le",
        "sample_rate": 16_000,
        "num_channels": 1,
        "enable_language_identification": True,
        "enable_endpoint_detection": True,
        "max_endpoint_delay_ms": 2000,
        "language_hints": ["fr"],
    }


def test_soniox_safe_contexts_exclude_api_key() -> None:
    config = TranscriptionConfig(
        api_key="soniox-test-secret",
        model=SONIOX_REALTIME_TRANSCRIPTION_MODEL,
        language="fr",
    )

    safe_payload = build_safe_soniox_config(config)
    realtime_context = safe_realtime_error_context(config, stage="websocket")
    async_context = safe_async_error_context(config, stage="http")

    raw_context = f"{safe_payload}{realtime_context}{async_context}"
    assert safe_payload["api_key"] == "<redacted>"
    assert realtime_context["provider"] == "soniox"
    assert async_context["transport"] == "http"
    assert "soniox-test-secret" not in raw_context


def test_endpoint_delay_maps_accuracy_modes() -> None:
    assert endpoint_delay_ms("minimal") == 500
    assert endpoint_delay_ms("low") == 500
    assert endpoint_delay_ms("medium") == 1000
    assert endpoint_delay_ms("high") == 2000
    assert endpoint_delay_ms("xhigh") == 3000


def test_send_audio_streams_binary_chunks_and_empty_final_frame() -> None:
    async def chunks():
        yield b"abc"
        yield b""
        yield b"def"

    async def run() -> list[bytes | str]:
        websocket = FakeWebSocket()
        await send_audio(websocket, chunks())
        return websocket.sent

    assert asyncio.run(run()) == [b"abc", b"def", ""]


def test_soniox_parser_emits_partial_final_and_ignores_end_token() -> None:
    parser = SonioxEventParser()

    partial_events = parser.parse(
        {
            "tokens": [
                {"text": "Bon", "is_final": False},
                {"text": "<end>", "is_final": False},
            ]
        }
    )
    final_events = parser.parse(
        {
            "tokens": [
                {"text": "Bonjour", "is_final": True},
                {"text": ".", "is_final": True},
            ],
            "finished": True,
        }
    )

    assert len(partial_events) == 1
    assert partial_events[0].type is TranscriptionEventType.PARTIAL
    assert partial_events[0].text == "Bon"
    assert len(final_events) == 1
    assert final_events[0].type is TranscriptionEventType.FINAL
    assert final_events[0].text == "Bonjour."


def test_soniox_parser_converts_cumulative_partial_text_to_delta() -> None:
    parser = SonioxEventParser()

    first = parser.parse({"tokens": [{"text": "Bon", "is_final": False}]})
    second = parser.parse({"tokens": [{"text": "Bonjour", "is_final": False}]})

    assert first[0].text == "Bon"
    assert second[0].text == "jour"


def test_soniox_parser_emits_server_error() -> None:
    event = SonioxEventParser().parse(
        {"error_code": "unauthorized", "error_message": "bad key"}
    )[0]

    assert event.type is TranscriptionEventType.ERROR
    assert event.error == "unauthorized: bad key"


def test_soniox_service_reports_missing_api_key_without_network() -> None:
    async def chunks():
        yield b"abc"

    async def run() -> list:
        service = SonioxRealtimeTranscriptionService(TranscriptionConfig(api_key=None))
        return [event async for event in service.transcribe(chunks())]

    events = asyncio.run(run())

    assert len(events) == 1
    assert events[0].type is TranscriptionEventType.ERROR
    assert events[0].error == "Soniox API key is missing."
    assert events[0].error_context["provider"] == "soniox"
    assert events[0].error_context["stage"] == "api_key"


def test_soniox_async_service_returns_final_transcript_for_completed_job() -> None:
    async def chunks():
        yield b"abc"

    async def run() -> list[str]:
        service = SonioxAsyncTranscriptionService(
            TranscriptionConfig(
                api_key="soniox-test",
                model=SONIOX_ASYNC_TRANSCRIPTION_MODEL,
            )
        )

        async def fake_upload_file(self, wav_path):
            assert wav_path.suffix == ".wav"
            return "file-id"

        async def fake_create_transcription(self, file_id):
            assert file_id == "file-id"
            return "transcription-id"

        async def fake_wait_for_transcript(self, transcription_id):
            assert transcription_id == "transcription-id"
            return "bonjour"

        service._upload_file = fake_upload_file.__get__(service)
        service._create_transcription = fake_create_transcription.__get__(service)
        service._wait_for_transcript = fake_wait_for_transcript.__get__(service)

        return [event.text for event in [event async for event in service.transcribe(chunks())]]

    events = asyncio.run(run())
    assert events == ["bonjour"]


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[bytes | str] = []

    async def send(self, payload: bytes | str) -> None:
        self.sent.append(payload)
