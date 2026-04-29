"""Vizyoner Genç scraper — Turkish youth & internship platform."""

import re
import logging
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

import config
from db.database import Job
from .base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

BASE_URL = "https://vizyonergenc.com"
STAJ_URL = "https://vizyonergenc.com/staj-ilanlari"
PROGRAM_URL = "https://vizyonergenc.com/yetenek-programlari"


class VizyonerGencScraper(BaseScraper):
    source_name = "Vizyoner Genç"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=8, max=40), reraise=True)
    async def scrape(self) -> list[Job]:
        self.logger.info("Scraping Vizyoner Genç …")
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
                for url in (STAJ_URL, PROGRAM_URL):
                    jobs = await self._scrape_url(page, url)
                    all_jobs.extend(jobs)
                    await self.random_sleep()
            finally:
                await context.close()
                await browser.close()

        self.logger.info("Vizyoner Genç: %d listings.", len(all_jobs))
        return all_jobs

    async def _scrape_url(self, page, url: str) -> list[Job]:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await self.random_sleep(2, 4)
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                import asyncio; await asyncio.sleep(1.2)
        except Exception as exc:
            self.logger.warning("VizyonerGenç nav error for %s: %s", url, exc)
            return []

        selectors = [
            # Specific class patterns for Turkish/WordPress sites
            ".ilan-item", ".staj-item", ".program-item", ".ilan-kutusu",
            "div[class*='ilan']", "div[class*='staj']", "div[class*='program']",
            # Bootstrap / generic card patterns
            ".card", ".card-body", ".post-item", ".blog-post", ".entry",
            ".haber", ".content-item",
            # Bootstrap grid cells
            ".col-md-4 article", ".col-lg-4 article", ".col-sm-6 article",
            # Data attrs
            "[data-type='ilan']", "[data-category*='staj']",
            # Broad last resort
            "article", "li",
        ]
        cards = []
        for sel in selectors:
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
            title_el = await card.query_selector("h2, h3, h4, .title, .ilan-baslik")
            title = (await title_el.inner_text()).strip() if title_el else ""

            company_el = await card.query_selector(".firma, .company, .sirket, [class*='company']")
            company = (await company_el.inner_text()).strip() if company_el else ""

            # Deadline is commonly shown on Vizyoner Genç
            deadline_el = await card.query_selector(".son-basvuru, .deadline, [class*='tarih'], [class*='date']")
            deadline_raw = (await deadline_el.inner_text()).strip() if deadline_el else None
            deadline = _clean_deadline(deadline_raw)

            location_el = await card.query_selector(".sehir, .location, [class*='city']")
            location = (await location_el.inner_text()).strip() if location_el else "Türkiye"

            link_el = await card.query_selector("a[href]")
            href = (await link_el.get_attribute("href") or "").strip() if link_el else ""
            url = href if href.startswith("http") else f"{BASE_URL}{href}" if href else ""

            if not title:
                return None
            if not company:
                # Try to get company from page title context
                company = "Bilinmiyor"

            return Job(
                title=title,
                company=company,
                location=location,
                source=self.source_name,
                url=url,
                deadline=deadline,
            )
        except Exception as exc:
            self.logger.debug("VizyonerGenç card error: %s", exc)
            return None


def _clean_deadline(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    # Remove label prefix: "Son Başvuru: 31.05.2025" → "31.05.2025"
    raw = re.sub(r"(?i)(son başvuru|deadline|tarih)[:\s]*", "", raw).strip()
    match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", raw)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    return raw if raw else None
