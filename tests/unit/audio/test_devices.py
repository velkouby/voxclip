from __future__ import annotations

from vox_voice_paste.audio.devices import format_input_devices, normalize_input_devices


def test_normalize_input_devices_filters_output_only_devices() -> None:
    devices = normalize_input_devices(
        [
            {"name": "Speakers", "max_input_channels": 0, "default_samplerate": 48_000},
            {"name": "Internal Mic", "max_input_channels": 2, "default_samplerate": 44_100},
        ],
        default_input_index=1,
    )

    assert len(devices) == 1
    assert devices[0].id == "1"
    assert devices[0].name == "Internal Mic"
    assert devices[0].is_default is True


def test_format_input_devices() -> None:
    devices = normalize_input_devices(
        [{"name": "Internal Mic", "max_input_channels": 1, "default_samplerate": 24_000}],
        default_input_index=0,
    )

    formatted = format_input_devices(devices)

    assert "Internal Mic" in formatted
    assert "default" in formatted
