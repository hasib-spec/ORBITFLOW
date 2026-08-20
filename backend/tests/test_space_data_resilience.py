"""
Tests for OrbitFlow 4-Tier Resilient Space Data Integration Engine
==================================================================
Verifies fast online probing, public TLE API fallback, offline verified OMM catalog,
deterministic Keplerian synthesizer, and space weather solar scaling.
"""

import pytest
from backend.app.integrations.space_data import (
    SpaceDataClient,
    TelemetrySource,
    VERIFIED_OMM_CATALOG,
    get_space_client,
)
from backend.app.models.satellite import OrbitType


def test_space_client_singleton():
    client1 = get_space_client()
    client2 = get_space_client()
    assert client1 is client2


def test_tier3_offline_catalog_lookup():
    client = SpaceDataClient()
    # Query Starlink-1007
    telem = client._try_tier3_catalog(44714, "STARLINK-1007")
    assert telem is not None
    assert telem.norad_cat_id == 44714
    assert "STARLINK" in telem.name
    assert telem.provenance == TelemetrySource.VERIFIED_LOCAL_CATALOG
    assert telem.orbit_type == OrbitType.LEO
    assert 500.0 <= telem.mean_altitude_km <= 600.0
    assert 50.0 <= telem.inclination_deg <= 55.0


def test_tier3_name_alias_lookup():
    client = SpaceDataClient()
    # Query ISS by name
    telem = client._try_tier3_catalog(None, "iss")
    assert telem is not None
    assert telem.norad_cat_id == 25544
    assert telem.orbit_type == OrbitType.LEO


def test_tier4_keplerian_synthesizer_arbitrary_id():
    client = SpaceDataClient()
    telem = client._synthesize_keplerian_telemetry(99412, "MY-PROTOTYPE-SAT")
    assert telem.norad_cat_id == 99412
    assert telem.name == "MY-PROTOTYPE-SAT"
    assert telem.provenance == TelemetrySource.KEPLERIAN_SYNTHESIZER
    assert telem.is_synthetic is True
    assert telem.semi_major_axis_km > 6378.137
    assert telem.orbital_period_min > 80.0
    assert telem.mean_motion_rev_day > 0.0


def test_space_weather_nominal_fallback():
    client = SpaceDataClient()
    weather = client.fetch_live_space_weather()
    assert weather.f107_solar_flux > 50.0
    assert weather.thermospheric_drag_multiplier >= 0.7
    assert weather.solar_activity_level is not None


def test_deorbit_lifetime_estimation():
    client = SpaceDataClient()
    weather = client.fetch_live_space_weather()
    
    # 400 km with propulsion should de-orbit quickly (<= 1.5 yrs)
    deorbit_low = client.estimate_deorbit_lifetime(400.0, 0.0001, True, weather)
    assert deorbit_low <= 1.5

    # 750 km without propulsion should take > 10 yrs
    deorbit_high = client.estimate_deorbit_lifetime(750.0, 0.0001, False, weather)
    assert deorbit_high >= 10.0


def test_waterfall_never_crashes_on_unknown_id():
    client = SpaceDataClient()
    # Pass unknown NORAD ID
    telem = client.fetch_live_satellite_telemetry(123456789)
    assert telem is not None
    assert telem.norad_cat_id == 123456789
    assert telem.status_badge is not None
