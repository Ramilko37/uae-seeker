from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import NormalizedJob

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    dedupe_key TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location_raw TEXT NOT NULL,
    country TEXT NOT NULL,
    city TEXT,
    workplace TEXT NOT NULL,
    seniority TEXT NOT NULL,
    role_family TEXT NOT NULL,
    stack_json TEXT NOT NULL,
    visa_relocation TEXT NOT NULL,
    description TEXT,
    canonical_url TEXT NOT NULL,
    apply_url TEXT,
    posted_at TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    status TEXT NOT NULL,
    score INTEGER NOT NULL,
    relevance_reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key TEXT NOT NULL,
    source TEXT NOT NULL,
    source_job_id TEXT,
    source_url TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(dedupe_key, source, source_url),
    FOREIGN KEY(dedupe_key) REFERENCES jobs(dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country);
CREATE INDEX IF NOT EXISTS idx_jobs_seniority ON jobs(seniority);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen_at);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def _to_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def upsert_jobs(connection: sqlite3.Connection, jobs: Iterable[NormalizedJob]) -> tuple[int, int]:
    new_count = 0
    updated_count = 0
    for job in jobs:
        existing = connection.execute(
            "SELECT first_seen_at FROM jobs WHERE dedupe_key = ?", (job.dedupe_key,)
        ).fetchone()
        first_seen_at = existing["first_seen_at"] if existing else _to_dt(job.first_seen_at)
        if existing:
            updated_count += 1
        else:
            new_count += 1

        connection.execute(
            """
            INSERT INTO jobs (
                dedupe_key, title, company, location_raw, country, city, workplace, seniority,
                role_family, stack_json, visa_relocation, description, canonical_url, apply_url,
                posted_at, first_seen_at, last_seen_at, status, score, relevance_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dedupe_key) DO UPDATE SET
                title = excluded.title,
                company = excluded.company,
                location_raw = excluded.location_raw,
                country = excluded.country,
                city = excluded.city,
                workplace = excluded.workplace,
                seniority = excluded.seniority,
                role_family = excluded.role_family,
                stack_json = excluded.stack_json,
                visa_relocation = excluded.visa_relocation,
                description = excluded.description,
                canonical_url = excluded.canonical_url,
                apply_url = excluded.apply_url,
                posted_at = excluded.posted_at,
                last_seen_at = excluded.last_seen_at,
                status = 'active',
                score = excluded.score,
                relevance_reason = excluded.relevance_reason
            """,
            (
                job.dedupe_key,
                job.title,
                job.company,
                job.location_raw,
                job.country,
                job.city,
                job.workplace,
                job.seniority,
                job.role_family,
                json.dumps(job.stack, ensure_ascii=False),
                job.visa_relocation,
                job.description,
                job.canonical_url,
                job.apply_url,
                job.posted_at.isoformat() if job.posted_at else None,
                first_seen_at,
                _to_dt(job.last_seen_at),
                job.status,
                job.score,
                job.relevance_reason,
            ),
        )
        connection.execute(
            """
            INSERT INTO job_sources (dedupe_key, source, source_job_id, source_url, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(dedupe_key, source, source_url) DO UPDATE SET
                source_job_id = excluded.source_job_id,
                last_seen_at = excluded.last_seen_at
            """,
            (
                job.dedupe_key,
                job.source,
                job.source_job_id,
                job.canonical_url,
                first_seen_at,
                _to_dt(job.last_seen_at),
            ),
        )
    connection.commit()
    return new_count, updated_count


def list_jobs(connection: sqlite3.Connection, limit: int = 50) -> list[NormalizedJob]:
    rows = connection.execute(
        "SELECT * FROM jobs WHERE status = 'active' ORDER BY last_seen_at DESC, score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_job(row) for row in rows]


def list_jobs_seen_since(connection: sqlite3.Connection, since: datetime, limit: int = 200) -> list[NormalizedJob]:
    rows = connection.execute(
        """
        SELECT * FROM jobs
        WHERE status = 'active' AND last_seen_at >= ?
        ORDER BY country ASC, score DESC, last_seen_at DESC
        LIMIT ?
        """,
        (_to_dt(since), limit),
    ).fetchall()
    return [_row_to_job(row) for row in rows]


def _row_to_job(row: sqlite3.Row) -> NormalizedJob:
    return NormalizedJob(
        dedupe_key=row["dedupe_key"],
        source="storage",
        title=row["title"],
        company=row["company"],
        location_raw=row["location_raw"],
        country=row["country"],
        city=row["city"],
        workplace=row["workplace"],
        seniority=row["seniority"],
        role_family=row["role_family"],
        stack=json.loads(row["stack_json"]),
        visa_relocation=row["visa_relocation"],
        description=row["description"],
        canonical_url=row["canonical_url"],
        apply_url=row["apply_url"],
        posted_at=row["posted_at"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
        status=row["status"],
        score=row["score"],
        relevance_reason=row["relevance_reason"],
    )
