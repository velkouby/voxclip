from __future__ import annotations

import subprocess

import pytest

from vox_voice_paste.desktop.clipboard import (
    ClipboardError,
    InMemoryClipboardService,
    clipboard_command,
    copy_with_command,
)


def test_in_memory_clipboard_refuses_empty_text() -> None:
    clipboard = InMemoryClipboardService()

    with pytest.raises(ClipboardError):
        clipboard.copy_text("   ")

    assert clipboard.text is None


def test_clipboard_command_prefers_wayland(monkeypatch) -> None:
    def which(name: str) -> str | None:
        return "/usr/bin/wl-copy" if name == "wl-copy" else None

    monkeypatch.setattr("shutil.which", which)

    assert clipboard_command({"WAYLAND_DISPLAY": "wayland-0"}) == ["wl-copy"]


def test_copy_with_command_raises_clipboard_error(monkeypatch) -> None:
    def fail_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["wl-copy"], timeout=3)

    monkeypatch.setattr("subprocess.run", fail_run)

    with pytest.raises(ClipboardError):
        copy_with_command(["wl-copy"], "text")
