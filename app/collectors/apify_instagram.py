from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

from app.collectors.base import Collector
from app.models import TrendItem

log = logging.getLogger(__name__)

_HASHTAG_RE = re.compile(r"(?<!\w)#([\w.]+)", re.UNICODE)


class ApifyInstagramCollector(Collector):
    """Collect public Instagram hashtag content through the Apify HTTP API.

    Default Actor: apify/instagram-hashtag-scraper.
    """

    name = "apify_instagram"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.token = os.getenv("APIFY_API_TOKEN", "").strip()
        self.actor_id = os.getenv(
            "APIFY_INSTAGRAM_ACTOR",
            "apify/instagram-hashtag-scraper",
        ).strip()
        self.hashtags = [
            str(x).lstrip("#").strip()
            for x in config.get("instagram_hashtags", [])
            if str(x).strip()
        ]
        self.results_limit = int(os.getenv(
            "APIFY_RESULTS_LIMIT",
            str(config.get("apify_results_limit", 10)),
        ))
        self.max_items = int(os.getenv(
            "APIFY_MAX_ITEMS",
            str(config.get("apify_max_items", 200)),
        ))
        self.timeout_seconds = int(os.getenv(
            "APIFY_TIMEOUT_SECONDS",
            str(max(120, int(config.get("apify_wait_seconds", 180)) + 30)),
        ))
        self.extra_input: dict[str, Any] = {}
        raw_extra = os.getenv("APIFY_EXTRA_INPUT_JSON", "").strip()
        if raw_extra:
            try:
                parsed = json.loads(raw_extra)
                if not isinstance(parsed, dict):
                    raise ValueError("APIFY_EXTRA_INPUT_JSON must be a JSON object")
                self.extra_input = parsed
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid APIFY_EXTRA_INPUT_JSON: {exc}") from exc

    def collect(self) -> list[TrendItem]:
        if not self.token:
            log.info("Apify Instagram collector disabled: APIFY_API_TOKEN is not configured")
            return []
        if not self.hashtags:
            log.warning("Apify Instagram collector enabled but no instagram_hashtags are configured")
            return []

        input_data: dict[str, Any] = {
            "hashtags": self.hashtags,
            "resultsType": "posts",
            "resultsLimit": self.results_limit,
            **self.extra_input,
        }
        actor_path = self.actor_id.replace("/", "~")
        url = f"https://api.apify.com/v2/actors/{quote(actor_path, safe="~")}/run-sync-get-dataset-items"
        log.info(
            "Starting Apify Actor %s for %d hashtags (limit=%d)",
            self.actor_id,
            len(self.hashtags),
            self.results_limit,
        )

        response = requests.post(
            url,
            params={"token": self.token},
            json=input_data,
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            log.error("Apify API error %s: %s", response.status_code, response.text[:1200])
        response.raise_for_status()

        payload = response.json()
        rows = payload.get("items", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise RuntimeError("Apify response did not contain a dataset item list")
        rows = rows[: self.max_items]
        log.info("Apify Actor returned %d dataset items", len(rows))
        return self._to_trends(rows)

    def _to_trends(self, rows: list[dict[str, Any]]) -> list[TrendItem]:
        now = datetime.now(timezone.utc)
        trends: list[TrendItem] = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            timestamp = self._parse_datetime(
                row.get("timestamp")
                or row.get("takenAt")
                or row.get("createdAt")
            ) or now

            likes = self._number(row, "likes", "likesCount", "likeCount")
            comments = self._number(row, "commentsCount", "comments", "commentCount")
            views = self._number(row, "videoViewCount", "views", "viewCount", "plays", "playCount")
            shares = self._number(row, "shares", "shareCount")
            engagement = likes + comments + shares + views

            caption = str(row.get("caption") or row.get("text") or "").strip().replace("\n", " ")
            permalink = str(row.get("url") or row.get("permalink") or row.get("postUrl") or "")
            parent = row.get("parentData") or {}
            source_hashtag = str(parent.get("hashtag") or parent.get("title") or "").lstrip("#").strip()

            hashtags = self._extract_hashtags(row, caption)
            if source_hashtag:
                hashtags.insert(0, source_hashtag)
            hashtags = self._dedupe(hashtags)

            if not hashtags:
                title = caption[:120] if caption else "Instagram trend signal"
                trends.append(self._make_item(
                    title=title,
                    keyword="",
                    source="Instagram via Apify",
                    url=permalink,
                    engagement=engagement,
                    observed_at=timestamp,
                    row=row,
                ))
                continue

            for hashtag in hashtags[:12]:
                trends.append(self._make_item(
                    title=f"#{hashtag}",
                    keyword=f"#{hashtag}",
                    source="Instagram via Apify",
                    url=permalink,
                    engagement=engagement,
                    observed_at=timestamp,
                    row=row,
                ))

        return trends

    @staticmethod
    def _make_item(*, title: str, keyword: str, source: str, url: str,
                   engagement: float, observed_at: datetime, row: dict[str, Any]) -> TrendItem:
        return TrendItem(
            title=title,
            source=source,
            url=url,
            keyword=keyword,
            engagement=engagement,
            observed_at=observed_at,
            metadata={
                "apify_actor": os.getenv("APIFY_INSTAGRAM_ACTOR", "apify/instagram-hashtag-scraper"),
                "instagram_id": row.get("id") or row.get("shortCode") or row.get("shortcode"),
                "likes": ApifyInstagramCollector._number(row, "likes", "likesCount", "likeCount"),
                "comments": ApifyInstagramCollector._number(row, "commentsCount", "comments", "commentCount"),
                "views": ApifyInstagramCollector._number(row, "videoViewCount", "views", "viewCount", "plays", "playCount"),
                "shares": ApifyInstagramCollector._number(row, "shares", "shareCount"),
                "caption": str(row.get("caption") or row.get("text") or "")[:500],
            },
        )

    @staticmethod
    def _number(row: dict[str, Any], *keys: str) -> float:
        for key in keys:
            value = row.get(key)
            if value is None or value == "":
                continue
            try:
                return float(str(value).replace(",", "").strip())
            except (TypeError, ValueError):
                continue
        return 0.0

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        try:
            epoch = float(text)
            return datetime.fromtimestamp(epoch, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _extract_hashtags(row: dict[str, Any], caption: str) -> list[str]:
        values: list[str] = []
        raw = row.get("hashtags")
        if isinstance(raw, list):
            values.extend(str(x).lstrip("#").strip() for x in raw if str(x).strip())
        elif isinstance(raw, str):
            values.extend(x.lstrip("#").strip() for x in raw.split() if x.strip().startswith("#"))
        values.extend(_HASHTAG_RE.findall(caption))
        return values

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            clean = value.strip().lower()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            output.append(clean)
        return output
