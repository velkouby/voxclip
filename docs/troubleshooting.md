# Troubleshooting

Run the diagnostic report first:

```bash
voxclip --diagnose
```

Inspect recent persistent errors:

```bash
voxclip --show-error-log
```

The persistent error journal is stored at `~/.local/state/voxclip/errors.log`.
It is written only when an error occurs and must not contain dictated text,
microphone audio, clipboard text, or API keys.

Common issues:

- `audio_devices: unavailable`: install `libportaudio2` and check microphone access.
- Clipboard does not persist after the window closes: install `wl-clipboard` on Wayland or `xclip`/`xsel` on X11.
- No notification appears: install `libnotify-bin` and verify desktop notifications are enabled.
- OpenAI key missing: run `voxclip --set-openai-key` or complete onboarding again.
