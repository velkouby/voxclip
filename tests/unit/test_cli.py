from __future__ import annotations

import subprocess
import sys

from vox_voice_paste.audio import AudioInputDevice
from vox_voice_paste.cli import build_parser, main
from vox_voice_paste.security import OPENAI_API_KEY_SECRET, InMemorySecretService


def test_build_parser_contains_expected_commands() -> None:
    help_text = build_parser().format_help()

    assert "vox-voice-paste" in help_text
    assert "--record-and-copy" in help_text
    assert "--list-audio-devices" in help_text
    assert "--diagnose" in help_text
    assert "--check-openai-key" in help_text


def test_main_without_args_prints_help(capsys) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Dictate text" in captured.out


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
