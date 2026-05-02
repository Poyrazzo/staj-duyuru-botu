"""
ATS Direct API Scraper — Greenhouse & Lever
============================================
These platforms expose public JSON endpoints with zero anti-bot measures.
This is the most reliable scraping method available.

Greenhouse: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
Lever:      https://api.lever.co/v0/postings/{slug}?mode=json
"""

import asyncio
import logging
import aiohttp

import config
from db.database import Job
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_API = "https://api.lever.co/v0/postings/{slug}?mode=json"
WORKABLE_API = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"


class ATSScraper(BaseScraper):
    """Scrapes Greenhouse and Lever job boards via their public JSON APIs."""

    source_name = "ATS"

    async def scrape(self) -> list[Job]:
        jobs: list[Job] = []

        async with aiohttp.ClientSession(
            headers={"User-Agent": self.random_user_agent()}
        ) as session:
            # Run all companies concurrently
            tasks = []
            for company, slug in config.GREENHOUSE_COMPANIES.items():
                tasks.append(self._fetch_greenhouse(session, company, slug))
            for company, slug in config.LEVER_COMPANIES.items():
                tasks.append(self._fetch_lever(session, company, slug))
            for company, slug in config.WORKABLE_COMPANIES.items():
                tasks.append(self._fetch_workable(session, company, slug))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    jobs.extend(r)
                elif isinstance(r, Exception):
                    logger.warning("ATS fetch error: %s", r)

        logger.info("ATS: %d total jobs fetched.", len(jobs))
        return jobs

    async def _fetch_greenhouse(
        self, session: aiohttp.ClientSession, company: str, slug: str
    ) -> list[Job]:
        url = GREENHOUSE_API.format(slug=slug)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning("Greenhouse %s returned HTTP %d", company, resp.status)
                    return []
                data = await resp.json()
        except Exception as exc:
            logger.warning("Greenhouse %s fetch failed: %s", company, exc)
            return []

        jobs = []
        for item in data.get("jobs", []):
            job = self._greenhouse_to_job(item, company)
            if job:
                jobs.append(job)
        logger.debug("Greenhouse %s: %d jobs", company, len(jobs))
        return jobs

    def _greenhouse_to_job(self, item: dict, company: str) -> Job | None:
        try:
            title = item.get("title", "").strip()
            url = item.get("absolute_url", "").strip()
            if not title or not url:
                return None

            location_data = item.get("location", {})
            location = location_data.get("name", "Türkiye") if isinstance(location_data, dict) else "Türkiye"

            # Extract content for requirements
            content = item.get("content", "") or ""
            # Greenhouse stores HTML content — strip tags for storage
            requirements = _strip_html(content)[:500]

            # Metadata
            metadata = item.get("metadata", []) or []
            dept = ""
            for m in metadata:
                if isinstance(m, dict) and m.get("name") == "Department":
                    dept = str(m.get("value", ""))

            updated_at = item.get("updated_at", "")
            posted_date = updated_at[:10] if updated_at else None

            return Job(
                title=title,
                company=company,
                location=location,
                source=f"Greenhouse ({company})",
                url=url,
                description=dept,
                requirements=requirements,
                posted_date=posted_date,
            )
        except Exception as exc:
            logger.debug("Greenhouse item parse error: %s", exc)
            return None

    async def _fetch_lever(
        self, session: aiohttp.ClientSession, company: str, slug: str
    ) -> list[Job]:
        url = LEVER_API.format(slug=slug)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning("Lever %s returned HTTP %d", company, resp.status)
                    return []
                data = await resp.json()
        except Exception as exc:
            logger.warning("Lever %s fetch failed: %s", company, exc)
            return []

        jobs = []
        for item in data if isinstance(data, list) else []:
            job = self._lever_to_job(item, company)
            if job:
                jobs.append(job)
        logger.debug("Lever %s: %d jobs", company, len(jobs))
        return jobs

    async def _fetch_workable(
        self, session: aiohttp.ClientSession, company: str, slug: str
    ) -> list[Job]:
        url = WORKABLE_API.format(slug=slug)
        try:
            async with session.post(
                url,
                json={"query": "intern"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    logger.warning("Workable %s returned HTTP %d", company, resp.status)
                    return []
                data = await resp.json()
        except Exception as exc:
            logger.warning("Workable %s fetch failed: %s", company, exc)
            return []

        jobs = []
        for item in data.get("results", []):
            job = self._workable_to_job(item, company)
            if job:
                jobs.append(job)
        logger.debug("Workable %s: %d jobs", company, len(jobs))
        return jobs

    def _workable_to_job(self, item: dict, company: str) -> Job | None:
        try:
            title = item.get("title", "").strip()
            shortcode = item.get("shortcode", "")
            url = f"https://apply.workable.com/{company.lower()}/j/{shortcode}/" if shortcode else ""
            if not title:
                return None
            location_data = item.get("location", {})
            city = location_data.get("city", "") if isinstance(location_data, dict) else ""
            country = location_data.get("country", "") if isinstance(location_data, dict) else ""
            location = f"{city}, {country}".strip(", ") or "Türkiye"
            dept = item.get("department", "") or ""
            return Job(
                title=title,
                company=company,
                location=location,
                source=f"Workable ({company})",
                url=url,
                description=dept,
            )
        except Exception as exc:
            logger.debug("Workable item parse error: %s", exc)
            return None

    def _lever_to_job(self, item: dict, company: str) -> Job | None:
        try:
            title = item.get("text", "").strip()
            url = item.get("hostedUrl", "").strip()
            if not title or not url:
                return None

            categories = item.get("categories", {}) or {}
            location = categories.get("location", "Türkiye")
            dept = categories.get("department", "")

            lists = item.get("lists", []) or []
            requirements = ""
            for lst in lists:
                if isinstance(lst, dict):
                    content = lst.get("content", "")
                    requirements += _strip_html(content) + "\n"
            requirements = requirements.strip()[:500]

            created_at = item.get("createdAt")
            posted_date = None
            if created_at:
                from datetime import datetime
                try:
                    posted_date = datetime.utcfromtimestamp(created_at / 1000).strftime("%Y-%m-%d")
                except Exception:
                    pass

            return Job(
                title=title,
                company=company,
                location=str(location),
                source=f"Lever ({company})",
                url=url,
                description=dept,
                requirements=requirements,
                posted_date=posted_date,
            )
        except Exception as exc:
            logger.debug("Lever item parse error: %s", exc)
            return None


def _strip_html(html: str) -> str:
    """Remove HTML tags and normalise whitespace."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
