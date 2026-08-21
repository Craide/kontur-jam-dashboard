"""Публичный /jams/api -> плоские числовые метрики."""

from __future__ import annotations

from . import sources

SKIP_KEYS = {"note", "success", "api_version", "generated_at", "sprint"}


def fetch_jam(jam_id: int) -> dict:
    return sources.get_json(f"/jams/api?id={jam_id}")


def jam_metrics(obj, prefix: str = "") -> dict[str, float]:
    """Числа в плоские ключи: overview.participants, tech.engines.Unity."""
    out: dict[str, float] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in SKIP_KEYS:
                continue
            out.update(jam_metrics(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(jam_metrics(v, f"{prefix}.{i}"))
    elif isinstance(obj, bool):
        out[prefix] = int(obj)
    elif isinstance(obj, (int, float)):
        out[prefix] = float(obj)
    return out
