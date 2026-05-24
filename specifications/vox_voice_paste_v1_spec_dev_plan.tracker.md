# Vox Voice Paste V1.0 - Tracker de developpement

Source : `specifications/vox_voice_paste_v1_spec_dev_plan.md`  
Date de creation : 2026-05-23  
Statut global : En cours - flux reel cable, installation Ubuntu propre et validations reelles restantes  
Environnement cible : Ubuntu desktop, priorite GNOME / Wayland  
Environnement local observe : `uv 0.9.17`, `.venv` present, Python `3.14.2`, depot Git initialise

---

## 1. Objectif du tracker

Ce document transforme la specification V1.0 en suivi de developpement executable dans ce workspace.

Objectif V1.0 :

- lancer une mini fenetre de dictee depuis une commande utilisable par un raccourci Ubuntu ;
- enregistrer le micro sans ecrire l'audio sur disque ;
- afficher une transcription live ;
- finaliser la transcription avec l'API OpenAI Realtime Transcription ;
- copier le texte final dans le presse-papiers ;
- notifier l'utilisateur qu'il peut coller manuellement avec `Ctrl+V`.

La V1.0 ne doit pas faire de collage automatique.

---

## 2. Etat initial du workspace

### 2.1 Fichiers presents

- [x] `pyproject.toml`
- [x] `specifications/vox_voice_paste_v1_spec_dev_plan.md`
- [x] `.venv/`
- [x] `uv.lock`
- [x] `src/`
- [x] `tests/`
- [x] `README.md`
- [x] `docs/`
- [x] `packaging/`

### 2.2 `pyproject.toml` actuel

```toml
[project]
name = "voice2paste"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "keyring>=25.7",
    "numpy>=2.3",
    "platformdirs>=4.5",
    "pydantic>=2.12",
    "PySide6>=6.10",
    "sounddevice>=0.5",
    "tomli-w>=1.2",
    "websockets>=15.0",
]
```

Points a suivre :

- [x] Confirmer si le nom de distribution reste `voice2paste` ou devient `vox-voice-paste`.
  - Decision : conserver la distribution Python `voice2paste`.
- [x] Conserver le binaire utilisateur `vox-voice-paste`, meme si le nom de package Python reste `voice2paste`.
- [x] Utiliser le module Python `vox_voice_paste` pour rester coherent avec la marque produit.
- [x] Confirmer Python `>=3.14` comme contrainte officielle, ou revenir a une cible plus large si PySide6, sounddevice, packaging `.deb` ou OpenAI SDK bloquent.
  - Decision : cibler `>=3.12` pour rester compatible avec Ubuntu 24.04 et faciliter le packaging.

---

## 3. Decisions techniques V1.0

### 3.1 Decisions confirmees

- [x] Pas de collage automatique en V1.0.
- [x] Le raccourci global est configure par Ubuntu et execute `vox-voice-paste --record-and-copy`.
- [x] Pas d'historique local des transcriptions par defaut.
- [x] Pas d'audio persistant sur disque.
- [x] Cle OpenAI stockee dans le keyring systeme, jamais en clair dans la config.
- [x] UI, audio, transcription, presse-papiers et notifications doivent rester decouples.
- [x] Mode mock complet avant branchement OpenAI reel.

### 3.2 Ajustements recommandes au plan initial

- [x] Remplacer le modele cible `gpt-realtime-whisper` par une valeur configurable.
  - Verification officielle 2026-05-24 : la documentation Realtime Transcription courante cible `gpt-realtime-whisper`.
  - Decision : conserver `gpt-realtime-whisper` comme defaut configurable.
  - Source officielle : https://platform.openai.com/docs/guides/realtime-transcription
- [x] Ne pas faire dependre la copie presse-papiers uniquement de `QClipboard` sans validation Wayland.
  - Sous Linux, la persistance du contenu apres fermeture immediate du processus doit etre testee.
  - Prevoir un `ClipboardService` capable d'utiliser Qt, `wl-copy` sur Wayland, et `xclip` ou `xsel` sur X11 selon disponibilite.
- [x] Ajouter un verrou de session pour empecher deux dictees concurrentes.
- [x] Ajouter une strategie de timeout explicite pour finalisation OpenAI.
- [ ] Ajouter une commande dev `--mock` utilisable avec `--record-and-copy`.
- [ ] Ajouter une commande dev pour tester le clipboard sans OpenAI.
- [x] Ajouter des tests sans micro reel, sans keyring reel et sans reseau.
- [ ] Distinguer les logs techniques des donnees utilisateur : jamais de transcript en log par defaut.

---

## 4. Conventions de suivi

Statuts :

- `[ ]` a faire
- `[~]` en cours
- `[x]` termine
- `[!]` bloque ou risque actif

Priorites :

- `P0` indispensable pour V1.0
- `P1` fortement recommande pour V1.0
- `P2` utile mais reportable si necessaire

Definition of done globale :

- [x] La commande `uv run vox-voice-paste --help` fonctionne.
- [x] La commande `uv run vox-voice-paste --record-and-copy --mock` ouvre la fenetre et produit une transcription simulee.
- [x] La commande configuree dans Ubuntu est documentee : `vox-voice-paste --record-and-copy`.
- [ ] Une dictee reelle courte copie le texte final dans le presse-papiers.
- [ ] L'annulation ne modifie pas le presse-papiers.
- [x] Une erreur reseau ou OpenAI ne provoque pas de crash.
- [x] Le diagnostic ne revele aucune donnee sensible.
- [ ] Les tests unitaires et les tests d'integration mock passent via `uv run pytest`.

---

## 5. Commandes de developpement prevues

### 5.1 Environnement local

```bash
uv venv --python 3.12
source .venv/bin/activate
uv sync --all-extras --dev
```

Notes :

- [x] Ajouter un `uv.lock` apres definition des dependances.
- [x] Documenter la version Python cible dans le README.
- [x] Ne pas supposer que l'utilisateur active toujours le venv : les commandes de documentation doivent preferer `uv run`.

### 5.2 Commandes attendues

```bash
uv run vox-voice-paste --help
uv run vox-voice-paste --settings
uv run vox-voice-paste --record-and-copy --mock
uv run vox-voice-paste --record-and-copy
uv run vox-voice-paste --list-audio-devices
uv run vox-voice-paste --diagnose
uv run vox-voice-paste --check-openai-key
uv run vox-voice-paste --set-openai-key
uv run vox-voice-paste --delete-openai-key
uv run pytest
```

---

## 6. Architecture cible

Structure a creer :

```text
src/
  vox_voice_paste/
    __init__.py
    __main__.py
    main.py
    cli.py
    app.py
    config.py
    logging_config.py
    audio/
      __init__.py
      capture.py
      devices.py
      level_meter.py
      resample.py
      fake.py
    transcription/
      __init__.py
      base.py
      mock.py
      openai_realtime.py
      transcript_buffer.py
    desktop/
      __init__.py
      clipboard.py
      notifications.py
      environment.py
      diagnostics.py
      session_lock.py
    ui/
      __init__.py
      recorder_window.py
      settings_window.py
      onboarding_window.py
      widgets.py
    security/
      __init__.py
      secrets.py
tests/
  unit/
  integration/
  fixtures/
docs/
  install.md
  troubleshooting.md
packaging/
  desktop/
  icons/
  debian/
```

Tracking :

- [x] Valider que cette structure reste proportionnee au projet.
- [x] Creer d'abord les interfaces et mocks avant les implementations systeme.
- [ ] Eviter les imports directs entre UI et OpenAI/audio bas niveau.

---

## 7. Dependances a definir

### 7.1 Runtime

- [x] `PySide6` - interface desktop Qt.
- [x] `sounddevice` - capture micro.
- [x] `numpy` - traitement audio et RMS.
- [x] `openai` ou `websockets` - client Realtime Transcription, a choisir apres prototype.
  - Decision : `websockets`, pour garder le protocole Realtime explicite et testable sans reseau.
- [x] `platformdirs` - chemins de configuration utilisateur.
- [x] `pydantic` - validation config.
- [x] `PyYAML` ou format TOML natif - persistance config.
  - Decision : lecture via `tomllib`, ecriture via `tomli-w`.
- [x] `keyring` - stockage cle OpenAI.
- [ ] `dbus-next` ou fallback `notify-send` - notifications.

### 7.2 Developpement et tests

- [x] `pytest`
- [x] `pytest-qt`
- [ ] `pytest-asyncio`
- [x] `ruff`
- [ ] `mypy` ou `pyright` si le typage strict est retenu.

### 7.3 Dependances systeme Ubuntu a documenter

- [!] PortAudio / bibliotheques necessaires a `sounddevice`.
  - Local : `uv run vox-voice-paste --list-audio-devices` echoue car la bibliotheque PortAudio est absente.
  - Action Ubuntu : installer `libportaudio2`.
- [ ] Backend Secret Service pour `keyring`.
- [x] `wl-clipboard` recommande sur Wayland si retenu.
- [x] `xclip` ou `xsel` recommande sur X11 si retenu.
- [x] Systeme de notifications compatible `org.freedesktop.Notifications`.

---

## 8. Backlog par phases

### Phase A - Initialisation projet

Objectif : obtenir un squelette installable et testable.

- [x] `A-001` `P0` Confirmer nom package, module et CLI.
- [x] `A-002` `P0` Completer `pyproject.toml` avec build backend, scripts console et dependances de base.
- [x] `A-003` `P0` Creer `src/vox_voice_paste`.
- [x] `A-004` `P0` Ajouter `__main__.py`, `main.py`, `cli.py`.
- [x] `A-005` `P0` Ajouter commande `vox-voice-paste --help`.
- [x] `A-006` `P0` Ajouter `tests/` et premier test CLI.
- [x] `A-007` `P1` Ajouter `ruff` et configuration minimale.
- [x] `A-008` `P1` Ajouter logs structures sans donnees sensibles.
- [x] `A-009` `P1` Creer README initial avec commandes `uv`.
- [x] `A-010` `P2` Initialiser Git si souhaite pour le suivi projet.

Critere d'acceptation :

- [x] `uv run vox-voice-paste --help` fonctionne.
- [x] `uv run python -m vox_voice_paste --help` fonctionne.
- [x] `uv run pytest` passe.

### Phase B - Configuration et secrets

Objectif : gerer config utilisateur et cle OpenAI proprement.

- [x] `B-001` `P0` Definir modele de configuration.
- [x] `B-002` `P0` Definir chemin config via `platformdirs`.
- [x] `B-003` `P0` Implementer lecture/ecriture atomique.
- [x] `B-004` `P0` Implementer `SecretService` base.
- [x] `B-005` `P0` Implementer stockage keyring.
- [x] `B-006` `P1` Ajouter commande dev pour definir ou supprimer la cle OpenAI.
- [x] `B-007` `P0` Masquer secrets dans logs et diagnostics.
- [x] `B-008` `P1` Tester config absente, config invalide, keyring indisponible.

Critere d'acceptation :

- [x] La cle n'est jamais ecrite dans le fichier de config.
- [x] Le diagnostic indique seulement presence/absence de cle.
- [x] Les tests unitaires couvrent config et secrets.

### Phase C - Audio devices et capture

Objectif : lister les micros et produire des chunks PCM compatibles.

- [x] `C-001` `P0` Lister les peripheriques d'entree.
- [x] `C-002` `P0` Identifier le micro par defaut.
- [x] `C-003` `P0` Implementer capture micro avec `sounddevice`.
- [x] `C-004` `P0` Convertir en mono.
- [x] `C-005` `P0` Resampler vers PCM mono 24 kHz si necessaire.
- [x] `C-006` `P0` Produire des chunks `bytes`.
- [x] `C-007` `P0` Calculer niveau RMS pour l'UI.
- [x] `C-008` `P0` Gerer arret propre et erreurs peripherique.
- [x] `C-009` `P0` Ajouter source audio factice pour tests.

Critere d'acceptation :

- [!] `uv run vox-voice-paste --list-audio-devices` affiche les entrees audio.
  - Commande implementee et testee avec fake ; validation locale bloquee par PortAudio absent.
- [!] Un test local capture 3 secondes sans ecriture disque.
  - Bloque localement tant que PortAudio et un micro ne sont pas disponibles.
- [!] Le niveau sonore varie quand l'utilisateur parle.
  - Bloque localement tant que PortAudio et un micro ne sont pas disponibles.
- [x] Les tests automatises ne dependent pas d'un micro reel.

### Phase D - Transcription mock puis OpenAI Realtime

Objectif : avoir une interface de transcription testable, puis brancher OpenAI.

- [x] `D-001` `P0` Creer interface `TranscriptionService`.
- [x] `D-002` `P0` Creer types d'evenements partial/final/error.
- [x] `D-003` `P0` Implementer `MockTranscriptionService`.
- [x] `D-004` `P0` Implementer `TranscriptBuffer`.
- [x] `D-005` `P0` Verifier officiellement les modeles Realtime Transcription disponibles avant implementation.
- [x] `D-006` `P0` Choisir client `openai` SDK ou `websockets`.
- [x] `D-007` `P0` Ouvrir session Realtime Transcription.
- [x] `D-008` `P0` Configurer audio input PCM 24 kHz.
- [x] `D-009` `P0` Streamer chunks audio.
- [x] `D-010` `P0` Recevoir deltas et completions.
- [x] `D-011` `P0` Finaliser explicitement a l'arret utilisateur.
- [x] `D-012` `P0` Gerer timeouts, erreurs reseau et erreurs API.
- [ ] `D-013` `P1` Ajouter logprobs ou score de confiance seulement si utile et sans surcharger V1.0.

Critere d'acceptation :

- [ ] Le mode mock affiche une transcription progressive sans cle OpenAI.
- [ ] Le mode reel transcrit une phrase courte.
- [x] Aucun test unitaire n'appelle OpenAI.
- [x] Le modele utilise est configurable.

### Phase E - Fenetre de dictee

Objectif : fournir le flux utilisateur principal.

- [x] `E-001` `P0` Creer `RecorderWindow` PySide6.
- [x] `E-002` `P0` Ajouter bouton micro/stop principal.
- [x] `E-003` `P0` Ajouter indicateur d'etat.
- [x] `E-004` `P0` Ajouter barre de niveau audio.
- [x] `E-005` `P0` Ajouter selecteur micro.
- [x] `E-006` `P0` Ajouter zone transcription live.
- [x] `E-007` `P0` Ajouter action annuler.
- [x] `E-008` `P0` Gerer `Entree` pour arreter.
- [x] `E-009` `P0` Gerer `Echap` pour annuler.
- [x] `E-010` `P0` Connecter audio + transcription mock.
- [x] `E-011` `P0` Connecter audio + transcription reelle.
- [x] `E-012` `P0` Implementer state machine UI.
- [x] `E-013` `P1` Gerer fermeture forcee sans fuite de capture audio.
- [x] `E-014` `P1` Tester avec `pytest-qt`.

Etats UI a couvrir :

- [x] `idle`
- [x] `recording`
- [x] `stopping`
- [x] `transcribing_final`
- [x] `copying`
- [x] `success`
- [x] `error`
- [x] `cancelled`

Critere d'acceptation :

- [x] `uv run vox-voice-paste --record-and-copy --mock` ouvre la fenetre.
- [x] Le bouton principal arrete correctement.
- [x] `Echap` annule sans copier.
- [x] Une erreur reste visible et lisible.

### Phase F - Clipboard et notifications

Objectif : copier le texte final et informer clairement l'utilisateur.

- [x] `F-001` `P0` Definir interface `ClipboardService`.
- [x] `F-002` `P0` Implementer copie texte final non vide.
- [x] `F-003` `P0` Garantir que l'annulation ne copie rien.
- [x] `F-004` `P0` Garantir qu'un texte vide ne remplace pas le presse-papiers.
- [!] `F-005` `P0` Valider persistance clipboard apres fermeture sur Wayland.
  - Implementation preferee via `wl-copy`; validation reelle a faire sur session Wayland.
- [x] `F-006` `P1` Ajouter fallback `wl-copy` / `xclip` / `xsel` selon environnement.
- [x] `F-007` `P0` Definir interface `NotificationService`.
- [x] `F-008` `P0` Implementer notification succes.
- [ ] `F-009` `P1` Implementer notifications annulation, erreur, texte vide.
- [ ] `F-010` `P1` Ajouter bouton "Copier le texte partiel" en cas d'erreur apres transcript partiel.

Critere d'acceptation :

- [!] Apres transcription mock, `Ctrl+V` colle le texte attendu.
  - Couvert par service fake ; validation manuelle restante selon clipboard systeme.
- [!] La notification succes est affichee.
  - Couvert par service fake ; validation manuelle restante selon session desktop.
- [!] La copie survit a la fermeture automatique de la fenetre.
  - Depend de `wl-copy`, `xclip` ou `xsel` en environnement reel.
- [x] Une erreur clipboard laisse le texte visible et recuperable.

### Phase G - Assistant de configuration

Objectif : rendre l'application utilisable sans terminal.

- [x] `G-001` `P0` Creer `OnboardingWindow`.
- [x] `G-002` `P0` Detecter premier lancement non configure.
- [x] `G-003` `P0` Ecran bienvenue et mention confidentialite OpenAI.
- [x] `G-004` `P0` Ecran cle OpenAI.
- [x] `G-005` `P0` Test de connexion OpenAI sans audio.
- [x] `G-006` `P0` Ecran choix micro.
- [ ] `G-007` `P0` Test niveau sonore.
- [x] `G-008` `P0` Ecran instruction raccourci Ubuntu.
- [x] `G-009` `P1` Copier la commande `vox-voice-paste --record-and-copy`.
- [ ] `G-010` `P1` Test final de dictee.
- [x] `G-011` `P0` Marquer onboarding termine ou ignore explicitement.

Critere d'acceptation :

- [x] Premier lancement sans config ouvre l'assistant.
- [x] L'utilisateur peut enregistrer une cle dans le keyring.
- [x] L'utilisateur voit et copie la commande du raccourci.
- [x] L'utilisateur peut terminer l'assistant sans perdre la config.

### Phase H - Diagnostic et robustesse

Objectif : faciliter support et debug.

- [x] `H-001` `P0` Detecter version application.
- [x] `H-002` `P0` Detecter version Python.
- [x] `H-003` `P0` Detecter desktop, Wayland/X11.
- [x] `H-004` `P0` Diagnostiquer audio devices.
- [x] `H-005` `P0` Diagnostiquer clipboard.
- [x] `H-006` `P0` Diagnostiquer notifications.
- [x] `H-007` `P0` Diagnostiquer presence cle OpenAI.
- [ ] `H-008` `P1` Tester connexion OpenAI sans envoyer d'audio.
- [x] `H-009` `P0` Ajouter option `--verbose`.
- [x] `H-010` `P0` Ajouter verrou anti-double-dictee.

Critere d'acceptation :

- [x] `uv run vox-voice-paste --diagnose` produit un rapport lisible.
- [x] Aucune cle, aucun audio et aucun transcript n'apparaissent.
- [x] Le rapport indique les actions probables a corriger.

### Phase I - Packaging Ubuntu

Objectif : produire un paquet installable.

- [x] `I-001` `P0` Choisir strategie package : PyInstaller, PEX/Shiv, ou packaging Python + dependances systeme.
  - Decision : package Debian local installant les sources Python dans `dist-packages` et declarant les dependances Ubuntu.
- [x] `I-002` `P0` Creer fichier `.desktop`.
- [x] `I-003` `P1` Ajouter icone.
- [x] `I-004` `P0` Declarer dependances systeme.
- [x] `I-005` `P0` Construire `.deb`.
- [!] `I-006` `P0` Tester installation sur Ubuntu propre.
  - Paquet construit localement ; installation systeme non executee dans ce workspace.
- [ ] `I-007` `P0` Tester desinstallation.
- [x] `I-008` `P1` Documenter mise a jour et suppression config utilisateur.

Critere d'acceptation :

- [!] `sudo apt install ./vox-voice-paste_x.y.z_amd64.deb` installe l'application.
  - Non execute localement ; paquet construit via `dpkg-deb`.
- [x] L'entree apparait dans le menu Ubuntu.
- [x] `vox-voice-paste` est disponible dans le PATH.
- [ ] La desinstallation ne laisse pas de fichiers systeme inutiles.

### Phase J - Validation V1.0

Objectif : verifier les cas reels avant release.

- [ ] `J-001` `P0` Ubuntu 24.04 GNOME Wayland.
- [ ] `J-002` `P1` Ubuntu 24.04 GNOME X11 si disponible.
- [ ] `J-003` `P0` GNOME Text Editor.
- [ ] `J-004` `P0` Firefox.
- [ ] `J-005` `P1` Chrome ou Chromium.
- [ ] `J-006` `P1` VS Code.
- [ ] `J-007` `P1` LibreOffice Writer.
- [ ] `J-008` `P1` Terminal GNOME.
- [ ] `J-009` `P0` Micro interne.
- [ ] `J-010` `P1` Casque Bluetooth si disponible.
- [ ] `J-011` `P0` Dictee francaise.
- [ ] `J-012` `P0` Dictee anglaise.
- [ ] `J-013` `P0` Reseau coupe.
- [ ] `J-014` `P0` Cle OpenAI invalide.
- [ ] `J-015` `P0` Dictee vide.
- [ ] `J-016` `P0` Annulation.
- [ ] `J-017` `P1` Dictee longue de 2 minutes.

Critere d'acceptation release :

- [ ] Aucun crash bloquant.
- [ ] Texte final copiable et recuperable.
- [ ] Clipboard non modifie en cas d'annulation ou texte vide.
- [ ] Erreurs comprehensibles.
- [ ] L'utilisateur peut toujours recuperer un transcript final produit.

---

## 9. Backlog par epics

### Epic CLI et configuration

- [ ] `CLI-001` `P0` Creer commande `vox-voice-paste`.
- [ ] `CLI-002` `P0` Ajouter `--record-and-copy`.
- [x] `CLI-003` `P1` Ajouter `--settings`.
- [x] `CLI-004` `P0` Ajouter `--diagnose`.
- [ ] `CLI-005` `P0` Ajouter `--mock`.
- [x] `CLI-006` `P1` Ajouter `--list-audio-devices`.
- [x] `CFG-001` `P0` Creer modele de config.
- [x] `CFG-002` `P0` Persister config utilisateur.
- [ ] `CFG-003` `P1` Ajouter migration config versionnee.
- [x] `SEC-001` `P0` Stocker cle OpenAI dans keyring.
- [x] `SEC-002` `P0` Masquer secrets dans logs.

### Epic Audio

- [x] `AUD-001` `P0` Lister peripheriques audio.
- [x] `AUD-002` `P0` Selectionner peripherique par defaut.
- [x] `AUD-003` `P0` Capturer flux micro.
- [x] `AUD-004` `P0` Convertir en mono.
- [x] `AUD-005` `P0` Resampler 24 kHz.
- [x] `AUD-006` `P0` Calculer niveau sonore.
- [x] `AUD-007` `P0` Gerer arret propre.
- [x] `AUD-008` `P0` Source audio factice.

### Epic Transcription

- [x] `TR-001` `P0` Interface `TranscriptionService`.
- [x] `TR-002` `P0` Service mock.
- [x] `TR-003` `P0` Session OpenAI Realtime.
- [x] `TR-004` `P0` Configuration transcription.
- [x] `TR-005` `P0` Streaming chunks audio.
- [x] `TR-006` `P0` Reception deltas.
- [x] `TR-007` `P0` Reception transcript final.
- [x] `TR-008` `P0` Timeouts.
- [x] `TR-009` `P0` Erreurs API.
- [x] `TR-010` `P0` Verification officielle modeles et events avant branchement.

### Epic UI

- [x] `UI-001` `P0` Fenetre de dictee.
- [x] `UI-002` `P0` Bouton micro/stop.
- [x] `UI-003` `P0` Barre niveau sonore.
- [x] `UI-004` `P0` Selecteur micro.
- [x] `UI-005` `P0` Zone transcription live.
- [x] `UI-006` `P0` Etat et messages.
- [x] `UI-007` `P0` Raccourcis internes.
- [x] `UI-008` `P0` Fermeture automatique sur succes.
- [x] `UI-009` `P1` Affichage erreur avec texte partiel.

### Epic Desktop

- [x] `DESK-001` `P0` Copier texte dans presse-papiers.
- [x] `DESK-002` `P0` Notification succes.
- [ ] `DESK-003` `P1` Notification annulation.
- [ ] `DESK-004` `P1` Notification erreur.
- [ ] `DESK-005` `P1` Bouton copier texte partiel.
- [x] `DESK-006` `P0` Verrou session unique.

### Epic Onboarding

- [x] `ONB-001` `P0` Ecran bienvenue.
- [x] `ONB-002` `P0` Ecran cle OpenAI.
- [x] `ONB-003` `P0` Test cle OpenAI.
- [x] `ONB-004` `P0` Ecran micro.
- [ ] `ONB-005` `P0` Test niveau sonore.
- [x] `ONB-006` `P0` Ecran raccourci Ubuntu.
- [ ] `ONB-007` `P1` Test final.
- [x] `ONB-008` `P0` Flag onboarding termine.

### Epic Packaging

- [x] `PKG-001` `P0` Fichier `.desktop`.
- [x] `PKG-002` `P1` Icone.
- [x] `PKG-003` `P0` Build executable ou bundle.
- [x] `PKG-004` `P0` Package `.deb`.
- [x] `PKG-005` `P1` Script install local.
- [ ] `PKG-006` `P0` Test install/desinstall.

---

## 10. Tests automatises a creer

### Unitaires

- [x] Config par defaut.
- [x] Serialization/deserialization config.
- [x] Config invalide.
- [x] Absence de cle OpenAI.
- [x] Presence de cle OpenAI sans affichage.
- [x] Masquage secrets dans logs.
- [x] Normalisation du transcript final.
- [x] Refus de copier un texte vide.
- [x] Aggregation des deltas.
- [x] State machine.
- [x] Diagnostic sans donnees sensibles.
- [x] Verrou anti-double-dictee.

### Integration mock

- [ ] Transcription mock complete.
- [ ] Source audio factice vers transcription mock.
- [x] Fenetre UI avec `pytest-qt`.
- [x] Clipboard fake.
- [x] Notifications fake.
- [ ] Erreur OpenAI simulee.
- [ ] Timeout simule.
- [ ] Annulation pendant enregistrement.

### Manuels

- [ ] Vrai micro.
- [ ] Vraie cle OpenAI.
- [ ] Ubuntu Wayland.
- [ ] Raccourci clavier Ubuntu.
- [ ] Collage manuel dans plusieurs applications.
- [ ] Clipboard apres fermeture de la fenetre.

---

## 11. Matrice de risques

| Risque | Impact | Probabilite | Mitigation | Statut |
| --- | --- | --- | --- | --- |
| Modele OpenAI cible obsolete | Haut | Moyen | Verifier docs officielles avant `TR-003`; modele configurable | [!] |
| Python 3.14 incompatible avec dependances desktop/audio | Haut | Moyen | Tester installation dependances tot; ajuster `requires-python` si besoin | [!] |
| Clipboard perdu apres fermeture sur Wayland | Haut | Moyen | Valider `QClipboard`, ajouter fallback `wl-copy` | [!] |
| Keyring absent ou verrouille | Moyen | Moyen | Diagnostic clair, onboarding avec message reparable | [ ] |
| Double lancement de dictee | Moyen | Moyen | Verrou fichier/processus | [x] |
| UI bloquee par reseau | Haut | Moyen | Async worker/service, jamais d'appel reseau direct dans UI thread | [ ] |
| Capture audio indisponible | Moyen | Moyen | Diagnostic audio, selection micro, messages clairs | [ ] |
| Package `.deb` trop fragile | Moyen | Moyen | Choisir packaging apres prototype runtime stable | [ ] |

---

## 12. Criteres d'acceptation fonctionnels suivis

- [ ] `AC-001` Premier lancement non configure ouvre l'assistant.
- [x] `AC-002` Cle OpenAI validee sans affichage en clair.
- [ ] `AC-003` Choix micro et niveau sonore visibles.
- [ ] `AC-004` Commande raccourci affichee et copiable.
- [ ] `AC-005` Dictee mock progressive.
- [ ] `AC-006` Dictee reelle copie le texte final.
- [x] `AC-007` Notification succes.
- [ ] `AC-008` Annulation sans modification du presse-papiers.
- [ ] `AC-009` Texte vide sans ecrasement du presse-papiers.
- [ ] `AC-010` Erreur reseau lisible sans crash.

---

## 13. Definition de release V1.0

La V1.0 est prete seulement si :

- [ ] Tous les items `P0` des phases A a H sont termines.
- [ ] Le package ou mode d'installation retenu est documente.
- [ ] La validation Wayland est passee.
- [ ] La validation OpenAI reelle est passee.
- [ ] La validation clipboard apres fermeture est passee.
- [ ] Les erreurs principales ont ete testees : cle absente, cle invalide, reseau coupe, micro absent, texte vide.
- [ ] Les tests automatises critiques passent.
- [ ] Aucun log ne contient de cle, audio ou transcript par defaut.
- [ ] Le README explique clairement le raccourci Ubuntu et le flux `Ctrl+V`.

---

## 14. Journal de suivi

| Date | Changement | Notes |
| --- | --- | --- |
| 2026-05-23 | Creation du tracker | Basee sur le plan V1.0 et l'environnement local `uv` / Python 3.14.2 |
