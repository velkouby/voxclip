from __future__ import annotations

from PySide6.QtCore import Qt

from vox_voice_paste.audio import AudioChunk, AudioInputDevice
from vox_voice_paste.desktop import (
    ClipboardError,
    InMemoryClipboardService,
    InMemoryNotificationService,
)
from vox_voice_paste.transcription import MockTranscriptionService, TranscriptionEvent
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

    assert "Transcription service is unavailable" in window.status_label.text()


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


def test_recorder_window_real_service_path_uses_audio_source(qtbot) -> None:
    clipboard = InMemoryClipboardService()
    window = RecorderWindow(
        transcription_service=EchoTranscriptionService(),
        audio_source_factory=fake_audio_source,
        input_devices=[
            AudioInputDevice(
                id="7",
                name="USB Mic",
                max_input_channels=1,
                default_sample_rate=24_000,
            )
        ],
        clipboard_service=clipboard,
        notification_service=InMemoryNotificationService(),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state is RecorderState.SUCCESS, timeout=2000)

    assert clipboard.text == "bonjour monde"
    assert window.level_meter.value() == 0


class FailingClipboardService:
    def copy_text(self, text: str) -> None:
        raise ClipboardError("clipboard failed")


class EchoTranscriptionService:
    async def transcribe(self, audio_chunks):
        async for _ in audio_chunks:
            yield TranscriptionEvent.partial("bonjour ", item_id="real")
            break
        yield TranscriptionEvent.final("bonjour monde", item_id="real")


async def fake_audio_source(device_id, stop_requested, cancel_requested):
    del device_id, stop_requested, cancel_requested
    yield AudioChunk(pcm=b"abc", rms=0.5)
