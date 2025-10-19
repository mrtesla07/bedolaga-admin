"""In-memory rate limiter for admin actions."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from fastapi import HTTPException


class RateLimitExceeded(HTTPException):
    """Raised when rate limit is exceeded."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=429, detail=detail)


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self) -> None:
        self._buckets: Dict[Tuple[int, str], Deque[float]] = defaultdict(deque)

    def hit(self, key: Tuple[int, str], *, limit: int, period: int) -> None:
        now = time.monotonic()
        bucket = self._buckets[key]
        boundary = now - period
        while bucket and bucket[0] < boundary:
            bucket.popleft()
        if len(bucket) >= limit:
            raise RateLimitExceeded(
                "Превышен лимит операций. Повторите попытку позже."  # noqa: E501
            )
        bucket.append(now)


__all__ = ["RateLimiter", "RateLimitExceeded"]
