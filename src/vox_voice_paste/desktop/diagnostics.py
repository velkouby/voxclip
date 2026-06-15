# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import os
import platform
import shutil
from pathlib import Path

from vox_voice_paste import __version__
from vox_voice_paste.audio import AudioDeviceError, list_input_devices
from vox_voice_paste.config import ConfigError, default_config_path, load_config
from vox_voice_paste.desktop.clipboard import clipboard_command
from vox_voice_paste.desktop.environment import detect_desktop_environment
from vox_voice_paste.error_log import default_error_log_path
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    SONIOX_API_KEY_SECRET,
    KeyringSecretService,
    SecretError,
    SecretService,
)


def build_diagnostic_lines(
    *,
    config_path: Path | None = None,
    secret_service: SecretService | None = None,
) -> list[str]:
    resolved_config_path = config_path or default_config_path()
    secrets = secret_service or KeyringSecretService()

    lines = [
        "VoxClip diagnostics",
        f"version: {__version__}",
        f"python: {platform.python_version()}",
        f"config_path: {resolved_config_path}",
    ]

    error_log_path = default_error_log_path()
    lines.append(f"error_log_path: {error_log_path}")
    if error_log_path.exists():
        try:
            error_log_size = error_log_path.stat().st_size
        except OSError:
            lines.append("error_log_exists: yes")
            lines.append("error_log_size_bytes: unavailable")
        else:
            lines.append("error_log_exists: yes")
            lines.append(f"error_log_size_bytes: {error_log_size}")
    else:
        lines.append("error_log_exists: no")
        lines.append("error_log_size_bytes: 0")

    desktop = detect_desktop_environment()
    lines.extend(
        [
            f"desktop_session: {desktop.session_type}",
            f"desktop_current: {desktop.current_desktop}",
            f"wayland_display: {'yes' if desktop.wayland_display else 'no'}",
            f"x11_display: {'yes' if desktop.x11_display else 'no'}",
        ]
    )

    if resolved_config_path.exists():
        try:
            load_config(resolved_config_path)
        except ConfigError:
            lines.append("config: invalid")
        else:
            lines.append("config: valid")
    else:
        lines.append("config: missing")

    try:
        key_present = secrets.get_secret(OPENAI_API_KEY_SECRET) is not None
    except SecretError:
        lines.append("openai_api_key: unavailable")
    else:
        lines.append(f"openai_api_key: {'present' if key_present else 'missing'}")

    try:
        key_present = secrets.get_secret(SONIOX_API_KEY_SECRET) is not None
    except SecretError:
        lines.append("soniox_api_key: unavailable")
    else:
        lines.append(f"soniox_api_key: {'present' if key_present else 'missing'}")

    try:
        input_devices = list_input_devices()
    except AudioDeviceError:
        lines.append(
            "audio_devices: unavailable "
            "(install libportaudio2 and check microphone access)"
        )
    else:
        lines.append(f"audio_devices: {len(input_devices)} input device(s)")

    command = clipboard_command(os.environ)
    lines.append(f"clipboard: {' '.join(command) if command else 'qt-fallback'}")
    notification_backend = "notify-send" if shutil.which("notify-send") else "unavailable"
    lines.append(f"notifications: {notification_backend}")

    return lines


def format_diagnostic_report(lines: list[str]) -> str:
    return "\n".join(lines)
