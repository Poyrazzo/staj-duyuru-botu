"""Kariyer.net scraper using Playwright with stealth plugin."""

import re
import logging
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

import config
from db.database import Job
from .base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

# Kariyer.net listing card selectors (verified against current DOM, May 2025)
# Each card is an <article> or <div> with class containing "list-items-wrapper"
CARD_SELECTOR = "div.list-items-wrapper > div.list-item"
TITLE_SEL = "a.list-item-title"
COMPANY_SEL = "a.company-name, span.company-name"
LOCATION_SEL = "div.list-item-info span.city"
DATE_SEL = "div.list-item-info span.date"
LINK_SEL = "a.list-item-title"
NEXT_PAGE_SEL = "a[title='Sonraki Sayfa'], a.pagination-next"

MAX_PAGES = 5  # stop after N pages to respect rate limits


class KariyerScraper(BaseScraper):
    source_name = "Kariyer.net"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=10, max=60),
        reraise=True,
    )
    async def scrape(self) -> list[Job]:
        self.logger.info("Scraping Kariyer.net …")
        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
        except ImportError as exc:
            raise ScraperError(f"Playwright not installed: {exc}") from exc

        jobs: list[Job] = []
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
                jobs = await self._scrape_pages(page)
            finally:
                await context.close()
                await browser.close()

        self.logger.info("Kariyer.net: %d listings fetched.", len(jobs))
        return jobs

    async def _scrape_pages(self, page) -> list[Job]:
        jobs: list[Job] = []
        url = config.KARIYER_URL
        page_num = 0

        # Warm up: visit homepage first so CF can set cookies/complete JS challenge
        await page.set_extra_http_headers({
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        try:
            await page.goto("https://www.kariyer.net/", wait_until="networkidle", timeout=30_000)
            await self.random_sleep(2, 4)
        except Exception:
            pass

        while url and page_num < MAX_PAGES:
            page_num += 1
            self.logger.debug("Kariyer page %d: %s", page_num, url)
            try:
                await page.goto(url, wait_until="networkidle", timeout=45_000)
                await self.random_sleep(2, 4)
                # Check for Cloudflare block
                content = await page.content()
                if "Access to this page has been denied" in content or "Just a moment" in content:
                    self.logger.warning("Kariyer.net: Cloudflare block on page %d, waiting…", page_num)
                    import asyncio as _aio; await _aio.sleep(5)
                    content = await page.content()
                    if "Access to this page has been denied" in content:
                        self.logger.warning("Kariyer.net: still blocked, skipping.")
                        break
                # Scroll to trigger lazy-load
                await _scroll_page(page)
                await self.random_sleep(1, 3)
            except Exception as exc:
                self.logger.warning("Navigation error on page %d: %s", page_num, exc)
                break

            cards = await page.query_selector_all(CARD_SELECTOR)
            if not cards:
                cards = await page.query_selector_all("div.job-list-item, article.job-item, [class*='jobItem'], [class*='job-item']")

            if not cards:
                # Fallback: harvest any job links on the page
                fallback = await self.harvest_job_links(
                    page, self.source_name, "https://www.kariyer.net"
                )
                jobs.extend(fallback)
                if fallback:
                    self.logger.info("Kariyer.net page %d: %d jobs via link-harvest fallback", page_num, len(fallback))
            else:
                for card in cards:
                    job = await self._parse_card(card, page)
                    if job:
                        jobs.append(job)

            await self.random_sleep()

            # Pagination
            next_btn = await page.query_selector(NEXT_PAGE_SEL)
            if next_btn:
                href = await next_btn.get_attribute("href")
                if href:
                    url = href if href.startswith("http") else f"https://www.kariyer.net{href}"
                else:
                    break
            else:
                break

        return jobs

    async def _parse_card(self, card, page) -> Job | None:
        try:
            title_el = await card.query_selector(TITLE_SEL)
            if not title_el:
                title_el = await card.query_selector("a[href*='is-ilani']")
            title = (await title_el.inner_text()).strip() if title_el else ""

            company_el = await card.query_selector(COMPANY_SEL)
            company = (await company_el.inner_text()).strip() if company_el else ""

            location_el = await card.query_selector(LOCATION_SEL)
            location = (await location_el.inner_text()).strip() if location_el else "Türkiye"

            date_el = await card.query_selector(DATE_SEL)
            date_str = (await date_el.inner_text()).strip() if date_el else None
            posted_date = _parse_kariyer_date(date_str)

            link_el = await card.query_selector(LINK_SEL)
            href = (await link_el.get_attribute("href")).strip() if link_el else ""
            url = href if href.startswith("http") else f"https://www.kariyer.net{href}"

            if not title or not company or not url:
                return None

            return Job(
                title=title,
                company=company,
                location=location,
                source=self.source_name,
                url=url,
                posted_date=posted_date,
            )
        except Exception as exc:
            self.logger.debug("Card parse error: %s", exc)
            return None


async def _scroll_page(page) -> None:
    """Scroll down to trigger infinite-scroll / lazy-loading."""
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        import asyncio
        await asyncio.sleep(0.8)


def _parse_kariyer_date(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    # Patterns: "2 gün önce", "Bugün", "3 saat önce", "14.05.2025"
    if "bugün" in raw.lower() or "today" in raw.lower():
        return datetime.utcnow().strftime("%Y-%m-%d")
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", raw)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    # Relative: "3 gün önce" → subtract N days
    match = re.search(r"(\d+)\s*(gün|day)", raw, re.IGNORECASE)
    if match:
        days_ago = int(match.group(1))
        dt = datetime.utcnow() - timedelta(days=days_ago)
        return dt.strftime("%Y-%m-%d")
    return None
