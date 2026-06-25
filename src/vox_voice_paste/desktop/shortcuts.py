# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import ast
import subprocess
from collections.abc import Sequence
from pathlib import Path

from .environment import detect_desktop_environment

GSETTINGS_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_KEY_SCHEMA_PREFIX = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
CUSTOM_KEY_BINDINGS_KEY = "custom-keybindings"
CUSTOM_KEY_BASE_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
SHORTCUT_LABEL = "VoxClip"
TRANSLATION_SHORTCUT_LABEL = "VoxClip Translation"
LEGACY_SHORTCUT_LABELS = {"Vox Voice Paste"}
MANAGED_SHORTCUT_PATH = f"{CUSTOM_KEY_BASE_PATH}voxclip/"
TRANSLATION_MANAGED_SHORTCUT_PATH = f"{CUSTOM_KEY_BASE_PATH}voxclip-translation/"
LEGACY_MANAGED_SHORTCUT_PATHS = {f"{CUSTOM_KEY_BASE_PATH}vox-voice-paste/"}
SHORTCUT_EXECUTABLE = "/usr/bin/voxclip"
DEFAULT_SHORTCUT_COMMAND = f"{SHORTCUT_EXECUTABLE} --record-and-copy"
DEFAULT_TRANSLATION_SHORTCUT_COMMAND = f"{SHORTCUT_EXECUTABLE} --record-and-translate"
LEGACY_SHORTCUT_COMMANDS = {"/usr/bin/vox-voice-paste --record-and-copy"}
AUTOSTART_SHORTCUT_NAME = "voxclip-shortcut.desktop"
LEGACY_AUTOSTART_SHORTCUT_NAMES = {"vox-voice-paste-shortcut.desktop"}
AUTOSTART_SHORTCUT_FILE = (
    Path.home() / ".config" / "autostart" / AUTOSTART_SHORTCUT_NAME
)
AUTOSTART_SHORTCUT_COMMAND = f"{SHORTCUT_EXECUTABLE} --ensure-ubuntu-shortcut"


class ShortcutInstallError(RuntimeError):
    """Raised when configuring the Ubuntu/GNOME shortcut fails."""


def set_ubuntu_shortcut(
    *,
    shortcut: str,
    command: str = DEFAULT_SHORTCUT_COMMAND,
    label: str = SHORTCUT_LABEL,
    managed_path: str = MANAGED_SHORTCUT_PATH,
    remove_stale: bool = True,
) -> str:
    if not shortcut:
        raise ShortcutInstallError("Shortcut must not be empty.")

    _ensure_gsettings_available()
    normalized = _normalize_shortcut(shortcut)
    paths = _load_custom_binding_paths()
    shortcut_commands = {command, *LEGACY_SHORTCUT_COMMANDS}
    shortcut_labels = {label, *LEGACY_SHORTCUT_LABELS}

    target_path = managed_path
    if target_path not in paths:
        paths.append(target_path)

    stale_paths = [
        path
        for path in paths
        if path != target_path
        and (
            path in LEGACY_MANAGED_SHORTCUT_PATHS
            or _read_schema_value(f"{CUSTOM_KEY_SCHEMA_PREFIX}:{path}", "command")
            in shortcut_commands
            or _read_schema_value(f"{CUSTOM_KEY_SCHEMA_PREFIX}:{path}", "name")
            in shortcut_labels
            or _read_schema_value(f"{CUSTOM_KEY_SCHEMA_PREFIX}:{path}", "binding")
            == normalized
            or _is_empty_binding(f"{CUSTOM_KEY_SCHEMA_PREFIX}:{path}")
        )
    ]

    for path in stale_paths:
        _clear_custom_binding(f"{CUSTOM_KEY_SCHEMA_PREFIX}:{path}")

    if remove_stale:
        paths = [path for path in paths if path not in stale_paths]

    paths = [path for path in paths if path != target_path]
    paths.insert(0, target_path)
    paths = _dedupe_paths(paths)
    _set_gsettings_value(
        GSETTINGS_SCHEMA,
        CUSTOM_KEY_BINDINGS_KEY,
        _format_variant_string_list(paths),
    )

    _set_custom_binding(
        f"{CUSTOM_KEY_SCHEMA_PREFIX}:{target_path}",
        command=command,
        label=label,
        shortcut=normalized,
    )
    return target_path


def set_ubuntu_shortcuts(
    *,
    transcription_shortcut: str,
    translation_shortcut: str,
) -> list[str]:
    return [
        set_ubuntu_shortcut(
            shortcut=transcription_shortcut,
            command=DEFAULT_SHORTCUT_COMMAND,
            label=SHORTCUT_LABEL,
            managed_path=MANAGED_SHORTCUT_PATH,
        ),
        set_ubuntu_shortcut(
            shortcut=translation_shortcut,
            command=DEFAULT_TRANSLATION_SHORTCUT_COMMAND,
            label=TRANSLATION_SHORTCUT_LABEL,
            managed_path=TRANSLATION_MANAGED_SHORTCUT_PATH,
        ),
    ]


def install_shortcut_autostart_entry() -> Path | None:
    """Create a user autostart entry so shortcut sync runs at each GNOME login."""
    if not _is_gnome_desktop():
        return None

    desktop_payload = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=VoxClip - Shortcut sync\n"
        "Comment=Re-apply VoxClip shortcut on login\n"
        f"Exec={AUTOSTART_SHORTCUT_COMMAND}\n"
        "OnlyShowIn=GNOME;\n"
        "NoDisplay=true\n"
        "Terminal=false\n"
        "StartupNotify=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    try:
        AUTOSTART_SHORTCUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART_SHORTCUT_FILE.write_text(desktop_payload, encoding="utf-8")
    except OSError as exc:
        raise ShortcutInstallError(
            f"Failed to create GNOME shortcut autostart entry: {exc}"
        ) from exc
    return AUTOSTART_SHORTCUT_FILE


def remove_shortcut_autostart_entry() -> None:
    """Remove user autostart file created for shortcut relinking."""
    try:
        AUTOSTART_SHORTCUT_FILE.unlink(missing_ok=True)
        for legacy_name in LEGACY_AUTOSTART_SHORTCUT_NAMES:
            (AUTOSTART_SHORTCUT_FILE.parent / legacy_name).unlink(missing_ok=True)
    except OSError as exc:
        raise ShortcutInstallError(
            f"Failed to remove GNOME shortcut autostart entry: {exc}"
        ) from exc


def remove_ubuntu_shortcut(
    *,
    command: str = DEFAULT_SHORTCUT_COMMAND,
    managed_path: str = MANAGED_SHORTCUT_PATH,
    label: str = SHORTCUT_LABEL,
    legacy_commands: set[str] | None = None,
    legacy_labels: set[str] | None = None,
    legacy_paths: set[str] | None = None,
) -> list[str]:
    """Remove VoxClip bindings from custom-keybindings and keep list consistent."""
    if not _is_gnome_desktop():
        return []

    paths = _load_custom_binding_paths()
    shortcut_commands = {
        command,
        *(LEGACY_SHORTCUT_COMMANDS if legacy_commands is None else legacy_commands),
    }
    shortcut_labels = {
        label,
        *(LEGACY_SHORTCUT_LABELS if legacy_labels is None else legacy_labels),
    }
    shortcut_paths = {
        managed_path,
        *(LEGACY_MANAGED_SHORTCUT_PATHS if legacy_paths is None else legacy_paths),
    }

    target_paths = [
        path
        for path in paths
        if path in shortcut_paths
        or _read_schema_value(f"{CUSTOM_KEY_SCHEMA_PREFIX}:{path}", "command")
        in shortcut_commands
        or _read_schema_value(f"{CUSTOM_KEY_SCHEMA_PREFIX}:{path}", "name")
        in shortcut_labels
    ]

    for path in target_paths:
        _clear_custom_binding(f"{CUSTOM_KEY_SCHEMA_PREFIX}:{path}")

    remaining_paths = [path for path in paths if path not in target_paths]
    if remaining_paths != paths:
        _set_gsettings_value(
            GSETTINGS_SCHEMA,
            CUSTOM_KEY_BINDINGS_KEY,
            _format_variant_string_list(_dedupe_paths(remaining_paths)),
        )

    return _dedupe_paths(target_paths)


def remove_ubuntu_shortcuts() -> list[str]:
    removed_paths = remove_ubuntu_shortcut()
    removed_paths.extend(
        remove_ubuntu_shortcut(
            command=DEFAULT_TRANSLATION_SHORTCUT_COMMAND,
            managed_path=TRANSLATION_MANAGED_SHORTCUT_PATH,
            label=TRANSLATION_SHORTCUT_LABEL,
            legacy_commands=set(),
            legacy_labels=set(),
            legacy_paths=set(),
        )
    )
    return _dedupe_paths(removed_paths)


def _ensure_gsettings_available() -> None:
    if not _is_gnome_desktop():
        raise ShortcutInstallError(
            "Ubuntu shortcut installation is supported on GNOME desktop environments only."
        )


def _is_gnome_desktop() -> bool:
    return "gnome" in detect_desktop_environment().current_desktop.lower()


def _first_available_custom_path(existing_paths: list[str]) -> str:
    for index in range(1_000):
        candidate = f"{CUSTOM_KEY_BASE_PATH}custom{index}/"
        if candidate not in existing_paths:
            return candidate

    raise ShortcutInstallError("No available GNOME custom shortcut slot found.")


def _set_custom_binding(schema: str, *, command: str, label: str, shortcut: str) -> None:
    _set_gsettings_value(schema, "name", _format_variant_string(label))
    _set_gsettings_value(schema, "command", _format_variant_string(command))
    _set_gsettings_value(schema, "binding", _format_variant_string(shortcut))


def _clear_custom_binding(schema: str) -> None:
    _set_gsettings_value(schema, "name", _format_variant_string(""))
    _set_gsettings_value(schema, "command", _format_variant_string(""))
    _set_gsettings_value(schema, "binding", _format_variant_string(""))


def _normalize_shortcut(shortcut: str) -> str:
    compact = shortcut.strip()
    if compact.startswith("<") and compact.endswith(">"):
        return compact

    tokens = [part.strip() for part in compact.split("+") if part.strip()]
    if len(tokens) < 2:
        raise ShortcutInstallError("Shortcut must contain at least one modifier and one key.")

    modifiers = tokens[:-1]
    key = tokens[-1].strip()
    if not key:
        raise ShortcutInstallError("Shortcut key is empty.")

    prefix_parts: list[str] = []
    for modifier in modifiers:
        mapped = {
            "ctrl": "<Primary>",
            "control": "<Primary>",
            "alt": "<Alt>",
            "shift": "<Shift>",
            "super": "<Super>",
            "meta": "<Super>",
            "cmd": "<Super>",
        }.get(modifier.lower())
        if mapped is None:
            raise ShortcutInstallError(f"Unsupported shortcut modifier: {modifier}")
        prefix_parts.append(mapped)

    normalized_key = key.lower() if len(key) == 1 else key
    return "".join(prefix_parts) + normalized_key


def _load_custom_binding_paths() -> list[str]:
    raw_paths = _get_gsettings_value(GSETTINGS_SCHEMA, CUSTOM_KEY_BINDINGS_KEY)
    if raw_paths in {"", "[]", "()", "None", "@as []"}:
        return []

    paths = _parse_gsettings_value(raw_paths)
    if paths in (None, ""):
        return []
    if not isinstance(paths, list):
        raise ShortcutInstallError(
            f"Unexpected gsettings value for custom keybindings: {raw_paths}"
        )
    return [str(path) for path in paths]


def _read_schema_value(schema: str, key: str):
    try:
        raw = _get_gsettings_value(schema, key)
    except ShortcutInstallError:
        return None
    return _parse_gsettings_value(raw)


def _get_gsettings_value(schema: str, key: str) -> str:
    return _run_gsettings(["get", schema, key])


def _set_gsettings_value(schema: str, key: str, value: str) -> None:
    _run_gsettings(["set", schema, key, value])


def _run_gsettings(args: Sequence[str]) -> str:
    try:
        result = subprocess.run(
            ["gsettings", *args],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ShortcutInstallError("gsettings executable is not available.") from exc

    if result.returncode != 0:
        message = (result.stderr or result.stdout or "gsettings failed").strip()
        raise ShortcutInstallError(f"gsettings failed: {message}")
    return result.stdout.strip()


def _parse_gsettings_value(raw: str):
    raw = raw.strip()
    if raw.startswith("@as "):
        raw = raw.removeprefix("@as ").strip()
    if raw.startswith("@a{") and " }" in raw and raw.endswith("}"):
        # Best-effort for dict-typed GVariant output, not needed for shortcuts
        brace_index = raw.find("{")
        raw = raw[brace_index:]
    try:
        return ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw


def _format_variant_string(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _format_variant_string_list(values: Sequence[str]) -> str:
    return "[" + ",".join(_format_variant_string(value) for value in values) + "]"


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen = set()
    deduped: list[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _is_empty_binding(schema: str) -> bool:
    return (
        not _read_schema_value(schema, "name")
        and not _read_schema_value(schema, "command")
        and not _read_schema_value(schema, "binding")
    )
