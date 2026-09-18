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
        self._evict(now)

        hits = self._hits[client]
        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) + cost > self.limit:
            return False, max(1, int(self.window - (now - hits[0]))) if hits else self.window

        hits.extend([now] * cost)
        return True, 0

    def _evict(self, now: float) -> None:
        """Drop buckets whose window has passed.

        Without this the map grows by one deque per distinct client key. Since the
        key derives from a client-supplied header, a caller rotating it would grow
        the map without bound — a slow leak reachable from the public endpoint.
        """
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] > self.window]
        for key in stale:
            del self._hits[key]


_limiter = SlidingWindowLimiter(settings.rate_limit_labels, settings.rate_limit_window_seconds)


def client_key(request: Request) -> str:
    """Identify the caller from behind the platform proxy.

    Proxies *append* to X-Forwarded-For, so the leftmost entry is whatever the
    caller sent and is fully forgeable — a script rotating it would get a fresh
    bucket per request and never meet the ceiling that protects the funded API
    key. The rightmost entry is the one the trusted proxy wrote, so that is the
    one used.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        entries = [part.strip() for part in forwarded.split(",") if part.strip()]
        if entries:
            return entries[-1]
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
