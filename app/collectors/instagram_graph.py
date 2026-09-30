from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import requests

from app.collectors.base import Collector
from app.models import TrendItem

log = logging.getLogger(__name__)


class InstagramGraphCollector(Collector):
    """
    Optional authorized collector.

    This uses documented Graph API-style hashtag endpoints when the account is
    eligible and configured. It deliberately does not attempt browser scraping,
    login automation, CAPTCHA solving, session theft, or rate-limit evasion.
    """

    name = "instagram_graph"

    def __init__(self, config: dict):
        super().__init__(config)
        self.token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
        self.ig_user_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
        self.hashtags = [str(x).lstrip("#").strip() for x in config.get("instagram_hashtags", []) if str(x).strip()]
        self.timeout = int(config.get("http_timeout_seconds", 20))
        self.version = os.getenv("WHATSAPP_GRAPH_VERSION", "").strip()

    def collect(self) -> list[TrendItem]:
        if not self.token or not self.ig_user_id or not self.version:
            log.info("Instagram Graph collector disabled: credentials/version not configured")
            return []

        base = f"https://graph.facebook.com/{self.version}"
        out: list[TrendItem] = []
        now = datetime.now(timezone.utc)

        for hashtag in self.hashtags:
            try:
                search = requests.get(
                    f"{base}/ig_hashtag_search",
                    params={"user_id": self.ig_user_id, "q": hashtag, "access_token": self.token},
                    timeout=self.timeout,
                )
                search.raise_for_status()
                ids = search.json().get("data", [])
                if not ids:
                    continue
                hashtag_id = ids[0].get("id")

                media = requests.get(
                    f"{base}/{hashtag_id}/top_media",
                    params={
                        "user_id": self.ig_user_id,
                        "fields": "id,caption,media_type,permalink,timestamp,like_count,comments_count",
                        "access_token": self.token,
                    },
                    timeout=self.timeout,
                )
                media.raise_for_status()
                for item in media.json().get("data", [])[:25]:
                    caption = (item.get("caption") or "").strip().replace("\n", " ")
                    title = caption[:120] if caption else f"#{hashtag}"
                    engagement = float(item.get("like_count") or 0) + float(item.get("comments_count") or 0)
                    observed = item.get("timestamp")
                    observed_at = now
                    if observed:
                        try:
                            observed_at = datetime.fromisoformat(observed.replace("Z", "+00:00"))
                        except ValueError:
                            pass
                    out.append(
                        TrendItem(
                            title=title,
                            source="Instagram Graph",
                            url=str(item.get("permalink") or ""),
                            keyword=f"#{hashtag}",
                            engagement=engagement,
                            observed_at=observed_at,
                            metadata={"instagram_media_id": item.get("id"), "hashtag": hashtag},
                        )
                    )
            except requests.RequestException as exc:
                log.warning("Instagram request failed for #%s: %s", hashtag, exc)
            except (ValueError, KeyError, TypeError) as exc:
                log.warning("Instagram response parse failed for #%s: %s", hashtag, exc)

        return out
