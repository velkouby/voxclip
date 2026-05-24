from __future__ import annotations

import numpy as np
import pytest

from vox_voice_paste.audio import AudioCaptureError, MicrophoneCapture, MicrophoneCaptureConfig


def test_microphone_capture_callback_queues_pcm_chunk() -> None:
    capture = MicrophoneCapture(MicrophoneCaptureConfig(sample_rate=24_000))

    capture._on_audio(np.ones((240, 1), dtype=np.float32) * 0.25, 240, None, None)
    chunk = capture.read(timeout=0)

    assert chunk is not None
    assert chunk.pcm
    assert 0.24 < chunk.rms < 0.26


def test_microphone_capture_callback_surfaces_stream_status() -> None:
    capture = MicrophoneCapture()

    capture._on_audio(np.zeros((240, 1), dtype=np.float32), 240, None, "overflow")

    with pytest.raises(AudioCaptureError):
        capture.read(timeout=0)
