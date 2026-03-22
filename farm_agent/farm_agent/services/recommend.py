"""Turn signals into a short farm management note."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from farm_agent.utils.openai_cfg import openai_chat_model


@dataclass
class Recommendation:
    text: str
    source: str


def _template(
    crop: str,
    geo_name: str,
    weather: Any,
    ndvi: Any | None,
    soil_proxy: Any | None,
    jaxa: Any | None = None,
    sentinel_weak: bool = False,
) -> str:
    lines = [
        f"作物: {crop}",
        f"圃場（推定位置）: {geo_name}",
        "",
        "## データ要約",
    ]
    if sentinel_weak:
        lines.append(
            "- 衛星（Sentinel-2 / NDVI）: 根拠が薄いと判断しました（シーン不足・古い観測など）。"
            " 環境変数で有効にしている場合は、JAXA Earth API の別系統（GSMaP 降水・AMSR2 土壌水分）を併記します。"
        )
    if weather is not None:
        lines.append(
            f"- 直近{weather.days_past}日: 降水量合計 {weather.precip_sum_mm} mm, "
            f"日最高気温平均 {weather.tmax_c_mean} °C, 日最低気温平均 {weather.tmin_c_mean} °C "
            f"（{weather.source}）"
        )
    else:
        lines.append("- 気象: 取得できず")

    if ndvi is not None and ndvi.mean_ndvi is not None:
        latest = getattr(ndvi, "latest_scene_date", None)
        latest_s = f"、直近シーン日 {latest}" if latest else ""
        lines.append(
            f"- 衛星NDVI（Sentinel-2, 直近{ndvi.days}日・雲除去後中央値の平均）: {ndvi.mean_ndvi:.3f} "
            f"（利用シーン数 {ndvi.image_count}{latest_s}）"
        )
    elif ndvi is not None:
        lines.append(
            f"- 衛星NDVI: この期間・条件では安定した値が得られませんでした（シーン数 {ndvi.image_count}）"
        )
    else:
        lines.append("- 衛星NDVI: 未取得")

    if soil_proxy is not None and soil_proxy.mean_soil_moisture_0_7cm is not None:
        lines.append(
            f"- 代替指標（再解析・土壌水分0-7cm平均）: {soil_proxy.mean_soil_moisture_0_7cm:.3f} "
            f"（{soil_proxy.source}）"
        )

    if jaxa is not None:
        jbits: list[str] = []
        if jaxa.precip_sum_mm is not None and jaxa.precip_mean_daily_mm is not None:
            jbits.append(
                f"GSMaP 日次（バンド PRECIP）: 期間合計おおよそ {jaxa.precip_sum_mm:.2f} mm、"
                f"日平均（空間平均の日次平均）{jaxa.precip_mean_daily_mm:.3f} mm/日"
            )
        elif jaxa.precip_mean_daily_mm is not None:
            jbits.append(f"GSMaP 日次: 日平均 {jaxa.precip_mean_daily_mm:.3f} mm/日")
        if jaxa.smc_mean is not None:
            jbits.append(f"AMSR2 土壌水分（昼・L3 SMC）: 期間平均（空間×日）おおよそ {jaxa.smc_mean:.3f}")
        if jbits:
            lines.append(
                "- JAXA Earth API 補完: "
                + " / ".join(jbits)
                + f"（{jaxa.source}、{jaxa.window_start}〜{jaxa.window_end}）"
            )
        elif getattr(jaxa, "notes", None):
            lines.append(
                f"- JAXA Earth API: 主要指標は得られませんでした（{jaxa.window_start}〜{jaxa.window_end}）。"
            )
        for note in getattr(jaxa, "notes", None) or []:
            lines.append(f"  - （JAXA メモ）{note}")

    lines.extend(["", "## 提案（参考）", _heuristics(crop, weather, ndvi, soil_proxy, jaxa)])
    lines.extend(
        [
            "",
            "※ 現地の生育・土壌・病害虫・農薬適正は必ず現地確認と専門家判断を優先してください。",
        ]
    )
    return "\n".join(lines)


def _heuristics(
    crop: str,
    weather: Any,
    ndvi: Any | None,
    soil_proxy: Any | None,
    jaxa: Any | None = None,
) -> str:
    tips: list[str] = []

    if weather is not None and weather.precip_sum_mm is not None:
        if weather.precip_sum_mm < 5:
            tips.append("直近は降雨が少なめです。灌漑・畦の保水を意識してください。")
        elif weather.precip_sum_mm > 80:
            tips.append("直近は降雨が多めです。排水・病害（葉病・根腐れ系）リスクに注意してください。")

    if ndvi is not None and ndvi.mean_ndvi is not None:
        if ndvi.mean_ndvi < 0.25:
            tips.append("NDVIが低めに見えます。欠株・栄養・干旱・病害・観測条件（雲・裸地）を現地で確認してください。")
        elif ndvi.mean_ndvi > 0.65:
            tips.append("NDVIは高めに見えます。繁茂過多や収穫適期の判断は現地の生育段階と合わせてください。")
        else:
            tips.append("NDVIは中程度です。週次でトレンド（上昇/平坦/低下）を追うと管理判断がしやすいです。")
    elif soil_proxy is not None and soil_proxy.mean_soil_moisture_0_7cm is not None:
        tips.append(
            "NDVIが使えないため、土壌水分（再解析）を参考にしました。灌水タイミングは現地の乾き具合と併用してください。"
        )

    if jaxa is not None and (jaxa.smc_mean is not None or jaxa.precip_sum_mm is not None):
        tips.append(
            "JAXA の降水・土壌水分は光学 NDVI とは独立した衛星系です。単位・解像度はデータセットに依存するため、解釈は現地観測と併用してください。"
        )

    if not tips:
        tips.append(f"{crop}について、気象と衛星の両方を週次で見て、異常だけ早期に拾う運用がおすすめです。")

    return "\n".join(f"- {t}" for t in tips)


def generate_recommendation(
    crop: str,
    geo_name: str,
    weather: Any,
    ndvi: Any | None,
    soil_proxy: Any | None,
    jaxa: Any | None = None,
    sentinel_weak: bool = False,
) -> Recommendation:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    base = _template(crop, geo_name, weather, ndvi, soil_proxy, jaxa=jaxa, sentinel_weak=sentinel_weak)
    if not key:
        return Recommendation(text=base, source="template")

    try:
        prompt = (
            "You are an agronomy assistant. Given the structured context below, "
            "write 5-8 bullet recommendations in Japanese. Be cautious, no pesticide rates.\n\n"
            + base
        )
        model = openai_chat_model()
        r = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=60.0,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return Recommendation(text=base + "\n\n## LLM追記\n" + content, source=f"openai+{model}")
    except Exception:
        return Recommendation(text=base + "\n\n(LLM追記は失敗したためテンプレのみ)", source="template_llm_failed")


def recommendation_template_only(
    crop: str,
    geo_name: str,
    weather: Any,
    ndvi: Any | None,
    soil_proxy: Any | None,
    jaxa: Any | None = None,
    sentinel_weak: bool = False,
) -> Recommendation:
    """OpenAI を呼ばずテンプレのみ（LLM ツールエージェントのフォールバック用）。"""
    return Recommendation(
        text=_template(crop, geo_name, weather, ndvi, soil_proxy, jaxa=jaxa, sentinel_weak=sentinel_weak),
        source="template",
    )
