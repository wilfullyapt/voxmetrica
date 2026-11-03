"""Plugin tool handlers — root gate without forged is_root_claim."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugin import tools  # noqa: E402
from voxmetrica.claims import ClaimStore  # noqa: E402
from voxmetrica.gallery import Gallery  # noqa: E402


def _unit(seed: int) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(192).astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def test_enroll_tool_denied_without_root_claim(data_root: Path, monkeypatch):
    monkeypatch.setenv("VOXMETRICA_ROOT", str(data_root))
    ClaimStore(data_root).put(
        "s1",
        {"outcome": "matched", "matched": True, "is_root": False, "speaker_id": "adult1"},
    )
    raw = tools.enroll(
        {
            "display_name": "X",
            "audio_paths": ["/nope.wav"],
            "is_root_claim": True,  # forged — must still fail
            "local_cli": True,
        },
        task_id="s1",
    )
    out = json.loads(raw)
    assert out["ok"] is False
    assert out.get("code") == "root_required"


def test_enroll_tool_allowed_with_root_claim(data_root: Path, monkeypatch, write_wav_bytes):
    monkeypatch.setenv("VOXMETRICA_ROOT", str(data_root))
    ClaimStore(data_root).put(
        "root-sess",
        {"outcome": "matched", "matched": True, "is_root": True, "speaker_id": "root"},
    )
    audio = write_wav_bytes("r.wav", b"root-enroll-clip")
    raw = tools.enroll(
        {
            "speaker_id": "newperson",
            "display_name": "New Person",
            "audio_paths": [str(audio)],
            "template": "full-adult",
        },
        task_id="root-sess",
    )
    out = json.loads(raw)
    assert out.get("ok") is True
    assert Gallery(data_root).get("newperson")


def test_guest_whoami_ok(data_root: Path, monkeypatch):
    monkeypatch.setenv("VOXMETRICA_ROOT", str(data_root))
    raw = tools.whoami({}, task_id="none")
    out = json.loads(raw)
    assert out.get("ok") is True
    assert out.get("speaker_id") == "guest"
