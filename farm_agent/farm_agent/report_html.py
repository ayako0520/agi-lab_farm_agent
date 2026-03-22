"""Self-contained HTML dashboard for PipelineResult (no external assets)."""

from __future__ import annotations

import html
from typing import Any


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_dashboard(result: Any) -> str:
    lat = lon = 0.0
    place = result.location_query
    has_point = result.geocode is not None
    if result.geocode:
        lat, lon = result.geocode.lat, result.geocode.lon
        place = result.geocode.display_name

    d = 0.035
    map_section = ""
    if has_point:
        bbox = f"{lon - d},{lat - d},{lon + d},{lat + d}"
        map_src = f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}&layer=mapnik"
        map_section = f"""
    <section class="card">
      <h2>地図（OpenStreetMap）</h2>
      <iframe class="map" loading="lazy" src="{_esc(map_src)}" title="map"></iframe>
      <p class="muted" style="margin:10px 0 0;font-size:0.85rem">
        緯度 {lat:.5f} · 経度 {lon:.5f}
        · <a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=14/{lat}/{lon}" target="_blank" rel="noreferrer">OSM で開く</a>
      </p>
    </section>"""
    else:
        map_section = """
    <section class="card">
      <h2>地図</h2>
      <p class="muted">位置が取得できなかったため地図を表示できません。</p>
    </section>"""

    precip = tmax = tmin = None
    days_past = None
    if result.weather:
        w = result.weather
        precip, tmax, tmin, days_past = w.precip_sum_mm, w.tmax_c_mean, w.tmin_c_mean, w.days_past

    ndvi = result.ndvi.mean_ndvi if result.ndvi and result.ndvi.mean_ndvi is not None else None
    ndvi_pct = max(0.0, min(100.0, (ndvi or 0.0) * 100.0))
    ndvi_label = f"{ndvi:.3f}" if ndvi is not None else "—"
    scenes = result.ndvi.image_count if result.ndvi else 0

    soil = None
    if result.soil_proxy and result.soil_proxy.mean_soil_moisture_0_7cm is not None:
        soil = result.soil_proxy.mean_soil_moisture_0_7cm

    rec_body = ""
    if result.recommendation:
        rec_body = _esc(result.recommendation.text).replace("\n", "<br>\n")

    err_html = ""
    if result.errors:
        items = "".join(f"<li>{_esc(e)}</li>" for e in result.errors)
        err_html = f'<section class="card errors"><h2>警告 / エラー</h2><ul>{items}</ul></section>'

    soil_block = ""
    if soil is not None:
        soil_block = f"""
        <div class="metric">
          <div class="metric-label">土壌水分（代替指標）</div>
          <div class="metric-value">{soil:.3f}</div>
        </div>"""

    weather_block = ""
    if result.weather:
        weather_block = f"""
        <div class="grid3">
          <div class="metric"><div class="metric-label">降水（過去{days_past}日合計）</div>
            <div class="metric-value">{(f"{precip:.1f}") if precip is not None else "—"}<span class="unit">mm</span></div></div>
          <div class="metric"><div class="metric-label">最高気温（日平均の平均）</div>
            <div class="metric-value">{(f"{tmax:.1f}") if tmax is not None else "—"}<span class="unit">°C</span></div></div>
          <div class="metric"><div class="metric-label">最低気温（日平均の平均）</div>
            <div class="metric-value">{(f"{tmin:.1f}") if tmin is not None else "—"}<span class="unit">°C</span></div></div>
        </div>"""
    else:
        weather_block = '<p class="muted">気象データを取得できませんでした。</p>'

    ndvi_note = ""
    if result.ndvi:
        ndvi_note = _esc(str(result.ndvi.note or ""))

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Farm agent — {_esc(result.crop)}</title>
  <style>
    :root {{
      --bg0: #070b14;
      --bg1: #0f172a;
      --card: rgba(255,255,255,0.06);
      --border: rgba(255,255,255,0.12);
      --text: #e8edf7;
      --muted: rgba(232,237,247,0.72);
      --accent: #22d3ee;
      --accent2: #7c3aed;
      --ok: #34d399;
      --warn: #fbbf24;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans JP", sans-serif;
      color: var(--text);
      background: radial-gradient(900px 500px at 15% 10%, rgba(124,58,237,0.35), transparent 55%),
                  radial-gradient(800px 480px at 85% 20%, rgba(34,211,238,0.22), transparent 55%),
                  linear-gradient(160deg, var(--bg0), var(--bg1));
      min-height: 100vh;
    }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 28px 18px 48px; }}
    h1 {{
      font-size: 1.55rem;
      font-weight: 650;
      letter-spacing: 0.02em;
      margin: 0 0 6px;
    }}
    .sub {{ color: var(--muted); margin: 0 0 22px; font-size: 0.95rem; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px 18px 16px;
      margin-bottom: 16px;
      backdrop-filter: blur(10px);
    }}
    .card h2 {{
      margin: 0 0 12px;
      font-size: 1.05rem;
      font-weight: 650;
      color: var(--accent);
    }}
    iframe.map {{
      width: 100%;
      height: 320px;
      border: 0;
      border-radius: 12px;
      background: #111827;
    }}
    .grid3 {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
    }}
    @media (max-width: 720px) {{ .grid3 {{ grid-template-columns: 1fr; }} }}
    .metric {{
      padding: 14px 14px 12px;
      border-radius: 12px;
      background: rgba(0,0,0,0.22);
      border: 1px solid var(--border);
    }}
    .metric-label {{ font-size: 0.78rem; color: var(--muted); margin-bottom: 6px; }}
    .metric-value {{ font-size: 1.65rem; font-weight: 720; letter-spacing: 0.02em; }}
    .unit {{ font-size: 0.95rem; color: var(--muted); margin-left: 4px; font-weight: 600; }}
    .meter-wrap {{ margin-top: 8px; }}
    .meter {{
      height: 14px;
      border-radius: 999px;
      background: rgba(255,255,255,0.08);
      overflow: hidden;
      border: 1px solid var(--border);
    }}
    .meter > span {{
      display: block;
      height: 100%;
      width: {ndvi_pct:.2f}%;
      background: linear-gradient(90deg, #f59e0b, var(--ok));
      box-shadow: 0 0 24px rgba(52,211,153,0.35);
    }}
    .ndvi-meta {{ font-size: 0.85rem; color: var(--muted); margin-top: 8px; }}
    .rec {{ line-height: 1.65; font-size: 0.95rem; }}
    .errors {{ border-color: rgba(251,191,36,0.45); }}
    .errors ul {{ margin: 0; padding-left: 1.1rem; }}
    .muted {{ color: var(--muted); }}
    footer {{ margin-top: 18px; font-size: 0.8rem; color: var(--muted); }}
    a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{_esc(result.crop)} — 圃場ダッシュボード</h1>
    <p class="sub">{_esc(place)} · 入力: {_esc(result.location_query)}</p>

    {map_section}

    <section class="card">
      <h2>気象（Open-Meteo）</h2>
      {weather_block}
    </section>

    <section class="card">
      <h2>衛星 NDVI（Sentinel-2 / GEE）</h2>
      <div class="metric">
        <div class="metric-label">中央値合成の平均（約500mバッファ）</div>
        <div class="metric-value">{ndvi_label}</div>
      </div>
      <div class="meter-wrap">
        <div class="meter" title="NDVI 0〜1 を%表示"><span></span></div>
        <div class="ndvi-meta">シーン数: {scenes} · {ndvi_note}</div>
      </div>
      {soil_block}
    </section>

    {err_html}

    <section class="card">
      <h2>管理提案</h2>
      <div class="rec">{rec_body}</div>
    </section>

    <footer>MVP レポート · 助言は参考用。現地確認と専門家判断を優先してください。</footer>
  </div>
</body>
</html>
"""
