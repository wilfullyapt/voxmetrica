"""Hooks: inject speaker capability context; light audit."""

from __future__ import annotations

import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from lib.audit import AuditLog  # noqa: E402
from lib.capabilities import load_capabilities, summarize_for_model  # noqa: E402
from lib.claims import ClaimStore  # noqa: E402


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
    store = ClaimStore()
    sid = session_id or "default"
    claim = store.get(sid) or {
        "speaker_id": "guest",
        "display_name": "Guest",
        "confidence": 0.0,
        "is_root": False,
        "matched": False,
        "source": "default_guest",
    }
    caps = load_capabilities(claim.get("speaker_id") or "guest")
    text = summarize_for_model(caps, claim)
    return {"context": text}


def audit_tool_call(tool_name: str = "", args=None, result: str = "", task_id: str = "", **kwargs):
    """post_tool_call — audit voxmetrica_* and denied high-risk names later."""
    if not (tool_name or "").startswith("voxmetrica_"):
        return None
    try:
        claim = ClaimStore().get(task_id or "default") or {}
        AuditLog().log(
            "tool",
            claim.get("speaker_id"),
            {"tool": tool_name, "task_id": task_id},
        )
    except Exception:
        pass
    return None
