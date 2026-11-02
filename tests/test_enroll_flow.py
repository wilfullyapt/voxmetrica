"""Blank-start self-enroll ceremony."""

from __future__ import annotations

from pathlib import Path

from voxmetrica.enroll_flow import self_enroll
from voxmetrica.gallery import Gallery
from voxmetrica.identify import identify_audio


def test_self_enroll_requires_min_clips(data_root: Path, write_wav_bytes):
    clips = [write_wav_bytes("a.wav", b"clip-one-only")]
    out = self_enroll(
        display_name="Alex",
        audio_paths=[str(p) for p in clips],
        root=data_root,
        local_cli=True,
    )
    assert out["ok"] is False
    assert "min_clips" in (out.get("error") or "").lower() or out.get("code") == "min_clips"


def test_self_enroll_blank_gallery_then_match(data_root: Path, write_wav_bytes):
    # Three distinct files but hash_stub is content-based — use same content
    # so identify of that content matches enrolled templates.
    payload = b"household-alex-voice-bytes-xyz"
    clips = [
        write_wav_bytes("e1.wav", payload),
        write_wav_bytes("e2.wav", payload + b"2"),  # slight change → different emb
        write_wav_bytes("e3.wav", payload + b"3"),
    ]
    # For reliable match after enroll, enroll + probe with identical bytes
    probe = write_wav_bytes("probe.wav", payload)
    clips[0] = write_wav_bytes("e1b.wav", payload)

    out = self_enroll(
        display_name="Alex",
        audio_paths=[str(p) for p in clips],
        root=data_root,
        local_cli=True,
        speaker_id="alex",
    )
    assert out["ok"] is True
    assert out["speaker_id"] == "alex"
    people = Gallery(data_root).list_people()
    assert any(p["speaker_id"] == "alex" for p in people)

    claim = identify_audio(probe, root=data_root)
    assert claim["outcome"] == "matched"
    assert claim["speaker_id"] == "alex"


def test_self_enroll_blocked_when_policy_off(data_root: Path, write_wav_bytes, monkeypatch):
    import yaml

    cfg_path = data_root / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["enroll"]["allow_self_enroll_when_unknown"] = False
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    clips = [write_wav_bytes(f"c{i}.wav", f"bytes-{i}".encode()) for i in range(3)]
    out = self_enroll(
        display_name="Intruder",
        audio_paths=[str(p) for p in clips],
        root=data_root,
        local_cli=False,
        is_root_claim=False,
    )
    assert out["ok"] is False


def test_self_enroll_slugifies_display_name(data_root: Path, write_wav_bytes):
    payload = b"name-slug-test"
    clips = [write_wav_bytes(f"n{i}.wav", payload + bytes([i])) for i in range(3)]
    out = self_enroll(
        display_name="Adult One",
        audio_paths=[str(p) for p in clips],
        root=data_root,
        local_cli=True,
    )
    assert out["ok"] is True
    assert out["speaker_id"] == "adult_one"
