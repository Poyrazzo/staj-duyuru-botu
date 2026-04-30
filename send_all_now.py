"""
One-time script: scrape everything, enrich every job, send ALL filtered
internships to Telegram regardless of dedup/DB status.

Usage:  python send_all_now.py
"""

import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.WARNING)

import config
from scrapers import (
    LinkedInScraper, KariyerScraper, YouthallScraper,
    ATSScraper, ToptalentScraper, VizyonerGencScraper,
    KariyerKapisiScraper, CompanyCareerScraper, ExtraBoardsScraper,
)
from modules.data_cleaner import DataCleaner
from modules.notifier import TelegramNotifier
from modules.detail_extractor import DetailExtractor

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"
W = "\033[0m"; BOLD = "\033[1m"

SCRAPERS = [
    ATSScraper, LinkedInScraper, KariyerScraper, YouthallScraper,
    ToptalentScraper, VizyonerGencScraper, KariyerKapisiScraper,
    ExtraBoardsScraper,
]

async def main():
    print(f"\n{BOLD}{'═'*55}")
    print(f"  SEND ALL — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'═'*55}{W}\n")

    # ── 1. Scrape all sources ────────────────────────────────
    print(f"{B}[1/4] Scraping all sources…{W}")
    all_raw = []

    fast = await asyncio.gather(
        *[cls().scrape() for cls in [ATSScraper, LinkedInScraper]],
        return_exceptions=True,
    )
    for cls, r in zip([ATSScraper, LinkedInScraper], fast):
        if isinstance(r, list):
            all_raw.extend(r)
            print(f"  {G}✓{W} {cls.__name__:<30} {len(r):>3} raw")
        else:
            print(f"  {R}✗{W} {cls.__name__:<30} {str(r)[:60]}")

    browser_scrapers = [
        KariyerScraper, YouthallScraper, ToptalentScraper,
        VizyonerGencScraper, KariyerKapisiScraper, ExtraBoardsScraper,
    ]
    browser = await asyncio.gather(
        *[cls().scrape() for cls in browser_scrapers],
        return_exceptions=True,
    )
    for cls, r in zip(browser_scrapers, browser):
        if isinstance(r, list):
            all_raw.extend(r)
            print(f"  {G}✓{W} {cls.__name__:<30} {len(r):>3} raw")
        else:
            print(f"  {R}✗{W} {cls.__name__:<30} {str(r)[:60]}")

    try:
        company_jobs = await CompanyCareerScraper().scrape()
        all_raw.extend(company_jobs)
        print(f"  {G}✓{W} {'CompanyCareerScraper':<30} {len(company_jobs):>3} raw")
    except Exception as e:
        print(f"  {R}✗{W} CompanyCareerScraper: {str(e)[:60]}")

    print(f"\n  Total raw: {BOLD}{len(all_raw)}{W}")

    # ── 2. Filter ────────────────────────────────────────────
    print(f"\n{B}[2/4] Filtering internships…{W}")
    cleaner = DataCleaner()
    filtered = cleaner.clean(all_raw)
    # Deduplicate within this run by URL
    seen_urls = set()
    unique = []
    for j in filtered:
        if j.url not in seen_urls:
            seen_urls.add(j.url)
            unique.append(j)
    print(f"  {G}✓{W} {len(unique)} unique internships after filtering")

    # ── 3. Enrich every job (deadline, requirements, etc.) ───
    print(f"\n{B}[3/4] Enriching details (deadline / requirements)…{W}")
    extractor = DetailExtractor()
    enriched = await extractor.enrich_batch(unique, max_concurrent=6)

    with_deadline = sum(1 for j in enriched if j.deadline)
    with_reqs     = sum(1 for j in enriched if j.requirements)
    print(f"  {G}✓{W} Enriched: {with_deadline} with deadline, {with_reqs} with requirements")

    # ── 4. Sort and send ALL to Telegram ────────────────────
    final = DataCleaner.sort_by_date(enriched)
    print(f"\n{B}[4/4] Sending {len(final)} internships to Telegram…{W}")

    notifier = TelegramNotifier()
    # Header message
    await notifier._send(
        f"📢 <b>Güncel Staj İlanları — {datetime.now().strftime('%d.%m.%Y %H:%M')}</b>\n"
        f"<i>Toplam <b>{len(final)}</b> aktif staj ilanı bulundu.</i>\n\n"
        "Sıradaki mesajlarda tüm ilanlar tek tek gelecek 👇",
        disable_web_page_preview=True,
    )

    import asyncio as _aio
    await _aio.sleep(1)

    sent = 0
    for i, job in enumerate(final, 1):
        ok = await notifier.send_job_alert(job)
        if ok:
            sent += 1
        print(f"  {G}✓{W} [{i:>2}/{len(final)}] {job.company[:20]:<20} — {job.title[:45]}")
        await _aio.sleep(1.2)

    print(f"\n{BOLD}{G}Done! {sent}/{len(final)} sent to Telegram.{W}\n")


if __name__ == "__main__":
    asyncio.run(main())
