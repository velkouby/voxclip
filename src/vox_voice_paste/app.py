# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import sys
from pathlib import Path
from typing import Literal

from PySide6.QtWidgets import QApplication, QDialog

from vox_voice_paste.config import (
    DEFAULT_TRANSLATION_TARGET_LANGUAGE,
    OPENAI_TRANSLATION_WEBSOCKET_BASE_URL,
    REALTIME_TRANSLATION_MODEL,
    SONIOX_WEBSOCKET_BASE_URL,
    TranscriptionProvider,
    load_config,
    normalize_language_code,
    normalize_soniox_transcription_model,
    normalize_transcription_model,
)
from vox_voice_paste.desktop import (
    ClipboardService,
    SessionAlreadyRunningError,
    SessionLock,
    ShortcutInstallError,
    install_shortcut_autostart_entry,
    set_ubuntu_shortcuts,
)
from vox_voice_paste.error_log import record_error
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    SONIOX_API_KEY_SECRET,
    KeyringSecretService,
    OpenAIHTTPKeyValidator,
    OpenAIKeyValidator,
    SecretError,
    SecretService,
    SonioxHTTPKeyValidator,
)
from vox_voice_paste.transcription import (
    OPENAI_SAMPLE_RATE,
    SONIOX_SAMPLE_RATE,
    MockTranscriptionService,
    OpenAIRealtimeTranscriptionService,
    OpenAIRealtimeTranslationService,
    SonioxRealtimeTranscriptionService,
    TranscriptionConfig,
)
from vox_voice_paste.ui.api_key_dialog import OpenAIKeyDialog
from vox_voice_paste.ui.onboarding_window import OnboardingWindow
from vox_voice_paste.ui.recorder_window import RecorderWindow
from vox_voice_paste.ui.settings_window import SettingsWindow

RecordingMode = Literal["transcription", "translation"]


def run_record_and_copy(
    *,
    mock: bool = False,
    secret_service: SecretService | None = None,
    key_validator: OpenAIKeyValidator | None = None,
) -> int:
    return _run_recording(
        mode="transcription",
        mock=mock,
        secret_service=secret_service,
        key_validator=key_validator,
    )


def run_record_and_translate(
    *,
    mock: bool = False,
    secret_service: SecretService | None = None,
    key_validator: OpenAIKeyValidator | None = None,
) -> int:
    return _run_recording(
        mode="translation",
        mock=mock,
        secret_service=secret_service,
        key_validator=key_validator,
    )


def _run_recording(
    *,
    mode: RecordingMode,
    mock: bool = False,
    secret_service: SecretService | None = None,
    key_validator: OpenAIKeyValidator | None = None,
) -> int:
    command_mode = _command_mode(mode)
    try:
        with SessionLock():
            app = QApplication.instance() or QApplication(sys.argv[:1])
            config = load_config()
            audio_sample_rate = OPENAI_SAMPLE_RATE
            if mock:
                service = MockTranscriptionService(
                    "This is a test translation."
                    if mode == "translation"
                    else "This is a test transcription.",
                    delay_seconds=0.05,
                )
            else:
                secrets = secret_service or KeyringSecretService()
                api_key = _api_key_or_prompt(
                    secret_service=secrets,
                    provider=config.transcription_provider,
                    key_validator=key_validator,
                )
                if api_key is None:
                    return 1
                service = _transcription_service(config, api_key=api_key, mode=mode)
                audio_sample_rate = _effective_sample_rate(config)
            window = RecorderWindow(
                transcription_service=service,
                auto_start=True,
                close_on_success=True,
                force_process_exit_on_success=True,
                audio_sample_rate=audio_sample_rate,
                error_context=_recording_error_context(config, mock=mock, mode=mode),
            )
            window.show()
            return int(app.exec())
    except SessionAlreadyRunningError as exc:
        record_error(
            event="session_already_running",
            component=f"app.{command_mode}",
            message=str(exc),
            context={"mode": command_mode, "mock": mock},
        )
        print(f"voxclip: {exc}", file=sys.stderr)
        return 1


def _api_key_or_prompt(
    *,
    secret_service: SecretService,
    provider: TranscriptionProvider = "openai",
    key_validator: OpenAIKeyValidator | None = None,
) -> str | None:
    secret_name = _api_key_secret_name(provider)
    try:
        api_key = secret_service.get_secret(secret_name)
    except SecretError:
        api_key = None
    if api_key:
        return api_key

    dialog = OpenAIKeyDialog(
        secret_service=secret_service,
        key_validator=key_validator or _key_validator(provider),
        provider_name=_provider_label(provider),
        secret_name=secret_name,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    try:
        return secret_service.get_secret(secret_name)
    except SecretError:
        return None


def _transcription_service(
    config,
    *,
    api_key: str,
    mode: RecordingMode = "transcription",
) -> (
    OpenAIRealtimeTranscriptionService
    | OpenAIRealtimeTranslationService
    | SonioxRealtimeTranscriptionService
):
    if config.transcription_provider == "soniox":
        return _soniox_transcription_service(
            config,
            api_key=api_key,
            translate=mode == "translation",
        )
    if mode == "translation":
        return _openai_translation_service(config, api_key=api_key)
    return _openai_transcription_service(config, api_key=api_key)


def _openai_transcription_service(config, *, api_key: str) -> OpenAIRealtimeTranscriptionService:
    return OpenAIRealtimeTranscriptionService(
        TranscriptionConfig(
            api_key=api_key,
            model=normalize_transcription_model(config.transcription_model),
            language=config.transcription_language,
            delay=config.transcription_delay,
            sample_rate=OPENAI_SAMPLE_RATE,
        )
    )


def _openai_translation_service(config, *, api_key: str) -> OpenAIRealtimeTranslationService:
    return OpenAIRealtimeTranslationService(
        TranscriptionConfig(
            api_key=api_key,
            model=REALTIME_TRANSLATION_MODEL,
            sample_rate=OPENAI_SAMPLE_RATE,
            websocket_base_url=OPENAI_TRANSLATION_WEBSOCKET_BASE_URL,
            translation_target_language=_translation_target_language(config),
        )
    )


def _soniox_transcription_service(
    config,
    *,
    api_key: str,
    translate: bool = False,
) -> SonioxRealtimeTranscriptionService:
    model = _effective_soniox_model(config.transcription_model)

    return SonioxRealtimeTranscriptionService(
        TranscriptionConfig(
            api_key=api_key,
            model=model,
            language=config.transcription_language,
            delay=config.transcription_delay,
            sample_rate=SONIOX_SAMPLE_RATE,
            websocket_base_url=SONIOX_WEBSOCKET_BASE_URL,
            translation_target_language=(
                _translation_target_language(config) if translate else None
            ),
        )
    )


def _api_key_secret_name(provider: TranscriptionProvider) -> str:
    return SONIOX_API_KEY_SECRET if provider == "soniox" else OPENAI_API_KEY_SECRET


def _key_validator(provider: TranscriptionProvider) -> OpenAIKeyValidator:
    return SonioxHTTPKeyValidator() if provider == "soniox" else OpenAIHTTPKeyValidator()


def _provider_label(provider: TranscriptionProvider) -> str:
    return "Soniox" if provider == "soniox" else "OpenAI"


def _effective_transcription_model(config, *, mode: RecordingMode = "transcription") -> str:
    if config.transcription_provider == "openai" and mode == "translation":
        return REALTIME_TRANSLATION_MODEL
    if config.transcription_provider == "soniox":
        return _effective_soniox_model(config.transcription_model)
    return normalize_transcription_model(config.transcription_model)


def _effective_sample_rate(config) -> int:
    return SONIOX_SAMPLE_RATE if config.transcription_provider == "soniox" else OPENAI_SAMPLE_RATE


def _effective_soniox_model(model: str) -> str:
    return normalize_soniox_transcription_model(model)


def _translation_target_language(config) -> str:
    return (
        normalize_language_code(config.translation_target_language)
        or DEFAULT_TRANSLATION_TARGET_LANGUAGE
    )


def _command_mode(mode: RecordingMode) -> str:
    return "record-and-translate" if mode == "translation" else "record-and-copy"


def _recording_error_context(
    config,
    *,
    mock: bool,
    mode: RecordingMode,
) -> dict[str, object]:
    return {
        "mode": _command_mode(mode),
        "mock": mock,
        "settings": {
            "transcription_provider": "mock" if mock else config.transcription_provider,
            "transcription_model": (
                "mock" if mock else _effective_transcription_model(config, mode=mode)
            ),
            "transcription_language": config.transcription_language,
            "transcription_delay": config.transcription_delay,
            "translation_target_language": (
                None if mode == "transcription" else _translation_target_language(config)
            ),
            "sample_rate": None if mock else _effective_sample_rate(config),
            "configured_input_device_id": config.default_input_device_id,
            "ubuntu_shortcut": config.ubuntu_shortcut,
            "translation_ubuntu_shortcut": config.translation_ubuntu_shortcut,
        },
    }


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
        startup_translation_shortcut=config.translation_ubuntu_shortcut,
        secret_service=secret_service,
        key_validator=key_validator,
    )
    window.show()
    return int(app.exec())


def _ensure_startup_shortcut(*, config) -> None:
    try:
        set_ubuntu_shortcuts(
            transcription_shortcut=config.ubuntu_shortcut,
            translation_shortcut=config.translation_ubuntu_shortcut,
        )
    except ShortcutInstallError:
        return

    try:
        install_shortcut_autostart_entry()
    except ShortcutInstallError:
        return
