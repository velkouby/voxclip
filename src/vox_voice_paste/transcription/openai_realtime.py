# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

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
FAILED_EVENT = "conversation.item.input_audio_transcription.failed"
ERROR_EVENT = "error"


class OpenAIRealtimeTranscriptionService:
    def __init__(self, config: TranscriptionConfig) -> None:
        self._config = config

    async def transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        if not self._config.api_key:
            yield TranscriptionEvent.error_event(
                "OpenAI API key is missing.",
                error_context=safe_error_context(self._config, stage="api_key"),
            )
            return

        try:
            async for event in self._transcribe(audio_chunks):
                yield event
        except TimeoutError:
            yield TranscriptionEvent.error_event(
                "Timed out while waiting for final transcript.",
                error_context=safe_error_context(self._config, stage="final_timeout"),
            )
        except OSError:
            yield TranscriptionEvent.error_event(
                "Network error while contacting OpenAI.",
                error_context=safe_error_context(self._config, stage="network"),
            )
        except WebSocketException as exc:
            yield TranscriptionEvent.error_event(
                f"Realtime transcription connection failed: {_safe_error_detail(exc)}",
                error_context=safe_error_context(
                    self._config,
                    stage="websocket",
                    exception_type=exc.__class__.__name__,
                ),
            )
        except Exception as exc:
            yield TranscriptionEvent.error_event(
                f"Realtime transcription failed: {_safe_error_detail(exc)}",
                error_context=safe_error_context(
                    self._config,
                    stage="unexpected",
                    exception_type=exc.__class__.__name__,
                ),
            )

    async def _transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        async with websockets.connect(
            websocket_url(self._config),
            additional_headers={"Authorization": f"Bearer {self._config.api_key}"},
            open_timeout=self._config.connect_timeout_seconds,
            close_timeout=self._config.close_timeout_seconds,
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
                    if (
                        event.type is TranscriptionEventType.ERROR
                        and event.error_context is None
                    ):
                        event = TranscriptionEvent.error_event(
                            event.error or "OpenAI realtime error.",
                            error_context=safe_error_context(
                                self._config,
                                stage="server_event",
                            ),
                        )
                    yield event
                    if event.type in {
                        TranscriptionEventType.FINAL,
                        TranscriptionEventType.ERROR,
                    }:
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


def safe_error_context(
    config: TranscriptionConfig,
    *,
    stage: str,
    exception_type: str | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "provider": "openai",
        "transport": "websocket",
        "stage": stage,
        "endpoint": websocket_url(config),
        "model": config.model,
        "language": config.language,
        "delay": config.delay,
        "sample_rate": config.sample_rate,
        "connect_timeout_seconds": config.connect_timeout_seconds,
        "final_timeout_seconds": config.final_timeout_seconds,
        "close_timeout_seconds": config.close_timeout_seconds,
        "session_update": build_session_update(config),
    }
    if exception_type is not None:
        context["exception_type"] = exception_type
    return context


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
    if event_type == FAILED_EVENT:
        error = raw_event.get("error") or {}
        message = error.get("message") if isinstance(error, dict) else None
        return TranscriptionEvent.error_event(
            str(message or "OpenAI realtime transcription failed.")
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
