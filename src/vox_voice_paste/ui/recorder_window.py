from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vox_voice_paste.transcription import (
    MockTranscriptionService,
    TranscriptBuffer,
    TranscriptionEvent,
    TranscriptionEventType,
    TranscriptionService,
)

from .widgets import create_level_meter


class RecorderState(StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    STOPPING = "stopping"
    TRANSCRIBING_FINAL = "transcribing_final"
    COPYING = "copying"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class RecorderWindow(QDialog):
    def __init__(
        self,
        *,
        transcription_service: TranscriptionService | None = None,
        auto_start: bool = False,
        close_on_success: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = transcription_service or MockTranscriptionService()
        self._close_on_success = close_on_success
        self._buffer = TranscriptBuffer()
        self._state = RecorderState.IDLE
        self._level_value = 0
        self._mock_words: list[str] = []
        self._mock_word_index = 0

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

        if not isinstance(self._service, MockTranscriptionService):
            self._handle_error("Real transcription UI is not implemented yet.")
            return

        self._mock_words = self._service.transcript.split()
        self._mock_word_index = 0
        interval_ms = max(1, round(self._service.delay_seconds * 1000))
        self._mock_timer.start(interval_ms)

    @Slot()
    def stop_recording(self) -> None:
        if self._state is not RecorderState.RECORDING:
            return
        self.set_state(RecorderState.STOPPING)
        QTimer.singleShot(120, self._mark_transcribing_final)

    @Slot()
    def cancel(self) -> None:
        self._mock_timer.stop()
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
            self.set_state(RecorderState.SUCCESS)
            if self._close_on_success:
                QTimer.singleShot(250, self.close)

    @Slot(str)
    def _handle_error(self, message: str) -> None:
        if self._state is RecorderState.CANCELLED:
            return
        self._level_timer.stop()
        self.set_state(RecorderState.ERROR)
        self.status_label.setText(message)

    @Slot()
    def _mark_transcribing_final(self) -> None:
        if self._state is RecorderState.STOPPING:
            self.set_state(RecorderState.TRANSCRIBING_FINAL)

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
