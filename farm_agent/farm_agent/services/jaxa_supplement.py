"""JAXA Earth API による GSMaP（降水）・AMSR2 SMC（土壌水分）の補完取得。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

try:
    from jaxa.earth import je as _je

    JAXA_EARTH_AVAILABLE = True
except ImportError:
    _je = None  # type: ignore[assignment]
    JAXA_EARTH_AVAILABLE = False

# 公式ドキュメント・データセット ID（JAXA Earth API）
GSMaP_DAILY_COLLECTION = "JAXA.EORC_GSMaP_standard.Gauge.00Z-23Z.v6_daily"
GSMaP_DAILY_BAND = "PRECIP"
SMC_DAILY_COLLECTION = "JAXA.G-Portal_GCOM-W.AMSR2_standard.L3-SMC.daytime.v3_global_daily"
SMC_DAILY_BAND = "SMC"


@dataclass
class JaxaSupplementSummary:
    """圃場周辺 bbox・期間内の、日次画像ごとの空間平均を時系列にした要約。"""

    precip_mean_daily_mm: float | None
    precip_sum_mm: float | None
    smc_mean: float | None
    window_start: str
    window_end: str
    bbox: tuple[float, float, float, float]
    days: int
    ppu: int
    source: str
    notes: list[str] = field(default_factory=list)
    # 期間平均合成ラスタのプレビュー（data:image/png;base64,...）。JAXA Earth API に URL サムネは無く自前生成。
    precip_thumb_data_uri: str | None = None
    smc_thumb_data_uri: str | None = None


def jaxa_supplement_enabled() -> bool:
    v = os.environ.get("FARM_AGENT_USE_JAXA", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _ssl_verify() -> bool:
    return os.environ.get("FARM_AGENT_JAXA_SSL_VERIFY", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _jaxa_days_default() -> int:
    raw = os.environ.get("FARM_AGENT_JAXA_DAYS", "30").strip()
    try:
        n = int(raw)
    except ValueError:
        return 30
    return max(3, min(n, 120))


def _jaxa_ppu() -> int:
    raw = os.environ.get("FARM_AGENT_JAXA_PPU", "8").strip()
    try:
        p = int(raw)
    except ValueError:
        return 8
    return max(4, min(p, 32))


def _jaxa_bbox_half_deg() -> float:
    """GSMaP は約 0.25° 格子。それより狭い bbox だと jaxa-earth が get_images 内で失敗することがある。"""
    raw = os.environ.get("FARM_AGENT_JAXA_BBOX_HALF_DEG", "0.25").strip()
    try:
        h = float(raw)
    except ValueError:
        return 0.25
    return max(0.12, min(h, 2.0))


def bbox_around_point(lat: float, lon: float, half_deg: float | None = None) -> tuple[float, float, float, float]:
    """[min_lon, min_lat, max_lon, max_lat]。GSMaP は概ね 60°N–60°S。"""
    h = _jaxa_bbox_half_deg() if half_deg is None else float(half_deg)
    return (
        max(-180.0, float(lon) - h),
        max(-90.0, float(lat) - h),
        min(180.0, float(lon) + h),
        min(90.0, float(lat) + h),
    )


def _dlim_utc(start: date, end: date) -> list[str]:
    return [f"{start.isoformat()}T00:00:00", f"{end.isoformat()}T00:00:00"]


def _jaxa_thumbs_enabled() -> bool:
    return os.environ.get("FARM_AGENT_JAXA_THUMB", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _raster_to_png_data_uri(img, cmap: str = "viridis") -> str | None:
    """ラスタを PNG の data URI にする（HTML 埋め込み用）。"""
    try:
        import base64
        import io

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return None

    a = np.asarray(img, dtype=float).squeeze()
    if a.ndim != 2 or a.size == 0:
        return None
    a = np.where(np.isfinite(a), a, np.nan)
    if not np.any(np.isfinite(a)):
        return None
    vmin = float(np.nanpercentile(a, 2))
    vmax = float(np.nanpercentile(a, 98))
    if vmax <= vmin:
        vmax = vmin + 1e-9

    fig, ax = plt.subplots(figsize=(3.4, 3.4), dpi=140)
    im = ax.imshow(a, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto", interpolation="nearest")
    ax.set_title("Temporal mean (coarse grid)", fontsize=8, color="#444")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white", pad_inches=0.08)
    plt.close(fig)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _layer_series_and_optional_thumb(
    collection: str,
    band: str,
    dlim: list[str],
    bbox: tuple[float, float, float, float],
    ppu: int,
    ssl_verify: bool,
    thumb_cmap: str,
):
    """日次スタックから空間平均時系列＋任意で期間平均合成のサムネ。"""
    import numpy as np

    if _je is None:
        raise RuntimeError("jaxa_earth_not_imported")
    data = (
        _je.ImageCollection(collection=collection, ssl_verify=ssl_verify)
        .filter_date(dlim=dlim)
        .filter_resolution(ppu=ppu)
        .filter_bounds(bbox=list(bbox))
        .select(band=band)
        .get_images()
    )
    proc_s = _je.ImageProcess(data).calc_spatial_stats()
    arr = np.asarray(proc_s.timeseries["mean"], dtype=float)
    thumb_uri: str | None = None
    if _jaxa_thumbs_enabled():
        try:
            proc_t = _je.ImageProcess(data).calc_temporal_stats("mean")
            thumb_uri = _raster_to_png_data_uri(getattr(proc_t.raster, "img", None), cmap=thumb_cmap)
        except Exception:
            thumb_uri = None
    return arr, thumb_uri


def _spatial_mean_timeseries(
    collection: str,
    band: str,
    dlim: list[str],
    bbox: tuple[float, float, float, float],
    ppu: int,
    ssl_verify: bool,
):
    """サムネ無しで時系列のみ（API 取得1回・軽量）。"""
    import numpy as np

    if _je is None:
        raise RuntimeError("jaxa_earth_not_imported")
    data = (
        _je.ImageCollection(collection=collection, ssl_verify=ssl_verify)
        .filter_date(dlim=dlim)
        .filter_resolution(ppu=ppu)
        .filter_bounds(bbox=list(bbox))
        .select(band=band)
        .get_images()
    )
    proc = _je.ImageProcess(data).calc_spatial_stats()
    return np.asarray(proc.timeseries["mean"], dtype=float)


def _aggregate_daily_series(arr) -> tuple[float | None, float | None]:
    import numpy as np

    a = np.asarray(arr, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None, None
    return float(np.mean(a)), float(np.sum(a))


def fetch_jaxa_supplement(lat: float, lon: float, days: int | None = None) -> JaxaSupplementSummary | None:
    """GSMaP 日次・AMSR2 SMC 日次を同一 bbox・期間で取得し要約する。"""
    if not JAXA_EARTH_AVAILABLE:
        return None
    d = days if days is not None else _jaxa_days_default()
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=d)
    bbox = bbox_around_point(lat, lon)
    ppu = _jaxa_ppu()
    ssl_verify = _ssl_verify()
    notes: list[str] = []

    if abs(lat) > 59.5:
        notes.append("緯度が GSMaP の対象外に近いため、降水は未取得としました。")

    precip_mean = precip_sum = None
    smc_mean = None
    precip_thumb: str | None = None
    smc_thumb: str | None = None

    if abs(lat) <= 59.5:
        try:
            arr_p, precip_thumb = _layer_series_and_optional_thumb(
                GSMaP_DAILY_COLLECTION,
                GSMaP_DAILY_BAND,
                _dlim_utc(start, end),
                bbox,
                ppu,
                ssl_verify,
                thumb_cmap="Blues",
            )
            precip_mean, precip_sum = _aggregate_daily_series(arr_p)
            if arr_p.size == 0:
                notes.append("GSMaP: 期間内に有効ピクセルが無かった、または API がデータを返しませんでした。")
        except Exception as e:
            notes.append(f"GSMaP 取得エラー: {e}")

    try:
        arr_s, smc_thumb = _layer_series_and_optional_thumb(
            SMC_DAILY_COLLECTION,
            SMC_DAILY_BAND,
            _dlim_utc(start, end),
            bbox,
            ppu,
            ssl_verify,
            thumb_cmap="BrBG",
        )
        smc_mean, _ = _aggregate_daily_series(arr_s)
        if arr_s.size == 0:
            notes.append("SMC: 期間内に有効ピクセルが無かった、または API がデータを返しませんでした。")
    except Exception as e:
        notes.append(f"SMC 取得エラー: {e}")

    if precip_mean is None and precip_sum is None and smc_mean is None and not notes:
        notes.append("JAXA: 値を集計できませんでした。")

    return JaxaSupplementSummary(
        precip_mean_daily_mm=precip_mean,
        precip_sum_mm=precip_sum,
        smc_mean=smc_mean,
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        bbox=bbox,
        days=d,
        ppu=ppu,
        source="jaxa_earth_gsmap_smc",
        notes=notes,
        precip_thumb_data_uri=precip_thumb,
        smc_thumb_data_uri=smc_thumb,
    )
