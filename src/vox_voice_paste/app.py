from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from vox_voice_paste.transcription import MockTranscriptionService
from vox_voice_paste.ui.recorder_window import RecorderWindow


def run_record_and_copy(*, mock: bool = False) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    service = MockTranscriptionService(delay_seconds=0.05) if mock else None
    window = RecorderWindow(
        transcription_service=service,
        auto_start=True,
        close_on_success=True,
    )
    window.show()
    return int(app.exec())
