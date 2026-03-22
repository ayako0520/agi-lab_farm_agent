"""OpenAI ツール呼び出しでデータ取得順を自律決定する LLM エージェント。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from farm_agent.orchestrator import PipelineResult, _is_sentinel_weak
from farm_agent.services import geocode, jaxa_supplement, recommend, satellite_fallback, satellite_gee, weather
from farm_agent.utils.logutil import log_event
from farm_agent.utils.openai_cfg import openai_chat_model

_SYSTEM = """あなたは農業向けの自律データ収集エージェントです。
ユーザーから「圃場の候補地点（住所・地名または lat,lon）」と「作物名」が与えられます。
あなたはツールだけを使って根拠データを集め、最後に必ず submit_assessment で日本語の統合レポートを出して終了してください。

厳守: **あなたが呼ぶ最初のツールは必ず geocode_place だけ**にすること。
fetch_weather / fetch_ndvi / fetch_soil_moisture / fetch_jaxa_gsmap_smc は、geocode_place が成功して緯度経度が得られた**後**だけ呼べる（先に呼ぶとエラーになり無駄なステップになる）。

指針:
1. **最初の1回は必ず geocode_place**（ユーザー入力がすでに lat,lon でも同じく呼ぶ）。
2. 座標が分かったら fetch_weather と fetch_ndvi を通常は取得する。
3. NDVI が欠測・シーン極少・明らかに信頼できないときは fetch_soil_moisture を検討する。
4. 光学 NDVI だけでは弱いと判断したら fetch_jaxa_gsmap_smc で降水・土壌水分（マイクロ波系）を補う（jaxa-earth 未導入時はツール結果にエラーが返る）。
5. 同じツールを同じ引数で繰り返さない。十分ならすぐ submit_assessment に進む。
6. 農薬の用法用量・品目の具体的な処方は書かない。現地確認と専門家判断を促す。

終了は submit_assessment の1回だけでよい。"""

_LLM_DEMO_JAXA_EXTRA = """
【追加指示】このセッションでは fetch_ndvi のあと、**必ず1回** fetch_jaxa_gsmap_smc を呼び出してください。
結果（数値）または jaxa-earth 未導入などのエラー内容を、submit_assessment の本文で簡潔に触れてから終了してください。"""


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _llm_system_prompt() -> str:
    parts = [_SYSTEM]
    if _env_flag("FARM_AGENT_LLM_DEMO_JAXA"):
        parts.append(_LLM_DEMO_JAXA_EXTRA)
    if _env_flag("FARM_AGENT_LLM_DEMO_FORCE_NDVI_FAIL"):
        parts.append(
            "\n【環境オプション】fetch_ndvi が最初の1回だけシミュレーション失敗として返ることがあります。"
            "失敗したら fetch_soil_moisture や fetch_jaxa_gsmap_smc で補い、レポートに書いてから終了してください。"
        )
    return "".join(parts)


_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "geocode_place",
            "description": "住所・地名、または 'lat,lon' 文字列を緯度経度に変換する。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "ジオコードする文字列"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_weather",
            "description": "Open-Meteo で直近の気象要約（降水・気温）を取得する。**前に geocode_place が成功していること**（未確定の座標では呼ばない）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "days_past": {"type": "integer", "description": "過去日数（既定14）", "default": 14},
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_ndvi",
            "description": "Google Earth Engine の Sentinel-2 から NDVI 要約を取得する（要 EARTHENGINE_PROJECT）。**geocode_place 成功後に呼ぶ。**",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "days": {"type": "integer", "description": "遡及日数（既定60）", "default": 60},
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_soil_moisture",
            "description": "NDVI が使えない場合の代替として Open-Meteo 再解析の土壌水分（0-7cm）を取得する。**geocode_place 成功後に呼ぶ。**",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "days": {"type": "integer", "default": 14},
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_jaxa_gsmap_smc",
            "description": "JAXA Earth API で GSMaP 日次降水と AMSR2 土壌水分（昼）の要約を取得する（要 jaxa-earth）。**geocode_place 成功後に呼ぶ。**",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "days": {"type": "integer", "description": "窓日数（既定30）", "default": 30},
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_assessment",
            "description": "収集結果を踏まえた最終レポートを出してエージェントを終了する。必ず最後に呼ぶ。",
            "parameters": {
                "type": "object",
                "properties": {
                    "assessment_markdown": {
                        "type": "string",
                        "description": "日本語 Markdown。データの読み取り・リスク・次のアクションを簡潔に。",
                    },
                    "rationale": {"type": "string", "description": "どのデータを主に根拠にしたか1-3文。"},
                },
                "required": ["assessment_markdown", "rationale"],
            },
        },
    },
]


@dataclass
class _AgentState:
    geocode: Any | None = None
    weather: Any | None = None
    ndvi: Any | None = None
    soil_proxy: Any | None = None
    jaxa_supplement: Any | None = None
    jaxa_fetched: bool = False
    demo_ndvi_simulated_fail_done: bool = False
    errors: list[str] = field(default_factory=list)
    done: bool = False
    final_markdown: str = ""
    final_rationale: str = ""


def _max_steps() -> int:
    raw = os.environ.get("FARM_AGENT_AGENT_MAX_STEPS", "14").strip()
    try:
        n = int(raw)
    except ValueError:
        return 14
    return max(4, min(n, 24))


def _serialize_geocode(g: Any) -> dict[str, Any]:
    return {
        "lat": g.lat,
        "lon": g.lon,
        "display_name": g.display_name,
        "source": g.source,
    }


def _serialize_weather(w: Any) -> dict[str, Any]:
    return {
        "days_past": w.days_past,
        "precip_sum_mm": w.precip_sum_mm,
        "tmax_c_mean": w.tmax_c_mean,
        "tmin_c_mean": w.tmin_c_mean,
        "source": w.source,
    }


def _serialize_ndvi(n: Any) -> dict[str, Any]:
    ts = getattr(n, "timeseries", None) or []
    return {
        "mean_ndvi": n.mean_ndvi,
        "image_count": n.image_count,
        "latest_scene_date": getattr(n, "latest_scene_date", None),
        "timeseries_points": len(ts),
        "source": n.source,
        "note": n.note,
    }


def _serialize_jaxa(j: Any) -> dict[str, Any]:
    return {
        "precip_sum_mm": j.precip_sum_mm,
        "precip_mean_daily_mm": j.precip_mean_daily_mm,
        "smc_mean": j.smc_mean,
        "window_start": j.window_start,
        "window_end": j.window_end,
        "notes": j.notes,
    }


def _tool_summary(name: str, payload: dict[str, Any]) -> str:
    if name == "geocode_place" and payload.get("ok"):
        d = payload.get("result") or {}
        return f"OK {d.get('display_name', '')} ({d.get('lat')}, {d.get('lon')})"
    if name == "fetch_weather" and payload.get("ok"):
        d = payload.get("result") or {}
        return f"OK 降水合計 {d.get('precip_sum_mm')} mm / {d.get('days_past')} 日"
    if name == "fetch_ndvi" and payload.get("ok"):
        d = payload.get("result") or {}
        return f"OK NDVI mean={d.get('mean_ndvi')} scenes={d.get('image_count')}"
    if name == "fetch_soil_moisture" and payload.get("ok"):
        d = payload.get("result") or {}
        return f"OK 土壌水分0-7cm mean={d.get('mean_soil_moisture_0_7cm')}"
    if name == "fetch_jaxa_gsmap_smc" and payload.get("ok"):
        d = payload.get("result") or {}
        return f"OK JAXA precip_sum={d.get('precip_sum_mm')} smc={d.get('smc_mean')}"
    if name == "submit_assessment" and payload.get("ok"):
        return "OK 終了"
    err = payload.get("error") or payload.get("message")
    return f"失敗: {err}" if err else str(payload)[:120]


def _execute_tool(name: str, raw_args: str, state: _AgentState, crop: str) -> dict[str, Any]:
    try:
        args = json.loads(raw_args) if raw_args else {}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"invalid_json: {e}"}

    if name == "geocode_place":
        q = str(args.get("query", "")).strip()
        if not q:
            return {"ok": False, "error": "query が空です"}
        try:
            g = geocode.geocode_location(q)
            state.geocode = g
            log_event("llm_agent_tool", tool=name, ok=True)
            return {"ok": True, "result": _serialize_geocode(g)}
        except Exception as e:
            state.errors.append(f"geocode: {e}")
            log_event("llm_agent_tool", tool=name, ok=False, error=str(e))
            return {"ok": False, "error": str(e)}

    if name == "fetch_weather":
        if state.geocode is None:
            return {"ok": False, "error": "先に geocode_place で座標を確定してください"}
        lat = float(args["latitude"])
        lon = float(args["longitude"])
        days = int(args.get("days_past") or 14)
        try:
            w = weather.fetch_weather_summary(lat, lon, days_past=days)
            state.weather = w
            log_event("llm_agent_tool", tool=name, ok=True, days_past=days)
            return {"ok": True, "result": _serialize_weather(w)}
        except Exception as e:
            state.errors.append(f"weather: {e}")
            log_event("llm_agent_tool", tool=name, ok=False, error=str(e))
            return {"ok": False, "error": str(e)}

    if name == "fetch_ndvi":
        lat = float(args["latitude"])
        lon = float(args["longitude"])
        days = int(args.get("days") or 60)
        if _env_flag("FARM_AGENT_LLM_DEMO_FORCE_NDVI_FAIL") and not state.demo_ndvi_simulated_fail_done:
            state.demo_ndvi_simulated_fail_done = True
            state.ndvi = None
            msg = (
                "【シミュレーション】雲の影響で Sentinel-2 の有効シーンが得られなかった想定です（0件）。"
                " fetch_soil_moisture（再解析土壌水分）や fetch_jaxa_gsmap_smc（降水・マイクロ波土壌水分）で補完してください。"
            )
            state.errors.append("ndvi: demo_simulated_failure")
            log_event("llm_agent_tool", tool=name, ok=False, demo_simulated_ndvi_fail=True)
            return {"ok": False, "error": msg}
        try:
            n = satellite_gee.fetch_ndvi_sentinel2(lat, lon, days=days)
            state.ndvi = n
            log_event("llm_agent_tool", tool=name, ok=True, mean_ndvi=n.mean_ndvi, scenes=n.image_count)
            return {"ok": True, "result": _serialize_ndvi(n)}
        except Exception as e:
            state.errors.append(f"ndvi_gee: {e}")
            state.ndvi = None
            log_event("llm_agent_tool", tool=name, ok=False, error=str(e))
            return {"ok": False, "error": str(e)}

    if name == "fetch_soil_moisture":
        lat = float(args["latitude"])
        lon = float(args["longitude"])
        days = int(args.get("days") or 14)
        try:
            s = satellite_fallback.fetch_soil_moisture_proxy(lat, lon, days=days)
            state.soil_proxy = s
            log_event("llm_agent_tool", tool=name, ok=True)
            return {
                "ok": True,
                "result": {
                    "mean_soil_moisture_0_7cm": s.mean_soil_moisture_0_7cm,
                    "source": s.source,
                    "note": s.note,
                },
            }
        except Exception as e:
            state.errors.append(f"soil: {e}")
            log_event("llm_agent_tool", tool=name, ok=False, error=str(e))
            return {"ok": False, "error": str(e)}

    if name == "fetch_jaxa_gsmap_smc":
        if not jaxa_supplement.JAXA_EARTH_AVAILABLE:
            return {"ok": False, "error": "jaxa-earth 未インストール"}
        lat = float(args["latitude"])
        lon = float(args["longitude"])
        days = int(args.get("days") or 30)
        try:
            j = jaxa_supplement.fetch_jaxa_supplement(lat, lon, days=days)
            state.jaxa_supplement = j
            state.jaxa_fetched = True
            log_event("llm_agent_tool", tool=name, ok=True)
            return {"ok": True, "result": _serialize_jaxa(j) if j else {}}
        except Exception as e:
            state.errors.append(f"jaxa: {e}")
            log_event("llm_agent_tool", tool=name, ok=False, error=str(e))
            return {"ok": False, "error": str(e)}

    if name == "submit_assessment":
        md = str(args.get("assessment_markdown", "")).strip()
        rationale = str(args.get("rationale", "")).strip()
        if not md:
            return {"ok": False, "error": "assessment_markdown が空です"}
        state.final_markdown = md
        state.final_rationale = rationale
        state.done = True
        log_event("llm_agent_tool", tool=name, ok=True, crop=crop)
        return {"ok": True, "message": "評価を受け付けました。これ以上ツールは呼ばないでください。"}

    return {"ok": False, "error": f"unknown_tool: {name}"}


def _chat(key: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    model = openai_chat_model()
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": messages,
            "tools": _TOOLS,
            "tool_choice": "auto",
            "temperature": 0.2,
            "parallel_tool_calls": False,
        },
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()


def run_llm_tool_agent(location: str, crop: str) -> PipelineResult:
    """OpenAI の function calling でツール実行順を自律決定し、PipelineResult を組み立てる。"""
    out = PipelineResult(location_query=location, crop=crop, llm_agent_mode=True)
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        out.errors.append("OPENAI_API_KEY が未設定です。--llm-agent には OpenAI の API キーが必要です。")
        log_event("llm_agent_aborted", reason="no_api_key")
        return out

    state = _AgentState()
    trace: list[dict[str, Any]] = []
    user_task = (
        f"圃場候補の入力: {location!r}\n"
        f"作物: {crop!r}\n"
        "上記についてデータを集め、submit_assessment でまとめてください。"
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _llm_system_prompt()},
        {"role": "user", "content": user_task},
    ]

    max_steps = _max_steps()
    for step in range(max_steps):
        try:
            data = _chat(key, messages)
        except Exception as e:
            out.errors.append(f"openai_chat: {e}")
            log_event("llm_agent_failed", error=str(e), step=step)
            break

        choice = data["choices"][0]
        msg = choice["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            if msg.get("content"):
                messages.append(
                    {
                        "role": "user",
                        "content": "ツールを使うか、submit_assessment で終了してください。",
                    }
                )
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": "必ず submit_assessment を呼び出して日本語レポートを提出してください。",
                    }
                )
            continue

        for tc in tool_calls:
            tid = tc["id"]
            fn = tc.get("function") or {}
            name = fn.get("name", "")
            arguments = fn.get("arguments", "{}")
            payload = _execute_tool(name, arguments, state, crop)
            trace.append(
                {
                    "step": step + 1,
                    "tool": name,
                    "ok": bool(payload.get("ok")),
                    "summary": _tool_summary(name, payload),
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tid,
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            )

        if state.done:
            break

    out.llm_agent_trace = trace
    out.geocode = state.geocode
    out.weather = state.weather
    out.ndvi = state.ndvi
    out.soil_proxy = state.soil_proxy
    out.jaxa_supplement = state.jaxa_supplement
    if state.jaxa_fetched:
        out.supplement_reason = "llm_agent_fetch_jaxa"

    weak = _is_sentinel_weak(out.ndvi)
    jaxa_on = jaxa_supplement.jaxa_supplement_enabled()
    geo_name = out.geocode.display_name if out.geocode else location

    if state.final_markdown:
        body = f"## 自律エージェントの統合判断\n\n{state.final_markdown}\n"
        if state.final_rationale:
            body += f"\n**根拠の要約（モデル）**: {state.final_rationale}\n"
        tmpl = recommend.recommendation_template_only(
            crop=crop,
            geo_name=geo_name,
            weather=out.weather,
            ndvi=out.ndvi,
            soil_proxy=out.soil_proxy,
            jaxa=out.jaxa_supplement,
            sentinel_weak=weak and jaxa_on,
        )
        out.recommendation = recommend.Recommendation(
            text=body + "\n---\n\n" + tmpl.text,
            source=f"openai_llm_tool_agent+{openai_chat_model()}",
        )
    else:
        out.errors.append("LLM エージェントが submit_assessment で終了しませんでした。テンプレ要約にフォールバックします。")
        out.recommendation = recommend.recommendation_template_only(
            crop=crop,
            geo_name=geo_name,
            weather=out.weather,
            ndvi=out.ndvi,
            soil_proxy=out.soil_proxy,
            jaxa=out.jaxa_supplement,
            sentinel_weak=weak and jaxa_on,
        )
        if out.recommendation:
            out.recommendation = recommend.Recommendation(
                text="## 自律エージェント\n（最大ステップ内に終了ツールが呼ばれなかったため、データ要約のみ表示します。）\n\n"
                + out.recommendation.text,
                source="llm_agent_incomplete+template",
            )

    demo_tags: list[str] = []
    if _env_flag("FARM_AGENT_LLM_DEMO_FORCE_NDVI_FAIL"):
        demo_tags.append("force_ndvi_fail_sim")
    if _env_flag("FARM_AGENT_LLM_DEMO_JAXA"):
        demo_tags.append("demo_jaxa_prompt")
    out.llm_agent_demo_tags = demo_tags

    log_event(
        "llm_agent_done",
        steps=len(trace),
        finished=state.done,
        ok_geocode=out.geocode is not None,
        ok_weather=out.weather is not None,
        ok_ndvi=out.ndvi is not None and out.ndvi.mean_ndvi is not None,
        jaxa=bool(out.jaxa_supplement),
        demo_tags=demo_tags,
    )
    return out
