"""Google Custom Search Engine scraper.

Strategy:
  1. General whole-web queries  — broad Turkish internship searches
  2. Targeted domain queries    — companies/sites we can't scrape directly

Free quota: 100 queries/day × 10 results = 1 000 URLs max.
We stay comfortably under that limit.
"""

import asyncio
import logging
import re
from urllib.parse import urlparse

import aiohttp

import config
from db.database import Job
from .base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# ── General queries (whole-web) ──────────────────────────────────────────────
# These surface listings we'd never find via targeted scraping.
_GENERAL_QUERIES = [
    "staj ilanı 2026 başvuru",
    "yaz stajı 2026 türkiye",
    "uzun dönem staj 2026",
    "internship turkey 2026 apply",
    "yetenek programı 2026 başvuru",
    "trainee program turkey 2026",
    "stajyer alımı 2026",
    "graduate program türkiye 2026",
]

# ── Domain-targeted queries ──────────────────────────────────────────────────
# Focused on companies/sites we couldn't scrape directly (geo-blocked, ATS, etc.)
_DOMAIN_QUERIES = [
    # Turkish conglomerates & banks (DNS unreachable from abroad)
    ("koc.com.tr",            "staj OR intern"),
    ("koccareers.com.tr",     "staj OR intern"),
    ("sabanci.com",           "staj OR intern"),
    ("eczacibasi.com.tr",     "staj OR intern"),
    ("anadolugrubu.com.tr",   "staj OR intern"),
    ("yildizholding.com.tr",  "staj OR intern"),
    ("baykartech.com",        "staj OR intern"),
    ("sisecam.com",           "staj OR intern"),
    ("akbank.com",            "staj OR intern"),
    ("garantibbva.com.tr",    "staj OR intern"),
    ("isbank.com.tr",         "staj OR intern"),
    ("yapikredi.com.tr",      "staj OR intern"),
    ("ziraatbank.com.tr",     "staj OR intern"),
    ("halkbank.com.tr",       "staj OR intern"),
    ("vakifbank.com.tr",      "staj OR intern"),
    ("thy.com",               "staj OR intern"),
    ("getir.com",             "staj OR intern"),
    ("trendyol.com",          "staj OR intern"),
    ("hepsiburada.com",       "staj OR intern"),
    # Insurance
    ("allianz.com.tr",        "staj OR intern"),
    ("axa.com.tr",            "staj OR intern"),
    ("turkiyesigorta.com.tr", "staj OR intern"),
    # FMCG / food / pharma
    ("efes.com",              "staj OR intern"),
    ("eti.com.tr",            "staj OR intern"),
    ("hayat.com.tr",          "staj OR intern"),
    ("abdiibrahim.com.tr",    "staj OR intern"),
    # International tech (ATS-heavy)
    ("oracle.com",            "intern turkey istanbul"),
    ("careers.bat.com",       "intern turkey"),
    ("jti.com",               "intern turkey"),
    ("henkel.com",            "intern turkey"),
    # Job boards that block direct scraping
    ("kariyer.net",           "staj ilanı"),
    ("secretcv.com",          "staj ilanı"),
    ("kariyerkapisi.cbiko.gov.tr", "staj"),
]


class GoogleCSEScraper(BaseScraper):
    """Uses Google Custom Search API to discover internship listings."""

    source_name = "Google CSE"

    async def scrape(self) -> list[Job]:
        if not config.GOOGLE_CSE_API_KEY or not config.GOOGLE_CSE_CX:
            self.logger.info("Google CSE: API key or CX not set, skipping.")
            return []

        self.logger.info("Scraping via Google CSE …")

        all_jobs: list[Job] = []
        query_count = 0

        async with aiohttp.ClientSession() as session:
            # ── 1. General queries ──────────────────────────────
            for q in _GENERAL_QUERIES:
                if query_count >= 90:   # stay under 100/day limit
                    break
                results = await self._search(session, q)
                query_count += 1
                for item in results:
                    job = self._result_to_job(item)
                    if job:
                        all_jobs.append(job)
                await asyncio.sleep(0.5)   # gentle rate-limiting

            # ── 2. Domain-targeted queries ─────────────────────
            for domain, kw in _DOMAIN_QUERIES:
                if query_count >= 90:
                    break
                q = f"site:{domain} {kw}"
                results = await self._search(session, q)
                query_count += 1
                for item in results:
                    job = self._result_to_job(item)
                    if job:
                        all_jobs.append(job)
                await asyncio.sleep(0.5)

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[Job] = []
        for j in all_jobs:
            if j.url not in seen:
                seen.add(j.url)
                unique.append(j)

        self.logger.info(
            "Google CSE: %d queries, %d unique results.", query_count, len(unique)
        )
        return unique

    async def _search(self, session: aiohttp.ClientSession, query: str) -> list[dict]:
        params = {
            "key": config.GOOGLE_CSE_API_KEY,
            "cx": config.GOOGLE_CSE_CX,
            "q": query,
            "num": 10,
        }
        try:
            async with session.get(_CSE_ENDPOINT, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 429:
                    self.logger.warning("Google CSE: rate limited (429), stopping.")
                    return []
                if resp.status != 200:
                    body = await resp.text()
                    self.logger.warning("Google CSE: HTTP %d for query '%s': %s", resp.status, query, body[:200])
                    return []
                data = await resp.json()
                return data.get("items", [])
        except Exception as exc:
            self.logger.warning("Google CSE request error for '%s': %s", query, exc)
            return []

    def _result_to_job(self, item: dict) -> Job | None:
        try:
            title = item.get("title", "").strip()
            url   = item.get("link", "").strip()
            snippet = item.get("snippet", "").strip()

            if not title or not url:
                return None

            # Filter out irrelevant results
            haystack = (title + " " + snippet + " " + url).lower()
            intern_kw = {"staj", "intern", "trainee", "yetenek programı", "graduate program", "stajyer"}
            if not any(kw in haystack for kw in intern_kw):
                return None

            # Skip senior/manager/director roles
            skip_kw = {" senior ", " manager ", " director ", " lead ", " head ", " vp "}
            if any(kw in f" {title.lower()} " for kw in skip_kw):
                return None

            # Extract company from domain
            domain = urlparse(url).netloc.lower()
            company = _domain_to_company(domain) or "Bilinmiyor"

            return Job(
                title=title[:200],
                company=company,
                location="Türkiye",
                source=self.source_name,
                url=url,
                description=snippet[:300] if snippet else "",
            )
        except Exception as exc:
            self.logger.debug("CSE result parse error: %s", exc)
            return None


# ── Domain → Company name map ───────────────────────────────────────────────

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
}


def _domain_to_company(domain: str) -> str:
    domain = domain.lstrip("www.")
    if domain in _DOMAIN_MAP:
        return _DOMAIN_MAP[domain]
    # Try partial match for subdomains like careers.microsoft.com
    for key, name in _DOMAIN_MAP.items():
        if key in domain or domain in key:
            return name
    # Fall back to capitalised domain root
    root = domain.split(".")[0]
    return root.capitalize() if root else ""
