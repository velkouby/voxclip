# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import asyncio
import json
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.exceptions import WebSocketException

from vox_voice_paste.audio import AudioChunk
from vox_voice_paste.config import DEFAULT_SONIOX_TRANSCRIPTION_MODEL

from .base import TranscriptionConfig, TranscriptionEvent, TranscriptionEventType
from .transcript_buffer import normalize_transcript

SONIOX_WEBSOCKET_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
SONIOX_ITEM_ID = "soniox"


class SonioxRealtimeTranscriptionService:
    def __init__(self, config: TranscriptionConfig) -> None:
        self._config = config

    async def transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        if not self._config.api_key:
            yield TranscriptionEvent.error_event("Soniox API key is missing.")
            return

        try:
            async for event in self._transcribe(audio_chunks):
                yield event
        except TimeoutError:
            yield TranscriptionEvent.error_event("Timed out while waiting for final transcript.")
        except OSError:
            yield TranscriptionEvent.error_event("Network error while contacting Soniox.")
        except WebSocketException as exc:
            yield TranscriptionEvent.error_event(
                f"Soniox transcription connection failed: {_safe_error_detail(exc)}"
            )
        except Exception as exc:
            yield TranscriptionEvent.error_event(
                f"Soniox transcription failed: {_safe_error_detail(exc)}"
            )

    async def _transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        async with websockets.connect(
            self._config.websocket_base_url or SONIOX_WEBSOCKET_URL,
            open_timeout=self._config.connect_timeout_seconds,
            close_timeout=self._config.close_timeout_seconds,
        ) as websocket:
            await websocket.send(json.dumps(build_start_request(self._config)))
            sender = asyncio.create_task(send_audio(websocket, audio_chunks))
            state = SonioxTranscriptState()
            try:
                while True:
                    raw_event = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=self._config.final_timeout_seconds,
                    )
                    event = state.apply(json.loads(raw_event))
                    if event is None:
                        continue
                    yield event
                    if event.type in {TranscriptionEventType.FINAL, TranscriptionEventType.ERROR}:
                        break
            finally:
                if not sender.done():
                    sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)


def build_start_request(config: TranscriptionConfig) -> dict[str, Any]:
    request: dict[str, Any] = {
        "api_key": config.api_key,
        "model": config.model or DEFAULT_SONIOX_TRANSCRIPTION_MODEL,
        "audio_format": "s16le",
        "sample_rate": config.sample_rate,
        "num_channels": 1,
    }
    if config.language:
        request["language_hints"] = [config.language]
    return request


async def send_audio(
    websocket,
    audio_chunks: AsyncIterable[AudioChunk | bytes],
) -> None:
    async for chunk in audio_chunks:
        pcm = chunk.pcm if isinstance(chunk, AudioChunk) else chunk
        if pcm:
            await websocket.send(pcm)
    await websocket.send(b"")


@dataclass
class SonioxTranscriptState:
    _final_tokens: list[str] = field(default_factory=list)
    _seen_final_tokens: set[tuple[Any, Any, str]] = field(default_factory=set)
    _last_visible_text: str = ""

    def apply(self, raw_event: dict[str, Any]) -> TranscriptionEvent | None:
        error = parse_error(raw_event)
        if error is not None:
            return TranscriptionEvent.error_event(error)

        tokens = raw_event.get("tokens") or []
        if not isinstance(tokens, list):
            tokens = []

        non_final_tokens: list[str] = []
        for token in tokens:
            if not isinstance(token, dict):
                continue
            text = str(token.get("text") or "")
            if not text:
                continue
            if token.get("is_final") is True:
                key = (token.get("start_ms"), token.get("end_ms"), text)
                if key not in self._seen_final_tokens:
                    self._seen_final_tokens.add(key)
                    self._final_tokens.append(text)
            else:
                non_final_tokens.append(text)

        final_text = normalize_transcript("".join(self._final_tokens))
        visible_text = normalize_transcript(final_text + " " + "".join(non_final_tokens))

        if raw_event.get("finished") is True:
            return TranscriptionEvent.final(final_text, item_id=SONIOX_ITEM_ID)

        if not visible_text or visible_text == self._last_visible_text:
            return None

        if visible_text.startswith(self._last_visible_text):
            delta = visible_text[len(self._last_visible_text) :]
        else:
            delta = visible_text
        self._last_visible_text = visible_text
        return TranscriptionEvent.partial(delta, item_id=SONIOX_ITEM_ID)


def parse_error(raw_event: dict[str, Any]) -> str | None:
    message = raw_event.get("error_message")
    if message:
        return str(message)
    error = raw_event.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    if isinstance(error, str) and error:
        return error
    return None


def _safe_error_detail(exc: Exception) -> str:
    detail = str(exc).strip()
    return detail or exc.__class__.__name__
