"""
Data Cleaner
============
Three-stage pipeline:
  1. Internship-only gate  — rejects full-time jobs before anything else
  2. Whitelist / blacklist — keyword-based relevance filter
  3. CS/software focus     — keeps software/computer-engineering adjacent roles
  4. Deduplication         — cross-source semantic hash
"""

import logging
from typing import Iterable
from datetime import datetime
import re

import config
from db.database import Job

logger = logging.getLogger(__name__)

# program_type values that are allowed through
ALLOWED_PROGRAM_TYPES = {"internship", "talent_program", "unknown"}


class DataCleaner:
    def __init__(
        self,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        categories: dict[str, list[str]] | None = None,
    ) -> None:
        self._white = [w.lower() for w in (whitelist or config.WHITELIST_KEYWORDS)]
        self._black = [b.lower() for b in (blacklist or config.BLACKLIST_KEYWORDS)]
        self._intern_confirm = [k.lower() for k in config.INTERN_CONFIRM_KEYWORDS]
        self._cs_field = [k.lower() for k in config.CS_FIELD_KEYWORDS]
        self._cs_exclude = [k.lower() for k in config.CS_EXCLUDE_KEYWORDS]
        self._cats = {
            cat: [kw.lower() for kw in kws]
            for cat, kws in (categories or config.ROLE_CATEGORIES).items()
        }

    def clean(self, jobs: Iterable[Job]) -> list[Job]:
        seen_hashes: set[str] = set()
        result: list[Job] = []

        for job in jobs:
            # ── Stage 1: reject confirmed full-time jobs ─────────
            if job.program_type == "full_time":
                logger.debug("REJECTED (full_time): %s @ %s", job.title, job.company)
                continue

            # ── Stage 1b: reject old campaigns / expired deadlines ──
            if self._is_stale_or_expired(job):
                logger.debug("REJECTED (stale/expired): %s @ %s", job.title, job.company)
                continue

            # ── Stage 2: blacklist on title+company ──────────────
            if self._hits_blacklist(job):
                logger.debug("REJECTED (blacklist): %s @ %s", job.title, job.company)
                continue

            # ── Stage 3: whitelist — must match at least one ─────
            if not self._passes_whitelist(job):
                logger.debug("REJECTED (no whitelist): %s @ %s", job.title, job.company)
                continue

            # ── Stage 4: CS/software field — must match at least one ──
            if not self._passes_cs_filter(job):
                logger.debug("REJECTED (not CS field): %s @ %s", job.title, job.company)
                continue

            # ── Stage 5: in-batch dedup ──────────────────────────
            if job.semantic_hash in seen_hashes:
                logger.debug("REJECTED (duplicate): %s @ %s", job.title, job.company)
                continue

            # ── Set program_type if not yet known ────────────────
            if job.program_type == "unknown":
                job.program_type = self._infer_program_type(job)

            # ── Assign role category ─────────────────────────────
            job.category = self._classify(job)

            seen_hashes.add(job.semantic_hash)
            result.append(job)

        logger.info("DataCleaner: %d jobs passed filtering.", len(result))
        return result

    # ── Helpers ──────────────────────────────────────────────

    def _haystack(self, job: Job) -> str:
        return f"{job.title} {job.company} {job.description}".lower()

    def _title_company(self, job: Job) -> str:
        return f"{job.title} {job.company}".lower()

    def _passes_whitelist(self, job: Job) -> bool:
        hay = self._haystack(job)
        return _contains_any(hay, self._white)

    def _hits_blacklist(self, job: Job) -> bool:
        hay = self._title_company(job)
        return _contains_any(hay, self._black)

    def _passes_cs_filter(self, job: Job) -> bool:
        title_company = self._title_company(job)
        if _contains_any(title_company, self._cs_exclude):
            return False
        return _contains_any(self._haystack(job), self._cs_field)

    def _is_stale_or_expired(self, job: Job) -> bool:
        today = datetime.utcnow().date()
        if job.deadline:
            try:
                if datetime.fromisoformat(job.deadline[:10]).date() < today:
                    return True
            except ValueError:
                pass

        hay = f"{job.title} {job.description} {job.url}".lower()
        years = [int(match) for match in re.findall(r"\b20\d{2}\b", hay)]
        return bool(years) and max(years) < today.year

    def _infer_program_type(self, job: Job) -> str:
        hay = self._haystack(job)
        if _contains_any(hay, self._intern_confirm):
            return "internship"
        return "unknown"

    def _classify(self, job: Job) -> str:
        hay = self._haystack(job)
        for category, keywords in self._cats.items():
            if _contains_any(hay, keywords):
                return category
        return "other"

    @staticmethod
    def sort_by_date(jobs: list[Job], newest_first: bool = True) -> list[Job]:
        def _key(j: Job) -> str:
            return j.deadline or j.posted_date or j.discovered_at or ""
        return sorted(jobs, key=_key, reverse=newest_first)


def _contains_any(text: str, keywords: list[str]) -> bool:
    """Keyword matcher that supports explicit space-padded short tokens."""
    hay = f" {text.lower()} "
    return any(kw in hay for kw in keywords)
