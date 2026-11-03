from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .capabilities import load_capabilities
from .claims import build_claim_v1
from .embedder import Embedder, load_embedding
from .gallery import Gallery
from .paths import get_data_root, load_config
from .score import cosine, decide_outcome, rank_scores
from .seal import Seal


def embed_file(audio_path: str | Path, root: Path | None = None) -> dict[str, Any]:
    emb = Embedder(root=root)
    return emb.embed(audio_path)


def _gallery_version(root: Path) -> int:
    gal = Gallery(root)
    idx = gal._load_index()
    return int(idx.get("version") or idx.get("gallery_version") or 1)


def _collect_scores(query: np.ndarray, root: Path) -> list[dict[str, Any]]:
    scores: list[dict[str, Any]] = []

    seal = Seal(root)
    root_meta: dict[str, Any] = {}
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

    gal = Gallery(root)
    for person in gal.list_people():
        if person.get("active") is False:
            continue
        sid = person["speaker_id"]
        best = -1.0
        best_ref = ""
        for p in gal.embedding_files(sid):
            try:
                ref = load_embedding(p)
                sc = cosine(query, ref)
                if sc > best:
                    best = sc
                    best_ref = str(p)
            except Exception:
                continue
        # centroid boost (max of centroid vs best member)
        cpath = gal.person_dir(sid) / "centroid.npy"
        if cpath.exists():
            try:
                sc = cosine(query, load_embedding(cpath))
                if sc > best:
                    best = sc
                    best_ref = str(cpath)
            except Exception:
                pass
        else:
            # compute on the fly when multiple embs
            try:
                from .adapt import speaker_centroid

                cent = speaker_centroid(sid, root)
                if cent is not None:
                    sc = cosine(query, cent)
                    if sc > best:
                        best = sc
                        best_ref = "centroid"
            except Exception:
                pass
        if best >= 0:
            scores.append(
                {
                    "speaker_id": sid,
                    "display_name": person.get("display_name", sid),
                    "is_root": False,
                    "score": float(best),
                    "ref": best_ref,
                }
            )
    return scores


def identify_embedding(
    query: np.ndarray,
    root: Path | None = None,
    *,
    embed_backend: str = "unknown",
    ingress: str = "cli",
    device_id: str | None = None,
) -> dict[str, Any]:
    """Score a query embedding against gallery + root; return claim v1."""
    root = root or get_data_root()
    cfg = load_config(root)
    id_cfg = cfg.get("identify") or {}
    accept = float(id_cfg.get("accept_threshold", id_cfg.get("threshold", 0.75)))
    clarify = float(id_cfg.get("clarify_threshold", 0.55))
    margin = float(id_cfg.get("min_margin", 0.05))

    raw_scores = _collect_scores(query, root)
    ranked = rank_scores(raw_scores)
    decision = decide_outcome(
        ranked,
        accept_threshold=accept,
        clarify_threshold=clarify,
        min_margin=margin,
    )

    caps_guest = load_capabilities("guest", root)
    if decision["outcome"] == "matched":
        display = decision.get("display_name")
    else:
        display = caps_guest.get("display_name", "Guest")

    claim = build_claim_v1(
        outcome=decision["outcome"],
        speaker_id=decision.get("speaker_id"),
        display_name=display,
        confidence=float(decision.get("confidence") or 0.0),
        margin=float(decision.get("margin") or 0.0),
        is_root=bool(decision.get("is_root")),
        candidates=decision.get("candidates") or [],
        embed_backend=embed_backend,
        gallery_version=_gallery_version(root),
        ingress=ingress,
        device_id=device_id,
        reason=decision.get("reason"),
        extra={
            "scores": [
                {
                    "speaker_id": s.get("speaker_id"),
                    "score": float(s.get("score", 0.0)),
                    "is_root": bool(s.get("is_root")),
                }
                for s in ranked[:10]
            ],
            "thresholds": {
                "accept": accept,
                "clarify": clarify,
                "min_margin": margin,
            },
        },
    )
    return claim


def identify_audio(
    audio_path: str | Path,
    root: Path | None = None,
    *,
    ingress: str = "cli",
    device_id: str | None = None,
) -> dict[str, Any]:
    """Embed audio, score against gallery + root, return claim v1."""
    root = root or get_data_root()
    emb_res = Embedder(root=root).embed(audio_path)
    if not emb_res.get("ok"):
        return build_claim_v1(
            outcome="unknown",
            speaker_id=None,
            display_name="Guest",
            confidence=0.0,
            margin=0.0,
            is_root=False,
            candidates=[],
            embed_backend=str(emb_res.get("backend") or "unknown"),
            gallery_version=_gallery_version(root),
            ingress=ingress,
            device_id=device_id,
            ok=False,
            error=str(emb_res.get("error") or "embed failed"),
            reason="embed failed",
        )

    return identify_embedding(
        emb_res["embedding"],
        root=root,
        embed_backend=str(emb_res.get("backend") or "unknown"),
        ingress=ingress,
        device_id=device_id,
    )
