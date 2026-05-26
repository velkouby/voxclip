# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import fcntl
import os
import tempfile
from pathlib import Path

from vox_voice_paste.config import APP_ID


class SessionAlreadyRunningError(RuntimeError):
    """Raised when another dictation session already holds the process lock."""


class SessionLock:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_session_lock_path()
        self._file = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self._path.open("w", encoding="utf-8")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_file.close()
            raise SessionAlreadyRunningError(
                "Another dictation session is already running."
            ) from exc
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        self._file = lock_file

    def release(self) -> None:
        if self._file is None:
            return
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None

    def __enter__(self) -> SessionLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()


def default_session_lock_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    base_dir = Path(runtime_dir) if runtime_dir else Path(tempfile.gettempdir())
    return base_dir / f"{APP_ID}.lock"
