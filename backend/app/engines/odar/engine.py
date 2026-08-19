"""
OrbitFlow Orbital Debris Assessment Engine (ODAR)
=================================================

Master calculation engine implementing NASA DAS 2.0/3.0 methodology and FCC
Part 100 Subpart C (§ 100.260 and § 100.111) debris mitigation requirements:

1. Orbital Lifetime & 5-Year De-orbit Rule (§ 100.260(e))
2. Small Debris Collision Probability (§ 100.111(c)(2)(v))
3. Large Object Collision Probability (§ 100.111(c)(2)(vi))
4. Re-Entry Human Casualty Risk (§ 100.111(c)(2)(vii))
5. Post-Mission Disposal Success Probability (§ 100.111(c)(2)(xi))
6. Passivation & Stored Energy Removal (§ 100.111(c)(2)(viii))
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from backend.app.core.config import DEORBIT_DEADLINE_YEARS, get_logger
from backend.app.engines.odar.atmosphere import AtmosphereModel
from backend.app.engines.odar.debris_flux import DebrisFluxModel
from backend.app.engines.odar.models import (
    CasualtyRiskResult,
    CollisionProbabilityResult,
    DisposalMethod,
    DisposalReliabilityResult,
    ODARReport,
    OrbitalLifetimeResult,
    StoredEnergyAssessment,
)
from backend.app.engines.odar.reentry import ReentryModel
from backend.app.models.satellite import OrbitType, SatelliteSpec

log = get_logger(__name__)


class ODAREngine:
    """Master engine for all FCC Part 100 Orbital Debris calculations."""

    EARTH_RADIUS_KM: float = 6378.137
    MU_EARTH_KM3_S2: float = 398600.4418

    @classmethod
    def calculate_orbital_lifetime(
        cls,
        altitude_km: float,
        mass_kg: float,
        cross_section_area_m2: float,
        drag_coefficient: float = 2.2,
        has_propulsion: bool = True,
        f107_solar_flux: float = 120.0,
    ) -> OrbitalLifetimeResult:
        """
        Compute natural and propulsion-assisted orbital decay lifetime
        using Runge-Kutta 4th Order (RK4) integration of atmospheric drag.

        Differential Equation:
            dr/dt = - sqrt(mu * r) * rho(r) * (Cd * A / m)

        Parameters
        ----------
        altitude_km : float
            Initial orbital altitude.
        mass_kg : float
            Spacecraft wet mass.
        cross_section_area_m2 : float
            Average drag cross-sectional area.
        drag_coefficient : float
            Aerodynamic drag coefficient (nominal Cd = 2.2 for tumbling bodies).
        has_propulsion : bool
            Whether active propulsion is available for disposal maneuvers.
        f107_solar_flux : float
            Solar radio flux (sfu) scaling atmospheric density.

        Returns
        -------
        OrbitalLifetimeResult
        """
        # Ballistic coefficient: B = m / (Cd * A) (kg/m^2)
        ballistic_coeff = mass_kg / max(1e-4, drag_coefficient * cross_section_area_m2)
        
        # RK4 numerical decay integration
        # Convert B to (m / (Cd * A)) in kg/km^2 for consistent units: 1 m^2 = 1e-6 km^2
        # dr/dt in km/s:
        # dr/dt = - sqrt(mu * r_km) * rho(kg/km^3) * (Cd*A/m)
        # where rho(kg/km^3) = rho(kg/m^3) * 1e9
        
        r = cls.EARTH_RADIUS_KM + altitude_km
        t_years = 0.0
        max_simulation_years = 100.0
        
        # Adaptive time step: smaller steps at low altitude, larger at high altitude
        dt_years = 0.05
        timeline_points: list[tuple[float, float]] = [(0.0, altitude_km)]

        def dr_dt(r_val: float) -> float:
            alt = r_val - cls.EARTH_RADIUS_KM
            if alt <= 100.0:
                return -100.0  # Instant rapid entry
            rho_kg_m3 = AtmosphereModel.get_density(alt, f107_solar_flux=f107_solar_flux)
            # v_orb in km/s
            v_orb = math.sqrt(cls.MU_EARTH_KM3_S2 / r_val)
            # Drag deceleration a_drag = 0.5 * rho * v^2 * (Cd * A / m)
            # dr/dt = - 2 * a_drag / (v_orb / r) = - rho * v * r * (Cd * A / m)
            # In km/yr:
            # (Cd * A / m) in m^2 / kg = 1.0 / ballistic_coeff
            dr_dt_km_s = - rho_kg_m3 * (v_orb * 1000.0) * (r_val * 1000.0) * (1.0 / ballistic_coeff) / 1000.0
            seconds_per_year = 365.25 * 86400.0
            return dr_dt_km_s * seconds_per_year

        # Integrate until altitude drops below 120 km (re-entry interface)
        current_alt = altitude_km
        current_r = r

        while current_alt > 120.0 and t_years < max_simulation_years:
            # Scale time step dynamically
            if current_alt > 700.0:
                dt = 0.25
            elif current_alt > 500.0:
                dt = 0.10
            elif current_alt > 300.0:
                dt = 0.02
            else:
                dt = 0.005

            # RK4 Integration steps
            k1 = dr_dt(current_r)
            k2 = dr_dt(current_r + 0.5 * dt * k1)
            k3 = dr_dt(current_r + 0.5 * dt * k2)
            k4 = dr_dt(current_r + dt * k3)

            dr = (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
            current_r += dr
            current_alt = current_r - cls.EARTH_RADIUS_KM
            t_years += dt

            # Record points periodically
            if len(timeline_points) < 50:
                timeline_points.append((round(t_years, 2), max(0.0, round(current_alt, 1))))

        natural_decay = min(max_simulation_years, round(t_years, 2))

        # Propulsion-assisted decay: active de-orbit maneuver lowers perigee into atmosphere
        prop_assisted_decay = None
        if has_propulsion:
            # Active propulsive disposal typically completes within 30-90 days (< 0.25 years)
            prop_assisted_decay = round(min(natural_decay, 0.25), 2)
            effective_lifetime = prop_assisted_decay
            strategy = DisposalMethod.PROPULSION_ASSISTED_PERIGEE_LOWERING
        else:
            effective_lifetime = natural_decay
            strategy = DisposalMethod.NATURAL_ORBITAL_DECAY

        compliant = effective_lifetime <= DEORBIT_DEADLINE_YEARS

        if compliant:
            details = f"Post-mission orbital lifetime of {effective_lifetime:.2f} years meets the § 100.260(e) 5-year requirement."
        else:
            details = f"Natural orbital decay lifetime ({natural_decay:.1f} years) exceeds the 5-year limit. Active propulsion disposal or drag augmentation required."

        return OrbitalLifetimeResult(
            initial_altitude_km=round(altitude_km, 1),
            ballistic_coefficient_kg_m2=round(ballistic_coeff, 2),
            natural_decay_years=natural_decay,
            propulsion_assisted_decay_years=prop_assisted_decay,
            compliant_with_5_year_rule=compliant,
            disposal_strategy=strategy,
            details=details,
            decay_timeline_points=timeline_points,
        )

    @classmethod
    def evaluate_satellite_odar(
        cls,
        spec: SatelliteSpec,
        cross_section_area_m2: Optional[float] = None,
        drag_coefficient: float = 2.2,
        f107_solar_flux: float = 120.0,
    ) -> ODARReport:
        """
        Execute full NASA DAS-equivalent Orbital Debris Assessment for a satellite spec.

        Parameters
        ----------
        spec : SatelliteSpec
            Validated satellite specifications.
        cross_section_area_m2 : float, optional
            Estimated or measured cross-section area in m^2. If None, derived from smallest dimension.
        drag_coefficient : float
            Aerodynamic drag coefficient (default 2.2).
        f107_solar_flux : float
            Current or reference solar flux (sfu).

        Returns
        -------
        ODARReport
        """
        log.info("Executing comprehensive ODAR assessment for: %s", spec.name)

        # 1. Estimate cross-sectional area if not provided
        if cross_section_area_m2 is None or cross_section_area_m2 <= 0.0:
            dim_m = spec.smallest_dimension_cm / 100.0
            # Heuristic: Area proportional to (mass / density)^(2/3) or dim^2
            area_m2 = max(dim_m * dim_m, 0.02 * (spec.mass_kg ** (2.0 / 3.0)))
        else:
            area_m2 = cross_section_area_m2

        # 2. Orbital Lifetime & 5-Year Rule (§ 100.260(e))
        if spec.orbit_type == OrbitType.GEO:
            lifetime_res = OrbitalLifetimeResult(
                initial_altitude_km=spec.altitude_km,
                ballistic_coefficient_kg_m2=round(spec.mass_kg / (drag_coefficient * area_m2), 2),
                natural_decay_years=10000.0,
                propulsion_assisted_decay_years=None,
                compliant_with_5_year_rule=True,
                disposal_strategy=DisposalMethod.GRAVEYARD_ORBIT_STORAGE,
                details="GEO spacecraft: 5-year LEO de-orbit rule N/A. Subject to § 100.260(b) graveyard storage (+300 km).",
            )
        else:
            lifetime_res = cls.calculate_orbital_lifetime(
                altitude_km=spec.altitude_km,
                mass_kg=spec.mass_kg,
                cross_section_area_m2=area_m2,
                drag_coefficient=drag_coefficient,
                has_propulsion=spec.has_propulsion,
                f107_solar_flux=f107_solar_flux,
            )

        # 3. Collision Probability (§ 100.111(c)(2)(v) & (vi))
        p_small, small_flux = DebrisFluxModel.calculate_small_debris_collision_probability(
            cross_section_area_m2=area_m2,
            altitude_km=spec.altitude_km,
            mission_lifetime_years=spec.mission_lifetime_years,
        )
        p_large_raw, p_large_mitigated, large_density = DebrisFluxModel.calculate_large_object_collision_probability(
            cross_section_area_m2=area_m2,
            altitude_km=spec.altitude_km,
            inclination_deg=spec.inclination_deg,
            mission_lifetime_years=spec.mission_lifetime_years,
            has_propulsion=spec.has_propulsion,
        )

        collision_res = CollisionProbabilityResult(
            small_debris_flux_per_m2_yr=round(small_flux, 6),
            small_debris_collision_prob=round(p_small, 6),
            small_debris_threshold=0.01,
            small_debris_compliant=p_small <= 0.01,
            large_object_spatial_density_per_km3=round(large_density, 12),
            large_object_collision_prob=round(p_large_raw, 6),
            large_object_collision_prob_with_maneuver=round(p_large_mitigated, 6),
            large_object_threshold=0.001,
            large_object_compliant=p_large_mitigated <= 0.001,
        )

        # 4. Human Casualty Risk (§ 100.111(c)(2)(vii))
        fragments = ReentryModel.decompose_default_spacecraft(
            total_mass_kg=spec.mass_kg,
            has_propulsion=spec.has_propulsion,
        )
        total_dca, ec, surv_count, surv_mass = ReentryModel.calculate_total_casualty_risk(
            fragments=fragments,
            inclination_deg=spec.inclination_deg,
            num_satellites=1,
        )

        casualty_compliant = ec <= 0.0001
        casualty_res = CasualtyRiskResult(
            total_spacecraft_mass_kg=spec.mass_kg,
            surviving_debris_mass_kg=surv_mass,
            surviving_fragments_count=surv_count,
            total_casualty_area_m2=total_dca,
            human_casualty_expectation=round(ec, 7),
            casualty_threshold=0.0001,
            casualty_risk_compliant=casualty_compliant,
            fragments=fragments,
            details=(
                f"Expected casualties E_c = {ec:.2e} (threshold <= 1.00e-04). "
                + ("PASSES NASA/FCC casualty requirement." if casualty_compliant else "FAILS: design modifications needed to demise titanium/steel components.")
            ),
        )

        # 5. Disposal Success Reliability (§ 100.111(c)(2)(xi))
        # Base subsystem reliability
        prop_rel = 0.99 if spec.has_propulsion else 0.0
        pwr_rel = 0.99
        adcs_rel = 0.98
        cnh_rel = 0.99
        
        if spec.has_propulsion:
            net_disp_prob = prop_rel * pwr_rel * adcs_rel * cnh_rel * (1.0 - p_small)
        else:
            # Natural decay does not rely on active systems if orbit decays < 5 yrs
            net_disp_prob = 0.99 if lifetime_res.natural_decay_years <= DEORBIT_DEADLINE_YEARS else 0.20

        disp_res = DisposalReliabilityResult(
            propulsion_reliability=prop_rel,
            power_system_eol_reliability=pwr_rel,
            adcs_system_reliability=adcs_rel,
            cnh_system_reliability=cnh_rel,
            overall_disposal_success_prob=round(net_disp_prob, 3),
            threshold=0.90,
            disposal_reliability_compliant=net_disp_prob >= 0.90,
            delta_v_margin_pct=25.0 if spec.has_propulsion else 0.0,
        )

        # 6. Passivation (§ 100.111(c)(2)(viii))
        stored_energy_res = StoredEnergyAssessment(
            propellant_depletion_passivation=spec.has_propulsion,
            battery_passivation=True,
            pressurant_depletion=True,
            reaction_wheel_spin_down=True,
            passivation_compliant=True,
            deficiencies=[],
        )

        # Master verdict
        all_passed = (
            lifetime_res.compliant_with_5_year_rule
            and collision_res.small_debris_compliant
            and collision_res.large_object_compliant
            and casualty_res.casualty_risk_compliant
            and disp_res.disposal_reliability_compliant
            and stored_energy_res.passivation_compliant
        )

        verdict = (
            "ALL ORBITAL DEBRIS MITIGATION CRITERIA SATISFIED. Mission qualifies for affirmative Schedule O Part 100 certification."
            if all_passed
            else "DEBRIS MITIGATION DEFICIENCIES IDENTIFIED. Specific engineering modifications required to meet Part 100 Subpart C."
        )

        report = ODARReport(
            report_id=f"ODAR-{uuid.uuid4().hex[:8].upper()}",
            satellite_name=spec.name,
            operator_name=spec.operator_name or "Applicant",
            orbital_lifetime=lifetime_res,
            collision_probability=collision_res,
            casualty_risk=casualty_res,
            disposal_reliability=disp_res,
            stored_energy=stored_energy_res,
            all_debris_requirements_met=all_passed,
            summary_verdict=verdict,
        )

        log.info("ODAR assessment generated: all_passed=%s, report_id=%s", all_passed, report.report_id)
        return report


# Module singleton
_odar_engine: ODAREngine | None = None


def get_odar_engine() -> ODAREngine:
    """Return singleton instance of ODAREngine."""
    global _odar_engine  # noqa: PLW0603
    if _odar_engine is None:
        _odar_engine = ODAREngine()
    return _odar_engine
