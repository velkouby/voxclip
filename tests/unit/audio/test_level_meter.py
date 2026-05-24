from __future__ import annotations

import numpy as np

from vox_voice_paste.audio import calculate_rms_level, float32_to_pcm16_bytes, pcm16_rms_level


def test_calculate_rms_level_for_silence() -> None:
    assert calculate_rms_level(np.zeros(100, dtype=np.float32)) == 0.0


def test_pcm16_rms_level_is_normalized() -> None:
    pcm = float32_to_pcm16_bytes(np.ones(100, dtype=np.float32) * 0.5)

    level = pcm16_rms_level(pcm)

    assert 0.49 < level < 0.51
