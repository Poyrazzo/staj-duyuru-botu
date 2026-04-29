"""Data cleaning, keyword filtering, and role categorisation."""

import re
import logging
from typing import Iterable

import config
from db.database import Job

logger = logging.getLogger(__name__)


class DataCleaner:
    """Filter raw Job objects and assign role categories."""

    def __init__(
        self,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        categories: dict[str, list[str]] | None = None,
    ) -> None:
        self._white = [w.lower() for w in (whitelist or config.WHITELIST_KEYWORDS)]
        self._black = [b.lower() for b in (blacklist or config.BLACKLIST_KEYWORDS)]
        self._cats = {
            cat: [kw.lower() for kw in kws]
            for cat, kws in (categories or config.ROLE_CATEGORIES).items()
        }

    def clean(self, jobs: Iterable[Job]) -> list[Job]:
        """Filter, deduplicate and categorise a batch of jobs."""
        seen_hashes: set[str] = set()
        result: list[Job] = []

        for job in jobs:
            if not self._passes_whitelist(job):
                logger.debug("FILTERED (no whitelist match): %s – %s", job.title, job.company)
                continue
            if self._hits_blacklist(job):
                logger.debug("FILTERED (blacklist hit): %s – %s", job.title, job.company)
                continue
            if job.semantic_hash in seen_hashes:
                logger.debug("FILTERED (in-batch duplicate): %s – %s", job.title, job.company)
                continue

            job.category = self._classify(job)
            seen_hashes.add(job.semantic_hash)
            result.append(job)

        logger.info("DataCleaner: %d jobs passed filtering.", len(result))
        return result

    # ── Private helpers ──────────────────────────────────────

    def _haystack(self, job: Job) -> str:
        """Combined lowercased text field for matching."""
        return (
            f"{job.title} {job.company} {job.description}"
        ).lower()

    def _passes_whitelist(self, job: Job) -> bool:
        hay = self._haystack(job)
        return any(kw in hay for kw in self._white)

    def _hits_blacklist(self, job: Job) -> bool:
        # Only match against title + company (not full description)
        hay = f"{job.title} {job.company}".lower()
        return any(kw in hay for kw in self._black)

    def _classify(self, job: Job) -> str:
        hay = self._haystack(job)
        for category, keywords in self._cats.items():
            if any(kw in hay for kw in keywords):
                return category
        return "other"

    # ── Utility: sort by date ────────────────────────────────

    @staticmethod
    def sort_by_date(jobs: list[Job], newest_first: bool = True) -> list[Job]:
        def _key(j: Job) -> str:
            return j.posted_date or j.discovered_at or ""

        return sorted(jobs, key=_key, reverse=newest_first)
