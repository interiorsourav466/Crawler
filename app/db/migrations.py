from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_compatibility_schema(engine: Engine) -> None:
    """Apply the small additive migration needed by this MVP during startup."""
    inspector = inspect(engine)
    if "crawl_runs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("crawl_runs")}
    if "max_pages" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE crawl_runs ADD COLUMN max_pages INTEGER DEFAULT 1000"))
