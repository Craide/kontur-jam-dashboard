"""Авторизация на dustore.ru для vote.php: JWT в куке auth_token, живёт 72 ч
и сам не продлевается. С DUSTORE_EMAIL/DUSTORE_PASSWORD входим через /login сами
и перелогиниваемся заранее; без них берём готовую строку DUSTORE_COOKIE из браузера."""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import requests

from . import sources

RE_CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')
REFRESH_BEFORE = timedelta(hours=1)

_client: requests.Session | None = None


def credentials() -> tuple[str, str] | None:
    email, password = os.getenv("DUSTORE_EMAIL", "").strip(), os.getenv("DUSTORE_PASSWORD", "")
    return (email, password) if email and password else None


def browser_cookies() -> dict[str, str]:
    """DUSTORE_COOKIE — строка Cookie из DevTools целиком («a=1; auth_token=eyJ…»)."""
    pairs = (p.split("=", 1) for p in os.getenv("DUSTORE_COOKIE", "").split(";") if "=" in p)
    return {k.strip(): v.strip() for k, v in pairs}


def configured() -> bool:
    return bool(credentials() or browser_cookies())


def token_expires(token: str | None) -> datetime | None:
    try:
        payload = unquote(token or "").split(".")[1]
        exp = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["exp"]
    except (IndexError, KeyError, ValueError):
        return None
    return datetime.fromtimestamp(exp, tz=timezone.utc)


def login(client: requests.Session) -> datetime | None:
    """GET /login ради csrf_token (привязан к PHPSESSID), затем POST формы.
    Банку чистим целиком, чтобы старый auth_token не задвоился с новым."""
    email, password = credentials()
    client.cookies.clear()
    page = sources.get("/login", client=client)
    csrf = RE_CSRF.search(page.text)
    if not csrf:
        raise ValueError("на /login нет csrf_token — форма входа поменялась?")
    resp = sources.post("/login", client=client, allow_redirects=False, data={
        "csrf_token": csrf.group(1), "action": "login", "backUrl": "/",
        "email": email, "password": password,
    })
    token = client.cookies.get("auth_token")
    if not token:
        raise ValueError(f"вход не удался: {resp.status_code} → {resp.headers.get('Location')}"
                         " — проверь DUSTORE_EMAIL/DUSTORE_PASSWORD")
    exp = token_expires(token)
    print(f"auth: вход выполнен, токен до {exp:%Y-%m-%d %H:%M} UTC" if exp else "auth: вход выполнен")
    return exp


def client(force_login: bool = False) -> requests.Session:
    """Одна сессия на процесс, отдельная от анонимной: её куки не смешиваются
    с теми, что оседают от публичных страниц."""
    global _client
    if _client is None:
        _client = sources.new_session()
        for k, v in browser_cookies().items():
            _client.cookies.set(k, v, domain="dustore.ru")

    exp = token_expires(_client.cookies.get("auth_token"))
    now = datetime.now(timezone.utc)
    if credentials() and (force_login or exp is None or exp - now < REFRESH_BEFORE):
        login(_client)
    elif exp and exp <= now:
        raise ValueError(f"auth_token истёк {exp:%Y-%m-%d %H:%M} UTC — обнови DUSTORE_COOKIE"
                         " или задай DUSTORE_EMAIL/DUSTORE_PASSWORD")
    return _client
