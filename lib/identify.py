from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from .embedder import Embedder, cosine, load_embedding
from .gallery import Gallery
from .paths import get_data_root, load_config
from .seal import Seal
from .capabilities import load_capabilities


def embed_file(audio_path: str | Path, root: Path | None = None) -> dict[str, Any]:
    emb = Embedder(root=root)
    return emb.embed(audio_path)


def identify_audio(audio_path: str | Path, root: Path | None = None) -> dict[str, Any]:
    """Embed audio, score against gallery + root, return claim."""
    root = root or get_data_root()
    cfg = load_config(root)
    threshold = float(cfg.get("identify", {}).get("threshold", 0.75))

    emb_res = Embedder(root=root).embed(audio_path)
    if not emb_res.get("ok"):
        return {
            "ok": False,
            "speaker_id": "guest",
            "display_name": "Guest",
            "confidence": 0.0,
            "is_root": False,
            "error": emb_res.get("error"),
            "backend": emb_res.get("backend"),
        }

    query: np.ndarray = emb_res["embedding"]
    scores: list[dict[str, Any]] = []

    # Root embeddings
    seal = Seal(root)
    root_meta = {}
    if seal.exists():
        v = seal.verify()
        if v.get("ok"):
            root_meta = v.get("meta") or {}
        for p in sorted((root / "control" / "root_embeddings").glob("*.npy")):
            try:
                ref = load_embedding(p)
                scores.append(
                    {
                        "speaker_id": root_meta.get("speaker_id", "root"),
                        "display_name": root_meta.get("display_name", "Root"),
                        "is_root": True,
                        "score": cosine(query, ref),
                        "ref": str(p),
                    }
                )
            except Exception:
                continue

    # Gallery
    gal = Gallery(root)
    for person in gal.list_people():
        sid = person["speaker_id"]
        for p in gal.embedding_files(sid):
            try:
                ref = load_embedding(p)
                scores.append(
                    {
                        "speaker_id": sid,
                        "display_name": person.get("display_name", sid),
                        "is_root": False,
                        "score": cosine(query, ref),
                        "ref": str(p),
                    }
                )
            except Exception:
                continue

    if not scores:
        caps = load_capabilities("guest", root)
        return {
            "ok": True,
            "speaker_id": "guest",
            "display_name": caps.get("display_name", "Guest"),
            "confidence": 0.0,
            "is_root": False,
            "matched": False,
            "backend": emb_res["backend"],
            "reason": "empty gallery",
            "scores": [],
            "matched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    best = max(scores, key=lambda s: s["score"])
    matched = best["score"] >= threshold
    if not matched:
        caps = load_capabilities("guest", root)
        return {
            "ok": True,
            "speaker_id": "guest",
            "display_name": caps.get("display_name", "Guest"),
            "confidence": float(best["score"]),
            "is_root": False,
            "matched": False,
            "backend": emb_res["backend"],
            "reason": f"below threshold {threshold}",
            "best_candidate": {
                "speaker_id": best["speaker_id"],
                "score": best["score"],
            },
            "scores": sorted(
                [{"speaker_id": s["speaker_id"], "score": s["score"], "is_root": s["is_root"]} for s in scores],
                key=lambda x: -x["score"],
            )[:10],
            "matched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    return {
        "ok": True,
        "speaker_id": best["speaker_id"],
        "display_name": best["display_name"],
        "confidence": float(best["score"]),
        "is_root": bool(best["is_root"]),
        "matched": True,
        "backend": emb_res["backend"],
        "scores": sorted(
            [{"speaker_id": s["speaker_id"], "score": s["score"], "is_root": s["is_root"]} for s in scores],
            key=lambda x: -x["score"],
        )[:10],
        "matched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
