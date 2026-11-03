from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .paths import get_data_root, load_config

CLAIM_SCHEMA = "voxmetrica.claim/v1"


def build_claim_v1(
    *,
    outcome: str,
    speaker_id: str | None,
    display_name: str | None,
    confidence: float,
    margin: float,
    is_root: bool,
    candidates: list[dict[str, Any]],
    embed_backend: str,
    gallery_version: int = 1,
    ingress: str = "cli",
    device_id: str | None = None,
    reason: str | None = None,
    ok: bool = True,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Canonical claim payload for hub + edges."""
    outcome = outcome if outcome in ("matched", "clarify", "unknown") else "unknown"
    needs_clarify = outcome == "clarify"
    is_unknown = outcome == "unknown"
    matched = outcome == "matched"

    sid = speaker_id
    dname = display_name
    if outcome in ("unknown", "clarify"):
        sid = "guest"
        dname = dname or "Guest"
    elif not sid:
        sid = "guest"
        dname = dname or "Guest"

    claim: dict[str, Any] = {
        "ok": ok,
        "schema": CLAIM_SCHEMA,
        "outcome": outcome,
        "speaker_id": sid,
        "display_name": dname or sid or "Guest",
        "confidence": float(confidence),
        "margin": float(margin),
        "is_root": bool(is_root) if matched else False,
        "is_unknown": is_unknown,
        "matched": matched,
        "needs_clarify": needs_clarify,
        "candidates": candidates or [],
        "ingress": ingress,
        "embed_backend": embed_backend,
        "gallery_version": int(gallery_version),
        "matched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if device_id:
        claim["device_id"] = device_id
    if reason:
        claim["reason"] = reason
    if error:
        claim["error"] = error
        claim["ok"] = False
    if extra:
        claim.update(extra)
    return claim


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
        if ttl > 0:
            try:
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
