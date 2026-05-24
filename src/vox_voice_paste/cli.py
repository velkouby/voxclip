from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from . import __version__
from .logging_config import configure_logging

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
        "--list-audio-devices",
        action="store_true",
        help="list available audio input devices",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="print a diagnostic report without secrets, audio, or transcripts",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

    if args.record_and_copy:
        mode = "mock " if args.mock else ""
        parser.exit(1, f"vox-voice-paste: {mode}recording is not implemented yet\n")

    if args.settings:
        parser.exit(1, "vox-voice-paste: settings are not implemented yet\n")

    if args.list_audio_devices:
        parser.exit(1, "vox-voice-paste: audio device listing is not implemented yet\n")

    if args.diagnose:
        parser.exit(1, "vox-voice-paste: diagnostics are not implemented yet\n")

    parser.print_help()
    return 0
