"""Turn-time policy: inject context + gate tools from claim + caps."""

from __future__ import annotations

from typing import Any

from .capabilities import check_resource, load_capabilities

# Mutations that must never run on guest / non-root claims from the agent path
ROOT_ONLY_TOOLS = frozenset(
    {
        "voxmetrica_enroll",
        "voxmetrica_delete",
        "voxmetrica_set_capabilities",
        "voxmetrica_sync_import",
        "voxmetrica_adapt",
        "voxmetrica_bootstrap_root",
    }
)

# Always allow these for any speaker (including guest) so identity can progress
ALWAYS_ALLOW = frozenset(
    {
        "voxmetrica_status",
        "voxmetrica_whoami",
        "voxmetrica_list",
        "voxmetrica_check",
        "voxmetrica_get_capabilities",
        "voxmetrica_clarify_resolve",
        "clarify",
        "tts",
    }
)


def effective_speaker_id(claim: dict[str, Any] | None) -> str:
    claim = claim or {}
    if claim.get("is_root") and claim.get("matched"):
        return claim.get("speaker_id") or "root"
    outcome = claim.get("outcome")
    if outcome in ("clarify", "unknown") or claim.get("needs_clarify") or claim.get("is_unknown"):
        return "guest"
    if claim.get("matched") and claim.get("speaker_id"):
        return str(claim["speaker_id"])
    return "guest"


def gate_tool(
    tool_name: str,
    claim: dict[str, Any] | None,
    *,
    root: Any = None,
) -> dict[str, Any]:
    """Return {allowed: bool, reason, speaker_id, ...} for a tool call."""
    name = (tool_name or "").strip()
    if not name:
        return {"allowed": False, "reason": "empty tool name", "speaker_id": "guest"}

    claim = claim or {}
    sid = effective_speaker_id(claim)
    is_root = bool(claim.get("is_root") and claim.get("matched"))

    if name in ALWAYS_ALLOW and name not in ROOT_ONLY_TOOLS:
        # get_capabilities: allow self or guest; others filtered in handler
        return {
            "allowed": True,
            "reason": "identity/status path always allowed",
            "speaker_id": sid,
            "is_root": is_root,
        }

    if name in ROOT_ONLY_TOOLS:
        if not is_root:
            return {
                "allowed": False,
                "reason": "root claim required for this VoxMetrica mutation",
                "speaker_id": sid,
                "is_root": False,
                "code": "root_required",
            }
        return {
            "allowed": True,
            "reason": "root claim",
            "speaker_id": sid,
            "is_root": True,
        }

    # Dangerous tools while clarify/unknown → guest caps
    caps = load_capabilities(sid, root=root)
    result = check_resource(caps, "tools", name)
    result["speaker_id"] = sid
    result["is_root"] = is_root
    result["claim_outcome"] = claim.get("outcome")
    return result
