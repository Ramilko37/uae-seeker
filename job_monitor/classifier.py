from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .dedupe import make_dedupe_key
from .models import NormalizedJob, RawJob, Seniority, Workplace

STACK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "TypeScript": ("typescript", " ts "),
    "JavaScript": ("javascript", " js "),
    "React": ("react",),
    "Next.js": ("next.js", "nextjs"),
    "Angular": ("angular",),
    "Vue": ("vue", "vue.js"),
    "Redux": ("redux", "zustand", "mobx"),
    "GraphQL": ("graphql", "apollo"),
    "HTML/CSS": ("html", "css", "sass", "scss", "tailwind"),
    "Design Systems": ("design system", "storybook", "component library"),
    "Web Performance": ("web performance", "core web vitals"),
    "Micro Frontends": ("micro frontend", "module federation"),
    "Node.js": ("node.js", "nodejs"),
}

FRONTEND_WORDS = (
    "frontend",
    "front-end",
    "front end",
    "ui engineer",
    "web engineer",
    "react",
    "angular",
    "vue",
    "next.js",
    "nextjs",
)
EXCLUDE_WORDS = ("junior", "intern", "internship", "graduate", "trainee", "entry level", "middle", "mid-level")
CITY_HINTS = [
    ("Dubai", "UAE", ("dubai",)),
    ("Abu Dhabi", "UAE", ("abu dhabi",)),
    ("Sharjah", "UAE", ("sharjah",)),
    ("Riyadh", "Saudi Arabia", ("riyadh",)),
    ("Jeddah", "Saudi Arabia", ("jeddah",)),
    ("Dammam", "Saudi Arabia", ("dammam",)),
    ("Singapore", "Singapore", ("singapore",)),
    ("Kuala Lumpur", "Malaysia", ("kuala lumpur", "malaysia")),
    ("Jakarta", "Indonesia", ("jakarta", "indonesia")),
    ("Ho Chi Minh City", "Vietnam", ("ho chi minh", "vietnam")),
    ("Bangkok", "Thailand", ("bangkok", "thailand")),
    ("Manila", "Philippines", ("manila", "philippines")),
    ("Limassol", "Cyprus", ("limassol",)),
    ("Nicosia", "Cyprus", ("nicosia",)),
    ("Larnaca", "Cyprus", ("larnaca",)),
]


@dataclass(frozen=True)
class Classification:
    seniority: Seniority
    stack: list[str]
    workplace: Workplace
    score: int
    is_relevant: bool
    reason: str
    city: str | None
    country: str
    visa_relocation: str


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def detect_seniority(title: str, description: str) -> Seniority:
    text = f"{title} {description}".lower()
    title_lower = title.lower()
    if "tech lead" in text or "technical lead" in text:
        return "tech_lead"
    if "principal" in title_lower:
        return "principal"
    if "staff" in title_lower:
        return "staff"
    if "lead" in text or "team lead" in text:
        return "lead"
    if "senior" in text or " sr " in f" {text} " or "5+ years" in text or "6+ years" in text:
        return "senior"
    return "unknown"


def detect_stack(text: str) -> list[str]:
    lower = f" {text.lower()} "
    return [label for label, words in STACK_KEYWORDS.items() if has_any(lower, words)]


def detect_workplace(text: str) -> Workplace:
    lower = text.lower()
    if "remote" in lower or "work from home" in lower:
        return "remote"
    if "hybrid" in lower:
        return "hybrid"
    if "onsite" in lower or "on-site" in lower or "in office" in lower:
        return "onsite"
    return "unknown"


def detect_location(location: str, configured_country: str | None = None) -> tuple[str | None, str]:
    lower = location.lower()
    for city, country, hints in CITY_HINTS:
        if has_any(lower, hints):
            return city, country
    if configured_country:
        return None, configured_country
    if "uae" in lower or "united arab emirates" in lower:
        return None, "UAE"
    if "saudi" in lower or "ksa" in lower:
        return None, "Saudi Arabia"
    if "cyprus" in lower:
        return None, "Cyprus"
    return None, "Unknown"


def detect_relocation(text: str) -> str:
    lower = text.lower()
    if "no relocation" in lower or "no visa sponsorship" in lower:
        return "no"
    if "relocation" in lower or "visa sponsorship" in lower or "visa support" in lower:
        return "yes"
    return "unknown"


def classify(raw: RawJob, configured_country: str | None = None) -> Classification:
    title = clean_text(raw.title)
    description = clean_text(raw.description)
    location = clean_text(raw.location)
    text = f"{title} {description} {location}"
    lower_text = text.lower()
    lower_title = title.lower()

    seniority = detect_seniority(title, description)
    stack = detect_stack(text)
    workplace = detect_workplace(text)
    city, country = detect_location(location, configured_country)
    visa_relocation = detect_relocation(text)

    frontend_in_title = has_any(lower_title, FRONTEND_WORDS)
    frontend_in_text = has_any(lower_text, FRONTEND_WORDS) or bool(stack)
    excluded = has_any(lower_title, EXCLUDE_WORDS) and seniority == "unknown"

    score = 0
    reasons: list[str] = []
    if frontend_in_title:
        score += 45
        reasons.append("frontend keyword in title")
    elif frontend_in_text:
        score += 25
        reasons.append("frontend stack in description")
    if seniority != "unknown":
        score += 30
        reasons.append(f"seniority={seniority}")
    if stack:
        score += min(20, len(stack) * 5)
        reasons.append("stack=" + ", ".join(stack[:5]))
    if country != "Unknown":
        score += 5
    if excluded:
        score -= 50
        reasons.append("excluded junior/mid/intern title")

    is_relevant = score >= 55 and not excluded and seniority != "unknown" and frontend_in_text
    return Classification(
        seniority=seniority,
        stack=stack,
        workplace=workplace,
        score=max(0, min(score, 100)),
        is_relevant=is_relevant,
        reason="; ".join(reasons),
        city=city,
        country=country,
        visa_relocation=visa_relocation,
    )


def normalize(raw: RawJob, configured_country: str | None = None) -> NormalizedJob | None:
    classification = classify(raw, configured_country=configured_country)
    if not classification.is_relevant:
        return None

    company = clean_text(raw.company) or "Unknown company"
    location = clean_text(raw.location) or classification.country
    now = datetime.now(timezone.utc)
    return NormalizedJob(
        dedupe_key=make_dedupe_key(raw.title, company, location, raw.apply_url or raw.url),
        source=raw.source,
        source_job_id=raw.source_job_id,
        title=clean_text(raw.title),
        company=company,
        location_raw=location,
        country=classification.country,
        city=classification.city,
        workplace=classification.workplace,
        seniority=classification.seniority,
        stack=classification.stack,
        visa_relocation=classification.visa_relocation,  # type: ignore[arg-type]
        description=clean_text(raw.description) or None,
        canonical_url=raw.url,
        apply_url=raw.apply_url,
        posted_at=raw.posted_at,
        first_seen_at=now,
        last_seen_at=now,
        score=classification.score,
        relevance_reason=classification.reason,
    )
