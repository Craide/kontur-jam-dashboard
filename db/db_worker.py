"""Хранилище: SQLAlchemy Core поверх Postgres, адрес в DB_URL.
Метрики в длинном формате (ts, scope, key, value), пишутся только при изменении."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))

from sqlalchemy import (
    Column, DateTime, Float, Integer, MetaData, String, Table, Text,
    create_engine, func, insert, select, update,
)

metadata = MetaData()

jam = Table(
    "jam", metadata,
    Column("jam_id", Integer, primary_key=True),
    Column("date_in", DateTime(timezone=True)),
    Column("date_up", DateTime(timezone=True)),
    Column("title", Text),
    Column("status", Text),
    Column("jam_start", Text),
    Column("jam_end", Text),
    Column("voting_start", Text),
    Column("voting_end", Text),
)

# ключи вида overview.participants, activity.votes_total, tech.engines.Unity
jam_metric = Table(
    "jam_metric", metadata,
    Column("id", Integer, primary_key=True),
    Column("date_in", DateTime(timezone=True), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False, index=True),
    Column("jam_id", Integer, nullable=False, index=True),
    Column("key", String(200), nullable=False, index=True),
    Column("value", Float),
)

game = Table(
    "game", metadata,
    Column("game_id", Integer, primary_key=True),
    Column("date_in", DateTime(timezone=True)),
    Column("date_up", DateTime(timezone=True)),
    Column("jam_id", Integer, index=True),
    Column("title", Text),
    Column("studio", Text),
    Column("studio_slug", Text),
    Column("genre", Text),
    Column("platforms", Text),
    Column("languages", Text),
    Column("age", Text),
    Column("price", Text),
    Column("in_catalog", Integer, default=0),
)

# downloads, rating_avg, ratings_count, build_bytes, jam_points, jam_voters
game_metric = Table(
    "game_metric", metadata,
    Column("id", Integer, primary_key=True),
    Column("date_in", DateTime(timezone=True), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False, index=True),
    Column("game_id", Integer, nullable=False, index=True),
    Column("key", String(64), nullable=False, index=True),
    Column("value", Float),
)

_engine = None


def get_engine(url: str | None = None):
    global _engine
    if _engine is None or url:
        db_url = url or os.getenv("DB_URL")
        if not db_url:
            raise RuntimeError("нет DB_URL — проект запускается через docker compose")
        _engine = create_engine(db_url, future=True, pool_pre_ping=True)
    return _engine


def init_db(url: str | None = None) -> None:
    metadata.create_all(get_engine(url))


def now() -> datetime:
    return datetime.now(timezone.utc)


def _last_values(table, scope_col, scope_id: int) -> dict[str, float | None]:
    latest = select(func.max(table.c.id)).where(scope_col == scope_id).group_by(table.c.key)
    with get_engine().connect() as conn:
        rows = conn.execute(select(table.c.key, table.c.value).where(table.c.id.in_(latest))).all()
    return dict(rows)


def _changed(old, new) -> bool:
    if old is None or new is None:
        return old is not new
    return abs(float(old) - float(new)) > 1e-9


def _write(table, scope_name: str, scope_id: int, metrics: dict, ts: datetime | None) -> int:
    last = _last_values(table, table.c[scope_name], scope_id)
    stamp = ts or now()
    written = now()
    rows = [{"ts": stamp, scope_name: scope_id, "key": k,
             "value": None if v is None else float(v), "date_in": written}
            for k, v in metrics.items() if k not in last or _changed(last[k], v)]
    if rows:
        with get_engine().begin() as conn:
            conn.execute(insert(table), rows)
    return len(rows)


def write_jam_metrics(jam_id: int, metrics: dict, ts: datetime | None = None) -> int:
    return _write(jam_metric, "jam_id", jam_id, metrics, ts)


def write_game_metrics(game_id: int, metrics: dict, ts: datetime | None = None) -> int:
    return _write(game_metric, "game_id", game_id, metrics, ts)


def _upsert(table, pk: str, pk_value: int, fields: dict) -> None:
    """Пустые и посторонние ключи источника (например sprint.id) отбрасываем."""
    stamp = now()
    fields = {k: v for k, v in fields.items() if v is not None and k in table.c and k != pk}
    col = table.c[pk]
    with get_engine().begin() as conn:
        if conn.execute(select(col).where(col == pk_value)).scalar() is None:
            conn.execute(insert(table).values(**{pk: pk_value}, date_in=stamp, date_up=stamp, **fields))
        else:
            conn.execute(update(table).where(col == pk_value).values(date_up=stamp, **fields))


def upsert_game(game_id: int, **fields) -> None:
    _upsert(game, "game_id", game_id, fields)


def upsert_jam(jam_id: int, **fields) -> None:
    _upsert(jam, "jam_id", jam_id, fields)


def jam_info(jam_id: int) -> dict | None:
    with get_engine().connect() as conn:
        row = conn.execute(select(jam).where(jam.c.jam_id == jam_id)).first()
    return dict(row._mapping) if row else None


def jam_latest(jam_id: int) -> dict:
    return _last_values(jam_metric, jam_metric.c.jam_id, jam_id)


def games_series(jam_id: int, key: str) -> list[tuple]:
    """Ряды по всем работам джема разом: (game_id, ts, value)."""
    with get_engine().connect() as conn:
        return list(conn.execute(
            select(game_metric.c.game_id, game_metric.c.ts, game_metric.c.value)
            .join(game, game.c.game_id == game_metric.c.game_id)
            .where(game.c.jam_id == jam_id, game_metric.c.key == key)
            .order_by(game_metric.c.ts)).all())


def downloads_daily(jam_id: int) -> list[dict]:
    """Свой подсчёт по МСК (там же живёт джем). Точка отсчёта — первое увиденное
    значение каждой игры: то, что уже было скачано до начала нашего наблюдения,
    в прирост не попадает (иначе первый же день показал бы всю историю скачиваний
    с релиза). Любое изменение счётчика после этого относится к дню, когда случилось,
    даже если это тот же календарный день, что и первый снимок."""
    rows = games_series(jam_id, "downloads")  # уже отсортированы по ts
    known: dict = {}
    running: dict = {}
    delta_by_day: dict = {}
    total_by_day: dict = {}
    for gid, ts, v in rows:
        d = ts.astimezone(MSK).date()
        if gid in known:
            delta_by_day[d] = delta_by_day.get(d, 0) + (v - known[gid])
        else:
            delta_by_day.setdefault(d, 0)
        known[gid] = v
        running[gid] = v
        total_by_day[d] = sum(running.values())
    return [{"date": d.isoformat(), "total": total_by_day[d], "delta": delta_by_day[d]}
            for d in sorted(total_by_day)]


def games(jam_id: int | None = None) -> list[dict]:
    q = select(game) if jam_id is None else select(game).where(game.c.jam_id == jam_id)
    with get_engine().connect() as conn:
        return [dict(r._mapping) for r in conn.execute(q.order_by(game.c.game_id)).all()]


def games_latest(jam_id: int | None = None) -> list[dict]:
    """Карточки работ с последними значениями метрик — одним запросом, без N+1."""
    latest = select(func.max(game_metric.c.id)).group_by(game_metric.c.game_id, game_metric.c.key)
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(game_metric.c.game_id, game_metric.c.key, game_metric.c.value)
            .where(game_metric.c.id.in_(latest))).all()
    by_game: dict[int, dict] = {}
    for gid, k, v in rows:
        by_game.setdefault(gid, {})[k] = v
    out = games(jam_id)
    for g in out:
        g["metrics"] = by_game.get(g["game_id"], {})
    return out


def stats() -> dict:
    with get_engine().connect() as conn:
        out = {t.name: conn.execute(select(func.count()).select_from(t)).scalar()
               for t in (jam, jam_metric, game, game_metric)}
        out["last_ts"] = conn.execute(select(func.max(jam_metric.c.ts))).scalar()
    return out
