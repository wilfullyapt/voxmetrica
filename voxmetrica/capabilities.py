from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

import yaml

from .paths import get_data_root


def _templates_dir(root: Path) -> Path:
    return root / "templates"


def load_template(name: str, root: Path | None = None) -> dict[str, Any]:
    root = root or get_data_root()
    path = _templates_dir(root) / f"{name}.yaml"
    if not path.exists():
        # bare name without .yaml already handled; try guest
        alt = _templates_dir(root) / "guest-default.yaml"
        if not alt.exists():
            return {
                "speaker_id": "guest",
                "display_name": "Guest",
                "mode": "allowlist",
                "resources": {"tools": {"allow": [], "deny": ["*"]}},
                "notes_for_model": "Guest — minimal access.",
            }
        path = alt
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def capabilities_path(speaker_id: str, root: Path | None = None) -> Path:
    root = root or get_data_root()
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in speaker_id.strip())
    return root / "gallery" / safe / "capabilities.yaml"


def load_capabilities(speaker_id: str, root: Path | None = None) -> dict[str, Any]:
    root = root or get_data_root()
    if speaker_id in ("guest", "unknown", ""):
        return load_template("guest-default", root)
    path = capabilities_path(speaker_id, root)
    if not path.exists():
        return load_template("guest-default", root)
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_capabilities(
    speaker_id: str,
    caps: dict[str, Any],
    root: Path | None = None,
    updated_by: str = "root",
) -> Path:
    root = root or get_data_root()
    path = capabilities_path(speaker_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = copy.deepcopy(caps)
    data["speaker_id"] = speaker_id
    data["updated_by"] = updated_by
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _match_list(value: str, rules: list[str]) -> bool:
    value = value or ""
    for r in rules or []:
        if r == "*":
            return True
        if r.endswith("*") and value.startswith(r[:-1]):
            return True
        if value == r:
            return True
    return False


def check_resource(
    caps: dict[str, Any],
    kind: str,
    name: str,
) -> dict[str, Any]:
    """Check whether a resource is allowed for these capabilities.

    kind: tools | toolsets | paths | memory_scopes | home
    mode: allowlist (default deny) | denylist (default allow)
    """
    resources = (caps or {}).get("resources") or {}
    block = resources.get(kind) or {}
    allow = block.get("allow") or []
    deny = block.get("deny") or []
    mode = (caps or {}).get("mode") or "allowlist"

    if _match_list(name, deny):
        return {"allowed": False, "reason": f"denied by {kind} deny list", "mode": mode}
    if mode == "denylist":
        return {"allowed": True, "reason": "denylist mode and not denied", "mode": mode}
    # allowlist
    if _match_list(name, allow):
        return {"allowed": True, "reason": f"allowed by {kind} allow list", "mode": mode}
    return {"allowed": False, "reason": f"not on {kind} allow list", "mode": mode}


def summarize_for_model(caps: dict[str, Any], claim: dict[str, Any] | None = None) -> str:
    sid = caps.get("speaker_id", "unknown")
    name = caps.get("display_name", sid)
    mode = caps.get("mode", "allowlist")
    notes = (caps.get("notes_for_model") or "").strip()
    lines = [
        "[VoxMetrica]",
        f"speaker_id: {sid}",
        f"display_name: {name}",
        f"mode: {mode}",
    ]
    if claim:
        lines.append(f"confidence: {claim.get('confidence', 'n/a')}")
        lines.append(f"is_root: {bool(claim.get('is_root'))}")
        if claim.get("outcome"):
            lines.append(f"outcome: {claim.get('outcome')}")
        if claim.get("needs_clarify"):
            lines.append("needs_clarify: true")
    res = caps.get("resources") or {}
    tools = res.get("tools") or {}
    if tools.get("allow"):
        lines.append("tools.allow: " + ", ".join(tools["allow"][:20]))
    if tools.get("deny"):
        lines.append("tools.deny: " + ", ".join(tools["deny"][:20]))
    if notes:
        lines.append("notes:")
        lines.append(notes)
    lines.append(
        "Enforce capability memory: refuse tools/paths/scopes not permitted for this speaker. "
        "Only root (is_root=true or local recovery CLI) may change other speakers' capabilities."
    )
    return "\n".join(lines)
