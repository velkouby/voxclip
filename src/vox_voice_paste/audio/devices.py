# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

from dataclasses import dataclass
from typing import Any


class AudioDeviceError(RuntimeError):
    """Raised when audio device discovery fails."""


@dataclass(frozen=True)
class AudioInputDevice:
    id: str
    name: str
    max_input_channels: int
    default_sample_rate: int
    is_default: bool = False


def list_input_devices() -> list[AudioInputDevice]:
    try:
        import sounddevice as sd

        raw_devices = sd.query_devices()
        default_index = _default_input_index(sd.default.device)
    except OSError as exc:
        raise AudioDeviceError(
            "Unable to query audio input devices; PortAudio may be missing"
        ) from exc
    except Exception as exc:
        raise AudioDeviceError("Unable to query audio input devices") from exc

    return normalize_input_devices(raw_devices, default_input_index=default_index)


def normalize_input_devices(
    raw_devices: list[dict[str, Any]],
    *,
    default_input_index: int | None,
) -> list[AudioInputDevice]:
    devices: list[AudioInputDevice] = []
    for index, raw_device in enumerate(raw_devices):
        max_input_channels = int(raw_device.get("max_input_channels") or 0)
        if max_input_channels <= 0:
            continue
        sample_rate = int(float(raw_device.get("default_samplerate") or 0))
        devices.append(
            AudioInputDevice(
                id=str(index),
                name=str(raw_device.get("name") or f"Input device {index}"),
                max_input_channels=max_input_channels,
                default_sample_rate=sample_rate,
                is_default=index == default_input_index,
            )
        )
    return devices


def format_input_devices(devices: list[AudioInputDevice]) -> str:
    if not devices:
        return "No input audio devices found."

    lines = ["Input audio devices:"]
    for device in devices:
        marker = " default" if device.is_default else ""
        lines.append(
            f"- {device.id}: {device.name}"
            f" ({device.max_input_channels} ch, {device.default_sample_rate} Hz{marker})"
        )
    return "\n".join(lines)


def _default_input_index(default_device: Any) -> int | None:
    if isinstance(default_device, (list, tuple)):
        raw_index = default_device[0] if default_device else None
    else:
        raw_index = default_device

    if raw_index is None:
        return None

    try:
        index = int(raw_index)
    except (TypeError, ValueError):
        return None

    return index if index >= 0 else None
