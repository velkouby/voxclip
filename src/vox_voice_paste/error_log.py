# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platformdirs import user_state_path

from vox_voice_paste import __version__
from vox_voice_paste.config import APP_ID

ERROR_LOG_FILENAME = "errors.log"
ERROR_LOG_MAX_BYTES = 1_048_576
ERROR_LOG_BACKUP_COUNT = 5
REDACTED = "<redacted>"

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "secret",
    "token",
    "password",
    "base64",
)
_SENSITIVE_EXACT_KEYS = {
    "audio",
    "audio_chunk",
    "audio_chunks",
    "raw_audio",
    "pcm",
    "transcript",
    "transcript_text",
    "final_text",
    "partial_text",
    "delta",
    "text",
}
_SENSITIVE_SUFFIXES = (
    "_audio",
    "_pcm",
    "_transcript",
    "_transcript_text",
    "_final_text",
    "_partial_text",
)


def default_error_log_path() -> Path:
    return user_state_path(APP_ID, appauthor=False) / ERROR_LOG_FILENAME


def record_error(
    *,
    event: str,
    component: str,
    message: str,
    context: Mapping[str, Any] | None = None,
    log_path: Path | None = None,
) -> Path | None:
    """Append one sanitized error entry without interrupting the app on failure."""
    path = log_path or default_error_log_path()
    entry: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "level": "ERROR",
        "event": event,
        "component": component,
        "message": _sanitize_string(message),
        "version": __version__,
    }
    if context:
        entry["context"] = sanitize_for_error_log(context)

    try:
        _append_json_line(path, entry)
    except OSError:
        return None
    return path


def sanitize_for_error_log(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_sensitive_key(str(key)) else sanitize_for_error_log(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [sanitize_for_error_log(item) for item in value]
    if isinstance(value, bytes | bytearray | memoryview):
        return REDACTED
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return _sanitize_string(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    return _sanitize_string(str(value))


def read_error_log_tail(*, path: Path | None = None, line_count: int = 50) -> str:
    resolved_path = path or default_error_log_path()
    if not resolved_path.exists():
        return ""
    lines = resolved_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-line_count:])


def _append_json_line(path: Path, entry: Mapping[str, Any]) -> None:
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
    encoded_size = len(line.encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        path.parent.chmod(0o700)
    if _needs_rotation(path, encoded_size):
        _rotate_error_logs(path)
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(line)


def _needs_rotation(path: Path, next_write_size: int) -> bool:
    try:
        return path.exists() and path.stat().st_size + next_write_size > ERROR_LOG_MAX_BYTES
    except OSError:
        return False


def _rotate_error_logs(path: Path) -> None:
    if ERROR_LOG_BACKUP_COUNT <= 0:
        path.unlink(missing_ok=True)
        return

    for index in range(ERROR_LOG_BACKUP_COUNT - 1, 0, -1):
        source = _backup_path(path, index)
        if not source.exists():
            continue
        source.replace(_backup_path(path, index + 1))
    if path.exists():
        path.replace(_backup_path(path, 1))


def _backup_path(path: Path, index: int) -> Path:
    return path.with_name(f"{path.name}.{index}")


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return (
        normalized in _SENSITIVE_EXACT_KEYS
        or normalized.endswith(_SENSITIVE_SUFFIXES)
        or any(part in normalized for part in _SENSITIVE_KEY_PARTS)
    )


def _sanitize_string(value: str) -> str:
    sanitized = re.sub(r"Bearer\s+\S+", f"Bearer {REDACTED}", value)
    sanitized = re.sub(r"\bsk-[A-Za-z0-9_-]+", REDACTED, sanitized)
    if len(sanitized) > 1_000:
        return f"{sanitized[:1_000]}..."
    return sanitized
