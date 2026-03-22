"""Linear pipeline with explicit stages (geocode → weather → satellite → recommend)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from farm_agent.services import geocode, jaxa_supplement, recommend, satellite_fallback, satellite_gee, weather
from farm_agent.utils.logutil import log_event


def _is_sentinel_weak(ndvi: Any | None) -> bool:
    """Sentinel-2（GEE）の根拠が薄いとき True（別センサーで補うトリガ）。"""
    if ndvi is None:
        return True
    if getattr(ndvi, "image_count", 0) == 0:
        return True
    if getattr(ndvi, "mean_ndvi", None) is None:
        return True
    ts = getattr(ndvi, "timeseries", None) or []
    if len(ts) < 3:
        return True
    if getattr(ndvi, "image_count", 0) < 4:
        return True
    latest = getattr(ndvi, "latest_scene_date", None)
    if latest:
        try:
            from datetime import date

            y, m, d = (int(x) for x in str(latest).split("-")[:3])
            ld = date(y, m, d)
            if (date.today() - ld).days > 21:
                return True
        except (TypeError, ValueError):
            pass
    return False


@dataclass
class PipelineResult:
    location_query: str
    crop: str
    geocode: Any | None = None
    weather: Any | None = None
    ndvi: Any | None = None
    soil_proxy: Any | None = None
    jaxa_supplement: jaxa_supplement.JaxaSupplementSummary | None = None
    supplement_reason: str | None = None
    recommendation: recommend.Recommendation | None = None
    errors: list[str] = field(default_factory=list)
    # --llm-agent: OpenAI ツール呼び出しでデータ取得順を自律決定したときの記録
    llm_agent_mode: bool = False
    llm_agent_trace: list[dict[str, Any]] = field(default_factory=list)
    # --llm-agent 用オプション（.env の FARM_AGENT_LLM_DEMO_* が有効だったとき）
    llm_agent_demo_tags: list[str] = field(default_factory=list)


def run_pipeline(location: str, crop: str, *, jaxa_always: bool = False) -> PipelineResult:
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
            timeseries_n=len(getattr(out.ndvi, "timeseries", None) or []),
            thumb=bool(getattr(out.ndvi, "thumb_url", None)),
            latest_scene=getattr(out.ndvi, "latest_scene_date", None),
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

    # 3b) JAXA（GSMaP / AMSR2 SMC）
    # ・通常: Sentinel が弱い かつ FARM_AGENT_USE_JAXA=1
    # ・CLI の --jaxa（Sentinel の強弱に依存せず JAXA を取得）
    weak = _is_sentinel_weak(out.ndvi)
    jaxa_on = jaxa_supplement.jaxa_supplement_enabled()
    want_jaxa = jaxa_always or (weak and jaxa_on)

    if want_jaxa and jaxa_supplement.JAXA_EARTH_AVAILABLE:
        out.supplement_reason = "cli_jaxa_demo" if jaxa_always else "sentinel_weak_fetch_jaxa"
        try:
            out.jaxa_supplement = jaxa_supplement.fetch_jaxa_supplement(lat, lon)
            if out.jaxa_supplement:
                log_event(
                    "jaxa_supplement_ok",
                    precip_sum_mm=out.jaxa_supplement.precip_sum_mm,
                    precip_mean_daily_mm=out.jaxa_supplement.precip_mean_daily_mm,
                    smc_mean=out.jaxa_supplement.smc_mean,
                    days=out.jaxa_supplement.days,
                    note_count=len(out.jaxa_supplement.notes),
                    mode="always" if jaxa_always else "sentinel_weak",
                )
        except Exception as e:
            out.errors.append(f"jaxa_supplement: {e}")
            log_event("jaxa_supplement_failed", error=str(e))
    elif want_jaxa and not jaxa_supplement.JAXA_EARTH_AVAILABLE:
        out.supplement_reason = "cli_jaxa_unavailable" if jaxa_always else "sentinel_weak_jaxa_unavailable"
        out.errors.append(
            "JAXA 補完: jaxa-earth が未インストールです。"
            " pip install --extra-index-url https://data.earth.jaxa.jp/api/python/repository/ jaxa-earth"
        )
        log_event("jaxa_supplement_skipped", reason="package_not_installed", jaxa_always=jaxa_always)

    # 4) Recommendation
    geo_name = out.geocode.display_name if out.geocode else location
    out.recommendation = recommend.generate_recommendation(
        crop=crop,
        geo_name=geo_name,
        weather=out.weather,
        ndvi=out.ndvi,
        soil_proxy=out.soil_proxy,
        jaxa=out.jaxa_supplement,
        sentinel_weak=weak and jaxa_on,
    )
    log_event("recommendation_ok", source=out.recommendation.source)

    return out
