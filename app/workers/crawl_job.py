from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.crawler.engine import Crawler
from app.crawler.url_normalizer import normalize_url
from app.db.session import SessionLocal
from app.models import CrawlStatus, Issue, Link, Page, StructuredData

from app.models import CrawlRun
from app.services.seo import calculate_seo_score, extract_seo_data


def run_crawl_job(domain: str, max_pages: int = 25) -> dict[str, Any]:
    result = asyncio.run(
        Crawler(
            max_pages=max_pages,
            max_depth=get_settings().max_depth,
            concurrency=get_settings().concurrency,
            request_delay=get_settings().request_delay,
            timeout=get_settings().request_timeout,
            max_response_bytes=get_settings().max_response_bytes,
            user_agent=get_settings().crawler_user_agent,
        ).crawl(domain)
    )
    first_page = result.pages[0] if result.pages else None
    return {
        'domain': domain,
        'status': 'completed',
        'page_count': len(result.pages),
        'max_pages': max_pages,
        'seo_score': first_page.seo.get('score') if first_page else None,
        'data': first_page.data if first_page else {},
    }


def run_crawl_run(crawl_id: int) -> None:
    db = SessionLocal()
    crawl = db.get(CrawlRun, crawl_id)
    if not crawl or crawl.status == CrawlStatus.stopped:
        db.close()
        return
    crawl.status = CrawlStatus.running
    crawl.started_at = datetime.now(timezone.utc)
    db.commit()
    try:
        project = crawl.project
        settings = get_settings()
        result = asyncio.run(
            Crawler(
                user_agent=settings.crawler_user_agent,
                max_pages=crawl.max_pages,
                max_depth=settings.max_depth,
                concurrency=settings.concurrency,
                request_delay=settings.request_delay,
                timeout=settings.request_timeout,
                max_response_bytes=settings.max_response_bytes,
            ).crawl(project.start_url)
        )
        crawl.pages_discovered = result.discovered
        crawl.pages_crawled = len(result.pages)
        crawl.pages_failed = sum(page.error is not None for page in result.pages)
        stored_urls: set[str] = set()
        for crawled in result.pages:
            normalized_url = normalize_url(crawled.url)
            if normalized_url in stored_urls:
                continue
            stored_urls.add(normalized_url)
            data = crawled.data
            seo = crawled.seo
            page = Page(
                crawl_run_id=crawl.id,
                url=crawled.url,
                normalized_url=normalized_url,
                status_code=crawled.status_code,
                content_type=crawled.content_type,
                response_time_ms=crawled.response_time_ms,
                title=str(data.get('title', '')),
                meta_description=str(data.get('meta_description', '')),
                canonical_url=str(data.get('canonical', '')),
                robots_directive=str(data.get('robots', '')),
                word_count=int(data.get('word_count', 0)),
                h1_count=len(data.get('headings', {}).get('h1', [])),
                h2_count=len(data.get('headings', {}).get('h2', [])),
                internal_link_count=sum(link['is_internal'] for link in data.get('links', [])),
                external_link_count=sum(not link['is_internal'] for link in data.get('links', [])),
                image_count=len(data.get('images', [])),
                images_missing_alt=int(seo.get('missing_alt', 0)),
                html_hash=crawled.html_hash,
                seo_score=seo.get('score'),
                error=crawled.error,
            )
            db.add(page)
            db.flush()
            for link in data.get('links', []):
                db.add(Link(source_page_id=page.id, **link, is_external=not link['is_internal']))
            for issue in seo.get('issues', []):
                db.add(Issue(page_id=page.id, **issue))
            for structured in data.get('structured_data', []):
                schema_type = structured.get('@type', '') if isinstance(structured, dict) else ''
                db.add(StructuredData(page_id=page.id, schema_type=str(schema_type), json_data=structured))
        crawl.status = CrawlStatus.stopped if crawl.status == CrawlStatus.stopped else CrawlStatus.completed
        crawl.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        crawl = db.get(CrawlRun, crawl_id)
        if crawl is None:
            db.close()
            raise
        crawl.status = CrawlStatus.failed
        crawl.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise
    finally:
        db.close()
