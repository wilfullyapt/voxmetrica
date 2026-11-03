"""Hooks: inject speaker capability context; gate tools; light audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from voxmetrica.audit import AuditLog  # noqa: E402
from voxmetrica.capabilities import load_capabilities, summarize_for_model  # noqa: E402
from voxmetrica.claims import ClaimStore  # noqa: E402
from voxmetrica.paths import get_data_root  # noqa: E402
from voxmetrica.policy import effective_speaker_id, gate_tool  # noqa: E402


def _session_claim(session_id: str = "", task_id: str = "") -> dict:
    sid = session_id or task_id or "default"
    return ClaimStore(get_data_root()).get(sid) or {
        "speaker_id": "guest",
        "display_name": "Guest",
        "confidence": 0.0,
        "is_root": False,
        "matched": False,
        "outcome": "unknown",
        "is_unknown": True,
        "source": "default_guest",
    }


def inject_speaker_context(
    session_id: str = "",
    user_message: str = "",
    conversation_history=None,
    is_first_turn: bool = False,
    model: str = "",
    platform: str = "",
    **kwargs,
):
    """pre_llm_call — inject VoxMetrica claim + capability notes."""
    root = get_data_root()
    sid = session_id or "default"
    claim = _session_claim(sid)
    eff = effective_speaker_id(claim)
    caps = load_capabilities(eff, root)
    text = summarize_for_model(caps, claim)
    extra = []
    if claim.get("outcome"):
        extra.append(f"claim.outcome: {claim.get('outcome')}")
    if claim.get("needs_clarify"):
        extra.append("needs_clarify: true — do not run privileged tools until clarify_resolve")
    if extra:
        text = text + "\n" + "\n".join(extra)
    return {"context": text}


def gate_tool_call(tool_name: str = "", args=None, task_id: str = "", session_id: str = "", **kwargs):
    """pre_tool_call — deny tools not permitted for current claim."""
    root = get_data_root()
    claim = _session_claim(session_id or task_id)
    decision = gate_tool(tool_name or "", claim, root=root)
    if decision.get("allowed"):
        return None  # allow
    try:
        AuditLog(root).log(
            "tool_denied",
            decision.get("speaker_id"),
            {"tool": tool_name, "reason": decision.get("reason"), "code": decision.get("code")},
        )
    except Exception:
        pass
    # Hermes plugin convention: return error / block payload
    return {
        "blocked": True,
        "error": decision.get("reason") or "not permitted for this speaker",
        "voxmetrica_gate": decision,
    }


def audit_tool_call(tool_name: str = "", args=None, result: str = "", task_id: str = "", **kwargs):
    """post_tool_call — audit voxmetrica_* calls."""
    if not (tool_name or "").startswith("voxmetrica_"):
        return None
    try:
        claim = _session_claim(task_id or "default")
        AuditLog(get_data_root()).log(
            "tool",
            claim.get("speaker_id"),
            {"tool": tool_name, "task_id": task_id},
        )
    except Exception:
        pass
    return None


def deny_message(decision: dict) -> str:
    return json.dumps(
        {
            "ok": False,
            "error": decision.get("reason"),
            "code": decision.get("code") or "denied",
            "speaker_id": decision.get("speaker_id"),
        }
    )
