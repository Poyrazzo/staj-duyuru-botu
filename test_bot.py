"""
Full system test — runs each scraper with a timeout, reports results,
and sends a real Telegram test notification.

Usage:  python test_bot.py
"""

import asyncio
import sys
import time
import logging
from datetime import datetime

# Silence noisy libs during test
logging.basicConfig(level=logging.WARNING)
logging.getLogger("main").setLevel(logging.WARNING)

from modules.logger_setup import setup_logging
from db.database import Database, Job
from modules.data_cleaner import DataCleaner
from modules.notifier import TelegramNotifier
import config

# ── colours ─────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; W = "\033[0m"; BOLD = "\033[1m"

def ok(msg):  print(f"  {G}✓{W} {msg}")
def fail(msg): print(f"  {R}✗{W} {msg}")
def warn(msg): print(f"  {Y}!{W} {msg}")
def header(msg): print(f"\n{BOLD}{B}{'─'*55}\n  {msg}\n{'─'*55}{W}")

# ── timeout wrapper ──────────────────────────────────────────
async def run_with_timeout(coro, seconds: int):
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        return None, f"TIMEOUT after {seconds}s"
    except Exception as e:
        return None, str(e)[:120]

# ─────────────────────────────────────────────────────────────
# TEST 1 — Config & credentials
# ─────────────────────────────────────────────────────────────
async def test_config():
    header("1 / Config & Credentials")
    passed = True

    if config.TELEGRAM_BOT_TOKEN and "your_bot" not in config.TELEGRAM_BOT_TOKEN:
        ok(f"TELEGRAM_BOT_TOKEN set ({config.TELEGRAM_BOT_TOKEN[:12]}…)")
    else:
        fail("TELEGRAM_BOT_TOKEN missing"); passed = False

    if config.TELEGRAM_CHAT_ID:
        ok(f"TELEGRAM_CHAT_ID set ({config.TELEGRAM_CHAT_ID})")
    else:
        fail("TELEGRAM_CHAT_ID missing"); passed = False

    if config.GOOGLE_CSE_API_KEY and "your_google" not in config.GOOGLE_CSE_API_KEY:
        ok("GOOGLE_CSE_API_KEY set")
    else:
        warn("GOOGLE_CSE_API_KEY not set — Google CSE will be skipped (optional)")

    ok(f"Total companies configured: {len(config.COMPANY_CONFIGS)}")
    ok(f"Total Google domains: {len(config.GOOGLE_SEARCH_DOMAINS)}")
    return passed

# ─────────────────────────────────────────────────────────────
# TEST 2 — Telegram notification
# ─────────────────────────────────────────────────────────────
async def test_telegram():
    header("2 / Telegram Notification")
    notifier = TelegramNotifier()
    sent = await notifier._send(
        "🧪 <b>Bot Test Mesajı</b>\n"
        f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</i>\n\n"
        "Bu mesaj test sırasında gönderildi.\n"
        "Eğer bunu görüyorsan Telegram bağlantısı ✅ çalışıyor."
    )
    if sent:
        ok("Telegram notification sent successfully → check your chat!")
    else:
        fail("Telegram send failed — check token/chat_id in .env")
    return sent

# ─────────────────────────────────────────────────────────────
# TEST 3 — Database
# ─────────────────────────────────────────────────────────────
async def test_database():
    header("3 / Database")
    try:
        db = Database("data/test_run.db")
        j = Job(title="Test Staj", company="Test A.Ş.", location="İstanbul",
                source="Test", url="https://test.com/job/1",
                program_type="internship", deadline="2025-12-31")
        assert db.save_job(j) == True,  "First save should return True"
        assert db.save_job(j) == False, "Duplicate save should return False"
        assert db.get_stats()["total"] == 1
        import os; os.remove("data/test_run.db")
        ok("SQLite save / dedup / stats all working")
        return True
    except Exception as e:
        fail(f"Database error: {e}")
        return False

# ─────────────────────────────────────────────────────────────
# TEST 4 — DataCleaner
# ─────────────────────────────────────────────────────────────
async def test_cleaner():
    header("4 / DataCleaner Filters")
    cleaner = DataCleaner()

    intern_job = Job(title="Yazılım Stajyeri", company="Trendyol",
                     location="İstanbul", source="Test", url="https://a.com/1")
    senior_job = Job(title="Senior Software Engineer", company="Trendyol",
                     location="İstanbul", source="Test", url="https://a.com/2")
    fulltime   = Job(title="Data Analyst", company="ACME", location="İstanbul",
                     source="Test", url="https://a.com/3", program_type="full_time")
    marketing  = Job(title="Marketing Intern", company="Google",
                     location="İstanbul", source="Test", url="https://a.com/4",
                     description="Technology company internship")
    mechanical = Job(title="Mechanical Engineering Intern", company="Ford",
                     location="İstanbul", source="Test", url="https://a.com/5")

    results = cleaner.clean([intern_job, senior_job, fulltime, marketing, mechanical])
    passed = True

    if len(results) == 1 and results[0].title == "Yazılım Stajyeri":
        ok("Software intern passed ✓   Senior/full-time/non-CS internships blocked ✓")
        ok(f"Category assigned: {results[0].category}")
    else:
        fail(f"Expected 1 job through filter, got {len(results)}: {[j.title for j in results]}")
        passed = False
    return passed


async def test_search_result_filter():
    header("4b / Search Result Hygiene")
    from scrapers.search_filter import is_actionable_search_result

    cases = [
        (
            "Software Engineering Intern - Trendyol Careers",
            "https://jobs.lever.co/trendyol/abc",
            "Apply for the 2026 software engineering internship.",
            True,
        ),
        (
            "Yazılım Stajyeri başvuruları başladı",
            "https://www.example-news.com/teknoloji/yazilim-stajyeri-basvuru",
            "Son başvuru tarihi ve başvuru linki açıklandı.",
            True,
        ),
        (
            "I am happy to share that I started my internship at Firm A",
            "https://www.linkedin.com/posts/person_started-my-internship",
            "A personal LinkedIn post about starting an internship.",
            False,
        ),
        (
            "Ahmet Yılmaz staja başladı",
            "https://www.linkedin.com/feed/update/urn:li:activity:123",
            "LinkedIn update.",
            False,
        ),
        (
            "2024 Yaz Stajı başvuruları",
            "https://company.com/kariyer/staj-2024",
            "Old internship application announcement.",
            False,
        ),
    ]

    passed = True
    for title, url, snippet, expected in cases:
        actual = is_actionable_search_result(title, url, snippet)
        if actual != expected:
            fail(f"{title!r}: expected {expected}, got {actual}")
            passed = False
    if passed:
        ok("Search junk blocked while actionable postings still pass")
    return passed

# ─────────────────────────────────────────────────────────────
# TEST 5 — Individual scrapers (with timeout)
# ─────────────────────────────────────────────────────────────
SCRAPER_TESTS = [
    # (label,            scraper_class,  timeout_sec)
    ("ATS (Greenhouse)",  "ATSScraper",         30),
    ("LinkedIn (JobSpy)", "LinkedInScraper",     60),
    ("Kariyer.net",       "KariyerScraper",      120),
    ("Youthall",          "YouthallScraper",     150),
    ("Toptalent",         "ToptalentScraper",    120),
    ("Vizyoner Genç",     "VizyonerGencScraper", 120),
    ("Kariyer Kapısı",    "KariyerKapisiScraper",120),
    ("Extra Boards",      "ExtraBoardsScraper",  150),
]

async def test_scrapers():
    header("5 / Scraper Tests (live)")
    import scrapers as sc

    results = {}
    for label, cls_name, timeout in SCRAPER_TESTS:
        cls = getattr(sc, cls_name)
        t0 = time.time()
        print(f"  {Y}→{W} {label} ...", end="", flush=True)
        try:
            jobs = await asyncio.wait_for(cls().scrape(), timeout=timeout)
            elapsed = time.time() - t0
            if jobs is None:
                jobs = []
            # Quick filter for internships
            cleaner = DataCleaner()
            filtered = cleaner.clean(jobs)
            print(f"\r  {G}✓{W} {label:<25} {len(jobs):>3} raw → {len(filtered):>3} internships  ({elapsed:.0f}s)")
            results[label] = {"raw": len(jobs), "intern": len(filtered), "status": "OK",
                              "sample": filtered[0].title[:50] if filtered else None}
        except asyncio.TimeoutError:
            elapsed = time.time() - t0
            print(f"\r  {Y}!{W} {label:<25} TIMEOUT after {timeout}s")
            results[label] = {"raw": 0, "intern": 0, "status": f"TIMEOUT({timeout}s)"}
        except Exception as e:
            elapsed = time.time() - t0
            print(f"\r  {R}✗{W} {label:<25} ERROR: {str(e)[:60]}")
            results[label] = {"raw": 0, "intern": 0, "status": f"ERROR: {str(e)[:60]}"}

    return results

# ─────────────────────────────────────────────────────────────
# TEST 6 — Company scraper (3 companies only)
# ─────────────────────────────────────────────────────────────
async def test_company_sample():
    header("6 / Company Career Pages (sample: 3 companies)")
    from scrapers.company_career_scraper import CompanyCareerScraper
    from config import CompanyConfig

    sample_companies = [
        cfg for cfg in config.COMPANY_CONFIGS
        if cfg.name in ("Trendyol", "Kariyer.net'te değil", "Akbank", "Garanti BBVA")
    ]
    # fallback: take first 3
    if not sample_companies:
        sample_companies = config.COMPANY_CONFIGS[:3]

    print(f"  Testing: {', '.join(c.name for c in sample_companies)}")
    results = {}

    try:
        from playwright.async_api import async_playwright
        from playwright_stealth import stealth_async

        scraper = CompanyCareerScraper()
        opts = scraper.get_browser_context_options()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=opts["headless"])
            for cfg in sample_companies:
                t0 = time.time()
                print(f"  {Y}→{W} {cfg.name} ...", end="", flush=True)
                try:
                    context = await browser.new_context(
                        locale=opts["locale"], timezone_id=opts["timezone_id"],
                        viewport=opts["viewport"], user_agent=scraper.random_user_agent()
                    )
                    page = await context.new_page()
                    await stealth_async(page)

                    jobs = await asyncio.wait_for(
                        scraper._scrape_company(page, cfg), timeout=45
                    )
                    elapsed = time.time() - t0
                    cleaner = DataCleaner()
                    filtered = cleaner.clean(jobs)
                    print(f"\r  {G}✓{W} {cfg.name:<25} {len(jobs):>3} raw → {len(filtered):>3} internships  ({elapsed:.0f}s)")
                    if filtered:
                        print(f"      Sample: \"{filtered[0].title}\"")
                    results[cfg.name] = len(filtered)
                    await context.close()
                except asyncio.TimeoutError:
                    print(f"\r  {Y}!{W} {cfg.name:<25} TIMEOUT (45s)")
                    results[cfg.name] = "TIMEOUT"
                except Exception as e:
                    print(f"\r  {R}✗{W} {cfg.name:<25} {str(e)[:60]}")
                    results[cfg.name] = f"ERROR"
            await browser.close()
    except Exception as e:
        fail(f"Company test setup failed: {e}")

    return results

# ─────────────────────────────────────────────────────────────
# TEST 7 — Send real job alert to Telegram
# ─────────────────────────────────────────────────────────────
async def test_full_pipeline(scraper_results: dict):
    header("7 / Full Pipeline Test (real notification)")
    notifier = TelegramNotifier()

    # Build a fake-but-realistic job from whatever the scrapers found
    sample_job = None
    for label, data in scraper_results.items():
        if isinstance(data, dict) and data.get("sample"):
            sample_job = Job(
                title=data["sample"],
                company=label.replace(" (JobSpy)", "").replace(" (Greenhouse)", ""),
                location="İstanbul, Türkiye",
                source=label,
                url="https://github.com/Poyrazzo/staj-duyuru-botu",
                program_type="internship",
                deadline="2025-07-15",
                requirements="• Python veya benzeri programlama dili\n• Üniversite 3. veya 4. sınıf öğrencisi",
                category="software",
            )
            break

    if not sample_job:
        sample_job = Job(
            title="Yazılım Geliştirme Stajyeri",
            company="Örnek Şirket A.Ş.",
            location="İstanbul",
            source="Test",
            url="https://github.com/Poyrazzo/staj-duyuru-botu",
            program_type="internship",
            deadline="2025-07-01",
            category="software",
        )

    sent = await notifier.send_job_alert(sample_job)
    if sent:
        ok("Real job-format Telegram message sent → check your chat!")
    else:
        fail("Telegram send failed")
    return sent

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
async def main():
    print(f"\n{BOLD}{'═'*55}")
    print(f"  STAJ DUYURU BOTU — FULL SYSTEM TEST")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"{'═'*55}{W}\n")

    scores = []

    scores.append(await test_config())
    scores.append(await test_telegram())
    scores.append(await test_database())
    scores.append(await test_cleaner())
    scores.append(await test_search_result_filter())

    scraper_results = await test_scrapers()
    working = sum(1 for v in scraper_results.values()
                  if isinstance(v, dict) and v["status"] == "OK")
    total_intern = sum(v["intern"] for v in scraper_results.values()
                       if isinstance(v, dict))

    scores.append(await test_company_sample())
    scores.append(await test_full_pipeline(scraper_results))

    # ── Summary ───────────────────────────────────────────────
    header("SUMMARY")
    print(f"  Scrapers working:       {G}{working}{W} / {len(SCRAPER_TESTS)}")
    print(f"  Internships found:      {G}{total_intern}{W} across all tested sources")
    print()

    for label, data in scraper_results.items():
        if isinstance(data, dict):
            status = data["status"]
            intern = data["intern"]
            icon = G+"✓"+W if status == "OK" else Y+"!"+W if "TIMEOUT" in status else R+"✗"+W
            print(f"  {icon}  {label:<25}  {intern:>3} internships  [{status}]")
            if data.get("sample"):
                print(f"       └─ e.g. \"{data['sample']}\"")

    print(f"\n{BOLD}  Check your Telegram — test messages should have arrived.{W}\n")


if __name__ == "__main__":
    asyncio.run(main())
