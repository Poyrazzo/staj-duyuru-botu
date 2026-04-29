"""Central configuration for the internship aggregator bot."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Scraper behaviour ────────────────────────────────────────
RUN_INTERVAL_MINUTES: int = int(os.getenv("RUN_INTERVAL_MINUTES", "30"))
MAX_JOBS_PER_SOURCE: int = int(os.getenv("MAX_JOBS_PER_SOURCE", "50"))
HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"
LOOKBACK_DAYS: int = int(os.getenv("LOOKBACK_DAYS", "1"))

# ── Paths ────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "data/jobs.db")
LOG_DIR: str = "logs"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Proxy ────────────────────────────────────────────────────
HTTP_PROXY: str | None = os.getenv("HTTP_PROXY") or None
HTTPS_PROXY: str | None = os.getenv("HTTPS_PROXY") or None

# ── Health check ─────────────────────────────────────────────
HEALTH_CHECK_INTERVAL_HOURS: int = int(
    os.getenv("HEALTH_CHECK_INTERVAL_HOURS", "168")
)

# ── Keyword filters ──────────────────────────────────────────
WHITELIST_KEYWORDS: list[str] = [
    "staj", "stajyer", "intern", "internship",
    "aday", "candidate", "programı", "program",
    "genç yetenek", "yetenek", "talent",
    "junior", "başlangıç",
]

BLACKLIST_KEYWORDS: list[str] = [
    "senior", "sr.", "lead", "principal", "manager",
    "director", "head of", "vp ", "c.t.o", "cto",
    "chief", "freelance", "serbest", "uzman", "expert",
    "experienced", "deneyimli",
]

# Role category tags (keyword → category)
ROLE_CATEGORIES: dict[str, str] = {
    "software": ["yazılım", "software", "developer", "geliştirici", "backend",
                 "frontend", "full stack", "fullstack", "mobile", "data",
                 "ml", "yapay zeka", "ai", "devops", "cloud", "cyber"],
    "marketing": ["pazarlama", "marketing", "dijital", "digital", "sosyal medya",
                  "social media", "content", "içerik", "seo", "sem", "growth"],
    "finance":   ["finans", "finance", "muhasebe", "accounting", "audit",
                  "bütçe", "budget", "yatırım", "investment"],
    "design":    ["tasarım", "design", "ui", "ux", "grafik", "graphic",
                  "motion", "product design"],
    "hr":        ["insan kaynakları", "human resources", "hr", "ik",
                  "recruitment", "işe alım"],
    "operations":["operasyon", "operations", "lojistik", "logistics",
                  "supply chain", "tedarik"],
    "sales":     ["satış", "sales", "business development", "iş geliştirme",
                  "account", "müşteri"],
}

# ── Source URLs ──────────────────────────────────────────────
KARIYER_URL: str = "https://www.kariyer.net/is-ilanlari?kw=stajyer&srt=1"
YOUTHALL_URL: str = "https://www.youthall.com/tr/jobs/"

# Request timing (seconds)
MIN_SLEEP: float = 3.0
MAX_SLEEP: float = 10.0

# Browser viewport to mimic a real student laptop
VIEWPORT: dict[str, int] = {"width": 1366, "height": 768}

# Turkish locale strings for Playwright
LOCALE: str = "tr-TR"
TIMEZONE: str = "Europe/Istanbul"
