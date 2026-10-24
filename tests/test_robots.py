import httpx
import pytest

from app.crawler.robots import RobotsPolicy


@pytest.mark.asyncio
async def test_missing_robots_file_allows_crawling():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        policy = RobotsPolicy("SEO-Intelligence-Crawler/0.1", client)
        assert await policy.allowed("https://example.com/") is True
