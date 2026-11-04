"""P6 policy gate + P7 edge client."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from voxmetrica.edge_client import EdgeClient
from voxmetrica.gallery import Gallery
from voxmetrica.policy import ALWAYS_ALLOW, ROOT_ONLY_TOOLS, effective_speaker_id, gate_tool


def _unit(seed: int, dim: int = 192) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def test_guest_claim_blocks_terminal(data_root: Path):
    claim = {"outcome": "unknown", "matched": False, "is_root": False, "speaker_id": "guest"}
    g = gate_tool("terminal", claim, root=data_root)
    assert g["allowed"] is False
    assert g["speaker_id"] == "guest"


def test_clarify_claim_uses_guest_caps(data_root: Path):
    claim = {
        "outcome": "clarify",
        "needs_clarify": True,
        "matched": False,
        "speaker_id": "guest",
        "candidates": [{"speaker_id": "alex", "score": 0.7}],
    }
    g = gate_tool("terminal", claim, root=data_root)
    assert g["allowed"] is False
    assert effective_speaker_id(claim) == "guest"


def test_matched_adult_allows_terminal(data_root: Path, save_embedding):
    from voxmetrica.embedder import Embedder

    v = _unit(1)
    path = data_root / "enroll_raw" / "a.npy"
    Embedder(data_root).save_embedding(v, path)
    Gallery(data_root).enroll("adult1", "Adult", [path], template="full-adult")
    claim = {
        "outcome": "matched",
        "matched": True,
        "is_root": False,
        "speaker_id": "adult1",
    }
    g = gate_tool("terminal", claim, root=data_root)
    assert g["allowed"] is True


def test_root_only_enroll_denied_without_root(data_root: Path):
    claim = {"outcome": "matched", "matched": True, "is_root": False, "speaker_id": "adult1"}
    g = gate_tool("voxmetrica_enroll", claim, root=data_root)
    assert g["allowed"] is False
    assert g.get("code") == "root_required"


def test_root_claim_allows_enroll(data_root: Path):
    claim = {"outcome": "matched", "matched": True, "is_root": True, "speaker_id": "root"}
    g = gate_tool("voxmetrica_enroll", claim, root=data_root)
    assert g["allowed"] is True


def test_whoami_always_allowed_for_guest(data_root: Path):
    claim = {"outcome": "unknown", "matched": False}
    g = gate_tool("voxmetrica_whoami", claim, root=data_root)
    assert g["allowed"] is True
    assert "voxmetrica_whoami" in ALWAYS_ALLOW
    assert "voxmetrica_enroll" in ROOT_ONLY_TOOLS


def test_edge_client_identify_and_badge(data_root: Path, write_wav_bytes, save_embedding):
    payload = b"edge-client-voice-aaa"
    audio = write_wav_bytes("e.wav", payload)
    from voxmetrica.embedder import Embedder

    emb = Embedder(data_root, backend="hash_stub").embed(audio)
    path = save_embedding("alex", emb["embedding"])
    Gallery(data_root).enroll("alex", "Alex", [path], template="full-adult")

    client = EdgeClient(data_root, ingress="narthex")
    claim = client.identify(audio, session_id="door1")
    assert claim["outcome"] == "matched"
    assert claim["speaker_id"] == "alex"
    assert "Alex" in client.badge(claim)

    unk = client.badge({"outcome": "unknown"})
    assert "don't know" in unk.lower() or "who" in unk.lower()


def test_edge_client_enroll_self(data_root: Path, write_wav_bytes):
    # min_clips 3 in fixture
    clips = [write_wav_bytes(f"c{i}.wav", f"bytes-{i}-xx".encode()) for i in range(3)]
    client = EdgeClient(data_root, ingress="mobile-ami")
    out = client.enroll_self("Pat", clips)
    assert out["ok"] is True
    assert out["speaker_id"] == "pat"
