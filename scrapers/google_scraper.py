"""
Google Custom Search Scraper — Daily Safety Net
================================================
Runs ONCE PER DAY. For each domain in config.GOOGLE_SEARCH_DOMAINS it fires:

    site:{domain} (staj OR intern OR internship) -senior -manager -director

Free tier: 100 queries/day → covers ~70 domains with room to spare.

Setup (5 min, one-time):
1. console.cloud.google.com → Create project → Enable "Custom Search API"
   → Create API key → set GOOGLE_CSE_API_KEY in .env
2. cse.google.com → New search engine → "Search the entire web" ON
   → Copy Search engine ID → set GOOGLE_CSE_CX in .env

If keys are not set, this scraper silently skips (no error).
"""

import asyncio
import logging
from datetime import datetime, date

import aiohttp

import config
from db.database import Job
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CSE_API_URL = "https://www.googleapis.com/customsearch/v1"
# Search query template
QUERY_TEMPLATE = 'site:{domain} (staj OR intern OR internship) -senior -manager -director'

# How many results to request per domain (max 10 per query on free tier)
RESULTS_PER_DOMAIN = 10


class GoogleScraper(BaseScraper):
    """Google Custom Search API — daily sweep across all configured domains."""

    source_name = "Google CSE"

    # Tracks the last date this scraper actually ran to enforce once-per-day
    _last_run_date: date | None = None

    def is_due(self) -> bool:
        """True if scraper hasn't run today yet."""
        return self._last_run_date != date.today()

    async def scrape(self) -> list[Job]:
        if not config.GOOGLE_CSE_API_KEY or not config.GOOGLE_CSE_CX:
            logger.info("Google CSE not configured — skipping. Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX in .env")
            return []

        if not self.is_due():
            logger.info("Google CSE already ran today — skipping.")
            return []

        self.logger.info("Google CSE: sweeping %d domains …", len(config.GOOGLE_SEARCH_DOMAINS))
        all_jobs: list[Job] = []

        async with aiohttp.ClientSession() as session:
            # Batch domains into groups of 5 to avoid hammering the API
            domains = config.GOOGLE_SEARCH_DOMAINS
            for i in range(0, len(domains), 5):
                batch = domains[i:i + 5]
                tasks = [self._search_domain(session, domain) for domain in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for domain, result in zip(batch, results):
                    if isinstance(result, list):
                        all_jobs.extend(result)
                    elif isinstance(result, Exception):
                        logger.warning("CSE error for %s: %s", domain, result)
                # Small pause between batches to respect rate limits
                await asyncio.sleep(2)

        GoogleScraper._last_run_date = date.today()
        self.logger.info("Google CSE: %d results found across all domains.", len(all_jobs))
        return all_jobs

    async def _search_domain(self, session: aiohttp.ClientSession, domain: str) -> list[Job]:
        query = QUERY_TEMPLATE.format(domain=domain)
        params = {
            "key": config.GOOGLE_CSE_API_KEY,
            "cx":  config.GOOGLE_CSE_CX,
            "q":   query,
            "num": RESULTS_PER_DOMAIN,
            "lr":  "lang_tr|lang_en",
            "gl":  "tr",
        }
        try:
            async with session.get(
                CSE_API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 429:
                    logger.warning("Google CSE rate limited — pause and retry")
                    await asyncio.sleep(10)
                    return []
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Google CSE HTTP %d for %s: %s", resp.status, domain, body[:200])
                    return []
                data = await resp.json()
        except Exception as exc:
            logger.warning("Google CSE request failed for %s: %s", domain, exc)
            return []

        items = data.get("items", [])
        jobs = []
        for item in items:
            job = self._item_to_job(item, domain)
            if job:
                jobs.append(job)
        return jobs

    def _item_to_job(self, item: dict, domain: str) -> Job | None:
        try:
            title = item.get("title", "").strip()
            url = item.get("link", "").strip()
            snippet = item.get("snippet", "").strip()

            if not title or not url:
                return None

            # Extract company name: try the domain first, then the page title breadcrumb
            pagemap = item.get("pagemap", {})
            org_name = ""
            metatags = pagemap.get("metatags", [{}])
            if metatags:
                org_name = (
                    metatags[0].get("og:site_name")
                    or metatags[0].get("application-name")
                    or ""
                ).strip()
            if not org_name:
                # Use domain as company name fallback (e.g. "careers.microsoft.com" → "Microsoft")
                org_name = _domain_to_company(domain)

            # Try to extract a date from snippet
            posted_date = _extract_date_from_snippet(snippet)

            return Job(
                title=title,
                company=org_name,
                location="Türkiye",
                source=self.source_name,
                url=url,
                description=snippet[:300],
                posted_date=posted_date,
            )
        except Exception as exc:
            logger.debug("CSE item parse error: %s", exc)
            return None


def _domain_to_company(domain: str) -> str:
    """Best-effort company name from domain string."""
    # Strip common prefixes
    for prefix in ("careers.", "jobs.", "career.", "www.", "new."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    # Take first segment and title-case it
    name = domain.split(".")[0]
    return name.replace("-", " ").title()


def _extract_date_from_snippet(snippet: str) -> str | None:
    import re
    match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", snippet)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    # ISO date
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", snippet)
    if match:
        return match.group(0)
    # Relative: "3 days ago"
    match = re.search(r"(\d+)\s*(?:days?|gün)\s*ago", snippet, re.IGNORECASE)
    if match:
        from datetime import timedelta
        return (datetime.utcnow() - timedelta(days=int(match.group(1)))).strftime("%Y-%m-%d")
    return None
