"""Caps matrix + seal fail-closed basics."""

from __future__ import annotations

from pathlib import Path

from voxmetrica.capabilities import check_resource, load_template
from voxmetrica.claims import ClaimStore
from voxmetrica.seal import Seal


def test_guest_template_denies_terminal(data_root: Path):
    caps = load_template("guest-default", data_root)
    r = check_resource(caps, "tools", "terminal")
    assert r["allowed"] is False


def test_adult_template_allows_broad_or_not_deny_terminal(data_root: Path):
    caps = load_template("full-adult", data_root)
    # denylist with empty deny → allowed
    r = check_resource(caps, "tools", "terminal")
    assert r["allowed"] is True


def test_seal_detects_tamper(data_root: Path):
    seal = Seal(data_root)
    seal.bootstrap(display_name="Root")
    assert seal.verify()["ok"] is True
    meta = data_root / "control" / "root.meta.json"
    meta.write_text(meta.read_text(encoding="utf-8").replace("Root", "Hax"), encoding="utf-8")
    v = seal.verify()
    assert v["ok"] is False
    assert v.get("code") == "seal_break"


def test_claim_store_ttl_expiry(data_root: Path, monkeypatch):
    store = ClaimStore(data_root)
    store.put("s1", {"speaker_id": "alex", "outcome": "matched"})
    assert store.get("s1") is not None
    # Force mtime old
    path = store._path("s1")
    import os
    import time

    old = time.time() - 10_000
    os.utime(path, (old, old))
    assert store.get("s1") is None
