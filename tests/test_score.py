"""Dual-threshold score bands — synthetic vectors only."""

from __future__ import annotations

import numpy as np

from voxmetrica.score import cosine, decide_outcome, rank_scores


def _unit(vec: list[float]) -> np.ndarray:
    a = np.asarray(vec, dtype=np.float32)
    return a / (np.linalg.norm(a) + 1e-9)


def test_cosine_identical_is_one():
    v = _unit([1.0, 2.0, 3.0])
    assert abs(cosine(v, v) - 1.0) < 1e-5


def test_rank_scores_orders_desc_and_margin():
    ranked = rank_scores(
        [
            {"speaker_id": "a", "score": 0.70, "display_name": "A", "is_root": False},
            {"speaker_id": "b", "score": 0.90, "display_name": "B", "is_root": False},
            {"speaker_id": "c", "score": 0.80, "display_name": "C", "is_root": False},
        ]
    )
    assert [r["speaker_id"] for r in ranked] == ["b", "c", "a"]
    assert abs(ranked[0]["score"] - ranked[1]["score"] - 0.10) < 1e-6


def test_decide_accept_when_above_threshold_and_margin():
    ranked = [
        {"speaker_id": "alex", "display_name": "Alex", "score": 0.82, "is_root": False},
        {"speaker_id": "sam", "display_name": "Sam", "score": 0.60, "is_root": False},
    ]
    d = decide_outcome(ranked, accept_threshold=0.75, clarify_threshold=0.55, min_margin=0.05)
    assert d["outcome"] == "matched"
    assert d["speaker_id"] == "alex"
    assert d["needs_clarify"] is False
    assert d["margin"] >= 0.05


def test_decide_clarify_when_gray_band():
    ranked = [
        {"speaker_id": "alex", "display_name": "Alex", "score": 0.68, "is_root": False},
        {"speaker_id": "sam", "display_name": "Sam", "score": 0.50, "is_root": False},
    ]
    d = decide_outcome(ranked, accept_threshold=0.75, clarify_threshold=0.55, min_margin=0.05)
    assert d["outcome"] == "clarify"
    assert d["needs_clarify"] is True
    assert d["speaker_id"] is None
    assert len(d["candidates"]) >= 1


def test_decide_clarify_when_accept_score_but_thin_margin():
    ranked = [
        {"speaker_id": "alex", "display_name": "Alex", "score": 0.80, "is_root": False},
        {"speaker_id": "sam", "display_name": "Sam", "score": 0.78, "is_root": False},
    ]
    d = decide_outcome(ranked, accept_threshold=0.75, clarify_threshold=0.55, min_margin=0.05)
    assert d["outcome"] == "clarify"
    assert d["needs_clarify"] is True
    assert len(d["candidates"]) >= 2


def test_decide_unknown_when_below_clarify():
    ranked = [
        {"speaker_id": "alex", "display_name": "Alex", "score": 0.40, "is_root": False},
    ]
    d = decide_outcome(ranked, accept_threshold=0.75, clarify_threshold=0.55, min_margin=0.05)
    assert d["outcome"] == "unknown"
    assert d["needs_clarify"] is False
    assert d["speaker_id"] is None


def test_decide_unknown_when_empty_scores():
    d = decide_outcome([], accept_threshold=0.75, clarify_threshold=0.55, min_margin=0.05)
    assert d["outcome"] == "unknown"
    assert d["confidence"] == 0.0
    assert d["candidates"] == []
