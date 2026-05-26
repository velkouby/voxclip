# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

from PySide6.QtWidgets import QProgressBar


def create_level_meter() -> QProgressBar:
    meter = QProgressBar()
    meter.setRange(0, 100)
    meter.setTextVisible(False)
    meter.setFixedHeight(12)
    return meter
