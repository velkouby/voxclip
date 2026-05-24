from __future__ import annotations

import argparse
import shutil
import stat
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "vox-voice-paste"
INSTALL_DIR = Path("opt") / PACKAGE_NAME


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Debian package.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    metadata = _project_metadata()
    package_version = metadata["version"]
    architecture = _dpkg_architecture()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"{PACKAGE_NAME}-deb-") as temp_dir:
        package_root = Path(temp_dir) / f"{PACKAGE_NAME}_{package_version}_{architecture}"
        _populate_package_root(package_root, package_version, architecture)
        subprocess.run(
            [
                "dpkg-deb",
                "--root-owner-group",
                "--build",
                str(package_root),
                str(output_dir / f"{PACKAGE_NAME}_{package_version}_{architecture}.deb"),
            ],
            check=True,
        )

    return 0


def _project_metadata() -> dict[str, str]:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    project = pyproject["project"]
    return {"version": project["version"]}


def _dpkg_architecture() -> str:
    result = subprocess.run(
        ["dpkg", "--print-architecture"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _populate_package_root(package_root: Path, version: str, architecture: str) -> None:
    app_dir = package_root / INSTALL_DIR
    venv_dir = app_dir / "venv"
    app_dir.mkdir(parents=True, exist_ok=True)
    _build_application_venv(venv_dir)

    bin_dir = package_root / "usr/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / "vox-voice-paste"
    launcher.write_text(
        "#!/bin/sh\n"
        "exec /opt/vox-voice-paste/venv/bin/python -m vox_voice_paste \"$@\"\n",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    applications_dir = package_root / "usr/share/applications"
    applications_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT / "packaging/desktop/vox-voice-paste.desktop",
        applications_dir / "vox-voice-paste.desktop",
    )

    icon_dir = package_root / "usr/share/icons/hicolor/scalable/apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT / "packaging/icons/vox-voice-paste.svg",
        icon_dir / "vox-voice-paste.svg",
    )

    debian_dir = package_root / "DEBIAN"
    debian_dir.mkdir(parents=True, exist_ok=True)
    control = (ROOT / "packaging/debian/control").read_text(encoding="utf-8")
    control = control.replace("Version: 0.1.0", f"Version: {version}")
    control = control.replace("Architecture: @ARCH@", f"Architecture: {architecture}")
    (debian_dir / "control").write_text(control, encoding="utf-8")


def _build_application_venv(venv_dir: Path) -> None:
    subprocess.run(["uv", "venv", "--python", "/usr/bin/python3", str(venv_dir)], check=True)
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(venv_dir / "bin/python"),
            str(ROOT),
        ],
        check=True,
    )
    _remove_python_caches(venv_dir)


def _remove_python_caches(path: Path) -> None:
    for cache_dir in path.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
    for bytecode in path.rglob("*.py[co]"):
        bytecode.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
