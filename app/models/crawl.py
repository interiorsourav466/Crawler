from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CrawlStatus(str, enum.Enum):
    queued = "QUEUED"
    running = "RUNNING"
    paused = "PAUSED"
    completed = "COMPLETED"
    failed = "FAILED"
    stopped = "STOPPED"


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(255), index=True)
    start_url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    crawl_runs: Mapped[list[CrawlRun]] = relationship(back_populates="project", cascade="all, delete-orphan")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[CrawlStatus] = mapped_column(Enum(CrawlStatus), default=CrawlStatus.queued)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pages_discovered: Mapped[int] = mapped_column(Integer, default=0)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, default=0)
    max_pages: Mapped[int] = mapped_column(Integer, default=1000)
    project: Mapped[Project] = relationship(back_populates="crawl_runs")
    pages: Mapped[list[Page]] = relationship(back_populates="crawl_run", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("crawl_run_id", "normalized_url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    crawl_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    normalized_url: Mapped[str] = mapped_column(String(2048), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(120))
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text, default="")
    meta_description: Mapped[str] = mapped_column(Text, default="")
    canonical_url: Mapped[str] = mapped_column(String(2048), default="")
    robots_directive: Mapped[str] = mapped_column(String(500), default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    h1_count: Mapped[int] = mapped_column(Integer, default=0)
    h2_count: Mapped[int] = mapped_column(Integer, default=0)
    internal_link_count: Mapped[int] = mapped_column(Integer, default=0)
    external_link_count: Mapped[int] = mapped_column(Integer, default=0)
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    images_missing_alt: Mapped[int] = mapped_column(Integer, default=0)
    html_hash: Mapped[str | None] = mapped_column(String(64))
    seo_score: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    crawled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    crawl_run: Mapped[CrawlRun] = relationship(back_populates="pages")
    links: Mapped[list[Link]] = relationship(back_populates="source_page", cascade="all, delete-orphan")
    issues: Mapped[list[Issue]] = relationship(back_populates="page", cascade="all, delete-orphan")
    structured_data: Mapped[list[StructuredData]] = relationship(back_populates="page", cascade="all, delete-orphan")


class Link(Base):
    __tablename__ = "links"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    target_url: Mapped[str] = mapped_column(String(2048))
    anchor_text: Mapped[str] = mapped_column(Text, default="")
    rel: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    source_page: Mapped[Page] = relationship(back_populates="links")


class Issue(Base):
    __tablename__ = "seo_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    issue_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    page: Mapped[Page] = relationship(back_populates="issues")


class StructuredData(Base):
    __tablename__ = "structured_data"
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    schema_type: Mapped[str] = mapped_column(String(255), default="")
    json_data: Mapped[dict] = mapped_column(JSON)
    page: Mapped[Page] = relationship(back_populates="structured_data")


class CrawlStatistic(Base):
    __tablename__ = "crawl_statistics"
    id: Mapped[int] = mapped_column(primary_key=True)
    crawl_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id", ondelete="CASCADE"), unique=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
