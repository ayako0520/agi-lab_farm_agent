"""Linear pipeline with explicit stages (geocode → weather → satellite → recommend)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from farm_agent.services import geocode, recommend, satellite_fallback, satellite_gee, weather
from farm_agent.utils.logutil import log_event


@dataclass
class PipelineResult:
    location_query: str
    crop: str
    geocode: Any | None = None
    weather: Any | None = None
    ndvi: Any | None = None
    soil_proxy: Any | None = None
    recommendation: recommend.Recommendation | None = None
    errors: list[str] = field(default_factory=list)


def run_pipeline(location: str, crop: str) -> PipelineResult:
    out = PipelineResult(location_query=location, crop=crop)

    # 1) Geocode
    try:
        out.geocode = geocode.geocode_location(location)
        log_event(
            "geocode_ok",
            lat=out.geocode.lat,
            lon=out.geocode.lon,
            display_name=out.geocode.display_name,
            source=out.geocode.source,
        )
    except Exception as e:
        msg = f"geocode: {e}"
        out.errors.append(msg)
        log_event("geocode_failed", error=str(e))
        return out

    lat, lon = out.geocode.lat, out.geocode.lon

    # 2) Weather (+ narrow retry)
    for days in (14, 7):
        try:
            out.weather = weather.fetch_weather_summary(lat, lon, days_past=days)
            log_event(
                "weather_ok",
                days_past=days,
                precip_sum_mm=out.weather.precip_sum_mm,
                tmax_c_mean=out.weather.tmax_c_mean,
                tmin_c_mean=out.weather.tmin_c_mean,
                source=out.weather.source,
            )
            break
        except Exception as e:
            log_event("weather_retry", days_past=days, error=str(e))
    if out.weather is None:
        msg = "weather: failed after retries"
        out.errors.append(msg)
        log_event("weather_failed")

    # 3) Satellite NDVI (GEE) + fallback proxy
    try:
        out.ndvi = satellite_gee.fetch_ndvi_sentinel2(lat, lon, days=60)
        log_event(
            "ndvi_ok",
            mean_ndvi=out.ndvi.mean_ndvi,
            image_count=out.ndvi.image_count,
            source=out.ndvi.source,
            note=out.ndvi.note,
        )
    except Exception as e:
        out.errors.append(f"ndvi_gee: {e}")
        log_event("ndvi_gee_failed", error=str(e))
        out.ndvi = None

    need_proxy = out.ndvi is None or (
        out.ndvi is not None and out.ndvi.mean_ndvi is None and out.ndvi.image_count == 0
    )
    if need_proxy:
        try:
            out.soil_proxy = satellite_fallback.fetch_soil_moisture_proxy(lat, lon, days=14)
            log_event(
                "satellite_fallback_ok",
                mean_soil_moisture_0_7cm=out.soil_proxy.mean_soil_moisture_0_7cm,
                source=out.soil_proxy.source,
                note=out.soil_proxy.note,
            )
        except Exception as e:
            out.errors.append(f"satellite_fallback: {e}")
            log_event("satellite_fallback_failed", error=str(e))

    # 4) Recommendation
    geo_name = out.geocode.display_name if out.geocode else location
    out.recommendation = recommend.generate_recommendation(
        crop=crop,
        geo_name=geo_name,
        weather=out.weather,
        ndvi=out.ndvi,
        soil_proxy=out.soil_proxy,
    )
    log_event("recommendation_ok", source=out.recommendation.source)

    return out
