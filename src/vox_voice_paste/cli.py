from __future__ import annotations

import argparse
import getpass
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from . import __version__
from .audio import AudioDeviceError, format_input_devices, list_input_devices
from .config import DEFAULT_UBUNTU_SHORTCUT, load_config
from .desktop.diagnostics import build_diagnostic_lines, format_diagnostic_report
from .logging_config import configure_logging
from .desktop.shortcuts import DEFAULT_SHORTCUT_COMMAND
from .security import OPENAI_API_KEY_SECRET, KeyringSecretService, SecretError, SecretService

DIST_NAME = "voice2paste"


def package_version() -> str:
    try:
        return version(DIST_NAME)
    except PackageNotFoundError:
        return __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vox-voice-paste",
        description=(
            "Dictate text from an Ubuntu desktop session and copy the final "
            "transcript to the clipboard."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {package_version()}",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="enable technical logs without transcript or secret content",
    )
    parser.add_argument(
        "--record-and-copy",
        action="store_true",
        help="open the recorder, start dictation, and copy the final transcript",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="use mock audio and transcription services for development",
    )
    parser.add_argument(
        "--settings",
        action="store_true",
        help="open the settings window",
    )
    parser.add_argument(
        "--set-ubuntu-shortcut",
        nargs="?",
        const=DEFAULT_UBUNTU_SHORTCUT,
        metavar="KEY_COMBO",
        help=(
            "create/update the GNOME shortcut for the recorder command "
            f"(default: {DEFAULT_UBUNTU_SHORTCUT})"
        ),
    )
    parser.add_argument(
        "--remove-ubuntu-shortcut",
        action="store_true",
        help="remove the managed GNOME shortcut binding and its autostart entry",
    )
    parser.add_argument(
        "--ensure-ubuntu-shortcut",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--list-audio-devices",
        action="store_true",
        help="list available audio input devices",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="print a diagnostic report without secrets, audio, or transcripts",
    )
    parser.add_argument(
        "--set-openai-key",
        action="store_true",
        help="prompt for an OpenAI API key and store it in the system keyring",
    )
    parser.add_argument(
        "--delete-openai-key",
        action="store_true",
        help="delete the stored OpenAI API key from the system keyring",
    )
    parser.add_argument(
        "--check-openai-key",
        action="store_true",
        help="print whether an OpenAI API key is present without showing it",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    secret_service: SecretService | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)
    secrets = secret_service or KeyringSecretService()

    if args.record_and_copy:
        from .app import run_record_and_copy

        return run_record_and_copy(mock=args.mock)

    if args.settings:
        from .app import run_settings

        return run_settings()

    if args.set_ubuntu_shortcut is not None:
        from .desktop import ShortcutInstallError, set_ubuntu_shortcut

        try:
            set_ubuntu_shortcut(
                shortcut=args.set_ubuntu_shortcut,
                command=DEFAULT_SHORTCUT_COMMAND,
            )
        except ShortcutInstallError as exc:
            parser.exit(1, f"vox-voice-paste: {exc}\n")
        print(
            f"Shortcut configured: {args.set_ubuntu_shortcut} -> "
            f"{DEFAULT_SHORTCUT_COMMAND}"
        )
        return 0

    if args.remove_ubuntu_shortcut:
        from .desktop import (
            ShortcutInstallError,
            remove_shortcut_autostart_entry,
            remove_ubuntu_shortcut,
        )

        try:
            remove_ubuntu_shortcut()
            remove_shortcut_autostart_entry()
        except ShortcutInstallError as exc:
            parser.exit(1, f"vox-voice-paste: {exc}\n")
        print("GNOME shortcut binding and autostart entry removed.")
        return 0

    if args.ensure_ubuntu_shortcut:
        from .desktop import ShortcutInstallError, set_ubuntu_shortcut

        config = load_config()
        try:
            set_ubuntu_shortcut(shortcut=config.ubuntu_shortcut)
        except ShortcutInstallError:
            return 0
        return 0

    if args.list_audio_devices:
        try:
            devices = list_input_devices()
        except AudioDeviceError as exc:
            parser.exit(1, f"vox-voice-paste: {exc}\n")
        print(format_input_devices(devices))
        return 0

    if args.diagnose:
        lines = build_diagnostic_lines(secret_service=secrets)
        print(format_diagnostic_report(lines))
        return 0

    if args.set_openai_key:
        value = getpass.getpass("OpenAI API key: ").strip()
        if not value:
            parser.exit(1, "vox-voice-paste: OpenAI API key was empty\n")
        try:
            secrets.set_secret(OPENAI_API_KEY_SECRET, value)
        except SecretError as exc:
            parser.exit(1, f"vox-voice-paste: {exc}\n")
        print("OpenAI API key stored in the system keyring.")
        return 0

    if args.delete_openai_key:
        try:
            secrets.delete_secret(OPENAI_API_KEY_SECRET)
        except SecretError as exc:
            parser.exit(1, f"vox-voice-paste: {exc}\n")
        print("OpenAI API key deleted from the system keyring.")
        return 0

    if args.check_openai_key:
        try:
            is_present = secrets.get_secret(OPENAI_API_KEY_SECRET) is not None
        except SecretError as exc:
            parser.exit(1, f"vox-voice-paste: {exc}\n")
        print(f"OpenAI API key: {'present' if is_present else 'missing'}")
        return 0

    from .app import run_main_app

    return run_main_app(secret_service=secrets)
