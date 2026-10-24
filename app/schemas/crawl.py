from datetime import datetime

from pydantic import BaseModel, Field


class CrawlResponse(BaseModel):
    id: int
    project_id: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    pages_discovered: int
    pages_crawled: int
    pages_failed: int
    max_pages: int


class CrawlCreate(BaseModel):
    max_pages: int = Field(default=1000, ge=1, le=1000)
