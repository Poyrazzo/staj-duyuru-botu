"""
Kariyer Kapısı scraper — Turkish government-backed internship portal.
URL: https://www.kariyerkapisi.cbiko.gov.tr/
"""

import re
import logging
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

import config
from db.database import Job
from .base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kariyer.gov.tr"
# Primary: public Turkish government career portal (accessible outside Turkey)
SEARCH_URL = f"{BASE_URL}/is-ilanlari?arama=staj"
# Fallback: old cbiko domain (may only resolve inside Turkey)
STAJ_URL = "https://www.kariyerkapisi.cbiko.gov.tr/Arama/staj"


class KariyerKapisiScraper(BaseScraper):
    source_name = "Kariyer Kapısı"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=8, max=40), reraise=True)
    async def scrape(self) -> list[Job]:
        self.logger.info("Scraping Kariyer Kapısı …")
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
                for url in (STAJ_URL, SEARCH_URL):
                    jobs = await self._scrape_page(page, url)
                    all_jobs.extend(jobs)
                    await self.random_sleep()
            finally:
                await context.close()
                await browser.close()

        # Deduplicate by URL
        seen: set[str] = set()
        unique = []
        for j in all_jobs:
            if j.url not in seen:
                seen.add(j.url)
                unique.append(j)

        self.logger.info("Kariyer Kapısı: %d listings.", len(unique))
        return unique

    async def _scrape_page(self, page, url: str) -> list[Job]:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await self.random_sleep(2, 5)
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                import asyncio; await asyncio.sleep(1)
        except Exception as exc:
            self.logger.warning("KariyerKapısı nav error: %s", exc)
            return []

        card_selectors = [
            # Government portal specific
            ".ilan-card", ".staj-card", ".card-ilan",
            "div[class*='ilan']", "li[class*='ilan']",
            ".ilan-listesi li", ".sonuc-listesi li",
            ".search-result-item", ".result-item",
            # Bootstrap / generic
            ".listing-item", ".panel-body .row",
            "table.table tbody tr",
            ".card", "article",
            # Broad last resort
            "li",
        ]
        cards = []
        for sel in card_selectors:
            found = await page.query_selector_all(sel)
            if found and len(found) > 1:
                cards = found
                break

        jobs = []
        for card in cards:
            job = await self._parse_card(card)
            if job:
                jobs.append(job)

        if not jobs:
            fallback = await self.harvest_job_links(page, self.source_name, BASE_URL)
            jobs.extend(fallback)

        return jobs

    async def _parse_card(self, card) -> Job | None:
        try:
            title_el = await card.query_selector("h2, h3, h4, .ilan-adi, .job-title, [class*='title']")
            title = (await title_el.inner_text()).strip() if title_el else ""

            company_el = await card.query_selector(".firma-adi, .company, [class*='company'], [class*='firma']")
            company = (await company_el.inner_text()).strip() if company_el else ""

            location_el = await card.query_selector(".sehir, .location, [class*='sehir'], [class*='city']")
            location = (await location_el.inner_text()).strip() if location_el else "Türkiye"

            # Government site often shows application deadline prominently
            deadline_el = await card.query_selector(
                ".son-basvuru, [class*='deadline'], [class*='son-tarih'], [class*='bitis']"
            )
            deadline_raw = (await deadline_el.inner_text()).strip() if deadline_el else None
            deadline = _parse_deadline(deadline_raw)

            date_el = await card.query_selector(".tarih, [class*='tarih'], [class*='date'], time")
            date_raw = (await date_el.inner_text()).strip() if date_el else None
            posted_date = _parse_deadline(date_raw)

            link_el = await card.query_selector("a[href]")
            href = (await link_el.get_attribute("href") or "").strip() if link_el else ""
            url = href if href.startswith("http") else f"{BASE_URL}{href}" if href else ""

            if not title:
                return None

            return Job(
                title=title,
                company=company or "Bilinmiyor",
                location=location,
                source=self.source_name,
                url=url,
                posted_date=posted_date,
                deadline=deadline,
            )
        except Exception as exc:
            self.logger.debug("KariyerKapısı card error: %s", exc)
            return None


def _parse_deadline(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = re.sub(r"(?i)(son başvuru|deadline|tarih|bitiş)[:\s]*", "", raw).strip()
    match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", raw)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    return None
