# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from .capture import AudioChunk
from .level_meter import calculate_rms_level
from .resample import TARGET_SAMPLE_RATE, float32_to_pcm16_bytes


@dataclass(frozen=True)
class FakeAudioSource:
    chunks: tuple[AudioChunk, ...]

    @classmethod
    def sine_wave(
        cls,
        *,
        duration_seconds: float = 0.2,
        frequency: float = 440.0,
        sample_rate: int = TARGET_SAMPLE_RATE,
        chunk_size: int = 480,
    ) -> FakeAudioSource:
        frame_count = max(1, round(duration_seconds * sample_rate))
        t = np.arange(frame_count, dtype=np.float32) / sample_rate
        samples = (0.25 * np.sin(2 * np.pi * frequency * t)).astype(np.float32)

        chunks: list[AudioChunk] = []
        for start in range(0, samples.size, chunk_size):
            chunk_samples = samples[start : start + chunk_size]
            chunks.append(
                AudioChunk(
                    pcm=float32_to_pcm16_bytes(chunk_samples),
                    rms=calculate_rms_level(chunk_samples),
                    sample_rate=sample_rate,
                )
            )
        return cls(tuple(chunks))

    def __iter__(self) -> Iterator[AudioChunk]:
        return iter(self.chunks)
