"""Health check module — tests each scraper source and reports status."""

import asyncio
import logging
from datetime import datetime, timedelta

import config
from db.database import Database

logger = logging.getLogger(__name__)


class HealthChecker:
    """Pings each source and verifies that data was collected recently."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._last_check: datetime | None = None

    def is_due(self) -> bool:
        """Return True if enough time has passed since the last health check."""
        if self._last_check is None:
            return True
        interval = timedelta(hours=config.HEALTH_CHECK_INTERVAL_HOURS)
        return datetime.utcnow() - self._last_check >= interval

    async def run(self) -> dict[str, str]:
        """
        Test each source with a lightweight request.
        Returns {source_name: "OK" | "ERROR: <msg>"}
        """
        from scrapers import LinkedInScraper, KariyerScraper, YouthallScraper

        sources = {
            "LinkedIn":   LinkedInScraper(),
            "Kariyer.net": KariyerScraper(),
            "Youthall":   YouthallScraper(),
        }

        results: dict[str, str] = {}
        for name, scraper in sources.items():
            status = await self._check_source(name, scraper)
            results[name] = status
            self.db.log_health(name, "OK" if status == "OK" else "ERROR", status)

        self._last_check = datetime.utcnow()
        logger.info("Health check complete: %s", results)
        return results

    async def _check_source(self, name: str, scraper) -> str:
        """Run scraper with a short timeout to test reachability."""
        try:
            jobs = await asyncio.wait_for(scraper.scrape(), timeout=90)
            if jobs is not None:
                return "OK"
            return "OK (0 results)"
        except asyncio.TimeoutError:
            msg = "TIMEOUT after 90s"
            logger.warning("Health check TIMEOUT for %s", name)
            return f"ERROR: {msg}"
        except Exception as exc:
            msg = str(exc)[:120]
            logger.warning("Health check ERROR for %s: %s", name, msg)
            return f"ERROR: {msg}"

    def get_db_health(self) -> dict:
        """Return database statistics for the health report."""
        try:
            return self.db.get_stats()
        except Exception as exc:
            logger.error("DB stats failed: %s", exc)
            return {"total": "?", "by_source": {}, "by_category": {}}
