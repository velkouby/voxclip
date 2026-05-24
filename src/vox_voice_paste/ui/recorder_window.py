from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections.abc import AsyncIterator, Callable
from enum import StrEnum

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vox_voice_paste.audio import AudioCaptureError, AudioChunk, MicrophoneCapture
from vox_voice_paste.audio.capture import MicrophoneCaptureConfig
from vox_voice_paste.audio.devices import AudioInputDevice
from vox_voice_paste.desktop import (
    ClipboardError,
    ClipboardService,
    DesktopNotificationService,
    NotificationService,
    SystemClipboardService,
)
from vox_voice_paste.transcription import (
    MockTranscriptionService,
    TranscriptBuffer,
    TranscriptionEvent,
    TranscriptionEventType,
    TranscriptionService,
)

from .widgets import create_level_meter

_logger = logging.getLogger(__name__)

FORCE_QUIT_AFTER_SUCCESS_MS = 1500
RUNNER_JOIN_TIMEOUT_SECONDS = 1.0
POST_STOP_DEADLINE_MS = 5000


class RecorderState(StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    STOPPING = "stopping"
    TRANSCRIBING_FINAL = "transcribing_final"
    COPYING = "copying"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


AudioSourceFactory = Callable[
    [str | None, threading.Event, threading.Event],
    AsyncIterator[AudioChunk | bytes],
]


class ThreadedTranscriptionRunner(QObject):
    event_received = Signal(object)
    level_received = Signal(float)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        service: TranscriptionService,
        audio_source_factory: AudioSourceFactory,
        device_id: str | None,
    ) -> None:
        super().__init__()
        self._service = service
        self._audio_source_factory = audio_source_factory
        self._device_id = device_id
        self._stop_requested = threading.Event()
        self._cancel_requested = threading.Event()
        self._loop_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._main_task: asyncio.Task | None = None
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="VoxTranscriptionRunner",
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_requested.set()

    def cancel(self) -> None:
        self._cancel_requested.set()
        self._stop_requested.set()
        self._abort_async_task()

    def _abort_async_task(self) -> None:
        with self._loop_lock:
            loop = self._loop
            task = self._main_task
        if loop is None or task is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(task.cancel)
        except RuntimeError:
            # Loop already closed between the check and the call.
            pass

    def join(self, timeout: float = 1.0) -> None:
        if self._thread.is_alive():
            self._thread.join(timeout)

    def is_running(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        try:
            asyncio.run(self._run_async())
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not self._cancel_requested.is_set():
                self.failed.emit(str(exc) or "Transcription failed.")
        finally:
            with self._loop_lock:
                self._loop = None
                self._main_task = None
            self.finished.emit()

    async def _run_async(self) -> None:
        with self._loop_lock:
            self._loop = asyncio.get_running_loop()
            self._main_task = asyncio.current_task()
        if self._cancel_requested.is_set():
            return
        source = self._audio_source_factory(
            self._device_id,
            self._stop_requested,
            self._cancel_requested,
        )
        audio_chunks = _with_level_signal(source, self.level_received)
        try:
            async for event in self._service.transcribe(audio_chunks):
                if self._cancel_requested.is_set():
                    return
                self.event_received.emit(event)
        finally:
            # Ensure the audio generator chain is closed even if the service
            # exited early or was cancelled, so MicrophoneCapture stops the
            # sounddevice stream before the worker thread exits.
            await _safe_aclose(audio_chunks)


async def _safe_aclose(aiterator: AsyncIterator) -> None:
    aclose = getattr(aiterator, "aclose", None)
    if aclose is None:
        return
    with contextlib.suppress(Exception):
        await aclose()


class RecorderWindow(QDialog):
    def __init__(
        self,
        *,
        transcription_service: TranscriptionService | None = None,
        audio_source_factory: AudioSourceFactory | None = None,
        input_devices: list[AudioInputDevice] | None = None,
        clipboard_service: ClipboardService | None = None,
        notification_service: NotificationService | None = None,
        auto_start: bool = False,
        close_on_success: bool = False,
        force_process_exit_on_success: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = transcription_service or MockTranscriptionService()
        self._audio_source_factory = audio_source_factory or microphone_audio_source
        self._input_devices = input_devices or []
        self._clipboard = clipboard_service or SystemClipboardService()
        self._notifications = notification_service or DesktopNotificationService()
        self._close_on_success = close_on_success
        self._force_process_exit_on_success = force_process_exit_on_success
        self._buffer = TranscriptBuffer()
        self._state = RecorderState.IDLE
        self._level_value = 0
        self._mock_words: list[str] = []
        self._mock_word_index = 0
        self._runner: ThreadedTranscriptionRunner | None = None
        self._finish_after_runner_stops = False

        self._build_ui()
        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._advance_mock_level)
        self._mock_timer = QTimer(self)
        self._mock_timer.timeout.connect(self._emit_mock_transcription_event)

        self.set_state(RecorderState.IDLE)
        if auto_start:
            QTimer.singleShot(0, self.start_recording)

    @property
    def state(self) -> RecorderState:
        return self._state

    def _build_ui(self) -> None:
        self.setWindowTitle("Vox Voice Paste")
        self.setMinimumWidth(520)

        title = QLabel("Vox Voice Paste")
        title.setObjectName("titleLabel")

        self.status_label = QLabel()
        self.device_combo = QComboBox()
        self.device_combo.addItem("Micro par defaut", None)
        for device in self._input_devices:
            marker = " (defaut)" if device.is_default else ""
            self.device_combo.addItem(f"{device.name}{marker}", device.id)

        self.level_meter = create_level_meter()
        self.transcript_edit = QTextEdit()
        self.transcript_edit.setReadOnly(True)
        self.transcript_edit.setMinimumHeight(150)

        self.primary_button = QPushButton("Demarrer")
        self.primary_button.setObjectName("primaryRecordButton")
        self.primary_button.clicked.connect(self._primary_action)

        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.cancel)

        hint = QLabel("Entree pour arreter, Echap pour annuler")
        hint.setObjectName("shortcutHint")

        buttons = QHBoxLayout()
        buttons.addWidget(self.primary_button)
        buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.device_combo)
        layout.addWidget(self.level_meter)
        layout.addWidget(self.transcript_edit)
        layout.addLayout(buttons)
        layout.addWidget(hint)
        self.setLayout(layout)

        self.setStyleSheet(
            """
            QLabel#titleLabel { font-size: 18px; font-weight: 600; }
            QPushButton#primaryRecordButton {
                background: #c62828;
                color: white;
                font-weight: 600;
                min-height: 36px;
            }
            QTextEdit { font-size: 14px; }
            QLabel#shortcutHint { color: #666; }
            """
        )

    def set_state(self, state: RecorderState) -> None:
        self._state = state
        self.status_label.setText(_status_text(state))
        self.primary_button.setText(_primary_button_text(state))
        busy = state in {
            RecorderState.STOPPING,
            RecorderState.TRANSCRIBING_FINAL,
            RecorderState.COPYING,
        }
        self.primary_button.setEnabled(not busy and state not in {RecorderState.SUCCESS})
        self.device_combo.setEnabled(state is RecorderState.IDLE)

    @Slot()
    def start_recording(self) -> None:
        if self._state is RecorderState.RECORDING:
            return
        self._buffer = TranscriptBuffer()
        self.transcript_edit.clear()
        self.set_state(RecorderState.RECORDING)
        self._level_timer.start(80)

        if isinstance(self._service, MockTranscriptionService):
            self._mock_words = self._service.transcript.split()
            self._mock_word_index = 0
            interval_ms = max(1, round(self._service.delay_seconds * 1000))
            self._mock_timer.start(interval_ms)
            return

        if not hasattr(self._service, "transcribe"):
            self._handle_error("Transcription service is unavailable.")
            return

        self._runner = ThreadedTranscriptionRunner(
            service=self._service,
            audio_source_factory=self._audio_source_factory,
            device_id=self.device_combo.currentData(),
        )
        connection_type = Qt.ConnectionType.QueuedConnection
        self._runner.event_received.connect(
            self._handle_transcription_event,
            connection_type,
        )
        self._runner.level_received.connect(self._set_level, connection_type)
        self._runner.failed.connect(self._handle_error, connection_type)
        self._runner.finished.connect(self._runner_finished, connection_type)
        self._runner.start()

    @Slot()
    def stop_recording(self) -> None:
        if self._state is not RecorderState.RECORDING:
            return
        self.set_state(RecorderState.STOPPING)
        if self._runner is not None:
            self._runner.stop()
        QTimer.singleShot(120, self._mark_transcribing_final)
        if self._close_on_success:
            # Hard deadline: if FINAL never arrives the window must still
            # close so the SessionLock is released and Ctrl+Alt+N can start
            # a fresh dictation immediately.
            QTimer.singleShot(POST_STOP_DEADLINE_MS, self._enforce_post_stop_deadline)

    @Slot()
    def cancel(self) -> None:
        self._mock_timer.stop()
        if self._runner is not None:
            self._runner.cancel()
        self._level_timer.stop()
        self.set_state(RecorderState.CANCELLED)
        QTimer.singleShot(120, self.close)

    def _primary_action(self) -> None:
        if self._state is RecorderState.IDLE:
            self.start_recording()
        elif self._state is RecorderState.RECORDING:
            self.stop_recording()

    @Slot(object)
    def _handle_transcription_event(self, event: TranscriptionEvent) -> None:
        if self._state is RecorderState.CANCELLED:
            return
        if event.type is TranscriptionEventType.ERROR:
            self._handle_error(event.error or "Transcription failed.")
            return

        self.transcript_edit.setPlainText(self._buffer.apply(event))
        self.transcript_edit.moveCursor(QTextCursor.MoveOperation.End)
        if event.type is TranscriptionEventType.FINAL:
            self._level_timer.stop()
            self.level_meter.setValue(0)
            self._copy_final_text(self._buffer.final_text)

    @Slot(str)
    def _handle_error(self, message: str) -> None:
        if self._state is RecorderState.CANCELLED:
            return
        self._level_timer.stop()
        self.set_state(RecorderState.ERROR)
        self.status_label.setText(message)
        if self._close_on_success:
            # Headless/record-and-copy mode: surface the error via the OS
            # notifier and close the session so the next Ctrl+Alt+N can run.
            self._close_session(notification=("Vox Voice Paste", message))

    def _copy_final_text(self, text: str) -> None:
        self.set_state(RecorderState.COPYING)
        try:
            self._clipboard.copy_text(text)
        except ClipboardError as exc:
            self._handle_error(str(exc))
            return

        self._notifications.notify(
            "Vox Voice Paste",
            "Texte copie. Faites Ctrl+V pour coller.",
        )
        self.set_state(RecorderState.SUCCESS)
        if self._close_on_success:
            QTimer.singleShot(0, self._finish_after_success)

    @Slot()
    def _mark_transcribing_final(self) -> None:
        if self._state is RecorderState.STOPPING:
            self.set_state(RecorderState.TRANSCRIBING_FINAL)

    @Slot()
    def _runner_finished(self) -> None:
        self._runner = None
        if self._finish_after_runner_stops:
            self._finish_after_runner_stops = False
            self._quit_application()

    @Slot()
    def _finish_after_success(self) -> None:
        if self._state is not RecorderState.SUCCESS:
            return
        self._close_session()

    @Slot()
    def _enforce_post_stop_deadline(self) -> None:
        if self._state in {
            RecorderState.IDLE,
            RecorderState.RECORDING,
            RecorderState.SUCCESS,
            RecorderState.CANCELLED,
        }:
            return
        _logger.warning(
            "Post-stop deadline (%sms) elapsed in state %s; closing session.",
            POST_STOP_DEADLINE_MS,
            self._state,
        )
        self._close_session(
            notification=(
                "Vox Voice Paste",
                "Transcription incomplete: no final text received.",
            )
        )

    def _close_session(
        self,
        *,
        notification: tuple[str, str] | None = None,
    ) -> None:
        """Tear down the dictation session and quit the Qt event loop.

        Hides the window immediately, fires an optional desktop notification,
        cancels the worker thread, and quits via the `finished` signal once
        the worker exits. The optional force-quit watchdog kicks in only if
        the worker fails to emit `finished` within the deadline.
        """
        if notification is not None:
            title, body = notification
            try:
                self._notifications.notify(title, body)
            except Exception:
                _logger.exception("Failed to dispatch close-session notification.")
        self.hide()
        self._mock_timer.stop()
        self._level_timer.stop()
        if self._runner is None or not self._runner.is_running():
            self._quit_application()
            return
        self._finish_after_runner_stops = True
        self._runner.cancel()
        if self._force_process_exit_on_success:
            # Isolated safety net: if the worker thread fails to emit
            # `finished` within the deadline, force the Qt event loop to
            # exit anyway. This does not call os._exit; it just stops
            # waiting on the daemon worker.
            QTimer.singleShot(
                FORCE_QUIT_AFTER_SUCCESS_MS,
                self._force_quit_application,
            )

    @Slot()
    def _force_quit_application(self) -> None:
        if not self._finish_after_runner_stops:
            return
        _logger.warning(
            "Transcription runner did not finish within %sms; forcing Qt quit.",
            FORCE_QUIT_AFTER_SUCCESS_MS,
        )
        self._finish_after_runner_stops = False
        self._quit_application()

    def _quit_application(self) -> None:
        self._mock_timer.stop()
        self._level_timer.stop()
        self.done(QDialog.DialogCode.Accepted)
        app = QApplication.instance()
        if app is not None:
            app.quit()

    @Slot(float)
    def _set_level(self, level: float) -> None:
        self.level_meter.setValue(round(level * 100))

    @Slot()
    def _emit_mock_transcription_event(self) -> None:
        if not isinstance(self._service, MockTranscriptionService):
            self._mock_timer.stop()
            return

        item_id = "mock-item"
        if self._mock_word_index < len(self._mock_words):
            word = self._mock_words[self._mock_word_index]
            self._mock_word_index += 1
            event = TranscriptionEvent.partial(f"{word} ", item_id=item_id)
            self._handle_transcription_event(event)
            return

        self._mock_timer.stop()
        self._handle_transcription_event(
            TranscriptionEvent.final(self._service.transcript, item_id=item_id)
        )

    def _advance_mock_level(self) -> None:
        self._level_value = (self._level_value + 17) % 100
        self.level_meter.setValue(self._level_value)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.stop_recording()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._mock_timer.stop()
        self._level_timer.stop()
        if self._runner is not None:
            self._runner.cancel()
            self._runner.join(timeout=RUNNER_JOIN_TIMEOUT_SECONDS)
        super().closeEvent(event)


def _status_text(state: RecorderState) -> str:
    return {
        RecorderState.IDLE: "Pret a enregistrer",
        RecorderState.RECORDING: "Enregistrement en cours",
        RecorderState.STOPPING: "Arret en cours",
        RecorderState.TRANSCRIBING_FINAL: "Finalisation de la transcription",
        RecorderState.COPYING: "Copie en cours",
        RecorderState.SUCCESS: "Transcription terminee",
        RecorderState.ERROR: "Erreur",
        RecorderState.CANCELLED: "Dictee annulee",
    }[state]


def _primary_button_text(state: RecorderState) -> str:
    if state is RecorderState.IDLE:
        return "Demarrer"
    if state is RecorderState.RECORDING:
        return "Arreter"
    return "Traitement"


async def microphone_audio_source(
    device_id: str | None,
    stop_requested: threading.Event,
    cancel_requested: threading.Event,
) -> AsyncIterator[AudioChunk]:
    config = MicrophoneCaptureConfig(device_id=device_id)
    try:
        with MicrophoneCapture(config) as capture:
            while not stop_requested.is_set() and not cancel_requested.is_set():
                chunk = capture.read(timeout=0.05)
                if chunk is not None:
                    yield chunk
                await asyncio.sleep(0)
    except AudioCaptureError as exc:
        raise RuntimeError(str(exc)) from exc


async def _with_level_signal(
    source: AsyncIterator[AudioChunk | bytes],
    level_signal: Signal,
) -> AsyncIterator[AudioChunk | bytes]:
    async for chunk in source:
        if isinstance(chunk, AudioChunk):
            level_signal.emit(chunk.rms)
        yield chunk
