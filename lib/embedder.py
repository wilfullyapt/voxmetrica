from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from .paths import load_config, get_data_root


class Embedder:
    """Voice embedding backend.

    - speechbrain: ECAPA-TDNN when installed
    - hash_stub: deterministic pseudo-embedding from file bytes (dev/smoke only)
    """

    def __init__(self, root: Path | None = None, backend: str | None = None):
        self.root = root or get_data_root()
        cfg = load_config(self.root)
        self.backend = backend or cfg.get("identify", {}).get("backend", "auto")
        self._sb_model = None
        self._resolved = None

    def resolve_backend(self) -> str:
        if self._resolved:
            return self._resolved
        if self.backend == "hash_stub":
            self._resolved = "hash_stub"
            return self._resolved
        if self.backend in ("auto", "speechbrain"):
            try:
                import speechbrain  # noqa: F401

                self._resolved = "speechbrain"
                return self._resolved
            except Exception:
                if self.backend == "speechbrain":
                    raise RuntimeError(
                        "speechbrain requested but not installed. "
                        "pip install speechbrain torch torchaudio"
                    )
                self._resolved = "hash_stub"
                return self._resolved
        self._resolved = "hash_stub"
        return self._resolved

    def _speechbrain_embed(self, wav_path: Path) -> np.ndarray:
        # Lazy load — heavy
        if self._sb_model is None:
            from speechbrain.inference.speaker import EncoderClassifier

            source = load_config(self.root).get("identify", {}).get(
                "speechbrain_source", "speechbrain/spkrec-ecapa-voxceleb"
            )
            savedir = self.root / ".cache" / "speechbrain"
            savedir.mkdir(parents=True, exist_ok=True)
            self._sb_model = EncoderClassifier.from_hparams(
                source=source, savedir=str(savedir)
            )
        # SpeechBrain expects a path or tensor; use file path helper
        emb = self._sb_model.encode_batch(
            self._sb_model.load_audio(str(wav_path))
        )
        vec = emb.squeeze().detach().cpu().numpy().astype(np.float32)
        # L2 normalize
        n = np.linalg.norm(vec) + 1e-9
        return (vec / n).astype(np.float32)

    def _hash_stub_embed(self, wav_path: Path, dim: int = 192) -> np.ndarray:
        data = wav_path.read_bytes()
        # Expand hash into a stable unit vector — NOT for production biometrics
        seed = hashlib.sha256(data).digest()
        rng = np.random.RandomState(int.from_bytes(seed[:4], "little"))
        vec = rng.randn(dim).astype(np.float32)
        # Mix in more hash bits
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
        backend = self.resolve_backend()
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


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32).reshape(-1)
    b = b.astype(np.float32).reshape(-1)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


def load_embedding(path: Path) -> np.ndarray:
    if path.suffix == ".npy":
        return np.load(path).astype(np.float32).reshape(-1)
    # json list fallback
    data = json.loads(path.read_text(encoding="utf-8"))
    return np.array(data, dtype=np.float32).reshape(-1)
