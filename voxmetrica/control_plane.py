from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from .audit import AuditLog
from .capabilities import check_resource, load_capabilities, load_template, save_capabilities
from .embedder import Embedder
from .gallery import Gallery
from .identify import identify_audio
from .paths import ensure_layout, get_data_root, load_config
from .seal import Seal


class ControlPlane:
    """Root-gated mutations: enroll, set caps, delete, bootstrap."""

    def __init__(self, root: Path | None = None):
        self.root = root or get_data_root()
        ensure_layout(self.root)
        self.seal = Seal(self.root)
        self.gallery = Gallery(self.root)
        self.audit = AuditLog(self.root)

    def status(self) -> dict[str, Any]:
        cfg = load_config(self.root)
        seal_v = self.seal.verify() if self.seal.exists() else {"ok": False, "code": "no_seal"}
        people = self.gallery.list_people()
        backend = "unknown"
        try:
            backend = Embedder(self.root).resolve_backend()
        except Exception as e:
            backend = f"error:{e}"
        idc = cfg.get("identify") or {}
        return {
            "ok": True,
            "data_root": str(self.root),
            "seal": seal_v,
            "people_count": len(people),
            "people": people,
            "embed_backend": backend,
            "threshold": idc.get("accept_threshold", idc.get("threshold")),
            "thresholds": {
                "accept": idc.get("accept_threshold", idc.get("threshold")),
                "clarify": idc.get("clarify_threshold"),
                "min_margin": idc.get("min_margin"),
            },
            "production": bool(cfg.get("production", False)),
            "config_version": cfg.get("version"),
        }

    def assert_root_authorized(self, *, is_root_claim: bool = False, local_cli: bool = False) -> dict[str, Any]:
        cfg = load_config(self.root)
        if local_cli and cfg.get("security", {}).get("allow_local_cli_root", True):
            return {"ok": True, "via": "local_cli"}
        if is_root_claim:
            if self.seal.exists():
                v = self.seal.verify()
                if not v.get("ok") and cfg.get("security", {}).get("fail_closed_on_seal_break", True):
                    return {"ok": False, "error": "seal broken; fail closed", "seal": v}
            return {"ok": True, "via": "root_claim"}
        return {"ok": False, "error": "root authorization required (root voice claim or local CLI)"}

    def bootstrap_root(
        self,
        display_name: str = "Root",
        audio_paths: list[str] | None = None,
        local_cli: bool = True,
    ) -> dict[str, Any]:
        auth = self.assert_root_authorized(local_cli=local_cli)
        if not auth.get("ok"):
            return auth
        result = self.seal.bootstrap(display_name=display_name)
        embedded = []
        if audio_paths:
            emb = Embedder(self.root)
            for i, ap in enumerate(audio_paths, start=1):
                r = emb.embed(ap)
                if not r.get("ok"):
                    return {"ok": False, "error": f"embed failed for {ap}: {r.get('error')}"}
                dest = self.root / "control" / "root_embeddings" / f"emb_{i:03d}.npy"
                emb.save_embedding(r["embedding"], dest)
                embedded.append(str(dest))
            self.seal.reseal()
        self.audit.log("root_bootstrap", "root", {"display_name": display_name, "embeddings": embedded})
        return {"ok": True, "bootstrap": result, "embeddings": embedded, "auth": auth}

    def enroll_speaker(
        self,
        speaker_id: str,
        display_name: str,
        audio_paths: list[str],
        template: str | None = None,
        discord_user_ids: list[str] | None = None,
        *,
        is_root_claim: bool = False,
        local_cli: bool = False,
        as_root_voice: bool = False,
    ) -> dict[str, Any]:
        auth = self.assert_root_authorized(is_root_claim=is_root_claim, local_cli=local_cli)
        if not auth.get("ok"):
            return auth
        if not audio_paths:
            return {"ok": False, "error": "at least one audio_path required"}

        emb = Embedder(self.root)
        tmpdir = Path(tempfile.mkdtemp(prefix="vox-enroll-"))
        emb_files: list[Path] = []
        try:
            for i, ap in enumerate(audio_paths, start=1):
                r = emb.embed(ap)
                if not r.get("ok"):
                    return {"ok": False, "error": f"embed failed for {ap}: {r.get('error')}"}
                dest = tmpdir / f"emb_{i:03d}.npy"
                emb.save_embedding(r["embedding"], dest)
                emb_files.append(dest)

            if as_root_voice:
                # Store under control/ and reseal — does not create gallery person
                for i, f in enumerate(emb_files, start=1):
                    dest = self.root / "control" / "root_embeddings" / f"emb_{i:03d}.npy"
                    shutil.copy2(f, dest)
                if not self.seal.exists():
                    self.seal.bootstrap(display_name=display_name)
                else:
                    # update display name lightly
                    import json

                    meta_path = self.root / "control" / "root.meta.json"
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    meta["display_name"] = display_name
                    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
                    self.seal.reseal()
                self.audit.log("root_enroll_voice", "root", {"display_name": display_name})
                return {"ok": True, "speaker_id": "root", "as_root_voice": True, "auth": auth}

            out = self.gallery.enroll(
                speaker_id=speaker_id,
                display_name=display_name,
                embedding_paths=emb_files,
                template=template,
                discord_user_ids=discord_user_ids,
                is_root_enrollment=True,
            )
            self.audit.log("enroll", speaker_id, {"display_name": display_name, "template": template})
            out["auth"] = auth
            return out
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def set_capabilities(
        self,
        speaker_id: str,
        caps: dict[str, Any] | None = None,
        caps_yaml_path: str | None = None,
        template: str | None = None,
        *,
        is_root_claim: bool = False,
        local_cli: bool = False,
    ) -> dict[str, Any]:
        auth = self.assert_root_authorized(is_root_claim=is_root_claim, local_cli=local_cli)
        if not auth.get("ok"):
            return auth
        if speaker_id in ("root",):
            return {"ok": False, "error": "root has no gallery capabilities file; use control plane"}
        if template:
            data = load_template(template, self.root)
            data["speaker_id"] = speaker_id
        elif caps_yaml_path:
            import yaml

            with open(caps_yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        elif caps:
            data = caps
        else:
            return {"ok": False, "error": "provide caps dict, caps_yaml_path, or template"}

        path = save_capabilities(speaker_id, data, root=self.root, updated_by="root")
        self.audit.log("set_capabilities", speaker_id, {"path": str(path)})
        return {"ok": True, "speaker_id": speaker_id, "path": str(path), "capabilities": data, "auth": auth}

    def delete_speaker(
        self,
        speaker_id: str,
        *,
        is_root_claim: bool = False,
        local_cli: bool = False,
    ) -> dict[str, Any]:
        auth = self.assert_root_authorized(is_root_claim=is_root_claim, local_cli=local_cli)
        if not auth.get("ok"):
            return auth
        out = self.gallery.delete(speaker_id)
        if out.get("ok"):
            self.audit.log("delete", speaker_id, {})
        out["auth"] = auth
        return out

    def whoami_from_audio(self, audio_path: str) -> dict[str, Any]:
        claim = identify_audio(audio_path, self.root)
        if claim.get("ok"):
            self.audit.log(
                "identify",
                claim.get("speaker_id"),
                {
                    "confidence": claim.get("confidence"),
                    "matched": claim.get("matched"),
                    "outcome": claim.get("outcome"),
                },
            )
        caps = load_capabilities(claim.get("speaker_id") or "guest", self.root)
        claim["capabilities_summary"] = {
            "mode": caps.get("mode"),
            "display_name": caps.get("display_name"),
        }
        return claim

    def check(self, speaker_id: str, kind: str, name: str) -> dict[str, Any]:
        caps = load_capabilities(speaker_id, self.root)
        result = check_resource(caps, kind, name)
        result["speaker_id"] = speaker_id
        result["kind"] = kind
        result["name"] = name
        return result
