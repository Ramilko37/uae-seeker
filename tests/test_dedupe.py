from job_monitor.dedupe import make_dedupe_key, normalize_url


def test_url_normalization_strips_query_and_fragment() -> None:
    left = normalize_url("https://Example.com/jobs/123/?utm_source=linkedin&foo=bar#section")
    right = normalize_url("https://example.com/jobs/123")

    assert left == right


def test_dedupe_prefers_canonical_url() -> None:
    left = make_dedupe_key(
        title="Senior Frontend Engineer",
        company="Demo",
        location="Dubai",
        url="https://example.com/jobs/1?utm_campaign=x",
    )
    right = make_dedupe_key(
        title="Different Title",
        company="Different Company",
        location="Different Location",
        url="https://example.com/jobs/1",
    )

    assert left == right
