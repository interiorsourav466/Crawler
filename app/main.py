from __future__ import annotations

from datetime import datetime, timezone
import csv
import io
import json
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crawler.url_normalizer import normalize_url
from app.config import get_settings
from app.db.base import Base
from app.db.migrations import ensure_compatibility_schema
from app.db.session import engine, get_db
from app.models import CrawlRun, CrawlStatus, Page, Project
from app.schemas.crawl import CrawlCreate, CrawlResponse
from app.schemas.project import ProjectCreate, ProjectResponse
from app.security.url_validation import UnsafeURL, validate_public_url
from app.workers.queue import get_queue

app = FastAPI(title='SEO Crawler API', version='0.1.0')
Base.metadata.create_all(bind=engine)
ensure_compatibility_schema(engine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in get_settings().cors_origins.split(',') if origin.strip()],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)


class JobCreate(BaseModel):
    domain: HttpUrl = Field(..., description='Target URL to crawl')
    max_pages: int = Field(default=25, ge=1, le=500)


class JobResponse(BaseModel):
    id: str
    domain: str
    status: str
    created_at: datetime
    max_pages: int
    seo_score: int | None = None


jobs: dict[str, JobResponse] = {}


@app.get('/health')
def health_check() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/jobs', response_model=JobResponse, status_code=202)
def create_job(payload: JobCreate) -> JobResponse:
    job_id = f"job-{len(jobs) + 1:04d}"
    created = JobResponse(
        id=job_id,
        domain=str(payload.domain).rstrip('/'),
        status='queued',
        created_at=datetime.now(timezone.utc),
        max_pages=payload.max_pages,
        seo_score=None,
    )
    jobs[job_id] = created

    try:
        queue = get_queue()
        queue.enqueue('app.workers.crawl_job.run_crawl_job', created.domain, created.max_pages)
    except Exception:
        # Graceful fallback when Redis is not available during local development or tests.
        pass

    return created


@app.get('/jobs/{job_id}', response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    return job


@app.get('/jobs')
def list_jobs() -> dict[str, Any]:
    return {'jobs': list(jobs.values())}


@app.post('/api/projects', response_model=ProjectResponse, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    start_url = normalize_url(str(payload.start_url))
    try:
        validate_public_url(start_url)
    except UnsafeURL as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    project = Project(
        name=payload.name.strip(),
        domain=urlsplit(start_url).hostname or '',
        start_url=start_url,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get('/api/projects', response_model=list[ProjectResponse])
def get_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@app.get('/api/projects/{project_id}', response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    return project


@app.delete('/api/projects/{project_id}', status_code=204, response_model=None)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> None:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    db.delete(project)
    db.commit()


@app.post('/api/projects/{project_id}/crawl', response_model=CrawlResponse, status_code=202)
def start_crawl(project_id: int, payload: CrawlCreate | None = None, db: Session = Depends(get_db)) -> CrawlRun:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    crawl = CrawlRun(
        project_id=project.id,
        status=CrawlStatus.queued,
        max_pages=payload.max_pages if payload else get_settings().max_pages,
    )
    db.add(crawl)
    db.commit()
    db.refresh(crawl)
    try:
        get_queue().enqueue('app.workers.crawl_job.run_crawl_run', crawl.id)
    except Exception:
        # The run remains queued and can be picked up when Redis is available.
        pass
    return crawl


@app.get('/api/crawls/{crawl_id}', response_model=CrawlResponse)
def get_crawl(crawl_id: int, db: Session = Depends(get_db)) -> CrawlRun:
    crawl = db.get(CrawlRun, crawl_id)
    if not crawl:
        raise HTTPException(status_code=404, detail='Crawl not found')
    return crawl


@app.get('/api/projects/{project_id}/latest-crawl', response_model=CrawlResponse)
def get_latest_crawl(project_id: int, db: Session = Depends(get_db)) -> CrawlRun:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail='Project not found')
    crawl = db.scalars(
        select(CrawlRun).where(CrawlRun.project_id == project_id).order_by(CrawlRun.id.desc())
    ).first()
    if not crawl:
        raise HTTPException(status_code=404, detail='Crawl not found')
    return crawl


@app.post('/api/crawls/{crawl_id}/stop', response_model=CrawlResponse)
def stop_crawl(crawl_id: int, db: Session = Depends(get_db)) -> CrawlRun:
    crawl = db.get(CrawlRun, crawl_id)
    if not crawl:
        raise HTTPException(status_code=404, detail='Crawl not found')
    if crawl.status in {CrawlStatus.queued, CrawlStatus.running, CrawlStatus.paused}:
        crawl.status = CrawlStatus.stopped
        db.commit()
        db.refresh(crawl)
    return crawl


@app.get('/api/crawls/{crawl_id}/pages')
def get_crawl_pages(crawl_id: int, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    if not db.get(CrawlRun, crawl_id):
        raise HTTPException(status_code=404, detail='Crawl not found')
    pages = db.scalars(select(Page).where(Page.crawl_run_id == crawl_id).order_by(Page.id)).all()
    return [
        {
            'id': page.id,
            'url': page.url,
            'status_code': page.status_code,
            'title': page.title,
            'h1_count': page.h1_count,
            'word_count': page.word_count,
            'seo_score': page.seo_score,
            'error': page.error,
        }
        for page in pages
    ]


@app.get('/api/pages/{page_id}')
def get_page(page_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    page = db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail='Page not found')
    return {
        'id': page.id,
        'url': page.url,
        'status_code': page.status_code,
        'content_type': page.content_type,
        'response_time_ms': page.response_time_ms,
        'seo_score': page.seo_score,
        'error': page.error,
        'seo': {
            'title': page.title,
            'meta_description': page.meta_description,
            'canonical': page.canonical_url,
            'robots': page.robots_directive,
            'word_count': page.word_count,
            'headings': {'h1': page.h1_count, 'h2': page.h2_count},
            'images': {'total': page.image_count, 'missing_alt': page.images_missing_alt},
        },
    }


@app.get('/api/projects/{project_id}/export/json')
def export_project_json(project_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    crawls = db.scalars(select(CrawlRun).where(CrawlRun.project_id == project_id).order_by(CrawlRun.id)).all()
    pages = db.scalars(
        select(Page).join(CrawlRun).where(CrawlRun.project_id == project_id).order_by(Page.id)
    ).all()
    payload = {
        'project': {'id': project.id, 'name': project.name, 'domain': project.domain, 'start_url': project.start_url},
        'crawl': [
            {
                'id': crawl.id,
                'status': crawl.status.value,
                'pages_discovered': crawl.pages_discovered,
                'pages_crawled': crawl.pages_crawled,
                'pages_failed': crawl.pages_failed,
            }
            for crawl in crawls
        ],
        'pages': [
            {
                'id': page.id,
                'url': page.url,
                'status_code': page.status_code,
                'title': page.title,
                'meta_description': page.meta_description,
                'seo_score': page.seo_score,
                'error': page.error,
            }
            for page in pages
        ],
    }
    body = json.dumps(payload, ensure_ascii=True).encode('utf-8')
    return StreamingResponse(io.BytesIO(body), media_type='application/json', headers={
        'Content-Disposition': f'attachment; filename="project-{project_id}.json"',
    })


@app.get('/api/projects/{project_id}/export/csv')
def export_project_csv(project_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail='Project not found')
    pages = db.scalars(
        select(Page).join(CrawlRun).where(CrawlRun.project_id == project_id).order_by(Page.id)
    ).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'url', 'status_code', 'title', 'meta_description', 'seo_score', 'error'])
    for page in pages:
        writer.writerow([page.id, page.url, page.status_code, page.title, page.meta_description, page.seo_score, page.error])
    return StreamingResponse(iter([output.getvalue().encode('utf-8')]), media_type='text/csv', headers={
        'Content-Disposition': f'attachment; filename="project-{project_id}.csv"',
    })
