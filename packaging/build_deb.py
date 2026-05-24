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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Debian package.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    metadata = _project_metadata()
    package_version = metadata["version"]
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"{PACKAGE_NAME}-deb-") as temp_dir:
        package_root = Path(temp_dir) / f"{PACKAGE_NAME}_{package_version}_all"
        _populate_package_root(package_root, package_version)
        subprocess.run(
            [
                "dpkg-deb",
                "--root-owner-group",
                "--build",
                str(package_root),
                str(output_dir / f"{PACKAGE_NAME}_{package_version}_all.deb"),
            ],
            check=True,
        )

    return 0


def _project_metadata() -> dict[str, str]:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    project = pyproject["project"]
    return {"version": project["version"]}


def _populate_package_root(package_root: Path, version: str) -> None:
    package_dir = package_root / "usr/lib/python3/dist-packages/vox_voice_paste"
    package_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ROOT / "src/vox_voice_paste",
        package_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    bin_dir = package_root / "usr/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / "vox-voice-paste"
    launcher.write_text(
        "#!/usr/bin/python3\n"
        "from vox_voice_paste.main import main\n"
        "raise SystemExit(main())\n",
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
    (debian_dir / "control").write_text(control, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
