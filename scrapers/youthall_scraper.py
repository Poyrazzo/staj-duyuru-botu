"""Youthall scraper using Playwright with stealth plugin.

Targets:
 - /tr/jobs/          → all internship/talent listings
 - Specifically looks for "Yetenek Programı" (Talent Programme) cards

Youthall is a React SPA; we wait for the job cards to hydrate before parsing.
"""

import re
import json
import logging
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

import config
from db.database import Job
from .base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.youthall.com"
JOBS_URL = f"{BASE_URL}/tr/jobs/?type=internship"
TALENT_URL = f"{BASE_URL}/tr/jobs/?type=talent_program"

CARD_SELECTORS = [
    "div[class*='JobCard']",
    "div[class*='job-card']",
    "div[class*='JobItem']",
    "div[class*='PositionCard']",
    "article[class*='job']",
    "li[class*='job']",
    "div.job-list-item",
    "[data-cy*='job']",
    "[data-testid*='job']",
]

TITLE_SEL = "[class*='JobCard__title'], [class*='job-title'], h3, h2"
COMPANY_SEL = "[class*='JobCard__company'], [class*='company-name'], [class*='employer']"
LOCATION_SEL = "[class*='location'], [class*='city']"
DATE_SEL = "[class*='date'], [class*='time'], time"
LINK_SEL = "a"

MAX_SCROLL_ATTEMPTS = 8


class YouthallScraper(BaseScraper):
    source_name = "Youthall"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=10, max=60),
        reraise=True,
    )
    async def scrape(self) -> list[Job]:
        self.logger.info("Scraping Youthall …")
        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
        except ImportError as exc:
            raise ScraperError(f"Playwright not installed: {exc}") from exc

        all_jobs: list[Job] = []
        opts = self.get_browser_context_options()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=opts["headless"])
            context = await browser.new_context(
                locale=opts["locale"],
                timezone_id=opts["timezone_id"],
                viewport=opts["viewport"],
                user_agent=opts["user_agent"],
            )
            page = await context.new_page()
            await stealth_async(page)

            try:
                # Intercept API responses for structured data when available
                api_jobs = await self._try_api_intercept(page, context)
                if api_jobs:
                    all_jobs.extend(api_jobs)
                else:
                    # Fallback: DOM scraping
                    for url in (JOBS_URL, TALENT_URL):
                        jobs = await self._scrape_url(page, url)
                        all_jobs.extend(jobs)
                        await self.random_sleep()
            finally:
                await context.close()
                await browser.close()

        # Deduplicate within this source
        seen: set[str] = set()
        unique: list[Job] = []
        for j in all_jobs:
            if j.url not in seen:
                seen.add(j.url)
                unique.append(j)

        self.logger.info("Youthall: %d listings fetched.", len(unique))
        return unique

    async def _try_api_intercept(self, page, context) -> list[Job]:
        """Attempt to capture the JSON API that Youthall's React app calls."""
        captured: list[dict] = []

        async def handle_response(response):
            try:
                if "api" in response.url and "job" in response.url:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            if isinstance(data, dict):
                                results = (
                                    data.get("results")
                                    or data.get("data")
                                    or data.get("jobs")
                                    or []
                                )
                                if isinstance(results, list):
                                    captured.extend(results)
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("response", handle_response)

        try:
            await page.goto(JOBS_URL, wait_until="domcontentloaded", timeout=20_000)
            await self.random_sleep(2, 3)
            await page.goto(TALENT_URL, wait_until="domcontentloaded", timeout=20_000)
            await self.random_sleep(2, 3)
        except Exception as exc:
            self.logger.debug("API intercept navigation failed: %s", exc)
            return []

        if not captured:
            return []

        jobs: list[Job] = []
        for item in captured:
            job = self._api_item_to_job(item)
            if job:
                jobs.append(job)
        return jobs

    def _api_item_to_job(self, item: dict) -> Job | None:
        try:
            title = (
                item.get("title")
                or item.get("position")
                or item.get("name", "")
            ).strip()

            company_data = item.get("company") or item.get("employer") or {}
            if isinstance(company_data, dict):
                company = company_data.get("name", "")
            else:
                company = str(company_data)
            company = company.strip()

            location = (
                item.get("location")
                or item.get("city")
                or "Türkiye"
            )
            if isinstance(location, dict):
                location = location.get("name", "Türkiye")

            slug = item.get("slug") or item.get("id", "")
            url = (
                item.get("url")
                or item.get("apply_url")
                or (f"{BASE_URL}/tr/jobs/{slug}/" if slug else "")
            )

            description = item.get("description") or item.get("summary") or ""

            posted_raw = item.get("created_at") or item.get("published_at") or ""
            posted_date = posted_raw[:10] if posted_raw else None

            if not title or not company or not url:
                return None

            return Job(
                title=title,
                company=company,
                location=str(location),
                source=self.source_name,
                url=url,
                description=str(description),
                posted_date=posted_date,
            )
        except Exception as exc:
            self.logger.debug("API item parse error: %s", exc)
            return None

    async def _scrape_url(self, page, url: str) -> list[Job]:
        jobs: list[Job] = []
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await self.random_sleep(2, 5)
        except Exception as exc:
            self.logger.warning("Navigation failed for %s: %s", url, exc)
            return []

        # Wait for cards to render
        for sel in CARD_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=8_000)
                break
            except Exception:
                continue

        # Infinite scroll
        prev_count = 0
        for _ in range(MAX_SCROLL_ATTEMPTS):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            import asyncio
            await asyncio.sleep(1.5)
            cards = await self._find_cards(page)
            if len(cards) == prev_count:
                break
            prev_count = len(cards)

        cards = await self._find_cards(page)
        for card in cards:
            job = await self._parse_card(card, url)
            if job:
                jobs.append(job)

        if not jobs:
            fallback = await self.harvest_job_links(page, self.source_name, BASE_URL)
            jobs.extend(fallback)

        return jobs

    async def _find_cards(self, page) -> list:
        for sel in CARD_SELECTORS:
            cards = await page.query_selector_all(sel)
            if cards:
                return cards
        return []

    async def _parse_card(self, card, page_url: str) -> Job | None:
        try:
            title = ""
            for sel in TITLE_SEL.split(", "):
                el = await card.query_selector(sel)
                if el:
                    title = (await el.inner_text()).strip()
                    if title:
                        break

            company = ""
            for sel in COMPANY_SEL.split(", "):
                el = await card.query_selector(sel)
                if el:
                    company = (await el.inner_text()).strip()
                    if company:
                        break

            location = "Türkiye"
            for sel in LOCATION_SEL.split(", "):
                el = await card.query_selector(sel)
                if el:
                    location = (await el.inner_text()).strip()
                    if location:
                        break

            date_str = None
            for sel in DATE_SEL.split(", "):
                el = await card.query_selector(sel)
                if el:
                    raw = await el.get_attribute("datetime") or await el.inner_text()
                    date_str = raw.strip()
                    break
            posted_date = _parse_youthall_date(date_str)

            # Build URL from card link
            link_el = await card.query_selector(LINK_SEL)
            href = ""
            if link_el:
                href = (await link_el.get_attribute("href") or "").strip()
            url = href if href.startswith("http") else f"{BASE_URL}{href}" if href else ""

            if not title or not company:
                return None

            return Job(
                title=title,
                company=company,
                location=location,
                source=self.source_name,
                url=url or page_url,
                posted_date=posted_date,
            )
        except Exception as exc:
            self.logger.debug("Card parse error: %s", exc)
            return None


def _parse_youthall_date(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    # ISO datetime
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    if "bugün" in raw.lower() or "today" in raw.lower():
        return datetime.utcnow().strftime("%Y-%m-%d")
    match = re.search(r"(\d+)\s*(gün|day|saat|hour)", raw, re.IGNORECASE)
    if match:
        n = int(match.group(1))
        unit = match.group(2).lower()
        if "saat" in unit or "hour" in unit:
            n = max(n // 24, 0)
        return (datetime.utcnow() - timedelta(days=n)).strftime("%Y-%m-%d")
    return None
