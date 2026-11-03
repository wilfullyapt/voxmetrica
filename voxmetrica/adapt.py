"""Template adaptation — append embeddings, centroid, caps (no backbone train)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from .audit import AuditLog
from .embedder import Embedder, load_embedding
from .gallery import Gallery
from .paths import get_data_root, load_config
from .score import cosine


def speaker_centroid(speaker_id: str, root: Path | None = None) -> np.ndarray | None:
    root = root or get_data_root()
    files = Gallery(root).embedding_files(speaker_id)
    if not files:
        return None
    vecs = []
    for p in files:
        try:
            v = load_embedding(p).astype(np.float32).reshape(-1)
            n = np.linalg.norm(v) + 1e-9
            vecs.append(v / n)
        except Exception:
            continue
    if not vecs:
        return None
    mean = np.mean(np.stack(vecs, axis=0), axis=0)
    n = np.linalg.norm(mean) + 1e-9
    return (mean / n).astype(np.float32)


def _prune_to_max(speaker_id: str, root: Path, max_n: int) -> None:
    gal = Gallery(root)
    files = gal.embedding_files(speaker_id)
    if len(files) <= max_n:
        return
    centroid = speaker_centroid(speaker_id, root)
    if centroid is None:
        # drop oldest
        for p in files[: len(files) - max_n]:
            p.unlink(missing_ok=True)
        return
    # drop farthest from centroid
    scored = []
    for p in files:
        try:
            v = load_embedding(p)
            scored.append((cosine(v, centroid), p))
        except Exception:
            scored.append((-1.0, p))
    scored.sort(key=lambda x: x[0])  # lowest similarity first
    drop = len(files) - max_n
    for _, p in scored[:drop]:
        p.unlink(missing_ok=True)


def adapt_append(
    speaker_id: str,
    embedding: np.ndarray | str | Path,
    *,
    root: Path | None = None,
    reason: str = "manual",
    confirmed: bool = False,
    audio_path: str | Path | None = None,
) -> dict[str, Any]:
    """Append one embedding to a speaker (gated)."""
    root = root or get_data_root()
    cfg = load_config(root)
    adapt_cfg = cfg.get("adapt") or {}
    if not adapt_cfg.get("enabled", True):
        return {"ok": False, "error": "adapt disabled", "code": "disabled"}

    require_confirm = bool(adapt_cfg.get("require_confirm", True))
    if require_confirm and not confirmed:
        # silent path only if score gates provided via reason=silent and thresholds — still need confirmed or silent flags
        if reason != "silent_high_conf" or not adapt_cfg.get("silent_enabled", False):
            return {"ok": False, "error": "adapt requires confirm", "code": "confirm_required"}

    gal = Gallery(root)
    if not gal.get(speaker_id):
        return {"ok": False, "error": f"unknown speaker: {speaker_id}", "code": "unknown"}

    if isinstance(embedding, (str, Path)):
        vec = load_embedding(Path(embedding))
    else:
        vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
    n = np.linalg.norm(vec) + 1e-9
    vec = (vec / n).astype(np.float32)

    # optional collision check vs other speakers
    c = speaker_centroid(speaker_id, root)
    if c is not None:
        # if closer to another speaker's centroid, refuse
        for person in gal.list_people():
            sid = person["speaker_id"]
            if sid == speaker_id:
                continue
            oc = speaker_centroid(sid, root)
            if oc is None:
                continue
            if cosine(vec, oc) > cosine(vec, c) + 0.05:
                return {
                    "ok": False,
                    "error": f"collision risk with {sid}",
                    "code": "collision",
                }

    emb_dir = gal.person_dir(speaker_id) / "embeddings"
    emb_dir.mkdir(parents=True, exist_ok=True)
    existing = gal.embedding_files(speaker_id)
    next_i = len(existing) + 1
    dest = emb_dir / f"emb_{next_i:03d}_{int(time.time())}.npy"
    Embedder(root).save_embedding(vec, dest)

    max_n = int(adapt_cfg.get("max_embeddings_per_speaker", 20))
    _prune_to_max(speaker_id, root, max_n)

    # refresh meta + index counts
    pdir = gal.person_dir(speaker_id)
    meta_path = pdir / "meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    files = gal.embedding_files(speaker_id)
    meta["embeddings"] = [str(f.relative_to(pdir)) for f in files]
    meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    idx = gal._load_index()
    if speaker_id in (idx.get("people") or {}):
        idx["people"][speaker_id]["embedding_count"] = len(files)
        gal._save_index(idx)

    # write centroid cache
    cent = speaker_centroid(speaker_id, root)
    if cent is not None:
        Embedder(root).save_embedding(cent, pdir / "centroid.npy")

    AuditLog(root).log("adapt_append", speaker_id, {"reason": reason, "count": len(files)})
    return {
        "ok": True,
        "speaker_id": speaker_id,
        "embedding_count": len(files),
        "path": str(dest),
        "reason": reason,
    }


def adapt_from_audio(
    speaker_id: str,
    audio_path: str | Path,
    *,
    root: Path | None = None,
    confirmed: bool = False,
    reason: str = "manual",
) -> dict[str, Any]:
    root = root or get_data_root()
    emb = Embedder(root).embed(audio_path)
    if not emb.get("ok"):
        return {"ok": False, "error": emb.get("error"), "code": "embed"}
    return adapt_append(
        speaker_id,
        emb["embedding"],
        root=root,
        confirmed=confirmed,
        reason=reason,
        audio_path=audio_path,
    )
