# VoxMetrica

Family **vocal biometrics** + **per-voice capability memory** for Hermes Agent.

- **No required roles** — each enrolled voice has its own `capabilities.yaml`
- **Immutable root** — sealed control plane can override any biometric's memory
- **Plugin** — tools, hooks, skill under `plugin/`
- **Runtime data** — `./data` (or `VOXMETRICA_ROOT`); gitignored

## Quick start

```bash
python3 scripts/voxmetrica_cli.py setup
python3 scripts/voxmetrica_cli.py bootstrap-root --display-name "Root"

# Enroll (hash_stub embeddings until SpeechBrain is installed)
python3 scripts/voxmetrica_cli.py enroll \
  --speaker-id adult1 --display-name "Adult One" \
  --audio /path/to/clip.wav --template full-adult

python3 scripts/voxmetrica_cli.py status
python3 scripts/voxmetrica_cli.py whoami --audio /path/to/clip.wav
python3 scripts/voxmetrica_cli.py check --speaker-id adult1 --kind tools --name terminal
```

## Install Hermes plugin

```bash
mkdir -p ~/.hermes/plugins
ln -sfn "$(pwd)/plugin" ~/.hermes/plugins/voxmetrica
hermes plugins enable voxmetrica
# restart gateway if needed
```

Set a durable data root for household use (do not commit it):

```bash
export VOXMETRICA_ROOT="$HOME/.local/share/voxmetrica"
python3 scripts/voxmetrica_cli.py setup
```

## Layout

```
voxmetrica/
  DESIGN.md
  config.yaml          # defaults only
  templates/           # enroll starters
  lib/                 # Python core
  plugin/              # Hermes plugin
  scripts/             # CLI + STT wrapper
  data/                # runtime (gitignored): gallery, control, claims, audit
```

## Security notes

- Root ops require local CLI recovery or a verified root voice claim
- `hash_stub` is for scaffolding only — install SpeechBrain for real fingerprints
- Never commit `data/`, seals, embeddings, claims, or audit DBs
- Raw enroll audio should be deleted after embed

## Requirements

- Python 3.10+
- `pyyaml`, `numpy` (required)
- Optional: `torch`, `torchaudio`, `speechbrain` for ECAPA embeddings
