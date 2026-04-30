"""
Detail Extractor
================
After a job is found, this module visits the job's detail page and
extracts richer information:
  - deadline         (son başvuru tarihi)
  - start_date       (başvuru başlangıç tarihi)
  - requirements     (aranan nitelikler / gereksinimler)
  - program_type     (staj / yetenek programı / tam zamanlı — to filter full-time)

Strategy:
  1. Try a lightweight requests GET first (fast, no JS needed).
  2. If the page needs JavaScript, fall back to Playwright.
  3. Use regex patterns to find Turkish date and requirement phrases.
"""

import re
import asyncio
import logging
from datetime import datetime

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from db.database import Job

logger = logging.getLogger(__name__)

# ── Regex patterns for Turkish + English date/info fields ────────────────────

DATE_PATTERNS = [
    r"(\d{1,2})[./](\d{1,2})[./](\d{4})",   # 31.05.2025 or 31/05/2025
    r"(\d{4})-(\d{2})-(\d{2})",              # 2025-05-31
]

DEADLINE_LABELS = [
    r"son\s*başvuru\s*(?:tarihi)?[:\s]*",
    r"başvuru\s*bitiş\s*(?:tarihi)?[:\s]*",
    r"başvuru\s*son\s*(?:tarihi)?[:\s]*",
    r"application\s*deadline[:\s]*",
    r"closing\s*date[:\s]*",
    r"apply\s*by[:\s]*",
    r"son\s*tarih[:\s]*",
    r"deadline[:\s]*",
    r"bitiş\s*tarihi[:\s]*",
    r"ilan\s*bitiş[:\s]*",
    r"valid\s*(?:until|through)[:\s]*",
    r"expires?[:\s]*",
]

START_DATE_LABELS = [
    r"başvurular?\s*(?:başlangıç|açıldı|açılıyor)[:\s]*",
    r"applications?\s*open[:\s]*",
    r"başvuru\s*başlangıç[:\s]*",
    r"program\s*başlangıç[:\s]*",
    r"staj\s*başlangıç[:\s]*",
    r"staj\s*tarihi[:\s]*",
    r"program\s*tarihi[:\s]*",
]

REQUIREMENTS_LABELS = [
    r"aranan\s*nitelikler?",
    r"aradığımız\s*(?:nitelikler?|özellikler?|profil)",
    r"gereksinimler?",
    r"requirements?",
    r"qualifications?",
    r"başvuru\s*koşulları",
    r"biz\s*kimlerle\s*çalışmak\s*istiyoruz",
    r"kimler\s*başvurabilir",
    r"hangi\s*özellikleri",
    r"tercih\s*(?:nedenleri|edilen)",
    r"what\s*we'?re?\s*looking\s*for",
    r"what\s*you'?ll?\s*need",
    r"who\s*you\s*are",
]

# Title phrases that confirm this is internship (not full-time)
INTERN_TITLE_SIGNALS = [
    "staj", "stajyer", "intern", "internship", "trainee",
    "yetenek programı", "talent program", "summer", "yaz dönemi",
    "aday", "kampüs", "genç yetenek",
]

# Title phrases that disqualify (full-time job).
# Intentionally narrow — "senior/uzman/specialist" are removed because they
# appear in internship page copy ("mentored by senior engineers") causing
# false positives. These are still filtered at title level in data_cleaner.
FULLTIME_TITLE_SIGNALS = [
    "sr.", "manager", "director", "head of",
    " vp ", "tam zamanlı", "full-time", "full time",
    "kalıcı pozisyon", "daimi",
]


class DetailExtractor:
    """Enrich a Job object with detail-page information."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def enrich(self, job: Job) -> Job:
        """Fetch detail page and fill in missing fields. Returns the same Job object."""
        if not job.url or job.url.startswith("https://example"):
            return job
        try:
            data = await asyncio.wait_for(self._extract(job.url), timeout=25)
            if data.get("deadline") and not job.deadline:
                job.deadline = data["deadline"]
            if data.get("start_date") and not job.start_date:
                job.start_date = data["start_date"]
            if data.get("requirements") and not job.requirements:
                job.requirements = data["requirements"]
            if data.get("program_type"):
                job.program_type = data["program_type"]
        except asyncio.TimeoutError:
            logger.debug("Detail extract timeout for %s", job.url)
        except Exception as exc:
            logger.debug("Detail extract error for %s: %s", job.url, exc)
        return job

    async def enrich_batch(self, jobs: list[Job], max_concurrent: int = 5) -> list[Job]:
        """Enrich multiple jobs concurrently, capped to avoid hammering servers."""
        sem = asyncio.Semaphore(max_concurrent)

        async def _bounded_enrich(job: Job) -> Job:
            async with sem:
                await asyncio.sleep(0.5)  # small stagger
                return await self.enrich(job)

        return list(await asyncio.gather(*[_bounded_enrich(j) for j in jobs]))

    async def _extract(self, url: str) -> dict:
        text = await self._fetch_text(url)
        if not text:
            return {}
        return _parse_text(text)

    async def _fetch_text(self, url: str) -> str:
        """Try requests first; fall back to Playwright if the page needs JS."""
        # Lightweight HTTP fetch
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
                    )},
                    allow_redirects=True,
                ) as resp:
                    if resp.status == 200:
                        return await resp.text(errors="replace")
        except Exception as exc:
            logger.debug("HTTP fetch failed for %s: %s", url, exc)

        # Playwright fallback for JS-heavy pages
        return await self._playwright_fetch(url)

    @staticmethod
    async def _playwright_fetch(url: str) -> str:
        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
        except ImportError:
            return ""
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await stealth_async(page)
                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                await asyncio.sleep(2)
                text = await page.inner_text("body")
                await browser.close()
                return text
        except Exception as exc:
            logger.debug("Playwright detail fetch failed for %s: %s", url, exc)
            return ""


def _parse_text(text: str) -> dict:
    result: dict = {}
    lower = text.lower()

    # ── program_type ─────────────────────────────────────────
    if any(kw in lower for kw in INTERN_TITLE_SIGNALS):
        if not any(kw in lower for kw in FULLTIME_TITLE_SIGNALS):
            result["program_type"] = "internship"
        else:
            result["program_type"] = "full_time"
    else:
        result["program_type"] = "unknown"

    # ── deadline ─────────────────────────────────────────────
    for label_pattern in DEADLINE_LABELS:
        match = re.search(label_pattern + r".*?(\d{1,2}[./]\d{1,2}[./]\d{4}|\d{4}-\d{2}-\d{2})",
                          lower, re.IGNORECASE)
        if match:
            result["deadline"] = _normalise_date(match.group(1))
            break

    # ── start_date ───────────────────────────────────────────
    for label_pattern in START_DATE_LABELS:
        match = re.search(label_pattern + r".*?(\d{1,2}[./]\d{1,2}[./]\d{4}|\d{4}-\d{2}-\d{2})",
                          lower, re.IGNORECASE)
        if match:
            result["start_date"] = _normalise_date(match.group(1))
            break

    # ── requirements ─────────────────────────────────────────
    for label_pattern in REQUIREMENTS_LABELS:
        match = re.search(label_pattern + r"[:\s]*(.{20,600}?)(?:\n\n|\Z)",
                          text, re.IGNORECASE | re.DOTALL)
        if match:
            raw = match.group(1).strip()
            # Clean up whitespace and bullets
            raw = re.sub(r"\s*[\•\-\*]\s*", "\n• ", raw)
            raw = re.sub(r"\n{3,}", "\n\n", raw)
            result["requirements"] = raw[:500].strip()
            break

    return result


def _normalise_date(raw: str) -> str | None:
    raw = raw.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    match = re.match(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", raw)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return None
