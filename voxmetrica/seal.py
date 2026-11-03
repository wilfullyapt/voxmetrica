from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .paths import get_data_root


class SealError(Exception):
    pass


class Seal:
    """Root control-plane integrity seal.

    Not cryptographic hardware root-of-trust — file-integrity for fail-closed
    detection when non-root processes tamper with control/.
    """

    def __init__(self, root: Path | None = None):
        self.root = root or get_data_root()
        self.control = self.root / "control"
        self.seal_path = self.control / "root.seal"
        self.meta_path = self.control / "root.meta.json"
        self.emb_dir = self.control / "root_embeddings"

    def exists(self) -> bool:
        return self.seal_path.exists() and self.meta_path.exists()

    def _hash_embeddings(self) -> str:
        h = hashlib.sha256()
        if not self.emb_dir.exists():
            return h.hexdigest()
        for p in sorted(self.emb_dir.glob("*.npy")):
            h.update(p.name.encode())
            h.update(p.read_bytes())
        return h.hexdigest()

    def bootstrap(
        self,
        display_name: str = "Root",
        speaker_id: str = "root",
        discord_user_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        self.control.mkdir(parents=True, exist_ok=True)
        self.emb_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "speaker_id": speaker_id,
            "display_name": display_name,
            "discord_user_ids": discord_user_ids or [],
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "version": 1,
        }
        self.meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        seal = {
            "version": 1,
            "speaker_id": speaker_id,
            "embeddings_sha256": self._hash_embeddings(),
            "meta_sha256": hashlib.sha256(self.meta_path.read_bytes()).hexdigest(),
            "sealed_at": meta["created_at"],
        }
        self.seal_path.write_text(json.dumps(seal, indent=2) + "\n", encoding="utf-8")
        try:
            self.seal_path.chmod(0o600)
            self.meta_path.chmod(0o600)
            self.control.chmod(0o700)
        except OSError:
            pass
        return {"ok": True, "meta": meta, "seal": seal}

    def verify(self) -> dict[str, Any]:
        if not self.exists():
            return {"ok": False, "error": "root seal not initialized", "code": "no_seal"}
        seal = json.loads(self.seal_path.read_text(encoding="utf-8"))
        meta_hash = hashlib.sha256(self.meta_path.read_bytes()).hexdigest()
        emb_hash = self._hash_embeddings()
        problems = []
        if seal.get("meta_sha256") != meta_hash:
            problems.append("root.meta.json hash mismatch")
        if seal.get("embeddings_sha256") != emb_hash:
            problems.append("root embeddings hash mismatch")
        if problems:
            return {"ok": False, "error": "; ".join(problems), "code": "seal_break", "problems": problems}
        meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        return {"ok": True, "meta": meta, "seal": seal}

    def reseal(self) -> dict[str, Any]:
        """Recompute seal after legitimate root embedding rotation."""
        if not self.meta_path.exists():
            raise SealError("no root meta; run bootstrap first")
        seal = {
            "version": 1,
            "speaker_id": json.loads(self.meta_path.read_text(encoding="utf-8")).get("speaker_id", "root"),
            "embeddings_sha256": self._hash_embeddings(),
            "meta_sha256": hashlib.sha256(self.meta_path.read_bytes()).hexdigest(),
            "sealed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.seal_path.write_text(json.dumps(seal, indent=2) + "\n", encoding="utf-8")
        try:
            self.seal_path.chmod(0o600)
        except OSError:
            pass
        return {"ok": True, "seal": seal}
