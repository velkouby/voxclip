from __future__ import annotations

import numpy as np

from vox_voice_paste.audio import float32_to_pcm16_bytes, resample_linear, to_mono_float32


def test_to_mono_float32_averages_channels() -> None:
    stereo = np.array([[1.0, -1.0], [0.5, 0.25]], dtype=np.float32)

    mono = to_mono_float32(stereo)

    np.testing.assert_allclose(mono, np.array([0.0, 0.375], dtype=np.float32))


def test_resample_linear_changes_length() -> None:
    samples = np.linspace(-1.0, 1.0, num=48_000, dtype=np.float32)

    resampled = resample_linear(samples, source_rate=48_000, target_rate=24_000)

    assert resampled.dtype == np.float32
    assert resampled.shape == (24_000,)


def test_float32_to_pcm16_bytes_clips_samples() -> None:
    samples = np.array([-2.0, 0.0, 2.0], dtype=np.float32)

    pcm = float32_to_pcm16_bytes(samples)

    decoded = np.frombuffer(pcm, dtype="<i2")
    assert decoded.tolist() == [-32767, 0, 32767]
