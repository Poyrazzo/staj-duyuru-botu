"""Central configuration for the internship aggregator bot."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ─────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Scraper behaviour ─────────────────────────────────────────
RUN_INTERVAL_MINUTES: int = int(os.getenv("RUN_INTERVAL_MINUTES", "60"))
MAX_JOBS_PER_SOURCE: int = int(os.getenv("MAX_JOBS_PER_SOURCE", "50"))
HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"
LOOKBACK_DAYS: int = int(os.getenv("LOOKBACK_DAYS", "1"))

# ── Paths ─────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "data/jobs.db")
LOG_DIR: str = "logs"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Proxy ─────────────────────────────────────────────────────
HTTP_PROXY: str | None = os.getenv("HTTP_PROXY") or None
HTTPS_PROXY: str | None = os.getenv("HTTPS_PROXY") or None

# ── Google Custom Search (optional fallback) ──────────────────
# Get free key at: https://developers.google.com/custom-search/v1/introduction
GOOGLE_CSE_API_KEY: str = os.getenv("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_CX: str = os.getenv("GOOGLE_CSE_CX", "")   # Search Engine ID

# ── Health check ──────────────────────────────────────────────
HEALTH_CHECK_INTERVAL_HOURS: int = int(os.getenv("HEALTH_CHECK_INTERVAL_HOURS", "168"))

# ── Request timing (seconds) ──────────────────────────────────
MIN_SLEEP: float = 3.0
MAX_SLEEP: float = 10.0

# ── Browser ───────────────────────────────────────────────────
VIEWPORT: dict[str, int] = {"width": 1366, "height": 768}
LOCALE: str = "tr-TR"
TIMEZONE: str = "Europe/Istanbul"

# ═══════════════════════════════════════════════════════════════
# KEYWORD FILTERS
# ═══════════════════════════════════════════════════════════════

# At least one of these must appear in title+company+description
WHITELIST_KEYWORDS: list[str] = [
    "staj", "stajyer", "intern", "internship",
    "aday", "trainee", "programı", "program",
    "genç yetenek", "yetenek programı", "talent",
    "yaz dönemi", "yaz staj", "summer intern",
    "junior staj", "kampüs",
]

# Any match in TITLE or COMPANY alone → reject
BLACKLIST_KEYWORDS: list[str] = [
    "senior", "sr.", " lead ", "principal", "manager",
    "director", "head of", " vp ", "c.t.o", "cto", "coo", "cfo",
    "chief", "freelance", "serbest çalışan",
    "uzman", "specialist", "experienced", "deneyimli",
    "full-time", "tam zamanlı", "kalıcı", "daimi",
]

# Words that CONFIRM this is an internship (stronger signal)
INTERN_CONFIRM_KEYWORDS: list[str] = [
    "staj", "stajyer", "intern", "internship",
    "yaz staj", "yetenek programı", "trainee", "aday programı",
]

# ═══════════════════════════════════════════════════════════════
# ROLE CATEGORIES
# ═══════════════════════════════════════════════════════════════
ROLE_CATEGORIES: dict[str, list[str]] = {
    "software":    ["yazılım", "software", "developer", "geliştirici", "backend",
                    "frontend", "full stack", "fullstack", "mobile", "data",
                    "ml", "yapay zeka", "ai", "devops", "cloud", "cyber", "bilgisayar",
                    "mühendis", "engineer", "siber", "ağ", "network"],
    "marketing":   ["pazarlama", "marketing", "dijital", "digital", "sosyal medya",
                    "social media", "content", "içerik", "seo", "sem", "growth",
                    "marka", "brand", "reklam", "advertising", "influencer"],
    "finance":     ["finans", "finance", "muhasebe", "accounting", "audit",
                    "bütçe", "budget", "yatırım", "investment", "bankacılık",
                    "treasury", "hazine", "vergi", "tax"],
    "design":      ["tasarım", "design", "ui", "ux", "grafik", "graphic",
                    "motion", "product design", "görsel", "illüstrasyon"],
    "hr":          ["insan kaynakları", "human resources", "hr", "ik",
                    "recruitment", "işe alım", "yetenek", "talent acquisition"],
    "operations":  ["operasyon", "operations", "lojistik", "logistics",
                    "supply chain", "tedarik", "depo", "warehouse"],
    "sales":       ["satış", "sales", "business development", "iş geliştirme",
                    "account", "müşteri", "crm"],
    "legal":       ["hukuk", "legal", "avukat", "lawyer", "compliance", "uyum"],
    "engineering": ["makine", "elektrik", "electronic", "elektronik", "endüstri",
                    "industrial", "inşaat", "civil", "kimya", "chemical",
                    "malzeme", "materials", "enerji", "energy"],
}

# ═══════════════════════════════════════════════════════════════
# JOB BOARD SOURCE URLs
# ═══════════════════════════════════════════════════════════════
KARIYER_URL: str = "https://www.kariyer.net/is-ilanlari?kw=stajyer&srt=1"
YOUTHALL_URL: str = "https://www.youthall.com/tr/jobs/?type=internship"
TOPTALENT_URL: str = "https://toptalent.co/tr/ilanlar/?type=internship"
VIZYONER_GENC_URL: str = "https://vizyonergenc.com/staj-ilanlari"
KARIYER_KAPISI_URL: str = "https://www.kariyerkapisi.cbiko.gov.tr/Arama/staj"

# ═══════════════════════════════════════════════════════════════
# ATS DIRECT API (Greenhouse & Lever)
# No anti-bot measures — 100% reliable JSON endpoints.
# ═══════════════════════════════════════════════════════════════

# Companies confirmed on Greenhouse.io
# API: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
GREENHOUSE_COMPANIES: dict[str, str] = {
    "Trendyol":   "trendyol",
    "Getir":      "getir",
}

# Companies confirmed on Lever
# API: https://api.lever.co/v0/postings/{slug}?mode=json
LEVER_COMPANIES: dict[str, str] = {
    # Add slugs as confirmed
}

# ═══════════════════════════════════════════════════════════════
# COMPANY CAREER PAGE CONFIGS
# Each entry is scraped directly with Playwright.
# intern_path: the specific sub-URL for internship/staj listings.
# ═══════════════════════════════════════════════════════════════
@dataclass
class CompanyConfig:
    name: str
    careers_url: str                  # Main career page
    intern_url: str = ""              # Direct URL to internship section (preferred)
    search_keyword: str = "staj"      # Keyword to search/filter if needed
    extra_urls: list[str] = field(default_factory=list)  # Any additional pages to check

COMPANY_CONFIGS: list[CompanyConfig] = [
    CompanyConfig(
        name="Trendyol",
        careers_url="https://jobs.trendyol.com/",
        intern_url="https://jobs.trendyol.com/?department=Intern",
        extra_urls=["https://jobs.trendyol.com/?query=staj"],
    ),
    CompanyConfig(
        name="Getir",
        careers_url="https://getir.com/en/careers/",
        intern_url="https://getir.com/en/careers/?department=Internship",
    ),
    CompanyConfig(
        name="Hepsiburada",
        careers_url="https://ik.hepsiburada.com/",
        intern_url="https://ik.hepsiburada.com/?keyword=staj",
    ),
    CompanyConfig(
        name="Baykar",
        careers_url="https://www.baykarsavunma.com/kariyer.html",
        intern_url="https://www.baykarsavunma.com/kariyer.html",
        search_keyword="staj",
    ),
    CompanyConfig(
        name="Koç",
        careers_url="https://www.koccareers.com.tr/",
        intern_url="https://www.koccareers.com.tr/staj",
        extra_urls=["https://www.koc.com.tr/kariyer/staj-programlari"],
    ),
    CompanyConfig(
        name="Sabancı",
        careers_url="https://kariyer.sabanci.com/",
        intern_url="https://kariyer.sabanci.com/staj",
    ),
    CompanyConfig(
        name="Eczacıbaşı",
        careers_url="https://kariyer.eczacibasi.com.tr/",
        intern_url="https://kariyer.eczacibasi.com.tr/?type=staj",
    ),
    CompanyConfig(
        name="Anadolu Grubu",
        careers_url="https://kariyer.anadolugrubu.com.tr/",
        intern_url="https://kariyer.anadolugrubu.com.tr/staj",
        extra_urls=[
            "https://www.efes.com/kariyer",
            "https://www.cciturkey.com/kariyer",
        ],
    ),
    CompanyConfig(
        name="Yıldız Holding",
        careers_url="https://kariyer.yildizholding.com.tr/",
        intern_url="https://kariyer.yildizholding.com.tr/staj",
        extra_urls=["https://jobs.pladis.com/?search=intern"],
    ),
    CompanyConfig(
        name="Akbank",
        careers_url="https://www.akbank.com/kariyer",
        intern_url="https://www.akbank.com/kariyer/staj",
        extra_urls=["https://genclikakademisi.akbank.com/"],
    ),
    CompanyConfig(
        name="Garanti BBVA",
        careers_url="https://www.garantibbva.com.tr/kariyer",
        intern_url="https://www.garantibbva.com.tr/kariyer/staj-programlari",
    ),
    CompanyConfig(
        name="Türkiye İş Bankası",
        careers_url="https://www.isbank.com.tr/kariyer",
        intern_url="https://www.isbank.com.tr/kariyer/staj-programlari",
    ),
    CompanyConfig(
        name="Şişecam",
        careers_url="https://kariyer.sisecam.com/",
        intern_url="https://kariyer.sisecam.com/?type=staj",
    ),
    # Additional banks
    CompanyConfig(
        name="Yapı Kredi",
        careers_url="https://kariyer.yapikredi.com.tr/",
        intern_url="https://kariyer.yapikredi.com.tr/staj",
    ),
    CompanyConfig(
        name="Ziraat Bankası",
        careers_url="https://www.ziraatbank.com.tr/kariyer",
        intern_url="https://www.ziraatbank.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Halkbank",
        careers_url="https://www.halkbank.com.tr/kariyer",
        intern_url="https://www.halkbank.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="VakıfBank",
        careers_url="https://www.vakifbank.com.tr/kariyer",
        intern_url="https://www.vakifbank.com.tr/kariyer/staj",
    ),
]

# ═══════════════════════════════════════════════════════════════
# GOOGLE CUSTOM SEARCH DOMAINS (used if API key configured)
# Searches site:<domain> "staj" OR "intern" once per day.
# ═══════════════════════════════════════════════════════════════
GOOGLE_SEARCH_DOMAINS: list[str] = [
    "koc.com.tr",
    "sabanci.com",
    "eczacibasi.com.tr",
    "anadolugrubu.com.tr",
    "yildizholding.com.tr",
    "baykarsavunma.com",
    "sisecam.com",
    "akbank.com",
    "garantibbva.com.tr",
    "isbank.com.tr",
    "yapikredi.com.tr",
    "ziraatbank.com.tr",
    "halkbank.com.tr",
    "vakifbank.com.tr",
    "youthall.com",
    "toptalent.co",
    "vizyonergenc.com",
]
