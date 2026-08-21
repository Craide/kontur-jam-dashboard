"""Страница /g/<id> -> карточка работы и её числовые метрики.
Вёрстка кривая (вложенные <html>), поэтому регулярки, а не DOM-парсер."""

from __future__ import annotations

import re

from . import sources

UNITS = {"КБ": 1024, "МБ": 1024 ** 2, "ГБ": 1024 ** 3}

RE_TITLE = re.compile(r'gp-title-block">\s*<h1>([^<]+)</h1>')
RE_JAM = re.compile(r'href="/jams/vote\.php\?id=(\d+)"')
RE_STAT = re.compile(r'gp-stat-val">\s*([^<]+?)\s*</div>\s*<div class="gp-stat-lbl">\s*([^<]+?)\s*<')
RE_DOWNLOADS = re.compile(r"Скачали:\s*([\d\s]+)\s*раз")
RE_SIZE = re.compile(r"Размер:\s*([\d.]+)\s*(КБ|МБ|ГБ)")
RE_STUDIO = re.compile(r'gp-dev-name">\s*([^<]+?)\s*<')
RE_STUDIO_SLUG = re.compile(r'gp-dev-card" href="/d/([^"]+)"')
RE_PRICE = re.compile(r'class="gp-price-tag[^"]*">\s*([^<]*?)\s*<')
RE_INFO = re.compile(r'gp-info-label">([^<]+)</span><span class="gp-info-val">([^<]+)<')


def parse(html: str) -> dict | None:
    """None, если это не страница игры."""
    title = RE_TITLE.search(html)
    if not title:
        return None
    info = dict(RE_INFO.findall(html))
    jam = RE_JAM.search(html)
    studio = RE_STUDIO.search(html)
    slug = RE_STUDIO_SLUG.search(html)
    price = RE_PRICE.search(html)

    metrics: dict[str, float] = {}
    dl = RE_DOWNLOADS.search(html)
    if dl:
        metrics["downloads"] = float(dl.group(1).replace(" ", ""))
    size = RE_SIZE.search(html)
    if size:
        metrics["build_bytes"] = float(size.group(1)) * UNITS[size.group(2)]
    for val, label in RE_STAT.findall(html):
        if label.startswith("Оценок"):
            metrics["ratings_count"] = float(re.sub(r"\D", "", label) or 0)
            metrics["rating_avg"] = float(val.split("/")[0])

    return {
        "title": title.group(1).strip(),
        "jam_id": int(jam.group(1)) if jam else None,
        "studio": studio.group(1) if studio else None,
        "studio_slug": slug.group(1) if slug else None,
        "price": (price.group(1).strip() or None) if price else None,
        "genre": info.get("Жанр"),
        "platforms": info.get("Платформы"),
        "languages": info.get("Языки"),
        "age": info.get("Возраст"),
        "metrics": metrics,
    }


def fetch(game_id: int) -> dict | None:
    """None, если игры нет (редирект на /explore)."""
    resp = sources.get_html(f"/g/{game_id}")
    if resp.status_code != 200:
        return None
    return parse(resp.text)
