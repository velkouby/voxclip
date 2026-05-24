from __future__ import annotations

import asyncio

from PySide6.QtCore import Qt

from vox_voice_paste.audio import AudioChunk
from vox_voice_paste.desktop import (
    ClipboardError,
    InMemoryClipboardService,
    InMemoryNotificationService,
)
from vox_voice_paste.transcription import MockTranscriptionService, TranscriptionEvent
from vox_voice_paste.ui import RecorderState, RecorderWindow
from vox_voice_paste.ui.recorder_window import RECORD_SYMBOL


def test_recorder_window_starts_in_idle_state(qtbot) -> None:
    window = RecorderWindow(auto_start=False)
    qtbot.addWidget(window)

    assert window.state is RecorderState.IDLE
    assert window.primary_button.text() == RECORD_SYMBOL
    assert window._buffer.text == ""


def test_recorder_window_stays_on_top(qtbot) -> None:
    window = RecorderWindow(auto_start=False)
    qtbot.addWidget(window)

    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


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

    assert window._buffer.final_text == "bonjour monde"
    assert clipboard.text == "bonjour monde"
    assert notifications.notifications[-1].body == "Texte copie. Faites Ctrl+V pour coller."


def test_recorder_window_closes_on_success_when_requested(qtbot) -> None:
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("bonjour monde", delay_seconds=0),
        clipboard_service=InMemoryClipboardService(),
        notification_service=InMemoryNotificationService(),
        auto_start=True,
        close_on_success=True,
    )
    qtbot.addWidget(window)

    with qtbot.waitSignal(window.finished, timeout=2000):
        window.show()

    assert window.state is RecorderState.SUCCESS
    assert not window.isVisible()


def test_recorder_window_stop_button_closes_real_service_on_success(qtbot) -> None:
    clipboard = InMemoryClipboardService()
    window = RecorderWindow(
        transcription_service=StopAwareTranscriptionService(),
        audio_source_factory=stop_controlled_audio_source,
        clipboard_service=clipboard,
        notification_service=InMemoryNotificationService(),
        auto_start=True,
        close_on_success=True,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.state is RecorderState.RECORDING, timeout=1000)

    with qtbot.waitSignal(window.finished, timeout=3000):
        qtbot.mouseClick(window.primary_button, Qt.MouseButton.LeftButton)

    assert clipboard.text == "bonjour monde"
    assert window.state is RecorderState.SUCCESS
    assert not window.isVisible()


def test_recorder_window_force_closes_when_final_never_arrives(
    qtbot, monkeypatch
) -> None:
    """When the user clicks Stop and the service never yields FINAL, the
    window must still close after the post-stop deadline so the SessionLock
    is released and the next Ctrl+Alt+N can fire."""
    monkeypatch.setattr(
        "vox_voice_paste.ui.recorder_window.POST_STOP_DEADLINE_MS", 100
    )
    notifications = InMemoryNotificationService()
    clipboard = InMemoryClipboardService()
    window = RecorderWindow(
        transcription_service=NeverFinalTranscriptionService(),
        audio_source_factory=stop_controlled_audio_source,
        clipboard_service=clipboard,
        notification_service=notifications,
        auto_start=True,
        close_on_success=True,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.state is RecorderState.RECORDING, timeout=1000)

    runner = window._runner
    assert runner is not None

    with qtbot.waitSignal(window.finished, timeout=3000):
        qtbot.mouseClick(window.primary_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: not runner.is_running(), timeout=2000)
    assert not window.isVisible()
    assert clipboard.text is None
    assert any(
        "incomplete" in n.body.lower() or "final" in n.body.lower()
        for n in notifications.notifications
    )


def test_recorder_window_force_closes_on_error_in_close_on_success_mode(qtbot) -> None:
    """A service error (e.g. network failure) must close the window when
    running in record-and-copy mode, surfacing the failure via a system
    notification instead of pinning the dialog open."""
    notifications = InMemoryNotificationService()
    clipboard = InMemoryClipboardService()
    window = RecorderWindow(
        transcription_service=ErroringTranscriptionService(),
        audio_source_factory=stop_controlled_audio_source,
        clipboard_service=clipboard,
        notification_service=notifications,
        auto_start=True,
        close_on_success=True,
    )
    qtbot.addWidget(window)

    with qtbot.waitSignal(window.finished, timeout=3000):
        window.show()

    assert window.state is RecorderState.ERROR
    assert not window.isVisible()
    assert clipboard.text is None
    assert any(
        "connection" in n.body.lower() or "failed" in n.body.lower()
        for n in notifications.notifications
    )


def test_recorder_window_quits_when_async_service_lingers_after_final(qtbot) -> None:
    """Simulates a transcription service that yields FINAL and then would hang
    indefinitely on cleanup (e.g. a slow websocket close handshake). The
    recorder window must cancel the runner so the worker thread exits quickly
    and the Qt event loop can quit."""
    clipboard = InMemoryClipboardService()
    service = LingeringTranscriptionService()
    window = RecorderWindow(
        transcription_service=service,
        audio_source_factory=stop_controlled_audio_source,
        clipboard_service=clipboard,
        notification_service=InMemoryNotificationService(),
        auto_start=True,
        close_on_success=True,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.state is RecorderState.RECORDING, timeout=1000)

    runner = window._runner
    assert runner is not None

    with qtbot.waitSignal(window.finished, timeout=3000):
        qtbot.mouseClick(window.primary_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: not runner.is_running(), timeout=2000)
    assert window._runner is None
    assert window.state is RecorderState.SUCCESS
    assert clipboard.text == "bonjour monde"
    assert service.cleanup_observed is True


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


def test_recorder_window_surfaces_clipboard_error_in_status(qtbot) -> None:
    window = RecorderWindow(
        transcription_service=MockTranscriptionService("bonjour monde", delay_seconds=0),
        clipboard_service=FailingClipboardService(),
        notification_service=InMemoryNotificationService(),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state is RecorderState.ERROR, timeout=1000)

    assert window._buffer.text == "bonjour monde"
    assert "clipboard failed" in window.status_label.text()


def test_recorder_window_real_service_path_uses_audio_source(qtbot) -> None:
    clipboard = InMemoryClipboardService()
    window = RecorderWindow(
        transcription_service=EchoTranscriptionService(),
        audio_source_factory=fake_audio_source,
        device_id="7",
        clipboard_service=clipboard,
        notification_service=InMemoryNotificationService(),
        auto_start=True,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state is RecorderState.SUCCESS, timeout=2000)

    assert clipboard.text == "bonjour monde"
    assert window._level_active is False


class FailingClipboardService:
    def copy_text(self, text: str) -> None:
        raise ClipboardError("clipboard failed")


class EchoTranscriptionService:
    async def transcribe(self, audio_chunks):
        async for _ in audio_chunks:
            yield TranscriptionEvent.partial("bonjour ", item_id="real")
            break
        yield TranscriptionEvent.final("bonjour monde", item_id="real")


class StopAwareTranscriptionService:
    async def transcribe(self, audio_chunks):
        async for _ in audio_chunks:
            pass
        yield TranscriptionEvent.final("bonjour monde", item_id="real")


class NeverFinalTranscriptionService:
    """Consumes the audio stream but never yields FINAL — exits only on cancel."""

    async def transcribe(self, audio_chunks):
        async for _ in audio_chunks:
            pass
        await asyncio.sleep(30.0)
        if False:  # pragma: no cover - keeps this an async generator
            yield TranscriptionEvent.final("", item_id="real")


class ErroringTranscriptionService:
    async def transcribe(self, audio_chunks):
        async for _ in audio_chunks:
            break
        yield TranscriptionEvent.error_event(
            "Realtime transcription failed: connection refused"
        )


class LingeringTranscriptionService:
    """Yields FINAL then awaits forever — only exits via task cancellation."""

    def __init__(self) -> None:
        self.cleanup_observed = False

    async def transcribe(self, audio_chunks):
        async for _ in audio_chunks:
            pass
        yield TranscriptionEvent.final("bonjour monde", item_id="real")
        try:
            await asyncio.sleep(30.0)
        except asyncio.CancelledError:
            self.cleanup_observed = True
            raise


async def fake_audio_source(device_id, stop_requested, cancel_requested):
    del device_id, stop_requested, cancel_requested
    yield AudioChunk(pcm=b"abc", rms=0.5)


async def stop_controlled_audio_source(device_id, stop_requested, cancel_requested):
    del device_id
    while not stop_requested.is_set() and not cancel_requested.is_set():
        yield AudioChunk(pcm=b"abc", rms=0.5)
        await asyncio.sleep(0.01)
