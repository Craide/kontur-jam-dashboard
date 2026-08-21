"""FastAPI: отдаёт ряды и срезы из БД, статику дашборда — из docs/."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from db import db_worker as db
from . import ratelimit

JAM_ID = 12
ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

app = FastAPI(title="Kontur Jam Dashboard", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def limit_rate(request, call_next):
    if request.url.path.startswith("/api") and not ratelimit.allow(ratelimit.client_ip(request)):
        return JSONResponse({"detail": "слишком много запросов"}, status_code=429,
                            headers={"Retry-After": "1"})
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"ok": True, "db": db.stats()}


@app.get("/api/jam/{jam_id}/latest")
def jam_latest(jam_id: int = JAM_ID):
    data = db.jam_latest(jam_id)
    if not data:
        raise HTTPException(404, "нет данных по джему")
    return data


@app.get("/api/jam/{jam_id}/info")
def jam_info(jam_id: int = JAM_ID):
    info = db.jam_info(jam_id)
    if not info:
        raise HTTPException(404, "джем не найден")
    return info


@app.get("/api/jam/{jam_id}/downloads_daily")
def downloads_daily(jam_id: int = JAM_ID):
    return db.downloads_daily(jam_id)


@app.get("/api/games")
def games(jam_id: int = JAM_ID):
    return db.games_latest(jam_id)


@app.get("/api/games/series")
def games_series(key: str, jam_id: int = JAM_ID):
    out: dict[int, list] = {}
    for gid, ts, v in db.games_series(jam_id, key):
        out.setdefault(gid, []).append({"ts": ts, "value": v})
    return out


if DOCS.exists():
    app.mount("/", StaticFiles(directory=DOCS, html=True), name="docs")
