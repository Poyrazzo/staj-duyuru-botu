"""
Extra Job Boards Scraper
========================
Covers: SecretCV, Yenibiriş, Co-Matching, İSO Staj

All use Playwright with stealth. They're lightweight Turkish portals
that regularly list internship programs.
"""

import re
import asyncio
import logging
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

import config
from db.database import Job
from .base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)


class ExtraBoardsScraper(BaseScraper):
    """Scrapes SecretCV, Yenibiriş, Co-Matching, and İSO Staj."""

    source_name = "ExtraBoards"

    BOARD_CONFIGS = [
        {
            "name": "SecretCV",
            "url": "https://www.secretcv.com/is-ilanlari?keyword=staj&sort=date",
            "card_sel": ".job-list-item, .ilan-item, [class*='job-card'], article",
            "title_sel": "h2, h3, [class*='title'], [class*='pozisyon']",
            "company_sel": "[class*='company'], [class*='firma'], .employer",
            "location_sel": "[class*='location'], [class*='sehir']",
            "link_sel": "a[href]",
            "date_sel": "[class*='date'], time",
        },
        {
            "name": "Yenibiriş",
            "url": "https://www.yenibis.com/is-ilani?q=staj&sort=date",
            "card_sel": ".job-item, .ilan, [class*='job'], article",
            "title_sel": "h2, h3, [class*='title'], [class*='baslik']",
            "company_sel": "[class*='company'], [class*='firma']",
            "location_sel": "[class*='city'], [class*='sehir'], [class*='location']",
            "link_sel": "a[href]",
            "date_sel": "time, [class*='date']",
        },
        {
            "name": "Co-Matching",
            "url": "https://www.co-matching.com/staj",
            "card_sel": "[class*='JobCard'], [class*='job-card'], .position-card, article",
            "title_sel": "h2, h3, [class*='title'], [class*='position']",
            "company_sel": "[class*='company'], [class*='employer']",
            "location_sel": "[class*='location'], [class*='city']",
            "link_sel": "a[href]",
            "date_sel": "time, [class*='date']",
        },
        {
            "name": "İSO Staj",
            "url": "https://staj.iso.org.tr/",
            "card_sel": ".staj-ilan, .ilan-card, [class*='ilan'], .card, article, tr",
            "title_sel": "h2, h3, td:first-child, [class*='title'], [class*='ilan-adi']",
            "company_sel": "[class*='firma'], [class*='company'], td:nth-child(2)",
            "location_sel": "[class*='sehir'], [class*='location']",
            "link_sel": "a[href]",
            "date_sel": "[class*='tarih'], [class*='date'], td:last-child, time",
        },
    ]

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=5, max=30))
    async def scrape(self) -> list[Job]:
        self.logger.info("Scraping extra job boards …")
        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
        except ImportError as exc:
            raise ScraperError(str(exc))

        all_jobs: list[Job] = []
        opts = self.get_browser_context_options()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=opts["headless"])

            for board in self.BOARD_CONFIGS:
                context = await browser.new_context(
                    locale=opts["locale"], timezone_id=opts["timezone_id"],
                    viewport=opts["viewport"], user_agent=self.random_user_agent(),
                )
                page = await context.new_page()
                await stealth_async(page)

                try:
                    jobs = await self._scrape_board(page, board)
                    all_jobs.extend(jobs)
                    self.logger.info("%s: %d jobs.", board["name"], len(jobs))
                except Exception as exc:
                    self.logger.warning("%s scrape error: %s", board["name"], exc)
                finally:
                    await context.close()
                    await self.random_sleep(2, 4)

            await browser.close()

        self.logger.info("ExtraBoards total: %d jobs.", len(all_jobs))
        return all_jobs

    async def _scrape_board(self, page, board: dict) -> list[Job]:
        try:
            await page.goto(board["url"], wait_until="domcontentloaded", timeout=30_000)
            await self.random_sleep(2, 4)
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(1)
        except Exception as exc:
            self.logger.warning("%s nav error: %s", board["name"], exc)
            return []

        cards = []
        for sel in board["card_sel"].split(", "):
            found = await page.query_selector_all(sel.strip())
            if found and len(found) > 1:
                cards = found
                break

        base_url = board["url"].split("/")[0] + "//" + board["url"].split("/")[2]
        jobs = []
        for card in cards[:config.MAX_JOBS_PER_SOURCE]:
            job = await self._parse_card(card, board, base_url)
            if job:
                jobs.append(job)

        if not jobs:
            fallback = await self.harvest_job_links(page, board["name"], base_url)
            jobs.extend(fallback[:config.MAX_JOBS_PER_SOURCE])

        return jobs

    async def _parse_card(self, card, board: dict, base_url: str) -> Job | None:
        try:
            title = await _first_text(card, board["title_sel"])
            if not title or len(title) < 3:
                return None

            company = await _first_text(card, board["company_sel"]) or "Bilinmiyor"
            location = await _first_text(card, board["location_sel"]) or "Türkiye"
            date_raw = await _first_text(card, board["date_sel"])
            posted_date = _parse_date(date_raw)

            # Build URL
            link_el = await card.query_selector(board["link_sel"])
            href = (await link_el.get_attribute("href") or "").strip() if link_el else ""
            url = href if href.startswith("http") else f"{base_url}{href}" if href else base_url

            return Job(
                title=title,
                company=company,
                location=location,
                source=board["name"],
                url=url,
                posted_date=posted_date,
            )
        except Exception as exc:
            self.logger.debug("Card error in %s: %s", board["name"], exc)
            return None


async def _first_text(card, selectors_str: str) -> str:
    """Try each selector and return the first non-empty text."""
    for sel in selectors_str.split(", "):
        try:
            el = await card.query_selector(sel.strip())
            if el:
                t = (await el.inner_text()).strip()
                if t:
                    return t
        except Exception:
            continue
    return ""


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", raw)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    if "bugün" in raw.lower() or "today" in raw.lower():
        return datetime.utcnow().strftime("%Y-%m-%d")
    match = re.search(r"(\d+)\s*(gün|day)", raw, re.IGNORECASE)
    if match:
        return (datetime.utcnow() - timedelta(days=int(match.group(1)))).strftime("%Y-%m-%d")
    return None
