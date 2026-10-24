import pytest

from app.crawler.url_normalizer import normalize_url
from app.security.url_validation import UnsafeURL, validate_public_url


def test_normalize_url_removes_fragment_default_port_and_sorts_query():
    assert normalize_url(
        "HTTPS://Example.COM:443/a/../page/?b=2&a=1#section"
    ) == "https://example.com/page/?a=1&b=2"


def test_normalize_url_resolves_relative_links():
    assert normalize_url("../contact#team", "https://example.com/docs/start") == (
        "https://example.com/contact"
    )


@pytest.mark.parametrize(
    "url",
    ["http://localhost", "http://127.0.0.1", "http://10.0.0.1", "file:///tmp/page"],
)
def test_validate_public_url_rejects_unsafe_targets(url: str):
    with pytest.raises(UnsafeURL):
        validate_public_url(url)
