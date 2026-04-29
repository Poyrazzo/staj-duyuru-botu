"""
Google Custom Search Scraper — Daily Safety Net
================================================
Runs ONCE PER DAY.

Since most CSE setups include LinkedIn, we query each target company by name:
    "{CompanyName}" (staj OR intern OR internship) -senior -manager

This surfaces LinkedIn listings for each company that JobSpy may have missed
(e.g. different posting dates, alternative keywords).

Free tier: 100 queries/day. We cap at 95 company queries to leave head-room.

Setup (5 min, one-time):
1. console.cloud.google.com → Enable "Custom Search API" → Create API key
   → set GOOGLE_CSE_API_KEY in .env
2. programmablesearchengine.google.com → New engine → add linkedin.com
   → Copy Search engine ID → set GOOGLE_CSE_CX in .env

If keys are not set, this scraper silently skips (no error).
"""

import asyncio
import logging
import re
from datetime import datetime, date

import aiohttp

import config
from db.database import Job
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CSE_API_URL = "https://www.googleapis.com/customsearch/v1"

# Company-name query (works with any CSE that includes LinkedIn or similar boards)
COMPANY_QUERY = '"{company}" (staj OR intern OR internship) -senior -manager'

# Optional domain query (only useful when CSE has "Search entire web" enabled)
DOMAIN_QUERY  = 'site:{domain} (staj OR intern OR internship) -senior -manager'

RESULTS_PER_QUERY = 10
MAX_QUERIES_PER_DAY = 95   # stay inside free-tier 100/day


class GoogleScraper(BaseScraper):
    """Google Custom Search API — daily sweep using company-name queries."""

    source_name = "Google CSE"
    _last_run_date: date | None = None

    def is_due(self) -> bool:
        return self._last_run_date != date.today()

    async def scrape(self) -> list[Job]:
        if not config.GOOGLE_CSE_API_KEY or not config.GOOGLE_CSE_CX:
            logger.info("Google CSE not configured — skipping.")
            return []
        if not self.is_due():
            logger.info("Google CSE already ran today — skipping.")
            return []

        companies = [cfg.name for cfg in config.COMPANY_CONFIGS]
        # Cap to daily limit
        companies = companies[:MAX_QUERIES_PER_DAY]

        self.logger.info("Google CSE: querying %d companies …", len(companies))
        all_jobs: list[Job] = []

        async with aiohttp.ClientSession() as session:
            for i in range(0, len(companies), 5):
                batch = companies[i:i + 5]
                tasks = [self._search_company(session, name) for name in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for name, result in zip(batch, results):
                    if isinstance(result, list):
                        all_jobs.extend(result)
                    elif isinstance(result, Exception):
                        logger.warning("CSE error for %s: %s", name, result)
                await asyncio.sleep(2)

        GoogleScraper._last_run_date = date.today()
        self.logger.info("Google CSE: %d results found.", len(all_jobs))
        return all_jobs

    async def _search_company(
        self, session: aiohttp.ClientSession, company_name: str
    ) -> list[Job]:
        query = COMPANY_QUERY.format(company=company_name)
        params = {
            "key": config.GOOGLE_CSE_API_KEY,
            "cx":  config.GOOGLE_CSE_CX,
            "q":   query,
            "num": RESULTS_PER_QUERY,
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
                    logger.warning("Google CSE rate-limited — pausing")
                    await asyncio.sleep(10)
                    return []
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("CSE HTTP %d for %s: %s", resp.status, company_name, body[:200])
                    return []
                data = await resp.json()
        except Exception as exc:
            logger.warning("CSE request failed for %s: %s", company_name, exc)
            return []

        jobs = []
        for item in data.get("items", []):
            job = self._item_to_job(item, company_name)
            if job:
                jobs.append(job)
        return jobs

    def _item_to_job(self, item: dict, queried_company: str) -> Job | None:
        try:
            title = item.get("title", "").strip()
            url = item.get("link", "").strip()
            snippet = item.get("snippet", "").strip()

            if not title or not url:
                return None

            # Extract real company name from page title
            # LinkedIn format: "Job Title | Company | LinkedIn"
            # or "Job Title at Company | LinkedIn"
            company = _extract_company_from_title(title) or queried_company

            # Try og:site_name / structured data
            pagemap = item.get("pagemap", {})
            metatags = pagemap.get("metatags", [{}])
            if metatags and not company:
                company = (
                    metatags[0].get("og:site_name")
                    or metatags[0].get("application-name")
                    or queried_company
                ).strip()

            posted_date = _extract_date_from_snippet(snippet)

            return Job(
                title=title,
                company=company,
                location="Türkiye",
                source=self.source_name,
                url=url,
                description=snippet[:300],
                posted_date=posted_date,
            )
        except Exception as exc:
            logger.debug("CSE item parse error: %s", exc)
            return None


def _extract_company_from_title(title: str) -> str:
    """
    Parse real company name from job-board page titles.
    LinkedIn: "Yazılım Stajyeri | Trendyol | LinkedIn"
              "Intern at Garanti BBVA | LinkedIn"
    Kariyer:  "Yazılım Stajyeri - Trendyol | Kariyer.net"
    """
    # Remove trailing board name ("| LinkedIn", "| Kariyer.net", etc.)
    boards = r"\|\s*(?:LinkedIn|Kariyer\.net|Youthall|Toptalent|Glassdoor|Indeed)\s*$"
    cleaned = re.sub(boards, "", title, flags=re.IGNORECASE).strip().rstrip("|").strip()

    # "Title | Company" → second segment is company
    if "|" in cleaned:
        parts = [p.strip() for p in cleaned.split("|") if p.strip()]
        if len(parts) >= 2:
            return parts[-1]   # last segment before board name

    # "Title at Company"
    match = re.search(r"\bat\s+(.+)$", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # "Title - Company"
    if " - " in cleaned:
        return cleaned.split(" - ")[-1].strip()

    return ""


def _extract_date_from_snippet(snippet: str) -> str | None:
    match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", snippet)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", snippet)
    if match:
        return match.group(0)
    match = re.search(r"(\d+)\s*(?:days?|gün)\s*ago", snippet, re.IGNORECASE)
    if match:
        from datetime import timedelta
        return (datetime.utcnow() - timedelta(days=int(match.group(1)))).strftime("%Y-%m-%d")
    return None
