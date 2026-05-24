from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import tomli_w
from platformdirs import user_config_path
from pydantic import BaseModel, ConfigDict, Field, ValidationError

APP_ID = "voxclip"
LEGACY_APP_IDS = ("vox-voice-paste",)
CONFIG_FILENAME = "config.toml"
DEFAULT_TRANSCRIPTION_MODEL = "gpt-realtime-whisper"
DEFAULT_UBUNTU_SHORTCUT = "Ctrl+Alt+N"


class ConfigError(RuntimeError):
    """Raised when the user config file cannot be loaded or validated."""


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    config_version: int = Field(default=1, ge=1)
    onboarding_completed: bool = False
    default_input_device_id: str | None = None
    transcription_model: str = DEFAULT_TRANSCRIPTION_MODEL
    transcription_language: str | None = None
    transcription_delay: str = Field(default="low", pattern="^(minimal|low|medium|high|xhigh)$")
    ubuntu_shortcut: str = DEFAULT_UBUNTU_SHORTCUT


def default_config_path() -> Path:
    return user_config_path(APP_ID, appauthor=False) / CONFIG_FILENAME


def legacy_config_paths() -> list[Path]:
    return [
        user_config_path(legacy_app_id, appauthor=False) / CONFIG_FILENAME
        for legacy_app_id in LEGACY_APP_IDS
    ]


def load_config(path: Path | None = None) -> AppConfig:
    config_path = _config_path_for_load(path)
    if not config_path.exists():
        return AppConfig()

    try:
        with config_path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)
    except OSError as exc:
        raise ConfigError(f"Cannot read config file: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML config file: {config_path}") from exc

    return parse_config(raw_config, source=config_path)


def _config_path_for_load(path: Path | None = None) -> Path:
    if path is not None:
        return path

    config_path = default_config_path()
    if config_path.exists():
        return config_path

    for legacy_config_path in legacy_config_paths():
        if legacy_config_path.exists():
            return legacy_config_path

    return config_path


def parse_config(raw_config: dict[str, Any], *, source: Path | None = None) -> AppConfig:
    try:
        return AppConfig.model_validate(raw_config)
    except ValidationError as exc:
        location = f": {source}" if source else ""
        raise ConfigError(f"Invalid config values{location}") from exc


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    payload = tomli_w.dumps(config.model_dump(mode="json", exclude_none=True))
    temp_name: str | None = None

    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{config_path.name}.",
            suffix=".tmp",
            dir=config_path.parent,
            text=True,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, config_path)
    except OSError as exc:
        raise ConfigError(f"Cannot write config file: {config_path}") from exc
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)

    return config_path
