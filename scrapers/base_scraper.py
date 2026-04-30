"""Abstract base scraper with shared utilities."""

import abc
import random
import asyncio
import logging
from typing import Optional

from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

import config
from db.database import Job

logger = logging.getLogger(__name__)

_ua = UserAgent(browsers=["chrome", "firefox"], os=["windows", "linux"])


class ScraperError(Exception):
    pass


class BaseScraper(abc.ABC):
    """Common interface and helpers for all scrapers."""

    source_name: str = "unknown"

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    async def scrape(self) -> list[Job]:
        """Fetch and return a list of Job objects. Must be overridden."""

    # ── Shared helpers ───────────────────────────────────────

    @staticmethod
    async def random_sleep(min_s: float = None, max_s: float = None) -> None:
        lo = min_s if min_s is not None else config.MIN_SLEEP
        hi = max_s if max_s is not None else config.MAX_SLEEP
        delay = random.uniform(lo, hi)
        await asyncio.sleep(delay)

    @staticmethod
    def random_user_agent() -> str:
        try:
            return _ua.random
        except Exception:
            return (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )

    @staticmethod
    def get_browser_context_options(headless: Optional[bool] = None) -> dict:
        h = headless if headless is not None else config.HEADLESS
        opts: dict = {
            "headless": h,
            "locale": config.LOCALE,
            "timezone_id": config.TIMEZONE,
            "viewport": config.VIEWPORT,
            "user_agent": BaseScraper.random_user_agent(),
            "java_script_enabled": True,
            "accept_downloads": False,
        }
        if config.HTTP_PROXY:
            opts["proxy"] = {"server": config.HTTP_PROXY}
        return opts

    @staticmethod
    async def harvest_job_links(page, source_name: str, base_url: str) -> list[Job]:
        """Last-resort fallback: scan all <a> tags for internship-looking links."""
        intern_kw = {"staj", "intern", "program", "trainee", "aday", "yetenek",
                     "ilan", "job", "kariyer", "position", "pozisyon"}
        path_kw   = {"/ilan", "/job", "/staj", "/intern", "/pozisyon",
                     "/position", "/kariyer", "/program"}
        # Generic navigation/section titles that are NOT job listings
        nav_blocklist = {
            "staj ilanları", "online staj programları", "ücretsiz cv hazırlama",
            "kişisel gelişim programı", "sertifika programları", "yetenek programları",
            "aday girişi", "tüm ilanlar", "tümünü gör", "tümünü incele",
            "daha fazla", "hepsini gör", "başvuru yap", "iş ilanları",
            "kariyer fırsatları", "haftanın staj ilanları", "staj seferberliğine katıl",
            "online staj", "staja başla", "ilanları gör", "tüm staj ilanları",
        }
        try:
            links = await page.query_selector_all("a[href]")
        except Exception:
            return []

        jobs: list[Job] = []
        seen: set[str] = set()
        for link in links[:400]:
            try:
                href = (await link.get_attribute("href") or "").strip()
                text = (await link.inner_text()).strip()
                # Title must look like a real job posting, not a nav label
                if not text or len(text) < 20 or len(text) > 300:
                    continue
                if text.lower() in nav_blocklist:
                    continue
                url = (
                    href if href.startswith("http")
                    else f"{base_url}{href}" if href.startswith("/")
                    else ""
                )
                if not url or url in seen:
                    continue
                haystack = (text + " " + href).lower()
                if (any(kw in haystack for kw in intern_kw)
                        or any(pk in href.lower() for pk in path_kw)):
                    seen.add(url)
                    jobs.append(Job(
                        title=text[:200],
                        company="Bilinmiyor",
                        location="Türkiye",
                        source=source_name,
                        url=url,
                    ))
            except Exception:
                continue
        return jobs
