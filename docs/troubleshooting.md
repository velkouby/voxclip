# Troubleshooting

Run the diagnostic report first:

```bash
vox-voice-paste --diagnose
```

Common issues:

- `audio_devices: unavailable`: install `libportaudio2` and check microphone access.
- Clipboard does not persist after the window closes: install `wl-clipboard` on Wayland or `xclip`/`xsel` on X11.
- No notification appears: install `libnotify-bin` and verify desktop notifications are enabled.
- OpenAI key missing: run `vox-voice-paste --set-openai-key` or complete onboarding again.
