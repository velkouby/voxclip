# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

from __future__ import annotations

import queue
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .level_meter import calculate_rms_level
from .resample import TARGET_SAMPLE_RATE, float32_to_pcm16_bytes, resample_linear


class AudioCaptureError(RuntimeError):
    """Raised when microphone capture cannot start or continue."""


@dataclass(frozen=True)
class AudioChunk:
    pcm: bytes
    rms: float
    sample_rate: int = TARGET_SAMPLE_RATE


@dataclass(frozen=True)
class MicrophoneCaptureConfig:
    device_id: str | None = None
    sample_rate: int = TARGET_SAMPLE_RATE
    block_size: int = 1024


class MicrophoneCapture:
    def __init__(self, config: MicrophoneCaptureConfig | None = None) -> None:
        self._config = config or MicrophoneCaptureConfig()
        self._queue: queue.Queue[AudioChunk] = queue.Queue()
        self._error: AudioCaptureError | None = None
        self._stream = None

    def __enter__(self) -> MicrophoneCapture:
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()

    def start(self) -> None:
        if self._stream is not None:
            return

        try:
            import sounddevice as sd

            self._stream = sd.InputStream(
                samplerate=self._config.sample_rate,
                blocksize=self._config.block_size,
                channels=1,
                device=_device_arg(self._config.device_id),
                dtype="float32",
                callback=self._on_audio,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise AudioCaptureError("Unable to start microphone capture") from exc

    def stop(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None

    def read(self, timeout: float = 0.1) -> AudioChunk | None:
        if self._error is not None:
            raise self._error
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            if self._error is not None:
                raise self._error from None
            return None

    def _on_audio(
        self,
        indata: NDArray[np.float32],
        frames: int,
        time,
        status,
    ) -> None:
        del frames, time
        if status:
            self._error = AudioCaptureError(f"Microphone stream status: {status}")
            return

        samples = resample_linear(indata, self._config.sample_rate, TARGET_SAMPLE_RATE)
        self._queue.put(
            AudioChunk(
                pcm=float32_to_pcm16_bytes(samples),
                rms=calculate_rms_level(samples),
            )
        )


def _device_arg(device_id: str | None) -> int | None:
    if device_id is None:
        return None
    try:
        return int(device_id)
    except ValueError as exc:
        raise AudioCaptureError(f"Invalid audio device id: {device_id}") from exc
