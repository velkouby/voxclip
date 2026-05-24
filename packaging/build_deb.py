from __future__ import annotations

import argparse
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "vox-voice-paste"
INSTALL_DIR = Path("opt") / PACKAGE_NAME


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Debian package.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="build from the local uv cache only; dependencies must already be cached",
    )
    args = parser.parse_args()

    metadata = _project_metadata()
    package_version = metadata["version"]
    architecture = _dpkg_architecture()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"{PACKAGE_NAME}-deb-") as temp_dir:
        package_root = Path(temp_dir) / f"{PACKAGE_NAME}_{package_version}_{architecture}"
        try:
            _populate_package_root(
                package_root,
                package_version,
                architecture,
                offline=args.offline,
            )
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
        except subprocess.CalledProcessError as exc:
            _print_build_failure(exc, offline=args.offline)
            return exc.returncode

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


def _populate_package_root(
    package_root: Path,
    version: str,
    architecture: str,
    *,
    offline: bool,
) -> None:
    app_dir = package_root / INSTALL_DIR
    venv_dir = app_dir / "venv"
    app_dir.mkdir(parents=True, exist_ok=True)
    _build_application_venv(venv_dir, version, offline=offline)

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

    for script in (ROOT / "packaging/debian").iterdir():
        if script.name == "control" or not script.is_file():
            continue
        shutil.copy2(script, debian_dir / script.name)
        # Maintainer scripts need executable bit in the package.
        current_mode = (debian_dir / script.name).stat().st_mode
        (debian_dir / script.name).chmod(current_mode | 0o111)


def _build_application_venv(venv_dir: Path, version: str, *, offline: bool) -> None:
    subprocess.run(["uv", "venv", "--python", "/usr/bin/python3", str(venv_dir)], check=True)
    with tempfile.NamedTemporaryFile(suffix=".requirements.txt") as requirements_file:
        requirements_path = Path(requirements_file.name)
        _run_uv(
            [
                "uv",
                "export",
                "--frozen",
                "--no-dev",
                "--no-emit-project",
                "--format",
                "requirements.txt",
                "--output-file",
                str(requirements_path),
            ],
            offline=offline,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
        )
        _run_uv(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(venv_dir / "bin/python"),
                "--requirements",
                str(requirements_path),
            ],
            offline=offline,
        )
    _install_application_source(venv_dir, version)
    _remove_python_caches(venv_dir)


def _run_uv(
    command: list[str],
    *,
    offline: bool,
    cwd: Path | None = None,
    stdout: int | None = None,
) -> None:
    if offline:
        command = [command[0], "--offline", *command[1:]]
    subprocess.run(command, check=True, cwd=cwd, stdout=stdout)


def _install_application_source(venv_dir: Path, version: str) -> None:
    site_packages = _site_packages_dir(venv_dir)

    package_target = site_packages / "vox_voice_paste"
    if package_target.exists():
        shutil.rmtree(package_target)
    shutil.copytree(ROOT / "src/vox_voice_paste", package_target)

    dist_info = site_packages / f"voice2paste-{version}.dist-info"
    if dist_info.exists():
        shutil.rmtree(dist_info)
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: voice2paste\n"
        f"Version: {version}\n",
        encoding="utf-8",
    )
    (dist_info / "WHEEL").write_text(
        "Wheel-Version: 1.0\n"
        "Generator: packaging/build_deb.py\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n",
        encoding="utf-8",
    )


def _site_packages_dir(venv_dir: Path) -> Path:
    result = subprocess.run(
        [
            str(venv_dir / "bin/python"),
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return Path(result.stdout.strip())


def _remove_python_caches(path: Path) -> None:
    for cache_dir in path.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
    for bytecode in path.rglob("*.py[co]"):
        bytecode.unlink()


def _print_build_failure(exc: subprocess.CalledProcessError, *, offline: bool) -> None:
    print("Failed to build Debian package.", file=sys.stderr)
    print(f"Failed command: {' '.join(map(str, exc.cmd))}", file=sys.stderr)
    if _is_uv_dependency_step(exc.cmd):
        print(
            "The package build installs Python wheels into an embedded virtual environment.",
            file=sys.stderr,
        )
        if offline:
            print(
                "Offline mode requires all runtime dependencies to already be present "
                "in the local uv cache.",
                file=sys.stderr,
            )
        else:
            print(
                "If PyPI is unreachable, fix DNS/network and rerun the build, or use "
                "`--offline` after the uv cache has been populated.",
                file=sys.stderr,
            )


def _is_uv_dependency_step(command: object) -> bool:
    return (
        isinstance(command, list)
        and command[:1] == ["uv"]
        and any(part in ("export", "pip") for part in command[1:3])
    )


if __name__ == "__main__":
    raise SystemExit(main())
