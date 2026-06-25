from __future__ import annotations

from vox_voice_paste.desktop.environment import DesktopEnvironment
from vox_voice_paste.desktop.shortcuts import (
    DEFAULT_SHORTCUT_COMMAND,
    DEFAULT_TRANSLATION_SHORTCUT_COMMAND,
    set_ubuntu_shortcut,
    set_ubuntu_shortcuts,
)


def test_set_ubuntu_shortcut_writes_binding_as_string(monkeypatch) -> None:
    written_values: list[tuple[str, str, str]] = []

    def fake_detect_desktop_environment() -> DesktopEnvironment:
        return DesktopEnvironment(
            session_type="wayland",
            current_desktop="ubuntu:GNOME",
            wayland_display=True,
            x11_display=False,
        )

    def fake_run_gsettings(args: list[str]) -> str:
        command, schema, key, *value = args
        if command == "get" and key == "custom-keybindings":
            return "@as []"
        if command == "set":
            written_values.append((schema, key, value[0]))
            return ""
        raise AssertionError(f"unexpected gsettings call: {args}")

    monkeypatch.setattr(
        "vox_voice_paste.desktop.shortcuts.detect_desktop_environment",
        fake_detect_desktop_environment,
    )
    monkeypatch.setattr("vox_voice_paste.desktop.shortcuts._run_gsettings", fake_run_gsettings)

    set_ubuntu_shortcut(shortcut="Ctrl+Alt+N")

    binding_writes = [value for _, key, value in written_values if key == "binding"]
    assert binding_writes == ["'<Primary><Alt>n'"]


def test_set_ubuntu_shortcuts_writes_transcription_and_translation_commands(
    monkeypatch,
) -> None:
    written_values: list[tuple[str, str, str]] = []

    def fake_detect_desktop_environment() -> DesktopEnvironment:
        return DesktopEnvironment(
            session_type="wayland",
            current_desktop="ubuntu:GNOME",
            wayland_display=True,
            x11_display=False,
        )

    def fake_run_gsettings(args: list[str]) -> str:
        command, schema, key, *value = args
        if command == "get" and key == "custom-keybindings":
            return "@as []"
        if command == "set":
            written_values.append((schema, key, value[0]))
            return ""
        raise AssertionError(f"unexpected gsettings call: {args}")

    monkeypatch.setattr(
        "vox_voice_paste.desktop.shortcuts.detect_desktop_environment",
        fake_detect_desktop_environment,
    )
    monkeypatch.setattr("vox_voice_paste.desktop.shortcuts._run_gsettings", fake_run_gsettings)

    set_ubuntu_shortcuts(
        transcription_shortcut="Ctrl+Alt+N",
        translation_shortcut="Ctrl+Alt+M",
    )

    command_writes = [value for _, key, value in written_values if key == "command"]
    assert f"'{DEFAULT_SHORTCUT_COMMAND}'" in command_writes
    assert f"'{DEFAULT_TRANSLATION_SHORTCUT_COMMAND}'" in command_writes
