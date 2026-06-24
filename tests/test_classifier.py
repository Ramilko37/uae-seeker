from job_monitor.classifier import classify, normalize
from job_monitor.models import RawJob


def test_accepts_senior_frontend_role() -> None:
    raw = RawJob(
        source="test",
        title="Senior Frontend Engineer",
        company="Demo",
        location="Dubai, UAE",
        url="https://example.com/job/1",
        description="React TypeScript Next.js design systems. 6+ years of experience.",
    )

    result = normalize(raw, configured_country="UAE")

    assert result is not None
    assert result.seniority == "senior"
    assert result.country == "UAE"
    assert "React" in result.stack
    assert "TypeScript" in result.stack
    assert result.score >= 80


def test_rejects_junior_role() -> None:
    raw = RawJob(
        source="test",
        title="Junior Web Developer",
        company="Demo",
        location="Dubai, UAE",
        url="https://example.com/job/2",
        description="HTML CSS entry level website support.",
    )

    result = normalize(raw, configured_country="UAE")

    assert result is None


def test_detects_tech_lead() -> None:
    raw = RawJob(
        source="test",
        title="Frontend Tech Lead",
        company="Demo",
        location="Riyadh, Saudi Arabia",
        url="https://example.com/job/3",
        description="Lead React TypeScript architecture and mentor engineers.",
    )

    classification = classify(raw, configured_country="Saudi Arabia")

    assert classification.is_relevant is True
    assert classification.seniority == "tech_lead"
    assert classification.country == "Saudi Arabia"
