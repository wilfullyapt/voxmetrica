"""Blank-start self-enroll and admin enroll ceremony."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .audit import AuditLog
from .control_plane import ControlPlane
from .embedder import Embedder
from .gallery import Gallery
from .paths import ensure_layout, get_data_root, load_config


def slugify_speaker_id(display_name: str, explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        raw = explicit.strip()
    else:
        raw = (display_name or "").strip().lower()
    raw = raw.replace(" ", "_")
    safe = re.sub(r"[^a-zA-Z0-9_\-]+", "", raw).strip("_-")
    safe = safe.lower() if not explicit else safe
    if not safe:
        raise ValueError("invalid speaker_id / display_name")
    return safe


def self_enroll(
    *,
    display_name: str,
    audio_paths: list[str],
    root: Path | None = None,
    speaker_id: str | None = None,
    template: str | None = None,
    local_cli: bool = False,
    is_root_claim: bool = False,
    discord_user_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Enroll a new voice when policy allows (blank house / unknown self-name).

    Does not require root when allow_self_enroll_when_unknown is true and
    either local_cli or open policy. Root approve path still works via ControlPlane.
    """
    root = root or get_data_root()
    ensure_layout(root)
    cfg = load_config(root)
    enroll_cfg = cfg.get("enroll") or {}
    min_clips = int(enroll_cfg.get("min_clips", 3))
    allow_self = bool(enroll_cfg.get("allow_self_enroll_when_unknown", True))
    root_required = bool(enroll_cfg.get("root_approve_required", False))

    if not display_name or not str(display_name).strip():
        return {"ok": False, "error": "display_name required", "code": "display_name"}

    paths = [str(p) for p in (audio_paths or []) if p]
    if len(paths) < min_clips:
        return {
            "ok": False,
            "error": f"min_clips={min_clips}; got {len(paths)}",
            "code": "min_clips",
            "min_clips": min_clips,
        }

    try:
        sid = slugify_speaker_id(display_name, speaker_id)
    except ValueError as e:
        return {"ok": False, "error": str(e), "code": "speaker_id"}

    gal = Gallery(root)
    if gal.get(sid):
        return {"ok": False, "error": f"speaker_id already enrolled: {sid}", "code": "exists"}

    # Authorization
    if root_required or not allow_self:
        cp = ControlPlane(root)
        auth = cp.assert_root_authorized(is_root_claim=is_root_claim, local_cli=local_cli)
        if not auth.get("ok"):
            return {
                "ok": False,
                "error": auth.get("error") or "self-enroll disabled; root approve required",
                "code": "auth",
                "auth": auth,
            }
        via = auth.get("via")
    else:
        # Open self-enroll: local CLI always OK; non-CLI allowed when policy open
        if not local_cli and not allow_self:
            return {"ok": False, "error": "self-enroll not allowed", "code": "auth"}
        via = "self_enroll" if allow_self else "local_cli"

    emb = Embedder(root)
    tmpdir = Path(tempfile.mkdtemp(prefix="vox-self-enroll-"))
    emb_files: list[Path] = []
    try:
        for i, ap in enumerate(paths, start=1):
            r = emb.embed(ap)
            if not r.get("ok"):
                return {"ok": False, "error": f"embed failed for {ap}: {r.get('error')}", "code": "embed"}
            dest = tmpdir / f"emb_{i:03d}.npy"
            emb.save_embedding(r["embedding"], dest)
            emb_files.append(dest)

        out = gal.enroll(
            speaker_id=sid,
            display_name=display_name.strip(),
            embedding_paths=emb_files,
            template=template or enroll_cfg.get("default_template", "full-adult"),
            discord_user_ids=discord_user_ids,
            is_root_enrollment=False,
        )
        # Bump gallery version
        idx = gal._load_index()
        idx["version"] = int(idx.get("version") or 1) + 1
        gal._save_index(idx)

        if enroll_cfg.get("delete_raw_after_embed", True):
            # raw paths are caller-owned; we only clean temp embeddings
            pass

        AuditLog(root).log(
            "self_enroll",
            sid,
            {"display_name": display_name, "via": via, "clips": len(paths)},
        )
        out["via"] = via
        out["gallery_version"] = idx["version"]
        return out
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
