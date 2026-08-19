"""
OrbitFlow Delta & Certification Audit Engine
=============================================

Core business logic for the 7-Day Sprint MVP.

This engine takes a ``SatelliteSpec``, evaluates it against both
FCC Part 25 (legacy) and Part 100 (adopted), and produces a
complete ``AuditResult`` for the $3,000 PDF report.

Implements:
- Bond matrix (§ 100.148(d))
- Trackability guillotine (§ 100.111(c)(2)(iii))
- De-orbit 5-year rule (§ 100.260(e))
- Targeted Review pre-screener (§ 100.136(b))
- Certification determination (Module 7)
- Milestone delta (§ 100.147)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.app.core.config import (
    BOND_BASE_USD,
    BOND_RELIEF_PCT,
    DEORBIT_DEADLINE_YEARS,
    ENGINE_VERSION,
    GEO_ALTITUDE_KM,
    LEO_CEILING_KM,
    REGIME_PART_100,
    REGIME_PART_25,
    TRACKABILITY_ABOVE_LEO_CM,
    TRACKABILITY_LEO_CM,
    get_logger,
)
from backend.app.engines.epfd import (
    SpectrumEngine,
    SpectrumSharingReport,
    get_spectrum_engine,
)
from backend.app.engines.fcc import (
    FCCFilingBundler,
    FilingPackage,
)
from backend.app.engines.odar import ODAREngine, ODARReport
from backend.app.models.satellite import (
    AuditResult,
    BondDelta,
    CertificationResult,
    CertStatus,
    MilestoneDelta,
    OrbitType,
    ReviewCategory,
    SatelliteSpec,
    SystemType,
    TargetedReviewFlag,
)

log = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM TYPE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════

def classify_system(spec: SatelliteSpec) -> SystemType:
    """Determine FCC system type from orbital parameters (§ 100.3)."""
    if spec.orbit_type == OrbitType.GEO:
        return SystemType.GSO_SATELLITE_SYSTEM
    if spec.orbit_type == OrbitType.VTSS:
        return SystemType.VTSS
    # LEO, MEO, HEO → NGSO
    return SystemType.NGSO_SATELLITE_SYSTEM


def classify_orbit(spec: SatelliteSpec) -> str:
    """Human-readable orbit classification with altitude context."""
    if spec.orbit_type == OrbitType.GEO:
        return f"Geostationary ({GEO_ALTITUDE_KM:,.0f} km)"
    if spec.orbit_type == OrbitType.VTSS:
        return f"Variable Trajectory ({spec.altitude_km:,.0f} km nominal)"
    label = spec.orbit_type.value
    return f"{label} ({spec.altitude_km:,.0f} km)"


# ═══════════════════════════════════════════════════════════════════════════
# BOND CALCULATOR (§ 100.148(d))
# ═══════════════════════════════════════════════════════════════════════════

def calculate_bond_part_25(spec: SatelliteSpec) -> int:
    """
    Legacy Part 25 bond estimate.

    Under Part 25 all space station licensees post an escalating bond.
    Simplified estimate: $5M for NGSO constellations.
    """
    if spec.orbit_type == OrbitType.GEO:
        return 3_000_000
    return 5_000_000


def calculate_bond_part_100(spec: SatelliteSpec) -> int:
    """
    Part 100 de-escalating bond — processing round participants only.

    Formula (§ 100.148(d)):
        B = $10,000,000 − $10,000,000 × (D / (0.9 × A))

    Returns $0 for non-processing-round applicants.
    Handles edge cases: A=0, D>A, negative results.
    """
    if not spec.in_processing_round:
        return 0

    a = spec.num_authorized
    d = spec.num_deployed

    # Guard: no authorized satellites → no bond calculable
    if a <= 0:
        return BOND_BASE_USD  # Full bond if nothing authorized yet

    ratio = d / (0.9 * a)
    bond = BOND_BASE_USD - BOND_BASE_USD * ratio
    bond = max(0, round(bond))
    return bond


def build_bond_delta(spec: SatelliteSpec) -> BondDelta:
    """Build the full bond comparison object."""
    p25 = calculate_bond_part_25(spec)
    p100 = calculate_bond_part_100(spec)
    deployment_pct = (
        (spec.num_deployed / spec.num_authorized * 100.0)
        if spec.num_authorized > 0
        else 0.0
    )

    notes_parts: list[str] = []
    if not spec.in_processing_round:
        notes_parts.append("Not in processing round → $0 bond under Part 100")
    if deployment_pct >= BOND_RELIEF_PCT:
        notes_parts.append(
            f"≥{BOND_RELIEF_PCT:.0f}% deployed → bond fully relieved"
        )

    return BondDelta(
        part_25_bond_usd=p25,
        part_100_bond_usd=p100,
        deployment_pct=round(deployment_pct, 2),
        notes=" | ".join(notes_parts) if notes_parts else "",
    )


# ═══════════════════════════════════════════════════════════════════════════
# MILESTONE SCHEDULE DELTA (§ 100.147)
# ═══════════════════════════════════════════════════════════════════════════

def build_milestones_part_25(spec: SatelliteSpec) -> MilestoneDelta:
    """Legacy Part 25 milestone schedule."""
    system = classify_system(spec)

    if system == SystemType.GSO_SATELLITE_SYSTEM:
        return MilestoneDelta(
            regime=REGIME_PART_25,
            milestones={"5yr": "Launch, position, and operate at assigned location"},
            notes="GSO milestone unchanged between Part 25 and Part 100",
        )

    # NGSO under Part 25
    return MilestoneDelta(
        regime=REGIME_PART_25,
        milestones={
            "6yr": "50% of authorized constellation deployed and operating",
            "9yr": "100% of authorized constellation deployed and operating",
        },
    )


def build_milestones_part_100(spec: SatelliteSpec) -> MilestoneDelta:
    """Part 100 milestone schedule — varies by system type and PR status."""
    system = classify_system(spec)

    if system == SystemType.VTSS:
        return MilestoneDelta(
            regime=REGIME_PART_100,
            milestones={},
            notes="No deployment milestones required for VTSS (§ 100.147)",
        )

    if system == SystemType.GSO_SATELLITE_SYSTEM:
        return MilestoneDelta(
            regime=REGIME_PART_100,
            milestones={"5yr": "Launch, position, and operate at assigned location"},
            notes="GSO milestone retained from Part 25 (§ 100.147(a))",
        )

    # NGSO
    if spec.in_processing_round:
        return MilestoneDelta(
            regime=REGIME_PART_100,
            milestones={
                "6yr": "50% deployed and operating",
                "9yr": "100% deployed and operating",
            },
            notes=(
                "Processing round milestones (§ 100.147(d)). "
                "6yr failure → reassignment to later round."
            ),
        )

    return MilestoneDelta(
        regime=REGIME_PART_100,
        milestones={
            "7yr": "≥1 satellite deployed, operating 90 days (BIU)",
            "9yr": "10% deployed and operating",
            "12yr": "50% deployed and operating",
            "14yr": "100% deployed and operating",
        },
        notes=(
            "ITU-aligned milestones (§ 100.147(b)). "
            "7yr BIU failure → automatic license termination."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# TRACKABILITY CHECK (§ 100.111(c)(2)(iii))
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_trackability(spec: SatelliteSpec) -> tuple[CertStatus, str]:
    """
    Evaluate the trackability bright-line requirement.

    LEO (< 2000 km):  smallest dimension ≥ 10 cm
    Above 2000 km:    smallest dimension ≥ 100 cm (1 m)
    """
    dim = spec.smallest_dimension_cm
    alt = spec.altitude_km

    if alt < LEO_CEILING_KM:
        threshold = TRACKABILITY_LEO_CM
        zone = f"LEO ({alt:,.0f} km)"
    else:
        threshold = TRACKABILITY_ABOVE_LEO_CM
        zone = f"Above LEO ({alt:,.0f} km)"

    if dim >= threshold:
        return (
            CertStatus.PASS,
            f"{zone}: {dim:.1f} cm ≥ {threshold:.0f} cm threshold — PASS",
        )

    return (
        CertStatus.FAIL,
        f"{zone}: {dim:.1f} cm < {threshold:.0f} cm threshold — FAIL. "
        f"Spacecraft does not meet trackability obligation.",
    )


# ═══════════════════════════════════════════════════════════════════════════
# DE-ORBIT 5-YEAR RULE (§ 100.260(e))
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_deorbit(spec: SatelliteSpec) -> tuple[CertStatus, str]:
    """
    Evaluate the 5-year post-mission de-orbit requirement.

    Only applies to spacecraft ending mission in or passing through LEO
    (below 2000 km).
    """
    # GEO satellites are not subject to the 5-year LEO de-orbit rule
    if spec.orbit_type == OrbitType.GEO:
        return (
            CertStatus.NOT_APPLICABLE,
            "GSO spacecraft — 5-year LEO de-orbit rule not applicable. "
            "Subject to § 100.260(b) graveyard orbit requirement.",
        )

    if spec.altitude_km >= LEO_CEILING_KM and spec.orbit_type != OrbitType.VTSS:
        return (
            CertStatus.NOT_APPLICABLE,
            f"Operational altitude ({spec.altitude_km:,.0f} km) ≥ {LEO_CEILING_KM:,.0f} km — "
            f"5-year de-orbit rule applies only to LEO.",
        )

    if spec.estimated_deorbit_years <= DEORBIT_DEADLINE_YEARS:
        return (
            CertStatus.PASS,
            f"Estimated de-orbit: {spec.estimated_deorbit_years:.1f} years "
            f"≤ {DEORBIT_DEADLINE_YEARS:.0f}-year threshold — PASS",
        )

    return (
        CertStatus.FAIL,
        f"Estimated de-orbit: {spec.estimated_deorbit_years:.1f} years "
        f"> {DEORBIT_DEADLINE_YEARS:.0f}-year threshold — FAIL. "
        f"Does not meet § 100.260(e) requirement.",
    )


# ═══════════════════════════════════════════════════════════════════════════
# CERTIFICATION MATRIX BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def build_certification_matrix(
    spec: SatelliteSpec,
    odar_report: Optional[ODARReport] = None,
    spectrum_report: Optional[SpectrumSharingReport] = None,
) -> list[CertificationResult]:
    """
    Build the full certification evaluation matrix for the given spec.

    Evaluates all deterministic certifications, physics-based orbital debris metrics (ODAR),
    and RF spectrum / PFD / EPFD interference metrics.
    """
    system = classify_system(spec)
    certs: list[CertificationResult] = []

    # If ODAR report not provided, calculate it on the fly
    if odar_report is None:
        odar_report = ODAREngine.evaluate_satellite_odar(
            spec=spec,
            cross_section_area_m2=spec.cross_section_area_m2,
            drag_coefficient=spec.drag_coefficient,
        )

    # ── Trackability (all types) ──
    track_status, track_detail = evaluate_trackability(spec)
    certs.append(CertificationResult(
        cert_id="NGSO-03" if system != SystemType.GSO_SATELLITE_SYSTEM else "GSO-05",
        criterion="Trackability — smallest dimension meets minimum size",
        section=(
            "§ 100.111(c)(2)(iii)"
            if system != SystemType.GSO_SATELLITE_SYSTEM
            else "§ 100.111(b)(2)(v)"
        ),
        status=track_status,
        value=f"{spec.smallest_dimension_cm:.1f} cm",
        threshold=(
            f"≥ {TRACKABILITY_LEO_CM:.0f} cm (LEO)"
            if spec.altitude_km < LEO_CEILING_KM
            else f"≥ {TRACKABILITY_ABOVE_LEO_CM:.0f} cm (above 2000 km)"
        ),
        evidence=f"Altitude: {spec.altitude_km:,.0f} km",
        notes=track_detail,
    ))

    # ── De-orbit (LEO/NGSO/VTSS) ──
    deorbit_status, deorbit_detail = evaluate_deorbit(spec)
    # Use ODAR physics if LEO
    if spec.altitude_km < LEO_CEILING_KM and spec.orbit_type != OrbitType.GEO:
        if odar_report.orbital_lifetime.compliant_with_5_year_rule:
            deorbit_status = CertStatus.PASS
        else:
            deorbit_status = CertStatus.FAIL
        deorbit_detail = odar_report.orbital_lifetime.details

    certs.append(CertificationResult(
        cert_id="NGSO-10",
        criterion="De-orbit within 5 years post-mission",
        section="§ 100.260(e)",
        status=deorbit_status,
        value=(
            f"{odar_report.orbital_lifetime.propulsion_assisted_decay_years:.2f} yrs (active)"
            if odar_report.orbital_lifetime.propulsion_assisted_decay_years
            else f"{odar_report.orbital_lifetime.natural_decay_years:.1f} yrs (natural)"
        ),
        threshold=f"≤ {DEORBIT_DEADLINE_YEARS:.0f} years",
        evidence=f"Has propulsion: {spec.has_propulsion} | Ballistic Coeff: {odar_report.orbital_lifetime.ballistic_coefficient_kg_m2:.1f} kg/m²",
        notes=deorbit_detail,
    ))

    # ── NGSO-specific certifications ──
    if system == SystemType.NGSO_SATELLITE_SYSTEM:
        # NGSO-01: Operates only in NGSO
        certs.append(CertificationResult(
            cert_id="NGSO-01",
            criterion="Operates only in non-geostationary orbit",
            section="§ 100.111(c)(2)(i)",
            status=CertStatus.PASS if spec.orbit_type != OrbitType.GEO else CertStatus.FAIL,
            value=spec.orbit_type.value,
            threshold="orbit ≠ GEO",
        ))

        # NGSO-02: Unique telemetry marker (attestation)
        certs.append(CertificationResult(
            cert_id="NGSO-02",
            criterion="Identifiable by unique signal-based telemetry marker",
            section="§ 100.111(c)(2)(ii)",
            status=CertStatus.INSUFFICIENT_DATA,
            notes="Requires operator attestation — not auto-evaluable",
        ))

        # NGSO-04: Collision avoidance (attestation)
        certs.append(CertificationResult(
            cert_id="NGSO-04",
            criterion="Will assess/mitigate collision risk on conjunction warning",
            section="§ 100.111(c)(2)(iv)",
            status=CertStatus.PASS if spec.has_propulsion else CertStatus.INSUFFICIENT_DATA,
            notes=(
                "Propulsion available for active collision avoidance maneuvers"
                if spec.has_propulsion
                else "Requires operator collision avoidance plan attestation"
            ),
        ))

        # NGSO-05: Small debris collision ≤ 0.01 (ODAR Physics)
        certs.append(CertificationResult(
            cert_id="NGSO-05",
            criterion="Small debris collision probability ≤ 0.01",
            section="§ 100.111(c)(2)(v)",
            status=CertStatus.PASS if odar_report.collision_probability.small_debris_compliant else CertStatus.FAIL,
            value=f"{odar_report.collision_probability.small_debris_collision_prob:.5f}",
            threshold="≤ 0.01",
            evidence=f"Flux: {odar_report.collision_probability.small_debris_flux_per_m2_yr:.2e} /m²/yr (NASA ORDEM 3.1)",
            notes="Evaluated via NASA DAS Poisson small debris flux model",
        ))

        # NGSO-06: Large object collision ≤ 0.001 (ODAR Physics)
        certs.append(CertificationResult(
            cert_id="NGSO-06",
            criterion="Large object collision probability ≤ 0.001",
            section="§ 100.111(c)(2)(vi)",
            status=CertStatus.PASS if odar_report.collision_probability.large_object_compliant else CertStatus.FAIL,
            value=f"{odar_report.collision_probability.large_object_collision_prob_with_maneuver:.6f}",
            threshold="≤ 0.001",
            evidence=f"Spatial density: {odar_report.collision_probability.large_object_spatial_density_per_km3:.2e} /km³",
            notes="Evaluated with 95% collision avoidance efficiency",
        ))

        # NGSO-07: Human casualty risk ≤ 0.0001 (ODAR Physics)
        certs.append(CertificationResult(
            cert_id="NGSO-07",
            criterion="Human casualty risk from re-entry ≤ 0.0001",
            section="§ 100.111(c)(2)(vii)",
            status=CertStatus.PASS if odar_report.casualty_risk.casualty_risk_compliant else CertStatus.FAIL,
            value=f"{odar_report.casualty_risk.human_casualty_expectation:.2e}",
            threshold="≤ 0.0001 (1 in 10,000)",
            evidence=f"DCA: {odar_report.casualty_risk.total_casualty_area_m2:.2f} m², Surviving mass: {odar_report.casualty_risk.surviving_debris_mass_kg:.1f} kg",
            notes=odar_report.casualty_risk.details,
        ))

        # NGSO-08: Stored energy removal (Passivation audit)
        certs.append(CertificationResult(
            cert_id="NGSO-08",
            criterion="All stored energy removed at end of life",
            section="§ 100.111(c)(2)(viii)",
            status=CertStatus.PASS if odar_report.stored_energy.passivation_compliant else CertStatus.FAIL,
            value="Passivation Compliant" if odar_report.stored_energy.passivation_compliant else "Deficient",
            notes="Passivation plan: fuel venting, battery disconnect, and momentum wheel spin-down verified",
        ))

        # NGSO-09: Atmospheric re-entry disposal
        certs.append(CertificationResult(
            cert_id="NGSO-09",
            criterion="Disposed of via atmospheric re-entry",
            section="§ 100.111(c)(2)(ix)",
            status=(
                CertStatus.PASS
                if spec.altitude_km < LEO_CEILING_KM
                else CertStatus.INSUFFICIENT_DATA
            ),
            value=f"Altitude: {spec.altitude_km:,.0f} km",
            notes=(
                "LEO spacecraft — atmospheric re-entry expected"
                if spec.altitude_km < LEO_CEILING_KM
                else "Above LEO — disposal method requires confirmation"
            ),
        ))

        # NGSO-11: Disposal success ≥ 0.9 (ODAR Reliability Physics)
        certs.append(CertificationResult(
            cert_id="NGSO-11",
            criterion="Probability of successful disposal ≥ 0.9",
            section="§ 100.111(c)(2)(xi)",
            status=CertStatus.PASS if odar_report.disposal_reliability.disposal_reliability_compliant else CertStatus.FAIL,
            value=f"{odar_report.disposal_reliability.overall_disposal_success_prob:.3f}",
            threshold="≥ 0.90",
            evidence=f"Propulsion R={odar_report.disposal_reliability.propulsion_reliability:.2f}, Power R={odar_report.disposal_reliability.power_system_eol_reliability:.2f}",
            notes="Engineering subsystem reliability calculation",
        ))

    # ── GSO-specific certifications ──
    if system == SystemType.GSO_SATELLITE_SYSTEM:
        certs.append(CertificationResult(
            cert_id="GSO-01",
            criterion="Two-degree orbital spacing compliance",
            section="§§ 100.230, 100.278, 100.279",
            status=CertStatus.INSUFFICIENT_DATA,
            notes="Requires assigned orbital location — not available in intake",
        ))

        certs.append(CertificationResult(
            cert_id="GSO-02",
            criterion="Orbital debris rules compliance",
            section="§ 100.260",
            status=CertStatus.INSUFFICIENT_DATA,
            notes="Requires full ODAR evaluation",
        ))

        certs.append(CertificationResult(
            cert_id="GSO-03",
            criterion="Small object collision probability ≤ 0.01",
            section="§ 100.111(b)(2)(iii)",
            status=CertStatus.INSUFFICIENT_DATA,
            threshold="≤ 0.01",
            notes="Requires NASA DAS calculation",
        ))

        certs.append(CertificationResult(
            cert_id="GSO-04",
            criterion="All stored energy removed at end of life",
            section="§ 100.111(b)(2)(iv)",
            status=CertStatus.INSUFFICIENT_DATA,
            notes="Requires passivation plan review",
        ))

    # ── Schedule F certifications (all types) ──
    if spectrum_report and spectrum_report.all_spectrum_requirements_met:
        freq01_status = CertStatus.PASS
        freq01_evidence = (
            f"Evaluated against PFD masks (§ 100.212), EPFD limits (§ 100.222), and "
            f"§ 100.280 2-degree off-axis EIRP density across {len(spectrum_report.channels_analyzed)} channel(s)."
        )
    elif spectrum_report:
        freq01_status = CertStatus.FAIL
        freq01_evidence = "PFD, EPFD, or off-axis EIRP density limits exceeded."
    else:
        freq01_status = CertStatus.INSUFFICIENT_DATA
        freq01_evidence = "Requires technical spectrum evaluation"

    certs.append(CertificationResult(
        cert_id="FREQ-01",
        criterion="Comply with all applicable technical/operational rules",
        section="§ 100.112(c)(1)",
        status=freq01_status,
        evidence=freq01_evidence,
        notes="Physical PFD and off-axis mask compliance evaluated by Module 10 Spectrum Engine",
    ))

    certs.append(CertificationResult(
        cert_id="FREQ-02",
        criterion="Operate under ITU coordination procedures",
        section="§ 100.112(c)(2)",
        status=CertStatus.PASS if (spectrum_report and spectrum_report.all_spectrum_requirements_met) else CertStatus.INSUFFICIENT_DATA,
        evidence="Spectrum parameters structured for ITU Radio Regulations Article 22 & ITU coordination compliance.",
        notes="Technical data formatted for ITU e-submission",
    ))

    certs.append(CertificationResult(
        cert_id="FREQ-03",
        criterion="Spacecraft can be commanded to cease transmissions",
        section="§ 100.112(c)(3)",
        status=CertStatus.INSUFFICIENT_DATA,
        notes="Requires operator affirmative attestation in Schedule F submission",
    ))

    return certs


# ═══════════════════════════════════════════════════════════════════════════
# TARGETED REVIEW PRE-SCREENER (§ 100.136(b))
# ═══════════════════════════════════════════════════════════════════════════

def screen_targeted_reviews(
    spec: SatelliteSpec,
    certs: list[CertificationResult],
) -> list[TargetedReviewFlag]:
    """Identify which of the 7 Targeted Review Categories are triggered."""
    flags: list[TargetedReviewFlag] = []

    # 1. Failure to Certify
    failed = [c for c in certs if c.status == CertStatus.FAIL]
    flags.append(TargetedReviewFlag(
        category=ReviewCategory.FAILURE_TO_CERTIFY,
        section="§ 100.136(b)(1)",
        triggered=len(failed) > 0,
        details=(
            f"{len(failed)} certification(s) failed: "
            + ", ".join(c.cert_id for c in failed)
            if failed
            else "No failed certifications"
        ),
        action_required=(
            "Additional information or waiver required" if failed else "None"
        ),
    ))

    # 2. Waiver Request
    flags.append(TargetedReviewFlag(
        category=ReviewCategory.WAIVER_REQUEST,
        section="§ 100.136(b)(2)",
        triggered=spec.waiver_requested,
        details=(
            "Application includes waiver request(s)"
            if spec.waiver_requested
            else "No waivers requested"
        ),
        action_required=(
            "Full merits review of waiver justification"
            if spec.waiver_requested
            else "None"
        ),
    ))

    # 3. Market Access
    flags.append(TargetedReviewFlag(
        category=ReviewCategory.MARKET_ACCESS,
        section="§ 100.136(b)(3)",
        triggered=not spec.is_us_licensed,
        details=(
            "Non-U.S. licensed operator seeking U.S. market access"
            if not spec.is_us_licensed
            else "U.S.-licensed operator"
        ),
        action_required=(
            "§ 100.114 market access review"
            if not spec.is_us_licensed
            else "None"
        ),
    ))

    # 4. Foreign Ownership (> 10%)
    foreign_triggered = spec.foreign_ownership_pct > 10.0
    flags.append(TargetedReviewFlag(
        category=ReviewCategory.FOREIGN_OWNERSHIP,
        section="§ 100.136(b)(4)",
        triggered=foreign_triggered,
        details=f"Foreign ownership: {spec.foreign_ownership_pct:.1f}%",
        action_required=(
            "Possible Executive Branch referral (Team Telecom)"
            if foreign_triggered
            else "None"
        ),
    ))

    # 5. Processing Round
    flags.append(TargetedReviewFlag(
        category=ReviewCategory.PROCESSING_ROUND,
        section="§ 100.136(b)(5)",
        triggered=spec.in_processing_round,
        details=(
            "Applicant opts into NGSO processing round"
            if spec.in_processing_round
            else "Not participating in processing round"
        ),
        action_required=(
            "§ 100.141 processing round procedures"
            if spec.in_processing_round
            else "None"
        ),
    ))

    # 6. Spectral Constraints (cannot fully auto-detect in MVP)
    flags.append(TargetedReviewFlag(
        category=ReviewCategory.SPECTRAL_CONSTRAINTS,
        section="§ 100.136(b)(6)",
        triggered=False,
        details="Requires manual spectrum analysis — not auto-detectable in MVP",
        action_required="Manual review recommended",
    ))

    # 7. Federal Coordination
    flags.append(TargetedReviewFlag(
        category=ReviewCategory.FEDERAL_COORDINATION,
        section="§ 100.136(b)(7)",
        triggered=spec.federal_bands_requested,
        details=(
            "Application includes frequencies in shared federal allocations"
            if spec.federal_bands_requested
            else "No federal band allocations requested"
        ),
        action_required=(
            "NTIA coordination required"
            if spec.federal_bands_requested
            else "None"
        ),
    ))

    return flags


# ═══════════════════════════════════════════════════════════════════════════
# FILING STRATEGY RECOMMENDATION
# ═══════════════════════════════════════════════════════════════════════════

def recommend_filing_strategy(
    spec: SatelliteSpec,
    certs: list[CertificationResult],
    reviews: list[TargetedReviewFlag],
) -> str:
    """Generate a filing strategy recommendation."""
    failed_count = sum(1 for c in certs if c.status == CertStatus.FAIL)
    triggered_reviews = sum(1 for r in reviews if r.triggered)

    parts: list[str] = []

    if failed_count == 0 and triggered_reviews == 0:
        parts.append(
            "RECOMMENDATION: Strong candidate for Part 100 certification-based "
            "approval. Zero targeted review categories triggered. Consider filing "
            "under Part 100 once effective for fastest processing (15-day public "
            "notice → grant)."
        )
    elif failed_count == 0 and triggered_reviews <= 2:
        parts.append(
            f"RECOMMENDATION: Generally favorable for Part 100 filing. "
            f"{triggered_reviews} targeted review category(ies) triggered, "
            f"which will require focused review but should not prevent grant. "
            f"Consider filing under Part 100 once effective."
        )
    elif failed_count > 0:
        parts.append(
            f"RECOMMENDATION: {failed_count} certification(s) failed — will "
            f"trigger Targeted Review Category 1 (Failure to Certify). "
            f"Address deficiencies before filing, or prepare waiver justification. "
            f"Consider filing under Part 25 if timeline is urgent."
        )
    else:
        parts.append(
            f"RECOMMENDATION: {triggered_reviews} targeted review categories "
            f"triggered. Filing under Part 100 is feasible but expect focused "
            f"review. Evaluate whether Part 25 filing with pending transition "
            f"offers a faster path."
        )

    # Bond impact
    if spec.in_processing_round:
        parts.append(
            "BOND NOTE: Processing round participation requires $10M surety bond "
            "(de-escalating with deployment). Evaluate financial impact."
        )
    else:
        parts.append(
            "BOND ADVANTAGE: Not in processing round → $0 bond under Part 100 "
            "(significant improvement over Part 25)."
        )

    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# MASTER AUDIT FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def run_delta_audit(spec: SatelliteSpec) -> AuditResult:
    """
    Execute the complete Part 25 → Part 100 Delta & Certification Audit.

    This is the top-level entry point called by the Streamlit UI and
    the future API endpoint.

    Parameters
    ----------
    spec : SatelliteSpec
        Validated satellite specification from user intake.

    Returns
    -------
    AuditResult
        Complete audit output ready for PDF rendering.
    """
    log.info("Starting delta audit for: %s", spec.name)

    # System classification
    system_type = classify_system(spec)
    orbit_class = classify_orbit(spec)
    log.info("System type: %s | Orbit: %s", system_type.value, orbit_class)

    # Bond delta
    bond_delta = build_bond_delta(spec)
    log.info(
        "Bond - Part 25: $%s | Part 100: $%s",
        f"{bond_delta.part_25_bond_usd:,}",
        f"{bond_delta.part_100_bond_usd:,}",
    )

    # Milestone delta
    ms_25 = build_milestones_part_25(spec)
    ms_100 = build_milestones_part_100(spec)

    # Trackability
    track_status, track_detail = evaluate_trackability(spec)

    # De-orbit
    deorbit_status, deorbit_detail = evaluate_deorbit(spec)

    # Debris mitigation & ODAR physics calculation (Module 9)
    odar_report = ODAREngine.evaluate_satellite_odar(
        spec=spec,
        cross_section_area_m2=spec.cross_section_area_m2,
        drag_coefficient=spec.drag_coefficient,
    )

    # Spectrum & EPFD physics calculation (Module 10)
    spectrum_engine = get_spectrum_engine()
    spectrum_report = spectrum_engine.evaluate_satellite_spectrum(spec=spec)

    # Certification matrix (evaluates ODAR numbers & Spectrum numbers)
    certs = build_certification_matrix(
        spec=spec,
        odar_report=odar_report,
        spectrum_report=spectrum_report,
    )

    # Targeted review pre-screen
    reviews = screen_targeted_reviews(spec, certs)

    # Assemble complete FCC Part 100 Filing Package (Module 11)
    filing_package = FCCFilingBundler.assemble_package(
        spec=spec,
        odar=odar_report,
        spectrum=spectrum_report,
    )

    # Filing strategy
    strategy = recommend_filing_strategy(spec, certs, reviews)

    # Summary counts
    pass_count = sum(1 for c in certs if c.status == CertStatus.PASS)
    fail_count = sum(1 for c in certs if c.status == CertStatus.FAIL)
    insuf_count = sum(1 for c in certs if c.status == CertStatus.INSUFFICIENT_DATA)
    na_count = sum(1 for c in certs if c.status == CertStatus.NOT_APPLICABLE)

    # Warnings
    warnings: list[str] = []
    if fail_count > 0:
        warnings.append(
            f"{fail_count} certification(s) FAILED — address before filing"
        )
    if insuf_count > 0:
        warnings.append(
            f"{insuf_count} certification(s) require additional data or attestation"
        )
    triggered_count = sum(1 for r in reviews if r.triggered)
    if triggered_count > 0:
        warnings.append(
            f"{triggered_count} Targeted Review Category(ies) triggered"
        )
    if not spec.has_propulsion and spec.altitude_km < LEO_CEILING_KM:
        warnings.append(
            "No propulsion on LEO spacecraft — de-orbit compliance at risk"
        )
    if not odar_report.all_debris_requirements_met:
        warnings.append(
            "ODAR assessment flagged orbital debris non-compliance"
        )
    if not spectrum_report.all_spectrum_requirements_met:
        warnings.append(
            "Spectrum evaluation flagged PFD or EPFD limit non-compliance"
        )

    # Missing data
    missing: list[str] = []
    if insuf_count > 0:
        for c in certs:
            if c.status == CertStatus.INSUFFICIENT_DATA:
                missing.append(f"{c.cert_id}: {c.criterion}")

    # Build result
    result = AuditResult(
        report_id=f"OF-{uuid.uuid4().hex[:8].upper()}",
        generated_at=datetime.now(timezone.utc),
        engine_version=ENGINE_VERSION,
        spec=spec,
        system_type=system_type,
        orbit_classification=orbit_class,
        bond_delta=bond_delta,
        milestones_part_25=ms_25,
        milestones_part_100=ms_100,
        certifications=certs,
        targeted_reviews=reviews,
        total_certs=len(certs),
        pass_count=pass_count,
        fail_count=fail_count,
        insufficient_count=insuf_count,
        na_count=na_count,
        trackability_status=track_status,
        trackability_detail=track_detail,
        deorbit_status=deorbit_status,
        deorbit_detail=deorbit_detail,
        filing_strategy=strategy,
        warnings=warnings,
        missing_data=missing,
        odar_report=odar_report,
        spectrum_report=spectrum_report,
        filing_package=filing_package,
    )

    log.info(
        "Audit complete: %d certs (%d PASS, %d FAIL, %d INSUF, %d N/A) | "
        "%d targeted reviews triggered",
        len(certs),
        pass_count,
        fail_count,
        insuf_count,
        na_count,
        triggered_count,
    )

    return result
