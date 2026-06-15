# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import asyncio
import json
import tempfile
import urllib.request
import wave
from collections.abc import AsyncIterable, AsyncIterator
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import websockets
from websockets.exceptions import WebSocketException

from vox_voice_paste.audio import AudioChunk
from vox_voice_paste.config import (
    SONIOX_ASYNC_TRANSCRIPTION_MODEL,
    SONIOX_REALTIME_TRANSCRIPTION_MODEL,
)

from .base import TranscriptionConfig, TranscriptionEvent, TranscriptionEventType
from .openai_realtime import _safe_error_detail

END_TOKEN = "<end>"
SONIOX_ITEM_ID = "soniox"
SONIOX_API_BASE_URL = "https://api.soniox.com/v1"


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
            parser = SonioxEventParser()
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


class SonioxAsyncTranscriptionService:
    def __init__(
        self,
        config: TranscriptionConfig,
        *,
        polling_interval_seconds: float = 0.25,
    ) -> None:
        self._config = config
        self._polling_interval_seconds = polling_interval_seconds

    async def transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        if not self._config.api_key:
            yield TranscriptionEvent.error_event(
                "Soniox API key is missing.",
                error_context=safe_async_error_context(self._config, stage="api_key"),
            )
            return

        try:
            async for event in self._transcribe(audio_chunks):
                yield event
        except TimeoutError:
            yield TranscriptionEvent.error_event(
                "Timed out while waiting for final transcript.",
                error_context=safe_async_error_context(
                    self._config,
                    stage="final_timeout",
                ),
            )
        except HTTPError as exc:
            yield TranscriptionEvent.error_event(
                "Soniox async transcription request failed: "
                f"{_parse_http_error(exc)}",
                error_context=safe_async_error_context(
                    self._config,
                    stage="http",
                    exception_type=exc.__class__.__name__,
                ),
            )
        except OSError:
            yield TranscriptionEvent.error_event(
                "Network error while contacting Soniox.",
                error_context=safe_async_error_context(self._config, stage="network"),
            )
        except Exception as exc:
            yield TranscriptionEvent.error_event(
                f"Soniox async transcription failed: {_safe_error_detail(exc)}",
                error_context=safe_async_error_context(
                    self._config,
                    stage="unexpected",
                    exception_type=exc.__class__.__name__,
                ),
            )

    async def _transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        raw_audio = await _collect_raw_audio(audio_chunks)
        if not raw_audio:
            return

        with tempfile.TemporaryDirectory() as scratch_dir:
            wav_path = await asyncio.to_thread(
                _write_wav_file,
                raw_audio,
                self._config.sample_rate,
                Path(scratch_dir),
            )
            file_id = await self._upload_file(wav_path)
            transcription_id = await self._create_transcription(file_id)
            transcript_text = await self._wait_for_transcript(transcription_id)

        yield TranscriptionEvent.final(transcript_text, item_id=SONIOX_ITEM_ID)

    async def _upload_file(self, wav_path: Path) -> str:
        raw_body, headers = _build_multipart_form(wav_path)
        response = await asyncio.to_thread(
            _request_json,
            api_key=self._config.api_key,
            method="POST",
            path="files",
            timeout_seconds=self._config.connect_timeout_seconds,
            raw_body=raw_body,
            headers=headers,
        )
        return response["id"]

    async def _create_transcription(self, file_id: str) -> str:
        payload = {
            "model": self._config.model,
            "file_id": file_id,
        }
        if self._config.language:
            payload["language_hints"] = [self._config.language]

        response = await asyncio.to_thread(
            _request_json,
            api_key=self._config.api_key,
            method="POST",
            path="transcriptions",
            timeout_seconds=self._config.connect_timeout_seconds,
            payload=payload,
        )
        return response["id"]

    async def _wait_for_transcript(self, transcription_id: str) -> str:
        deadline = asyncio.get_running_loop().time() + self._config.final_timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            status = await self._get_transcription_status(transcription_id)
            state = status.get("status")
            if state == "completed":
                transcript = await self._get_transcript(transcription_id)
                return transcript.get("text", "")
            if state == "error":
                raise RuntimeError(
                    status.get("error_message", "Soniox async transcription failed.")
                )
            if state not in {"queued", "processing"}:
                raise RuntimeError(f"Unexpected transcription state: {state}")
            await asyncio.sleep(self._polling_interval_seconds)

        raise TimeoutError("Timed out while waiting for async transcription to complete.")

    async def _get_transcription_status(self, transcription_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(
            _request_json,
            api_key=self._config.api_key,
            method="GET",
            path=f"transcriptions/{transcription_id}",
            timeout_seconds=self._config.final_timeout_seconds,
        )

    async def _get_transcript(self, transcription_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(
            _request_json,
            api_key=self._config.api_key,
            method="GET",
            path=f"transcriptions/{transcription_id}/transcript",
            timeout_seconds=self._config.final_timeout_seconds,
        )


def build_soniox_config(config: TranscriptionConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "api_key": config.api_key,
        "model": config.model or SONIOX_REALTIME_TRANSCRIPTION_MODEL,
        "audio_format": "pcm_s16le",
        "sample_rate": config.sample_rate,
        "num_channels": 1,
        "enable_language_identification": True,
        "enable_endpoint_detection": True,
        "max_endpoint_delay_ms": endpoint_delay_ms(config.delay),
    }
    if config.language:
        payload["language_hints"] = [config.language]
    return payload


def build_safe_soniox_config(config: TranscriptionConfig) -> dict[str, Any]:
    payload = build_soniox_config(config)
    payload["api_key"] = "<redacted>"
    return payload


def build_soniox_async_config(config: TranscriptionConfig) -> dict[str, Any]:
    model = config.model or SONIOX_ASYNC_TRANSCRIPTION_MODEL
    payload: dict[str, Any] = {
        "model": model,
    }
    if config.language:
        payload["language_hints"] = [config.language]
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
        "model": config.model or SONIOX_REALTIME_TRANSCRIPTION_MODEL,
        "language": config.language,
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


def safe_async_error_context(
    config: TranscriptionConfig,
    *,
    stage: str,
    exception_type: str | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "provider": "soniox",
        "transport": "http",
        "stage": stage,
        "endpoint": SONIOX_API_BASE_URL,
        "model": config.model or SONIOX_ASYNC_TRANSCRIPTION_MODEL,
        "language": config.language,
        "delay": config.delay,
        "sample_rate": config.sample_rate,
        "connect_timeout_seconds": config.connect_timeout_seconds,
        "final_timeout_seconds": config.final_timeout_seconds,
        "request_config": build_soniox_async_config(config),
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
    def __init__(self) -> None:
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


def _parse_error(raw_event: dict[str, Any]) -> str | None:
    error_code = raw_event.get("error_code")
    error_message = raw_event.get("error_message")
    if not error_code and not error_message:
        return None
    if error_code and error_message:
        return f"{error_code}: {error_message}"
    return str(error_message or error_code)


def _parse_http_error(exc: Exception) -> str:
    if not isinstance(exc, HTTPError):
        return _safe_error_detail(exc)

    try:
        raw_error = exc.read().decode("utf-8", errors="replace")
        payload = json.loads(raw_error)
        if isinstance(payload, dict):
            message = payload.get("message")
            if message:
                return str(message)
            return str(payload.get("error_type", str(exc)))
        return str(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, OSError):
        return str(exc)


async def _collect_raw_audio(audio_chunks: AsyncIterable[AudioChunk | bytes]) -> bytes:
    chunks: list[bytes] = []
    async for chunk in audio_chunks:
        if isinstance(chunk, AudioChunk):
            chunk = chunk.pcm
        if chunk:
            chunks.append(chunk)
    return b"".join(chunks)


def _write_wav_file(raw_audio: bytes, sample_rate: int, scratch_dir: Path) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=scratch_dir) as wav_file:
        with wave.open(wav_file, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(raw_audio)
        return Path(wav_file.name)


def _build_multipart_form(
    file_path: Path, *, field_name: str = "file"
) -> tuple[bytes, dict[str, str]]:
    boundary = "----voxclip-soniox"
    payload = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_path.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    payload += file_path.read_bytes()
    payload += f"\r\n--{boundary}--\r\n".encode()
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    return payload, headers


def _request_json(
    *,
    api_key: str,
    method: str,
    path: str,
    timeout_seconds: float,
    payload: dict[str, Any] | None = None,
    raw_body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    request_body: bytes | None = None
    if raw_body is not None:
        request_body = raw_body
    elif payload is not None:
        request_body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{SONIOX_API_BASE_URL}/{path}",
        data=request_body,
        headers=request_headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
    if not raw:
        return {}
    return json.loads(raw)
