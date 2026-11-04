"""Thin edge client — narthex / mobile-ami identify + enroll against hub gallery root."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .claims import ClaimStore
from .clarify import begin_clarify, clarify_resolve
from .enroll_flow import self_enroll
from .identify import identify_audio
from .paths import ensure_layout, get_data_root


class EdgeClient:
    """Library client for doorways. Does not talk HTTP yet — same-process or shared FS.

    Future: hub_url transport for remote VOXMETRICA_ROOT. Today: local root path /
    VOXMETRICA_ROOT shared via NFS/mount or same host.
    """

    def __init__(self, root: Path | str | None = None, *, ingress: str = "edge"):
        self.root = Path(root).resolve() if root else get_data_root()
        ensure_layout(self.root)
        self.ingress = ingress

    def identify(
        self,
        audio_path: str | Path,
        *,
        session_id: str | None = None,
        device_id: str | None = None,
        auto_clarify_pending: bool = True,
    ) -> dict[str, Any]:
        claim = identify_audio(
            audio_path,
            root=self.root,
            ingress=self.ingress,
            device_id=device_id,
        )
        if session_id:
            ClaimStore(self.root).put(session_id, claim)
            if auto_clarify_pending and claim.get("outcome") == "clarify":
                # stash pending without re-embed
                begin_clarify(session_id, claim, root=self.root)
        return claim

    def enroll_self(
        self,
        display_name: str,
        audio_paths: list[str | Path],
        *,
        speaker_id: str | None = None,
        template: str | None = None,
    ) -> dict[str, Any]:
        return self_enroll(
            display_name=display_name,
            audio_paths=[str(p) for p in audio_paths],
            root=self.root,
            speaker_id=speaker_id,
            template=template,
            local_cli=True,
        )

    def resolve_clarify(
        self,
        session_id: str,
        choice: str,
        *,
        adapt: bool = True,
    ) -> dict[str, Any]:
        return clarify_resolve(session_id, choice, root=self.root, adapt=adapt)

    def badge(self, claim: dict[str, Any] | None) -> str:
        """Short OLED / glass greeting line."""
        claim = claim or {}
        if claim.get("outcome") == "matched":
            return f"Hello, {claim.get('display_name') or claim.get('speaker_id')}"
        if claim.get("outcome") == "clarify" or claim.get("needs_clarify"):
            names = [c.get("display_name") or c.get("speaker_id") for c in (claim.get("candidates") or [])[:2]]
            if names:
                return "Are you " + " or ".join(str(n) for n in names) + "?"
            return "Who is speaking?"
        return "I don't know this voice yet. Who is speaking?"


def identify_clip(
    audio_path: str | Path,
    *,
    root: Path | str | None = None,
    ingress: str = "edge",
    session_id: str | None = None,
    device_id: str | None = None,
) -> dict[str, Any]:
    return EdgeClient(root, ingress=ingress).identify(
        audio_path, session_id=session_id, device_id=device_id
    )
