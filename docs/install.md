# Install

Build a local Debian package:

```bash
uv run python packaging/build_deb.py
sudo apt install ./dist/voxclip_0.2.0_amd64.deb
```

The first build downloads the locked Python wheels for `/usr/bin/python3` and
embeds them under `/opt/voxclip/venv`. If the network is temporarily
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

The installed shortcut commands for Ubuntu custom keyboard shortcuts are:

```bash
/usr/bin/voxclip --record-and-copy
/usr/bin/voxclip --record-and-translate
```

The app also applies these GNOME shortcuts automatically on startup and installs a
user autostart entry so the shortcuts are re-applied at every GNOME login.

You can also install them directly for GNOME with:

```bash
voxclip --set-ubuntu-shortcut
voxclip --set-ubuntu-translation-shortcut
```

To clean the desktop integration (for removal/uninstall workflows), run:

```bash
voxclip --remove-ubuntu-shortcut
```

Uninstall the package:

```bash
sudo apt remove voxclip
```

On Debian/Ubuntu uninstall, the package runs a best-effort cleanup of
`voxclip` desktop-integration files and tries to remove the managed GNOME
shortcut binding for each local user.

To guarantee a full per-user cleanup, you can still run:

```bash
voxclip --remove-ubuntu-shortcut
```

User configuration is intentionally left under the user config/keyring stores.
Remove it manually only if you want to reset the app:

```bash
rm -rf ~/.config/voxclip
voxclip --delete-openai-key
```
