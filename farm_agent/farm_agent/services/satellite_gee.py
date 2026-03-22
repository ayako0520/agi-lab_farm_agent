"""Sentinel-2 NDVI via Google Earth Engine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class NdviSummary:
    mean_ndvi: float | None
    image_count: int
    days: int
    source: str
    note: str


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
    return NdviSummary(
        mean_ndvi=mean_f,
        image_count=count,
        days=days,
        source="gee_sentinel2",
        note="median_ndvi_roi_500m",
    )
