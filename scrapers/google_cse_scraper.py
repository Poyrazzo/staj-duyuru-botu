"""DuckDuckGo search scraper — no API key, no quota limits.

Replaces the Google CSE scraper. Uses the `duckduckgo-search` library
which wraps DDG's HTML search with no authentication required.

Strategy:
  1. General queries  — broad Turkish internship discovery across the whole web
  2. Domain queries   — targeted searches on companies we can't scrape directly
"""

import asyncio
import logging
import re
from urllib.parse import urlparse

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

import config
from db.database import Job
from .base_scraper import BaseScraper
from .search_filter import is_actionable_search_result

logger = logging.getLogger(__name__)

# ── General queries ──────────────────────────────────────────────────────────
_GENERAL_QUERIES = [
    "software staj ilanı 2026 başvuru",
    "bilgisayar mühendisliği staj 2026 başvuru",
    "yazılım stajyer ilanı 2026",
    "data intern turkey 2026 apply",
    "internship turkey 2026 software apply",
    "yapay zeka staj 2026 başvuru",
    "siber güvenlik staj 2026 başvuru",
]

# ── Domain-targeted queries ──────────────────────────────────────────────────
# Companies/sites we can't reach by direct Playwright scraping
_DOMAIN_QUERIES = [
    ("koc.com.tr",                 "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("sabanci.com",                "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("eczacibasi.com.tr",          "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("anadolugrubu.com.tr",        "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("yildizholding.com.tr",       "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("baykartech.com",             "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("sisecam.com",                "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("akbank.com",                 "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("garantibbva.com.tr",         "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("isbank.com.tr",              "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("yapikredi.com.tr",           "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("ziraatbank.com.tr",          "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("thy.com",                    "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("getir.com",                  "(software OR data OR intern) apply"),
    ("hepsiburada.com",            "(software OR data OR intern) apply"),
    ("allianz.com.tr",             "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("axa.com.tr",                 "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("turkiyesigorta.com.tr",      "(yazılım OR bilgisayar OR data OR staj OR intern) başvuru"),
    ("oracle.com",                 "(software OR data OR intern) turkey apply"),
    ("henkel.com",                 "(software OR data OR intern) turkey apply"),
    ("kariyer.net",                "yazılım staj ilanı"),
    ("kariyerkapisi.cbiko.gov.tr", "yazılım staj başvuru"),
]

_INTERN_KW   = {"staj", "intern", "trainee", "stajyer", "yetenek programı", "graduate program"}
_SKIP_KW     = {" senior ", " manager ", " director ", " lead ", " head ", " vp "}
_RESULTS_PER = 10   # DDG max per query


class GoogleCSEScraper(BaseScraper):
    """DuckDuckGo-based web search scraper (replaces Google CSE)."""

    source_name = "DDG Search"

    async def scrape(self) -> list[Job]:
        self.logger.info("Scraping via DuckDuckGo …")
        all_jobs: list[Job] = []

        loop = asyncio.get_event_loop()

        # General queries
        for q in _GENERAL_QUERIES:
            jobs = await loop.run_in_executor(None, self._search_sync, q)
            all_jobs.extend(jobs)
            await asyncio.sleep(1.5)   # polite delay between queries

        # Domain-targeted queries
        for domain, kw in _DOMAIN_QUERIES:
            q = f"site:{domain} {kw}"
            jobs = await loop.run_in_executor(None, self._search_sync, q)
            all_jobs.extend(jobs)
            await asyncio.sleep(1.5)

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[Job] = []
        for j in all_jobs:
            if j.url not in seen:
                seen.add(j.url)
                unique.append(j)

        self.logger.info("DDG Search: %d unique results.", len(unique))
        return unique

    def _search_sync(self, query: str) -> list[Job]:
        """Run a single DDG query (synchronous — called via executor)."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=_RESULTS_PER, timelimit="y"))
        except Exception as exc:
            self.logger.warning("DDG query failed for '%s': %s", query, exc)
            return []

        jobs: list[Job] = []
        for r in results:
            job = self._result_to_job(r)
            if job:
                jobs.append(job)
        return jobs

    def _result_to_job(self, item: dict) -> Job | None:
        try:
            title   = (item.get("title")   or "").strip()
            url     = (item.get("href")    or item.get("url") or "").strip()
            snippet = (item.get("body")    or item.get("snippet") or "").strip()

            if not title or not url:
                return None

            if not is_actionable_search_result(title, url, snippet):
                return None

            haystack = (title + " " + snippet + " " + url).lower()
            if not any(kw in haystack for kw in _INTERN_KW):
                return None
            if any(kw in f" {title.lower()} " for kw in _SKIP_KW):
                return None

            domain  = urlparse(url).netloc.lower().lstrip("www.")
            company = _domain_to_company(domain) or _company_from_title(title) or "Bilinmiyor"

            return Job(
                title=title[:200],
                company=company,
                location="Türkiye",
                source=self.source_name,
                url=url,
                description=snippet[:300] if snippet else "",
            )
        except Exception as exc:
            self.logger.debug("DDG result parse error: %s", exc)
            return None


# ── Helpers ──────────────────────────────────────────────────────────────────

_DOMAIN_MAP: dict[str, str] = {
    "koc.com.tr": "Koç Holding", "koccareers.com.tr": "Koç Holding",
    "sabanci.com": "Sabancı Holding",
    "eczacibasi.com.tr": "Eczacıbaşı",
    "anadolugrubu.com.tr": "Anadolu Grubu",
    "yildizholding.com.tr": "Yıldız Holding",
    "baykartech.com": "Baykar",
    "sisecam.com": "Şişecam",
    "akbank.com": "Akbank",
    "garantibbva.com.tr": "Garanti BBVA",
    "isbank.com.tr": "İş Bankası",
    "yapikredi.com.tr": "Yapı Kredi",
    "ziraatbank.com.tr": "Ziraat Bankası",
    "halkbank.com.tr": "Halkbank",
    "vakifbank.com.tr": "VakıfBank",
    "thy.com": "Türk Hava Yolları",
    "flypgs.com": "Pegasus",
    "getir.com": "Getir",
    "trendyol.com": "Trendyol",
    "hepsiburada.com": "Hepsiburada",
    "allianz.com.tr": "Allianz Türkiye",
    "axa.com.tr": "AXA Sigorta",
    "turkiyesigorta.com.tr": "Türkiye Sigorta",
    "efes.com": "Anadolu Efes",
    "eti.com.tr": "ETİ",
    "hayat.com.tr": "Hayat Kimya",
    "abdiibrahim.com.tr": "Abdi İbrahim",
    "oracle.com": "Oracle",
    "careers.bat.com": "British American Tobacco",
    "jti.com": "JTI",
    "henkel.com": "Henkel",
    "kariyer.net": "Kariyer.net",
    "secretcv.com": "SecretCV",
    "kariyerkapisi.cbiko.gov.tr": "Kariyer Kapısı",
    "linkedin.com": "LinkedIn",
    "youthall.com": "Youthall",
    "toptalent.co": "Toptalent",
    "amazon.jobs": "Amazon",
    "careers.microsoft.com": "Microsoft",
    "careers.google.com": "Google",
    "jobs.sap.com": "SAP",
    "jobs.siemens.com": "Siemens",
    "bosch.com.tr": "Bosch",
    "jobs.ericsson.com": "Ericsson",
    "careers.dhl.com": "DHL",
    "pmicareers.com": "Philip Morris",
    "careers.loreal.com": "L'Oréal",
    "pfizer.com": "Pfizer",
    "sanofi.com": "Sanofi",
    "novartis.com": "Novartis",
    "basf.com": "BASF",
    "reckitt.com": "Reckitt",
    "fordotosan.com.tr": "Ford Otosan",
    "borusan.com": "Borusan",
    "toyota-tr.com": "Toyota Türkiye",
    "diageo.com": "Diageo",
}


def _domain_to_company(domain: str) -> str:
    if domain in _DOMAIN_MAP:
        return _DOMAIN_MAP[domain]
    for key, name in _DOMAIN_MAP.items():
        if key in domain or domain in key:
            return name
    root = domain.split(".")[0]
    return root.capitalize() if root else ""


def _company_from_title(title: str) -> str:
    """Extract company from job-board page titles like 'Title | Company | LinkedIn'."""
    boards = r"\|\s*(?:LinkedIn|Kariyer\.net|Youthall|Toptalent|Glassdoor|Indeed|DuckDuckGo)\s*$"
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
