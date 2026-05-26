# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import numpy as np
from numpy.typing import NDArray

from .resample import to_mono_float32


def calculate_rms_level(samples: NDArray[np.generic]) -> float:
    mono = to_mono_float32(samples)
    if mono.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(np.clip(mono, -1.0, 1.0)), dtype=np.float64)))
    return max(0.0, min(1.0, rms))


def pcm16_rms_level(pcm: bytes) -> float:
    if not pcm:
        return 0.0
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    return calculate_rms_level(samples)
