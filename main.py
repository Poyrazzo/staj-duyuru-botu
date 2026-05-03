"""
Staj Duyuru Botu — Main Orchestrator
=====================================
Sources (10 scrapers total):

  FAST (API/lightweight, every scheduled run):
    · ATSScraper        — Greenhouse + Lever direct JSON API
    · LinkedInScraper   — JobSpy API wrapper

  BROWSER (Playwright + stealth, every scheduled run):
    · KariyerScraper    — kariyer.net
    · YouthallScraper   — youthall.com
    · ToptalentScraper  — toptalent.co
    · VizyonerGencScraper — vizyonergenc.com
    · KariyerKapisiScraper — kariyerkapisi.cbiko.gov.tr
    · ExtraBoardsScraper  — SecretCV, Yenibiriş, Co-Matching, İSO Staj

  COMPANY (Playwright, every scheduled run):
    · CompanyCareerScraper — 33 company career pages

  GOOGLE (CSE API, ONCE PER DAY, safety net):
    · GoogleScraper     — ~70 domains via Custom Search

Usage:
    python main.py              # single run then exit
    python main.py --loop       # run every RUN_INTERVAL_MINUTES
    python main.py --health     # force health check report
    python main.py --google     # force a Google CSE sweep right now
"""

import sys
import asyncio
import logging
import argparse
from datetime import datetime

import config
from modules.logger_setup import setup_logging
from db.database import Database
from scrapers import (
    LinkedInScraper, KariyerScraper, YouthallScraper,
    ATSScraper, ToptalentScraper, VizyonerGencScraper,
    KariyerKapisiScraper, CompanyCareerScraper,
    ExtraBoardsScraper, GoogleScraper, GoogleCSEScraper,
)
from modules.data_cleaner import DataCleaner
from modules.notifier import TelegramNotifier
from modules.health_check import HealthChecker
from modules.detail_extractor import DetailExtractor

logger = logging.getLogger("main")

FAST_SCRAPERS    = [ATSScraper, LinkedInScraper]
BROWSER_SCRAPERS = [KariyerScraper, YouthallScraper, ToptalentScraper,
                    VizyonerGencScraper, KariyerKapisiScraper, ExtraBoardsScraper]
COMPANY_SCRAPERS = [CompanyCareerScraper]


class Bot:
    def __init__(self) -> None:
        self.db = Database(config.DB_PATH)
        self.cleaner = DataCleaner()
        self.notifier = TelegramNotifier()
        self.health = HealthChecker(self.db)
        self.extractor = DetailExtractor()
        self._google     = GoogleScraper()
        self._google_cse = GoogleCSEScraper()

    async def run_once(self, force_google: bool = False) -> int:
        logger.info("=== Scrape cycle at %s ===", datetime.now().strftime("%H:%M:%S"))

        raw_jobs = await self._scrape_all(force_google=force_google)
        logger.info("Raw jobs total: %d", len(raw_jobs))

        clean_jobs = self.cleaner.clean(raw_jobs)
        enriched   = await self.extractor.enrich_batch(clean_jobs, max_concurrent=4)
        final      = [j for j in enriched if j.program_type != "full_time"]
        final      = DataCleaner.sort_by_date(final)

        new_jobs = [j for j in final if self.db.save_job(j)]

        if new_jobs:
            sent = await self.notifier.send_batch(new_jobs)
            if sent:
                for job in new_jobs:
                    self.db.mark_notified(job.job_id)
            logger.info("Done: %d new internship(s) notified.", sent)
            return sent

        logger.info("Done: no new internships this run.")
        return 0

    async def run_loop(self) -> None:
        await self.notifier.send_startup_message()
        interval = config.RUN_INTERVAL_MINUTES * 60
        while True:
            try:
                await self.run_once()
            except Exception as exc:
                logger.exception("Unhandled error: %s", exc)
                await self.notifier.send_error_alert("Orchestrator", str(exc))
            if self.health.is_due():
                await self._do_health_check()
            logger.info("Next run in %d minutes.", config.RUN_INTERVAL_MINUTES)
            await asyncio.sleep(interval)

    async def run_health_check(self) -> None:
        await self._do_health_check()

    # ── Internal pipeline ─────────────────────────────────────

    async def _scrape_all(self, force_google: bool = False) -> list:
        all_jobs = []

        # Fast scrapers — fully concurrent
        fast_results = await asyncio.gather(
            *[cls().scrape() for cls in FAST_SCRAPERS], return_exceptions=True
        )
        for cls, r in zip(FAST_SCRAPERS, fast_results):
            if isinstance(r, Exception):
                logger.error("%s failed: %s", cls.__name__, r)
                await self.notifier.send_error_alert(cls.__name__, str(r))
            else:
                logger.info("%s → %d", cls.__name__, len(r))
                all_jobs.extend(r)

        # Browser scrapers — concurrent (each has its own browser instance)
        browser_results = await asyncio.gather(
            *[cls().scrape() for cls in BROWSER_SCRAPERS], return_exceptions=True
        )
        for cls, r in zip(BROWSER_SCRAPERS, browser_results):
            if isinstance(r, Exception):
                logger.error("%s failed: %s", cls.__name__, r)
                await self.notifier.send_error_alert(cls.__name__, str(r))
            else:
                logger.info("%s → %d", cls.__name__, len(r))
                all_jobs.extend(r)

        # Company scraper — sequential within, but one single pass
        for cls in COMPANY_SCRAPERS:
            try:
                r = await cls().scrape()
                logger.info("%s → %d", cls.__name__, len(r))
                all_jobs.extend(r)
            except Exception as exc:
                logger.error("%s failed: %s", cls.__name__, exc)
                await self.notifier.send_error_alert(cls.__name__, str(exc))

        # Google CSE — once per day (or forced)
        if force_google or self._google.is_due():
            try:
                r = await self._google.scrape()
                logger.info("GoogleScraper (company) → %d", len(r))
                all_jobs.extend(r)
            except Exception as exc:
                logger.error("GoogleScraper failed: %s", exc)
            try:
                r = await self._google_cse.scrape()
                logger.info("GoogleCSEScraper (web) → %d", len(r))
                all_jobs.extend(r)
            except Exception as exc:
                logger.error("GoogleCSEScraper failed: %s", exc)

        return all_jobs

    async def _do_health_check(self) -> None:
        logger.info("Running health check …")
        source_statuses = await self.health.run()
        stats = self.health.get_db_health()
        await self.notifier.send_health_report(stats, source_statuses)


# ── CLI ───────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Turkish Internship Aggregator Bot")
    parser.add_argument("--loop",   action="store_true", help="Run on schedule")
    parser.add_argument("--health", action="store_true", help="Force health check")
    parser.add_argument("--google", action="store_true", help="Force Google CSE sweep now")
    return parser.parse_args()


async def main() -> None:
    setup_logging()
    args = parse_args()
    if not config.TELEGRAM_BOT_TOKEN or "your_bot" in config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Edit .env before running.")
    bot = Bot()
    if args.health:
        await bot.run_health_check()
    elif args.loop:
        await bot.run_loop()
    else:
        await bot.run_once(force_google=args.google)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
        sys.exit(0)
