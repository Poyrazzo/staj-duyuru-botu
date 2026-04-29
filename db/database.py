"""SQLite persistence layer for the internship aggregator bot."""

import os
import sqlite3
import hashlib
import logging
from datetime import datetime
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Represents a single internship posting."""
    title: str
    company: str
    location: str
    source: str
    url: str
    description: str = ""
    posted_date: Optional[str] = None
    category: str = "other"
    # computed on post-init
    job_id: str = field(default="", init=False)
    semantic_hash: str = field(default="", init=False)
    discovered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self) -> None:
        self.semantic_hash = _semantic_hash(self.company, self.title)
        self.job_id = _job_id(self.source, self.url)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "semantic_hash": self.semantic_hash,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "source": self.source,
            "url": self.url,
            "description": self.description,
            "posted_date": self.posted_date,
            "category": self.category,
            "discovered_at": self.discovered_at,
        }


def _semantic_hash(company: str, title: str) -> str:
    """Cross-site dedup: same company+title = same hash regardless of source."""
    raw = f"{company.lower().strip()}|{title.lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _job_id(source: str, url: str) -> str:
    raw = f"{source}|{url}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


class Database:
    """Thread-safe SQLite wrapper for job persistence."""

    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id          TEXT PRIMARY KEY,
        semantic_hash   TEXT NOT NULL,
        title           TEXT NOT NULL,
        company         TEXT NOT NULL,
        location        TEXT,
        source          TEXT NOT NULL,
        url             TEXT NOT NULL,
        description     TEXT,
        posted_date     TEXT,
        category        TEXT DEFAULT 'other',
        discovered_at   TEXT NOT NULL,
        notified        INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_semantic_hash ON jobs(semantic_hash);
    CREATE INDEX IF NOT EXISTS idx_discovered_at ON jobs(discovered_at);
    CREATE TABLE IF NOT EXISTS health_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        checked_at  TEXT NOT NULL,
        source      TEXT NOT NULL,
        status      TEXT NOT NULL,
        message     TEXT
    );
    """

    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            for stmt in self.CREATE_TABLE_SQL.strip().split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(s)
        logger.debug("Database initialised at %s", self.db_path)

    def is_new_job(self, job: Job) -> bool:
        """Return True if this job has never been seen (by semantic hash OR job_id)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM jobs WHERE job_id=? OR semantic_hash=?",
                (job.job_id, job.semantic_hash),
            ).fetchone()
        return row is None

    def save_job(self, job: Job) -> bool:
        """Insert a job. Returns True on success, False if duplicate."""
        if not self.is_new_job(job):
            return False
        d = job.to_dict()
        with self._conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO jobs
                   (job_id, semantic_hash, title, company, location, source,
                    url, description, posted_date, category, discovered_at, notified)
                   VALUES (:job_id, :semantic_hash, :title, :company, :location,
                           :source, :url, :description, :posted_date, :category,
                           :discovered_at, 0)""",
                d,
            )
        logger.debug("Saved new job: %s @ %s [%s]", job.title, job.company, job.source)
        return True

    def mark_notified(self, job_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET notified=1 WHERE job_id=?", (job_id,)
            )

    def get_unnotified_jobs(self) -> list[Job]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE notified=0 ORDER BY discovered_at ASC"
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def log_health(self, source: str, status: str, message: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO health_log (checked_at, source, status, message) VALUES (?,?,?,?)",
                (datetime.utcnow().isoformat(), source, status, message),
            )

    def get_stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            by_source = conn.execute(
                "SELECT source, COUNT(*) FROM jobs GROUP BY source"
            ).fetchall()
            by_category = conn.execute(
                "SELECT category, COUNT(*) FROM jobs GROUP BY category"
            ).fetchall()
        return {
            "total": total,
            "by_source": dict(by_source),
            "by_category": dict(by_category),
        }


def _row_to_job(row: sqlite3.Row) -> Job:
    j = Job(
        title=row["title"],
        company=row["company"],
        location=row["location"] or "",
        source=row["source"],
        url=row["url"],
        description=row["description"] or "",
        posted_date=row["posted_date"],
        category=row["category"] or "other",
    )
    j.job_id = row["job_id"]
    j.semantic_hash = row["semantic_hash"]
    j.discovered_at = row["discovered_at"]
    return j
