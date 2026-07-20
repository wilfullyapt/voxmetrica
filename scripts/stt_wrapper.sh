#!/usr/bin/env bash
# VoxMetrica STT wrapper sketch:
#   identify audio → write claim for session → run real STT → print transcript
#
# Wire later via Hermes local STT command.
# Args: <audio_path> [session_id]
set -euo pipefail
AUDIO="${1:-}"
SESSION="${2:-default}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(cd "$SCRIPT_DIR/.." && pwd)"
export VOXMETRICA_ROOT="${VOXMETRICA_ROOT:-$PKG/data}"

if [[ -z "$AUDIO" || ! -f "$AUDIO" ]]; then
  echo "usage: stt_wrapper.sh <audio_path> [session_id]" >&2
  exit 2
fi

python3 - <<PY
import json, sys
sys.path.insert(0, "${PKG}")
from lib.control_plane import ControlPlane
from lib.claims import ClaimStore
from lib.paths import get_data_root

cp = ControlPlane(get_data_root())
claim = cp.whoami_from_audio("${AUDIO}")
ClaimStore().put("${SESSION}", claim)
print(json.dumps({"voxmetrica_claim": {k: claim.get(k) for k in ("speaker_id","display_name","confidence","is_root","matched")}}), file=sys.stderr)
PY

if command -v faster-whisper >/dev/null 2>&1; then
  faster-whisper "$AUDIO" 2>/dev/null | tail -n +1
  exit 0
fi

python3 - <<'PY' "$AUDIO" 2>/dev/null || true
import sys
path = sys.argv[1]
try:
    from faster_whisper import WhisperModel
    model = WhisperModel("base")
    segments, _ = model.transcribe(path)
    print("".join(s.text for s in segments).strip())
except Exception:
    print("")
PY
