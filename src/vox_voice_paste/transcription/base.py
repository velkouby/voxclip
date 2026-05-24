from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from vox_voice_paste.audio import TARGET_SAMPLE_RATE, AudioChunk
from vox_voice_paste.config import DEFAULT_TRANSCRIPTION_MODEL


class TranscriptionEventType(StrEnum):
    PARTIAL = "partial"
    FINAL = "final"
    ERROR = "error"


@dataclass(frozen=True)
class TranscriptionEvent:
    type: TranscriptionEventType
    text: str = ""
    item_id: str | None = None
    error: str | None = None

    @classmethod
    def partial(cls, text: str, *, item_id: str | None = None) -> TranscriptionEvent:
        return cls(type=TranscriptionEventType.PARTIAL, text=text, item_id=item_id)

    @classmethod
    def final(cls, text: str, *, item_id: str | None = None) -> TranscriptionEvent:
        return cls(type=TranscriptionEventType.FINAL, text=text, item_id=item_id)

    @classmethod
    def error_event(cls, error: str) -> TranscriptionEvent:
        return cls(type=TranscriptionEventType.ERROR, error=error)


@dataclass(frozen=True)
class TranscriptionConfig:
    api_key: str | None = None
    model: str = DEFAULT_TRANSCRIPTION_MODEL
    language: str | None = None
    delay: str = "low"
    sample_rate: int = TARGET_SAMPLE_RATE
    connect_timeout_seconds: float = 10.0
    final_timeout_seconds: float = 20.0
    websocket_base_url: str = "wss://api.openai.com/v1/realtime"


class TranscriptionService(Protocol):
    async def transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]: ...
