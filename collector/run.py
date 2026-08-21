"""Цикл сбора: python -m collector.run --jam 12 [--api] [--games] [--scan 1-350]"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from db import db_worker as db

from . import parse_api, parse_game, parse_vote

JAM_ID = 12


def collect_api(jam_id: int) -> None:
    payload = parse_api.fetch_jam(jam_id)
    if not payload.get("success"):
        print("api: неуспешный ответ", payload.get("error"))
        return
    db.upsert_jam(jam_id, **payload.get("sprint", {}))
    written = db.write_jam_metrics(jam_id, parse_api.jam_metrics(payload))
    print(f"api: метрик записано {written}")


def collect_game(game_id: int, jam_id: int | None = None) -> bool:
    """True, если работа относится к джему."""
    data = parse_game.fetch(game_id)
    if not data:
        return False
    if jam_id is not None and data["jam_id"] != jam_id:
        return False
    metrics = data.pop("metrics")
    db.upsert_game(game_id, **data)
    db.write_game_metrics(game_id, metrics)
    return True


def collect_games(jam_id: int) -> None:
    ids = [g["game_id"] for g in db.games(jam_id)]
    if not ids:
        print("games: ростер пуст, сначала --scan")
        return
    ok = sum(collect_game(gid, jam_id) for gid in ids)
    print(f"games: обновлено {ok} из {len(ids)}")


def collect_vote(jam_id: int, path: str | None = None) -> None:
    """path — сохранённый HTML для добора истории, иначе живой запрос по сессии."""
    ts = None
    if path:
        html = Path(path).read_text(encoding="utf-8", errors="replace")
        ts = datetime.fromtimestamp(Path(path).stat().st_mtime, tz=timezone.utc)
    else:
        try:
            html = parse_vote.fetch(jam_id)
        except (RuntimeError, ValueError) as e:
            print("vote:", e)
            return
    try:
        data = parse_vote.parse(html)
    except ValueError as e:
        print("vote:", e)
        return
    written = db.write_jam_metrics(jam_id, data["jam"], ts=ts)
    for gid, metrics in data["games"].items():
        db.upsert_game(gid, jam_id=jam_id, title=data["titles"].get(gid))
        written += db.write_game_metrics(gid, metrics, ts=ts)
    j = data["jam"]
    print(f"vote: работ {int(j['vote.games_live'])}, очков {int(j['vote.points_total'])}, "
          f"голосов {int(j['vote.votes_total'])}, метрик записано {written}")


def scan_roster(jam_id: int, start: int, end: int) -> None:
    found = 0
    for gid in range(start, end + 1):
        if collect_game(gid, jam_id):
            found += 1
        if gid % 25 == 0:
            print(f"  скан {gid}/{end}, найдено {found}", flush=True)
    print(f"scan: работ джема {jam_id} найдено {found}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--jam", type=int, default=JAM_ID)
    p.add_argument("--api", action="store_true")
    p.add_argument("--games", action="store_true")
    p.add_argument("--scan", help="диапазон id, например 1-350")
    p.add_argument("--vote", action="store_true", help="баллы джема по сессии")
    p.add_argument("--vote-file", help="сохранённый HTML страницы голосования")
    p.add_argument("--stats", action="store_true", help="только показать состояние базы")
    args = p.parse_args()

    db.init_db()
    if args.scan:
        a, b = (int(x) for x in args.scan.split("-"))
        scan_roster(args.jam, a, b)
    if args.api or not any((args.scan, args.games, args.stats, args.vote, args.vote_file)):
        collect_api(args.jam)
    if args.games:
        collect_games(args.jam)
    if args.vote or args.vote_file:
        collect_vote(args.jam, args.vote_file)
    print("db:", db.stats())


if __name__ == "__main__":
    main()
