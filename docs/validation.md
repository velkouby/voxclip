# Validation Status

Date: 2026-05-24

Automated validation passed locally:

```bash
uv run pytest
uv run ruff check .
uv run python packaging/build_deb.py
uv run voxclip --help
uv run python -m vox_voice_paste --help
uv run voxclip --diagnose
QT_QPA_PLATFORM=offscreen uv run voxclip --record-and-copy --mock
```

Current local diagnostic notes:

- PortAudio is missing locally, so real microphone listing/capture still needs Ubuntu validation after installing `libportaudio2`.
- OpenAI key is missing locally, so real Realtime transcription still needs validation with a valid key.
- Clipboard persistence after process exit still needs validation on a real Wayland/X11 desktop with `wl-copy`, `xclip`, or `xsel`.
- Debian package builds locally at `dist/voxclip_0.2.0_amd64.deb`; install/uninstall on a clean Ubuntu machine is still pending.
