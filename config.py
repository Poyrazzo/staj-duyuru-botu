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

# ── Google Custom Search API ──────────────────────────────────
# Free tier: 100 queries/day  →  runs ONCE PER DAY as safety net
# Setup: https://developers.google.com/custom-search/v1/introduction
# 1. Create API key at console.cloud.google.com
# 2. Create CSE at cse.google.com, enable "Search the entire web"
GOOGLE_CSE_API_KEY: str = os.getenv("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_CX: str = os.getenv("GOOGLE_CSE_CX", "")

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

WHITELIST_KEYWORDS: list[str] = [
    "staj", "stajyer", "intern", "internship",
    "aday", "trainee", "programı", "program",
    "genç yetenek", "yetenek programı", "talent",
    "yaz dönemi", "yaz staj", "summer intern",
    "junior staj", "kampüs", "take-off", "takeoff",
    "graduate", "mezun aday",
]

BLACKLIST_KEYWORDS: list[str] = [
    "senior", "sr.", " lead ", "principal", "manager",
    "director", "head of", " vp ", "c.t.o", "cto", "coo", "cfo",
    "chief", "freelance", "serbest çalışan",
    "uzman", "specialist", "experienced", "deneyimli",
    "full-time", "tam zamanlı", "kalıcı", "daimi",
]

INTERN_CONFIRM_KEYWORDS: list[str] = [
    "staj", "stajyer", "intern", "internship",
    "yaz staj", "yetenek programı", "trainee", "aday programı",
    "take-off", "kampüs",
]

# ═══════════════════════════════════════════════════════════════
# ROLE CATEGORIES
# ═══════════════════════════════════════════════════════════════
ROLE_CATEGORIES: dict[str, list[str]] = {
    "software":    ["yazılım", "software", "developer", "geliştirici", "backend",
                    "frontend", "full stack", "fullstack", "mobile", "data",
                    "ml", "yapay zeka", "ai", "devops", "cloud", "cyber",
                    "bilgisayar", "mühendis", "engineer", "siber", "ağ", "network"],
    "marketing":   ["pazarlama", "marketing", "dijital", "digital", "sosyal medya",
                    "social media", "content", "içerik", "seo", "sem", "growth",
                    "marka", "brand", "reklam", "advertising"],
    "finance":     ["finans", "finance", "muhasebe", "accounting", "audit",
                    "bütçe", "budget", "yatırım", "investment", "bankacılık",
                    "treasury", "hazine", "vergi", "tax"],
    "design":      ["tasarım", "design", "ui", "ux", "grafik", "graphic",
                    "motion", "product design", "görsel"],
    "hr":          ["insan kaynakları", "human resources", "hr", "ik",
                    "recruitment", "işe alım", "yetenek"],
    "operations":  ["operasyon", "operations", "lojistik", "logistics",
                    "supply chain", "tedarik", "depo", "warehouse"],
    "sales":       ["satış", "sales", "business development", "iş geliştirme",
                    "account", "müşteri", "crm"],
    "legal":       ["hukuk", "legal", "avukat", "lawyer", "compliance", "uyum"],
    "engineering": ["makine", "elektrik", "electronic", "elektronik", "endüstri",
                    "industrial", "inşaat", "civil", "kimya", "chemical",
                    "malzeme", "materials", "enerji", "energy", "üretim",
                    "manufacturing", "kalite", "quality"],
    "pharma":      ["ilaç", "pharma", "pharmaceutical", "klinik", "clinical",
                    "medikal", "medical", "sağlık", "health", "biyoteknoloji"],
}

# ═══════════════════════════════════════════════════════════════
# JOB BOARD SOURCE URLs
# ═══════════════════════════════════════════════════════════════
KARIYER_URL: str = "https://www.kariyer.net/is-ilanlari?kw=stajyer&srt=1"
YOUTHALL_URL: str = "https://www.youthall.com/tr/jobs/?type=internship"
TOPTALENT_URL: str = "https://toptalent.co/tr/ilanlar/?type=internship"
VIZYONER_GENC_URL: str = "https://vizyonergenc.com/staj-ilanlari"
KARIYER_KAPISI_URL: str = "https://www.kariyerkapisi.cbiko.gov.tr/Arama/staj"
SECRETCV_URL: str = "https://www.secretcv.com/is-ilanlari?keyword=staj&sort=date"
YENIBIS_URL: str = "https://www.yenibis.com/is-ilani?q=staj"
COMATCHING_URL: str = "https://www.co-matching.com/staj"
ISO_STAJ_URL: str = "https://staj.iso.org.tr/"

# ═══════════════════════════════════════════════════════════════
# ATS DIRECT API (Greenhouse & Lever)
# ═══════════════════════════════════════════════════════════════
GREENHOUSE_COMPANIES: dict[str, str] = {
    # Verified slugs only — unconfirmed ones are handled by CompanyCareerScraper
}

LEVER_COMPANIES: dict[str, str] = {
    # Add as confirmed
}

# ═══════════════════════════════════════════════════════════════
# COMPANY CAREER PAGE CONFIGS
# ═══════════════════════════════════════════════════════════════
@dataclass
class CompanyConfig:
    name: str
    careers_url: str
    intern_url: str = ""
    search_keyword: str = "staj"
    extra_urls: list[str] = field(default_factory=list)

# ── Original 16 companies ─────────────────────────────────────
_ORIGINAL_COMPANIES: list[CompanyConfig] = [
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
        extra_urls=["https://www.efes.com/kariyer", "https://www.cciturkey.com/kariyer"],
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

# ── New Turkish companies ─────────────────────────────────────
_TURKISH_COMPANIES: list[CompanyConfig] = [
    CompanyConfig(
        name="Hayat Kimya",
        careers_url="https://www.hayat.com.tr/kariyer",
        intern_url="https://www.hayat.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Eti",
        careers_url="https://www.eticareer.com/",
        intern_url="https://www.eticareer.com/?type=staj",
        extra_urls=["https://www.eti.com.tr/kariyer"],
    ),
    CompanyConfig(
        name="Sütaş",
        careers_url="https://www.sutasgroup.com/kariyer",
        intern_url="https://www.sutasgroup.com/kariyer/staj",
    ),
    CompanyConfig(
        name="THY Take-Off Jr",
        careers_url="https://www.thy.com/kariyer",
        intern_url="https://www.thy.com/kariyer/staj-programlari",
        extra_urls=[
            "https://career.turkishairlines.com/",
            "https://www.thy.com/tr-TR/kurumsal/kariyer/staj",
        ],
        search_keyword="staj",
    ),
    CompanyConfig(
        name="Pegasus",
        careers_url="https://www.flypgs.com/kariyer",
        intern_url="https://www.flypgs.com/kariyer/staj",
        extra_urls=["https://career.flypgs.com/"],
    ),
    CompanyConfig(
        name="Ford Otosan",
        careers_url="https://www.fordotosan.com.tr/kariyer",
        intern_url="https://www.fordotosan.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Borusan Otomotiv",
        careers_url="https://www.borusan.com/kariyer",
        intern_url="https://www.borusan.com/kariyer/staj",
        extra_urls=["https://kariyer.borusan.com/"],
    ),
    CompanyConfig(
        name="Toyota Türkiye",
        careers_url="https://www.toyota.com.tr/kariyer",
        intern_url="https://www.toyota.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Hyundai Assan",
        careers_url="https://www.hyundaiassan.com.tr/kariyer",
        intern_url="https://www.hyundaiassan.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="MAN Türkiye",
        careers_url="https://www.man.com.tr/kariyer",
        intern_url="https://www.man.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Kastamonu Entegre",
        careers_url="https://www.kastamonuintegrated.com/kariyer",
        intern_url="https://www.kastamonuintegrated.com/kariyer/staj",
    ),
    CompanyConfig(
        name="Yıldız Entegre",
        careers_url="https://www.yildizentegre.com/kariyer",
        intern_url="https://www.yildizentegre.com/kariyer/staj",
    ),
    CompanyConfig(
        name="Filli Boya / Betek",
        careers_url="https://www.bekolite.com.tr/kariyer",
        intern_url="https://www.bekolite.com.tr/kariyer/staj",
        extra_urls=["https://www.filliboya.com.tr/kariyer"],
    ),
    CompanyConfig(
        name="Türkiye Sigorta",
        careers_url="https://www.turkiyesigorta.com.tr/kariyer",
        intern_url="https://www.turkiyesigorta.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Allianz Türkiye",
        careers_url="https://www.allianz.com.tr/kariyer",
        intern_url="https://www.allianz.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="AXA Sigorta",
        careers_url="https://www.axa.com.tr/kariyer",
        intern_url="https://www.axa.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Anadolu Efes",
        careers_url="https://www.efes.com/kariyer",
        intern_url="https://www.efes.com/kariyer/staj",
    ),
    CompanyConfig(
        name="Mey|Diageo",
        careers_url="https://www.mey.com.tr/kariyer",
        intern_url="https://www.mey.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Abdi İbrahim",
        careers_url="https://www.abdiibrahim.com.tr/kariyer",
        intern_url="https://www.abdiibrahim.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Nobel İlaç",
        careers_url="https://www.nobelilac.com.tr/kariyer",
        intern_url="https://www.nobelilac.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="Santa Farma",
        careers_url="https://www.santafarma.com.tr/kariyer",
        intern_url="https://www.santafarma.com.tr/kariyer/staj",
    ),
    CompanyConfig(
        name="İSO Staj",
        careers_url="https://staj.iso.org.tr/",
        intern_url="https://staj.iso.org.tr/",
    ),
]

# ── International / multinational companies with Turkey offices ──
_INTERNATIONAL_COMPANIES: list[CompanyConfig] = [
    CompanyConfig(
        name="Amazon Turkey",
        careers_url="https://www.amazon.jobs/en/search?base_query=intern&loc_query=Turkey",
        intern_url="https://www.amazon.jobs/en/search?base_query=intern&loc_query=Turkey",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Microsoft Turkey",
        careers_url="https://careers.microsoft.com/students/us/en/search-results?keywords=intern&country=Turkey",
        intern_url="https://careers.microsoft.com/students/us/en/search-results?keywords=intern&country=Turkey",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Google Turkey",
        careers_url="https://careers.google.com/jobs/results/?q=intern&location=Turkey",
        intern_url="https://careers.google.com/jobs/results/?q=intern&location=Turkey",
        extra_urls=["https://buildyourfuture.withgoogle.com/programs/student-training-employment-program"],
        search_keyword="intern",
    ),
    CompanyConfig(
        name="SAP Turkey",
        careers_url="https://jobs.sap.com/search/?searchby=location&q=Turkey&category=Students+%26+Graduates",
        intern_url="https://jobs.sap.com/search/?searchby=location&q=Turkey&category=Students+%26+Graduates",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Oracle Turkey",
        careers_url="https://careers.oracle.com/jobs/#en/sites/jobsearch/requisitions?keyword=intern&location=Turkey",
        intern_url="https://careers.oracle.com/jobs/#en/sites/jobsearch/requisitions?keyword=intern&location=Turkey",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Siemens Turkey",
        careers_url="https://jobs.siemens.com/careers?query=intern&location=Turkey",
        intern_url="https://jobs.siemens.com/careers?query=intern&location=Turkey",
        extra_urls=["https://www.siemens.com/tr/tr/company/jobs.html"],
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Bosch Turkey",
        careers_url="https://www.bosch.com.tr/kariyer/",
        intern_url="https://www.bosch.com.tr/kariyer/staj/",
        extra_urls=["https://jobs.smartrecruiters.com/BoschGroup?keyword=intern&location=Turkey"],
        search_keyword="staj",
    ),
    CompanyConfig(
        name="ABB Turkey",
        careers_url="https://careers.abb/global/en/search-results?keywords=intern&location=Turkey",
        intern_url="https://careers.abb/global/en/search-results?keywords=intern&location=Turkey",
        extra_urls=["https://new.abb.com/careers/tr"],
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Ericsson Turkey",
        careers_url="https://jobs.ericsson.com/careers?query=intern&location=Turkey",
        intern_url="https://jobs.ericsson.com/careers?query=intern&location=Turkey",
        extra_urls=["https://www.ericsson.com/en/careers/find-your-role?country=Turkey"],
        search_keyword="intern",
    ),
    CompanyConfig(
        name="DHL Express Turkey",
        careers_url="https://careers.dhl.com/global/en/search-results?keywords=intern&location=Turkey",
        intern_url="https://careers.dhl.com/global/en/search-results?keywords=intern&location=Turkey",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Philip Morris Turkey",
        careers_url="https://www.pmicareers.com/search-jobs?country=Turkey&keywords=intern",
        intern_url="https://www.pmicareers.com/search-jobs?country=Turkey&keywords=intern",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="JTI Turkey",
        careers_url="https://www.jti.com/careers/job-search?country=Turkey&keyword=intern",
        intern_url="https://www.jti.com/careers/job-search?country=Turkey&keyword=intern",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="BAT Turkey",
        careers_url="https://careers.bat.com/search/?createNewAlert=false&q=intern&locationsearch=Turkey",
        intern_url="https://careers.bat.com/search/?createNewAlert=false&q=intern&locationsearch=Turkey",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Danone Turkey",
        careers_url="https://danone.wd3.myworkdayjobs.com/danone?q=intern&locationCountry=TR",
        intern_url="https://danone.wd3.myworkdayjobs.com/danone?q=intern&locationCountry=TR",
        extra_urls=["https://www.danone.com.tr/kariyer"],
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Reckitt Turkey",
        careers_url="https://careers.reckitt.com/search/?q=intern&q2=&alertId=&locationsearch=Turkey",
        intern_url="https://careers.reckitt.com/search/?q=intern&q2=&alertId=&locationsearch=Turkey",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="L'Oréal Turkey",
        careers_url="https://careers.loreal.com/en_US/jobs/SearchJobs/intern?3_55_3=16921",
        intern_url="https://careers.loreal.com/en_US/jobs/SearchJobs/intern?3_55_3=16921",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Estée Lauder Turkey",
        careers_url="https://careers.elcompanies.com/search-jobs?keywords=intern&location=Turkey",
        intern_url="https://careers.elcompanies.com/search-jobs?keywords=intern&location=Turkey",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="GSK Turkey",
        careers_url="https://jobs.gsk.com/en-gb/search#q=intern&t=Jobs&numberOfResults=15&ac=country%3ATurkey",
        intern_url="https://jobs.gsk.com/en-gb/search#q=intern&t=Jobs&numberOfResults=15&ac=country%3ATurkey",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Pfizer Turkey",
        careers_url="https://www.pfizer.com/about/careers/search?q=intern&country=TR",
        intern_url="https://www.pfizer.com/about/careers/search?q=intern&country=TR",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Sanofi Turkey",
        careers_url="https://sanofi.wd3.myworkdayjobs.com/SanofiCareers?q=intern&locationCountry=TR",
        intern_url="https://sanofi.wd3.myworkdayjobs.com/SanofiCareers?q=intern&locationCountry=TR",
        extra_urls=["https://www.sanofi.com.tr/kariyer"],
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Bayer Turkey",
        careers_url="https://career.bayer.com/en/job-search#q=intern&location=Turkey",
        intern_url="https://career.bayer.com/en/job-search#q=intern&location=Turkey",
        extra_urls=["https://www.bayer.com/en/tr/careers"],
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Novartis Turkey",
        careers_url="https://www.novartis.com/careers/career-search?search=intern&country=Turkey",
        intern_url="https://www.novartis.com/careers/career-search?search=intern&country=Turkey",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="BASF Turkey",
        careers_url="https://www.basf.com/global/en/careers/jobs.html?search=intern&country=TR",
        intern_url="https://www.basf.com/global/en/careers/jobs.html?search=intern&country=TR",
        extra_urls=["https://www.basf.com/tr/tr/who-we-are/careers.html"],
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Henkel Turkey",
        careers_url="https://www.henkel.com/careers/jobs-and-applications#q=intern&location=Turkey",
        intern_url="https://www.henkel.com/careers/jobs-and-applications#q=intern&location=Turkey",
        extra_urls=["https://www.henkel.com.tr/kariyer"],
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Jotun Turkey",
        careers_url="https://www.jotun.com/tr/tr/b2b/about-jotun/careers/vacancies.html",
        intern_url="https://www.jotun.com/tr/tr/b2b/about-jotun/careers/vacancies.html",
        search_keyword="staj",
    ),
]

# ── Merge all company configs ─────────────────────────────────
COMPANY_CONFIGS: list[CompanyConfig] = (
    _ORIGINAL_COMPANIES + _TURKISH_COMPANIES + _INTERNATIONAL_COMPANIES
)

# ═══════════════════════════════════════════════════════════════
# GOOGLE CUSTOM SEARCH — DOMAIN LIST
# One query per domain per day as safety net.
# Free: 100 queries/day. Total domains here: ~70 → fits within limit.
# Query pattern: site:{domain} (staj OR intern OR internship) -senior -manager
# ═══════════════════════════════════════════════════════════════
GOOGLE_SEARCH_DOMAINS: list[str] = [
    # Turkish job boards
    "youthall.com", "toptalent.co", "vizyonergenc.com",
    "kariyerkapisi.cbiko.gov.tr", "secretcv.com", "yenibis.com",
    "co-matching.com", "staj.iso.org.tr",
    # Turkish conglomerates
    "koc.com.tr", "koccareers.com.tr", "sabanci.com", "eczacibasi.com.tr",
    "anadolugrubu.com.tr", "yildizholding.com.tr", "baykarsavunma.com",
    "sisecam.com", "hayat.com.tr", "eti.com.tr",
    # Banks & insurance
    "akbank.com", "garantibbva.com.tr", "isbank.com.tr",
    "yapikredi.com.tr", "ziraatbank.com.tr", "halkbank.com.tr",
    "vakifbank.com.tr", "turkiyesigorta.com.tr", "allianz.com.tr", "axa.com.tr",
    # FMCG / food
    "sutasgroup.com", "efes.com", "mey.com.tr", "abdiibrahim.com.tr",
    "nobelilac.com.tr", "santafarma.com.tr",
    # Airlines & automotive
    "thy.com", "flypgs.com", "fordotosan.com.tr", "borusan.com",
    "toyota.com.tr", "hyundaiassan.com.tr", "man.com.tr",
    # Materials & industry
    "kastamonuintegrated.com", "yildizentegre.com", "bekolite.com.tr",
    # International tech
    "amazon.jobs", "careers.microsoft.com", "careers.google.com",
    "jobs.sap.com", "oracle.com", "jobs.siemens.com",
    "bosch.com.tr", "careers.abb", "jobs.ericsson.com", "careers.dhl.com",
    # International FMCG / pharma / tobacco
    "pmicareers.com", "jti.com", "careers.bat.com",
    "careers.loreal.com", "careers.elcompanies.com", "jobs.gsk.com",
    "pfizer.com", "sanofi.com", "career.bayer.com", "novartis.com",
    "basf.com", "henkel.com", "jotun.com", "reckitt.com",
    # Paint / chemicals
    "filliboya.com.tr",
]
