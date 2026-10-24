from __future__ import annotations

from posixpath import normpath
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


def normalize_url(url: str, base_url: str | None = None) -> str:
    absolute_url = urljoin(base_url, url) if base_url else url
    parsed = urlsplit(absolute_url.strip())
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower().rstrip(".")
    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = hostname
    if parsed.username or parsed.password:
        netloc = parsed.netloc.lower()
    elif port:
        netloc = f"{hostname}:{port}"

    path = normpath(parsed.path or "/")
    if not path.startswith("/"):
        path = f"/{path}"
    if parsed.path.endswith("/") and path != "/":
        path += "/"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, path, query, ""))
