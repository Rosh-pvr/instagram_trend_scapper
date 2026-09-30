from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models import TrendItem


class Storage:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    norm_title TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '',
                    keyword TEXT NOT NULL DEFAULT '',
                    engagement REAL NOT NULL DEFAULT 0,
                    observed_at TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 0,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_title_time ON observations(norm_title, observed_at)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_trends (
                    norm_title TEXT PRIMARY KEY,
                    sent_at TEXT NOT NULL
                )
                """
            )

    def history_for(self, norm_title: str, since_hours: int) -> list[tuple[float, datetime]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT engagement, observed_at FROM observations WHERE norm_title=? AND observed_at>=? ORDER BY observed_at DESC",
                (norm_title, cutoff.isoformat()),
            ).fetchall()
        return [(float(row[0]), datetime.fromisoformat(row[1])) for row in rows]

    def save_observations(self, items: list[TrendItem]) -> None:
        with self._connect() as conn:
            for item in items:
                norm = normalize_title(item.title)
                observed = item.observed_at or datetime.now(timezone.utc)
                score = float((item.metadata or {}).get("score", 0))
                conn.execute(
                    "INSERT INTO observations(norm_title,title,source,url,keyword,engagement,observed_at,score,metadata) VALUES(?,?,?,?,?,?,?,?,?)",
                    (norm, item.title, item.source, item.url, item.keyword, float(item.engagement or 0), observed.isoformat(), score, "{}"),
                )

    def unseen(self, items: list[TrendItem], cooldown_hours: int = 24) -> list[TrendItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
        out = []
        with self._connect() as conn:
            for item in items:
                row = conn.execute(
                    "SELECT 1 FROM sent_trends WHERE norm_title=? AND sent_at>=?",
                    (normalize_title(item.title), cutoff.isoformat()),
                ).fetchone()
                if not row:
                    out.append(item)
        return out

    def mark_sent(self, items: list[TrendItem]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO sent_trends(norm_title,sent_at) VALUES(?,?)",
                [(normalize_title(x.title), now) for x in items],
            )


def normalize_title(title: str) -> str:
    return " ".join(title.lower().strip().split())
