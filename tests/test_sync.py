"""P5 — signature sync export/import."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from voxmetrica.gallery import Gallery
from voxmetrica.identify import identify_embedding
from voxmetrica.paths import ensure_layout
from voxmetrica.sync import export_sync_package, import_sync_package


def _unit(seed: int, dim: int = 192) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def test_export_import_roundtrip(data_root: Path, save_embedding, tmp_path: Path, monkeypatch):
    v = _unit(7)
    Gallery(data_root).enroll("alex", "Alex", [save_embedding("a", v)], template="full-adult")
    pkg = tmp_path / "pkg"
    out = export_sync_package(data_root, pkg)
    assert out["ok"] is True
    assert (pkg / "manifest.json").exists()
    assert (pkg / "gallery" / "index.json").exists()

    dest = tmp_path / "dest-root"
    ensure_layout(dest)
    (dest / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "production": False,
                "identify": {"backend": "hash_stub", "accept_threshold": 0.75, "clarify_threshold": 0.55, "min_margin": 0.05},
                "enroll": {"min_clips": 1, "default_template": "full-adult"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VOXMETRICA_ROOT", str(dest))
    imp = import_sync_package(pkg, dest)
    assert imp["ok"] is True
    people = Gallery(dest).list_people()
    assert any(p["speaker_id"] == "alex" for p in people)
    claim = identify_embedding(v, root=dest, embed_backend="hash_stub")
    assert claim["outcome"] == "matched"
    assert claim["speaker_id"] == "alex"


def test_import_refuses_backend_mismatch(data_root: Path, save_embedding, tmp_path: Path):
    Gallery(data_root).enroll("alex", "Alex", [save_embedding("a", _unit(1))])
    pkg = tmp_path / "pkg2"
    export_sync_package(data_root, pkg, embed_backend="hash_stub")
    # tamper manifest backend
    import json

    man = json.loads((pkg / "manifest.json").read_text())
    man["embed_backend"] = "speechbrain-ecapa"
    (pkg / "manifest.json").write_text(json.dumps(man), encoding="utf-8")

    dest = tmp_path / "d2"
    ensure_layout(dest)
    (dest / "config.yaml").write_text(
        yaml.safe_dump({"identify": {"backend": "hash_stub"}, "production": False}),
        encoding="utf-8",
    )
    out = import_sync_package(pkg, dest, expected_backend="hash_stub")
    assert out["ok"] is False
    assert "backend" in (out.get("error") or "").lower() or out.get("code") == "backend_mismatch"
