from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from vox_voice_paste.audio import FakeAudioSource
from vox_voice_paste.transcription import MockTranscriptionService, TranscriptionEventType


async def _fake_audio() -> AsyncIterator[bytes]:
    for chunk in FakeAudioSource.sine_wave(duration_seconds=0.01):
        yield chunk.pcm


def test_mock_transcription_service_streams_partials_then_final() -> None:
    async def run() -> list:
        service = MockTranscriptionService("bonjour monde", delay_seconds=0)
        return [event async for event in service.transcribe(_fake_audio())]

    events = asyncio.run(run())

    assert [event.type for event in events] == [
        TranscriptionEventType.PARTIAL,
        TranscriptionEventType.PARTIAL,
        TranscriptionEventType.FINAL,
    ]
    assert events[-1].text == "bonjour monde"
