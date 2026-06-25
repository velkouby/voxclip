# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import asyncio
import json
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

import websockets
from websockets.exceptions import WebSocketException

from vox_voice_paste.audio import AudioChunk
from vox_voice_paste.config import normalize_soniox_transcription_model

from .base import TranscriptionConfig, TranscriptionEvent, TranscriptionEventType
from .openai_realtime import _safe_error_detail

END_TOKEN = "<end>"
SONIOX_ITEM_ID = "soniox"


class SonioxRealtimeTranscriptionService:
    def __init__(self, config: TranscriptionConfig) -> None:
        self._config = config

    async def transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        if not self._config.api_key:
            yield TranscriptionEvent.error_event(
                "Soniox API key is missing.",
                error_context=safe_realtime_error_context(self._config, stage="api_key"),
            )
            return

        try:
            async for event in self._transcribe(audio_chunks):
                yield event
        except TimeoutError:
            yield TranscriptionEvent.error_event(
                "Timed out while waiting for final transcript.",
                error_context=safe_realtime_error_context(
                    self._config,
                    stage="final_timeout",
                ),
            )
        except OSError:
            yield TranscriptionEvent.error_event(
                "Network error while contacting Soniox.",
                error_context=safe_realtime_error_context(self._config, stage="network"),
            )
        except WebSocketException as exc:
            yield TranscriptionEvent.error_event(
                "Soniox realtime transcription connection failed: "
                f"{_safe_error_detail(exc)}",
                error_context=safe_realtime_error_context(
                    self._config,
                    stage="websocket",
                    exception_type=exc.__class__.__name__,
                ),
            )
        except Exception as exc:
            yield TranscriptionEvent.error_event(
                f"Soniox realtime transcription failed: {_safe_error_detail(exc)}",
                error_context=safe_realtime_error_context(
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
            self._config.websocket_base_url,
            open_timeout=self._config.connect_timeout_seconds,
            close_timeout=self._config.close_timeout_seconds,
        ) as websocket:
            await websocket.send(json.dumps(build_soniox_config(self._config)))
            sender = asyncio.create_task(send_audio(websocket, audio_chunks))
            parser = SonioxEventParser(
                translation_only=self._config.translation_target_language is not None
            )
            try:
                while True:
                    raw_event = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=self._config.final_timeout_seconds,
                    )
                    events = parser.parse(json.loads(raw_event))
                    for event in events:
                        if (
                            event.type is TranscriptionEventType.ERROR
                            and event.error_context is None
                        ):
                            event = TranscriptionEvent.error_event(
                                event.error or "Soniox realtime transcription failed.",
                                error_context=safe_realtime_error_context(
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


def build_soniox_config(config: TranscriptionConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "api_key": config.api_key,
        "model": normalize_soniox_transcription_model(config.model),
        "audio_format": "pcm_s16le",
        "sample_rate": config.sample_rate,
        "num_channels": 1,
        "enable_language_identification": True,
        "enable_endpoint_detection": True,
        "max_endpoint_delay_ms": endpoint_delay_ms(config.delay),
    }
    if config.language:
        payload["language_hints"] = [config.language]
    if config.translation_target_language:
        payload["translation"] = {
            "type": "one_way",
            "target_language": config.translation_target_language,
        }
    return payload


def build_safe_soniox_config(config: TranscriptionConfig) -> dict[str, Any]:
    payload = build_soniox_config(config)
    payload["api_key"] = "<redacted>"
    return payload


def safe_realtime_error_context(
    config: TranscriptionConfig,
    *,
    stage: str,
    exception_type: str | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "provider": "soniox",
        "transport": "websocket",
        "stage": stage,
        "endpoint": config.websocket_base_url,
        "model": normalize_soniox_transcription_model(config.model),
        "language": config.language,
        "translation_target_language": config.translation_target_language,
        "delay": config.delay,
        "sample_rate": config.sample_rate,
        "connect_timeout_seconds": config.connect_timeout_seconds,
        "final_timeout_seconds": config.final_timeout_seconds,
        "close_timeout_seconds": config.close_timeout_seconds,
        "request_config": build_safe_soniox_config(config),
    }
    if exception_type is not None:
        context["exception_type"] = exception_type
    return context


def endpoint_delay_ms(delay: str) -> int:
    return {
        "minimal": 500,
        "low": 500,
        "medium": 1000,
        "high": 2000,
        "xhigh": 3000,
    }.get(delay, 500)


async def send_audio(
    websocket,
    audio_chunks: AsyncIterable[AudioChunk | bytes],
) -> None:
    async for chunk in audio_chunks:
        pcm = chunk.pcm if isinstance(chunk, AudioChunk) else chunk
        if not pcm:
            continue
        await websocket.send(pcm)

    await websocket.send("")


class SonioxEventParser:
    def __init__(self, *, translation_only: bool = False) -> None:
        self._translation_only = translation_only
        self._final_parts: list[str] = []
        self._partial_text = ""

    def parse(self, raw_event: dict[str, Any]) -> list[TranscriptionEvent]:
        error = _parse_error(raw_event)
        if error is not None:
            return [TranscriptionEvent.error_event(error)]

        events: list[TranscriptionEvent] = []
        partial = self._parse_tokens(raw_event.get("tokens"))
        if partial:
            events.append(TranscriptionEvent.partial(partial, item_id=SONIOX_ITEM_ID))

        if raw_event.get("finished") is True:
            events.append(
                TranscriptionEvent.final(
                    "".join(self._final_parts),
                    item_id=SONIOX_ITEM_ID,
                )
            )
        return events

    def _parse_tokens(self, raw_tokens: Any) -> str:
        if not isinstance(raw_tokens, list):
            return ""

        partial_parts: list[str] = []
        for token in raw_tokens:
            if not isinstance(token, dict):
                continue
            if not self._should_include_token(token):
                continue
            text = str(token.get("text") or "")
            if not text or text == END_TOKEN:
                continue
            if token.get("is_final") is True:
                self._final_parts.append(text)
            else:
                partial_parts.append(text)
        partial_text = "".join(partial_parts)
        if partial_text.startswith(self._partial_text):
            delta = partial_text[len(self._partial_text) :]
        else:
            delta = partial_text
        self._partial_text = partial_text
        return delta

    def _should_include_token(self, token: dict[str, Any]) -> bool:
        translation_status = token.get("translation_status")
        if self._translation_only:
            return translation_status == "translation"
        return translation_status != "translation"


def _parse_error(raw_event: dict[str, Any]) -> str | None:
    error_code = raw_event.get("error_code")
    error_message = raw_event.get("error_message")
    if not error_code and not error_message:
        return None
    if error_code and error_message:
        return f"{error_code}: {error_message}"
    return str(error_message or error_code)
