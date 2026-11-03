"""P3 — clarify session store + resolve."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from voxmetrica.clarify import ClarifyStore, begin_clarify, clarify_resolve
from voxmetrica.gallery import Gallery
from voxmetrica.identify import identify_embedding


def _unit(seed: int, dim: int = 192) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def test_begin_clarify_stores_pending(data_root: Path, save_embedding):
    a, b = _unit(1), _unit(2)
    Gallery(data_root).enroll("alex", "Alex", [save_embedding("a", a)])
    Gallery(data_root).enroll("sam", "Sam", [save_embedding("b", b)])
    # gray blend
    q = a * 0.65 + b * 0.35
    q = q / (np.linalg.norm(q) + 1e-9)
    claim = identify_embedding(q, root=data_root, embed_backend="hash_stub")
    assert claim["outcome"] in ("clarify", "matched", "unknown")
    # force pending via begin_clarify with a synthetic clarify claim
    clarify_claim = {
        "ok": True,
        "schema": "voxmetrica.claim/v1",
        "outcome": "clarify",
        "needs_clarify": True,
        "confidence": 0.68,
        "margin": 0.02,
        "candidates": [
            {"speaker_id": "alex", "display_name": "Alex", "score": 0.68},
            {"speaker_id": "sam", "display_name": "Sam", "score": 0.66},
        ],
        "embed_backend": "hash_stub",
    }
    pending = begin_clarify("sess1", clarify_claim, query_embedding=q, root=data_root)
    assert pending["ok"] is True
    store = ClarifyStore(data_root)
    got = store.get("sess1")
    assert got is not None
    assert got["outcome"] == "clarify"
    assert len(got["candidates"]) == 2


def test_clarify_resolve_binds_candidate(data_root: Path, save_embedding):
    a = _unit(5)
    Gallery(data_root).enroll("alex", "Alex", [save_embedding("a", a)])
    claim = {
        "outcome": "clarify",
        "needs_clarify": True,
        "confidence": 0.70,
        "margin": 0.03,
        "candidates": [{"speaker_id": "alex", "display_name": "Alex", "score": 0.70}],
        "embed_backend": "hash_stub",
        "gallery_version": 1,
    }
    begin_clarify("s2", claim, query_embedding=a, root=data_root)
    out = clarify_resolve("s2", choice="alex", root=data_root, adapt=True)
    assert out["ok"] is True
    assert out["outcome"] == "matched"
    assert out["speaker_id"] == "alex"
    assert out["needs_clarify"] is False
    # pending cleared
    assert ClarifyStore(data_root).get("s2") is None


def test_clarify_resolve_guest(data_root: Path):
    claim = {
        "outcome": "clarify",
        "candidates": [{"speaker_id": "alex", "display_name": "Alex", "score": 0.70}],
        "confidence": 0.70,
        "margin": 0.01,
        "embed_backend": "hash_stub",
    }
    begin_clarify("s3", claim, root=data_root)
    out = clarify_resolve("s3", choice="guest", root=data_root)
    assert out["ok"] is True
    assert out["outcome"] == "unknown"
    assert out["speaker_id"] == "guest"


def test_clarify_resolve_rejects_unknown_choice(data_root: Path):
    claim = {
        "outcome": "clarify",
        "candidates": [{"speaker_id": "alex", "display_name": "Alex", "score": 0.70}],
        "confidence": 0.70,
        "margin": 0.01,
        "embed_backend": "hash_stub",
    }
    begin_clarify("s4", claim, root=data_root)
    out = clarify_resolve("s4", choice="not_a_person", root=data_root)
    assert out["ok"] is False


def test_clarify_expired(data_root: Path, monkeypatch):
    import os
    import time

    claim = {
        "outcome": "clarify",
        "candidates": [{"speaker_id": "alex", "display_name": "Alex", "score": 0.70}],
        "confidence": 0.7,
        "margin": 0.01,
        "embed_backend": "hash_stub",
    }
    begin_clarify("old", claim, root=data_root)
    path = ClarifyStore(data_root)._path("old")
    old = time.time() - 10_000
    os.utime(path, (old, old))
    out = clarify_resolve("old", choice="alex", root=data_root)
    assert out["ok"] is False
    assert out.get("code") in ("expired", "missing")
