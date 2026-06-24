from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .classifier import normalize
from .config import AppConfig, SourceConfig
from .digest import write_digest
from .models import CollectionStats, NormalizedJob, RawJob
from .sources import build_source
from .storage import connect, list_jobs_seen_since, upsert_jobs


async def fetch_source(config: SourceConfig) -> tuple[SourceConfig, list[RawJob], Exception | None]:
    try:
        source = build_source(config)
        jobs = await source.fetch()
        return config, jobs, None
    except Exception as exc:  # keep one bad source from failing the full run
        return config, [], exc


async def collect_raw(config: AppConfig) -> tuple[list[tuple[SourceConfig, RawJob]], CollectionStats]:
    stats = CollectionStats(sources_enabled=len(config.enabled_sources))
    tasks = [fetch_source(source_config) for source_config in config.enabled_sources]
    results = await asyncio.gather(*tasks)

    raw_jobs: list[tuple[SourceConfig, RawJob]] = []
    for source_config, jobs, error in results:
        if error:
            stats.sources_failed += 1
            stats.errors.append(f"{source_config.name}: {error}")
            continue
        stats.sources_succeeded += 1
        stats.raw_seen += len(jobs)
        raw_jobs.extend((source_config, job) for job in jobs)

    return raw_jobs, stats


async def collect_and_store(
    config: AppConfig,
    db_path: str | Path,
    digest_path: str | Path | None = None,
    digest_window_hours: int = 24,
) -> tuple[list[NormalizedJob], CollectionStats]:
    raw_jobs, stats = await collect_raw(config)

    normalized: list[NormalizedJob] = []
    for source_config, raw in raw_jobs:
        job = normalize(raw, configured_country=source_config.country)
        if job is None:
            stats.rejected += 1
            continue
        normalized.append(job)
        stats.accepted += 1

    connection = connect(db_path)
    new_count, updated_count = upsert_jobs(connection, normalized)
    stats.new_jobs = new_count
    stats.updated_jobs = updated_count

    since = datetime.now(timezone.utc) - timedelta(hours=digest_window_hours)
    digest_jobs = list_jobs_seen_since(connection, since=since)
    if digest_path:
        write_digest(digest_jobs, digest_path, stats=stats)
    connection.close()
    return normalized, stats
