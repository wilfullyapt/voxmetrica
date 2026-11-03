"""VoxMetrica tool handlers — always return JSON strings."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_PKG = Path(__file__).resolve().parents[1]
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from voxmetrica.adapt import adapt_from_audio  # noqa: E402
from voxmetrica.capabilities import load_capabilities  # noqa: E402
from voxmetrica.claims import ClaimStore  # noqa: E402
from voxmetrica.clarify import begin_clarify, clarify_resolve  # noqa: E402
from voxmetrica.control_plane import ControlPlane  # noqa: E402
from voxmetrica.paths import get_data_root  # noqa: E402
from voxmetrica.policy import effective_speaker_id, gate_tool  # noqa: E402
from voxmetrica.sync import export_sync_package, import_sync_package  # noqa: E402


def _j(obj: Any) -> str:
    return json.dumps(obj, default=str)


def _cp() -> ControlPlane:
    return ControlPlane(get_data_root())


def _claim(session_id: str | None = None, kwargs: dict | None = None) -> dict[str, Any]:
    kwargs = kwargs or {}
    sid = (session_id or kwargs.get("task_id") or "default")
    if isinstance(sid, str):
        sid = sid.strip() or "default"
    return ClaimStore(get_data_root()).get(str(sid)) or {
        "speaker_id": "guest",
        "matched": False,
        "is_root": False,
        "outcome": "unknown",
    }


def _require_root(tool_name: str, kwargs: dict) -> str | None:
    claim = _claim(kwargs.get("session_id"), kwargs)
    decision = gate_tool(tool_name, claim, root=get_data_root())
    if not decision.get("allowed"):
        return _j(
            {
                "ok": False,
                "error": decision.get("reason"),
                "code": decision.get("code") or "denied",
                "speaker_id": decision.get("speaker_id"),
            }
        )
    return None


def status(args: dict, **kwargs) -> str:
    return _j(_cp().status())


def whoami(args: dict, **kwargs) -> str:
    args = args or {}
    audio = (args.get("audio_path") or "").strip()
    session_id = (args.get("session_id") or kwargs.get("task_id") or "default").strip()
    store = ClaimStore(get_data_root())
    if audio:
        claim = _cp().whoami_from_audio(audio)
        if claim.get("ok"):
            store.put(session_id, claim)
            if claim.get("outcome") == "clarify":
                begin_clarify(session_id, claim, root=get_data_root())
        return _j(claim)
    claim = store.get(session_id)
    if claim:
        return _j({"ok": True, "source": "session_claim", **claim})
    return _j(
        {
            "ok": True,
            "source": "none",
            "speaker_id": "guest",
            "display_name": "Guest",
            "is_root": False,
            "matched": False,
            "outcome": "unknown",
            "reason": "no claim for session; send voice audio or identify with audio_path",
        }
    )


def list_people(args: dict, **kwargs) -> str:
    st = _cp().status()
    return _j({"ok": True, "people": st.get("people", []), "people_count": st.get("people_count")})


def enroll(args: dict, **kwargs) -> str:
    denied = _require_root("voxmetrica_enroll", kwargs)
    if denied:
        return denied
    args = args or {}
    display_name = (args.get("display_name") or "").strip()
    audio_paths = args.get("audio_paths") or []
    if isinstance(audio_paths, str):
        audio_paths = [audio_paths]
    speaker_id = (args.get("speaker_id") or "").strip() or display_name.lower().replace(" ", "_")
    # Never trust client local_cli / is_root_claim — root already verified via claim
    return _j(
        _cp().enroll_speaker(
            speaker_id=speaker_id,
            display_name=display_name,
            audio_paths=list(audio_paths),
            template=args.get("template"),
            discord_user_ids=args.get("discord_user_ids"),
            is_root_claim=True,
            local_cli=False,
            as_root_voice=bool(args.get("as_root_voice")),
        )
    )


def delete(args: dict, **kwargs) -> str:
    denied = _require_root("voxmetrica_delete", kwargs)
    if denied:
        return denied
    args = args or {}
    return _j(
        _cp().delete_speaker(
            speaker_id=(args.get("speaker_id") or "").strip(),
            is_root_claim=True,
            local_cli=False,
        )
    )


def get_capabilities(args: dict, **kwargs) -> str:
    args = args or {}
    claim = _claim(args.get("session_id"), kwargs)
    req = (args.get("speaker_id") or "guest").strip()
    eff = effective_speaker_id(claim)
    if not (claim.get("is_root") and claim.get("matched")) and req not in (eff, "guest", ""):
        return _j({"ok": False, "error": "can only read own capabilities unless root", "code": "forbidden"})
    sid = req or eff
    caps = load_capabilities(sid, get_data_root())
    return _j({"ok": True, "speaker_id": sid, "capabilities": caps})


def set_capabilities(args: dict, **kwargs) -> str:
    denied = _require_root("voxmetrica_set_capabilities", kwargs)
    if denied:
        return denied
    args = args or {}
    return _j(
        _cp().set_capabilities(
            speaker_id=(args.get("speaker_id") or "").strip(),
            caps=args.get("capabilities"),
            caps_yaml_path=args.get("caps_yaml_path"),
            template=args.get("template"),
            is_root_claim=True,
            local_cli=False,
        )
    )


def check(args: dict, **kwargs) -> str:
    args = args or {}
    return _j(
        _cp().check(
            speaker_id=(args.get("speaker_id") or "guest").strip(),
            kind=(args.get("kind") or "tools").strip(),
            name=(args.get("name") or "").strip(),
        )
    )


def clarify_resolve_tool(args: dict, **kwargs) -> str:
    args = args or {}
    session_id = (args.get("session_id") or kwargs.get("task_id") or "default").strip()
    choice = (args.get("choice") or "").strip()
    adapt = bool(args.get("adapt", True))
    out = clarify_resolve(session_id, choice, root=get_data_root(), adapt=adapt)
    if out.get("ok") is not False and out.get("outcome"):
        ClaimStore(get_data_root()).put(session_id, out)
    return _j(out)


def adapt_tool(args: dict, **kwargs) -> str:
    denied = _require_root("voxmetrica_adapt", kwargs)
    if denied:
        return denied
    args = args or {}
    return _j(
        adapt_from_audio(
            (args.get("speaker_id") or "").strip(),
            args.get("audio_path") or "",
            root=get_data_root(),
            confirmed=True,
            reason=str(args.get("reason") or "plugin"),
        )
    )


def sync_export_tool(args: dict, **kwargs) -> str:
    claim = _claim(kwargs.get("session_id"), kwargs)
    if not (claim.get("is_root") and claim.get("matched")):
        return _j({"ok": False, "error": "root claim required for sync export", "code": "root_required"})
    args = args or {}
    dest = args.get("dest") or ""
    if not dest:
        return _j({"ok": False, "error": "dest required"})
    return _j(export_sync_package(get_data_root(), dest))


def sync_import_tool(args: dict, **kwargs) -> str:
    denied = _require_root("voxmetrica_sync_import", kwargs)
    if denied:
        return denied
    args = args or {}
    src = args.get("src") or ""
    if not src:
        return _j({"ok": False, "error": "src required"})
    return _j(import_sync_package(src, get_data_root()))
