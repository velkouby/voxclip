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
from vox_voice_paste.config import DEFAULT_TRANSLATION_TARGET_LANGUAGE, normalize_language_code

from .base import TranscriptionConfig, TranscriptionEvent, TranscriptionEventType
from .openai_realtime import _safe_error_detail

OUTPUT_TRANSCRIPT_DELTA_EVENT = "session.output_transcript.delta"
SESSION_CLOSED_EVENT = "session.closed"
ERROR_EVENT = "error"
OPENAI_TRANSLATION_ITEM_ID = "openai-translation"


class OpenAIRealtimeTranslationService:
    def __init__(self, config: TranscriptionConfig) -> None:
        self._config = config

    async def transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        if not self._config.api_key:
            yield TranscriptionEvent.error_event(
                "OpenAI API key is missing.",
                error_context=safe_translation_error_context(self._config, stage="api_key"),
            )
            return

        try:
            async for event in self._transcribe(audio_chunks):
                yield event
        except TimeoutError:
            yield TranscriptionEvent.error_event(
                "Timed out while waiting for final translation.",
                error_context=safe_translation_error_context(
                    self._config,
                    stage="final_timeout",
                ),
            )
        except OSError:
            yield TranscriptionEvent.error_event(
                "Network error while contacting OpenAI.",
                error_context=safe_translation_error_context(self._config, stage="network"),
            )
        except WebSocketException as exc:
            yield TranscriptionEvent.error_event(
                f"Realtime translation connection failed: {_safe_error_detail(exc)}",
                error_context=safe_translation_error_context(
                    self._config,
                    stage="websocket",
                    exception_type=exc.__class__.__name__,
                ),
            )
        except Exception as exc:
            yield TranscriptionEvent.error_event(
                f"Realtime translation failed: {_safe_error_detail(exc)}",
                error_context=safe_translation_error_context(
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
            translation_websocket_url(self._config),
            additional_headers={"Authorization": f"Bearer {self._config.api_key}"},
            open_timeout=self._config.connect_timeout_seconds,
            close_timeout=self._config.close_timeout_seconds,
        ) as websocket:
            await websocket.send(json.dumps(build_translation_session_update(self._config)))
            sender = asyncio.create_task(send_translation_audio(websocket, audio_chunks))
            parser = OpenAITranslationEventParser()
            try:
                while True:
                    raw_event = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=self._config.final_timeout_seconds,
                    )
                    event = parser.parse(json.loads(raw_event))
                    if event is None:
                        continue
                    if (
                        event.type is TranscriptionEventType.ERROR
                        and event.error_context is None
                    ):
                        event = TranscriptionEvent.error_event(
                            event.error or "OpenAI realtime translation error.",
                            error_context=safe_translation_error_context(
                                self._config,
                                stage="server_event",
                            ),
                        )
                    yield event
                    if event.type in {
                        TranscriptionEventType.FINAL,
                        TranscriptionEventType.ERROR,
                    }:
                        return
            finally:
                if not sender.done():
                    sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)


def translation_websocket_url(config: TranscriptionConfig) -> str:
    return f"{config.websocket_base_url}?{urlencode({'model': config.model})}"


def build_translation_session_update(config: TranscriptionConfig) -> dict[str, Any]:
    return {
        "type": "session.update",
        "session": {
            "audio": {
                "output": {
                    "language": _translation_target_language(config),
                },
            },
        },
    }


def safe_translation_error_context(
    config: TranscriptionConfig,
    *,
    stage: str,
    exception_type: str | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "provider": "openai",
        "transport": "websocket",
        "mode": "translation",
        "stage": stage,
        "endpoint": translation_websocket_url(config),
        "model": config.model,
        "translation_target_language": _translation_target_language(config),
        "sample_rate": config.sample_rate,
        "connect_timeout_seconds": config.connect_timeout_seconds,
        "final_timeout_seconds": config.final_timeout_seconds,
        "close_timeout_seconds": config.close_timeout_seconds,
        "session_update": build_translation_session_update(config),
    }
    if exception_type is not None:
        context["exception_type"] = exception_type
    return context


async def send_translation_audio(
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
                    "type": "session.input_audio_buffer.append",
                    "audio": base64.b64encode(pcm).decode("ascii"),
                }
            )
        )

    await websocket.send(json.dumps({"type": "session.close"}))


class OpenAITranslationEventParser:
    def __init__(self) -> None:
        self._parts: list[str] = []

    def parse(self, raw_event: dict[str, Any]) -> TranscriptionEvent | None:
        event_type = raw_event.get("type")
        if event_type == OUTPUT_TRANSCRIPT_DELTA_EVENT:
            delta = str(raw_event.get("delta") or "")
            self._parts.append(delta)
            return TranscriptionEvent.partial(delta, item_id=OPENAI_TRANSLATION_ITEM_ID)
        if event_type == SESSION_CLOSED_EVENT:
            return TranscriptionEvent.final(
                "".join(self._parts),
                item_id=OPENAI_TRANSLATION_ITEM_ID,
            )
        if event_type == ERROR_EVENT:
            error = raw_event.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else None
            return TranscriptionEvent.error_event(str(message or "OpenAI realtime error."))
        return None


def _translation_target_language(config: TranscriptionConfig) -> str:
    return (
        normalize_language_code(config.translation_target_language)
        or DEFAULT_TRANSLATION_TARGET_LANGUAGE
    )
