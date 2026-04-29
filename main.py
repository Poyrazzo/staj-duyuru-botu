"""
Staj Duyuru Botu — Main Orchestrator
=====================================
Sources monitored:
  Job Boards : LinkedIn, Kariyer.net, Youthall, Toptalent, Vizyoner Genç, Kariyer Kapısı
  ATS APIs   : Greenhouse (Trendyol, Getir, …) — direct JSON, zero anti-bot
  Companies  : 16 company career pages via Playwright

Usage:
    python main.py              # single run then exit
    python main.py --loop       # run every RUN_INTERVAL_MINUTES
    python main.py --health     # force health check report
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
)
from modules.data_cleaner import DataCleaner
from modules.notifier import TelegramNotifier
from modules.health_check import HealthChecker
from modules.detail_extractor import DetailExtractor

logger = logging.getLogger("main")

# ── Scraper groups ────────────────────────────────────────────
# Fast scrapers (API/lightweight) run first, then heavier Playwright ones
FAST_SCRAPERS = [
    ATSScraper,          # Direct JSON API — no anti-bot
    LinkedInScraper,     # JobSpy API wrapper
]
BROWSER_SCRAPERS = [
    KariyerScraper,
    YouthallScraper,
    ToptalentScraper,
    VizyonerGencScraper,
    KariyerKapisiScraper,
]
COMPANY_SCRAPERS = [
    CompanyCareerScraper,  # All 16 company pages in one pass
]


class Bot:
    def __init__(self) -> None:
        self.db = Database(config.DB_PATH)
        self.cleaner = DataCleaner()
        self.notifier = TelegramNotifier()
        self.health = HealthChecker(self.db)
        self.extractor = DetailExtractor()

    # ── Public entry points ───────────────────────────────────

    async def run_once(self) -> int:
        logger.info("=== Scrape cycle started at %s ===", datetime.now().strftime("%H:%M:%S"))

        # 1. Scrape all sources
        raw_jobs = await self._scrape_all()
        logger.info("Total raw jobs from all sources: %d", len(raw_jobs))

        # 2. Clean & filter (whitelist, blacklist, dedup)
        clean_jobs = self.cleaner.clean(raw_jobs)
        logger.info("Jobs after cleaning: %d", len(clean_jobs))

        # 3. Enrich with detail pages (deadline, requirements, program_type)
        enriched = await self.extractor.enrich_batch(clean_jobs, max_concurrent=4)

        # 4. Final internship gate after enrichment (program_type may now be 'full_time')
        final = [j for j in enriched if j.program_type != "full_time"]
        logger.info("Jobs after internship gate: %d", len(final))

        # 5. Sort newest deadline first
        final = DataCleaner.sort_by_date(final)

        # 6. Persist & notify only genuinely new ones
        new_jobs = []
        for job in final:
            if self.db.save_job(job):
                new_jobs.append(job)

        if new_jobs:
            sent = await self.notifier.send_batch(new_jobs)
            for job in new_jobs:
                self.db.mark_notified(job.job_id)
            logger.info("Cycle done: %d new internship(s) notified.", sent)
            return sent
        else:
            logger.info("Cycle done: no new internships this run.")
            return 0

    async def run_loop(self) -> None:
        await self.notifier.send_startup_message()
        interval_secs = config.RUN_INTERVAL_MINUTES * 60
        while True:
            try:
                await self.run_once()
            except Exception as exc:
                logger.exception("Unhandled error in run cycle: %s", exc)
                await self.notifier.send_error_alert("Orchestrator", str(exc))
            if self.health.is_due():
                await self._do_health_check()
            logger.info("Next run in %d minutes.", config.RUN_INTERVAL_MINUTES)
            await asyncio.sleep(interval_secs)

    async def run_health_check(self) -> None:
        await self._do_health_check()

    # ── Internal pipeline ─────────────────────────────────────

    async def _scrape_all(self) -> list:
        all_jobs = []

        # Fast scrapers run fully concurrently
        fast_tasks = [asyncio.create_task(cls().scrape()) for cls in FAST_SCRAPERS]
        fast_results = await asyncio.gather(*fast_tasks, return_exceptions=True)
        for cls, result in zip(FAST_SCRAPERS, fast_results):
            if isinstance(result, Exception):
                logger.error("Fast scraper %s failed: %s", cls.__name__, result)
                await self.notifier.send_error_alert(cls.__name__, str(result))
            else:
                logger.info("%s → %d jobs", cls.__name__, len(result))
                all_jobs.extend(result)

        # Browser scrapers run concurrently (each manages its own browser instance)
        browser_tasks = [asyncio.create_task(cls().scrape()) for cls in BROWSER_SCRAPERS]
        browser_results = await asyncio.gather(*browser_tasks, return_exceptions=True)
        for cls, result in zip(BROWSER_SCRAPERS, browser_results):
            if isinstance(result, Exception):
                logger.error("Browser scraper %s failed: %s", cls.__name__, result)
                await self.notifier.send_error_alert(cls.__name__, str(result))
            else:
                logger.info("%s → %d jobs", cls.__name__, len(result))
                all_jobs.extend(result)

        # Company scraper runs last (most time-consuming — 16 pages sequentially)
        for cls in COMPANY_SCRAPERS:
            try:
                result = await cls().scrape()
                logger.info("%s → %d jobs", cls.__name__, len(result))
                all_jobs.extend(result)
            except Exception as exc:
                logger.error("Company scraper %s failed: %s", cls.__name__, exc)
                await self.notifier.send_error_alert(cls.__name__, str(exc))

        return all_jobs

    async def _do_health_check(self) -> None:
        logger.info("Running health check …")
        source_statuses = await self.health.run()
        stats = self.health.get_db_health()
        await self.notifier.send_health_report(stats, source_statuses)


# ── CLI ───────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Turkish Internship Aggregator Bot")
    parser.add_argument("--loop", action="store_true",
                        help=f"Run every {config.RUN_INTERVAL_MINUTES} minutes")
    parser.add_argument("--health", action="store_true",
                        help="Force health check report and exit")
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
        await bot.run_once()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
        sys.exit(0)
