"""
Unit and Physical Verification Tests for Module 10 (Spectrum & EPFD Engine)
===========================================================================
Mathematically and physically tests slant range kinematics, ITU-R P.676 atmospheric absorption,
ITU-R S.1428 antenna gain envelopes, § 100.212 stepped PFD masks, ITU Article 22 EPFD, and § 100.280 off-axis EIRP.
"""

import math
import pytest

from backend.app.engines.epfd.models import (
    FrequencyBand,
    FrequencyChannelConfig,
    LinkDirection,
    Polarization,
)
from backend.app.engines.epfd.propagation import (
    R_EARTH_KM,
    calculate_atmospheric_loss,
    calculate_free_space_loss,
    calculate_slant_range,
)
from backend.app.engines.epfd.antenna import (
    calculate_itu_s1428_gain,
    evaluate_off_axis_eirp_density,
)
from backend.app.engines.epfd.engine import SpectrumEngine, get_spectrum_engine
from backend.app.models.satellite import OrbitType, SatelliteSpec


class TestSlantRangeAndPropagationPhysics:
    """Rigorous geometric and propagation model validation."""

    def test_slant_range_zenith_and_horizon_boundary_conditions(self):
        """Proves d(90 deg) == h and d(0 deg) == sqrt(2*R_E*h + h^2)."""
        altitude_km = 550.0

        # Zenith (delta = 90 deg)
        geom_zenith = calculate_slant_range(90.0, altitude_km)
        assert pytest.approx(geom_zenith.slant_range_km, rel=1e-3) == altitude_km
        assert geom_zenith.satellite_off_nadir_deg == 0.0

        # Horizon (delta = 0 deg)
        geom_horizon = calculate_slant_range(0.0, altitude_km)
        expected_horizon = math.sqrt(2.0 * R_EARTH_KM * altitude_km + altitude_km ** 2)
        assert pytest.approx(geom_horizon.slant_range_km, rel=1e-3) == expected_horizon

    def test_slant_range_numerical_stability_near_zenith(self):
        """Verifies IEEE-754 rationalized form avoids cancellation at delta = 89.999 deg."""
        altitude_km = 400.0
        geom = calculate_slant_range(89.999, altitude_km)
        assert geom.slant_range_km >= altitude_km
        assert pytest.approx(geom.slant_range_km, rel=1e-3) == altitude_km

    def test_free_space_loss_exact_values(self):
        """Verifies L_bf = 92.4478 + 20*log10(d) + 20*log10(f)."""
        # d = 1000 km, f = 10 GHz -> L_bf = 92.4478 + 60.0 + 20.0 = 172.4478 dB
        fsl = calculate_free_space_loss(1000.0, 10.0)
        assert pytest.approx(fsl, abs=0.05) == 172.45

    def test_atmospheric_loss_frequency_resonance(self):
        """Verifies ITU-R P.676 gaseous absorption and water vapor peak."""
        # 12 GHz Ku-band loss should be small (< 0.5 dB at 30 deg elevation)
        a_ku = calculate_atmospheric_loss(12.0, 30.0)
        assert 0.02 <= a_ku <= 0.60

        # 22.235 GHz water vapor peak should produce higher attenuation than 12 GHz
        a_water = calculate_atmospheric_loss(22.235, 30.0)
        assert a_water > a_ku

        # Near-horizon elevation (5 deg) should have significantly higher path attenuation
        a_low_elev = calculate_atmospheric_loss(20.0, 5.0)
        a_zenith = calculate_atmospheric_loss(20.0, 90.0)
        assert a_low_elev > a_zenith


class TestAntennaAndInterferenceEnvelopes:
    """Antenna gain patterns and regulatory masks."""

    def test_itu_s1428_antenna_gain_pattern(self):
        """Verifies ITU-R S.1428 on-axis peak gain and off-axis sidelobe roll-off."""
        dish_diameter_m = 1.2
        freq_ghz = 20.0  # Ka-band

        # Boresight peak gain (theta = 0 deg)
        gain_on_axis, g_max = calculate_itu_s1428_gain(0.0, dish_diameter_m, freq_ghz)
        assert gain_on_axis == g_max
        assert g_max > 40.0  # 1.2m dish at 20 GHz has >40 dBi gain

        # Sidelobe region (theta = 10 deg)
        gain_sidelobe, _ = calculate_itu_s1428_gain(10.0, dish_diameter_m, freq_ghz)
        assert gain_sidelobe < gain_on_axis
        # 29 - 25*log10(10) = 29 - 25 = 4.0 dBi
        assert pytest.approx(gain_sidelobe, abs=1.0) == 4.0

        # Far sidelobes (theta = 60 deg) -> -10 dBi floor
        gain_far, _ = calculate_itu_s1428_gain(60.0, dish_diameter_m, freq_ghz)
        assert gain_far == -10.0

    def test_off_axis_eirp_two_degree_spacing(self):
        """Verifies 47 CFR § 100.280 (§ 25.218) 2-degree spacing mask."""
        # Ku-band at theta = 2.0 deg: limit = 15 - 25*log10(2.0) = 7.47 dB(W/4kHz)
        res_pass = evaluate_off_axis_eirp_density(
            theta_deg=2.0,
            actual_eirp_density_dbw=5.0,  # below 7.47 dBW
            band=FrequencyBand.KU_BAND,
        )
        assert res_pass.two_degree_spacing_compliant is True
        assert res_pass.copolar_compliant is True

        res_fail = evaluate_off_axis_eirp_density(
            theta_deg=2.0,
            actual_eirp_density_dbw=12.0,  # exceeds 7.47 dBW
            band=FrequencyBand.KU_BAND,
        )
        assert res_fail.two_degree_spacing_compliant is False
        assert res_fail.copolar_compliant is False


class TestSpectrumEngineMasterEvaluation:
    """Master Spectrum & EPFD Engine validation."""

    @pytest.fixture
    def sample_leo_spec(self) -> SatelliteSpec:
        return SatelliteSpec(
            name="Aetheris Broadband",
            operator_name="Aetheris Space Corp",
            orbit_type=OrbitType.LEO,
            altitude_km=550.0,
            inclination_deg=53.0,
            num_authorized=720,
            num_deployed=60,
            smallest_dimension_cm=85.0,
            mass_kg=350.0,
            mission_lifetime_years=5.0,
            has_propulsion=True,
            estimated_deorbit_years=2.2,
        )

    def test_pfd_mask_compliance(self, sample_leo_spec):
        """Verifies PFD mask calculation across all angles of arrival."""
        engine = SpectrumEngine()
        ch = FrequencyChannelConfig(
            channel_id="CH-TEST-KA",
            direction=LinkDirection.TRANSMIT,
            band=FrequencyBand.KA_BAND,
            center_frequency_mhz=19950.0,
            bandwidth_mhz=500.0,
            max_eirp_density_dbw_mhz=-5.0,
        )
        pfd_res = engine.evaluate_pfd_mask(sample_leo_spec.altitude_km, ch)
        assert pfd_res.is_fully_compliant is True
        assert pfd_res.min_margin_db > 0.0
        assert len(pfd_res.data_points) >= 10

    def test_epfd_downlink_aggregate_evaluation(self, sample_leo_spec):
        """Verifies aggregate downlink EPFD calculation meets ITU Article 22 limits."""
        engine = SpectrumEngine()
        ch = FrequencyChannelConfig(
            channel_id="CH-TEST-KU",
            direction=LinkDirection.TRANSMIT,
            band=FrequencyBand.KU_BAND,
            center_frequency_mhz=11950.0,
            bandwidth_mhz=500.0,
            max_eirp_density_dbw_mhz=-10.0,
        )
        epfd_res = engine.evaluate_epfd_downlink(
            altitude_km=sample_leo_spec.altitude_km,
            num_satellites_visible=12,
            channel=ch,
            gso_dish_diameter_m=1.2,
        )
        assert epfd_res.compliant is True
        assert epfd_res.margin_db > 0.0
        assert len(epfd_res.satellite_breakdown) == 12

    def test_master_spectrum_report_generation(self, sample_leo_spec):
        """Verifies master spectrum evaluation returns fully populated SpectrumSharingReport."""
        engine = get_spectrum_engine()
        report = engine.evaluate_satellite_spectrum(sample_leo_spec)

        assert report.report_id.startswith("SPEC-")
        assert report.system_name == "Aetheris Broadband"
        assert len(report.channels_analyzed) >= 2
        assert len(report.pfd_analysis) >= 1
        assert report.epfd_downlink_analysis is not None
        assert report.all_spectrum_requirements_met is True
        assert "FULL SPECTRUM COMPLIANCE" in report.summary_verdict
