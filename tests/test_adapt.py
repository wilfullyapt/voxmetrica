"""P4 — multi-embedding centroid + gated adapt."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from voxmetrica.adapt import adapt_append, speaker_centroid
from voxmetrica.gallery import Gallery
from voxmetrica.identify import identify_embedding
from voxmetrica.score import cosine


def _unit(seed: int, dim: int = 192) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def test_append_embedding_increases_count(data_root: Path, save_embedding):
    v1 = _unit(10)
    Gallery(data_root).enroll("alex", "Alex", [save_embedding("1", v1)])
    assert len(Gallery(data_root).embedding_files("alex")) == 1
    out = adapt_append("alex", _unit(11), root=data_root, reason="confirm", confirmed=True)
    assert out["ok"] is True
    assert len(Gallery(data_root).embedding_files("alex")) == 2


def test_adapt_requires_confirm_by_default(data_root: Path, save_embedding):
    Gallery(data_root).enroll("alex", "Alex", [save_embedding("1", _unit(1))])
    out = adapt_append("alex", _unit(2), root=data_root, reason="silent", confirmed=False)
    assert out["ok"] is False
    assert out.get("code") == "confirm_required"


def test_centroid_is_unit_mean(data_root: Path, save_embedding):
    a, b = _unit(20), _unit(21)
    Gallery(data_root).enroll("alex", "Alex", [save_embedding("a", a), save_embedding("b", b)])
    c = speaker_centroid("alex", root=data_root)
    assert c is not None
    assert abs(float(np.linalg.norm(c)) - 1.0) < 1e-4
    # centroid should be closer to both than orthogonal noise
    noise = _unit(99)
    assert cosine(c, a) > cosine(c, noise)


def test_identify_uses_centroid_boost(data_root: Path, save_embedding):
    """Query near centroid of two refs should match."""
    a, b = _unit(30), _unit(31)
    Gallery(data_root).enroll("alex", "Alex", [save_embedding("a", a), save_embedding("b", b)])
    c = speaker_centroid("alex", root=data_root)
    claim = identify_embedding(c, root=data_root, embed_backend="hash_stub")
    assert claim["outcome"] == "matched"
    assert claim["speaker_id"] == "alex"


def test_max_embeddings_cap(data_root: Path, save_embedding, monkeypatch):
    import yaml

    cfg = yaml.safe_load((data_root / "config.yaml").read_text())
    cfg.setdefault("adapt", {})
    cfg["adapt"]["max_embeddings_per_speaker"] = 3
    cfg["adapt"]["require_confirm"] = True
    (data_root / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    Gallery(data_root).enroll("alex", "Alex", [save_embedding("0", _unit(0))])
    for i in range(1, 5):
        adapt_append("alex", _unit(100 + i), root=data_root, confirmed=True, reason="test")
    assert len(Gallery(data_root).embedding_files("alex")) <= 3
