#!/usr/bin/env python3
"""VoxMetrica local CLI — setup, bootstrap root, enroll, caps (recovery path)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))

from lib.control_plane import ControlPlane  # noqa: E402
from lib.paths import ensure_layout, get_data_root  # noqa: E402


def _print(obj):
    print(json.dumps(obj, indent=2, default=str))


def main(argv=None):
    p = argparse.ArgumentParser(prog="voxmetrica", description="VoxMetrica control CLI")
    p.add_argument("--root", default=None, help="Data root (default: VOXMETRICA_ROOT or ./data)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="Create directories and ensure layout")
    sub.add_parser("status", help="Show seal, people, backend")

    b = sub.add_parser("bootstrap-root", help="Initialize root seal (local recovery)")
    b.add_argument("--display-name", default="Root")
    b.add_argument("--audio", action="append", default=[], help="Root enrollment audio (repeatable)")

    e = sub.add_parser("enroll", help="Enroll a speaker (local root)")
    e.add_argument("--speaker-id", required=True)
    e.add_argument("--display-name", required=True)
    e.add_argument("--audio", action="append", required=True)
    e.add_argument("--template", default="full-adult")
    e.add_argument("--as-root-voice", action="store_true")

    d = sub.add_parser("delete", help="Delete speaker")
    d.add_argument("--speaker-id", required=True)

    g = sub.add_parser("get-caps", help="Print capabilities as JSON")
    g.add_argument("--speaker-id", required=True)

    s = sub.add_parser("set-caps", help="Set capabilities from template or file")
    s.add_argument("--speaker-id", required=True)
    s.add_argument("--template")
    s.add_argument("--yaml")

    w = sub.add_parser("whoami", help="Identify audio file")
    w.add_argument("--audio", required=True)

    c = sub.add_parser("check", help="Check resource permission")
    c.add_argument("--speaker-id", required=True)
    c.add_argument("--kind", default="tools")
    c.add_argument("--name", required=True)

    args = p.parse_args(argv)
    root = Path(args.root).resolve() if args.root else get_data_root()
    ensure_layout(root)
    cp = ControlPlane(root)

    if args.cmd == "setup":
        _print({"ok": True, "data_root": str(root), "layout": "ok"})
        return 0
    if args.cmd == "status":
        _print(cp.status())
        return 0
    if args.cmd == "bootstrap-root":
        _print(
            cp.bootstrap_root(
                display_name=args.display_name,
                audio_paths=args.audio or None,
                local_cli=True,
            )
        )
        return 0
    if args.cmd == "enroll":
        _print(
            cp.enroll_speaker(
                speaker_id=args.speaker_id,
                display_name=args.display_name,
                audio_paths=args.audio,
                template=args.template,
                local_cli=True,
                as_root_voice=args.as_root_voice,
            )
        )
        return 0
    if args.cmd == "delete":
        _print(cp.delete_speaker(args.speaker_id, local_cli=True))
        return 0
    if args.cmd == "get-caps":
        from lib.capabilities import load_capabilities

        _print({"ok": True, "capabilities": load_capabilities(args.speaker_id, root)})
        return 0
    if args.cmd == "set-caps":
        _print(
            cp.set_capabilities(
                speaker_id=args.speaker_id,
                template=args.template,
                caps_yaml_path=args.yaml,
                local_cli=True,
            )
        )
        return 0
    if args.cmd == "whoami":
        _print(cp.whoami_from_audio(args.audio))
        return 0
    if args.cmd == "check":
        _print(cp.check(args.speaker_id, args.kind, args.name))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
