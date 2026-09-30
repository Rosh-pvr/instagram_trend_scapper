from datetime import datetime, timezone

from app.models import TrendItem
from app.scoring import rank
from app.storage import Storage


def test_rank_prefers_repeated_signal(tmp_path):
    db = Storage(str(tmp_path / "trends.db"))
    now = datetime.now(timezone.utc)
    items = [
        TrendItem("AI Agents", "Instagram", engagement=500, observed_at=now),
        TrendItem("AI Agents", "Google Trends", engagement=400, observed_at=now),
        TrendItem("Other", "Google Trends", engagement=30, observed_at=now),
    ]
    out = rank(items, db, limit=2)
    assert out
    assert out[0].title == "AI Agents"


def test_storage_cooldown(tmp_path):
    db = Storage(str(tmp_path / "trends.db"))
    item = TrendItem("AI", "x", observed_at=datetime.now(timezone.utc))
    assert db.unseen([item]) == [item]
    db.mark_sent([item])
    assert db.unseen([item], cooldown_hours=24) == []
