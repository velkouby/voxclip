# Install

Build a local Debian package:

```bash
uv run python packaging/build_deb.py
sudo apt install ./dist/vox-voice-paste_0.1.0_all.deb
```

Runtime system packages expected on Ubuntu:

```bash
sudo apt install \
  libportaudio2 \
  libnotify-bin \
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
