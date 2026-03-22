"""Thin 'agent' wrapper: runs the orchestrator and prints a final summary block."""

from __future__ import annotations

from farm_agent.agents.autonomous_llm_agent import run_llm_tool_agent
from farm_agent.orchestrator import PipelineResult, run_pipeline
from farm_agent.utils.logutil import log_event


def run_autonomous(
    location: str,
    crop: str,
    *,
    jaxa_always: bool = False,
    llm_agent: bool = False,
) -> PipelineResult:
    log_event(
        "agent_start",
        location=location,
        crop=crop,
        jaxa_always=jaxa_always,
        llm_agent=llm_agent,
    )
    if llm_agent:
        result = run_llm_tool_agent(location, crop)
    else:
        result = run_pipeline(location=location, crop=crop, jaxa_always=jaxa_always)
    log_event(
        "agent_done",
        ok_geocode=result.geocode is not None,
        ok_weather=result.weather is not None,
        ok_ndvi=result.ndvi is not None and result.ndvi.mean_ndvi is not None,
        used_fallback=result.soil_proxy is not None,
        jaxa_supplement=result.jaxa_supplement is not None,
        supplement_reason=result.supplement_reason,
        error_count=len(result.errors),
        llm_agent_mode=result.llm_agent_mode,
    )
    return result


def format_summary(result: PipelineResult) -> str:
    lines = [
        "",
        "========== FINAL SUMMARY ==========",
        f"入力: location={result.location_query!r}, crop={result.crop!r}",
    ]
    if getattr(result, "llm_agent_mode", False):
        lines.append("モード: OpenAI ツール自律エージェント（--llm-agent）")
        if "force_ndvi_fail_sim" in (getattr(result, "llm_agent_demo_tags", None) or []):
            lines.append("（FARM_AGENT_LLM_DEMO_FORCE_NDVI_FAIL=1: 最初の NDVI はシミュレーション失敗）")
        tr = getattr(result, "llm_agent_trace", None) or []
        if tr:
            lines.append("LLMツール呼び出し順:")
            for ev in tr:
                step = ev.get("step", "")
                name = ev.get("tool", "")
                summ = ev.get("summary", "")
                ok = "OK" if ev.get("ok") else "NG"
                lines.append(f"  {step}. {name} — {ok} {summ}")
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
        latest = getattr(result.ndvi, "latest_scene_date", None)
        latest_s = f", 直近シーン日付={latest}" if latest else ""
        lines.append(
            f"NDVI: {result.ndvi.mean_ndvi:.3f} (scenes={result.ndvi.image_count}{latest_s}, {result.ndvi.source})"
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

    if result.supplement_reason:
        lines.append(f"補完: {result.supplement_reason}")
    if result.jaxa_supplement:
        j = result.jaxa_supplement
        if j.precip_sum_mm is not None:
            md = j.precip_mean_daily_mm
            md_s = f"{md:.3f}" if md is not None else "—"
            lines.append(
                f"JAXA GSMaP: 期間降水合計(空間平均の日次合計)≈{j.precip_sum_mm:.2f}mm, "
                f"日平均≈{md_s}mm/日 ({j.window_start}〜{j.window_end})"
            )
        elif j.precip_mean_daily_mm is not None:
            lines.append(f"JAXA GSMaP: 日平均≈{j.precip_mean_daily_mm}mm/日")
        if j.smc_mean is not None:
            lines.append(f"JAXA AMSR2 SMC: 期間平均≈{j.smc_mean:.3f}")

    if result.errors:
        lines.append("エラー/警告ログ:")
        for e in result.errors:
            lines.append(f"  - {e}")

    lines.append("-----------------------------------")
    if result.recommendation:
        lines.append(result.recommendation.text)
    lines.append("===================================")
    return "\n".join(lines)
