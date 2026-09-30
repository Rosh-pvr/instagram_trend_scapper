from __future__ import annotations

import argparse
import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.collectors.google_trends import GoogleTrendsCollector
from app.collectors.instagram_graph import InstagramGraphCollector
from app.collectors.apify_instagram import ApifyInstagramCollector
from app.config import env_bool, load_config
from app.scoring import rank
from app.storage import Storage
from app.summarizer import summarize
from app.whatsapp import send_whatsapp

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("trendbot")


def run_once(dry_run: bool | None = None) -> str:
    cfg = load_config()
    storage = Storage(os.getenv("DATABASE_PATH", "/app/data/trends.db"))
    items = []

    sources = cfg.get("sources", {})
    if sources.get("google_trends", True):
        items.extend(GoogleTrendsCollector(cfg).collect())
    if sources.get("apify_instagram", True):
        items.extend(ApifyInstagramCollector(cfg).collect())
    if sources.get("instagram_graph", False):
        items.extend(InstagramGraphCollector(cfg).collect())

    log.info("Collected %d raw observations", len(items))
    ranked = rank(
        items,
        storage=storage,
        limit=int(cfg.get("max_trends", 10)),
        min_score=float(cfg.get("min_score", 0.2)),
        history_hours=int(cfg.get("history_window_hours", 168)),
        weights=cfg.get("scoring", {}),
    )
    storage.save_observations(ranked)
    cooldown = int(cfg.get("lookback_hours", 24))
    fresh = storage.unseen(ranked, cooldown_hours=cooldown)

    if not fresh:
        log.info("No new report-worthy trends found")
        return "No new trends found today."

    report = summarize(fresh)
    use_dry_run = env_bool("DRY_RUN", False) if dry_run is None else dry_run
    send_whatsapp(report, dry_run=use_dry_run)

    if use_dry_run:
        log.info("DRY_RUN enabled; WhatsApp message was not sent")
    else:
        storage.mark_sent(fresh)
        log.info("WhatsApp report sent successfully and trends marked as sent")

    log.info("Report contains %d trends", len(fresh))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Trend-to-WhatsApp digest bot")
    parser.add_argument("--once", action="store_true", help="Run one collection/report cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Collect and print the report without sending WhatsApp")
    args = parser.parse_args()

    cfg = load_config()
    if args.once or args.dry_run:
        run_once(dry_run=True if args.dry_run else None)
        return

    timezone = os.getenv("TIMEZONE", "Asia/Kolkata")
    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        run_once,
        CronTrigger.from_crontab(cfg.get("schedule", "0 9 * * *"), timezone=timezone),
        id="daily-trends",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    log.info("Trend bot started; timezone=%s schedule=%s", timezone, cfg.get("schedule"))
    scheduler.start()


if __name__ == "__main__":
    main()
