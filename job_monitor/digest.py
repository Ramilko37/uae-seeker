from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .models import CollectionStats, NormalizedJob


def write_digest(jobs: list[NormalizedJob], path: str | Path, stats: CollectionStats | None = None) -> None:
    digest_path = Path(path)
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(render_digest(jobs, stats=stats), encoding="utf-8")


def render_digest(jobs: list[NormalizedJob], stats: CollectionStats | None = None) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = ["# Senior/Lead Frontend Jobs Digest", "", f"Generated at: **{generated_at}**", ""]

    if stats:
        lines.extend(
            [
                "## Run stats",
                "",
                f"- Sources enabled: {stats.sources_enabled}",
                f"- Sources succeeded: {stats.sources_succeeded}",
                f"- Sources failed: {stats.sources_failed}",
                f"- Raw jobs seen: {stats.raw_seen}",
                f"- Accepted: {stats.accepted}",
                f"- Rejected: {stats.rejected}",
                f"- New jobs: {stats.new_jobs}",
                f"- Updated jobs: {stats.updated_jobs}",
                "",
            ]
        )
        if stats.errors:
            lines.extend(["### Source errors", ""])
            for error in stats.errors:
                lines.append(f"- {error}")
            lines.append("")

    if not jobs:
        lines.extend(["## Jobs", "", "No matching jobs found in this run.", ""])
        return "\n".join(lines)

    grouped: dict[str, list[NormalizedJob]] = defaultdict(list)
    for job in jobs:
        grouped[job.country or "Unknown"].append(job)

    lines.extend(["## Jobs", ""])
    for country in sorted(grouped):
        lines.extend([f"### {country}", ""])
        for index, job in enumerate(sorted(grouped[country], key=lambda item: item.score, reverse=True), 1):
            stack = ", ".join(job.stack) if job.stack else "stack unknown"
            city = ""
            if job.city and job.city.lower() not in job.location_raw.lower():
                city = f", {job.city}"
            lines.extend(
                [
                    f"{index}. **{job.title}** — {job.company}",
                    f"   - Location: {job.location_raw}{city}",
                    f"   - Seniority: `{job.seniority}` · Score: `{job.score}` · Workplace: `{job.workplace}`",
                    f"   - Stack: {stack}",
                    f"   - Visa/relocation: `{job.visa_relocation}`",
                    f"   - Why matched: {job.relevance_reason or 'matched frontend seniority rules'}",
                    f"   - Link: {job.canonical_url}",
                    "",
                ]
            )
    return "\n".join(lines)
