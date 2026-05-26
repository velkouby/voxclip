# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

from collections.abc import Mapping
from dataclasses import dataclass
from os import environ


@dataclass(frozen=True)
class DesktopEnvironment:
    session_type: str
    current_desktop: str
    wayland_display: bool
    x11_display: bool


def detect_desktop_environment(env: Mapping[str, str] = environ) -> DesktopEnvironment:
    return DesktopEnvironment(
        session_type=env.get("XDG_SESSION_TYPE", "unknown") or "unknown",
        current_desktop=env.get("XDG_CURRENT_DESKTOP", "unknown") or "unknown",
        wayland_display=bool(env.get("WAYLAND_DISPLAY")),
        x11_display=bool(env.get("DISPLAY")),
    )
