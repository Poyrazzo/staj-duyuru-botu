"""Company-name DDG search — daily sweep across all target companies.

Queries DuckDuckGo for each company in COMPANIES_LIST once per day.
No API key, no quota limits.
"""

import asyncio
import logging
import re
from datetime import date
from urllib.parse import urlparse

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

import config
from db.database import Job
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_INTERN_KW = {"staj", "intern", "trainee", "stajyer", "yetenek programı", "graduate program"}
_SKIP_KW   = {" senior ", " manager ", " director ", " lead ", " head ", " vp "}


class GoogleScraper(BaseScraper):
    """DDG company-name search — runs once per day."""

    source_name = "DDG Company"
    _last_run_date: date | None = None

    def is_due(self) -> bool:
        return self._last_run_date != date.today()

    async def scrape(self) -> list[Job]:
        if not self.is_due():
            logger.info("DDG company search already ran today — skipping.")
            return []

        companies = config.COMPANIES_LIST
        if not companies:
            logger.info("COMPANIES_LIST is empty — skipping DDG company search.")
            return []

        logger.info("DDG company search: querying %d companies …", len(companies))
        all_jobs: list[Job] = []
        loop = asyncio.get_event_loop()

        for company in companies:
            q = f'"{company}" (staj OR intern OR internship) -senior -manager'
            jobs = await loop.run_in_executor(None, self._search_sync, q, company)
            all_jobs.extend(jobs)
            await asyncio.sleep(2.0)

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[Job] = []
        for j in all_jobs:
            if j.url not in seen:
                seen.add(j.url)
                unique.append(j)

        GoogleScraper._last_run_date = date.today()
        logger.info("DDG company search: %d unique results.", len(unique))
        return unique

    def _search_sync(self, query: str, company: str) -> list[Job]:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=10, timelimit="y"))
        except Exception as exc:
            logger.warning("DDG query failed for '%s': %s", company, exc)
            return []

        jobs: list[Job] = []
        for r in results:
            job = self._result_to_job(r, company)
            if job:
                jobs.append(job)
        return jobs

    def _result_to_job(self, item: dict, queried_company: str) -> Job | None:
        try:
            title   = (item.get("title")  or "").strip()
            url     = (item.get("href")   or item.get("url") or "").strip()
            snippet = (item.get("body")   or item.get("snippet") or "").strip()

            if not title or not url:
                return None

            haystack = (title + " " + snippet + " " + url).lower()
            if not any(kw in haystack for kw in _INTERN_KW):
                return None
            if any(kw in f" {title.lower()} " for kw in _SKIP_KW):
                return None

            # Try to extract company from page title (e.g. "Title | Company | LinkedIn")
            company = _extract_company(title) or queried_company

            return Job(
                title=title[:200],
                company=company,
                location="Türkiye",
                source=self.source_name,
                url=url,
                description=snippet[:300] if snippet else "",
            )
        except Exception as exc:
            logger.debug("DDG result parse error: %s", exc)
            return None


def _extract_company(title: str) -> str:
    boards = r"\|\s*(?:LinkedIn|Kariyer\.net|Youthall|Toptalent|Glassdoor|Indeed)\s*$"
    cleaned = re.sub(boards, "", title, flags=re.IGNORECASE).strip().rstrip("|").strip()
    if "|" in cleaned:
        parts = [p.strip() for p in cleaned.split("|") if p.strip()]
        if len(parts) >= 2:
            return parts[-1]
    match = re.search(r"\bat\s+(.+)$", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if " - " in cleaned:
        return cleaned.split(" - ")[-1].strip()
    return ""
