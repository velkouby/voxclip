from __future__ import annotations

import asyncio

from vox_voice_paste.config import SONIOX_REALTIME_TRANSCRIPTION_MODEL
from vox_voice_paste.transcription import (
    SONIOX_SAMPLE_RATE,
    TranscriptionConfig,
    TranscriptionEventType,
)
from vox_voice_paste.transcription.soniox_realtime import (
    SonioxEventParser,
    SonioxRealtimeTranscriptionService,
    build_safe_soniox_config,
    build_soniox_config,
    endpoint_delay_ms,
    safe_realtime_error_context,
    send_audio,
)


def test_build_soniox_config_uses_realtime_shape() -> None:
    config = TranscriptionConfig(
        api_key="soniox-test",
        model=SONIOX_REALTIME_TRANSCRIPTION_MODEL,
        language="fr",
        delay="high",
        sample_rate=SONIOX_SAMPLE_RATE,
    )

    payload = build_soniox_config(config)

    assert payload == {
        "api_key": "soniox-test",
        "model": "stt-rt-v5",
        "audio_format": "pcm_s16le",
        "sample_rate": SONIOX_SAMPLE_RATE,
        "num_channels": 1,
        "enable_language_identification": True,
        "enable_endpoint_detection": True,
        "max_endpoint_delay_ms": 2000,
        "language_hints": ["fr"],
    }


def test_build_soniox_config_adds_one_way_translation() -> None:
    payload = build_soniox_config(
        TranscriptionConfig(api_key="soniox-test", translation_target_language="en")
    )

    assert payload["translation"] == {
        "type": "one_way",
        "target_language": "en",
    }


def test_build_soniox_config_normalizes_legacy_models_to_realtime_v5() -> None:
    for model in ("stt-rt-v4", "stt-async-v5", "gpt-realtime-whisper", "   "):
        payload = build_soniox_config(TranscriptionConfig(api_key="soniox-test", model=model))

        assert payload["model"] == SONIOX_REALTIME_TRANSCRIPTION_MODEL


def test_soniox_safe_contexts_exclude_api_key() -> None:
    config = TranscriptionConfig(
        api_key="soniox-test-secret",
        model=SONIOX_REALTIME_TRANSCRIPTION_MODEL,
        language="fr",
    )

    safe_payload = build_safe_soniox_config(config)
    realtime_context = safe_realtime_error_context(config, stage="websocket")

    raw_context = f"{safe_payload}{realtime_context}"
    assert safe_payload["api_key"] == "<redacted>"
    assert realtime_context["provider"] == "soniox"
    assert realtime_context["transport"] == "websocket"
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


def test_soniox_translation_parser_keeps_translation_tokens_only() -> None:
    parser = SonioxEventParser(translation_only=True)

    partial_events = parser.parse(
        {
            "tokens": [
                {
                    "text": "Bonjour",
                    "is_final": False,
                    "translation_status": "original",
                },
                {
                    "text": "Hello",
                    "is_final": False,
                    "translation_status": "translation",
                },
            ]
        }
    )
    final_events = parser.parse(
        {
            "tokens": [
                {
                    "text": "Bonjour.",
                    "is_final": True,
                    "translation_status": "original",
                },
                {
                    "text": "Hello.",
                    "is_final": True,
                    "translation_status": "translation",
                },
            ],
            "finished": True,
        }
    )

    assert len(partial_events) == 1
    assert partial_events[0].text == "Hello"
    assert len(final_events) == 1
    assert final_events[0].text == "Hello."


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


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[bytes | str] = []

    async def send(self, payload: bytes | str) -> None:
        self.sent.append(payload)
