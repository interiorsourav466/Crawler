from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    app_env: str = 'development'
    redis_url: str = 'redis://localhost:6379/0'
    database_url: str = 'sqlite:///./seo_crawler.db'
    crawler_user_agent: str = 'SEO-Intelligence-Crawler/0.1 (+https://example.com/crawler)'
    max_pages: int = 1000
    max_depth: int = 10
    concurrency: int = 5
    request_timeout: float = 15.0
    request_delay: float = 0.0
    max_response_bytes: int = 5 * 1024 * 1024
    cors_origins: str = 'http://localhost:3000,http://localhost:3001'


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv('APP_ENV', 'development'),
        redis_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        database_url=os.getenv('DATABASE_URL', 'sqlite:///./seo_crawler.db'),
        crawler_user_agent=os.getenv('CRAWLER_USER_AGENT', Settings.model_fields['crawler_user_agent'].default),
        max_pages=int(os.getenv('MAX_PAGES', '1000')),
        max_depth=int(os.getenv('MAX_DEPTH', '10')),
        concurrency=int(os.getenv('CONCURRENCY', '5')),
        request_timeout=float(os.getenv('REQUEST_TIMEOUT', '15')),
        request_delay=float(os.getenv('REQUEST_DELAY', '0')),
        max_response_bytes=int(os.getenv('MAX_RESPONSE_BYTES', str(5 * 1024 * 1024))),
        cors_origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:3001'),
    )
