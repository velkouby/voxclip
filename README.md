# Vox Voice Paste

Vox Voice Paste is an Ubuntu desktop dictation helper. The V1 goal is to open a
small recorder from a user-configured Ubuntu shortcut, stream speech to
transcription, copy the final text to the clipboard, and let the user paste it
manually with `Ctrl+V`.

The project is currently in Phase A: installable Python skeleton, CLI entrypoint,
logging baseline, and tests.

## Development

Install and run through `uv`:

```bash
uv sync --all-extras --dev
uv run vox-voice-paste --help
uv run vox-voice-paste --diagnose
uv run vox-voice-paste --check-openai-key
uv run vox-voice-paste --set-openai-key
uv run python -m vox_voice_paste --help
uv run pytest
uv run ruff check .
```

The project targets Python `>=3.12`.

The distribution package is `voice2paste`, the Python module is
`vox_voice_paste`, and the user-facing command is `vox-voice-paste`.

Configuration is stored under the user config directory. The OpenAI API key is
stored separately in the system keyring and is never written to `config.toml` or
shown in diagnostics.

Audio capture uses PortAudio through `sounddevice`. On Ubuntu, install the system
runtime before listing or capturing real microphones:

```bash
sudo apt install libportaudio2
```

## Product Constraints

- No automatic paste simulation in V1.
- No local transcript history by default.
- No persistent audio files.
- OpenAI API keys must be stored in the system keyring, never in plaintext config.
