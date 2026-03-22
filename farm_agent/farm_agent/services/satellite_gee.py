"""Sentinel-2 NDVI via Google Earth Engine."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class NdviSummary:
    mean_ndvi: float | None
    image_count: int
    days: int
    source: str
    note: str
    # (YYYY-MM-DD, mean_ndvi) 雲フィルタ後の各シーン（重複日はそのまま複数点になり得る）
    timeseries: list[tuple[str, float]] = field(default_factory=list)
    # 期間中央値 NDVI の疑似カラー PNG（GEE getThumbURL）
    thumb_url: str | None = None
    # 雲フィルタ後コレクションに含まれる「最も新しいシーン」の観測日（YYYY-MM-DD）
    latest_scene_date: str | None = None


def fetch_ndvi_sentinel2(lat: float, lon: float, days: int = 60) -> NdviSummary:
    import ee

    project = (
        os.environ.get("EARTHENGINE_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("EE_PROJECT_ID")
        or ""
    ).strip()
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
    except Exception as e:
        raise RuntimeError(f"ee_init_failed: {e}") from e
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    point = ee.Geometry.Point([float(lon), float(lat)])
    roi = point.buffer(500)

    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(str(start), str(end))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 35))
    )

    def add_ndvi(img: ee.Image) -> ee.Image:
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        return img.addBands(ndvi)

    with_ndvi = col.map(add_ndvi).select("NDVI")
    count = int(col.size().getInfo() or 0)
    if count == 0:
        return NdviSummary(
            mean_ndvi=None,
            image_count=0,
            days=days,
            source="gee_sentinel2",
            note="no_cloud_filtered_images",
        )

    def image_to_ndvi_row(img):
        ndvi_img = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        stat = ndvi_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=20,
            maxPixels=1_000_000_000,
            bestEffort=True,
        )
        return ee.Feature(
            None,
            {
                "NDVI": stat.get("NDVI"),
                "date": img.date().format("YYYY-MM-dd"),
            },
        )

    fc = ee.FeatureCollection(col.map(image_to_ndvi_row))
    series: list[tuple[str, float]] = []
    try:
        raw = fc.getInfo()
        for ft in raw.get("features") or []:
            p = ft.get("properties") or {}
            d = p.get("date")
            v = p.get("NDVI")
            if d and v is not None:
                try:
                    series.append((str(d), float(v)))
                except (TypeError, ValueError):
                    pass
        series.sort(key=lambda x: x[0])
    except Exception:
        series = []

    latest_scene_date: str | None = series[-1][0] if series else None
    if latest_scene_date is None and count > 0:
        try:
            latest_scene_date = (
                ee.Image(col.sort("system:time_start", False).first())
                .date()
                .format("YYYY-MM-dd")
                .getInfo()
            )
        except Exception:
            latest_scene_date = None

    composite = with_ndvi.median().clip(roi)
    stats = composite.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=20,
        maxPixels=1_000_000_000,
        bestEffort=True,
    ).getInfo()

    mean = stats.get("NDVI")
    mean_f = float(mean) if mean is not None else None

    thumb_url: str | None = None
    try:
        thumb_rgb = composite.select("NDVI").visualize(
            min=-0.2,
            max=0.8,
            palette=[
                "#543005",
                "#bf812d",
                "#dfc27d",
                "#f6e8c3",
                "#c7eae5",
                "#80cdc1",
                "#35978f",
                "#01665e",
            ],
        )
        # 円だけだと縮尺が伝わりにくいので、集計円の外接矩形を切り出し（辺 ≈ 直径 1km 前後）
        thumb_region = roi.bounds()
        thumb_url = thumb_rgb.getThumbURL(
            {
                "region": thumb_region,
                "dimensions": 520,
                "format": "png",
                "crs": "EPSG:4326",
            }
        )
    except Exception:
        thumb_url = None

    return NdviSummary(
        mean_ndvi=mean_f,
        image_count=count,
        days=days,
        source="gee_sentinel2",
        note="median_ndvi_roi_500m",
        timeseries=series,
        thumb_url=thumb_url,
        latest_scene_date=latest_scene_date,
    )
