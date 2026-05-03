"""Central configuration for the internship aggregator bot."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# Load target companies from companies.csv (preferred) or Companies.txt fallback
import pathlib, csv as _csv

_csv_file  = pathlib.Path(__file__).parent / "companies.csv"
_txt_file  = pathlib.Path(__file__).parent / "Companies.txt"
COMPANIES_LIST: list[str] = []

if _csv_file.exists():
    with open(_csv_file, encoding="utf-8", newline="") as _f:
        COMPANIES_LIST = [row["Company"] for row in _csv.DictReader(_f) if row.get("Company", "").strip()]
elif _txt_file.exists():
    _raw = _txt_file.read_text(encoding="utf-8")
    COMPANIES_LIST = [c.strip() for c in _raw.replace("\n", ",").split(",") if c.strip()]

# ── Telegram ─────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Scraper behaviour ─────────────────────────────────────────
RUN_INTERVAL_MINUTES: int = int(os.getenv("RUN_INTERVAL_MINUTES", "180"))
MAX_JOBS_PER_SOURCE: int = int(os.getenv("MAX_JOBS_PER_SOURCE", "50"))
HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"
LOOKBACK_DAYS: int = int(os.getenv("LOOKBACK_DAYS", "1"))
DDG_COMPANY_QUERY_LIMIT: int = int(os.getenv("DDG_COMPANY_QUERY_LIMIT", "80"))
DDG_COMPANY_CONCURRENCY: int = int(os.getenv("DDG_COMPANY_CONCURRENCY", "4"))

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
    "graduate", "graduate program", "mezun aday",
    "new grad", "new graduate", "yeni mezun", "entry level", "entry-level",
    "long term intern", "uzun dönem staj",
]

BLACKLIST_KEYWORDS: list[str] = [
    "senior", "sr.", " lead ", "principal", "manager",
    "director", "head of", " vp ", "c.t.o", "cto", "coo", "cfo",
    "chief", "freelance", "serbest çalışan",
    "uzman", "specialist", "experienced", "deneyimli",
    "full-time", "tam zamanlı", "kalıcı", "daimi",
    # Non-Turkey / wrong audience
    "saudi", "nationals only", "deutschland", "germany",
    "london", "amsterdam", "dubai", "egypt", "poland",
]

# ── Software / computer engineering focus ───────────────────────────────────
# After a job passes the internship gate, it must match at least one of these
# software-focused signals. Keep this list role/skill-specific; broad words
# such as "engineer", "mühendis", "digital", or "product" create noisy alerts.
CS_FIELD_KEYWORDS: list[str] = [
    # Turkish roles / domains
    "yazılım", "yazilim", "bilgisayar", "bilişim", "bilisim",
    "bilgi işlem", "bilgi islem", "bilgi sistem",
    "yazılım mühendis", "yazilim muhendis",
    "bilgisayar mühendis", "bilgisayar muhendis",
    "geliştirici", "gelistirici", "uygulama geliştir", "uygulama gelistir",
    "mobil uygulama", "web geliştir", "web gelistir",
    "programlama", "kodlama", "veri ", "veri bilim", "veri bilimi",
    "veri analiz", "veri analiti", "veri mühendis", "veri muhendis",
    "veri tabanı", "veri tabani", "yapay zeka", "makine öğren",
    "makine ogren", "derin öğren", "derin ogren",
    "siber güvenlik", "siber guvenlik", "siber", "bulut",
    "ağ yönetim", "ag yonetim", "ağ mühendis", "ag muhendis",
    "sistem mühendis", "sistem muhendis", "donanım", "donanim",
    "gömülü", "gomulu", "otomasyon test", "test otomasyon",
    "oyun geliştir", "oyun gelistir",
    # English roles / domains
    "software", "computer science", "computer engineering",
    "developer", "development", "software engineer", "software engineering",
    "data ", "data science", "data analyst", "data analytics", "data engineer",
    "business intelligence", "data visualization",
    "machine learning", "deep learning", "artificial intelligence",
    "frontend", "backend", "full stack", "fullstack",
    "mobile", "android", "ios", "web",
    "devops", "cloud", "cybersecurity", "cyber security", "infosec",
    "network engineer", "systems engineer", "infrastructure", "embedded",
    "information technology", "information systems",
    "quality assurance", "test engineer", "test automation", "automation testing",
    "game developer", "game development", "robotics", "mechatronics", "mekatronik",
    # Tools / languages / platforms
    "python", "java ", "c++", "c#", "javascript", "typescript",
    "react", "angular", "vue", "node", "django", "flask",
    "spring", ".net", "swift", "kotlin", "golang", "rust",
    "sql", "nosql", "database", "api ", "rest api", "graphql", "microservice",
    "aws", "azure", "gcp", "docker", "kubernetes",
    "blockchain", "iot", "ar/vr", "3d", "unity", "unreal",
    "tableau", "power bi", "git", "linux",
    # Short tokens with spaces are matched against a padded text haystack.
    " it ", " ai ", " ml ", " qa ", " bi ", " ui ", " ux ",
]

# If one of these appears in the title/company text, reject it even if the
# company or snippet contains a tech word. This prevents "Marketing Intern at
# Google" or "Finance Data Intern" style false positives.
CS_EXCLUDE_KEYWORDS: list[str] = [
    "marketing", "pazarlama", "sales", "satış", "satis",
    "business development", "iş geliştirme", "is gelistirme",
    "customer success", "müşteri", "musteri", "crm",
    "human resources", "hr intern", "recruitment", "insan kaynak",
    "finance", "finans", "accounting", "muhasebe", "audit", "denetim",
    "treasury", "hazine", "tax", "vergi", "legal", "hukuk",
    "procurement", "satın alma", "satin alma", "purchasing",
    "supply chain", "lojistik", "logistics", "operations", "operasyon",
    "production", "üretim", "uretim", "manufacturing",
    "mechanical", "makine mühendis", "makine muhendis",
    "industrial engineering", "endüstri mühendis", "endustri muhendis",
    "chemical", "kimya", "civil engineering", "inşaat", "insaat",
    "pharma", "pharmaceutical", "clinical", "klinik", "medical", "medikal",
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
    "Trendyol": "trendyol",
    "Dream Games": "dreamgames",
    "Peak Games": "peakgames",
    "Codeway Studios": "codeway",
    # Insider returns 404 on Lever — covered via DDG search
}

WORKABLE_COMPANIES: dict[str, str] = {
    "Getir": "getir",
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

# ── Original companies — only verified globally accessible URLs ───────────────
_ORIGINAL_COMPANIES: list[CompanyConfig] = [
    # Banks/conglomerates with inaccessible career pages removed.
    # They post on Toptalent/Youthall/LinkedIn instead.
]

# ── Turkish companies with globally accessible career pages ───────────────────
_TURKISH_COMPANIES: list[CompanyConfig] = [
    CompanyConfig(
        name="Pegasus",
        careers_url="https://www.flypgs.com/kariyer",
        intern_url="https://www.flypgs.com/kariyer",
        search_keyword="staj",
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
    ),
    CompanyConfig(
        name="Toyota Türkiye",
        careers_url="https://www.toyota-tr.com/kariyer",
        intern_url="https://www.toyota-tr.com/kariyer/staj",
    ),
    CompanyConfig(
        name="AXA Sigorta",
        careers_url="https://axa.taleo.net/careersection/ax/jobsearch.ftl?lang=en&location=Turkey",
        intern_url="https://axa.taleo.net/careersection/ax/jobsearch.ftl?lang=en&location=Turkey&keyword=intern",
        search_keyword="intern",
    ),
    CompanyConfig(
        name="Diageo Türkiye",
        careers_url="https://www.diageoturkiye.com/kariyer",
        intern_url="https://www.diageoturkiye.com/kariyer",
        search_keyword="staj",
    ),
    CompanyConfig(
        name="Abdi İbrahim",
        careers_url="https://www.abdiibrahim.com.tr/kariyer",
        intern_url="https://www.abdiibrahim.com.tr/kariyer",
        search_keyword="staj",
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
        intern_url="https://www.bosch.com.tr/kariyer/oegrenciler-ve-mezunlar/",
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
    # BASF, Henkel, Jotun: direct scraping returns global/wrong results — covered by DDG

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
    "youthall.com", "toptalent.co",
    "kariyerkapisi.cbiko.gov.tr", "secretcv.com",
    # Turkish conglomerates
    "koc.com.tr", "koccareers.com.tr", "sabanci.com", "eczacibasi.com.tr",
    "anadolugrubu.com.tr", "yildizholding.com.tr", "baykartech.com",
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
    "toyota-tr.com", "hyundaiassan.com.tr", "man.com.tr",
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
