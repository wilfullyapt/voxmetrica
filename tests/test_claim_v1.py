"""Claim schema v1 shape helpers."""

from __future__ import annotations

from voxmetrica.claims import build_claim_v1


def test_build_claim_matched():
    claim = build_claim_v1(
        outcome="matched",
        speaker_id="adult1",
        display_name="Adult One",
        confidence=0.91,
        margin=0.12,
        is_root=False,
        candidates=[{"speaker_id": "adult1", "display_name": "Adult One", "score": 0.91}],
        embed_backend="hash_stub",
        gallery_version=2,
        ingress="cli",
    )
    assert claim["schema"] == "voxmetrica.claim/v1"
    assert claim["outcome"] == "matched"
    assert claim["needs_clarify"] is False
    assert claim["is_unknown"] is False
    assert claim["matched"] is True
    assert claim["gallery_version"] == 2
    assert "matched_at" in claim


def test_build_claim_clarify():
    claim = build_claim_v1(
        outcome="clarify",
        speaker_id=None,
        display_name="Guest",
        confidence=0.68,
        margin=0.02,
        is_root=False,
        candidates=[
            {"speaker_id": "a", "display_name": "A", "score": 0.68},
            {"speaker_id": "b", "display_name": "B", "score": 0.66},
        ],
        embed_backend="speechbrain-ecapa",
        gallery_version=1,
        ingress="narthex",
    )
    assert claim["outcome"] == "clarify"
    assert claim["needs_clarify"] is True
    assert claim["is_unknown"] is False
    assert claim["matched"] is False
    assert claim["speaker_id"] == "guest"


def test_build_claim_unknown_empty_gallery():
    claim = build_claim_v1(
        outcome="unknown",
        speaker_id=None,
        display_name="Guest",
        confidence=0.0,
        margin=0.0,
        is_root=False,
        candidates=[],
        embed_backend="hash_stub",
        gallery_version=1,
        ingress="cli",
        reason="empty gallery",
    )
    assert claim["outcome"] == "unknown"
    assert claim["is_unknown"] is True
    assert claim["matched"] is False
    assert claim["reason"] == "empty gallery"
