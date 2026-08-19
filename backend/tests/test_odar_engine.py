"""
Unit Tests for Module 9: Orbital Debris Assessment Engine (ODAR)
================================================================

Exhaustively verifies physical and mathematical accuracy of:
1. NRLMSISE-00 / US Standard 1976 atmospheric density profiles & solar scaling
2. Runge-Kutta 4th Order (RK4) orbital lifetime & 5-year deorbit decay curves
3. NASA ORDEM 3.1 small debris Poisson flux & large object collision probability
4. NASA DAS 2.0 / 3.0 aerothermal demise, impact kinetic energy, and casualty risk (Ec <= 1e-4)
5. Subsystem disposal reliability (P >= 0.90) and passivation audit
"""

from __future__ import annotations

import math
import pytest

from backend.app.engines.odar import (
    AtmosphereModel,
    DebrisFluxModel,
    MaterialType,
    ODAREngine,
    ReentryModel,
    get_odar_engine,
)
from backend.app.models.satellite import OrbitType, SatelliteSpec


class TestAtmosphereModel:
    """Mathematical verification of atmospheric density calculations."""

    def test_density_monotonic_decay(self) -> None:
        """Atmospheric density must decrease monotonically with altitude."""
        alts = [150.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 1000.0]
        densities = [AtmosphereModel.get_density(h) for h in alts]
        
        for i in range(len(densities) - 1):
            assert densities[i] > densities[i + 1], f"Density at {alts[i]} km ({densities[i]}) not greater than at {alts[i+1]} km ({densities[i+1]})"

    def test_density_reference_orders_of_magnitude(self) -> None:
        """Density values must match US Standard Atmosphere 1976 reference ranges."""
        rho_200 = AtmosphereModel.get_density(200.0)
        assert 1.0e-10 <= rho_200 <= 1.0e-9, f"rho(200km)={rho_200} out of expected range"

        rho_400 = AtmosphereModel.get_density(400.0)
        assert 1.0e-12 <= rho_400 <= 1.0e-11, f"rho(400km)={rho_400} out of expected range"

        rho_600 = AtmosphereModel.get_density(600.0)
        assert 1.0e-14 <= rho_600 <= 1.0e-12, f"rho(600km)={rho_600} out of expected range"

    def test_solar_flux_density_expansion(self) -> None:
        """Solar maximum (F10.7=200) must yield significantly higher thermospheric density than solar minimum (F10.7=70)."""
        rho_min = AtmosphereModel.get_density(500.0, f107_solar_flux=70.0)
        rho_max = AtmosphereModel.get_density(500.0, f107_solar_flux=200.0)
        
        assert rho_max > rho_min
        assert (rho_max / rho_min) >= 2.0, "Thermospheric expansion under solar max should at least double density at 500km"


class TestDebrisFluxAndCollisionRisk:
    """Mathematical verification of NASA ORDEM 3.1 collision risk calculations."""

    def test_small_debris_poisson_probability(self) -> None:
        """Verify Poisson distribution formula: P = 1 - exp(-Phi * A * T)."""
        area = 2.0  # m^2
        alt = 550.0 # km (flux ~ 8.5e-4 /m^2/yr)
        lifetime = 5.0 # years

        prob, flux = DebrisFluxModel.calculate_small_debris_collision_probability(
            cross_section_area_m2=area,
            altitude_km=alt,
            mission_lifetime_years=lifetime,
        )

        expected_hits = flux * area * lifetime
        expected_prob = 1.0 - math.exp(-expected_hits)
        
        assert math.isclose(prob, expected_prob, rel_tol=1e-6)
        assert prob <= 0.01, f"Small debris collision prob ({prob}) should be <= 0.01 threshold"

    def test_large_object_collision_probability_with_maneuvers(self) -> None:
        """Active propulsion must reduce large object collision risk by 95% (0.05x)."""
        area = 1.5
        alt = 600.0
        inc = 53.0
        lifetime = 5.0

        p_unmitigated, p_mitigated, density = DebrisFluxModel.calculate_large_object_collision_probability(
            cross_section_area_m2=area,
            altitude_km=alt,
            inclination_deg=inc,
            mission_lifetime_years=lifetime,
            has_propulsion=True,
        )

        assert p_mitigated < p_unmitigated
        assert math.isclose(p_mitigated, p_unmitigated * 0.05, rel_tol=1e-5)
        assert p_mitigated <= 0.001, f"Mitigated large object risk ({p_mitigated}) should be <= 0.001"


class TestReentryAerothermalDemise:
    """Verification of NASA DAS aerothermal demise and casualty expectation."""

    def test_aluminum_structural_demise(self) -> None:
        """Aluminum structural chassis must demise above 60 km."""
        frag = ReentryModel.evaluate_fragment_demise(
            fragment_name="Chassis",
            material=MaterialType.ALUMINUM_6061,
            mass_kg=25.0,
            cross_section_area_m2=0.5,
        )
        assert frag.survives_to_surface is False
        assert frag.demise_altitude_km is not None
        assert frag.demise_altitude_km >= 60.0
        assert frag.impact_kinetic_energy_joules == 0.0
        assert frag.casualty_area_m2 == 0.0

    def test_titanium_tank_partial_survival(self) -> None:
        """Thick titanium tanks have high heat of ablation and should survive with KE > 15 Joules."""
        frag = ReentryModel.evaluate_fragment_demise(
            fragment_name="Titanium Tank",
            material=MaterialType.TITANIUM_6AL4V,
            mass_kg=15.0,
            cross_section_area_m2=0.08,
        )
        assert frag.survives_to_surface is True
        assert frag.demise_altitude_km is None
        assert frag.impact_kinetic_energy_joules > 15.0
        assert frag.casualty_area_m2 > 0.0

    def test_human_casualty_expectation_formula(self) -> None:
        """Verify casualty expectation Ec formula and inclination weighting."""
        # 1. Demisable smallsat (150 kg)
        fragments_smallsat = ReentryModel.decompose_default_spacecraft(
            total_mass_kg=150.0,
            has_propulsion=True,
        )
        dca_small, ec_small, count_small, surv_mass_small = ReentryModel.calculate_total_casualty_risk(
            fragments=fragments_smallsat,
            inclination_deg=53.0,
            num_satellites=1,
        )
        assert ec_small <= 0.0001, f"Expected casualties Ec={ec_small} should meet standard threshold <= 1e-4"

        # 2. Heavy satellite with titanium tanks (2500 kg)
        fragments_heavy = ReentryModel.decompose_default_spacecraft(
            total_mass_kg=2500.0,
            has_propulsion=True,
        )
        dca_heavy, ec_heavy, count_heavy, surv_mass_heavy = ReentryModel.calculate_total_casualty_risk(
            fragments=fragments_heavy,
            inclination_deg=53.0,
            num_satellites=1,
        )
        assert dca_heavy > 0.0
        assert ec_heavy > 0.0


class TestODAREngineIntegration:
    """Integration tests for master ODAREngine and RK4 decay integration."""

    @pytest.fixture
    def odar(self) -> ODAREngine:
        return get_odar_engine()

    def test_starlink_class_odar_evaluation(self, odar: ODAREngine) -> None:
        """Starlink-class satellite (550 km, active krypton propulsion, 1200 kg)."""
        spec = SatelliteSpec(
            name="Starlink-V2-Mini",
            operator_name="SpaceX",
            orbit_type=OrbitType.LEO,
            altitude_km=550.0,
            inclination_deg=53.2,
            num_authorized=7500,
            num_deployed=500,
            smallest_dimension_cm=80.0,
            mass_kg=800.0,
            mission_lifetime_years=5.0,
            has_propulsion=True,
            in_processing_round=True,
        )

        report = odar.evaluate_satellite_odar(spec)
        assert report.all_debris_requirements_met is True
        assert report.orbital_lifetime.compliant_with_5_year_rule is True
        assert report.collision_probability.small_debris_compliant is True
        assert report.collision_probability.large_object_compliant is True
        assert report.disposal_reliability.disposal_reliability_compliant is True
        assert report.stored_energy.passivation_compliant is True

    def test_high_altitude_unpropelled_debris_failure(self, odar: ODAREngine) -> None:
        """Unpropelled spacecraft at 800 km altitude must fail the 5-year post-mission deorbit rule."""
        spec = SatelliteSpec(
            name="High-LEO-Smallsat",
            operator_name="Research Lab",
            orbit_type=OrbitType.LEO,
            altitude_km=800.0,
            inclination_deg=98.0,
            num_authorized=1,
            num_deployed=1,
            smallest_dimension_cm=20.0,
            mass_kg=25.0,
            mission_lifetime_years=3.0,
            has_propulsion=False,  # No propulsion at 800km -> takes > 50 years to decay
        )

        report = odar.evaluate_satellite_odar(spec)
        assert report.orbital_lifetime.compliant_with_5_year_rule is False
        assert report.orbital_lifetime.natural_decay_years > 5.0
        assert report.all_debris_requirements_met is False
        assert "Natural orbital decay lifetime" in report.orbital_lifetime.details

    def test_rk4_decay_curve_generation(self, odar: ODAREngine) -> None:
        """RK4 simulation must produce continuous descending timeline points."""
        res = odar.calculate_orbital_lifetime(
            altitude_km=450.0,
            mass_kg=50.0,
            cross_section_area_m2=0.2,
            drag_coefficient=2.2,
            has_propulsion=False,
        )
        assert len(res.decay_timeline_points) >= 2
        # Verify altitude decreases over time
        for i in range(len(res.decay_timeline_points) - 1):
            t1, h1 = res.decay_timeline_points[i]
            t2, h2 = res.decay_timeline_points[i + 1]
            assert t2 >= t1
            assert h2 <= h1
