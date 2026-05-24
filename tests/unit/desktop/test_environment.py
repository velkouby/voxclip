from __future__ import annotations

from vox_voice_paste.desktop.environment import detect_desktop_environment


def test_detect_desktop_environment_from_env_mapping() -> None:
    env = {
        "XDG_SESSION_TYPE": "wayland",
        "XDG_CURRENT_DESKTOP": "GNOME",
        "WAYLAND_DISPLAY": "wayland-0",
    }

    desktop = detect_desktop_environment(env)

    assert desktop.session_type == "wayland"
    assert desktop.current_desktop == "GNOME"
    assert desktop.wayland_display is True
    assert desktop.x11_display is False
