"""Thin 'agent' wrapper: runs the orchestrator and prints a final summary block."""

from __future__ import annotations

from farm_agent.orchestrator import PipelineResult, run_pipeline
from farm_agent.utils.logutil import log_event


def run_autonomous(location: str, crop: str) -> PipelineResult:
    log_event("agent_start", location=location, crop=crop)
    result = run_pipeline(location=location, crop=crop)
    log_event(
        "agent_done",
        ok_geocode=result.geocode is not None,
        ok_weather=result.weather is not None,
        ok_ndvi=result.ndvi is not None and result.ndvi.mean_ndvi is not None,
        used_fallback=result.soil_proxy is not None,
        error_count=len(result.errors),
    )
    return result


def format_summary(result: PipelineResult) -> str:
    lines = [
        "",
        "========== FINAL SUMMARY ==========",
        f"入力: location={result.location_query!r}, crop={result.crop!r}",
    ]
    if result.geocode:
        lines.append(
            f"位置: {result.geocode.display_name} ({result.geocode.lat:.5f}, {result.geocode.lon:.5f}) "
            f"[{result.geocode.source}]"
        )
    else:
        lines.append("位置: 取得失敗（ジオコーディング）")

    if result.weather:
        w = result.weather
        lines.append(
            f"気象(過去{w.days_past}日): 降水合計={w.precip_sum_mm}mm, "
            f"最高平均={w.tmax_c_mean}°C, 最低平均={w.tmin_c_mean}°C"
        )
    else:
        lines.append("気象: 取得失敗")

    if result.ndvi and result.ndvi.mean_ndvi is not None:
        lines.append(
            f"NDVI: {result.ndvi.mean_ndvi:.3f} (scenes={result.ndvi.image_count}, {result.ndvi.source})"
        )
    elif result.ndvi:
        lines.append(f"NDVI: 欠測/不安定 (scenes={result.ndvi.image_count})")
    else:
        lines.append("NDVI: GEE未取得")

    if result.soil_proxy and result.soil_proxy.mean_soil_moisture_0_7cm is not None:
        lines.append(
            f"代替(土壌水分0-7cm平均): {result.soil_proxy.mean_soil_moisture_0_7cm:.3f} "
            f"({result.soil_proxy.source})"
        )

    if result.errors:
        lines.append("エラー/警告ログ:")
        for e in result.errors:
            lines.append(f"  - {e}")

    lines.append("-----------------------------------")
    if result.recommendation:
        lines.append(result.recommendation.text)
    lines.append("===================================")
    return "\n".join(lines)
