# Vox Voice Paste

Vox Voice Paste est une application desktop Ubuntu pour dicter du texte, copier
la transcription finale dans le presse-papiers, puis coller manuellement avec
`Ctrl+V`.

La V1 ne simule pas `Ctrl+V` automatiquement. Ce choix evite les problemes de
fiabilite sous GNOME / Wayland.

## Etat actuel

Le flux principal est cable :

- lancement via `vox-voice-paste --record-and-copy` ;
- fenetre de dictee PySide6 ;
- capture micro via PortAudio / `sounddevice` ;
- transcription OpenAI Realtime ;
- mode mock sans cle OpenAI ;
- copie presse-papiers avec fallback `wl-copy`, `xclip`, `xsel`, puis Qt ;
- notification de succes via `notify-send` ;
- onboarding et fenetre de parametres ;
- stockage de la cle OpenAI dans le keyring systeme ;
- diagnostic sans secret ni transcript ;
- build `.deb` local.

Validations automatiques locales :

```bash
uv run pytest
uv run ruff check .
uv run python packaging/build_deb.py
QT_QPA_PLATFORM=offscreen uv run vox-voice-paste --record-and-copy --mock
```

Les validations restantes sont les tests reels Ubuntu : micro physique,
session Wayland/X11, vraie cle OpenAI, installation/desinstallation du paquet sur
une machine propre.

## Installation

### Option 1 - Depuis le depot avec `uv`

Prerequis :

```bash
sudo apt update
sudo apt install libportaudio2 libnotify-bin wl-clipboard xclip xsel
uv sync --all-extras --dev
```

Lancer l'application :

```bash
uv run vox-voice-paste
```

Lancer une dictee :

```bash
uv run vox-voice-paste --record-and-copy
```

### Option 2 - Paquet Debian local

Construire le paquet :

```bash
uv run python packaging/build_deb.py
```

Installer le paquet :

```bash
sudo apt install ./dist/vox-voice-paste_0.1.0_all.deb
```

Desinstaller :

```bash
sudo apt remove vox-voice-paste
```

## Cle API OpenAI

La cle OpenAI n'est jamais ecrite dans `config.toml`. Elle est stockee dans le
keyring systeme.

Vous pouvez la renseigner de quatre facons :

1. Au premier lancement :

```bash
vox-voice-paste
```

2. Depuis les parametres, avec le bouton `Configurer la cle OpenAI` :

```bash
vox-voice-paste --settings
```

3. Automatiquement pendant l'utilisation : si une dictee reelle est lancee sans
cle, une boite de dialogue demande la cle avant d'ouvrir la fenetre de dictee.

4. En ligne de commande :

```bash
vox-voice-paste --set-openai-key
vox-voice-paste --check-openai-key
vox-voice-paste --delete-openai-key
```

## Utilisation

Configurer un raccourci clavier Ubuntu personnalise qui execute :

```bash
vox-voice-paste --record-and-copy
```

Raccourci recommande : `Ctrl+Alt+V`.

Il n'y a pas de raccourci global installe automatiquement en V1 : Ubuntu gere
le raccourci, l'application fournit seulement la commande a executer.

Flux utilisateur :

1. Placez le curseur dans le champ texte cible.
2. Lancez le raccourci Ubuntu.
3. La fenetre Vox Voice Paste s'ouvre et l'enregistrement demarre.
4. Parlez.
5. Appuyez sur `Entree` ou cliquez sur le bouton rouge pour arreter.
6. Le texte final est copie dans le presse-papiers.
7. Collez avec `Ctrl+V`.

Dans la fenetre :

- `Entree` arrete et finalise la dictee ;
- `Echap` annule sans modifier le presse-papiers ;
- un texte vide n'ecrase pas le presse-papiers ;
- en cas d'erreur, la fenetre reste ouverte avec le texte recuperable.

## Mode mock

Le mode mock permet de tester l'interface sans micro et sans cle OpenAI :

```bash
uv run vox-voice-paste --record-and-copy --mock
```

En environnement headless :

```bash
QT_QPA_PLATFORM=offscreen uv run vox-voice-paste --record-and-copy --mock
```

## Diagnostic

Pour verifier l'environnement sans exposer de secret :

```bash
vox-voice-paste --diagnose
```

Le diagnostic indique notamment :

- version application et Python ;
- type de session desktop ;
- presence/absence de la cle OpenAI ;
- etat audio ;
- backend clipboard ;
- disponibilite des notifications.

## Developpement

Commandes utiles :

```bash
uv sync --all-extras --dev
uv run pytest
uv run ruff check .
uv run vox-voice-paste --help
uv run python -m vox_voice_paste --help
```

Le projet cible Python `>=3.12`.

Nommage :

- distribution Python : `voice2paste` ;
- module Python : `vox_voice_paste` ;
- commande utilisateur : `vox-voice-paste`.

## Contraintes produit

- Pas de collage automatique en V1.
- Pas d'historique local des transcriptions par defaut.
- Pas d'audio persistant sur disque.
- Pas de secret en clair dans les fichiers de configuration ou les diagnostics.
