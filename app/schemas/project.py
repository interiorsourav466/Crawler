from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    start_url: AnyHttpUrl


class ProjectResponse(BaseModel):
    id: int
    name: str
    domain: str
    start_url: str
    created_at: datetime
