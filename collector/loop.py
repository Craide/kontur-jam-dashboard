"""Бесконечный цикл сбора для контейнера: каждая задача со своим интервалом.
Сбой одной задачи не роняет остальные."""

from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime, timezone

from db import db_worker as db

from . import run

JAM_ID = int(os.getenv("JAM_ID", "12"))
SCAN_RANGE = os.getenv("SCAN_RANGE", "1-350")
TICK = 10


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def tasks() -> list[tuple[str, int, callable]]:
    """Интервалы в секундах; 0 отключает задачу."""
    return [
        ("api", _env_int("API_EVERY", 600), lambda: run.collect_api(JAM_ID)),
        ("vote", _env_int("VOTE_EVERY", 900), lambda: run.collect_vote(JAM_ID)),
        ("games", _env_int("GAMES_EVERY", 21600), lambda: run.collect_games(JAM_ID)),
        ("scan", _env_int("SCAN_EVERY", 86400),
         lambda: run.scan_roster(JAM_ID, *(int(x) for x in SCAN_RANGE.split("-")))),
    ]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    db.init_db()

    active = [(n, sec, fn) for n, sec, fn in tasks() if sec > 0]
    if not os.getenv("DUSTORE_SESSION"):
        active = [t for t in active if t[0] != "vote"]
        log("vote: пропускаем, нет DUSTORE_SESSION")
    log("старт: " + ", ".join(f"{n} каждые {sec}с" for n, sec, _ in active))

    # первый прогон сразу, дальше по интервалам
    next_run = {n: 0.0 for n, _, _ in active}
    while True:
        now = time.monotonic()
        for name, sec, fn in active:
            if now < next_run[name]:
                continue
            try:
                fn()
            except Exception:
                log(f"{name}: сбой\n{traceback.format_exc()}")
            next_run[name] = time.monotonic() + sec
        time.sleep(TICK)


if __name__ == "__main__":
    main()
