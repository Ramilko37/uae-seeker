from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import httpx

from ..config import SourceConfig
from ..models import RawJob


class JobSource(ABC):
    def __init__(self, config: SourceConfig) -> None:
        self.config = config

    @abstractmethod
    async def fetch(self) -> list[RawJob]:
        raise NotImplementedError


class SampleSource(JobSource):
    async def fetch(self) -> list[RawJob]:
        jobs: list[RawJob] = []
        for index, item in enumerate(self.config.items):
            payload = dict(item)
            posted_at = payload.get("posted_at")
            if isinstance(posted_at, str):
                payload["posted_at"] = date.fromisoformat(posted_at)
            jobs.append(
                RawJob(
                    source=self.config.name,
                    source_job_id=str(index),
                    title=payload.get("title", "Untitled job"),
                    company=payload.get("company"),
                    location=payload.get("location"),
                    url=payload.get("url", f"sample://{self.config.name}/{index}"),
                    apply_url=payload.get("apply_url"),
                    description=payload.get("description"),
                    posted_at=payload.get("posted_at"),
                    raw=payload,
                )
            )
        return jobs


class RssSource(JobSource):
    async def fetch(self) -> list[RawJob]:
        if not self.config.url:
            raise RuntimeError(f"{self.config.name}: rss source requires url")
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(self.config.url)
            response.raise_for_status()
        root = ElementTree.fromstring(response.text)
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        jobs: list[RawJob] = []
        for index, item in enumerate(items):
            title = _text(item, "title") or _text(item, "{http://www.w3.org/2005/Atom}title")
            link = _text(item, "link") or _atom_link(item)
            description = _text(item, "description") or _text(item, "summary") or _text(item, "{http://www.w3.org/2005/Atom}summary")
            published = _text(item, "pubDate") or _text(item, "published") or _text(item, "{http://www.w3.org/2005/Atom}published")
            if not title or not link:
                continue
            jobs.append(
                RawJob(
                    source=self.config.name,
                    source_job_id=str(index),
                    title=title,
                    company=None,
                    location=self.config.country,
                    url=link,
                    description=description,
                    posted_at=_parse_date(published),
                    raw={"feed_url": self.config.url},
                )
            )
        return jobs


class JSearchSource(JobSource):
    async def fetch(self) -> list[RawJob]:
        api_key = os.getenv("JSEARCH_API_KEY") or os.getenv("JSEARCH_RAPIDAPI_KEY")
        if not api_key:
            return []
        host = os.getenv("JSEARCH_API_HOST", "jsearch.p.rapidapi.com")
        url = self.config.options.get("url", f"https://{host}/search")
        headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": host}
        queries = self.config.queries or ["Senior Frontend Developer"]
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for query in queries:
                response = await client.get(url, headers=headers, params={"query": query, "page": 1, "num_pages": self.config.options.get("num_pages", 1)})
                response.raise_for_status()
                for item in response.json().get("data") or []:
                    parsed = self._parse_item(item, query)
                    if parsed:
                        jobs.append(parsed)
        return jobs

    def _parse_item(self, item: dict[str, Any], query: str) -> RawJob | None:
        title = item.get("job_title") or item.get("title")
        job_url = item.get("job_apply_link") or item.get("job_google_link") or item.get("url")
        if not title or not job_url:
            return None
        location = ", ".join(str(part) for part in [item.get("job_city"), item.get("job_state"), item.get("job_country") or self.config.country] if part)
        return RawJob(
            source=self.config.name,
            source_job_id=str(item.get("job_id") or item.get("id") or "") or None,
            title=title,
            company=item.get("employer_name") or item.get("company_name"),
            location=location or self.config.country,
            url=job_url,
            apply_url=item.get("job_apply_link"),
            description=item.get("job_description"),
            posted_at=_parse_iso_date(item.get("job_posted_at_datetime_utc")),
            raw={"query": query, **item},
        )


class GreenhouseSource(JobSource):
    async def fetch(self) -> list[RawJob]:
        if not self.config.board_token:
            raise RuntimeError(f"{self.config.name}: greenhouse source requires board_token")
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.config.board_token}/jobs"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, params={"content": "true"})
            response.raise_for_status()
        jobs: list[RawJob] = []
        for item in response.json().get("jobs", []):
            offices = item.get("offices") or []
            location = ", ".join(office.get("name", "") for office in offices if office.get("name")) or self.config.country
            if item.get("title") and item.get("absolute_url"):
                jobs.append(
                    RawJob(
                        source=self.config.name,
                        source_job_id=str(item.get("id")) if item.get("id") else None,
                        title=item.get("title"),
                        company=self.config.options.get("company"),
                        location=location,
                        url=item.get("absolute_url"),
                        apply_url=item.get("absolute_url"),
                        description=item.get("content"),
                        posted_at=_parse_iso_date(item.get("updated_at")),
                        raw=item,
                    )
                )
        return jobs


class LeverSource(JobSource):
    async def fetch(self) -> list[RawJob]:
        if not self.config.site:
            raise RuntimeError(f"{self.config.name}: lever source requires site")
        url = f"https://api.lever.co/v0/postings/{self.config.site}"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, params={"mode": "json"})
            response.raise_for_status()
        jobs: list[RawJob] = []
        for item in response.json():
            title = item.get("text")
            job_url = item.get("hostedUrl") or item.get("applyUrl")
            if not title or not job_url:
                continue
            categories = item.get("categories") or {}
            description = "\n".join(part for part in [item.get("descriptionPlain"), item.get("additionalPlain")] if part)
            jobs.append(
                RawJob(
                    source=self.config.name,
                    source_job_id=item.get("id"),
                    title=title,
                    company=self.config.options.get("company"),
                    location=categories.get("location") or self.config.country,
                    url=job_url,
                    apply_url=item.get("applyUrl") or job_url,
                    description=description,
                    posted_at=_parse_millis(item.get("createdAt")),
                    raw=item,
                )
            )
        return jobs


class AshbySource(JobSource):
    async def fetch(self) -> list[RawJob]:
        if not self.config.organization:
            raise RuntimeError(f"{self.config.name}: ashby source requires organization")
        url = f"https://api.ashbyhq.com/posting-api/job-board/{self.config.organization}"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        jobs: list[RawJob] = []
        for item in response.json().get("jobs") or response.json().get("jobPostings") or []:
            title = item.get("title")
            job_url = item.get("jobUrl") or item.get("hostedUrl") or item.get("applyUrl")
            if not title or not job_url:
                continue
            jobs.append(
                RawJob(
                    source=self.config.name,
                    source_job_id=item.get("id") or item.get("jobPostingId"),
                    title=title,
                    company=self.config.options.get("company"),
                    location=item.get("locationName") or item.get("location") or self.config.country,
                    url=job_url,
                    apply_url=item.get("applyUrl") or job_url,
                    description=item.get("descriptionPlain") or item.get("descriptionHtml") or item.get("description"),
                    posted_at=_parse_iso_date(item.get("publishedDate") or item.get("updatedAt")),
                    raw=item,
                )
            )
        return jobs


SOURCE_TYPES: dict[str, type[JobSource]] = {
    "sample": SampleSource,
    "rss": RssSource,
    "jsearch": JSearchSource,
    "greenhouse": GreenhouseSource,
    "lever": LeverSource,
    "ashby": AshbySource,
}


def build_source(config: SourceConfig) -> JobSource:
    source_cls = SOURCE_TYPES.get(config.type)
    if source_cls is None:
        known = ", ".join(sorted(SOURCE_TYPES))
        raise ValueError(f"Unknown source type '{config.type}'. Known: {known}")
    return source_cls(config)


def _text(element: ElementTree.Element, tag: str) -> str | None:
    child = element.find(tag)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _atom_link(element: ElementTree.Element) -> str | None:
    link = element.find("{http://www.w3.org/2005/Atom}link")
    return None if link is None else link.attrib.get("href")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        return _parse_iso_date(value)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")[:10]).date()
    except ValueError:
        return None


def _parse_millis(value: int | None) -> date | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
