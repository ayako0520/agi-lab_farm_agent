"""Self-contained HTML dashboard for PipelineResult (no external assets)."""

from __future__ import annotations

import html
import json
import math
from typing import Any


# 衛星 NDVI の集計円（半径 500m）の外接矩形に近い縮尺で OSM を切り出す
_OSM_HALF_EXTENT_M = 550.0
_M_PER_DEG_LAT = 111_320.0


def _osm_bbox_degrees(lat: float, lon: float, half_extent_m: float = _OSM_HALF_EXTENT_M) -> tuple[float, float, float, float]:
    d_lat = half_extent_m / _M_PER_DEG_LAT
    cos_lat = max(0.2, abs(math.cos(math.radians(lat))))
    d_lon = half_extent_m / (_M_PER_DEG_LAT * cos_lat)
    return (lon - d_lon, lat - d_lat, lon + d_lon, lat + d_lat)


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_dashboard(result: Any) -> str:
    lat = lon = 0.0
    place = result.location_query
    has_point = result.geocode is not None
    if result.geocode:
        lat, lon = result.geocode.lat, result.geocode.lon
        place = result.geocode.display_name

    map_section = ""
    if has_point:
        min_lon, min_lat, max_lon, max_lat = _osm_bbox_degrees(lat, lon)
        bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        map_src = f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}&layer=mapnik"
        map_section = f"""
    <section class="card">
      <h2>地図（OpenStreetMap）</h2>
      <p class="muted" style="font-size:0.82rem;margin:0 0 8px">
        衛星 NDVI プレビューと同じイメージの広さです（代表点から<strong>およそ ±550 m</strong>・辺の長さ<strong>約 1.1 km</strong>前後。緯度によりわずかに変わります）。
      </p>
      <iframe class="map" loading="lazy" src="{_esc(map_src)}" title="map"></iframe>
      <p class="muted" style="margin:10px 0 0;font-size:0.85rem">
        緯度 {lat:.5f} · 経度 {lon:.5f}
        · <a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}" target="_blank" rel="noreferrer">OSM で開く（おおよそ同じ縮尺）</a>
      </p>
    </section>"""
    else:
        map_section = """
    <section class="card">
      <h2>地図</h2>
      <p class="muted">位置が取得できなかったため地図を表示できません。</p>
    </section>"""

    llm_agent_section = ""
    if getattr(result, "llm_agent_mode", False):
        tr = getattr(result, "llm_agent_trace", None) or []
        demo_tags = getattr(result, "llm_agent_demo_tags", None) or []
        demo_banner = ""
        if "force_ndvi_fail_sim" in demo_tags:
            demo_banner = """
      <p class="muted" style="font-size:0.82rem;margin:0 0 10px;padding:10px 12px;border-radius:10px;border:1px solid rgba(251,191,36,0.5);background:rgba(251,191,36,0.1)">
        <strong>補足</strong>: 環境変数 <code>FARM_AGENT_LLM_DEMO_FORCE_NDVI_FAIL=1</code> により、
        最初の <code>fetch_ndvi</code> は<strong>シミュレーション失敗</strong>として扱われます（実際の Google Earth Engine の応答ではありません）。
        代替ツールの選択挙動を確認するためのオプションです。
      </p>"""
        if tr:
            items = "".join(
                f"<li><strong>{_esc(str(ev.get('step', '')))}.</strong> "
                f"<code>{_esc(str(ev.get('tool', '')))}</code> — "
                f"{_esc(str(ev.get('summary', '')))}</li>"
                for ev in tr
            )
            llm_agent_section = f"""
    <section class="card">
      <h2>自律 LLM エージェント（OpenAI ツール）</h2>
      {demo_banner}
      <p class="muted" style="font-size:0.85rem;margin:0 0 10px">
        モデルが <strong>どのデータソースをいつ取得するか</strong>を自律選択しました（OpenAI function calling）。要 <code>OPENAI_API_KEY</code>。
        下の一覧は<strong>呼び出し順どおり</strong>で、順序ミスによる<strong>一度きりの失敗</strong>が含まれることがあります（その後に正しい順で再試行されます）。
      </p>
      <ol class="muted" style="margin:0;padding-left:1.2rem;line-height:1.6;font-size:0.88rem">{items}</ol>
    </section>"""
        else:
            llm_agent_section = """
    <section class="card">
      <h2>自律 LLM エージェント</h2>
      <p class="muted">ツール実行ログがありません（API キー未設定などで中断した可能性があります）。</p>
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
    latest_scene_date = getattr(result.ndvi, "latest_scene_date", None) if result.ndvi else None
    latest_scene_meta = (
        f" · 直近シーン日（雲フィルタ後）: {_esc(latest_scene_date)}"
        if latest_scene_date
        else ""
    )

    soil = None
    if result.soil_proxy and result.soil_proxy.mean_soil_moisture_0_7cm is not None:
        soil = result.soil_proxy.mean_soil_moisture_0_7cm

    rec_body = ""
    if result.recommendation:
        rec_body = _esc(result.recommendation.text).replace("\n", "<br>\n")

    satellite_doc = """
    <details class="satellite-doc">
      <summary>この衛星データについて（NDVI とは）</summary>
      <div class="satellite-doc-body">
        <p><strong>NDVI</strong>（Normalized Difference Vegetation Index）は、近赤外と赤の反射の差から求める植生指標です。
        値はおおよそ -1〜1 で、<strong>緑の植生が多いほど高め</strong>に出る傾向があります（農地では目安として 0.2〜0.8 付近に収まることが多いですが、作物・生育期・土壌露出で変化します）。</p>
        <p><strong>データソース</strong>：欧州コペルニクス計画の <strong>Sentinel-2</strong>（多バンド光学衛星）を、
        <strong>Google Earth Engine</strong> 上の大気補正済みコレクション（<code>COPERNICUS/S2_SR_HARMONIZED</code>）から読み、
        赤（B4）と近赤外（B8）から NDVI を計算しています。Sentinel-2 の空間解像度はバンドにより異なりますが、本処理では合成・集約に合わせて <strong>おおよそ数十m〜20m スケール</strong>で統計を取っています。</p>
        <p><strong>この画面の数値の意味</strong>：指定座標の周辺 <strong>約 500 m を半径とした円</strong>内について、
        期間中・<strong>雲量が比較的少ないシーンだけ</strong>を選び、各日（シーン）の NDVI をとったうえで <strong>期間中央値</strong>で合成し、
        その画像の <strong>ROI 平均</strong>を表示しています。表示の「シーン数」は、雲フィルタ後に残った観測回数の目安です。
        <strong>折れ線グラフ</strong>は各シーンの ROI 平均 NDVI の時系列、<strong>画像プレビュー</strong>は中央値合成 NDVI の疑似カラー（GEE サムネイル。集計円の<strong>外接長方形</strong>を切り出し）です。</p>
        <ul>
          <li><strong>都市・道路・水域</strong>がピクセルに混ざると、農地単体より NDVI は<strong>低く出やすい</strong>です。</li>
          <li><strong>雲・影・雪・霧</strong>があると欠測や低値になり、シーン数が少ないときは値が不安定になりえます。</li>
          <li>本値は <strong>「その地点周辺の植生状況の参考」</strong>であり、品目別の絶対評価や収量推定を保証するものではありません。</li>
        </ul>
        <p><strong>土壌水分が別枠で出ている場合</strong>：Open-Meteo の <strong>再解析ベース</strong>の土壌水分（光学衛星 NDVI とは別物）を、
        NDVI が取得できない場合の<strong>参考用フォールバック</strong>として表示していることがあります。</p>
        <p class="muted" style="margin-top:10px;font-size:0.82rem">利用規約・クォータは Google Earth Engine および各データ提供者の条件に従ってください。</p>
      </div>
    </details>
    """

    jaxa_section = ""
    jx = getattr(result, "jaxa_supplement", None)
    jx_reason = getattr(result, "supplement_reason", None)
    if jx is not None or jx_reason:
        jaxa_body = ""
        if jx is not None:
            gmin = (
                f"{jx.precip_sum_mm:.1f}"
                if jx.precip_sum_mm is not None
                else "—"
            )
            gavg = (
                f"{jx.precip_mean_daily_mm:.3f}"
                if jx.precip_mean_daily_mm is not None
                else "—"
            )
            smc_v = f"{jx.smc_mean:.3f}" if jx.smc_mean is not None else "—"
            notes_li = "".join(f"<li>{_esc(n)}</li>" for n in (jx.notes or []))
            notes_block = (
                f'<ul class="muted" style="margin:8px 0 0;padding-left:1.1rem;font-size:0.85rem">{notes_li}</ul>'
                if notes_li
                else ""
            )
            b = jx.bbox
            p_uri = getattr(jx, "precip_thumb_data_uri", None)
            s_uri = getattr(jx, "smc_thumb_data_uri", None)
            jaxa_thumbs = ""
            if p_uri or s_uri:
                fig_parts: list[str] = []
                if p_uri:
                    fig_parts.append(
                        f"""<figure class="jaxa-fig">
      <figcaption class="muted jaxa-cap">GSMaP 日次 <code>PRECIP</code> · 期間平均合成（粗格子）</figcaption>
      <img class="jaxa-thumb-img" src="{p_uri}" alt="GSMaP PRECIP temporal mean" loading="lazy" />
    </figure>"""
                    )
                if s_uri:
                    fig_parts.append(
                        f"""<figure class="jaxa-fig">
      <figcaption class="muted jaxa-cap">AMSR2 昼 <code>SMC</code> · 期間平均合成（粗格子）</figcaption>
      <img class="jaxa-thumb-img" src="{s_uri}" alt="AMSR2 SMC temporal mean" loading="lazy" />
    </figure>"""
                    )
                jaxa_thumbs = f"""
      <div class="jaxa-thumb-row">
        <p class="muted jaxa-thumb-note">画像は <strong>JAXA Earth API</strong> のラスタをアプリ側で PNG 化したものです（Sentinel の GEE サムネのような公式 URL はありません）。色は相対スケールです。</p>
        {"".join(fig_parts)}
      </div>"""
            if jx_reason == "cli_jaxa_demo":
                jaxa_intro = """
      <p class="muted" style="font-size:0.82rem;margin:0 0 10px">
        CLI の <code>--jaxa</code> により、Sentinel-2（NDVI）の強弱に関係なく <strong>JAXA Earth API</strong> から
        <strong>GSMaP 日次降水</strong>と <strong>AMSR2 土壌水分（昼）</strong>を取得した結果です（周辺矩形は粗い解像度）。
        API のプロトタイプ DB により日付が取れない場合があります。
        集計矩形は <strong>GSMaP の格子（おおよそ 0.25°）</strong>より狭いと取得に失敗しやすいため、
        代表点の<strong>およそ ±0.25°</strong>（環境変数 <code>FARM_AGENT_JAXA_BBOX_HALF_DEG</code>）を既定にしています。
      </p>"""
            elif jx_reason == "llm_agent_fetch_jaxa":
                jaxa_intro = """
      <p class="muted" style="font-size:0.82rem;margin:0 0 10px">
        <strong>自律 LLM エージェント</strong>が <code>fetch_jaxa_gsmap_smc</code> を呼び出し、
        <strong>JAXA Earth API</strong> から取得した結果です。矩形は GSMaP 格子に合わせ <strong>およそ ±0.25°</strong> です。
      </p>"""
            else:
                jaxa_intro = """
      <p class="muted" style="font-size:0.82rem;margin:0 0 10px">
        Sentinel-2（高解像・光学）の根拠が弱いときに、<strong>JAXA Earth API</strong> で
        <strong>GSMaP 日次降水</strong>（マイクロ波＋補正）と <strong>AMSR2 土壌水分（昼）</strong>を
        おおよそ同じ周辺矩形（粗い解像度）で参照した結果です。API のプロトタイプ DB により日付が取れない場合があります。
        矩形は <strong>およそ ±0.25°</strong>（<code>FARM_AGENT_JAXA_BBOX_HALF_DEG</code>）を既定とし、
        格子より狭い領域での取得失敗を避けています。
      </p>"""
            jaxa_body = f"""{jaxa_intro}
      <div class="grid3">
        <div class="metric"><div class="metric-label">GSMaP 期間合計（空間平均の日次合計）</div>
          <div class="metric-value">{gmin}<span class="unit">mm</span></div></div>
        <div class="metric"><div class="metric-label">GSMaP 日平均（日次空間平均の平均）</div>
          <div class="metric-value">{gavg}<span class="unit">mm/日</span></div></div>
        <div class="metric"><div class="metric-label">AMSR2 SMC（期間平均）</div>
          <div class="metric-value">{smc_v}</div></div>
      </div>
      <p class="muted" style="font-size:0.8rem;margin:10px 0 0">
        窓: {_esc(jx.window_start)} 〜 {_esc(jx.window_end)}（{jx.days} 日）· bbox [{b[0]:.4f}, {b[1]:.4f}, {b[2]:.4f}, {b[3]:.4f}] · ppu={jx.ppu}
      </p>
      {jaxa_thumbs}
      {notes_block}"""
        elif jx_reason == "sentinel_weak_jaxa_unavailable":
            jaxa_body = """
      <p class="muted">Sentinel の根拠が弱い状態で JAXA 補完が有効でしたが、
      Python パッケージ <code>jaxa-earth</code> が未インストールです。警告一覧に <code>pip</code> 手順があります。</p>"""
        elif jx_reason == "cli_jaxa_unavailable":
            jaxa_body = """
      <p class="muted"><code>--jaxa</code> を付けましたが、Python パッケージ <code>jaxa-earth</code> が未インストールです。
      警告一覧の <code>pip</code> 手順を実行してください。</p>"""
        else:
            jaxa_body = f"""
      <p class="muted">Sentinel の根拠が弱いため JAXA 補完を試みましたが、
      この実行では結果オブジェクトを得られませんでした（<code>{_esc(str(jx_reason or ""))}</code>）。</p>"""
        jaxa_section = f"""
    <section class="card jaxa-data-card">
      <h2 class="jaxa-h2"><span class="jaxa-h2-badge">JAXA</span> Earth API 補完（GSMaP 降水 · AMSR2 土壌水分）</h2>
      {jaxa_body}
    </section>"""

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

    series: list[tuple[str, float]] = []
    thumb_url: str | None = None
    if result.ndvi:
        series = list(getattr(result.ndvi, "timeseries", None) or [])
        thumb_url = getattr(result.ndvi, "thumb_url", None)

    chart_payload = json.dumps(
        {"labels": [x[0] for x in series], "values": [x[1] for x in series]},
        ensure_ascii=False,
    )
    if series:
        chart_block = f"""
      <h3 class="h3ndvi">NDVI 時系列（シーンごと・ROI 平均）</h3>
      <p class="muted" style="font-size:0.82rem;margin:0 0 8px">横軸: シーン日付（同一日に複数点ある場合は重複通過）。縦軸: NDVI。</p>
      <div class="chart-wrap">
        <canvas id="ndviChart" height="140" aria-label="NDVI chart"></canvas>
      </div>
      <script type="application/json" id="ndvi-series-json">{chart_payload}</script>"""
    else:
        chart_block = """
      <h3 class="h3ndvi">NDVI 時系列</h3>
      <p class="muted">雲フィルタ後のシーンが無い、または時系列の取得に失敗したためグラフを表示できません。</p>"""

    latest_scene_caption = ""
    if latest_scene_date:
        latest_scene_caption = (
            f'<p class="muted" style="font-size:0.82rem;margin:0 0 8px">'
            f'直近で条件を満たした観測の日付（UTC 基準の日付）: <strong>{_esc(latest_scene_date)}</strong>。'
            f"プレビュー画像自体は期間<strong>中央値</strong>合成のため、単一シーンの写真ではありません。</p>"
        )

    thumb_scale_box = """
      <div class="thumb-scale-box">
        <p class="thumb-scale-caption muted">
          <strong>距離の目安</strong>：NDVI の集計は、代表点から<strong>半径約 500 m</strong>の<strong>円</strong>内です（直径はおおよそ<strong>1 km</strong>）。
          上の画像はその円を囲む<strong>長方形</strong>を切り出したものです。色が付いているのは主に円の内側だけで、角付近はデータがマスクされることがあります。
          緯度によって外接矩形の辺の実長は数％変わります。
        </p>
        <svg viewBox="0 0 240 130" width="240" height="130" role="img" aria-label="集計範囲の模式図">
          <title>集計範囲の模式図</title>
          <rect x="8" y="8" width="224" height="114" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="2" rx="4"/>
          <circle cx="120" cy="65" r="48" fill="none" stroke="#22d3ee" stroke-width="2.5" stroke-dasharray="5 4"/>
          <circle cx="120" cy="65" r="3" fill="#fbbf24"/>
          <text x="120" y="124" text-anchor="middle" fill="rgba(232,237,247,0.75)" font-size="11" font-family="system-ui,sans-serif">外接矩形 ≒ 辺 1 km 前後</text>
          <text x="120" y="62" text-anchor="middle" fill="#22d3ee" font-size="10" font-family="system-ui,sans-serif">r≈500m</text>
        </svg>
      </div>"""

    if thumb_url:
        thumb_block = f"""
      <h3 class="h3ndvi">衛星 NDVI プレビュー（期間中央値合成）</h3>
      {latest_scene_caption}
      <p class="muted" style="font-size:0.82rem;margin:0 0 8px">
        画像は<strong>長方形</strong>（集計円の外接範囲）のサムネイルです。Google Earth Engine が疑似カラーで描画しています。白っぽい領域は雲・薄曇の残りやすい見え方のことがあります。
      </p>
      <img class="ndvi-thumb" src="{_esc(thumb_url)}" alt="NDVI median composite preview" loading="lazy" />
      {thumb_scale_box}"""
    else:
        thumb_block = f"""
      <h3 class="h3ndvi">衛星 NDVI プレビュー</h3>
      {latest_scene_caption}
      <p class="muted">サムネイル URL を取得できませんでした（GEE 側の制限やタイムアウトの可能性があります）。</p>"""

    chart_script = ""
    if series:
        chart_script = """
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <script>
  (function () {
    var el = document.getElementById('ndvi-series-json');
    if (!el || typeof Chart === 'undefined') return;
    var payload = JSON.parse(el.textContent);
    var ctx = document.getElementById('ndviChart');
    if (!ctx || !payload.labels.length) return;
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: payload.labels,
        datasets: [{
          label: 'NDVI',
          data: payload.values,
          borderColor: '#22d3ee',
          backgroundColor: 'rgba(34,211,238,0.12)',
          tension: 0.2,
          pointRadius: 3,
          pointHoverRadius: 5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: { legend: { labels: { color: '#e8edf7' } } },
        scales: {
          x: { ticks: { color: '#94a3b8', maxRotation: 45, minRotation: 0 } },
          y: {
            min: -0.2,
            max: 1,
            ticks: { color: '#94a3b8' },
            grid: { color: 'rgba(255,255,255,0.06)' }
          }
        }
      }
    });
  })();
  </script>"""

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
    .satellite-doc {{
      margin: 0 0 14px;
      font-size: 0.88rem;
      color: var(--muted);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      background: rgba(0,0,0,0.18);
    }}
    .satellite-doc summary {{
      cursor: pointer;
      color: var(--accent);
      font-weight: 600;
    }}
    .satellite-doc-body {{ margin-top: 10px; line-height: 1.55; }}
    .satellite-doc-body ul {{ margin: 8px 0 0; padding-left: 1.15rem; }}
    .satellite-doc-body li {{ margin: 5px 0; }}
    .satellite-doc-body strong {{ color: var(--text); }}
    .h3ndvi {{
      font-size: 0.95rem;
      font-weight: 650;
      color: var(--accent2);
      margin: 18px 0 6px;
    }}
    .chart-wrap {{
      position: relative;
      height: 220px;
      margin-top: 8px;
    }}
    .ndvi-thumb {{
      display: block;
      max-width: 100%;
      height: auto;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: #111827;
    }}
    .sentinel-data-card .ndvi-thumb {{
      border: 2px solid rgba(14,165,233,0.55);
    }}
    .thumb-scale-box {{
      margin-top: 14px;
      padding: 14px 14px 12px;
      border-radius: 12px;
      background: rgba(0,0,0,0.22);
      border: 1px solid var(--border);
    }}
    .thumb-scale-box svg {{ display: block; margin: 8px auto 4px; max-width: 100%; height: auto; }}
    .thumb-scale-caption {{ font-size: 0.82rem; line-height: 1.55; margin: 0; }}
    .sentinel-data-card {{
      border: 2px solid rgba(14,165,233,0.88);
      background: linear-gradient(135deg, rgba(56,189,248,0.14), transparent 44%),
                  var(--card);
      box-shadow: inset 0 0 0 1px rgba(14,165,233,0.22),
                  0 0 20px rgba(14,165,233,0.12);
    }}
    .sentinel-data-card h2.sentinel-h2, .sentinel-data-card .sentinel-h2 {{
      color: #7dd3fc;
    }}
    .sentinel-h2-badge {{
      display: inline-block;
      margin-right: 8px;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 750;
      letter-spacing: 0.05em;
      color: #0c4a6e;
      background: linear-gradient(90deg, #0ea5e9, #38bdf8);
    }}
    .jaxa-data-card {{
      border: 2px solid rgba(234,88,12,0.92);
      background: linear-gradient(135deg, rgba(249,115,22,0.16), transparent 44%),
                  var(--card);
      box-shadow: inset 0 0 0 1px rgba(251,146,60,0.28),
                  0 0 22px rgba(234,88,12,0.14);
    }}
    .jaxa-data-card h2.jaxa-h2, .jaxa-data-card .jaxa-h2 {{
      color: #fb923c;
    }}
    .jaxa-h2-badge {{
      display: inline-block;
      margin-right: 8px;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 750;
      letter-spacing: 0.06em;
      color: #0f172a;
      background: linear-gradient(90deg, #f97316, #fb923c);
    }}
    .jaxa-thumb-row {{
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px dashed rgba(249,115,22,0.5);
    }}
    .jaxa-thumb-note {{
      font-size: 0.8rem;
      line-height: 1.5;
      margin: 0 0 14px;
    }}
    .jaxa-fig {{
      margin: 0 0 16px;
    }}
    .jaxa-cap {{
      font-size: 0.78rem;
      margin-bottom: 8px;
      display: block;
    }}
    .jaxa-thumb-img {{
      display: block;
      max-width: min(100%, 380px);
      height: auto;
      border-radius: 10px;
      border: 2px solid rgba(234,88,12,0.85);
      background: #0f172a;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{_esc(result.crop)} — 圃場ダッシュボード</h1>
    <p class="sub">{_esc(place)} · 入力: {_esc(result.location_query)}</p>

    {llm_agent_section}

    {map_section}

    <section class="card">
      <h2>気象（Open-Meteo）</h2>
      {weather_block}
    </section>

    <section class="card sentinel-data-card">
      <h2 class="sentinel-h2"><span class="sentinel-h2-badge">S2</span>衛星 NDVI（Sentinel-2 / GEE）</h2>
      {satellite_doc}
      <div class="metric">
        <div class="metric-label">中央値合成の平均（約500mバッファ）</div>
        <div class="metric-value">{ndvi_label}</div>
      </div>
      <div class="meter-wrap">
        <div class="meter" title="NDVI 0〜1 を%表示"><span></span></div>
        <div class="ndvi-meta">シーン数: {scenes}{latest_scene_meta} · {ndvi_note}</div>
      </div>
      {thumb_block}
      {chart_block}
      {soil_block}
    </section>

    {jaxa_section}

    {err_html}

    <section class="card">
      <h2>管理提案</h2>
      <div class="rec">{rec_body}</div>
    </section>

    <footer>助言は参考用です。現地確認と専門家判断を優先してください。</footer>
  </div>
{chart_script}
</body>
</html>
"""
