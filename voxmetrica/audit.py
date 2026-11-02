from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .paths import get_data_root, load_config


class AuditLog:
    def __init__(self, root: Path | None = None):
        self.root = root or get_data_root()
        cfg = load_config(self.root)
        rel = cfg.get("audit", {}).get("sqlite_path", "audit/events.sqlite")
        self.path = self.root / rel
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path))

    def _init(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    speaker_id TEXT,
                    detail TEXT
                )
                """
            )

    def log(self, kind: str, speaker_id: str | None = None, detail: dict[str, Any] | None = None) -> None:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._conn() as c:
            c.execute(
                "INSERT INTO events (ts, kind, speaker_id, detail) VALUES (?, ?, ?, ?)",
                (ts, kind, speaker_id, json.dumps(detail or {})),
            )

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, ts, kind, speaker_id, detail FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r[0],
                    "ts": r[1],
                    "kind": r[2],
                    "speaker_id": r[3],
                    "detail": json.loads(r[4] or "{}"),
                }
            )
        return out
