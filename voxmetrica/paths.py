from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Package root = repo root (parent of voxmetrica/ package dir)
_PKG_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ROOT = _PKG_ROOT / "data"

_DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "production": False,
    "identify": {
        "accept_threshold": 0.75,
        "clarify_threshold": 0.55,
        "min_margin": 0.05,
        "min_seconds": 1.5,
        "backend": "auto",
        "claim_ttl_seconds": 900,
        "threshold": 0.75,
    },
    "enroll": {
        "min_clips": 3,
        "delete_raw_after_embed": True,
        "default_template": "full-adult",
        "allow_self_enroll_when_unknown": True,
        "root_approve_required": False,
    },
    "guest": {"template": "guest-default"},
    "security": {"fail_closed_on_seal_break": True, "allow_local_cli_root": True},
    "audit": {"sqlite_path": "audit/events.sqlite"},
    "adapt": {
        "enabled": True,
        "require_confirm": True,
        "silent_enabled": False,
        "silent_min_score": 0.85,
        "silent_min_margin": 0.10,
        "max_embeddings_per_speaker": 20,
    },
    "sync": {"hub_url": None},
}


def get_data_root() -> Path:
    env = os.environ.get("VOXMETRICA_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    cfg_path = _PKG_ROOT / "config.yaml"
    if cfg_path.exists():
        try:
            with cfg_path.open("r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            dr = cfg.get("data_root")
            if dr and dr not in (".", "data", "./data"):
                return Path(dr).expanduser().resolve()
            if dr in (".", "data", "./data", None, ""):
                return (_PKG_ROOT / "data").resolve()
        except Exception:
            pass
    return _DEFAULT_ROOT.resolve()


def load_config(root: Path | None = None) -> dict[str, Any]:
    root = root or get_data_root()
    candidates = [root / "config.yaml", _PKG_ROOT / "config.yaml"]
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        return {**_DEFAULT_CONFIG, "data_root": str(root)}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out = {**_DEFAULT_CONFIG, **data}
    for key in ("identify", "enroll", "guest", "security", "audit", "adapt", "sync"):
        base = dict(_DEFAULT_CONFIG.get(key) or {})
        base.update(dict(data.get(key) or {}))
        out[key] = base
    out.setdefault("data_root", str(root))
    idc = out["identify"]
    if "accept_threshold" not in (data.get("identify") or {}) and "threshold" in idc:
        idc.setdefault("accept_threshold", idc.get("threshold", 0.75))
    return out


def ensure_layout(root: Path | None = None) -> Path:
    root = root or get_data_root()
    for rel in (
        "control/root_embeddings",
        "gallery",
        "templates",
        "claims",
        "clarify",
        "enroll_raw",
        "audit",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)
    index = root / "gallery" / "index.json"
    if not index.exists():
        index.write_text('{"version": 1, "people": {}}\n', encoding="utf-8")
    src_tpl = _PKG_ROOT / "templates"
    dst_tpl = root / "templates"
    if src_tpl.is_dir():
        for p in src_tpl.glob("*.yaml"):
            dest = dst_tpl / p.name
            if not dest.exists():
                dest.write_bytes(p.read_bytes())
    try:
        os.chmod(root / "control", 0o700)
    except OSError:
        pass
    return root


def package_root() -> Path:
    return _PKG_ROOT
