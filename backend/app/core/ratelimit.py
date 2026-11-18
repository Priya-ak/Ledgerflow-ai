"""Minimal in-process sliding-window rate limiter.

Adequate for a single-process MVP. For multiple workers/instances, replace
with a shared store (e.g. Postgres or Redis) behind the same interface.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import TooManyRequests


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self.enabled = True

    def check(self, key: str, limit: int, window_s: int) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                raise TooManyRequests("Too many requests. Please wait and try again.")
            q.append(now)


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """Real client address.

    With TRUSTED_PROXY_HOPS=N, the N right-most X-Forwarded-For entries were added by
    our own proxies, so the client is the entry just before them. Left-most values are
    client-controlled and are never trusted (prevents rate-limit bypass by spoofing).
    """
    from app.core.config import settings

    peer = request.client.host if request.client else "unknown"
    hops = settings.TRUSTED_PROXY_HOPS
    if hops <= 0:
        return peer
    chain = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if len(chain) >= hops:
        return chain[-hops]
    return chain[0] if chain else peer


def rate_limit(name: str, limit: int, window_s: int):
    def dep(request: Request) -> None:
        limiter.check(f"{name}:{client_ip(request)}", limit, window_s)
    return dep
