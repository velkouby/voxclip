from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from vox_voice_paste.transcription import TranscriptionConfig, TranscriptionEventType
from vox_voice_paste.transcription.soniox_realtime import (
    SonioxRealtimeTranscriptionService,
    SonioxTranscriptState,
    build_start_request,
    send_audio,
)


def test_build_start_request_uses_soniox_shape() -> None:
    config = TranscriptionConfig(
        api_key="soniox-test",
        model="stt-rt-preview",
        language="fr",
    )

    payload = build_start_request(config)

    assert payload == {
        "api_key": "soniox-test",
        "model": "stt-rt-preview",
        "audio_format": "s16le",
        "sample_rate": 24_000,
        "num_channels": 1,
        "language_hints": ["fr"],
    }


def test_send_audio_uses_binary_frames_and_empty_end_frame() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"abc"
        yield b""

    async def run() -> list[bytes]:
        websocket = FakeWebSocket()
        await send_audio(websocket, chunks())
        return websocket.sent

    assert asyncio.run(run()) == [b"abc", b""]


def test_soniox_state_emits_partial_delta_then_final() -> None:
    state = SonioxTranscriptState()

    partial = state.apply(
        {
            "tokens": [
                {"text": "Bonjour", "start_ms": 0, "end_ms": 300, "is_final": True},
                {"text": " Vincent", "start_ms": 300, "end_ms": 600, "is_final": False},
            ]
        }
    )
    final = state.apply(
        {
            "tokens": [
                {"text": " Vincent.", "start_ms": 300, "end_ms": 700, "is_final": True},
            ],
            "finished": True,
        }
    )

    assert partial is not None
    assert partial.type is TranscriptionEventType.PARTIAL
    assert partial.text == "Bonjour Vincent"
    assert final is not None
    assert final.type is TranscriptionEventType.FINAL
    assert final.text == "Bonjour Vincent."


def test_soniox_state_emits_error_response() -> None:
    event = SonioxTranscriptState().apply({"error_message": "Incorrect API key provided."})

    assert event is not None
    assert event.type is TranscriptionEventType.ERROR
    assert event.error == "Incorrect API key provided."


def test_soniox_service_reports_missing_api_key_without_network() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"abc"

    async def run() -> list:
        service = SonioxRealtimeTranscriptionService(TranscriptionConfig(api_key=None))
        return [event async for event in service.transcribe(chunks())]

    events = asyncio.run(run())

    assert len(events) == 1
    assert events[0].type is TranscriptionEventType.ERROR
    assert events[0].error == "Soniox API key is missing."


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    async def send(self, payload: bytes) -> None:
        self.sent.append(payload)
