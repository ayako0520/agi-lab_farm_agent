"""Geocode free-text location (Nominatim)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim


@dataclass
class GeocodeResult:
    lat: float
    lon: float
    display_name: str
    source: str


def _parse_lat_lon(text: str) -> GeocodeResult | None:
    text = text.strip()
    m = re.match(
        r"^\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)\s*$",
        text,
    )
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return GeocodeResult(lat=lat, lon=lon, display_name=f"{lat}, {lon}", source="coordinates")


def geocode_location(query: str, timeout: float = 12.0) -> GeocodeResult:
    direct = _parse_lat_lon(query)
    if direct:
        return direct

    geolocator = Nominatim(
        user_agent="farm_agent_hackathon_mvp/0.1 (educational)",
        timeout=timeout,
    )
    try:
        loc = geolocator.geocode(query)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        raise RuntimeError(f"geocode_failed: {e}") from e
    if loc is None:
        raise RuntimeError("geocode_failed: no results")
    return GeocodeResult(
        lat=float(loc.latitude),
        lon=float(loc.longitude),
        display_name=loc.address or query,
        source="nominatim",
    )
