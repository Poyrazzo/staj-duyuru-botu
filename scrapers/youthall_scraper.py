"""Youthall scraper — server-rendered Turkish internship/talent portal.

DOM structure (verified 2026-04):
  div.jobs > a[href=full_url] > div.jobs-body > div.jobs-content
    h5                         → title
    img.jobs-content-logo[alt] → "Company Name logo"  → strip " logo"
    div.jobs-content-desc      → description snippet
    div.jobs-content-bottom > div.jobs-tag (0=type, 1=deadline, 2=location)
"""

import re
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
                for url in (JOBS_URL, TALENT_URL):
                    jobs = await self._scrape_url(page, url)
                    all_jobs.extend(jobs)
                    await self.random_sleep(1, 3)
            finally:
                await context.close()
                await browser.close()

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[Job] = []
        for j in all_jobs:
            if j.url not in seen:
                seen.add(j.url)
                unique.append(j)

        self.logger.info("Youthall: %d listings fetched.", len(unique))
        return unique

    async def _scrape_url(self, page, url: str) -> list[Job]:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await self.random_sleep(2, 3)
            # Scroll to trigger lazy-loaded images / more cards
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                import asyncio
                await asyncio.sleep(1.2)
        except Exception as exc:
            self.logger.warning("Youthall nav error for %s: %s", url, exc)
            return []

        cards = await page.query_selector_all("div.jobs")
        self.logger.debug("Youthall: found %d cards on %s", len(cards), url)

        jobs: list[Job] = []
        for card in cards[:config.MAX_JOBS_PER_SOURCE]:
            job = await self._parse_card(card)
            if job:
                jobs.append(job)

        return jobs

    async def _parse_card(self, card) -> Job | None:
        try:
            # URL lives on the wrapping <a> tag
            link_el = await card.query_selector("a[href]")
            if not link_el:
                return None
            href = (await link_el.get_attribute("href") or "").strip()
            job_url = href if href.startswith("http") else f"{BASE_URL}{href}" if href else ""
            # Skip generic listing URLs
            if not job_url or job_url.rstrip("/") in (BASE_URL, f"{BASE_URL}/tr/jobs"):
                return None

            # Title
            title_el = await card.query_selector("div.jobs-content-title h5, div.jobs-content-title h4, div.jobs-content-title h3")
            title = (await title_el.inner_text()).strip() if title_el else ""
            if not title:
                return None

            # Company — from logo alt text: "AXA Sigorta logo" → "AXA Sigorta"
            logo_el = await card.query_selector("img.jobs-content-logo")
            company = ""
            if logo_el:
                alt = (await logo_el.get_attribute("alt") or "").strip()
                company = re.sub(r"\s+logo\s*$", "", alt, flags=re.IGNORECASE).strip()
            if not company:
                company = "Bilinmiyor"

            # Description snippet
            desc_el = await card.query_selector("div.jobs-content-desc")
            description = (await desc_el.inner_text()).strip() if desc_el else ""

            # Tags: [0]=type, [1]=deadline, [2]=location
            tags = await card.query_selector_all("div.jobs-content-bottom div.jobs-tag")
            deadline = None
            location = "Türkiye"
            if len(tags) >= 2:
                deadline_raw = (await tags[1].inner_text()).strip()
                deadline = _parse_deadline(deadline_raw)
            if len(tags) >= 3:
                loc_raw = (await tags[2].inner_text()).strip()
                # Clean up whitespace/icons
                loc_raw = re.sub(r"\s+", " ", loc_raw).strip()
                # Remove font-awesome icon characters (non-ASCII leftovers)
                loc_raw = re.sub(r"[^\w\s,+ğüşöçıİĞÜŞÖÇ]", "", loc_raw).strip()
                if loc_raw:
                    location = loc_raw

            return Job(
                title=title,
                company=company,
                location=location,
                source=self.source_name,
                url=job_url,
                description=description[:300] if description else "",
                deadline=deadline,
            )
        except Exception as exc:
            self.logger.debug("Youthall card parse error: %s", exc)
            return None


def _parse_deadline(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    # "31.05.2026" format
    match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", raw)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    return None
