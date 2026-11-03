#!/usr/bin/env python3
"""VoxMetrica local CLI — setup, bootstrap root, enroll, caps (recovery path)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    from voxmetrica.control_plane import ControlPlane
    from voxmetrica.enroll_flow import self_enroll
    from voxmetrica.paths import ensure_layout, get_data_root

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

    se = sub.add_parser("enroll-self", help="Blank-start self-enroll (name + clips)")
    se.add_argument("--display-name", required=True)
    se.add_argument("--speaker-id", default=None)
    se.add_argument("--audio", action="append", required=True)
    se.add_argument("--template", default=None)

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
    w.add_argument("--ingress", default="cli")

    c = sub.add_parser("check", help="Check resource permission")
    c.add_argument("--speaker-id", required=True)
    c.add_argument("--kind", default="tools")
    c.add_argument("--name", required=True)

    cr = sub.add_parser("clarify-resolve", help="Resolve pending clarify session")
    cr.add_argument("--session-id", required=True)
    cr.add_argument("--choice", required=True, help="speaker_id | guest")
    cr.add_argument("--no-adapt", action="store_true")

    ad = sub.add_parser("adapt", help="Append embedding from audio (confirmed)")
    ad.add_argument("--speaker-id", required=True)
    ad.add_argument("--audio", required=True)
    ad.add_argument("--reason", default="manual")

    sx = sub.add_parser("sync-export", help="Export voxmetrica-sync-v1 package")
    sx.add_argument("--dest", required=True)

    si = sub.add_parser("sync-import", help="Import voxmetrica-sync-v1 package")
    si.add_argument("--src", required=True)

    args = p.parse_args(argv)
    root = Path(args.root).resolve() if args.root else get_data_root()
    ensure_layout(root)
    cp = ControlPlane(root)

    if args.cmd == "setup":
        _print({"ok": True, "data_root": str(root), "layout": "ok"})
        return 0
    if args.cmd == "status":
        st = cp.status()
        # surface new thresholds
        from voxmetrica.paths import load_config

        idc = load_config(root).get("identify") or {}
        st["thresholds"] = {
            "accept": idc.get("accept_threshold", idc.get("threshold")),
            "clarify": idc.get("clarify_threshold"),
            "min_margin": idc.get("min_margin"),
        }
        _print(st)
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
    if args.cmd == "enroll-self":
        _print(
            self_enroll(
                display_name=args.display_name,
                audio_paths=args.audio,
                root=root,
                speaker_id=args.speaker_id,
                template=args.template,
                local_cli=True,
            )
        )
        return 0
    if args.cmd == "delete":
        _print(cp.delete_speaker(args.speaker_id, local_cli=True))
        return 0
    if args.cmd == "get-caps":
        from voxmetrica.capabilities import load_capabilities

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
    if args.cmd == "clarify-resolve":
        from voxmetrica.clarify import clarify_resolve

        _print(
            clarify_resolve(
                args.session_id,
                args.choice,
                root=root,
                adapt=not args.no_adapt,
            )
        )
        return 0
    if args.cmd == "adapt":
        from voxmetrica.adapt import adapt_from_audio

        _print(
            adapt_from_audio(
                args.speaker_id,
                args.audio,
                root=root,
                confirmed=True,
                reason=args.reason,
            )
        )
        return 0
    if args.cmd == "sync-export":
        from voxmetrica.sync import export_sync_package

        _print(export_sync_package(root, args.dest))
        return 0
    if args.cmd == "sync-import":
        from voxmetrica.sync import import_sync_package

        _print(import_sync_package(args.src, root))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
