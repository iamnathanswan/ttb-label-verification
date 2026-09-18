"""Per-client rate limiting (OPS-05).

The deployed prototype is a public URL with a funded API key behind it. Without a
ceiling, one script can exhaust the credit that the reviewers need to evaluate the
tool. In-process and best-effort: a single container is the whole deployment, and
a prototype does not need a shared store to bring along its own failure modes.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings


class SlidingWindowLimiter:
    """Allow N label extractions per client per window."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client: str, cost: int = 1) -> tuple[bool, int]:
        """Record `cost` units against `client`. Returns (allowed, seconds_to_wait)."""
        now = time.monotonic()
        hits = self._hits[client]
        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) + cost > self.limit:
            return False, max(1, int(self.window - (now - hits[0]))) if hits else self.window

        hits.extend([now] * cost)
        return True, 0


_limiter = SlidingWindowLimiter(settings.rate_limit_labels, settings.rate_limit_window_seconds)


def client_key(request: Request) -> str:
    """Identify the caller. Railway terminates TLS upstream, so trust its header."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(request: Request, cost: int = 1) -> None:
    """Raise 429 with a human-readable message when the caller is over the limit."""
    allowed, retry_after = _limiter.check(client_key(request), cost)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit reached: {settings.rate_limit_labels} labels per "
                f"{settings.rate_limit_window_seconds // 60} minutes. Try again in about "
                f"{retry_after} seconds."
            ),
            headers={"Retry-After": str(retry_after)},
        )
