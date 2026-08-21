"""HTTP к dustore.ru: свой User-Agent, троттлинг, ретраи."""

from __future__ import annotations

import os
import time

import requests

BASE = "https://dustore.ru"
UA = os.getenv("UA", "kontur-jam-dashboard/0.1 (jam participant; contact: calicatura13@gmail.com)")
MIN_INTERVAL = float(os.getenv("MIN_INTERVAL", "0.7"))

_session = requests.Session()
_session.headers["User-Agent"] = UA
_last = 0.0


def _throttle() -> None:
    global _last
    gap = time.monotonic() - _last
    if gap < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - gap)
    _last = time.monotonic()


def get(path: str, *, allow_redirects: bool = True, tries: int = 3, cookies: dict | None = None):
    url = path if path.startswith("http") else BASE + path
    last_err = None
    for attempt in range(tries):
        _throttle()
        try:
            return _session.get(url, timeout=20, allow_redirects=allow_redirects, cookies=cookies)
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise last_err


def get_json(path: str):
    return get(path).json()


def get_html(path: str, *, allow_redirects: bool = False):
    return get(path, allow_redirects=allow_redirects)
