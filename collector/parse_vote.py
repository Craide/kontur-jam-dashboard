"""Страница голосования /jams/vote.php: баллы джема по работам.
Требует сессии. Ники голосовавших (.av-row) сознательно не собираем."""

from __future__ import annotations

import os
import re

from . import sources

RE_CARD = re.compile(r'id="card-(\d+)" data-points="(\d+)"')
RE_AGG = re.compile(r'id="pts-(\d+)">(\d+)</strong>\s*очков\s*·\s*<span id="vtr-\d+">(\d+)</span>')
RE_TITLE = re.compile(r'id="card-(\d+)".*?class="g-title"[^>]*>\s*([^<]+?)\s*</a>', re.S)
RE_PLAYED = re.compile(r'id="vote-row-(\d+)" data-played="(\d+)"')
RE_PENDING = re.compile(r'id="pcard-(\d+)"')
RE_REMAINING = re.compile(r'id="remaining">(\d+)</strong>\s*/\s*(\d+)')


def parse(html: str) -> dict:
    """{games: {id: {...}}, jam: {метрики джема}}. ValueError, если мы разлогинены."""
    if 'class="games-grid"' not in html or 'id="card-' not in html:
        raise ValueError("страница голосования без данных — сессия протухла?")

    games: dict[int, dict] = {}
    for gid, mine in RE_CARD.findall(html):
        games[int(gid)] = {"my_points": float(mine)}
    for gid, pts, voters in RE_AGG.findall(html):
        games.setdefault(int(gid), {}).update(jam_points=float(pts), jam_voters=float(voters))
    for gid, played in RE_PLAYED.findall(html):
        games.setdefault(int(gid), {})["played"] = float(played)

    titles = {int(g): t for g, t in RE_TITLE.findall(html)}
    pending = [int(g) for g in RE_PENDING.findall(html)]
    rem = RE_REMAINING.search(html)

    jam = {
        "vote.games_live": float(len(games)),
        "vote.games_pending": float(len(pending)),
        "vote.points_total": sum(g.get("jam_points", 0) for g in games.values()),
        "vote.votes_total": sum(g.get("jam_voters", 0) for g in games.values()),
        "vote.games_played_by_me": sum(g.get("played", 0) for g in games.values()),
    }
    if rem:
        jam["vote.my_remaining"] = float(rem.group(1))
        jam["vote.budget"] = float(rem.group(2))
    return {"games": games, "titles": titles, "pending": pending, "jam": jam}


def fetch(jam_id: int, session: str | None = None) -> str:
    """HTML страницы голосования по куке PHPSESSID."""
    sid = session or os.getenv("DUSTORE_SESSION")
    if not sid:
        raise RuntimeError("нет DUSTORE_SESSION — положи PHPSESSID в .env")
    resp = sources.get(f"/jams/vote.php?id={jam_id}", allow_redirects=False,
                       cookies={"PHPSESSID": sid})
    if resp.status_code != 200:
        raise ValueError(f"вместо страницы {resp.status_code} → {resp.headers.get('Location')}")
    return resp.text
