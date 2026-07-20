---
name: voxmetrica
description: Family vocal biometrics — enroll speakers, set per-voice capability memory, root-only admin.
version: 0.1.0
---

# VoxMetrica

Identify household speakers by voiceprint and load **that voice's capability memory**.
There are **no required roles**. Root is an immutable control-plane principal that can rewrite any biometric's memory.

## Data root

Default: package `data/` directory. Override with `VOXMETRICA_ROOT` for durable private storage (never commit).

## Local setup (recovery / first run)

```bash
python3 scripts/voxmetrica_cli.py setup
python3 scripts/voxmetrica_cli.py bootstrap-root --display-name "Root"
# optional root voice samples:
#   --audio /path/to/root1.wav --audio /path/to/root2.wav

python3 scripts/voxmetrica_cli.py enroll \
  --speaker-id adult1 --display-name "Adult One" \
  --audio /path/to/adult.wav --template full-adult

python3 scripts/voxmetrica_cli.py enroll \
  --speaker-id child1 --display-name "Child One" \
  --audio /path/to/child.wav --template limited-child
```

## Root-only memory updates

Only root claim or local CLI may change capabilities:

```bash
python3 scripts/voxmetrica_cli.py set-caps \
  --speaker-id child1 --template limited-child
```

Or `set-caps --yaml /path/to/capabilities.yaml`.

## Agent tools

- `voxmetrica_status` / `voxmetrica_list` / `voxmetrica_whoami`
- `voxmetrica_get_capabilities` / `voxmetrica_check`
- `voxmetrica_enroll` / `voxmetrica_delete` / `voxmetrica_set_capabilities` (**root**)

## Identify path

Gateway should run `scripts/stt_wrapper.sh` on voice notes so claims land in `claims/<session>.json` before the agent turn. The `pre_llm_call` hook injects capability notes for the matched speaker.

## Embed backend

- **Production:** SpeechBrain ECAPA (`pip install speechbrain torch torchaudio`)
- **Scaffold/dev:** `hash_stub` (not real biometrics)

Set `identify.backend` in `config.yaml`.
