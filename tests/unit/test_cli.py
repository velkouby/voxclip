from __future__ import annotations

import subprocess
import sys

from vox_voice_paste.audio import AudioInputDevice
from vox_voice_paste.ui.onboarding_window import RECOMMENDED_SHORTCUT, SHORTCUT_COMMAND
from vox_voice_paste.cli import build_parser, main
from vox_voice_paste.security import OPENAI_API_KEY_SECRET, InMemorySecretService


def test_build_parser_contains_expected_commands() -> None:
    help_text = build_parser().format_help()

    assert "vox-voice-paste" in help_text
    assert "--record-and-copy" in help_text
    assert "--set-ubuntu-shortcut" in help_text
    assert "--remove-ubuntu-shortcut" in help_text
    assert "--list-audio-devices" in help_text
    assert "--diagnose" in help_text
    assert "--check-openai-key" in help_text


def test_set_ubuntu_shortcut_default_binding_runs_for_default_command(monkeypatch) -> None:
    recorded = {}

    def fake_set_ubuntu_shortcut(*, shortcut: str, command: str) -> str:
        recorded["shortcut"] = shortcut
        recorded["command"] = command
        return "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"

    monkeypatch.setattr("vox_voice_paste.desktop.set_ubuntu_shortcut", fake_set_ubuntu_shortcut)

    assert main(["--set-ubuntu-shortcut"]) == 0

    assert recorded["shortcut"] == RECOMMENDED_SHORTCUT
    assert recorded["command"] == SHORTCUT_COMMAND


def test_set_ubuntu_shortcut_accepts_custom_binding(monkeypatch) -> None:
    recorded = {}

    def fake_set_ubuntu_shortcut(*, shortcut: str, command: str) -> str:
        recorded["shortcut"] = shortcut
        recorded["command"] = command
        return "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"

    monkeypatch.setattr("vox_voice_paste.desktop.set_ubuntu_shortcut", fake_set_ubuntu_shortcut)

    assert main(["--set-ubuntu-shortcut", "Ctrl+Alt+K"]) == 0

    assert recorded["shortcut"] == "Ctrl+Alt+K"
    assert recorded["command"] == SHORTCUT_COMMAND


def test_remove_ubuntu_shortcut_runs_cleanup(monkeypatch) -> None:
    removed = {}

    def fake_remove_ubuntu_shortcut() -> list[str]:
        removed["binding"] = "removed"
        return ["/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"]

    def fake_remove_shortcut_autostart_entry() -> None:
        removed["autostart"] = "removed"

    monkeypatch.setattr(
        "vox_voice_paste.desktop.remove_ubuntu_shortcut",
        fake_remove_ubuntu_shortcut,
    )
    monkeypatch.setattr(
        "vox_voice_paste.desktop.remove_shortcut_autostart_entry",
        fake_remove_shortcut_autostart_entry,
    )

    assert main(["--remove-ubuntu-shortcut"]) == 0

    assert removed["binding"] == "removed"
    assert removed["autostart"] == "removed"


def test_main_without_args_runs_main_app(monkeypatch) -> None:
    import vox_voice_paste.app

    monkeypatch.setattr(vox_voice_paste.app, "run_main_app", lambda **kwargs: 17)

    assert main([], secret_service=InMemorySecretService()) == 17


def test_module_help_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vox_voice_paste", "--help"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "vox-voice-paste" in result.stdout


def test_check_openai_key_does_not_print_secret(capsys) -> None:
    secrets = InMemorySecretService({OPENAI_API_KEY_SECRET: "sk-test-secret"})

    exit_code = main(["--check-openai-key"], secret_service=secrets)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "present" in captured.out
    assert "sk-test-secret" not in captured.out


def test_list_audio_devices_prints_devices(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "vox_voice_paste.cli.list_input_devices",
        lambda: [
            AudioInputDevice(
                id="0",
                name="Internal Mic",
                max_input_channels=1,
                default_sample_rate=24_000,
                is_default=True,
            )
        ],
    )

    exit_code = main(["--list-audio-devices"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Internal Mic" in captured.out


def test_record_and_copy_mock_runs_app(monkeypatch) -> None:
    import vox_voice_paste.app

    monkeypatch.setattr(vox_voice_paste.app, "run_record_and_copy", lambda *, mock: 23)

    assert main(["--record-and-copy", "--mock"]) == 23


def test_record_and_copy_real_runs_app(monkeypatch) -> None:
    import vox_voice_paste.app

    monkeypatch.setattr(vox_voice_paste.app, "run_record_and_copy", lambda *, mock: 29)

    assert main(["--record-and-copy"]) == 29


def test_settings_runs_settings_window(monkeypatch) -> None:
    import vox_voice_paste.app

    monkeypatch.setattr(vox_voice_paste.app, "run_settings", lambda: 19)

    assert main(["--settings"]) == 19
