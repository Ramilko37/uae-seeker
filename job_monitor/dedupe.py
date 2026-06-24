from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"[^a-z0-9+.#]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def make_dedupe_key(title: str, company: str, location: str, url: str | None = None) -> str:
    canonical_url = normalize_url(url)
    if canonical_url:
        payload = f"url:{canonical_url}"
    else:
        payload = "|".join([normalize_text(company), normalize_text(title), normalize_text(location)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
