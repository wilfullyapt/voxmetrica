from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from .paths import get_data_root, load_config
from .capabilities import load_template, save_capabilities


class Gallery:
    def __init__(self, root: Path | None = None):
        self.root = root or get_data_root()
        self.gallery = self.root / "gallery"
        self.index_path = self.gallery / "index.json"

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"version": 1, "people": {}}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, data: dict[str, Any]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def list_people(self) -> list[dict[str, Any]]:
        idx = self._load_index()
        out = []
        for sid, info in (idx.get("people") or {}).items():
            out.append({"speaker_id": sid, **info})
        return out

    def person_dir(self, speaker_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in speaker_id.strip())
        if not safe:
            raise ValueError("invalid speaker_id")
        return self.gallery / safe

    def get(self, speaker_id: str) -> dict[str, Any] | None:
        idx = self._load_index()
        info = (idx.get("people") or {}).get(speaker_id)
        if not info:
            return None
        return {"speaker_id": speaker_id, **info}

    def enroll(
        self,
        speaker_id: str,
        display_name: str,
        embedding_paths: list[Path],
        template: str | None = None,
        discord_user_ids: list[str] | None = None,
        notes: str = "",
        is_root_enrollment: bool = False,
    ) -> dict[str, Any]:
        """Register a speaker and store embeddings. Does not write root seal."""
        cfg = load_config(self.root)
        template = template or cfg.get("enroll", {}).get("default_template", "full-adult")
        pdir = self.person_dir(speaker_id)
        emb_dir = pdir / "embeddings"
        emb_dir.mkdir(parents=True, exist_ok=True)

        stored = []
        for i, src in enumerate(embedding_paths, start=1):
            dest = emb_dir / f"emb_{i:03d}{src.suffix or '.npy'}"
            shutil.copy2(src, dest)
            stored.append(str(dest.relative_to(pdir)))

        meta = {
            "display_name": display_name,
            "discord_user_ids": discord_user_ids or [],
            "notes": notes,
            "enrolled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "active": True,
            "embeddings": stored,
            "template_used": template,
        }
        (pdir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

        caps = load_template(template, self.root)
        caps["speaker_id"] = speaker_id
        caps["display_name"] = display_name
        caps["updated_by"] = "root" if is_root_enrollment else "system"
        caps["updated_at"] = meta["enrolled_at"]
        save_capabilities(speaker_id, caps, root=self.root)

        idx = self._load_index()
        idx.setdefault("people", {})[speaker_id] = {
            "display_name": display_name,
            "path": str(pdir.relative_to(self.gallery)),
            "enrolled_at": meta["enrolled_at"],
            "active": True,
            "embedding_count": len(stored),
        }
        self._save_index(idx)
        return {"ok": True, "speaker_id": speaker_id, "meta": meta, "capabilities": caps}

    def delete(self, speaker_id: str) -> dict[str, Any]:
        if speaker_id == "root":
            return {"ok": False, "error": "refuse to delete root via gallery; use control plane"}
        idx = self._load_index()
        if speaker_id not in (idx.get("people") or {}):
            return {"ok": False, "error": f"unknown speaker_id: {speaker_id}"}
        pdir = self.person_dir(speaker_id)
        if pdir.exists():
            shutil.rmtree(pdir)
        del idx["people"][speaker_id]
        self._save_index(idx)
        return {"ok": True, "deleted": speaker_id}

    def embedding_files(self, speaker_id: str) -> list[Path]:
        pdir = self.person_dir(speaker_id)
        emb_dir = pdir / "embeddings"
        if not emb_dir.exists():
            return []
        return sorted(emb_dir.glob("*.npy")) + sorted(emb_dir.glob("*.json"))
