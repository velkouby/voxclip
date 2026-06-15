# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import numpy as np
from numpy.typing import NDArray

TARGET_SAMPLE_RATE = 16_000


class AudioConversionError(ValueError):
    """Raised when audio samples cannot be converted to the target format."""


def to_mono_float32(samples: NDArray[np.generic]) -> NDArray[np.float32]:
    audio = np.asarray(samples, dtype=np.float32)
    if audio.ndim == 1:
        return audio
    if audio.ndim == 2:
        if audio.shape[1] == 0:
            raise AudioConversionError("Audio data has no channels")
        return np.mean(audio, axis=1, dtype=np.float32)
    raise AudioConversionError(f"Unsupported audio shape: {audio.shape}")


def resample_linear(
    samples: NDArray[np.generic],
    source_rate: int,
    target_rate: int = TARGET_SAMPLE_RATE,
) -> NDArray[np.float32]:
    if source_rate <= 0 or target_rate <= 0:
        raise AudioConversionError("Sample rates must be positive")

    mono = to_mono_float32(samples)
    if mono.size == 0 or source_rate == target_rate:
        return mono.astype(np.float32, copy=True)

    target_length = max(1, round(mono.size * target_rate / source_rate))
    source_positions = np.arange(mono.size, dtype=np.float32)
    target_positions = np.linspace(0, mono.size - 1, num=target_length, dtype=np.float32)
    return np.interp(target_positions, source_positions, mono).astype(np.float32)


def float32_to_pcm16_bytes(samples: NDArray[np.generic]) -> bytes:
    mono = to_mono_float32(samples)
    clipped = np.clip(mono, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    return pcm.tobytes()
