# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from __future__ import annotations

from datetime import datetime, timezone

from astral import Observer
from astral.sun import azimuth as sun_azimuth
from astral.sun import elevation as sun_elevation

# Uniform shade fraction when the sun is below the horizon (all edges equally shaded).
NIGHT_UNIFORM_SHADE = 1.0


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def sun_altitude_deg(dt: datetime, lat: float, lng: float) -> float:
    """Solar elevation in degrees at ``(lat, lng)`` (negative = below horizon)."""
    dt = ensure_utc(dt)
    obs = Observer(latitude=lat, longitude=lng)
    return float(sun_elevation(obs, dt))


def sun_azimuth_deg(dt: datetime, lat: float, lng: float) -> float:
    """Solar azimuth in degrees clockwise from north at ``(lat, lng)``."""
    dt = ensure_utc(dt)
    obs = Observer(latitude=lat, longitude=lng)
    return float(sun_azimuth(obs, dt))


def is_sun_below_horizon(dt: datetime, lat: float, lng: float) -> bool:
    return sun_altitude_deg(dt, lat, lng) <= 0.0


def is_route_at_night(
    dt: datetime,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> bool:
    """
    True when the sun is down for the whole trip (both endpoints below horizon).

    When true, shade routing should use uniform full shade so coolest == shortest.
    """
    return is_sun_below_horizon(dt, origin_lat, origin_lng) and is_sun_below_horizon(
        dt, dest_lat, dest_lng
    )
