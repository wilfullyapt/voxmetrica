# VoxMetrica — design (v0.1)

Family vocal-biometric gate for Hermes: identify speaker from voice, load that speaker's capability memory, enforce access. Named project: **VoxMetrica**.

## Design principles

1. **Per-biometric capability memory** — not role-based RBAC. Each enrolled voiceprint has its own allow/deny/resource memory. "Roles" are optional convenience templates only; not required at runtime.
2. **Immutable root / core user** — a sealed superuser binding that can always override policy, rewrite capability memories, enroll/delete biometrics, and recover the system. Root is not just another soft memory entry.
3. **Biometrics at gateway/STT ingress** — identity claim is produced where audio exists; agent hooks consume the claim.
4. **Local durable data** — embeddings + capability memory under `VOXMETRICA_ROOT` or package `./data` (gitignored). No cloud voiceprints by default.
5. **Paper-first / safety defaults** — unknown speaker = minimal capabilities; high-risk resources require explicit per-biometric grants + root can revoke anytime.

## Identity model

```
voice audio
  → embedding
  → match gallery (cosine / threshold)
  → speaker_id | unknown
  → load capabilities for that speaker_id
  → inject claim + caps into turn
  → enforce on sensitive actions
```

### Root (immutable core)

- Single **root principal**, established at first setup (or recovery).
- Bound by **at least one** of:
  - sealed root voiceprint(s) under `control/` with integrity protection
  - local CLI with host filesystem access (bootstrap / recovery path)
  - optional secondary factor later (PIN file, paired platform user ID) — never sole factor for high-risk if spoofing is a concern
- Root can:
  - enroll / delete any biometric
  - rewrite any speaker's capability memory
  - set global defaults and thresholds
  - export/import gallery
  - rotate root voiceprints (re-seal)
- Root capabilities are **not** editable via normal capability memory writes from non-root speakers.
- Implementation: root ACL lives in a **sealed control plane** file, not in the same mutable YAML non-root speakers can influence through agent tools.

### Everyone else

- One entry per enrolled person/voice in the gallery.
- Each has `capabilities.yaml` describing what *this* voice may use.
- No required `role: parent|child`. Optional templates at enroll only.

## Filesystem

```text
voxmetrica/                      # repo / package
├── DESIGN.md
├── README.md
├── config.yaml                  # non-secret defaults
├── templates/                   # enroll starters
├── lib/
├── plugin/
├── scripts/
└── data/                        # RUNTIME — gitignored
    ├── control/
    │   ├── root.seal
    │   ├── root.meta.json
    │   └── root_embeddings/
    ├── gallery/
    │   ├── index.json
    │   └── <speaker_id>/
    │       ├── meta.json
    │       ├── embeddings/
    │       └── capabilities.yaml
    ├── claims/
    ├── enroll_raw/
    └── audit/
```

### Hermes plugin install location

```text
~/.hermes/plugins/voxmetrica/   # symlink or copy of plugin/
```

Plugin code is replaceable; **control/ + gallery/** under the data root are durable and private.

## Capability memory (per biometric)

Prefer **structured YAML** (machine-enforceable) with optional free-text notes for the model.

Example `gallery/child1/capabilities.yaml`:

```yaml
speaker_id: child1
display_name: Child One
version: 1
updated_at: 2026-01-01T00:00:00Z
updated_by: root   # only root (or sealed process) may write

mode: allowlist   # allowlist | denylist
resources:
  tools:
    allow: [web_search, tts, clarify]
    deny: [terminal, file_write, cronjob, memory, delegate_task]
  toolsets:
    allow: [safe, web]
    deny: [homeassistant, discord_admin]
  paths:
    allow: []
    deny: ["*"]
  memory_scopes:
    allow: [child1_public]
    deny: [family_private, couple_private, root]
  home:
    allow: []
    deny: ["*"]
  network:
    allow: [search]
  time_windows: []

notes_for_model: |
  Limited-access speaker. Be friendly, short answers.
  Never discuss private household finances or override admin rules.
  If asked for denied resources, refuse and suggest asking a household admin.
```

Example trusted adult:

```yaml
speaker_id: adult1
display_name: Adult One
mode: denylist
resources:
  tools:
    deny: []   # empty deny = broad access; still cannot rewrite root.seal
  paths:
    deny: []
  memory_scopes:
    allow: ["*"]
notes_for_model: |
  Trusted adult speaker. Broad access to household assistant features.
  Cannot rewrite control plane unless speaking as root or via local recovery CLI.
```

**Important:** Household authority is encoded as **that person's capability file**, not a role enum. Root is still separate and stronger.

## Immutable root — how "immutable" is enforced

Software cannot be literally unbreakable on a box the owner controls, but VoxMetrica should make non-root paths **unable** to change the control plane:

1. **Separate control directory** with file permissions `0700` / service-user owned.
2. **Writes to any `capabilities.yaml` or gallery index** go through a single control-plane API that checks:
   - caller claim is root (high confidence), **or**
   - process is local CLI with recovery flag
3. **Agent tools**:
   - Non-root: read own caps (optional), cannot edit others
   - Root-claim only: `voxmetrica_set_capabilities`, `voxmetrica_enroll`, `voxmetrica_delete`
4. **Integrity seal** (`root.seal`): hash of root embedding set + meta; on verify failure, **fail closed** (guest-only until recovery).
5. **Override path**: root voice (or local recovery CLI) can always rewrite any biometric's memory files.

## Runtime claim

```json
{
  "speaker_id": "adult1",
  "display_name": "Adult One",
  "confidence": 0.91,
  "is_root": false,
  "matched_at": "..."
}
```

`pre_llm_call` injects a short summary of caps + notes_for_model.
Enforcement: check resource requests against that speaker's file.

## Gateway / STT placement

- Prefer **STT wrapper** that embeds+matches before transcript, writes claim, then STT.
- Plugin injects claim into the turn.
- Unknown → guest template caps.

## Hermes plugin tools (proposed)

| Tool | Who |
|------|-----|
| `voxmetrica_status` | any |
| `voxmetrica_whoami` | any |
| `voxmetrica_list` | any (metadata only) |
| `voxmetrica_enroll` | root only |
| `voxmetrica_delete` | root only |
| `voxmetrica_get_capabilities` | root, or self |
| `voxmetrica_set_capabilities` | **root only** |
| `voxmetrica_check` | any (evaluation) |

## Privacy / repo hygiene

- Never commit `data/`, embeddings, seals, claims, audit DBs, or raw enroll audio.
- No personal names, platform user IDs, or household paths in committed templates/docs.
- Defaults use placeholders (`adult1`, `child1`, `Root`).

## Open decisions (product)

1. Root = voice only, or voice + platform user binding for admin tools?
2. Low confidence: guest, or re-authenticate?
3. Re-enroll reminders for changing voices (e.g. children).

## Implementation phases

1. Scaffold plugin + data dirs + root seal + guest/default caps
2. Gallery enroll/identify (SpeechBrain ECAPA; hash_stub for dev)
3. Capability engine allowlist/denylist
4. STT wrapper + pre_llm_call inject
5. Root-only set_capabilities + audit
6. Messaging-platform enrollment UX

## Non-goals (v0)

- Always-on room mic
- Cloud biometrics
- Clinical therapist mode
- Hard guarantee against physical host compromise
