"""production: true must refuse hash_stub."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from voxmetrica.embedder import Embedder
from voxmetrica.paths import ensure_layout


def test_production_refuses_hash_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "prod"
    ensure_layout(root)
    (root / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "production": True,
                "identify": {"backend": "hash_stub", "accept_threshold": 0.75},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VOXMETRICA_ROOT", str(root))
    emb = Embedder(root=root)
    with pytest.raises(RuntimeError, match="hash_stub"):
        emb.resolve_backend()


def test_production_auto_without_speechbrain_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "prod2"
    ensure_layout(root)
    (root / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "production": True,
                "identify": {"backend": "auto"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VOXMETRICA_ROOT", str(root))
    emb = Embedder(root=root)
    # If speechbrain isn't installed, resolve must not silently fall back
    try:
        import speechbrain  # noqa: F401

        backend = emb.resolve_backend()
        assert backend == "speechbrain"
    except Exception:
        with pytest.raises(RuntimeError):
            emb.resolve_backend()


def test_dev_allows_hash_stub(data_root: Path):
    emb = Embedder(root=data_root, backend="hash_stub")
    assert emb.resolve_backend() == "hash_stub"
