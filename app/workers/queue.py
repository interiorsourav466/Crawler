from __future__ import annotations

import redis
from rq import Queue

from app.config import get_settings


def get_queue() -> Queue:
    settings = get_settings()
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return Queue(connection=client)
