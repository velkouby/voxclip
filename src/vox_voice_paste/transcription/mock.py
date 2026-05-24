from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator

from vox_voice_paste.audio import AudioChunk

from .base import TranscriptionEvent


class MockTranscriptionService:
    def __init__(
        self,
        transcript: str = "Ceci est une transcription de test.",
        *,
        delay_seconds: float = 0.01,
    ) -> None:
        self._transcript = transcript
        self._delay_seconds = delay_seconds

    @property
    def transcript(self) -> str:
        return self._transcript

    @property
    def delay_seconds(self) -> float:
        return self._delay_seconds

    async def transcribe(
        self,
        audio_chunks: AsyncIterable[AudioChunk | bytes],
    ) -> AsyncIterator[TranscriptionEvent]:
        async for _ in audio_chunks:
            break

        words = self._transcript.split()
        item_id = "mock-item"
        for word in words:
            await asyncio.sleep(self._delay_seconds)
            yield TranscriptionEvent.partial(f"{word} ", item_id=item_id)

        await asyncio.sleep(self._delay_seconds)
        yield TranscriptionEvent.final(self._transcript, item_id=item_id)
