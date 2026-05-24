from __future__ import annotations

from PySide6.QtCore import Qt

from vox_voice_paste.transcription import MockTranscriptionService
from vox_voice_paste.ui import RecorderState, RecorderWindow


def test_recorder_window_starts_in_idle_state(qtbot) -> None:
    window = RecorderWindow(auto_start=False)
    qtbot.addWidget(window)

    assert window.state is RecorderState.IDLE
    assert window.primary_button.text() == "Demarrer"
    assert window.transcript_edit.toPlainText() == ""


def test_recorder_window_mock_transcription_reaches_success(qtbot) -> None:
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("bonjour monde", delay_seconds=0),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state is RecorderState.SUCCESS, timeout=2000)

    assert window.transcript_edit.toPlainText() == "bonjour monde"


def test_recorder_window_enter_stops_recording(qtbot) -> None:
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("bonjour monde", delay_seconds=0.05),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.state is RecorderState.RECORDING, timeout=1000)

    qtbot.keyClick(window, Qt.Key.Key_Return)

    qtbot.waitUntil(
        lambda: window.state
        in {RecorderState.STOPPING, RecorderState.TRANSCRIBING_FINAL, RecorderState.SUCCESS},
        timeout=1000,
    )


def test_recorder_window_escape_cancels(qtbot) -> None:
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("bonjour monde", delay_seconds=0.05),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.state is RecorderState.RECORDING, timeout=1000)

    qtbot.keyClick(window, Qt.Key.Key_Escape)

    assert window.state is RecorderState.CANCELLED


def test_recorder_window_keeps_error_visible(qtbot) -> None:
    window = RecorderWindow(transcription_service=object(), auto_start=True)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state is RecorderState.ERROR, timeout=1000)

    assert "Real transcription UI" in window.status_label.text()
