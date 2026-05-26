# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import os
import shutil
import subprocess
from collections.abc import Mapping
from typing import Protocol


class ClipboardError(RuntimeError):
    """Raised when text cannot be copied safely."""


class ClipboardService(Protocol):
    def copy_text(self, text: str) -> None: ...


class SystemClipboardService:
    def copy_text(self, text: str) -> None:
        normalized = text.strip()
        if not normalized:
            raise ClipboardError("Refusing to copy empty text.")

        command = clipboard_command(os.environ)
        if command is not None:
            copy_with_command(command, normalized)
            return

        copy_with_qt(normalized)


class InMemoryClipboardService:
    def __init__(self) -> None:
        self.text: str | None = None

    def copy_text(self, text: str) -> None:
        normalized = text.strip()
        if not normalized:
            raise ClipboardError("Refusing to copy empty text.")
        self.text = normalized


def clipboard_command(environ: Mapping[str, str]) -> list[str] | None:
    if environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        return ["wl-copy"]
    if environ.get("DISPLAY"):
        if shutil.which("xclip"):
            return ["xclip", "-selection", "clipboard"]
        if shutil.which("xsel"):
            return ["xsel", "--clipboard", "--input"]
    return None


def copy_with_command(command: list[str], text: str) -> None:
    # `wl-copy` and `xclip` double-fork a daemon that keeps the selection
    # alive after the foreground process exits. The daemon inherits stdout
    # and stderr; piping them keeps the read end open forever and makes
    # `subprocess.run` block until the timeout fires even though the
    # clipboard was set correctly. Redirect to DEVNULL so we wait only on
    # the foreground process.
    try:
        subprocess.run(
            command,
            input=text,
            text=True,
            check=True,
            timeout=3,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ClipboardError("Unable to copy text to the system clipboard.") from exc


def copy_with_qt(text: str) -> None:
    try:
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QApplication.processEvents()
    except Exception as exc:
        raise ClipboardError("Unable to copy text to the Qt clipboard.") from exc
