from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

from app.crawler.robots import RobotsPolicy
from app.crawler.url_normalizer import normalize_url
from app.parser.html_parser import parse_html
from app.security.url_validation import UnsafeURL, validate_public_url
from app.seo.analyzer import analyze_seo

logger = logging.getLogger(__name__)


@dataclass
class CrawledPage:
    url: str
    depth: int
    status_code: int | None = None
    content_type: str = ""
    response_time_ms: int | None = None
    error: str | None = None
    data: dict[str, object] = field(default_factory=dict)
    seo: dict[str, object] = field(default_factory=dict)
    html_hash: str | None = None


@dataclass
class CrawlResult:
    start_url: str
    pages: list[CrawledPage]
    discovered: int


class Crawler:
    def __init__(
        self,
        *,
        user_agent: str = "SEO-Intelligence-Crawler/0.1 (+https://example.com/crawler)",
        max_pages: int = 1000,
        max_depth: int = 10,
        concurrency: int = 5,
        request_delay: float = 0.0,
        timeout: float = 15.0,
        max_response_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        self.user_agent = user_agent
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.concurrency = max(1, concurrency)
        self.request_delay = max(0.0, request_delay)
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes

    async def crawl(self, start_url: str) -> CrawlResult:
        validate_public_url(start_url)
        normalized_start = normalize_url(start_url)
        hostname = urlsplit(normalized_start).hostname
        if not hostname:
            raise UnsafeURL("Start URL must include a hostname")

        frontier: asyncio.Queue[tuple[str, int] | None] = asyncio.Queue()
        queued: set[str] = {normalized_start}
        await frontier.put((normalized_start, 0))
        pages: list[CrawledPage] = []
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            robots = RobotsPolicy(self.user_agent, client)
            lock = asyncio.Lock()

            async def worker() -> None:
                while True:
                    item = await frontier.get()
                    if item is None:
                        frontier.task_done()
                        return
                    url, depth = item
                    try:
                        page = await self._fetch_page(client, robots, url, depth, hostname)
                        async with lock:
                            pages.append(page)
                            links = page.data.get("links", []) if page.error is None else []
                            if depth < self.max_depth:
                                for link in links:
                                    target = str(link["target_url"])
                                    if (
                                        bool(link["is_internal"])
                                        and target not in queued
                                        and len(queued) < self.max_pages
                                    ):
                                        queued.add(target)
                                        await frontier.put((target, depth + 1))
                    finally:
                        frontier.task_done()

            workers = [asyncio.create_task(worker()) for _ in range(self.concurrency)]
            await frontier.join()
            for _ in workers:
                await frontier.put(None)
            await asyncio.gather(*workers)

        return CrawlResult(normalized_start, pages, len(queued))

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        robots: RobotsPolicy,
        url: str,
        depth: int,
        allowed_hostname: str,
    ) -> CrawledPage:
        page = CrawledPage(url=url, depth=depth)
        if not await robots.allowed(url):
            page.error = "Blocked by robots.txt"
            return page
        started = time.perf_counter()
        try:
            async with client.stream("GET", url) as response:
                for redirect in response.history:
                    validate_public_url(str(redirect.url))
                validate_public_url(str(response.url))
                page.status_code = response.status_code
                page.content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                page.response_time_ms = round((time.perf_counter() - started) * 1000)
                if "text/html" not in page.content_type and "application/xhtml+xml" not in page.content_type:
                    return page
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self.max_response_bytes:
                        page.error = "Response exceeded configured size limit"
                        return page
                    chunks.append(chunk)
                html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
                page.data = parse_html(html, str(response.url), allowed_hostname)
                page.seo = analyze_seo(page.data)
                page.html_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
                logger.info("url_crawled", extra={"url": url, "status": page.status_code, "duration": page.response_time_ms})
        except (httpx.HTTPError, UnsafeURL, UnicodeError) as exc:
            page.error = str(exc)
            logger.warning("url_failed", extra={"url": url, "error": page.error})
        if self.request_delay:
            await asyncio.sleep(self.request_delay)
        return page
