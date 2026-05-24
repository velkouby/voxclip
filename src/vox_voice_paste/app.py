from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog

from vox_voice_paste.audio import AudioDeviceError, list_input_devices
from vox_voice_paste.config import load_config
from vox_voice_paste.desktop import (
    ClipboardService,
    SessionAlreadyRunningError,
    SessionLock,
    ShortcutInstallError,
    install_shortcut_autostart_entry,
    set_ubuntu_shortcut,
)
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    KeyringSecretService,
    OpenAIHTTPKeyValidator,
    OpenAIKeyValidator,
    SecretError,
    SecretService,
)
from vox_voice_paste.transcription import (
    MockTranscriptionService,
    OpenAIRealtimeTranscriptionService,
    TranscriptionConfig,
)
from vox_voice_paste.ui.api_key_dialog import OpenAIKeyDialog
from vox_voice_paste.ui.onboarding_window import OnboardingWindow
from vox_voice_paste.ui.recorder_window import RecorderWindow
from vox_voice_paste.ui.settings_window import SettingsWindow


def run_record_and_copy(
    *,
    mock: bool = False,
    secret_service: SecretService | None = None,
    key_validator: OpenAIKeyValidator | None = None,
) -> int:
    try:
        with SessionLock():
            app = QApplication.instance() or QApplication(sys.argv[:1])
            config = load_config()
            devices = _input_devices()
            if mock:
                service = MockTranscriptionService(delay_seconds=0.05)
            else:
                secrets = secret_service or KeyringSecretService()
                api_key = _api_key_or_prompt(
                    secret_service=secrets,
                    key_validator=key_validator,
                )
                if api_key is None:
                    return 1
                service = _openai_transcription_service(config, api_key=api_key)
            window = RecorderWindow(
                transcription_service=service,
                input_devices=devices,
                auto_start=True,
                close_on_success=True,
                force_process_exit_on_success=True,
            )
            window.show()
            return int(app.exec())
    except SessionAlreadyRunningError as exc:
        print(f"vox-voice-paste: {exc}", file=sys.stderr)
        return 1


def _api_key_or_prompt(
    *,
    secret_service: SecretService,
    key_validator: OpenAIKeyValidator | None = None,
) -> str | None:
    try:
        api_key = secret_service.get_secret(OPENAI_API_KEY_SECRET)
    except SecretError:
        api_key = None
    if api_key:
        return api_key

    dialog = OpenAIKeyDialog(
        secret_service=secret_service,
        key_validator=key_validator or OpenAIHTTPKeyValidator(),
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    try:
        return secret_service.get_secret(OPENAI_API_KEY_SECRET)
    except SecretError:
        return None


def _openai_transcription_service(config, *, api_key: str) -> OpenAIRealtimeTranscriptionService:
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
    key_validator: OpenAIKeyValidator | None = None,
    clipboard_service: ClipboardService | None = None,
) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    config = load_config(config_path)
    _ensure_startup_shortcut(config=config)
    if not config.onboarding_completed:
        window = OnboardingWindow(
            config_path=config_path,
            secret_service=secret_service or KeyringSecretService(),
            key_validator=key_validator,
            clipboard_service=clipboard_service,
        )
    else:
        window = SettingsWindow(
            config_path=config_path,
            secret_service=secret_service,
            key_validator=key_validator,
        )
    window.show()
    return int(app.exec())


def run_settings(
    *,
    config_path: Path | None = None,
    secret_service: SecretService | None = None,
    key_validator: OpenAIKeyValidator | None = None,
) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    config = load_config(config_path)
    _ensure_startup_shortcut(config=config)
    window = SettingsWindow(
        config_path=config_path,
        startup_shortcut=config.ubuntu_shortcut,
        secret_service=secret_service,
        key_validator=key_validator,
    )
    window.show()
    return int(app.exec())


def _ensure_startup_shortcut(*, config) -> None:
    try:
        set_ubuntu_shortcut(shortcut=config.ubuntu_shortcut)
    except ShortcutInstallError:
        return

    try:
        install_shortcut_autostart_entry()
    except ShortcutInstallError:
        return
