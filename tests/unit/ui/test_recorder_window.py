from __future__ import annotations

from PySide6.QtCore import Qt

from vox_voice_paste.desktop import (
    ClipboardError,
    InMemoryClipboardService,
    InMemoryNotificationService,
)
from vox_voice_paste.transcription import MockTranscriptionService
from vox_voice_paste.ui import RecorderState, RecorderWindow


def test_recorder_window_starts_in_idle_state(qtbot) -> None:
    window = RecorderWindow(auto_start=False)
    qtbot.addWidget(window)

    assert window.state is RecorderState.IDLE
    assert window.primary_button.text() == "Demarrer"
    assert window.transcript_edit.toPlainText() == ""


def test_recorder_window_mock_transcription_reaches_success(qtbot) -> None:
    clipboard = InMemoryClipboardService()
    notifications = InMemoryNotificationService()
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("bonjour monde", delay_seconds=0),
        clipboard_service=clipboard,
        notification_service=notifications,
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state is RecorderState.SUCCESS, timeout=2000)

    assert window.transcript_edit.toPlainText() == "bonjour monde"
    assert clipboard.text == "bonjour monde"
    assert notifications.notifications[-1].body == "Texte copie. Faites Ctrl+V pour coller."


def test_recorder_window_enter_stops_recording(qtbot) -> None:
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("bonjour monde", delay_seconds=0.05),
        clipboard_service=InMemoryClipboardService(),
        notification_service=InMemoryNotificationService(),
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
    clipboard = InMemoryClipboardService()
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("bonjour monde", delay_seconds=0.05),
        clipboard_service=clipboard,
        notification_service=InMemoryNotificationService(),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.state is RecorderState.RECORDING, timeout=1000)

    qtbot.keyClick(window, Qt.Key.Key_Escape)

    assert window.state is RecorderState.CANCELLED
    assert clipboard.text is None


def test_recorder_window_keeps_error_visible(qtbot) -> None:
    window = RecorderWindow(
        transcription_service=object(),
        clipboard_service=InMemoryClipboardService(),
        notification_service=InMemoryNotificationService(),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state is RecorderState.ERROR, timeout=1000)

    assert "Real transcription UI" in window.status_label.text()


def test_recorder_window_refuses_to_copy_empty_transcript(qtbot) -> None:
    clipboard = InMemoryClipboardService()
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("", delay_seconds=0),
        clipboard_service=clipboard,
        notification_service=InMemoryNotificationService(),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state is RecorderState.ERROR, timeout=1000)

    assert clipboard.text is None
    assert "empty text" in window.status_label.text()


def test_recorder_window_keeps_text_visible_when_clipboard_fails(qtbot) -> None:
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("bonjour monde", delay_seconds=0),
        clipboard_service=FailingClipboardService(),
        notification_service=InMemoryNotificationService(),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state is RecorderState.ERROR, timeout=1000)

    assert window.transcript_edit.toPlainText() == "bonjour monde"
    assert "clipboard failed" in window.status_label.text()


class FailingClipboardService:
    def copy_text(self, text: str) -> None:
        raise ClipboardError("clipboard failed")
