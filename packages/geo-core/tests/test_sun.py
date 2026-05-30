from datetime import datetime, timezone

from umbrastride_geo.sun import (
    is_route_at_night,
    is_sun_below_horizon,
    sun_altitude_deg,
    sun_azimuth_deg,
)

# Phoenix area
PHX_LAT = 33.45
PHX_LNG = -112.07


def test_sun_above_horizon_noon_utc():
    dt = datetime(2026, 6, 21, 18, 0, tzinfo=timezone.utc)  # ~11am MST
    assert sun_altitude_deg(dt, PHX_LAT, PHX_LNG) > 5.0
    assert not is_sun_below_horizon(dt, PHX_LAT, PHX_LNG)


def test_sun_azimuth_is_clockwise_from_north():
    morning = datetime(2026, 6, 21, 16, 0, tzinfo=timezone.utc)  # ~9am MST
    afternoon = datetime(2026, 6, 21, 22, 0, tzinfo=timezone.utc)  # ~3pm MST

    assert 60.0 < sun_azimuth_deg(morning, PHX_LAT, PHX_LNG) < 180.0
    assert 180.0 < sun_azimuth_deg(afternoon, PHX_LAT, PHX_LNG) < 300.0


def test_sun_below_horizon_midnight_utc():
    dt = datetime(2026, 6, 21, 8, 0, tzinfo=timezone.utc)  # ~1am MST
    assert sun_altitude_deg(dt, PHX_LAT, PHX_LNG) < 0.0
    assert is_sun_below_horizon(dt, PHX_LAT, PHX_LNG)


def test_route_at_night_both_endpoints():
    dt = datetime(2026, 6, 21, 8, 0, tzinfo=timezone.utc)
    assert is_route_at_night(dt, PHX_LAT, PHX_LNG, PHX_LAT + 0.01, PHX_LNG + 0.01)


def test_route_not_at_night_if_one_endpoint_day():
    dt = datetime(2026, 6, 21, 18, 0, tzinfo=timezone.utc)
    assert not is_route_at_night(dt, PHX_LAT, PHX_LNG, PHX_LAT, PHX_LNG)
