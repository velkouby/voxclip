from __future__ import annotations

import pytest

from vox_voice_paste.desktop import SessionAlreadyRunningError, SessionLock


def test_session_lock_prevents_second_acquire(tmp_path) -> None:
    lock_path = tmp_path / "session.lock"

    with SessionLock(lock_path):
        with pytest.raises(SessionAlreadyRunningError):
            SessionLock(lock_path).acquire()


def test_session_lock_releases_after_context(tmp_path) -> None:
    lock_path = tmp_path / "session.lock"

    with SessionLock(lock_path):
        pass

    with SessionLock(lock_path):
        pass
