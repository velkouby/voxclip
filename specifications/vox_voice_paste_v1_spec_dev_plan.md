# VoxClip — Spécification fonctionnelle et plan de développement V1.0

Version : 1.0  
Date : 2026-05-23  
Cible : Ubuntu desktop, prioritairement GNOME / Wayland  
Statut : document de cadrage pour agent de développement

---

## 1. Résumé exécutif

VoxClip V1.0 est une application desktop Ubuntu permettant de dicter du texte depuis n’importe quel contexte d’édition, puis de copier automatiquement la transcription finale dans le presse-papiers.

Le déclenchement se fait via un raccourci clavier global configuré par l’utilisateur dans Ubuntu, par exemple `Ctrl+Alt+V`. Une petite fenêtre de dictée s’ouvre, l’enregistrement démarre immédiatement, l’utilisateur parle, puis arrête l’enregistrement. L’application affiche la transcription en direct, récupère le texte final via l’API OpenAI Realtime Transcription, copie ce texte dans le presse-papiers et affiche une notification indiquant que le texte est prêt à être collé.

La V1.0 ne tente pas de coller automatiquement dans l’application active. Ce choix est volontaire : sous Ubuntu moderne, en particulier GNOME / Wayland, l’injection clavier universelle est fragile et nécessite des mécanismes système plus intrusifs. La V1.0 privilégie donc la fiabilité, la simplicité d’installation et l’absence de perte de texte.

---

## 2. Objectifs produit

### 2.1 Objectif principal

Permettre à l’utilisateur de produire rapidement du texte par dictée vocale depuis n’importe quel champ texte, avec un flux simple :

```text
Utilisateur dans un champ texte
→ raccourci clavier global
→ mini fenêtre de dictée
→ transcription live
→ arrêt manuel
→ texte copié dans le presse-papiers
→ notification
→ l’utilisateur colle avec Ctrl+V
```

### 2.2 Principes de conception

La V1.0 doit respecter les principes suivants :

- fiabilité avant automatisation ;
- aucune perte silencieuse de transcription ;
- expérience utilisateur courte et prévisible ;
- installation simple sur Ubuntu ;
- pas de dépendance à un hack Wayland pour cette version ;
- stockage sécurisé de la clé OpenAI ;
- pas d’historique local des transcriptions par défaut ;
- pas d’enregistrement audio persistant sur disque ;
- code modulaire pour préparer une V1.1 avec collage automatique.

### 2.3 Ce que la V1.0 doit absolument réussir

- L’utilisateur déclenche la dictée par une commande système utilisable dans un raccourci Ubuntu.
- La mini fenêtre s’ouvre rapidement.
- L’enregistrement démarre automatiquement à l’ouverture.
- Le niveau sonore du micro est visible.
- L’utilisateur peut choisir son périphérique d’entrée audio.
- La transcription apparaît progressivement.
- À l’arrêt, le texte final est copié dans le presse-papiers.
- L’utilisateur reçoit une notification claire : “Texte copié. Faites Ctrl+V pour coller.”
- Si une erreur survient, l’utilisateur comprend ce qui s’est passé.

---

## 3. Hors périmètre V1.0

Les éléments suivants ne doivent pas être implémentés dans la V1.0 :

- collage automatique via simulation de `Ctrl+V` ;
- intégration dans le menu clic droit des applications ;
- extension navigateur ;
- moteur IBus ;
- mode correction / reformulation par LLM ;
- historique local des dictées ;
- synchronisation cloud ;
- multi-utilisateur ;
- application mobile ;
- gestion d’un compte SaaS ;
- proxy backend propriétaire ;
- support officiel autre qu’Ubuntu desktop récent.

Ces sujets peuvent être préparés architecturalement, mais ne doivent pas alourdir la V1.0.

---

## 4. Utilisateurs cibles

### 4.1 Utilisateur principal

Utilisateur Ubuntu qui travaille souvent dans des éditeurs de texte, navigateurs, IDE, outils bureautiques ou formulaires web, et souhaite dicter rapidement du texte.

### 4.2 Hypothèses utilisateur

L’utilisateur :

- sait configurer un raccourci clavier si l’application le guide ;
- possède une clé API OpenAI ;
- utilise Ubuntu avec GNOME ou environnement compatible ;
- accepte de faire `Ctrl+V` manuellement après la transcription en V1.0 ;
- veut une application simple plutôt qu’un outil technique à lancer depuis le terminal.

---

## 5. Parcours utilisateur

### 5.1 Premier lancement

1. L’utilisateur installe le package.
2. Il lance “VoxClip” depuis le menu Ubuntu.
3. L’assistant de configuration s’ouvre.
4. Il saisit sa clé OpenAI.
5. L’application teste la clé.
6. Il choisit son micro par défaut.
7. Il teste le niveau sonore.
8. L’application affiche la commande à configurer dans les raccourcis Ubuntu :

```bash
voxclip --record-and-copy
```

9. L’utilisateur configure un raccourci personnalisé Ubuntu, par exemple `Ctrl+Alt+V`.
10. L’assistant propose un test de dictée.
11. À la fin du test, le texte est copié dans le presse-papiers.
12. Une notification confirme que le texte est prêt à coller.

### 5.2 Usage quotidien

1. L’utilisateur place son curseur dans un champ texte.
2. Il déclenche le raccourci global.
3. La fenêtre de dictée s’ouvre.
4. L’enregistrement démarre immédiatement.
5. L’utilisateur parle.
6. La transcription partielle s’affiche.
7. L’utilisateur clique sur le bouton rouge ou appuie sur `Entrée` pour arrêter.
8. L’application attend le transcript final.
9. L’application copie le texte final dans le presse-papiers.
10. La fenêtre se ferme.
11. Une notification indique : “Texte copié. Faites Ctrl+V pour coller.”
12. L’utilisateur colle le texte dans l’application cible.

### 5.3 Annulation

1. L’utilisateur déclenche la fenêtre de dictée.
2. Il appuie sur `Échap` ou clique sur “Annuler”.
3. L’enregistrement s’arrête.
4. Aucun texte n’est copié.
5. La fenêtre se ferme.
6. Notification optionnelle : “Dictée annulée.”

### 5.4 Erreur réseau ou OpenAI

1. L’utilisateur parle.
2. La connexion OpenAI échoue ou expire.
3. L’application arrête l’enregistrement proprement.
4. La fenêtre affiche une erreur lisible.
5. Aucun texte vide ou partiel non validé n’écrase le presse-papiers sans confirmation.
6. L’utilisateur peut copier manuellement une transcription partielle si elle existe.

---

## 6. Spécification fonctionnelle détaillée

### 6.1 Commandes installées

L’installation doit fournir au minimum deux commandes :

```bash
voxclip
voxclip --record-and-copy
```

`voxclip` ouvre l’application principale ou l’écran de configuration.

`voxclip --record-and-copy` lance directement la mini fenêtre de dictée, démarre l’enregistrement et copie le texte final dans le presse-papiers. C’est cette commande qui doit être utilisée dans le raccourci clavier Ubuntu.

Commandes optionnelles utiles pour le debug :

```bash
voxclip --settings
voxclip --list-audio-devices
voxclip --diagnose
```

### 6.2 Assistant de configuration

L’assistant doit être affiché au premier lancement si la configuration minimale n’existe pas.

Configuration minimale :

- clé OpenAI présente dans le keyring ;
- micro par défaut sélectionné ou fallback système disponible ;
- onboarding terminé ou ignoré explicitement.

Écrans recommandés :

1. Bienvenue
2. Configuration de la clé OpenAI
3. Test de connexion OpenAI
4. Choix du micro
5. Test audio
6. Configuration du raccourci Ubuntu
7. Test final
8. Fin

### 6.3 Fenêtre de dictée

La fenêtre doit être petite, non intrusive et centrée ou positionnée près du centre de l’écran.

Composants visibles :

- titre : “VoxClip” ;
- bouton principal rouge avec icône micro ;
- indicateur d’état ;
- barre de niveau sonore ;
- sélecteur de micro ;
- zone de transcription live ;
- bouton “Annuler” ;
- aide courte : “Entrée pour arrêter, Échap pour annuler”.

États UI :

```text
idle
recording
stopping
transcribing_final
copying
success
error
cancelled
```

Comportements :

- à l’ouverture via `--record-and-copy`, l’état passe directement à `recording` ;
- pendant `recording`, le bouton rouge signifie “Arrêter” ;
- pendant `stopping` et `transcribing_final`, les contrôles sont désactivés sauf annulation forcée ;
- à `success`, le texte est copié, la notification est envoyée et la fenêtre se ferme ;
- à `error`, la fenêtre reste ouverte pour permettre à l’utilisateur de lire l’erreur et de copier un éventuel texte partiel.

### 6.4 Raccourcis clavier internes

Dans la fenêtre :

- `Entrée` : arrêter l’enregistrement et finaliser ;
- `Échap` : annuler ;
- `Ctrl+C` dans la zone de texte : copier la sélection ;
- `Ctrl+A` dans la zone de texte : sélectionner toute la transcription.

Le raccourci global n’est pas géré directement par l’application en V1.0. Il est configuré dans Ubuntu comme raccourci personnalisé exécutant `voxclip --record-and-copy`.

### 6.5 Transcription live

L’application doit utiliser l’API OpenAI Realtime Transcription avec un modèle de transcription live.

Configuration cible :

- modèle : `gpt-realtime-whisper` ;
- format audio : PCM mono 24 kHz ;
- transcription en streaming ;
- langue par défaut : `auto`, avec possibilité de forcer `fr` ou `en`.

L’application doit afficher les deltas ou segments partiels reçus. Le texte affiché peut être instable pendant la dictée. Le texte final reçu à la fin de session fait foi.

### 6.6 Gestion de l’audio

Exigences :

- détecter les périphériques d’entrée audio disponibles ;
- proposer le périphérique système par défaut ;
- permettre de sélectionner un autre micro ;
- mémoriser le choix de l’utilisateur ;
- afficher un niveau sonore simple ;
- ne pas écrire l’audio sur disque ;
- envoyer l’audio par chunks courts à l’API ;
- gérer proprement les périphériques indisponibles.

Le pipeline audio doit convertir ou resampler vers le format attendu par l’API si nécessaire.

### 6.7 Presse-papiers

À la fin d’une transcription réussie :

- nettoyer le texte final ;
- copier le texte dans le presse-papiers ;
- afficher une notification.

Règles :

- ne pas écraser le presse-papiers si la dictée est annulée ;
- ne pas écraser le presse-papiers si aucun texte final utilisable n’est produit ;
- en cas de texte partiel après erreur, demander confirmation ou proposer un bouton “Copier le texte partiel” ;
- conserver les retours ligne produits par la transcription ;
- normaliser les espaces de début et fin.

### 6.8 Notifications

Notifications attendues :

- succès : “Texte copié. Faites Ctrl+V pour coller.”
- annulation : “Dictée annulée.”
- erreur OpenAI : “Transcription impossible. Vérifiez votre connexion ou votre clé OpenAI.”
- erreur micro : “Aucun micro disponible ou autorisé.”
- texte vide : “Aucun texte détecté.”

L’implémentation peut utiliser DBus `org.freedesktop.Notifications`, `notify-send`, ou une abstraction remplaçable.

### 6.9 Paramètres

Paramètres utilisateur V1.0 :

```yaml
audio:
  input_device_id: null
  sample_rate: 24000
transcription:
  model: gpt-realtime-whisper
  language: auto
  latency: low
clipboard:
  copy_on_success: true
ui:
  close_on_success: true
  show_live_transcript: true
  always_on_top: true
privacy:
  save_history: false
  log_transcripts: false
```

La clé OpenAI ne doit pas être stockée dans ce fichier. Elle doit être stockée dans le keyring système.

### 6.10 Diagnostic

La commande `voxclip --diagnose` doit vérifier :

- version de l’application ;
- version Python / runtime ;
- environnement desktop détecté ;
- Wayland ou X11 ;
- disponibilité du presse-papiers ;
- disponibilité des notifications ;
- périphériques audio détectés ;
- présence de la clé OpenAI dans le keyring ;
- test réseau simple vers OpenAI, sans envoyer d’audio ;
- permissions micro si détectables.

La commande ne doit pas afficher la clé OpenAI.

---

## 7. Exigences non fonctionnelles

### 7.1 Performance

Objectifs indicatifs :

- ouverture de la fenêtre : < 1 seconde après lancement à chaud ;
- début de capture audio : < 500 ms après ouverture ;
- latence perçue des premiers textes partiels : aussi basse que possible, à valider empiriquement ;
- finalisation après arrêt : idéalement < 3 secondes pour une dictée courte.

### 7.2 Fiabilité

L’application doit :

- éviter les crashs non capturés ;
- afficher les erreurs de façon lisible ;
- ne jamais perdre silencieusement une transcription finalisée ;
- ne jamais copier un texte vide sans le signaler ;
- gérer les timeouts réseau ;
- gérer la fermeture forcée de la fenêtre ;
- gérer un deuxième lancement alors qu’une dictée est déjà en cours.

### 7.3 Sécurité et confidentialité

Exigences :

- clé OpenAI stockée dans Secret Service / keyring, pas dans un fichier texte ;
- pas d’enregistrement audio persistant ;
- pas d’historique local par défaut ;
- pas de log contenant l’audio ;
- pas de log contenant les transcriptions par défaut ;
- logs techniques limités aux événements, erreurs et timings ;
- message clair indiquant que l’audio est envoyé à OpenAI pour transcription.

### 7.4 Maintenabilité

Le code doit être modulaire :

- UI indépendante du client OpenAI ;
- service de transcription abstrait ;
- capture audio testable avec source audio factice ;
- presse-papiers abstrait ;
- notifications abstraites ;
- configuration centralisée ;
- tests unitaires possibles sans micro réel et sans appel OpenAI réel.

---

## 8. Architecture technique proposée

### 8.1 Stack recommandée

Langage :

```text
Python 3.11+
```

UI :

```text
PySide6
```

Audio :

```text
sounddevice
numpy
```

Transcription :

```text
websockets ou SDK OpenAI si le support Realtime Transcription est suffisamment stable
```

Configuration :

```text
platformdirs
pydantic
PyYAML ou tomllib/tomli-w selon format choisi
```

Secrets :

```text
keyring
```

Notifications :

```text
DBus org.freedesktop.Notifications
fallback notify-send si disponible
```

Packaging :

```text
PyInstaller ou PEX/Shiv pour isoler le runtime
.deb pour Ubuntu
```

Tests :

```text
pytest
pytest-qt
serveur WebSocket mock selon implémentation
```

### 8.2 Structure de dépôt recommandée

```text
voxclip/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── LICENSE
├── docs/
│   ├── functional-spec-v1.md
│   ├── install.md
│   └── troubleshooting.md
├── packaging/
│   ├── debian/
│   ├── desktop/
│   │   └── voxclip.desktop
│   └── icons/
├── src/
│   └── vox_voice_paste/
│       ├── __init__.py
│       ├── main.py
│       ├── cli.py
│       ├── app.py
│       ├── config.py
│       ├── logging_config.py
│       ├── audio/
│       │   ├── __init__.py
│       │   ├── capture.py
│       │   ├── devices.py
│       │   ├── level_meter.py
│       │   └── resample.py
│       ├── transcription/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── openai_realtime.py
│       │   └── transcript_buffer.py
│       ├── desktop/
│       │   ├── __init__.py
│       │   ├── clipboard.py
│       │   ├── notifications.py
│       │   ├── environment.py
│       │   └── diagnostics.py
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── recorder_window.py
│       │   ├── settings_window.py
│       │   ├── onboarding_window.py
│       │   └── widgets.py
│       └── security/
│           ├── __init__.py
│           └── secrets.py
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

### 8.3 Interfaces internes recommandées

#### Transcription service

```python
class TranscriptionService:
    """Streams audio chunks and emits partial/final transcription events."""

    async def start(self) -> None:
        ...

    async def send_audio_chunk(self, pcm_chunk: bytes) -> None:
        ...

    async def stop_and_finalize(self) -> str:
        ...

    async def cancel(self) -> None:
        ...
```

#### Audio capture

```python
class AudioCapture:
    """Captures microphone audio and yields PCM chunks."""

    def list_devices(self) -> list[AudioDevice]:
        ...

    async def start(self, device_id: str | None) -> None:
        ...

    async def read_chunks(self):
        ...

    async def stop(self) -> None:
        ...
```

#### Clipboard service

```python
class ClipboardService:
    """Writes text to the desktop clipboard."""

    def copy_text(self, text: str) -> None:
        ...
```

#### Notification service

```python
class NotificationService:
    """Sends desktop notifications."""

    def notify(self, title: str, message: str) -> None:
        ...
```

### 8.4 State machine

```text
not_configured
configured
launching
recording
stopping
waiting_final_transcript
copying_to_clipboard
success
error
cancelled
```

Transitions principales :

```text
configured → launching
launching → recording
recording → stopping
stopping → waiting_final_transcript
waiting_final_transcript → copying_to_clipboard
copying_to_clipboard → success
recording → cancelled
any_active_state → error
```

L’état `success` ferme automatiquement la fenêtre si `ui.close_on_success = true`.

---

## 9. Détails OpenAI Realtime Transcription

L’implémentation doit être isolée dans `transcription/openai_realtime.py`.

Contraintes :

- ne pas disperser les appels OpenAI dans l’UI ;
- supporter un mode mock pour les tests ;
- exposer des événements partiels/finalisés ;
- gérer les erreurs réseau ;
- gérer l’expiration de session ;
- gérer l’arrêt manuel de l’enregistrement.

Configuration de session cible, à adapter selon la version exacte de l’API :

```json
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": {
      "input": {
        "format": {
          "type": "audio/pcm",
          "rate": 24000
        },
        "transcription": {
          "model": "gpt-realtime-whisper",
          "language": "fr"
        }
      }
    }
  }
}
```

Règles :

- si `language = auto`, ne pas envoyer de hint langue si l’API le permet ;
- si `language = fr`, envoyer le hint `fr` ;
- prévoir un paramètre `delay` ou `latency` si l’API le supporte ;
- finaliser explicitement à l’arrêt utilisateur ;
- concaténer proprement les deltas ;
- remplacer le texte partiel par le texte final quand il arrive.

---

## 10. Plan de développement complet

### Phase A — Initialisation projet

Objectif : créer un squelette propre, testable et packagé.

Tâches :

1. Créer le dépôt.
2. Créer `pyproject.toml`.
3. Configurer Python 3.11+.
4. Ajouter dépendances de base.
5. Mettre en place `src/vox_voice_paste`.
6. Ajouter `pytest`.
7. Ajouter formatage et lint si souhaité.
8. Ajouter une commande CLI minimale.
9. Ajouter logs structurés simples.
10. Ajouter README initial.

Critères d’acceptation :

- `python -m vox_voice_paste --help` fonctionne ;
- `voxclip --help` fonctionne après installation locale ;
- les tests de base passent ;
- la structure de modules correspond au document.

### Phase B — Configuration et secrets

Objectif : gérer la configuration utilisateur et la clé OpenAI.

Tâches :

1. Implémenter le modèle de configuration.
2. Stocker le fichier de configuration dans le répertoire utilisateur standard.
3. Implémenter lecture/écriture atomique de la config.
4. Implémenter `SecretService` avec `keyring`.
5. Ajouter commande CLI pour définir la clé OpenAI en dev.
6. Ajouter masquage de la clé dans tous les logs.
7. Tester les cas : clé absente, clé présente, erreur keyring.

Critères d’acceptation :

- la clé n’est jamais écrite dans le fichier de config ;
- `voxclip --diagnose` détecte si une clé est présente sans l’afficher ;
- tests unitaires couvrent config et secrets.

### Phase C — Audio devices et capture

Objectif : lister les micros, enregistrer et produire des chunks PCM.

Tâches :

1. Implémenter `list_audio_devices`.
2. Identifier le micro par défaut.
3. Implémenter capture audio avec `sounddevice`.
4. Convertir en mono si nécessaire.
5. Resampler vers 24 kHz si nécessaire.
6. Produire des chunks bytes PCM.
7. Calculer un niveau RMS simple pour l’UI.
8. Gérer arrêt propre.
9. Ajouter source audio factice pour tests.

Critères d’acceptation :

- `voxclip --list-audio-devices` affiche les entrées audio ;
- un test local peut capturer 3 secondes d’audio sans écrire sur disque ;
- les chunks produits sont au format attendu ;
- le niveau sonore varie quand l’utilisateur parle.

### Phase D — Client OpenAI Realtime mockable

Objectif : connecter le pipeline audio à OpenAI Realtime Transcription.

Tâches :

1. Créer `TranscriptionService` abstrait.
2. Implémenter `OpenAIRealtimeTranscriptionService`.
3. Ouvrir une session WebSocket / Realtime.
4. Envoyer la configuration de session.
5. Envoyer les chunks audio.
6. Recevoir les deltas de transcription.
7. Recevoir le texte final.
8. Gérer l’arrêt manuel.
9. Gérer timeouts et erreurs.
10. Ajouter un `MockTranscriptionService` pour l’UI et les tests.

Critères d’acceptation :

- le mode mock affiche une transcription progressive sans OpenAI ;
- le mode réel transcrit une phrase courte ;
- les erreurs réseau sont converties en erreurs applicatives lisibles ;
- aucun appel OpenAI n’est effectué dans les tests unitaires.

### Phase E — Fenêtre de dictée

Objectif : fournir l’expérience utilisateur principale.

Tâches :

1. Créer fenêtre PySide6.
2. Ajouter bouton micro rouge.
3. Ajouter niveau audio.
4. Ajouter sélecteur de micro.
5. Ajouter zone de transcription live.
6. Ajouter bouton Annuler.
7. Gérer `Entrée` pour arrêter.
8. Gérer `Échap` pour annuler.
9. Connecter audio capture + transcription service.
10. Gérer les états UI.
11. Fermer automatiquement sur succès.

Critères d’acceptation :

- `voxclip --record-and-copy --mock` ouvre la fenêtre et simule une transcription ;
- le bouton rouge démarre/arrête correctement ;
- `Échap` annule sans copier ;
- les états sont visibles et cohérents ;
- les erreurs restent lisibles.

### Phase F — Clipboard et notifications

Objectif : copier le texte final et notifier l’utilisateur.

Tâches :

1. Implémenter `ClipboardService`.
2. Copier le texte final dans le presse-papiers.
3. Implémenter `NotificationService`.
4. Envoyer notification de succès.
5. Envoyer notifications d’erreur.
6. Gérer erreur clipboard.
7. Ajouter bouton “Copier le texte partiel” en cas d’erreur après transcription partielle.

Critères d’acceptation :

- après transcription mock, le texte est disponible avec `Ctrl+V` ;
- la notification de succès est affichée ;
- aucun texte n’est copié en cas d’annulation ;
- une transcription vide ne remplace pas le presse-papiers.

### Phase G — Assistant de configuration

Objectif : rendre l’installation utilisable par un non-développeur.

Tâches :

1. Créer `OnboardingWindow`.
2. Écran clé OpenAI.
3. Test de connexion.
4. Écran choix micro.
5. Test de niveau sonore.
6. Écran instruction raccourci Ubuntu.
7. Copier la commande du raccourci dans le presse-papiers.
8. Test final de dictée en mode réel ou mock.
9. Marquer onboarding terminé.

Critères d’acceptation :

- premier lancement sans config ouvre l’assistant ;
- l’utilisateur peut configurer la clé ;
- l’utilisateur peut choisir le micro ;
- l’assistant explique clairement comment créer le raccourci Ubuntu ;
- l’utilisateur peut copier `voxclip --record-and-copy`.

### Phase H — Diagnostic et robustesse

Objectif : faciliter support et debug.

Tâches :

1. Implémenter détection environnement Wayland/X11.
2. Implémenter diagnostic audio.
3. Implémenter diagnostic clipboard.
4. Implémenter diagnostic notifications.
5. Implémenter diagnostic OpenAI key.
6. Produire un rapport texte.
7. Ajouter option `--verbose`.

Critères d’acceptation :

- `voxclip --diagnose` produit un rapport exploitable ;
- aucune donnée sensible n’apparaît ;
- le diagnostic indique les problèmes probables.

### Phase I — Packaging Ubuntu `.deb`

Objectif : fournir un package installable.

Tâches :

1. Choisir stratégie de bundle Python.
2. Construire l’exécutable ou environnement embarqué.
3. Créer fichier `.desktop`.
4. Ajouter icône.
5. Préparer structure Debian.
6. Déclarer dépendances système nécessaires.
7. Générer `.deb`.
8. Tester installation sur Ubuntu propre.
9. Tester désinstallation.

Critères d’acceptation :

- l’utilisateur installe avec `sudo apt install ./voxclip_x.y.z_amd64.deb` ;
- l’entrée apparaît dans le menu d’applications ;
- la commande `voxclip` est disponible ;
- l’assistant s’ouvre au premier lancement ;
- la désinstallation ne laisse pas de fichiers système inutiles.

### Phase J — Tests et validation manuelle

Objectif : valider la V1.0 dans des cas réels.

Tests manuels minimum :

- Ubuntu 24.04 GNOME Wayland ;
- Ubuntu 24.04 GNOME X11 si disponible ;
- éditeur GNOME Text Editor ;
- Firefox ;
- Chrome ou Chromium ;
- VS Code ;
- LibreOffice Writer ;
- terminal GNOME ;
- micro interne ;
- casque Bluetooth si disponible ;
- langue française ;
- langue anglaise ;
- réseau coupé ;
- clé OpenAI invalide ;
- dictée vide ;
- annulation ;
- dictée longue de 2 minutes.

Critères d’acceptation globaux :

- aucun crash bloquant ;
- le texte final est copié dans le presse-papiers ;
- le fallback est clair ;
- la fenêtre se ferme sur succès ;
- l’utilisateur peut toujours récupérer le texte final.

---

## 11. Backlog technique détaillé

### Epic 1 — CLI et configuration

- `CLI-001` : créer commande `voxclip`.
- `CLI-002` : ajouter argument `--record-and-copy`.
- `CLI-003` : ajouter argument `--settings`.
- `CLI-004` : ajouter argument `--diagnose`.
- `CFG-001` : créer modèle de config.
- `CFG-002` : persister config utilisateur.
- `SEC-001` : stocker clé OpenAI dans keyring.
- `SEC-002` : masquer secrets dans logs.

### Epic 2 — Audio

- `AUD-001` : lister périphériques audio.
- `AUD-002` : sélectionner périphérique par défaut.
- `AUD-003` : capturer flux micro.
- `AUD-004` : convertir en mono.
- `AUD-005` : resampler 24 kHz.
- `AUD-006` : calculer niveau sonore.
- `AUD-007` : gérer arrêt propre.

### Epic 3 — Transcription

- `TR-001` : créer interface `TranscriptionService`.
- `TR-002` : implémenter service mock.
- `TR-003` : ouvrir session OpenAI Realtime.
- `TR-004` : envoyer configuration transcription.
- `TR-005` : streamer chunks audio.
- `TR-006` : recevoir deltas.
- `TR-007` : recevoir final transcript.
- `TR-008` : gérer timeouts.
- `TR-009` : gérer erreurs API.

### Epic 4 — UI

- `UI-001` : créer fenêtre principale de dictée.
- `UI-002` : bouton rouge micro.
- `UI-003` : barre niveau sonore.
- `UI-004` : sélecteur micro.
- `UI-005` : zone transcription live.
- `UI-006` : état et messages.
- `UI-007` : raccourcis internes.
- `UI-008` : fermeture automatique sur succès.
- `UI-009` : affichage erreur avec texte partiel.

### Epic 5 — Clipboard et notifications

- `DESK-001` : copier texte dans presse-papiers.
- `DESK-002` : notification succès.
- `DESK-003` : notification annulation.
- `DESK-004` : notification erreur.
- `DESK-005` : bouton copier texte partiel.

### Epic 6 — Onboarding

- `ONB-001` : écran bienvenue.
- `ONB-002` : écran clé OpenAI.
- `ONB-003` : test clé OpenAI.
- `ONB-004` : écran micro.
- `ONB-005` : test niveau sonore.
- `ONB-006` : écran raccourci Ubuntu.
- `ONB-007` : test final.
- `ONB-008` : flag onboarding terminé.

### Epic 7 — Packaging

- `PKG-001` : fichier `.desktop`.
- `PKG-002` : icône.
- `PKG-003` : build exécutable.
- `PKG-004` : package `.deb`.
- `PKG-005` : script install local.
- `PKG-006` : test install/désinstall.

---

## 12. Critères d’acceptation fonctionnels

### AC-001 — Premier lancement

Étant donné que l’application est installée et non configurée, quand l’utilisateur lance VoxClip, alors l’assistant de configuration s’ouvre.

### AC-002 — Clé OpenAI

Étant donné que l’utilisateur saisit une clé OpenAI valide, quand il clique sur “Tester”, alors l’application confirme que la clé semble valide sans l’afficher en clair.

### AC-003 — Choix micro

Étant donné que des micros sont disponibles, quand l’utilisateur ouvre l’écran audio, alors il peut sélectionner un micro et visualiser le niveau sonore.

### AC-004 — Commande de raccourci

Étant donné que l’utilisateur veut configurer le raccourci Ubuntu, quand il arrive à l’écran correspondant, alors l’application affiche et permet de copier la commande :

```bash
voxclip --record-and-copy
```

### AC-005 — Dictée mock

Étant donné que l’application est lancée en mode mock, quand l’utilisateur démarre une dictée, alors une transcription simulée apparaît progressivement.

### AC-006 — Dictée réelle

Étant donné que l’application est configurée avec une clé valide et un micro fonctionnel, quand l’utilisateur parle puis arrête, alors le texte final est copié dans le presse-papiers.

### AC-007 — Notification succès

Étant donné qu’une transcription a réussi, quand le texte est copié, alors une notification indique que le texte est prêt à coller.

### AC-008 — Annulation

Étant donné qu’une dictée est en cours, quand l’utilisateur appuie sur `Échap`, alors l’enregistrement s’arrête, la fenêtre se ferme et le presse-papiers n’est pas modifié.

### AC-009 — Texte vide

Étant donné que l’utilisateur n’a rien dit, quand il arrête l’enregistrement, alors l’application n’écrase pas le presse-papiers et affiche une notification “Aucun texte détecté.”

### AC-010 — Erreur réseau

Étant donné que le réseau est indisponible, quand l’utilisateur tente une dictée, alors l’application affiche une erreur claire et ne crashe pas.

---

## 13. Tests automatisés attendus

### Unit tests

- configuration par défaut ;
- sérialisation/désérialisation config ;
- absence de clé OpenAI ;
- secret masqué dans les logs ;
- normalisation du transcript final ;
- refus de copier un texte vide ;
- agrégation de deltas ;
- state machine ;
- diagnostic sans données sensibles.

### Integration tests

- transcription mock complète ;
- audio source factice vers transcription mock ;
- fenêtre UI avec `pytest-qt` ;
- clipboard fake ;
- notifications fake ;
- erreur OpenAI simulée ;
- timeout simulé.

### Manual tests

- vrai micro ;
- vraie clé OpenAI ;
- Ubuntu Wayland ;
- raccourci clavier Ubuntu ;
- collage manuel dans plusieurs applications.

---

## 14. Gestion des erreurs

### Erreur : clé OpenAI absente

Message :

```text
Clé OpenAI non configurée. Ouvrez les paramètres VoxClip pour l’ajouter.
```

Action :

- ouvrir assistant ou paramètres.

### Erreur : clé OpenAI invalide

Message :

```text
La clé OpenAI semble invalide ou refusée.
```

Action :

- proposer de modifier la clé.

### Erreur : micro absent

Message :

```text
Aucun micro disponible. Vérifiez les paramètres audio Ubuntu.
```

Action :

- ouvrir écran audio.

### Erreur : silence ou texte vide

Message :

```text
Aucun texte détecté. Le presse-papiers n’a pas été modifié.
```

Action :

- fermer ou proposer de réessayer.

### Erreur : réseau

Message :

```text
Connexion impossible au service de transcription. Vérifiez votre réseau.
```

Action :

- conserver le texte partiel si disponible ;
- proposer bouton “Copier le texte partiel”.

### Erreur : presse-papiers

Message :

```text
La transcription est terminée, mais la copie dans le presse-papiers a échoué.
```

Action :

- afficher le texte final dans la fenêtre ;
- proposer bouton “Réessayer la copie”.

---

## 15. UX copy proposée

### Notification succès

```text
VoxClip
Texte copié. Faites Ctrl+V pour coller.
```

### Notification annulation

```text
VoxClip
Dictée annulée.
```

### Fenêtre enregistrement

```text
Enregistrement en cours…
Parlez maintenant. Entrée pour arrêter, Échap pour annuler.
```

### Fenêtre finalisation

```text
Finalisation de la transcription…
```

### Écran raccourci

```text
Configurez un raccourci Ubuntu pour lancer VoxClip depuis n’importe quelle application.

Nom :
VoxClip

Commande :
voxclip --record-and-copy

Raccourci recommandé :
Ctrl+Alt+V
```

---

## 16. Instructions spécifiques pour l’agent de code

L’agent doit respecter strictement ces règles :

1. Ne pas implémenter le collage automatique dans la V1.0.
2. Ne pas écrire l’audio sur disque.
3. Ne pas logger les transcriptions par défaut.
4. Ne pas stocker la clé OpenAI dans un fichier de config.
5. Garder la logique OpenAI hors de l’UI.
6. Garder la logique audio hors de l’UI.
7. Implémenter un mode mock complet avant de brancher OpenAI.
8. Ajouter des tests pour les services critiques.
9. Prévoir des abstractions remplaçables pour clipboard, notifications, transcription et audio.
10. Ne pas bloquer l’UI pendant les appels réseau.
11. Éviter les dépendances Linux trop intrusives en V1.0.
12. Documenter les commandes d’installation et de test.
13. Produire un package `.deb` si possible ; sinon fournir d’abord une procédure reproductible locale.
14. Ajouter un `--diagnose` exploitable pour le support.

---

## 17. Ordre de réalisation recommandé pour l’agent

L’ordre recommandé est :

1. Squelette projet + CLI.
2. Config + keyring.
3. UI mock sans audio.
4. Clipboard + notifications.
5. Audio capture + niveau sonore.
6. Transcription mock branchée UI.
7. OpenAI Realtime branché derrière l’interface.
8. Onboarding.
9. Diagnostic.
10. Packaging.
11. Tests manuels.
12. Corrections robustesse.

Ne pas commencer par le packaging. Ne pas commencer par OpenAI. D’abord obtenir une UX complète en mode mock, puis brancher les services réels.

---

## 18. Definition of Done V1.0

La V1.0 est terminée lorsque :

- l’application s’installe sur Ubuntu ;
- l’utilisateur peut la lancer depuis le menu ;
- le premier lancement guide la configuration ;
- la commande `voxclip --record-and-copy` fonctionne ;
- l’utilisateur peut configurer un raccourci Ubuntu vers cette commande ;
- la fenêtre de dictée s’ouvre et enregistre ;
- la transcription live fonctionne avec OpenAI ;
- le texte final est copié dans le presse-papiers ;
- une notification indique que le texte est prêt à coller ;
- les erreurs principales sont gérées ;
- aucune donnée sensible n’est loggée ;
- la clé OpenAI est stockée dans le keyring ;
- les tests unitaires et les tests d’intégration mock passent ;
- un test manuel a été réalisé sur Ubuntu GNOME Wayland.

---

## 19. Références techniques à consulter avant implémentation

Ces références doivent être vérifiées par l’agent au moment de coder, car les API et comportements desktop peuvent évoluer.

- OpenAI API — Realtime transcription guide
- OpenAI API — Realtime and audio guide
- OpenAI API — `gpt-realtime-whisper` model page
- Ubuntu Help — Custom keyboard shortcuts
- PySide6 documentation
- sounddevice documentation
- Python keyring documentation
- Freedesktop Notifications specification
- Debian packaging documentation

---

## 20. Note de cadrage finale

La V1.0 doit rester volontairement simple : elle transforme la voix en texte et rend ce texte immédiatement disponible dans le presse-papiers. Le collage automatique, l’intégration clic droit et les méthodes d’entrée natives sont des sujets de V1.1/V2.

Le succès de cette version dépend moins de la sophistication technique que de trois qualités :

1. déclenchement rapide ;
2. transcription fiable ;
3. impossibilité pratique de perdre le texte produit.

Ces trois critères doivent guider toutes les décisions d’implémentation.
