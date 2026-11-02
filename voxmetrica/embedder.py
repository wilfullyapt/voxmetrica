from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from .paths import get_data_root, load_config
from .score import cosine


class Embedder:
    """Voice embedding backend.

    - speechbrain: ECAPA-TDNN when installed
    - hash_stub: deterministic pseudo-embedding from file bytes (dev/smoke only)
    """

    def __init__(self, root: Path | None = None, backend: str | None = None):
        self.root = root or get_data_root()
        cfg = load_config(self.root)
        self.backend = backend or cfg.get("identify", {}).get("backend", "auto")
        self.production = bool(cfg.get("production", False))
        self._sb_model = None
        self._resolved = None

    def resolve_backend(self) -> str:
        if self._resolved:
            return self._resolved

        requested = self.backend
        if requested == "hash_stub":
            if self.production:
                raise RuntimeError(
                    "hash_stub is forbidden when production: true — install SpeechBrain "
                    "(pip install 'voxmetrica[speechbrain]') and set identify.backend: speechbrain|auto"
                )
            self._resolved = "hash_stub"
            return self._resolved

        if requested in ("auto", "speechbrain"):
            try:
                import speechbrain  # noqa: F401

                self._resolved = "speechbrain"
                return self._resolved
            except Exception:
                if requested == "speechbrain" or self.production:
                    raise RuntimeError(
                        "speechbrain required (production or explicit backend) but not installed. "
                        "pip install 'voxmetrica[speechbrain]' or torch/torchaudio/speechbrain"
                    ) from None
                self._resolved = "hash_stub"
                return self._resolved

        if self.production:
            raise RuntimeError(f"unknown embed backend in production: {requested}")
        self._resolved = "hash_stub"
        return self._resolved

    def _speechbrain_embed(self, wav_path: Path) -> np.ndarray:
        if self._sb_model is None:
            from speechbrain.inference.speaker import EncoderClassifier

            source = load_config(self.root).get("identify", {}).get(
                "speechbrain_source", "speechbrain/spkrec-ecapa-voxceleb"
            )
            savedir = self.root / ".cache" / "speechbrain"
            savedir.mkdir(parents=True, exist_ok=True)
            self._sb_model = EncoderClassifier.from_hparams(source=source, savedir=str(savedir))
        emb = self._sb_model.encode_batch(self._sb_model.load_audio(str(wav_path)))
        vec = emb.squeeze().detach().cpu().numpy().astype(np.float32)
        n = np.linalg.norm(vec) + 1e-9
        return (vec / n).astype(np.float32)

    def _hash_stub_embed(self, wav_path: Path, dim: int = 192) -> np.ndarray:
        data = wav_path.read_bytes()
        seed = hashlib.sha256(data).digest()
        rng = np.random.RandomState(int.from_bytes(seed[:4], "little"))
        vec = rng.randn(dim).astype(np.float32)
        for i in range(0, min(len(data), 4096), 32):
            chunk = hashlib.sha256(data[i : i + 32]).digest()
            for j, b in enumerate(chunk):
                vec[j % dim] += (b / 255.0) * 0.01
        n = np.linalg.norm(vec) + 1e-9
        return (vec / n).astype(np.float32)

    def embed(self, audio_path: str | Path) -> dict[str, Any]:
        path = Path(audio_path)
        if not path.exists():
            return {"ok": False, "error": f"audio not found: {path}"}
        try:
            backend = self.resolve_backend()
        except RuntimeError as e:
            return {"ok": False, "error": str(e), "backend": self.backend}
        try:
            if backend == "speechbrain":
                vec = self._speechbrain_embed(path)
            else:
                vec = self._hash_stub_embed(path)
            return {
                "ok": True,
                "backend": backend,
                "dim": int(vec.shape[0]),
                "embedding": vec,
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "backend": backend}

    def save_embedding(self, vec: np.ndarray, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        np.save(dest, vec.astype(np.float32))
        return dest


def load_embedding(path: Path) -> np.ndarray:
    if path.suffix == ".npy":
        return np.load(path).astype(np.float32).reshape(-1)
    data = json.loads(path.read_text(encoding="utf-8"))
    return np.array(data, dtype=np.float32).reshape(-1)


__all__ = ["Embedder", "cosine", "load_embedding"]
