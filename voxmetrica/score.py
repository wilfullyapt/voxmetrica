"""Score ranking and dual-threshold decision bands."""

from __future__ import annotations

from typing import Any

import numpy as np


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32).reshape(-1)
    b = b.astype(np.float32).reshape(-1)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


def rank_scores(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Best score per speaker_id, then sort descending."""
    best: dict[str, dict[str, Any]] = {}
    for s in scores or []:
        sid = s.get("speaker_id") or ""
        prev = best.get(sid)
        if prev is None or float(s.get("score", 0.0)) > float(prev.get("score", 0.0)):
            best[sid] = dict(s)
    ranked = sorted(best.values(), key=lambda x: float(x.get("score", 0.0)), reverse=True)
    return ranked


def decide_outcome(
    ranked: list[dict[str, Any]],
    *,
    accept_threshold: float = 0.75,
    clarify_threshold: float = 0.55,
    min_margin: float = 0.05,
    max_candidates: int = 5,
) -> dict[str, Any]:
    """Map ranked scores → matched | clarify | unknown."""
    if not ranked:
        return {
            "outcome": "unknown",
            "speaker_id": None,
            "display_name": None,
            "confidence": 0.0,
            "margin": 0.0,
            "is_root": False,
            "needs_clarify": False,
            "candidates": [],
            "reason": "empty gallery",
        }

    top = ranked[0]
    top_score = float(top.get("score", 0.0))
    second = float(ranked[1].get("score", 0.0)) if len(ranked) > 1 else 0.0
    margin = top_score - second if len(ranked) > 1 else top_score

    candidates = [
        {
            "speaker_id": r.get("speaker_id"),
            "display_name": r.get("display_name", r.get("speaker_id")),
            "score": float(r.get("score", 0.0)),
            "is_root": bool(r.get("is_root")),
        }
        for r in ranked[:max_candidates]
    ]

    if top_score < clarify_threshold:
        return {
            "outcome": "unknown",
            "speaker_id": None,
            "display_name": None,
            "confidence": top_score,
            "margin": margin,
            "is_root": False,
            "needs_clarify": False,
            "candidates": candidates,
            "reason": f"below clarify threshold {clarify_threshold}",
        }

    if top_score >= accept_threshold and margin >= min_margin:
        return {
            "outcome": "matched",
            "speaker_id": top.get("speaker_id"),
            "display_name": top.get("display_name", top.get("speaker_id")),
            "confidence": top_score,
            "margin": margin,
            "is_root": bool(top.get("is_root")),
            "needs_clarify": False,
            "candidates": candidates,
            "reason": "accept band",
        }

    # Gray zone or thin margin
    return {
        "outcome": "clarify",
        "speaker_id": None,
        "display_name": None,
        "confidence": top_score,
        "margin": margin,
        "is_root": False,
        "needs_clarify": True,
        "candidates": candidates,
        "reason": "gray zone or thin margin",
    }
