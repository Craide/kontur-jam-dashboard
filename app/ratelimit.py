"""Лимит частоты запросов к /api по IP: токенное ведро, RATE_RPS в секунду с запасом RATE_BURST."""

from __future__ import annotations

import os
import time

RPS = float(os.getenv("RATE_RPS", "5"))
BURST = float(os.getenv("RATE_BURST", "20"))
MAX_TRACKED = 10_000

_buckets: dict[str, tuple[float, float]] = {}


def client_ip(request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def allow(ip: str) -> bool:
    now = time.monotonic()
    tokens, last = _buckets.get(ip, (BURST, now))
    tokens = min(BURST, tokens + (now - last) * RPS)
    if len(_buckets) > MAX_TRACKED:
        _prune(now)
    if tokens < 1:
        _buckets[ip] = (tokens, now)
        return False
    _buckets[ip] = (tokens - 1, now)
    return True


def _prune(now: float) -> None:
    """Чистим тех, чьё ведро давно полное — они всё равно начнут с нуля."""
    full_after = BURST / RPS
    for ip in [k for k, (_, last) in _buckets.items() if now - last > full_after]:
        _buckets.pop(ip, None)
