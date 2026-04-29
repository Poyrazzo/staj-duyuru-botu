"""
Staj Duyuru Botu — Main Orchestrator
=====================================
Runs indefinitely, scraping LinkedIn, Kariyer.net, and Youthall on a
configurable interval, filtering results, persisting to SQLite, and
sending instant Telegram alerts for every new internship found.

Usage:
    python main.py          # run once then exit
    python main.py --loop   # run on schedule (config.RUN_INTERVAL_MINUTES)
    python main.py --health # force a health check report
"""

import sys
import asyncio
import logging
import argparse
from datetime import datetime

import config
from modules.logger_setup import setup_logging
from db.database import Database
from scrapers import LinkedInScraper, KariyerScraper, YouthallScraper
from modules.data_cleaner import DataCleaner
from modules.notifier import TelegramNotifier
from modules.health_check import HealthChecker

logger = logging.getLogger("main")


class Bot:
    def __init__(self) -> None:
        self.db = Database(config.DB_PATH)
        self.cleaner = DataCleaner()
        self.notifier = TelegramNotifier()
        self.health = HealthChecker(self.db)
        self._scrapers = [
            LinkedInScraper(),
            KariyerScraper(),
            YouthallScraper(),
        ]

    # ── Public entry points ──────────────────────────────────

    async def run_once(self) -> int:
        """Single scrape-filter-notify cycle. Returns count of new jobs sent."""
        logger.info("=== Starting scrape cycle at %s ===", datetime.now().strftime("%H:%M:%S"))
        raw_jobs = await self._scrape_all()
        new_jobs = self._process(raw_jobs)

        if new_jobs:
            sent = await self.notifier.send_batch(new_jobs)
            for job in new_jobs:
                self.db.mark_notified(job.job_id)
            logger.info("Cycle complete: %d new internship(s) sent.", sent)
            return sent
        else:
            logger.info("Cycle complete: no new internships.")
            return 0

    async def run_loop(self) -> None:
        """Run scrape cycle on a fixed interval until interrupted."""
        await self.notifier.send_startup_message()
        interval_secs = config.RUN_INTERVAL_MINUTES * 60

        while True:
            try:
                await self.run_once()
            except Exception as exc:
                logger.exception("Unhandled error in run cycle: %s", exc)
                await self.notifier.send_error_alert("Orchestrator", str(exc))

            # Weekly health check
            if self.health.is_due():
                await self._do_health_check()

            logger.info(
                "Sleeping %d minutes until next cycle…", config.RUN_INTERVAL_MINUTES
            )
            await asyncio.sleep(interval_secs)

    async def run_health_check(self) -> None:
        """Force a health check and send the report."""
        await self._do_health_check()

    # ── Internal pipeline ────────────────────────────────────

    async def _scrape_all(self):
        """Run all scrapers concurrently and merge results."""
        tasks = [asyncio.create_task(s.scrape()) for s in self._scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_jobs = []
        for scraper, result in zip(self._scrapers, results):
            if isinstance(result, Exception):
                logger.error(
                    "Scraper %s failed: %s", scraper.source_name, result
                )
                await self.notifier.send_error_alert(scraper.source_name, str(result))
            else:
                logger.info(
                    "Scraper %s returned %d jobs.", scraper.source_name, len(result)
                )
                all_jobs.extend(result)

        return all_jobs

    def _process(self, raw_jobs):
        """Clean, filter, deduplicate, persist, and return truly new jobs."""
        cleaned = self.cleaner.clean(raw_jobs)
        cleaned = DataCleaner.sort_by_date(cleaned)

        new_jobs = []
        for job in cleaned:
            saved = self.db.save_job(job)
            if saved:
                new_jobs.append(job)
                logger.info("NEW: %s @ %s [%s]", job.title, job.company, job.source)

        return new_jobs

    async def _do_health_check(self) -> None:
        logger.info("Running health check …")
        source_statuses = await self.health.run()
        stats = self.health.get_db_health()
        await self.notifier.send_health_report(stats, source_statuses)


# ── CLI entry point ──────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turkish Internship Aggregator Bot"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help=f"Run continuously every {config.RUN_INTERVAL_MINUTES} minutes",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Force a health check report and exit",
    )
    return parser.parse_args()


async def main() -> None:
    setup_logging()
    args = parse_args()

    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        logger.warning(
            "TELEGRAM_BOT_TOKEN not set. Copy .env.example → .env and fill in your credentials."
        )

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
        logger.info("Bot stopped by user.")
        sys.exit(0)
