"""
Tests for OrbitFlow Module 19: Earth Station Nationwide Non-Site Engine
=======================================================================
Verifies Antenna G/T calculations, ITU-R P.618/P.676 atmospheric losses,
Form 312 Schedule B XML export, and 47 CFR § 100.120(f) pre-grant validation.
"""

from datetime import date, timedelta
import pytest

from backend.app.engines.earth_station import (
    AntennaAssemblySpec,
    EarthStationEngine,
    EarthStationRFPhysics,
    PreGrantCertificationEngine,
    ScheduleBGenerator,
    SiteClassification,
    SiteRegistrationData,
    get_earth_station_engine,
)
from backend.app.models.satellite import OrbitType, SatelliteSpec


def test_antenna_gain_and_gt_thermodynamics():
    # 9.0m dish at 19.7 GHz with 65% efficiency
    gain_dbi = EarthStationRFPhysics.calculate_antenna_gain_dbi(
        diameter_m=9.0, frequency_ghz=19.7, efficiency=0.65
    )
    # Expected approx 63.1 dBi
    assert 62.0 <= gain_dbi <= 64.5

    # G/T under clear sky (0.5 dB loss) vs rain faded (5.0 dB loss)
    gt_clear, t_sys_clear = EarthStationRFPhysics.calculate_gt_and_noise_temp(
        rx_gain_dbi=gain_dbi, feed_loss_db=0.45, lna_temp_k=95.0, a_total_db=0.5
    )
    gt_rain, t_sys_rain = EarthStationRFPhysics.calculate_gt_and_noise_temp(
        rx_gain_dbi=gain_dbi, feed_loss_db=0.45, lna_temp_k=95.0, a_total_db=5.0
    )

    assert gt_clear > gt_rain
    assert t_sys_rain > t_sys_clear
    assert 38.0 <= gt_clear <= 43.0


def test_downlink_link_budget_closure():
    calc = EarthStationRFPhysics.evaluate_downlink_budget(
        frequency_ghz=19.7,
        satellite_altitude_km=550.0,
        elevation_deg=25.0,
        sat_eirp_dbw=23.0,
        dish_diameter_m=9.0,
        user_bit_rate_mbps=250.0,
        required_eb_n0_db=6.5,
    )
    assert calc.free_space_loss_db > 170.0
    assert calc.atmospheric_loss_db > 0.1
    assert calc.rain_attenuation_db > 0.1
    assert calc.is_link_closed is True
    assert calc.link_margin_rain_db > 0.0


def test_earth_station_engine_package_and_schedule_b_xml():
    spec = SatelliteSpec(
        name="Starlink Gen2",
        operator_name="SpaceX (Space Exploration Technologies Corp.)",
        orbit_type=OrbitType.LEO,
        altitude_km=530.0,
        inclination_deg=53.0,
        num_authorized=7500,
        num_deployed=5000,
        smallest_dimension_cm=100.0,
        mass_kg=800.0,
    )
    engine = get_earth_station_engine()

    res = engine.generate_earth_station_package(spec)

    assert res.license_callsign == "E260100"
    assert len(res.registered_sites) >= 2
    assert "<Form312ScheduleB" in res.schedule_b_xml
    assert "BringIntoUseTracking" in res.schedule_b_xml
    assert "Cape Canaveral Gateway Core Hub" in res.schedule_b_xml
    assert res.pre_grant_status.is_authorized_pre_grant is True
    assert (res.biu_deadline - date.today()).days == 365
