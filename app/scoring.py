from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone

from app.models import TrendItem
from app.storage import Storage, normalize_title

STOP = {"the", "and", "for", "with", "from", "this", "that", "are", "you", "your", "about", "into", "what", "how"}


def tokens(text: str) -> list[str]:
    return [x for x in re.findall(r"[a-zA-Z0-9#]+", text.lower()) if x not in STOP]


def rank(
    items: list[TrendItem],
    storage: Storage,
    limit: int = 10,
    min_score: float = 0.2,
    history_hours: int = 168,
    weights: dict | None = None,
) -> list[TrendItem]:
    if not items:
        return []
    weights = weights or {}
    w_source = float(weights.get("source_weight", 0.10))
    w_recent = float(weights.get("recency_weight", 0.15))
    w_freq = float(weights.get("frequency_weight", 0.20))
    w_eng = float(weights.get("engagement_weight", 0.20))
    w_vel = float(weights.get("velocity_weight", 0.35))

    freq = Counter(normalize_title(t.title) for t in items)
    maxfreq = max(freq.values()) or 1
    now = datetime.now(timezone.utc)

    source_count = max(1, len({t.source for t in items}))
    # Aggregate the strongest signal for each topic before ranking.
    best_by_topic: dict[str, TrendItem] = {}
    scored_values: dict[str, float] = {}

    for t in items:
        key = normalize_title(t.title)
        frequency = freq[key] / maxfreq
        engagement = min(1.0, math.log1p(max(0.0, t.engagement)) / math.log(1000001))
        recency = 1.0
        if t.observed_at:
            age_h = max(0.0, (now - t.observed_at).total_seconds() / 3600)
            recency = math.exp(-age_h / 24)

        history = storage.history_for(key, history_hours)
        current_signal = max(0.0, float(t.engagement)) + 1.0
        if history:
            baseline = sum(max(0.0, e) + 1.0 for e, _ in history) / len(history)
            velocity = min(1.0, max(0.0, math.log1p(current_signal / baseline) / math.log(6)))
        else:
            velocity = 0.75

        is_instagram = t.source.lower().startswith("instagram")
        source_score = min(1.0, 1.0 / source_count + (0.25 if is_instagram else 0.0))
        score = (
            w_source * source_score
            + w_recent * recency
            + w_freq * frequency
            + w_eng * engagement
            + w_vel * velocity
        )
        t.metadata = {
            **(t.metadata or {}),
            "score": round(score, 4),
            "velocity": round(velocity, 4),
            "frequency": round(frequency, 4),
            "recency": round(recency, 4),
            "engagement_signal": round(engagement, 4),
        }

        if score > scored_values.get(key, -1.0):
            scored_values[key] = score
            best_by_topic[key] = t

    ranked = sorted(best_by_topic.values(), key=lambda x: float((x.metadata or {}).get("score", 0)), reverse=True)
    return [
        item for item in ranked
        if float((item.metadata or {}).get("score", 0)) >= min_score
    ][:limit]
