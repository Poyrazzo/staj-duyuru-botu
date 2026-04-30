"""Toptalent.co scraper — Turkish internship & talent platform."""

import re
import logging
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

import config
from db.database import Job
from .base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

BASE_URL = "https://toptalent.co"
# Verified URLs — the /tr/ilanlar/ path returns 404
INTERN_URL = "https://toptalent.co/is-ilanlari/staj-ilanlari"
TALENT_URL = "https://toptalent.co/is-ilanlari/yetenek-programlari"

# DOM structure (verified May 2025):
# Each job is <a class="position" href="/slug"> wrapping a <div class="card">
# Title:   .card-title  (h5)
# Company+Location: first <p> inside .card-body  e.g. "Byqee Tüm Türkiye"
# Deadline: second <p> inside .card-body  e.g. "Son 40 Gün\nBaşvur"
CARD_SEL = "a.position"

# Known Turkish city / region names to split company from location
_LOCATION_TOKENS = {
    "tüm türkiye", "istanbul", "İstanbul", "ankara", "İzmir", "izmir",
    "bursa", "antalya", "kocaeli", "anadolu", "avrupa", "remote", "uzaktan",
    "hibrit", "hybrid", "online", "türkiye",
}


class ToptalentScraper(BaseScraper):
    source_name = "Toptalent"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=8, max=40), reraise=True)
    async def scrape(self) -> list[Job]:
        self.logger.info("Scraping Toptalent.co …")
        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
        except ImportError as exc:
            raise ScraperError(str(exc))

        all_jobs: list[Job] = []
        opts = self.get_browser_context_options()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=opts["headless"])
            context = await browser.new_context(
                locale=opts["locale"], timezone_id=opts["timezone_id"],
                viewport=opts["viewport"], user_agent=opts["user_agent"],
            )
            page = await context.new_page()
            await stealth_async(page)

            try:
                for url in (INTERN_URL, TALENT_URL):
                    jobs = await self._scrape_url(page, url)
                    all_jobs.extend(jobs)
                    await self.random_sleep()
            finally:
                await context.close()
                await browser.close()

        # Deduplicate
        seen: set[str] = set()
        unique = []
        for j in all_jobs:
            if j.url not in seen:
                seen.add(j.url)
                unique.append(j)

        self.logger.info("Toptalent: %d listings.", len(unique))
        return unique

    async def _scrape_url(self, page, url: str) -> list[Job]:
        try:
            await page.goto(url, wait_until="networkidle", timeout=40_000)
            await self.random_sleep(2, 3)
            for _ in range(4):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                import asyncio; await asyncio.sleep(0.8)
        except Exception as exc:
            self.logger.warning("Toptalent nav error: %s", exc)
            return []

        cards = await page.query_selector_all(CARD_SEL)
        jobs = []
        for card in cards[:config.MAX_JOBS_PER_SOURCE]:
            job = await self._parse_card(card)
            if job:
                jobs.append(job)

        if not jobs:
            jobs = await self.harvest_job_links(page, self.source_name, BASE_URL)

        return jobs

    async def _parse_card(self, card) -> Job | None:
        try:
            # URL is on the <a class="position"> element itself
            href = (await card.get_attribute("href") or "").strip()
            url = href if href.startswith("http") else f"{BASE_URL}{href}" if href else ""
            if not url:
                return None

            title_el = await card.query_selector(".card-title, h5, h4, h3")
            title = (await title_el.inner_text()).strip() if title_el else ""
            if not title:
                return None

            # First <p> has "Company Location" merged in one string
            ps = await card.query_selector_all("p")
            company = "Bilinmiyor"
            location = "Türkiye"
            deadline = None

            if ps:
                company_loc = (await ps[0].inner_text()).strip()
                company, location = _split_company_location(company_loc)

            if len(ps) > 1:
                deadline_raw = (await ps[1].inner_text()).strip()
                deadline = _parse_deadline(deadline_raw)

            return Job(
                title=title,
                company=company,
                location=location,
                source=self.source_name,
                url=url,
                deadline=deadline,
            )
        except Exception as exc:
            self.logger.debug("Toptalent card error: %s", exc)
            return None


def _split_company_location(text: str) -> tuple[str, str]:
    """Split 'Byqee Tüm Türkiye' → ('Byqee', 'Tüm Türkiye')."""
    text = text.strip()
    lower = text.lower()
    for loc in sorted(_LOCATION_TOKENS, key=len, reverse=True):
        idx = lower.find(loc.lower())
        if idx > 0:
            company = text[:idx].strip().rstrip(",").strip()
            location = text[idx:].strip()
            if company:
                return company, location
    return text, "Türkiye"


def _parse_deadline(raw: str) -> str | None:
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
