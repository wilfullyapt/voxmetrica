"""Clarify session store — pending gray-zone identity."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from .adapt import adapt_append
from .audit import AuditLog
from .claims import ClaimStore, build_claim_v1
from .gallery import Gallery
from .paths import get_data_root, load_config


class ClarifyStore:
    def __init__(self, root: Path | None = None):
        self.root = root or get_data_root()
        self.dir = self.root / "clarify"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (session_id or "default"))
        return self.dir / f"{safe}.json"

    def put(self, session_id: str, payload: dict[str, Any]) -> Path:
        path = self._path(session_id)
        data = dict(payload)
        data["session_id"] = session_id
        data["stored_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
        return path

    def get(self, session_id: str) -> dict[str, Any] | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        ttl = int(load_config(self.root).get("identify", {}).get("claim_ttl_seconds", 900))
        if ttl > 0:
            try:
                if time.time() - path.stat().st_mtime > ttl:
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


def begin_clarify(
    session_id: str,
    claim: dict[str, Any],
    *,
    query_embedding: np.ndarray | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Persist a pending clarify claim (and optional query embedding) for resolve."""
    root = root or get_data_root()
    store = ClarifyStore(root)
    payload = dict(claim)
    payload["outcome"] = "clarify"
    payload["needs_clarify"] = True
    if query_embedding is not None:
        emb_dir = root / "clarify" / "embeddings"
        emb_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        emb_path = emb_dir / f"{safe}.npy"
        np.save(emb_path, query_embedding.astype(np.float32))
        payload["query_embedding_path"] = str(emb_path)
    store.put(session_id, payload)
    ClaimStore(root).put(session_id, {**payload, "speaker_id": "guest", "matched": False})
    AuditLog(root).log("clarify_begin", "guest", {"session_id": session_id})
    return {"ok": True, "session_id": session_id, "pending": True}


def clarify_resolve(
    session_id: str,
    choice: str,
    *,
    root: Path | None = None,
    adapt: bool = True,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Bind a pending clarify session to a candidate, guest, or new enroll name.

    choice: speaker_id from candidates | 'guest' | 'new' (requires display_name + separate enroll)
    """
    root = root or get_data_root()
    store = ClarifyStore(root)
    pending = store.get(session_id)
    if not pending:
        # distinguish missing vs expired: path gone vs path exists but TTL
        if store._path(session_id).exists():
            return {"ok": False, "error": "clarify session expired", "code": "expired"}
        return {"ok": False, "error": "no pending clarify session", "code": "missing"}

    choice = (choice or "").strip()
    candidates = pending.get("candidates") or []
    cand_ids = {c.get("speaker_id") for c in candidates}

    if choice in ("guest", "unknown", "decline", ""):
        claim = build_claim_v1(
            outcome="unknown",
            speaker_id=None,
            display_name="Guest",
            confidence=float(pending.get("confidence") or 0.0),
            margin=float(pending.get("margin") or 0.0),
            is_root=False,
            candidates=candidates,
            embed_backend=str(pending.get("embed_backend") or "unknown"),
            gallery_version=int(pending.get("gallery_version") or 1),
            ingress=str(pending.get("ingress") or "cli"),
            reason="clarify declined",
        )
        store.clear(session_id)
        ClaimStore(root).put(session_id, claim)
        AuditLog(root).log("clarify_resolve", "guest", {"choice": "guest"})
        return claim

    if choice == "new":
        return {
            "ok": False,
            "error": "choice=new requires enroll-self / enroll with display_name; pending kept",
            "code": "use_enroll",
            "display_name": display_name,
            "session_id": session_id,
        }

    if choice not in cand_ids:
        # also allow resolving to any enrolled speaker if admin
        if not Gallery(root).get(choice):
            return {"ok": False, "error": f"choice not in candidates: {choice}", "code": "bad_choice"}

    person = Gallery(root).get(choice) or {}
    dname = person.get("display_name") or next(
        (c.get("display_name") for c in candidates if c.get("speaker_id") == choice), choice
    )
    conf = float(pending.get("confidence") or 0.0)
    for c in candidates:
        if c.get("speaker_id") == choice:
            conf = float(c.get("score") or conf)
            break

    claim = build_claim_v1(
        outcome="matched",
        speaker_id=choice,
        display_name=dname,
        confidence=conf,
        margin=float(pending.get("margin") or 0.0),
        is_root=False,
        candidates=candidates,
        embed_backend=str(pending.get("embed_backend") or "unknown"),
        gallery_version=int(pending.get("gallery_version") or Gallery(root)._load_index().get("version") or 1),
        ingress=str(pending.get("ingress") or "cli"),
        reason="clarify resolved",
    )

    if adapt:
        emb_path = pending.get("query_embedding_path")
        if emb_path and Path(emb_path).exists():
            vec = np.load(emb_path).astype(np.float32).reshape(-1)
            adapt_append(choice, vec, root=root, reason="clarify_confirm", confirmed=True)

    store.clear(session_id)
    ClaimStore(root).put(session_id, claim)
    AuditLog(root).log("clarify_resolve", choice, {"session_id": session_id})
    return claim
