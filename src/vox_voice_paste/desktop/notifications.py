# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol


class NotificationService(Protocol):
    def notify(self, title: str, body: str) -> None: ...


class DesktopNotificationService:
    def notify(self, title: str, body: str) -> None:
        if not shutil.which("notify-send"):
            return
        subprocess.run(
            ["notify-send", title, body],
            check=False,
            timeout=3,
            capture_output=True,
            text=True,
        )


@dataclass(frozen=True)
class Notification:
    title: str
    body: str


class InMemoryNotificationService:
    def __init__(self) -> None:
        self.notifications: list[Notification] = []

    def notify(self, title: str, body: str) -> None:
        self.notifications.append(Notification(title=title, body=body))
