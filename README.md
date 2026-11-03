# VoxMetrica

Family **vocal biometrics** + **per-voice capability memory** for Hermes Agent.

- **No required roles** — each enrolled voice has its own `capabilities.yaml`
- **Immutable root** — sealed control plane can override any biometric's memory
- **Plugin** — tools, hooks, skill under `plugin/`
- **Runtime data** — `./data` (or `VOXMETRICA_ROOT`); gitignored
- **Claim v1** — `matched | clarify | unknown` with dual threshold + margin
- **Clarify / adapt / sync** — session resolve, template adaptation, `voxmetrica-sync-v1`

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# Real ECAPA embeddings (hub / GPU):
# pip install -e ".[speechbrain]"
```

## Quick start

```bash
export VOXMETRICA_ROOT="${VOXMETRICA_ROOT:-$HOME/.local/share/voxmetrica}"
voxmetrica setup
voxmetrica bootstrap-root --display-name "Root"

# Blank house: voice names itself (min 3 clips by default)
voxmetrica enroll-self \
  --display-name "Adult One" \
  --audio /path/to/clip1.wav \
  --audio /path/to/clip2.wav \
  --audio /path/to/clip3.wav

# Or root-gated enroll
voxmetrica enroll \
  --speaker-id adult1 --display-name "Adult One" \
  --audio /path/to/clip.wav --template full-adult

voxmetrica status
voxmetrica whoami --audio /path/to/clip.wav
voxmetrica check --speaker-id adult1 --kind tools --name terminal

# After a clarify claim (session pending):
voxmetrica clarify-resolve --session-id default --choice adult1

# Confirmed template adapt + signature sync
voxmetrica adapt --speaker-id adult1 --audio /path/to/clip.wav
voxmetrica sync-export --dest /tmp/vox-sync
voxmetrica sync-import --src /tmp/vox-sync
```

`hash_stub` embeddings are **dev only**. Set `production: true` in config to refuse them.

## Decision bands (defaults — calibrate on household mics)

| Band | Cosine (ECAPA) | Outcome |
|------|----------------|---------|
| Accept | ≥ 0.75 and margin ≥ 0.05 | `matched` |
| Clarify | 0.55–0.75 or thin margin | `clarify` |
| Reject | < 0.55 | `unknown` / guest |

## Install Hermes / Portunus plugin

```bash
pip install -e .
mkdir -p ~/.hermes/plugins   # or profiles/portunus plugins path
ln -sfn "$(pwd)/plugin" ~/.hermes/plugins/voxmetrica
hermes -p portunus plugins enable voxmetrica   # when available
# gateway restart from SSH after enable
```

**Turn policy:** `pre_llm_call` injects claim + caps; `pre_tool_call` gates tools (guest/clarify cannot hit `terminal`; root-only mutations ignore forged `is_root_claim` args).

**Edge doorways:**

```python
from voxmetrica import EdgeClient
client = EdgeClient(ingress="narthex")  # or mobile-ami
claim = client.identify("/tmp/clip.wav", session_id="door1")
print(client.badge(claim))
```

## Layout

```
voxmetrica/
  DESIGN.md
  config.yaml          # defaults only
  templates/           # enroll starters
  voxmetrica/          # Python package
  plugin/              # Hermes plugin
  scripts/             # CLI shim + STT wrapper
  tests/
  data/                # runtime (gitignored)
```

## Security notes

- Root ops require local CLI recovery or a verified root voice claim
- `hash_stub` is scaffolding only — install SpeechBrain for real fingerprints
- Never commit `data/`, seals, embeddings, claims, or audit DBs
- Raw enroll audio should be deleted after embed
- Prefer false reject + clarify over false accept for privileged tools

## Requirements

- Python 3.10+
- `pyyaml`, `numpy` (required)
- Optional: `torch`, `torchaudio`, `speechbrain` for ECAPA embeddings
