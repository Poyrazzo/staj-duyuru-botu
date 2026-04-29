"""LinkedIn scraper via the python-jobspy library."""

import logging
from datetime import datetime, timedelta

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from db.database import Job
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    source_name = "LinkedIn"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        reraise=True,
    )
    async def scrape(self) -> list[Job]:
        """Scrape LinkedIn internship listings for Turkey via JobSpy."""
        self.logger.info("Scraping LinkedIn …")

        # JobSpy is synchronous; run in thread pool to stay async-friendly
        import asyncio
        jobs_df = await asyncio.get_event_loop().run_in_executor(
            None, self._fetch_jobspy
        )

        if jobs_df is None or jobs_df.empty:
            self.logger.warning("LinkedIn returned no results.")
            return []

        results: list[Job] = []
        for _, row in jobs_df.iterrows():
            job = self._row_to_job(row)
            if job:
                results.append(job)

        self.logger.info("LinkedIn: %d raw listings fetched.", len(results))
        return results

    def _fetch_jobspy(self) -> pd.DataFrame | None:
        try:
            from jobspy import scrape_jobs

            df = scrape_jobs(
                site_name=["linkedin"],
                search_term="staj OR intern OR internship OR \"genç yetenek\"",
                location="Turkey",
                results_wanted=config.MAX_JOBS_PER_SOURCE,
                hours_old=config.LOOKBACK_DAYS * 24,
                country_indeed="Turkey",
                linkedin_fetch_description=True,
            )
            return df
        except Exception as exc:
            self.logger.error("JobSpy fetch failed: %s", exc)
            return None

    def _row_to_job(self, row: pd.Series) -> Job | None:
        try:
            title = str(row.get("title", "")).strip()
            company = str(row.get("company", "")).strip()
            location = str(row.get("location", "Turkey")).strip()
            url = str(row.get("job_url", "")).strip()
            description = str(row.get("description", "")).strip()

            if not title or not company or not url:
                return None

            # Normalise posted date
            posted = row.get("date_posted")
            posted_str: str | None = None
            if posted is not None:
                try:
                    if isinstance(posted, str):
                        posted_str = posted
                    else:
                        posted_str = pd.Timestamp(posted).strftime("%Y-%m-%d")
                except Exception:
                    posted_str = None

            return Job(
                title=title,
                company=company,
                location=location,
                source=self.source_name,
                url=url,
                description=description,
                posted_date=posted_str,
            )
        except Exception as exc:
            self.logger.debug("Skipping malformed row: %s", exc)
            return None
