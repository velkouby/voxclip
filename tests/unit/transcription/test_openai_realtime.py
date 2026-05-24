from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator

from websockets.exceptions import WebSocketException

from vox_voice_paste.transcription import TranscriptionConfig, TranscriptionEventType
from vox_voice_paste.transcription.openai_realtime import (
    OpenAIRealtimeTranscriptionService,
    build_session_update,
    parse_realtime_event,
    send_audio,
    websocket_url,
)


def test_build_session_update_uses_transcription_session_shape() -> None:
    config = TranscriptionConfig(
        api_key="sk-test",
        model="gpt-realtime-whisper",
        language="fr",
        delay="low",
    )

    payload = build_session_update(config)

    assert payload["type"] == "session.update"
    assert payload["session"]["type"] == "transcription"
    assert payload["session"]["audio"]["input"]["format"] == {
        "type": "audio/pcm",
        "rate": 24_000,
    }
    assert payload["session"]["audio"]["input"]["transcription"] == {
        "model": "gpt-realtime-whisper",
        "delay": "low",
        "language": "fr",
    }
    assert payload["session"]["audio"]["input"]["turn_detection"] is None


def test_websocket_url_uses_transcription_intent() -> None:
    url = websocket_url(TranscriptionConfig(api_key="sk-test", model="gpt-realtime-whisper"))

    assert url == "wss://api.openai.com/v1/realtime?intent=transcription"


def test_parse_realtime_delta_and_completed_events() -> None:
    partial = parse_realtime_event(
        {
            "type": "conversation.item.input_audio_transcription.delta",
            "item_id": "item_1",
            "delta": "Bonjour",
        }
    )
    final = parse_realtime_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "item_1",
            "transcript": "Bonjour.",
        }
    )

    assert partial is not None
    assert partial.type is TranscriptionEventType.PARTIAL
    assert partial.text == "Bonjour"
    assert final is not None
    assert final.type is TranscriptionEventType.FINAL
    assert final.text == "Bonjour."


def test_parse_realtime_error_event() -> None:
    event = parse_realtime_event({"type": "error", "error": {"message": "bad request"}})

    assert event is not None
    assert event.type is TranscriptionEventType.ERROR
    assert event.error == "bad request"


def test_send_audio_appends_base64_and_commits() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"abc"
        yield b""

    async def run() -> list[str]:
        websocket = FakeWebSocket()
        await send_audio(websocket, chunks())
        return websocket.sent

    sent = asyncio.run(run())

    assert json.loads(sent[0]) == {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(b"abc").decode("ascii"),
    }
    assert json.loads(sent[1]) == {"type": "input_audio_buffer.commit"}


def test_openai_service_reports_missing_api_key_without_network() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"abc"

    async def run() -> list:
        service = OpenAIRealtimeTranscriptionService(TranscriptionConfig(api_key=None))
        return [event async for event in service.transcribe(chunks())]

    events = asyncio.run(run())

    assert len(events) == 1
    assert events[0].type is TranscriptionEventType.ERROR
    assert events[0].error == "OpenAI API key is missing."


def test_openai_service_reports_websocket_error_detail(monkeypatch) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"abc"

    def fail_connect(*args, **kwargs):
        raise WebSocketException("server rejected WebSocket connection: HTTP 403")

    monkeypatch.setattr(
        "vox_voice_paste.transcription.openai_realtime.websockets.connect",
        fail_connect,
    )

    async def run() -> list:
        service = OpenAIRealtimeTranscriptionService(
            TranscriptionConfig(api_key="sk-test", connect_timeout_seconds=0.01)
        )
        return [event async for event in service.transcribe(chunks())]

    events = asyncio.run(run())

    assert len(events) == 1
    assert events[0].type is TranscriptionEventType.ERROR
    assert "HTTP 403" in str(events[0].error)


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, payload: str) -> None:
        self.sent.append(payload)
