"""VoxMetrica tool handlers — always return JSON strings."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Shared lib lives next to plugin: <pkg>/plugin → <pkg>/lib
_PKG = Path(__file__).resolve().parents[1]
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from voxmetrica.capabilities import load_capabilities  # noqa: E402
from voxmetrica.claims import ClaimStore  # noqa: E402
from voxmetrica.control_plane import ControlPlane  # noqa: E402
from voxmetrica.paths import get_data_root  # noqa: E402


def _j(obj: Any) -> str:
    return json.dumps(obj, default=str)


def _cp() -> ControlPlane:
    return ControlPlane(get_data_root())


def status(args: dict, **kwargs) -> str:
    return _j(_cp().status())


def whoami(args: dict, **kwargs) -> str:
    args = args or {}
    audio = (args.get("audio_path") or "").strip()
    session_id = (args.get("session_id") or kwargs.get("task_id") or "default").strip()
    store = ClaimStore()
    if audio:
        claim = _cp().whoami_from_audio(audio)
        if claim.get("ok"):
            store.put(session_id, claim)
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
            "reason": "no claim for session; send voice audio or identify with audio_path",
        }
    )


def list_people(args: dict, **kwargs) -> str:
    st = _cp().status()
    return _j({"ok": True, "people": st.get("people", []), "people_count": st.get("people_count")})


def enroll(args: dict, **kwargs) -> str:
    args = args or {}
    display_name = (args.get("display_name") or "").strip()
    audio_paths = args.get("audio_paths") or []
    if isinstance(audio_paths, str):
        audio_paths = [audio_paths]
    speaker_id = (args.get("speaker_id") or "").strip() or display_name.lower().replace(" ", "_")
    return _j(
        _cp().enroll_speaker(
            speaker_id=speaker_id,
            display_name=display_name,
            audio_paths=list(audio_paths),
            template=args.get("template"),
            discord_user_ids=args.get("discord_user_ids"),
            is_root_claim=bool(args.get("is_root_claim")),
            local_cli=bool(args.get("local_cli")),
            as_root_voice=bool(args.get("as_root_voice")),
        )
    )


def delete(args: dict, **kwargs) -> str:
    args = args or {}
    return _j(
        _cp().delete_speaker(
            speaker_id=(args.get("speaker_id") or "").strip(),
            is_root_claim=bool(args.get("is_root_claim")),
            local_cli=bool(args.get("local_cli")),
        )
    )


def get_capabilities(args: dict, **kwargs) -> str:
    args = args or {}
    sid = (args.get("speaker_id") or "guest").strip()
    caps = load_capabilities(sid)
    return _j({"ok": True, "speaker_id": sid, "capabilities": caps})


def set_capabilities(args: dict, **kwargs) -> str:
    args = args or {}
    return _j(
        _cp().set_capabilities(
            speaker_id=(args.get("speaker_id") or "").strip(),
            caps=args.get("capabilities"),
            caps_yaml_path=args.get("caps_yaml_path"),
            template=args.get("template"),
            is_root_claim=bool(args.get("is_root_claim")),
            local_cli=bool(args.get("local_cli")),
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
