"""
Company Career Page Scraper
============================
One configurable Playwright scraper that handles every company in
config.COMPANY_CONFIGS. Adding a new company = adding one CompanyConfig
entry to config.py — no new code needed.

Strategy per company:
1. Load intern_url (or careers_url if not set)
2. Load any extra_urls
3. Parse job cards with adaptive selectors
4. Follow job links to detail pages for deadline/requirements
"""

import re
import asyncio
import logging
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

import config
from config import CompanyConfig
from db.database import Job
from .base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

# Generic selectors tried in order — works on most ATS-hosted pages
CARD_SELECTORS = [
    "[data-testid*='job']", "[data-qa*='job']",
    "li[class*='job']", "div[class*='job-card']", "div[class*='JobCard']",
    "article[class*='job']", ".posting", ".job-posting",
    "tr[class*='job']", "div[class*='position']",
    "div[class*='opening']", "div[class*='vacancy']",
    "div[class*='ilan']", "li[class*='ilan']",
    ".careers-item", ".career-item",
]

TITLE_SELECTORS = [
    "h1", "h2", "h3",
    "[class*='title']", "[class*='position']", "[class*='job-name']",
    "[class*='posting-name']", "[class*='job-title']",
    ".ilan-adi", ".pozisyon",
]

LINK_SELECTORS = ["a[href*='job']", "a[href*='career']", "a[href*='kariyer']", "a[href*='ilan']", "a"]
LOCATION_SELECTORS = ["[class*='location']", "[class*='city']", "[class*='sehir']", ".location", ".city"]
DATE_SELECTORS = ["time", "[class*='date']", "[class*='tarih']", "[datetime]"]
DEADLINE_SELECTORS = [
    "[class*='deadline']", "[class*='son-basvuru']", "[class*='son-tarih']",
    "[class*='bitis']", "[class*='closing']",
]

COMPANY_CONCURRENCY = 4
COMPANY_TIMEOUT_SECONDS = 45


class CompanyCareerScraper(BaseScraper):
    """Scrapes all company career pages defined in config.COMPANY_CONFIGS."""

    source_name = "Company"

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=5, max=30), reraise=True)
    async def scrape(self) -> list[Job]:
        self.logger.info("Scraping %d company career pages …", len(config.COMPANY_CONFIGS))
        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
        except ImportError as exc:
            raise ScraperError(str(exc))

        all_jobs: list[Job] = []
        opts = self.get_browser_context_options()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=opts["headless"])
            semaphore = asyncio.Semaphore(COMPANY_CONCURRENCY)

            async def scrape_one(company_cfg: CompanyConfig) -> list[Job]:
                async with semaphore:
                    return await asyncio.wait_for(
                        self._scrape_company_with_context(
                            browser, stealth_async, opts, company_cfg
                        ),
                        timeout=COMPANY_TIMEOUT_SECONDS,
                    )

            results = await asyncio.gather(
                *[scrape_one(company_cfg) for company_cfg in config.COMPANY_CONFIGS],
                return_exceptions=True,
            )

            for company_cfg, result in zip(config.COMPANY_CONFIGS, results):
                if isinstance(result, TimeoutError):
                    self.logger.warning(
                        "%s timed out after %ds.",
                        company_cfg.name,
                        COMPANY_TIMEOUT_SECONDS,
                    )
                elif isinstance(result, Exception):
                    self.logger.error("Error scraping %s: %s", company_cfg.name, result)
                else:
                    all_jobs.extend(result)
                    self.logger.info("%s: %d jobs found.", company_cfg.name, len(result))

            await browser.close()

        self.logger.info("Company pages total: %d jobs.", len(all_jobs))
        return all_jobs

    async def _scrape_company_with_context(
        self, browser, stealth_async, opts: dict, company_cfg: CompanyConfig
    ) -> list[Job]:
        context = await browser.new_context(
            locale=opts["locale"], timezone_id=opts["timezone_id"],
            viewport=opts["viewport"], user_agent=self.random_user_agent(),
        )
        page = await context.new_page()
        await stealth_async(page)

        try:
            return await self._scrape_company(page, company_cfg)
        finally:
            await context.close()

    async def _scrape_company(self, page, cfg: CompanyConfig) -> list[Job]:
        jobs: list[Job] = []

        # URLs to check: prefer intern_url, then careers_url, then extra_urls
        urls_to_check: list[str] = []
        if cfg.intern_url:
            urls_to_check.append(cfg.intern_url)
        elif cfg.careers_url:
            urls_to_check.append(cfg.careers_url)
        urls_to_check.extend(cfg.extra_urls)

        seen_urls: set[str] = set()

        for url in urls_to_check:
            page_jobs = await self._scrape_page(page, url, cfg)
            for j in page_jobs:
                if j.url not in seen_urls:
                    seen_urls.add(j.url)
                    jobs.append(j)

        return jobs

    async def _scrape_page(self, page, url: str, cfg: CompanyConfig) -> list[Job]:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            await self.random_sleep(0.5, 1.0)

            # Try to filter by keyword if the page is just the main careers page
            if cfg.search_keyword and url == cfg.careers_url:
                await self._try_search(page, cfg.search_keyword)

            # Scroll to load dynamic content
            for _ in range(2):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(0.5)

        except Exception as exc:
            self.logger.warning("Navigation failed for %s (%s): %s", cfg.name, url, exc)
            return []

        cards = await self._find_cards(page)
        if not cards:
            self.logger.debug("%s: no cards found at %s", cfg.name, url)
            return []

        jobs = []
        for card in cards[:config.MAX_JOBS_PER_SOURCE]:
            job = await self._parse_card(card, cfg, url)
            if job:
                jobs.append(job)
        return jobs

    async def _try_search(self, page, keyword: str) -> None:
        """Try to find a search box and filter by keyword."""
        try:
            search_sel = "input[type='search'], input[placeholder*='ara'], input[placeholder*='search'], input[name*='keyword'], input[name*='q']"
            inp = await page.query_selector(search_sel)
            if inp:
                await inp.fill(keyword)
                await inp.press("Enter")
                await asyncio.sleep(1)
        except Exception:
            pass

    async def _find_cards(self, page) -> list:
        for sel in CARD_SELECTORS:
            cards = await page.query_selector_all(sel)
            if len(cards) >= 1:
                return cards
        return []

    async def _parse_card(self, card, cfg: CompanyConfig, page_url: str) -> Job | None:
        try:
            # Title
            title = ""
            for sel in TITLE_SELECTORS:
                el = await card.query_selector(sel)
                if el:
                    t = (await el.inner_text()).strip()
                    if t and len(t) > 3:
                        title = t
                        break

            # Link
            url = ""
            for sel in LINK_SELECTORS:
                el = await card.query_selector(sel)
                if el:
                    href = (await el.get_attribute("href") or "").strip()
                    if href:
                        if href.startswith("http"):
                            url = href
                        else:
                            # Resolve relative URL using the company's base domain
                            from urllib.parse import urljoin
                            url = urljoin(page_url, href)
                        break

            # Location
            location = "Türkiye"
            for sel in LOCATION_SELECTORS:
                el = await card.query_selector(sel)
                if el:
                    t = (await el.inner_text()).strip()
                    if t:
                        location = t
                        break

            # Date
            posted_date = None
            for sel in DATE_SELECTORS:
                el = await card.query_selector(sel)
                if el:
                    raw = await el.get_attribute("datetime") or await el.inner_text()
                    posted_date = _parse_date(raw)
                    if posted_date:
                        break

            # Deadline
            deadline = None
            for sel in DEADLINE_SELECTORS:
                el = await card.query_selector(sel)
                if el:
                    raw = (await el.inner_text()).strip()
                    deadline = _parse_date(raw)
                    if deadline:
                        break

            if not title or len(title) < 3:
                return None

            return Job(
                title=title,
                company=cfg.name,
                location=location,
                source=cfg.name,
                url=url or page_url,
                posted_date=posted_date,
                deadline=deadline,
            )
        except Exception as exc:
            self.logger.debug("Card parse error for %s: %s", cfg.name, exc)
            return None


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
