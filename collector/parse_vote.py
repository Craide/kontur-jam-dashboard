"""Страница голосования /jams/vote.php: баллы джема по работам.
Требует авторизации (см. auth.py). Ники голосовавших (.jv-vrow) и всё личное владельца
сессии (свои баллы, открытое/оценённое, остаток бюджета) сознательно не собираем.
Из списка «кто голосовал» берём только сумму баллов строк с 🏅 (эксперты джема) —
сами ники не покидают parse().

Вёрстка jv-* (с сентября 2026): <article class="jv-card" id="card-N">, внутри
.jv-name и <b id="pts-N">очки</b> · <span id="vtr-N">голоса</span>; работы на
проверке — <article class="jv-card pending"> без id. Очки и голоса ищем по id,
а не по подписям вокруг: подписи («очков» → «очк.») уже менялись."""

from __future__ import annotations

import re

from . import auth, sources

# сервер пишет атрибуты карточки по одному на строку, браузер при сохранении — в одну
RE_CARD = re.compile(r'<article\s[^>]*?\bid="card-(\d+)"')
RE_PTS = re.compile(r'id="pts-(\d+)">(\d+)<')
RE_VTR = re.compile(r'id="vtr-(\d+)">(\d+)<')
RE_TITLE = re.compile(r'id="card-(\d+)".*?class="jv-name"[^>]*>\s*([^<]+?)\s*<', re.S)
RE_PENDING = re.compile(r'<article\s+class="jv-card pending"')
# список «кто голосовал»: <div class="jv-votes" id="av-N"> из строк ник/баллы
RE_VOTES = re.compile(r'id="av-(\d+)"[^>]*>(.*?)(?=id="av-\d+"|<article\b|$)', re.S)
RE_VROW = re.compile(r'class="jv-vrow"[^>]*>\s*<span>([^<]*)</span>\s*<span>(\d+)</span>')
EXPERT_MARKS = ("🏅", "&#127941;", "&#x1F3C5;", "&#x1f3c5;")


def expert_points(html: str, games: dict[int, dict]) -> None:
    """expert_points/expert_voters в метрики работ. Работу пропускаем, если число
    строк в списке не сходится со счётчиком голосов — лучше пусто, чем неверно."""
    blocks = {int(gid): RE_VROW.findall(body) for gid, body in RE_VOTES.findall(html)}
    if not blocks:
        return  # списков нет вовсе — вёрстка поменялась, нули не пишем
    for gid, m in games.items():
        rows = blocks.get(gid, [])
        if len(rows) != m["jam_voters"]:
            continue
        experts = [int(pts) for nick, pts in rows if any(mark in nick for mark in EXPERT_MARKS)]
        m["expert_points"], m["expert_voters"] = float(sum(experts)), float(len(experts))


def parse(html: str) -> dict:
    """{games: {id: {...}}, titles: {id: название}, jam: {метрики джема}}.
    ValueError, если мы разлогинены или вёрстка снова поменялась."""
    if 'id="gamesGrid"' not in html or not RE_CARD.search(html):
        raise ValueError("страница голосования без данных — разлогинило или вёрстка поменялась?")

    games: dict[int, dict] = {int(gid): {} for gid in RE_CARD.findall(html)}
    for gid, pts in RE_PTS.findall(html):
        games.setdefault(int(gid), {})["jam_points"] = float(pts)
    for gid, voters in RE_VTR.findall(html):
        games.setdefault(int(gid), {})["jam_voters"] = float(voters)
    missing = [gid for gid, m in games.items() if "jam_points" not in m or "jam_voters" not in m]
    if missing:
        raise ValueError(f"у работ {missing[:5]} нет очков/голосов — вёрстка поменялась?")
    expert_points(html, games)

    titles = {int(g): t for g, t in RE_TITLE.findall(html)}
    jam = {
        "vote.games_live": float(len(games)),
        "vote.games_pending": float(len(RE_PENDING.findall(html))),
        "vote.points_total": sum(g["jam_points"] for g in games.values()),
        "vote.votes_total": sum(g["jam_voters"] for g in games.values()),
    }
    return {"games": games, "titles": titles, "jam": jam}


def fetch(jam_id: int) -> str:
    """HTML страницы голосования под авторизацией. Если сервер всё же отправил
    на /login (токен отозван раньше срока), при наличии пароля входим заново
    и пробуем ещё раз."""
    for attempt in range(2):
        resp = sources.get(f"/jams/vote.php?id={jam_id}", allow_redirects=False,
                           client=auth.client(force_login=attempt > 0))
        if resp.status_code == 200:
            return resp.text
        if not auth.credentials():
            break
    raise ValueError(f"вместо страницы {resp.status_code} → {resp.headers.get('Location')}"
                     " — авторизация не прошла")
