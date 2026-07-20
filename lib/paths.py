from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Package root = .../voxmetrica (parent of lib/)
_PKG_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ROOT = _PKG_ROOT / "data"


def get_data_root() -> Path:
    env = os.environ.get("VOXMETRICA_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # Prefer explicit config if present next to package
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
    # Config may live in data root or package root
    candidates = [root / "config.yaml", _PKG_ROOT / "config.yaml"]
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        return {
            "version": 1,
            "data_root": str(root),
            "identify": {"threshold": 0.75, "backend": "auto", "claim_ttl_seconds": 900},
            "enroll": {"min_clips": 1, "delete_raw_after_embed": True, "default_template": "full-adult"},
            "guest": {"template": "guest-default"},
            "security": {"fail_closed_on_seal_break": True, "allow_local_cli_root": True},
            "audit": {"sqlite_path": "audit/events.sqlite"},
        }
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("data_root", str(root))
    return data


def ensure_layout(root: Path | None = None) -> Path:
    root = root or get_data_root()
    for rel in (
        "control/root_embeddings",
        "gallery",
        "templates",
        "claims",
        "enroll_raw",
        "audit",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)
    index = root / "gallery" / "index.json"
    if not index.exists():
        index.write_text('{"version": 1, "people": {}}\n', encoding="utf-8")
    # Copy stock templates into data root if missing
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
