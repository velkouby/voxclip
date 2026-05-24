from __future__ import annotations

import platform
from pathlib import Path

from vox_voice_paste import __version__
from vox_voice_paste.config import ConfigError, default_config_path, load_config
from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
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
        "Vox Voice Paste diagnostics",
        f"version: {__version__}",
        f"python: {platform.python_version()}",
        f"config_path: {resolved_config_path}",
    ]

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

    return lines


def format_diagnostic_report(lines: list[str]) -> str:
    return "\n".join(lines)
