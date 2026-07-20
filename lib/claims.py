from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .paths import get_data_root, load_config


class ClaimStore:
    """Ephemeral per-session speaker claims written by STT wrapper / identify."""

    def __init__(self, root: Path | None = None):
        self.root = root or get_data_root()
        self.dir = self.root / "claims"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (session_id or "default"))
        return self.dir / f"{safe}.json"

    def put(self, session_id: str, claim: dict[str, Any]) -> Path:
        path = self._path(session_id)
        payload = dict(claim)
        payload["session_id"] = session_id
        payload["stored_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def get(self, session_id: str) -> dict[str, Any] | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        ttl = int(load_config(self.root).get("identify", {}).get("claim_ttl_seconds", 900))
        stored = data.get("stored_at") or data.get("matched_at")
        if stored and ttl > 0:
            # loose TTL check: if parse fails, keep claim
            try:
                # compare epoch roughly via mtime
                age = time.time() - path.stat().st_mtime
                if age > ttl:
                    return None
            except OSError:
                pass
        return data

    def clear(self, session_id: str) -> bool:
        path = self._path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False
