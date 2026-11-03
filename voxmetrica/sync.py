"""Signature sync package export/import (embeddings + meta + caps; no raw wav)."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from .audit import AuditLog
from .embedder import Embedder
from .gallery import Gallery
from .paths import ensure_layout, get_data_root, load_config

SYNC_FORMAT = "voxmetrica-sync-v1"


def _resolved_backend_label(root: Path) -> str:
    cfg = load_config(root)
    backend = (cfg.get("identify") or {}).get("backend", "auto")
    if backend == "hash_stub":
        return "hash_stub"
    if backend == "speechbrain":
        return "speechbrain-ecapa"
    try:
        b = Embedder(root).resolve_backend()
        return "speechbrain-ecapa" if b == "speechbrain" else b
    except Exception:
        return str(backend)


def export_sync_package(
    root: Path | None,
    dest: str | Path,
    *,
    embed_backend: str | None = None,
    device_id: str | None = None,
    include_control: bool = False,
) -> dict[str, Any]:
    root = root or get_data_root()
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    gal_src = root / "gallery"
    gal_dst = dest / "gallery"
    if gal_src.exists():
        shutil.copytree(gal_src, gal_dst)
    else:
        gal_dst.mkdir()
        (gal_dst / "index.json").write_text('{"version": 1, "people": {}}\n', encoding="utf-8")

    idx = Gallery(root)._load_index()
    backend = embed_backend or _resolved_backend_label(root)
    manifest = {
        "format": SYNC_FORMAT,
        "gallery_version": int(idx.get("version") or 1),
        "embed_backend": backend,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "device_id": device_id,
        "people_count": len(idx.get("people") or {}),
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if include_control:
        ctrl = root / "control"
        if ctrl.exists():
            # copy meta only by default — embeddings optional; seals stay hub-local unless forced
            cdest = dest / "control"
            cdest.mkdir(exist_ok=True)
            for name in ("root.meta.json",):
                p = ctrl / name
                if p.exists():
                    shutil.copy2(p, cdest / name)

    AuditLog(root).log("sync_export", None, {"dest": str(dest), "backend": backend})
    return {"ok": True, "path": str(dest), "manifest": manifest}


def import_sync_package(
    src: str | Path,
    root: Path | None = None,
    *,
    expected_backend: str | None = None,
    replace: bool = True,
) -> dict[str, Any]:
    root = root or get_data_root()
    ensure_layout(root)
    src = Path(src)
    man_path = src / "manifest.json"
    if not man_path.exists():
        return {"ok": False, "error": "missing manifest.json", "code": "bad_package"}
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    if manifest.get("format") != SYNC_FORMAT:
        return {"ok": False, "error": f"unsupported format: {manifest.get('format')}", "code": "format"}

    pkg_backend = manifest.get("embed_backend") or "unknown"
    want = expected_backend or _resolved_backend_label(root)
    # normalize speechbrain labels
    def norm(b: str) -> str:
        b = (b or "").lower()
        if "speechbrain" in b or "ecapa" in b:
            return "speechbrain-ecapa"
        return b

    if want and pkg_backend and norm(want) != norm(str(pkg_backend)):
        # allow unknown want only if hash_stub both
        if not (norm(want) == norm(str(pkg_backend))):
            return {
                "ok": False,
                "error": f"embed backend mismatch: package={pkg_backend} expected={want}",
                "code": "backend_mismatch",
            }

    gal_src = src / "gallery"
    if not gal_src.exists():
        return {"ok": False, "error": "missing gallery/", "code": "bad_package"}

    gal_dst = root / "gallery"
    if replace and gal_dst.exists():
        # merge people: replace listed speakers from package
        idx_src = json.loads((gal_src / "index.json").read_text(encoding="utf-8")) if (gal_src / "index.json").exists() else {"people": {}}
        for sid in (idx_src.get("people") or {}):
            sp = gal_src / sid
            if sp.exists():
                target = gal_dst / sid
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(sp, target)
        # merge index
        gal = Gallery(root)
        idx = gal._load_index()
        idx.setdefault("people", {}).update(idx_src.get("people") or {})
        idx["version"] = max(int(idx.get("version") or 1), int(manifest.get("gallery_version") or 1))
        # bump
        idx["version"] = int(idx["version"]) + 0  # keep max
        if int(manifest.get("gallery_version") or 0) > int(idx.get("version") or 0):
            idx["version"] = int(manifest["gallery_version"])
        gal._save_index(idx)
    else:
        if gal_dst.exists():
            shutil.rmtree(gal_dst)
        shutil.copytree(gal_src, gal_dst)

    AuditLog(root).log(
        "sync_import",
        None,
        {"src": str(src), "backend": pkg_backend, "gallery_version": manifest.get("gallery_version")},
    )
    return {
        "ok": True,
        "manifest": manifest,
        "people_count": len(Gallery(root).list_people()),
        "gallery_version": Gallery(root)._load_index().get("version"),
    }
