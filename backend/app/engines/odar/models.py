"""
OrbitFlow ODAR Data Models
==========================

Pydantic v2 schemas for NASA DAS-equivalent Orbital Debris Assessment (ODAR)
and Post-Mission Disposal (PMD) evaluations under FCC Part 100 (§ 100.260 & § 100.111).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MaterialType(str, Enum):
    """Structural and component materials with distinct demise characteristics."""
    ALUMINUM_6061 = "Aluminum 6061-T6"
    TITANIUM_6AL4V = "Titanium Ti-6Al-4V"
    STAINLESS_STEEL_316 = "Stainless Steel 316"
    CARBON_COMPOSITE = "Carbon Fiber Epoxy Composite"
    SILICON_GLASS = "Solar Cell Glass"
    BERYLLIUM = "Beryllium Copper"
    INCONEL = "Inconel 718"


class DisposalMethod(str, Enum):
    """Post-mission disposal strategy."""
    DIRECT_CONTROLLED_REENTRY = "Direct Controlled Re-entry"
    PROPULSION_ASSISTED_PERIGEE_LOWERING = "Propulsion-Assisted Perigee Lowering"
    NATURAL_ORBITAL_DECAY = "Natural Orbital Decay"
    GRAVEYARD_ORBIT_STORAGE = "Graveyard Orbit Storage (GEO/MEO)"
    HELIOCENTRIC_ESCAPE = "Heliocentric Escape"


class DebrisFragment(BaseModel):
    """A modeled physical component evaluated for re-entry thermal survivability."""
    component_name: str
    material: MaterialType
    mass_kg: float = Field(..., gt=0)
    dimensions_cm: str = Field(default="10x10x10 cm")
    cross_section_area_m2: float = Field(..., gt=0)
    demise_altitude_km: Optional[float] = Field(default=None, description="Altitude where mass reaches 0 km, None if survives to surface")
    survives_to_surface: bool = Field(default=False)
    terminal_velocity_mps: float = Field(default=0.0, description="Impact velocity in m/s")
    impact_kinetic_energy_joules: float = Field(default=0.0, description="Kinetic energy at surface (threshold > 15 J)")
    casualty_area_m2: float = Field(default=0.0, description="Debris casualty area (sqrt(A) + 0.6)^2")


class OrbitalLifetimeResult(BaseModel):
    """Orbital decay and 5-year rule compliance metrics (§ 100.260(e))."""
    initial_altitude_km: float
    ballistic_coefficient_kg_m2: float = Field(..., description="m / (Cd * A)")
    natural_decay_years: float = Field(..., description="Duration from EOL to atmospheric re-entry without propulsion")
    propulsion_assisted_decay_years: Optional[float] = Field(default=None, description="Disposal duration using active maneuvers")
    compliant_with_5_year_rule: bool
    disposal_strategy: DisposalMethod
    details: str = Field(default="")
    decay_timeline_points: list[tuple[float, float]] = Field(
        default_factory=list,
        description="List of (time_years, altitude_km) for decay curve plotting",
    )


class CollisionProbabilityResult(BaseModel):
    """Collision risk analysis for small debris and large tracked objects."""
    # Small debris (1mm to 10cm) — § 100.111(c)(2)(v)
    small_debris_flux_per_m2_yr: float
    small_debris_collision_prob: float = Field(..., description="Probability of small debris strike causing loss of control")
    small_debris_threshold: float = Field(default=0.01)
    small_debris_compliant: bool

    # Large tracked objects (>= 10cm) — § 100.111(c)(2)(vi)
    large_object_spatial_density_per_km3: float
    large_object_collision_prob: float = Field(..., description="Probability of collision with cataloged space debris")
    large_object_collision_prob_with_maneuver: float = Field(..., description="Residual probability with 95% collision avoidance reliability")
    large_object_threshold: float = Field(default=0.001)
    large_object_compliant: bool


class CasualtyRiskResult(BaseModel):
    """Re-entry survivability and human casualty risk (§ 100.111(c)(2)(vii))."""
    total_spacecraft_mass_kg: float
    surviving_debris_mass_kg: float
    surviving_fragments_count: int
    total_casualty_area_m2: float = Field(..., description="Sum of (sqrt(A_i) + 0.6)^2 for fragments > 15 Joules")
    human_casualty_expectation: float = Field(..., description="Ec = (DCA / A_earth) * Population * N_sats")
    casualty_threshold: float = Field(default=0.0001, description="1 in 10,000 requirement")
    casualty_risk_compliant: bool
    fragments: list[DebrisFragment] = Field(default_factory=list)
    details: str = Field(default="")


class DisposalReliabilityResult(BaseModel):
    """Post-mission disposal reliability breakdown (§ 100.111(c)(2)(xi))."""
    propulsion_reliability: float = Field(default=0.98)
    power_system_eol_reliability: float = Field(default=0.97)
    adcs_system_reliability: float = Field(default=0.96)
    cnh_system_reliability: float = Field(default=0.99)
    overall_disposal_success_prob: float = Field(..., description="Net probability of successful disposal >= 0.9")
    threshold: float = Field(default=0.90)
    disposal_reliability_compliant: bool
    delta_v_margin_pct: float = Field(default=20.0, description="Delta-V fuel reserve percentage")


class StoredEnergyAssessment(BaseModel):
    """Passivation plan evaluation (§ 100.111(c)(2)(viii))."""
    propellant_depletion_passivation: bool = Field(default=True, description="Venting or burning residual fuel to zero pressure")
    battery_passivation: bool = Field(default=True, description="Discharging and disconnecting solar charge circuits")
    pressurant_depletion: bool = Field(default=True, description="Relieving all high-pressure tanks")
    reaction_wheel_spin_down: bool = Field(default=True, description="Desaturating and dumping momentum")
    passivation_compliant: bool = Field(default=True)
    deficiencies: list[str] = Field(default_factory=list)


class ODARReport(BaseModel):
    """
    Complete Orbital Debris Assessment Report (ODAR).
    Fully auditable, physics-grounded engineering report matching NASA DAS specifications.
    """
    report_id: str
    satellite_name: str
    operator_name: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Physics evaluation results
    orbital_lifetime: OrbitalLifetimeResult
    collision_probability: CollisionProbabilityResult
    casualty_risk: CasualtyRiskResult
    disposal_reliability: DisposalReliabilityResult
    stored_energy: StoredEnergyAssessment
    
    # Overall compliance status
    all_debris_requirements_met: bool
    summary_verdict: str
    disclaimer: str = Field(
        default="CONFIDENTIAL - ENGINEERING ASSESSMENT. Generated in accordance with NASA DAS 2.0/3.0 methodology and FCC Part 100 Subpart C."
    )
