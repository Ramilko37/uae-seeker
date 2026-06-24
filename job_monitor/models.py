from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Seniority = Literal["senior", "staff", "principal", "lead", "tech_lead", "unknown"]
Workplace = Literal["remote", "hybrid", "onsite", "unknown"]


class RawJob(BaseModel):
    """Job shape emitted by source connectors before normalization."""

    source: str
    title: str
    company: str | None = None
    location: str | None = None
    url: str
    apply_url: str | None = None
    source_job_id: str | None = None
    description: str | None = None
    posted_at: date | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "source", "url")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class NormalizedJob(BaseModel):
    """Canonical job record saved to storage and shown in the digest."""

    dedupe_key: str
    source: str
    source_job_id: str | None = None
    title: str
    company: str
    location_raw: str
    country: str
    city: str | None = None
    workplace: Workplace = "unknown"
    seniority: Seniority = "unknown"
    role_family: str = "frontend"
    stack: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    visa_relocation: Literal["yes", "no", "unknown"] = "unknown"
    description: str | None = None
    canonical_url: str
    apply_url: str | None = None
    posted_at: date | None = None
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["active", "closed", "stale"] = "active"
    score: int = 0
    relevance_reason: str = ""


class CollectionStats(BaseModel):
    sources_enabled: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    raw_seen: int = 0
    accepted: int = 0
    rejected: int = 0
    new_jobs: int = 0
    updated_jobs: int = 0
    errors: list[str] = Field(default_factory=list)
