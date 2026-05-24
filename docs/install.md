# Install

Build a local Debian package:

```bash
uv run python packaging/build_deb.py
sudo apt install ./dist/vox-voice-paste_0.1.0_amd64.deb
```

The first build downloads the locked Python wheels for `/usr/bin/python3` and
embeds them under `/opt/vox-voice-paste/venv`. If the network is temporarily
unavailable but those system-Python wheels are already present in the local
`uv` cache, build from cache only:

```bash
uv run python packaging/build_deb.py --offline
```

Runtime system packages expected on Ubuntu:

```bash
sudo apt install \
  libportaudio2 \
  libnotify-bin \
  libxcb-cursor0 \
  wl-clipboard xclip xsel
```

The installed shortcut command for Ubuntu custom keyboard shortcuts is:

```bash
vox-voice-paste --record-and-copy
```

Uninstall the package:

```bash
sudo apt remove vox-voice-paste
```

User configuration is intentionally left under the user config/keyring stores.
Remove it manually only if you want to reset the app:

```bash
rm -rf ~/.config/vox-voice-paste
vox-voice-paste --delete-openai-key
```
