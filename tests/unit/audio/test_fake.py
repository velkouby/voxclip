from __future__ import annotations

from vox_voice_paste.audio import TARGET_SAMPLE_RATE, FakeAudioSource


def test_fake_audio_source_generates_pcm_chunks() -> None:
    source = FakeAudioSource.sine_wave(duration_seconds=0.05, chunk_size=240)
    chunks = list(source)

    assert chunks
    assert {chunk.sample_rate for chunk in chunks} == {TARGET_SAMPLE_RATE}
    assert all(chunk.pcm for chunk in chunks)
    assert all(0.0 <= chunk.rms <= 1.0 for chunk in chunks)
