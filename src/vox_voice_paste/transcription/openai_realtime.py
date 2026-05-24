from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any
from urllib.parse import urlencode

import websockets
from websockets.exceptions import WebSocketException

from vox_voice_paste.audio import AudioChunk

from .base import TranscriptionConfig, TranscriptionEvent, TranscriptionEventType

DELTA_EVENT = "conversation.item.input_audio_transcription.delta"
COMPLETED_EVENT = "conversation.item.input_audio_transcription.completed"
ERROR_EVENT = "error"


class OpenAIRealtimeTranscriptionService:
    def __init__(self, config: TranscriptionConfig) -> None:
        self._config = config

    async def transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        if not self._config.api_key:
            yield TranscriptionEvent.error_event("OpenAI API key is missing.")
            return

        try:
            async for event in self._transcribe(audio_chunks):
                yield event
        except TimeoutError:
            yield TranscriptionEvent.error_event("Timed out while waiting for final transcript.")
        except OSError:
            yield TranscriptionEvent.error_event("Network error while contacting OpenAI.")
        except WebSocketException as exc:
            yield TranscriptionEvent.error_event(
                f"Realtime transcription connection failed: {_safe_error_detail(exc)}"
            )
        except Exception as exc:
            yield TranscriptionEvent.error_event(
                f"Realtime transcription failed: {_safe_error_detail(exc)}"
            )

    async def _transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        async with websockets.connect(
            websocket_url(self._config),
            additional_headers={"Authorization": f"Bearer {self._config.api_key}"},
            open_timeout=self._config.connect_timeout_seconds,
        ) as websocket:
            await websocket.send(json.dumps(build_session_update(self._config)))
            sender = asyncio.create_task(send_audio(websocket, audio_chunks))
            try:
                while True:
                    raw_event = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=self._config.final_timeout_seconds,
                    )
                    event = parse_realtime_event(json.loads(raw_event))
                    if event is None:
                        continue
                    yield event
                    if event.type in {TranscriptionEventType.FINAL, TranscriptionEventType.ERROR}:
                        break
            finally:
                if not sender.done():
                    sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)


def websocket_url(config: TranscriptionConfig) -> str:
    return f"{config.websocket_base_url}?{urlencode({'intent': 'transcription'})}"


def build_session_update(config: TranscriptionConfig) -> dict[str, Any]:
    transcription: dict[str, Any] = {
        "model": config.model,
        "delay": config.delay,
    }
    if config.language:
        transcription["language"] = config.language

    return {
        "type": "session.update",
        "session": {
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": config.sample_rate,
                    },
                    "transcription": transcription,
                    "turn_detection": None,
                }
            },
        },
    }


async def send_audio(
    websocket,
    audio_chunks: AsyncIterable[AudioChunk | bytes],
) -> None:
    async for chunk in audio_chunks:
        pcm = chunk.pcm if isinstance(chunk, AudioChunk) else chunk
        if not pcm:
            continue
        await websocket.send(
            json.dumps(
                {
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(pcm).decode("ascii"),
                }
            )
        )

    await websocket.send(json.dumps({"type": "input_audio_buffer.commit"}))


def parse_realtime_event(raw_event: dict[str, Any]) -> TranscriptionEvent | None:
    event_type = raw_event.get("type")
    if event_type == DELTA_EVENT:
        return TranscriptionEvent.partial(
            str(raw_event.get("delta") or ""),
            item_id=_optional_str(raw_event.get("item_id")),
        )
    if event_type == COMPLETED_EVENT:
        return TranscriptionEvent.final(
            str(raw_event.get("transcript") or ""),
            item_id=_optional_str(raw_event.get("item_id")),
        )
    if event_type == ERROR_EVENT:
        error = raw_event.get("error") or {}
        message = error.get("message") if isinstance(error, dict) else None
        return TranscriptionEvent.error_event(str(message or "OpenAI realtime error."))
    return None


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _safe_error_detail(exc: Exception) -> str:
    detail = str(exc).strip()
    return detail or exc.__class__.__name__
