"""Fallback vegetation proxy when GEE is unavailable (reanalysis, not optical NDVI)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class SoilMoistureProxy:
    mean_soil_moisture_0_7cm: float | None
    days: int
    source: str
    note: str


def fetch_soil_moisture_proxy(lat: float, lon: float, days: int = 14) -> SoilMoistureProxy:
    """Soil moisture proxy via Open-Meteo forecast API (past_days). Archive soil vars often 400."""

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "soil_moisture_0_to_7cm",
        "past_days": days,
        "forecast_days": 1,
        "timezone": "UTC",
    }
    r = httpx.get(url, params=params, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    daily = data.get("daily") or {}
    xs = daily.get("soil_moisture_0_to_7cm") or []
    nums = [float(x) for x in xs if x is not None]
    mean = sum(nums) / len(nums) if nums else None
    return SoilMoistureProxy(
        mean_soil_moisture_0_7cm=mean,
        days=days,
        source="open_meteo_forecast_past_soil_proxy",
        note="not_satellite_ndvi",
    )
