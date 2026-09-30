from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser

from app.collectors.base import Collector
from app.models import TrendItem


class GoogleTrendsCollector(Collector):
    name = "google_trends"

    def __init__(self, config: dict):
        super().__init__(config)
        self.region = config.get("region", "IN")
        self.keywords = config.get("keywords", [])

    def collect(self) -> list[TrendItem]:
        # Google Trends exposes a public RSS feed for trending searches by geo.
        url = f"https://trends.google.com/trending/rss?geo={quote_plus(self.region)}"
        feed = feedparser.parse(url)
        now = datetime.now(timezone.utc)
        results: list[TrendItem] = []

        configured = {str(x).strip().lower() for x in self.keywords if str(x).strip()}
        for entry in feed.entries:
            title = str(entry.get("title", "")).strip()
            if not title:
                continue
            text = f"{title} {entry.get('summary','')}".lower()
            matched = next((kw for kw in configured if kw in text or title.lower() in kw or kw in title.lower()), "")
            traffic = 0.0
            raw_traffic = entry.get("ht_approx_traffic") or entry.get("approx_traffic") or ""
            digits = "".join(ch for ch in str(raw_traffic) if ch.isdigit())
            if digits:
                traffic = float(digits)
            results.append(
                TrendItem(
                    title=title,
                    source="Google Trends",
                    url=str(entry.get("link", "")),
                    keyword=matched,
                    engagement=traffic,
                    observed_at=now,
                    metadata={"source_rank": len(results) + 1},
                )
            )
        return results
