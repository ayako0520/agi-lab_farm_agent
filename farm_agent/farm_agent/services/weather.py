"""Weather via Open-Meteo (no API key)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import httpx


@dataclass
class WeatherSummary:
    lat: float
    lon: float
    days_past: int
    precip_sum_mm: float | None
    tmax_c_mean: float | None
    tmin_c_mean: float | None
    source: str
    raw_status: str


def fetch_weather_summary(lat: float, lon: float, days_past: int = 14) -> WeatherSummary:
    end = date.today()
    start = end - timedelta(days=days_past)
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ["precipitation_sum", "temperature_2m_max", "temperature_2m_min"],
        "timezone": "UTC",
    }
    try:
        r = httpx.get(url, params=params, timeout=20.0)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"weather_http_failed: {e}") from e

    daily = data.get("daily") or {}
    pr = daily.get("precipitation_sum") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []

    def _sum(xs: list) -> float | None:
        nums = [float(x) for x in xs if x is not None]
        return sum(nums) if nums else None

    def _mean(xs: list) -> float | None:
        nums = [float(x) for x in xs if x is not None]
        return sum(nums) / len(nums) if nums else None

    return WeatherSummary(
        lat=lat,
        lon=lon,
        days_past=days_past,
        precip_sum_mm=_sum(pr),
        tmax_c_mean=_mean(tmax),
        tmin_c_mean=_mean(tmin),
        source="open_meteo_archive",
        raw_status="ok",
    )
