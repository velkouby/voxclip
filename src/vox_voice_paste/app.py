from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from vox_voice_paste.audio import AudioDeviceError, list_input_devices
from vox_voice_paste.config import load_config
from vox_voice_paste.desktop import ClipboardService, SessionAlreadyRunningError, SessionLock
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    KeyringSecretService,
    SecretError,
    SecretService,
)
from vox_voice_paste.transcription import (
    MockTranscriptionService,
    OpenAIRealtimeTranscriptionService,
    TranscriptionConfig,
)
from vox_voice_paste.ui.onboarding_window import OnboardingWindow
from vox_voice_paste.ui.recorder_window import RecorderWindow
from vox_voice_paste.ui.settings_window import SettingsWindow


def run_record_and_copy(*, mock: bool = False) -> int:
    try:
        with SessionLock():
            app = QApplication.instance() or QApplication(sys.argv[:1])
            config = load_config()
            devices = _input_devices()
            service = (
                MockTranscriptionService(delay_seconds=0.05)
                if mock
                else _openai_transcription_service(config)
            )
            window = RecorderWindow(
                transcription_service=service,
                input_devices=devices,
                auto_start=True,
                close_on_success=True,
            )
            window.show()
            return int(app.exec())
    except SessionAlreadyRunningError as exc:
        print(f"vox-voice-paste: {exc}", file=sys.stderr)
        return 1


def _openai_transcription_service(config) -> OpenAIRealtimeTranscriptionService:
    secrets = KeyringSecretService()
    try:
        api_key = secrets.get_secret(OPENAI_API_KEY_SECRET)
    except SecretError:
        api_key = None

    return OpenAIRealtimeTranscriptionService(
        TranscriptionConfig(
            api_key=api_key,
            model=config.transcription_model,
            language=config.transcription_language,
            delay=config.transcription_delay,
        )
    )


def _input_devices():
    try:
        return list_input_devices()
    except AudioDeviceError:
        return []


def run_main_app(
    *,
    config_path: Path | None = None,
    secret_service: SecretService | None = None,
    clipboard_service: ClipboardService | None = None,
) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    config = load_config(config_path)
    if not config.onboarding_completed:
        window = OnboardingWindow(
            config_path=config_path,
            secret_service=secret_service or KeyringSecretService(),
            clipboard_service=clipboard_service,
        )
    else:
        window = SettingsWindow(config_path=config_path)
    window.show()
    return int(app.exec())


def run_settings(*, config_path: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = SettingsWindow(config_path=config_path)
    window.show()
    return int(app.exec())
