"""VoxMetrica Hermes plugin — registration."""

from __future__ import annotations

import logging
from pathlib import Path

from . import schemas, tools
from .hooks import audit_tool_call, inject_speaker_context

logger = logging.getLogger(__name__)


def _slash_family(raw: str) -> str:
    """In-session slash helper: /vox <status|whoami|list|help>."""
    parts = (raw or "").strip().split()
    cmd = parts[0].lower() if parts else "help"
    if cmd in ("help", ""):
        return (
            "VoxMetrica commands:\n"
            "  /vox status\n"
            "  /vox whoami [audio_path]\n"
            "  /vox list\n"
            "Root ops use tools or: python scripts/voxmetrica_cli.py …"
        )
    if cmd == "status":
        return tools.status({})
    if cmd == "list":
        return tools.list_people({})
    if cmd == "whoami":
        audio = parts[1] if len(parts) > 1 else ""
        return tools.whoami({"audio_path": audio} if audio else {})
    return f"Unknown /vox subcommand: {cmd}. Try /vox help"


def register(ctx):
    ctx.register_tool(
        name="voxmetrica_status",
        toolset="voxmetrica",
        schema=schemas.STATUS,
        handler=tools.status,
    )
    ctx.register_tool(
        name="voxmetrica_whoami",
        toolset="voxmetrica",
        schema=schemas.WHOAMI,
        handler=tools.whoami,
    )
    ctx.register_tool(
        name="voxmetrica_list",
        toolset="voxmetrica",
        schema=schemas.LIST,
        handler=tools.list_people,
    )
    ctx.register_tool(
        name="voxmetrica_enroll",
        toolset="voxmetrica",
        schema=schemas.ENROLL,
        handler=tools.enroll,
    )
    ctx.register_tool(
        name="voxmetrica_delete",
        toolset="voxmetrica",
        schema=schemas.DELETE,
        handler=tools.delete,
    )
    ctx.register_tool(
        name="voxmetrica_get_capabilities",
        toolset="voxmetrica",
        schema=schemas.GET_CAPS,
        handler=tools.get_capabilities,
    )
    ctx.register_tool(
        name="voxmetrica_set_capabilities",
        toolset="voxmetrica",
        schema=schemas.SET_CAPS,
        handler=tools.set_capabilities,
    )
    ctx.register_tool(
        name="voxmetrica_check",
        toolset="voxmetrica",
        schema=schemas.CHECK,
        handler=tools.check,
    )

    ctx.register_hook("pre_llm_call", inject_speaker_context)
    ctx.register_hook("post_tool_call", audit_tool_call)

    try:
        ctx.register_command("vox", _slash_family, description="VoxMetrica voice biometrics")
    except Exception as e:
        logger.debug("register_command skipped: %s", e)

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                try:
                    ctx.register_skill(child.name, skill_md)
                except Exception as e:
                    logger.debug("register_skill %s: %s", child.name, e)

    logger.info("VoxMetrica plugin registered")
