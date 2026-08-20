"""
OrbitFlow Core Data Models
==========================

Pydantic v2 schemas for FCC Part 100 satellite intake, certification
evaluation, bond calculation, and audit output.

All models are strictly typed. No optional fields without explicit defaults.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrbitType(str, Enum):
    """Orbital regime classification per § 100.3 definitions."""
    LEO = "LEO"      # Low Earth Orbit (< 2,000 km)
    MEO = "MEO"      # Medium Earth Orbit (2,000 – 35,786 km)
    GEO = "GEO"      # Geostationary Orbit (35,786 km)
    HEO = "HEO"      # Highly Elliptical Orbit
    VTSS = "VTSS"    # Variable Trajectory Spacecraft System


class SystemType(str, Enum):
    """FCC system classification under Part 100."""
    GSO_SATELLITE_SYSTEM = "GSO Satellite System"
    NGSO_SATELLITE_SYSTEM = "NGSO Satellite System"
    VTSS = "VTSS"
    MOSS = "MOSS"
    EARTH_STATION = "Earth Station"


class CertStatus(str, Enum):
    """Certification evaluation outcome."""
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "N/A"


class ReviewCategory(str, Enum):
    """The 7 Targeted Review Categories — § 100.136(b)."""
    FAILURE_TO_CERTIFY = "Failure to Certify"
    WAIVER_REQUEST = "Waiver Request"
    MARKET_ACCESS = "Market Access"
    FOREIGN_OWNERSHIP = "Foreign Ownership"
    PROCESSING_ROUND = "Processing Round"
    SPECTRAL_CONSTRAINTS = "Spectral Constraints"
    FEDERAL_COORDINATION = "Federal Coordination"


# ---------------------------------------------------------------------------
# Input Model
# ---------------------------------------------------------------------------

class SatelliteSpec(BaseModel):
    """
    Core satellite specification intake.

    All fields required for the Part 100 Delta & Certification Audit.
    Mirrors the Schedule O (§ 100.111) and Form 312 data requirements.
    """

    # Identity
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Satellite system or constellation name",
    )
    operator_name: str = Field(
        default="",
        max_length=200,
        description="Applicant / operator legal name",
    )

    # Orbital parameters
    orbit_type: OrbitType = Field(
        ...,
        description="Primary orbital regime",
    )
    altitude_km: float = Field(
        ...,
        gt=0,
        le=500_000,
        description="Mean operational altitude in km (apogee for elliptical)",
    )
    apogee_km: Optional[float] = Field(
        default=None,
        gt=0,
        le=500_000,
        description="Apogee altitude in km",
    )
    perigee_km: Optional[float] = Field(
        default=None,
        gt=0,
        le=500_000,
        description="Perigee altitude in km",
    )
    inclination_deg: float = Field(
        default=0.0,
        ge=0.0,
        le=180.0,
        description="Orbital inclination in degrees",
    )

    # Constellation / fleet
    num_authorized: int = Field(
        ...,
        ge=0,
        description="Total number of authorized (non-replacement) satellites",
    )
    num_deployed: int = Field(
        default=0,
        ge=0,
        description="Number of satellites currently deployed and operating",
    )

    # Physical characteristics
    smallest_dimension_cm: float = Field(
        ...,
        gt=0,
        description="Smallest physical dimension in centimeters",
    )
    mass_kg: float = Field(
        ...,
        gt=0,
        description="Satellite wet mass in kilograms",
    )
    mission_lifetime_years: float = Field(
        default=5.0,
        gt=0,
        le=50,
        description="Planned operational mission lifetime in years",
    )

    # Regulatory flags
    in_processing_round: bool = Field(
        default=False,
        description="Whether the applicant opts into an NGSO processing round",
    )
    federal_bands_requested: bool = Field(
        default=False,
        description="Whether any requested frequencies are in shared federal allocations",
    )
    foreign_ownership_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Reportable aggregate foreign ownership percentage",
    )
    is_us_licensed: bool = Field(
        default=True,
        description="Whether the operator is a U.S.-licensed entity",
    )
    waiver_requested: bool = Field(
        default=False,
        description="Whether the application includes any waiver requests",
    )

    # Disposal & Physical aerodynamics
    has_propulsion: bool = Field(
        default=True,
        description="Whether the spacecraft has a propulsion system for disposal",
    )
    estimated_deorbit_years: float = Field(
        default=5.0,
        gt=0,
        le=100,
        description="Estimated time from end-of-mission to atmospheric re-entry (years)",
    )
    cross_section_area_m2: Optional[float] = Field(
        default=None,
        description="Average cross-sectional drag/collision area in m^2",
    )
    drag_coefficient: float = Field(
        default=2.2,
        ge=1.0,
        le=4.0,
        description="Aerodynamic drag coefficient (nominal Cd = 2.2)",
    )
    fuel_mass_kg: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Propellant mass in kg",
    )
    delta_v_ms: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Total Delta-V capability in m/s",
    )

    # Validators
    @field_validator("num_deployed")
    @classmethod
    def deployed_cannot_exceed_authorized(cls, v: int, info: object) -> int:
        """Deployed count must not exceed authorized count."""
        data = info.data if hasattr(info, "data") else {}  # type: ignore[union-attr]
        authorized = data.get("num_authorized", 0)
        if authorized > 0 and v > authorized:
            raise ValueError(
                f"num_deployed ({v}) cannot exceed num_authorized ({authorized})"
            )
        return v


# ---------------------------------------------------------------------------
# Output / Analysis Models
# ---------------------------------------------------------------------------

class CertificationResult(BaseModel):
    """Single certification line-item evaluation."""
    cert_id: str = Field(..., description="e.g. NGSO-03")
    criterion: str = Field(..., description="Human-readable criterion text")
    section: str = Field(..., description="FCC rule section, e.g. § 100.111(c)(2)(iii)")
    status: CertStatus
    value: Optional[str] = Field(default=None, description="Measured / input value")
    threshold: Optional[str] = Field(default=None, description="Required threshold")
    evidence: str = Field(default="", description="Evidence or source data used")
    notes: str = Field(default="")


class BondDelta(BaseModel):
    """Surety bond comparison between Part 25 and Part 100."""
    part_25_bond_usd: int = Field(..., description="Bond under legacy Part 25 rules")
    part_100_bond_usd: int = Field(..., description="Bond under adopted Part 100 rules")
    part_100_formula: str = Field(
        default="B = $10M − $10M × (D / (0.9 × A))",
        description="Part 100 § 100.148(d) formula",
    )
    deployment_pct: float = Field(default=0.0, description="Current deployment percentage")
    bond_relieved_at_pct: float = Field(default=90.0)
    citation: str = Field(default="§ 100.148(d)")
    notes: str = Field(default="")


class MilestoneDelta(BaseModel):
    """Milestone schedule comparison."""
    regime: str = Field(..., description="Part 25 or Part 100")
    milestones: dict[str, str] = Field(
        ...,
        description="Year-key to milestone description, e.g. {'7yr': 'BIU'}",
    )
    notes: str = Field(default="")


class TargetedReviewFlag(BaseModel):
    """A single targeted review category flag."""
    category: ReviewCategory
    section: str = Field(..., description="FCC rule section")
    triggered: bool = Field(default=False)
    details: str = Field(default="")
    action_required: str = Field(default="")


class AuditResult(BaseModel):
    """
    Complete output of the Part 25 → Part 100 Delta & Certification Audit.

    This is the top-level object rendered into the $3,000 PDF.
    """

    # Metadata
    report_id: str = Field(..., description="Unique report identifier")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    engine_version: str = Field(default="0.1.0")
    regime_evaluated: str = Field(default="FCC Part 100 (Adopted — FCC 25-69)")

    # Input echo
    spec: SatelliteSpec

    # System classification
    system_type: SystemType
    orbit_classification: str = Field(
        default="",
        description="LEO / MEO / GEO / HEO / VTSS with altitude context",
    )

    # Bond comparison
    bond_delta: BondDelta

    # Milestone comparison
    milestones_part_25: MilestoneDelta
    milestones_part_100: MilestoneDelta

    # Certification matrix
    certifications: list[CertificationResult] = Field(default_factory=list)

    # Targeted review pre-screen
    targeted_reviews: list[TargetedReviewFlag] = Field(default_factory=list)

    # Summary counts
    total_certs: int = Field(default=0)
    pass_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    insufficient_count: int = Field(default=0)
    na_count: int = Field(default=0)

    # Trackability
    trackability_status: CertStatus = Field(default=CertStatus.INSUFFICIENT_DATA)
    trackability_detail: str = Field(default="")

    # De-orbit
    deorbit_status: CertStatus = Field(default=CertStatus.INSUFFICIENT_DATA)
    deorbit_detail: str = Field(default="")

    # Filing recommendation
    filing_strategy: str = Field(
        default="",
        description="Recommended approach: file now under Part 25 vs wait for Part 100",
    )

    # License term
    license_term_part_25: str = Field(default="15 years")
    license_term_part_100: str = Field(default="20 years")

    # Warnings / missing data
    warnings: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)

    # Detailed Orbital Debris Assessment Report (NASA DAS equivalent)
    odar_report: Optional[Any] = Field(
        default=None,
        description="Detailed ODAR physics calculation report",
    )

    # Detailed Spectrum & EPFD Assessment Report
    spectrum_report: Optional[Any] = Field(
        default=None,
        description="Detailed Spectrum, PFD, and EPFD compliance report",
    )

    # Complete Submission-Ready FCC Part 100 Filing Package
    filing_package: Optional[Any] = Field(
        default=None,
        description="Complete Form 312 + Schedule O + Schedule F legal filing package",
    )

    # Complete Submission-Ready ITU Filing Package (Module 12)
    itu_package: Optional[Any] = Field(
        default=None,
        description="Complete ITU Appendix 4 + SpaceCap XML filing package",
    )

    # Complete Earth Station Nationwide Non-Site Package (Module 19)
    earth_station_package: Optional[Any] = Field(
        default=None,
        description="Complete Schedule B XML + Link Budget + Site Registration package",
    )

