"""HTTP к dustore.ru: свой User-Agent, троттлинг, ретраи."""

from __future__ import annotations

import os
import time

import requests

BASE = "https://dustore.ru"
UA = os.getenv("UA", "kontur-jam-dashboard/0.1 (jam participant; contact: calicatura13@gmail.com)")
MIN_INTERVAL = float(os.getenv("MIN_INTERVAL", "0.7"))
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "60"))  # dustore бывает отвечает по 15+ с

_last = 0.0


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


_session = new_session()


def _throttle() -> None:
    global _last
    gap = time.monotonic() - _last
    if gap < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - gap)
    _last = time.monotonic()


def request(method: str, path: str, *, allow_redirects: bool = True, tries: int = 3,
            client: requests.Session | None = None, data: dict | None = None):
    """client — своя сессия (авторизованная), чтобы её куки не смешивались
    с анонимными от публичных страниц; троттлинг общий."""
    url = path if path.startswith("http") else BASE + path
    last_err = None
    for attempt in range(tries):
        _throttle()
        try:
            return (client or _session).request(method, url, data=data, timeout=TIMEOUT,
                                                allow_redirects=allow_redirects)
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise last_err


def get(path: str, **kw):
    return request("GET", path, **kw)


def post(path: str, **kw):
    return request("POST", path, **kw)


def get_json(path: str):
    return get(path).json()


def get_html(path: str, *, allow_redirects: bool = False):
    return get(path, allow_redirects=allow_redirects)
