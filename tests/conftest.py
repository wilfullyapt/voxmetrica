"""Shared fixtures — isolated VOXMETRICA_ROOT per test."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from voxmetrica.embedder import Embedder
from voxmetrica.paths import ensure_layout


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vox-data"
    ensure_layout(root)
    cfg = {
        "version": 1,
        "data_root": str(root),
        "production": False,
        "identify": {
            "accept_threshold": 0.75,
            "clarify_threshold": 0.55,
            "min_margin": 0.05,
            "min_seconds": 0.0,
            "backend": "hash_stub",
            "claim_ttl_seconds": 900,
        },
        "enroll": {
            "min_clips": 3,
            "delete_raw_after_embed": True,
            "default_template": "full-adult",
            "allow_self_enroll_when_unknown": True,
            "root_approve_required": False,
        },
        "guest": {"template": "guest-default"},
        "security": {
            "fail_closed_on_seal_break": True,
            "allow_local_cli_root": True,
        },
        "audit": {"sqlite_path": "audit/events.sqlite"},
    }
    (root / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    monkeypatch.setenv("VOXMETRICA_ROOT", str(root))
    return root


@pytest.fixture
def write_wav_bytes(tmp_path: Path):
    def _write(name: str, payload: bytes) -> Path:
        # Minimal RIFF-ish bytes; hash_stub only needs stable file bytes
        p = tmp_path / name
        p.write_bytes(payload)
        return p

    return _write


@pytest.fixture
def save_embedding(data_root: Path):
    def _save(name: str, vec: np.ndarray) -> Path:
        emb = Embedder(root=data_root, backend="hash_stub")
        dest = data_root / "enroll_raw" / f"{name}.npy"
        return emb.save_embedding(vec.astype(np.float32), dest)

    return _save
