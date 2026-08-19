"""
Live Space Data Integration Test Suite
=======================================

Verifies real-time API integrations with:
- CelesTrak GP (General Perturbations) OMM Telemetry API
- NOAA Space Weather Prediction Center (SWPC) Penticton F10.7 Solar Radio Flux
- End-to-end autonomous FCC Part 100 Delta Audit generation from live telemetry
"""

from __future__ import annotations

import pytest

from backend.app.integrations.space_data import (
    LiveSatelliteTelemetry,
    LiveSpaceWeather,
    SpaceDataClient,
    get_space_client,
)
from backend.app.models.satellite import CertStatus, OrbitType, SystemType


@pytest.fixture
def space_client() -> SpaceDataClient:
    return get_space_client()


class TestLiveSpaceDataAPIs:
    """Test live network calls to CelesTrak and NOAA SWPC."""

    def test_live_iss_telemetry_fetch(self, space_client: SpaceDataClient) -> None:
        """Fetch live telemetry for International Space Station (NORAD #25544)."""
        telem = space_client.fetch_live_satellite_telemetry(25544)

        assert isinstance(telem, LiveSatelliteTelemetry)
        assert telem.norad_cat_id == 25544
        assert "ISS" in telem.name.upper() or "ZARYA" in telem.name.upper()

        # Astrodynamic physical sanity checks
        assert 380.0 <= telem.mean_altitude_km <= 450.0, f"Unexpected ISS altitude: {telem.mean_altitude_km}"
        assert 50.0 <= telem.inclination_deg <= 53.0, f"Unexpected ISS inclination: {telem.inclination_deg}"
        assert 90.0 <= telem.orbital_period_min <= 95.0, f"Unexpected ISS period: {telem.orbital_period_min}"
        assert telem.orbit_type == OrbitType.LEO

    def test_live_starlink_telemetry_fetch(self, space_client: SpaceDataClient) -> None:
        """Fetch live telemetry for an active Starlink satellite (NORAD #44714)."""
        telem = space_client.fetch_live_satellite_telemetry(44714)

        assert isinstance(telem, LiveSatelliteTelemetry)
        assert telem.norad_cat_id == 44714
        assert "STARLINK" in telem.name.upper()
        assert 300.0 <= telem.mean_altitude_km <= 650.0
        assert 52.0 <= telem.inclination_deg <= 54.5
        assert telem.orbit_type == OrbitType.LEO

    def test_live_noaa_space_weather_fetch(self, space_client: SpaceDataClient) -> None:
        """Fetch live NOAA Penticton F10.7 Solar Radio Flux index."""
        weather = space_client.fetch_live_space_weather()

        assert isinstance(weather, LiveSpaceWeather)
        # Solar flux physically ranges between 60 sfu (solar min) to 300+ sfu (solar max)
        assert 60.0 <= weather.f107_solar_flux <= 350.0, f"Invalid flux: {weather.f107_solar_flux}"
        assert weather.thermospheric_drag_multiplier > 0.0
        assert weather.solar_activity_level in [
            "LOW (Solar Minimum)",
            "MODERATE",
            "ELEVATED (Solar Maximum)",
            "HIGH / EXTREME",
        ]

    def test_end_to_end_live_autonomous_audit(self, space_client: SpaceDataClient) -> None:
        """Execute a full autonomous FCC Part 100 Delta Audit on real-time Starlink telemetry."""
        audit, telem, weather = space_client.run_live_autonomous_audit(
            44714,
            num_authorized=7500,
            num_deployed=2500,
            smallest_dimension_cm=100.0,
            mass_kg=800.0,
            has_propulsion=True,
            in_processing_round=True,
            federal_bands_requested=False,
            foreign_ownership_pct=5.0,
            is_us_licensed=True,
        )

        # Audit object validation
        assert audit.system_type == SystemType.NGSO_SATELLITE_SYSTEM
        assert audit.trackability_status == CertStatus.PASS
        assert audit.deorbit_status == CertStatus.PASS
        assert audit.bond_delta.part_100_bond_usd > 0
        assert audit.bond_delta.part_100_bond_usd < 10_000_000
        assert audit.fail_count == 0
        assert "STARLINK" in audit.spec.name
