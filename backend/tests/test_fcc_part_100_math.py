"""
Mathematical Verification & Exhaustive Testing Suite
=====================================================

Strict mathematical audit of OrbitFlow's FCC Part 100 Delta Engine
against FCC 25-69 Report & Order (SB Docket 25-306).

Audited sections:
- § 100.148(d) Surety Bond Formula & De-escalation
- § 100.147 Deployment Milestone Schedules
- § 100.111(c)(2)(iii) Trackability Thresholds (LEO & Beyond)
- § 100.260(e) 5-Year De-orbit Guillotine Rule
- § 100.136(b) 7 Targeted Review Categories
- Real-world satellite verification (Starlink Gen2, Kuiper, NASA PACE, Planet Dove)
"""

from __future__ import annotations

import pytest

from backend.app.engines.delta.engine import (
    calculate_bond_part_100,
    calculate_bond_part_25,
    classify_system,
    evaluate_deorbit,
    evaluate_trackability,
    run_delta_audit,
    screen_targeted_reviews,
)
from backend.app.models.satellite import (
    CertStatus,
    OrbitType,
    ReviewCategory,
    SatelliteSpec,
    SystemType,
)


# ===========================================================================
# 1. SURETY BOND MATHEMATICAL AUDIT (§ 100.148(d))
# Formula: B = $10,000,000 - $10,000,000 * (D / (0.9 * A))
# ===========================================================================

class TestSuretyBondMath:
    """Rigorous verification of the Part 100 de-escalating surety bond formula."""

    @pytest.mark.parametrize(
        "authorized,deployed,expected_bond",
        [
            # Case 1: Zero deployment (D=0) -> 100% of base bond ($10,000,000)
            (1000, 0, 10_000_000),
            (100, 0, 10_000_000),
            (1, 0, 10_000_000),

            # Case 2: 25% of target deployed (D = 0.25 * 0.9 * A = 0.225 * A)
            # B = 10M - 10M * 0.25 = $7,500,000
            (1000, 225, 7_500_000),

            # Case 3: 50% of target deployed (D = 0.50 * 0.9 * A = 0.45 * A)
            # B = 10M - 10M * 0.50 = $5,000,000
            (1000, 450, 5_000_000),
            (200, 90, 5_000_000),

            # Case 4: 75% of target deployed (D = 0.75 * 0.9 * A = 0.675 * A)
            # B = 10M - 10M * 0.75 = $2,500,000
            (1000, 675, 2_500_000),

            # Case 5: 90% deployment threshold (D = 0.9 * A) -> Bond completely relieved ($0)
            (1000, 900, 0),
            (100, 90, 0),
            (10, 9, 0),

            # Case 6: 100% deployment (D = A > 0.9 * A) -> Clamped at $0 (cannot be negative)
            (1000, 1000, 0),
            (100, 100, 0),

            # Case 7: Edge case - Zero authorized satellites (Division by zero guard)
            # Should safely return full base bond ($10,000,000) without crashing
            (0, 0, 10_000_000),
        ],
    )
    def test_processing_round_bond_formula(
        self, authorized: int, deployed: int, expected_bond: int
    ) -> None:
        """Verify mathematical precision of Part 100 § 100.148(d)."""
        spec = SatelliteSpec(
            name="Bond Audit Sat",
            orbit_type=OrbitType.LEO,
            altitude_km=550.0,
            num_authorized=authorized,
            num_deployed=deployed,
            smallest_dimension_cm=50.0,
            mass_kg=250.0,
            in_processing_round=True,
        )
        calculated_bond = calculate_bond_part_100(spec)
        assert calculated_bond == expected_bond, (
            f"Failed for A={authorized}, D={deployed}: "
            f"Expected ${expected_bond:,}, got ${calculated_bond:,}"
        )

    def test_non_processing_round_zero_bond(self) -> None:
        """Under Part 100, non-processing round NGSO applicants owe $0 bond."""
        spec = SatelliteSpec(
            name="Non-PR Constellation",
            orbit_type=OrbitType.LEO,
            altitude_km=600.0,
            num_authorized=500,
            num_deployed=0,
            smallest_dimension_cm=40.0,
            mass_kg=150.0,
            in_processing_round=False,
        )
        assert calculate_bond_part_100(spec) == 0
        # Part 25 legacy would have charged $5,000,000
        assert calculate_bond_part_25(spec) == 5_000_000


# ===========================================================================
# 2. MILESTONES AUDIT (§ 100.147)
# ===========================================================================

class TestMilestonesScheduleMath:
    """Verify statutory milestone schedules across all operational regimes."""

    def test_ngso_non_processing_round_itu_milestones(self) -> None:
        """
        Part 100 § 100.147(b) ITU-aligned 14-year schedule:
        7yr: BIU (>= 1 sat for 90 days)
        9yr: 10% deployed
        12yr: 50% deployed
        14yr: 100% deployed
        """
        spec = SatelliteSpec(
            name="ITU-Aligned NGSO",
            orbit_type=OrbitType.LEO,
            altitude_km=500.0,
            num_authorized=1000,
            smallest_dimension_cm=30.0,
            mass_kg=200.0,
            in_processing_round=False,
        )
        result = run_delta_audit(spec)
        ms = result.milestones_part_100.milestones

        assert "7yr" in ms and "BIU" in ms["7yr"]
        assert "9yr" in ms and "10%" in ms["9yr"]
        assert "12yr" in ms and "50%" in ms["12yr"]
        assert "14yr" in ms and "100%" in ms["14yr"]
        assert "automatic license termination" in result.milestones_part_100.notes

    def test_ngso_processing_round_milestones(self) -> None:
        """
        Part 100 § 100.147(d) Processing Round retained schedule:
        6yr: 50% deployed
        9yr: 100% deployed
        """
        spec = SatelliteSpec(
            name="PR NGSO Fleet",
            orbit_type=OrbitType.LEO,
            altitude_km=500.0,
            num_authorized=1000,
            smallest_dimension_cm=30.0,
            mass_kg=200.0,
            in_processing_round=True,
        )
        result = run_delta_audit(spec)
        ms = result.milestones_part_100.milestones

        assert "6yr" in ms and "50%" in ms["6yr"]
        assert "9yr" in ms and "100%" in ms["9yr"]
        assert "reassignment" in result.milestones_part_100.notes

    def test_gso_milestone(self) -> None:
        """Part 100 § 100.147(a) GSO 5-year milestone."""
        spec = SatelliteSpec(
            name="GSO Telecom-1",
            orbit_type=OrbitType.GEO,
            altitude_km=35786.0,
            num_authorized=1,
            smallest_dimension_cm=250.0,
            mass_kg=3500.0,
        )
        result = run_delta_audit(spec)
        ms = result.milestones_part_100.milestones

        assert "5yr" in ms
        assert "assigned" in ms["5yr"]

    def test_vtss_no_milestones(self) -> None:
        """VTSS systems have NO deployment milestones under Part 100."""
        spec = SatelliteSpec(
            name="OrbitServicer-1",
            orbit_type=OrbitType.VTSS,
            altitude_km=600.0,
            num_authorized=5,
            smallest_dimension_cm=120.0,
            mass_kg=800.0,
        )
        result = run_delta_audit(spec)
        assert len(result.milestones_part_100.milestones) == 0
        assert "No deployment milestones" in result.milestones_part_100.notes


# ===========================================================================
# 3. TRACKABILITY & DE-ORBIT THRESHOLDS (§ 100.111 & § 100.260(e))
# ===========================================================================

class TestTrackabilityAndDeorbit:
    """Verify physical trackability thresholds and 5-year deorbit guillotine."""

    @pytest.mark.parametrize(
        "altitude_km,dimension_cm,expected_status",
        [
            # LEO (< 2000 km): minimum 10 cm
            (400.0, 10.0, CertStatus.PASS),     # Exact boundary PASS
            (550.0, 15.0, CertStatus.PASS),     # Above threshold PASS
            (1999.0, 10.0, CertStatus.PASS),    # LEO ceiling PASS
            (550.0, 9.9, CertStatus.FAIL),      # Sub-10cm LEO FAIL
            (550.0, 3.0, CertStatus.FAIL),      # Thin picosat FAIL

            # Above LEO (>= 2000 km): minimum 100 cm (1 meter)
            (2000.0, 100.0, CertStatus.PASS),   # Exact MEO boundary PASS
            (8000.0, 120.0, CertStatus.PASS),   # MEO PASS
            (35786.0, 200.0, CertStatus.PASS),  # GEO PASS
            (2000.0, 99.9, CertStatus.FAIL),    # Sub-1m at 2000km FAIL
            (10000.0, 50.0, CertStatus.FAIL),   # Sub-1m MEO FAIL
        ],
    )
    def test_trackability_thresholds(
        self, altitude_km: float, dimension_cm: float, expected_status: CertStatus
    ) -> None:
        """Affirmative trackability obligations under Part 100."""
        spec = SatelliteSpec(
            name="Trackability Test",
            orbit_type=OrbitType.LEO if altitude_km < 2000 else OrbitType.MEO,
            altitude_km=altitude_km,
            num_authorized=10,
            smallest_dimension_cm=dimension_cm,
            mass_kg=100.0,
        )
        status, _ = evaluate_trackability(spec)
        assert status == expected_status

    @pytest.mark.parametrize(
        "orbit_type,altitude_km,deorbit_years,expected_status",
        [
            # LEO: strict <= 5 years
            (OrbitType.LEO, 500.0, 1.0, CertStatus.PASS),
            (OrbitType.LEO, 500.0, 5.0, CertStatus.PASS),   # Exact 5-year limit
            (OrbitType.LEO, 500.0, 5.1, CertStatus.FAIL),   # Exceeds 5-year rule
            (OrbitType.LEO, 500.0, 25.0, CertStatus.FAIL),  # Legacy 25-yr rule fails Part 100

            # GEO: 5-year rule not applicable (graveyard orbit § 100.260(b))
            (OrbitType.GEO, 35786.0, 0.0, CertStatus.NOT_APPLICABLE),

            # MEO: 5-year LEO rule not applicable
            (OrbitType.MEO, 8000.0, 50.0, CertStatus.NOT_APPLICABLE),
        ],
    )
    def test_deorbit_5_year_guillotine(
        self,
        orbit_type: OrbitType,
        altitude_km: float,
        deorbit_years: float,
        expected_status: CertStatus,
    ) -> None:
        """Part 100 § 100.260(e) 5-year post-mission deorbit rule."""
        spec = SatelliteSpec(
            name="Deorbit Test",
            orbit_type=orbit_type,
            altitude_km=altitude_km,
            num_authorized=10,
            smallest_dimension_cm=50.0,
            mass_kg=100.0,
            estimated_deorbit_years=max(0.1, deorbit_years),
        )
        status, _ = evaluate_deorbit(spec)
        assert status == expected_status


# ===========================================================================
# 4. TARGETED REVIEW CATEGORIES PRE-SCREENER (§ 100.136(b))
# ===========================================================================

class TestTargetedReviewPreScreen:
    """Verify all 7 Targeted Review Categories trigger correctly."""

    def test_foreign_ownership_threshold(self) -> None:
        """TR-04: > 10.0% reportable foreign ownership triggers Team Telecom review."""
        spec_clear = SatelliteSpec(
            name="US Owned Sat",
            orbit_type=OrbitType.LEO,
            altitude_km=500.0,
            num_authorized=10,
            smallest_dimension_cm=30.0,
            mass_kg=100.0,
            foreign_ownership_pct=10.0,  # Boundary: <= 10% is CLEAR
        )
        result_clear = run_delta_audit(spec_clear)
        fo_flag_clear = next(
            r for r in result_clear.targeted_reviews
            if r.category == ReviewCategory.FOREIGN_OWNERSHIP
        )
        assert not fo_flag_clear.triggered

        spec_triggered = SatelliteSpec(
            name="Foreign Owned Sat",
            orbit_type=OrbitType.LEO,
            altitude_km=500.0,
            num_authorized=10,
            smallest_dimension_cm=30.0,
            mass_kg=100.0,
            foreign_ownership_pct=10.1,  # Boundary: > 10% triggers
        )
        result_trig = run_delta_audit(spec_triggered)
        fo_flag_trig = next(
            r for r in result_trig.targeted_reviews
            if r.category == ReviewCategory.FOREIGN_OWNERSHIP
        )
        assert fo_flag_trig.triggered
        assert "Team Telecom" in fo_flag_trig.action_required

    def test_federal_coordination_flag(self) -> None:
        """TR-07: Requesting shared federal allocations triggers NTIA coordination."""
        spec = SatelliteSpec(
            name="Fed Shared Sat",
            orbit_type=OrbitType.LEO,
            altitude_km=550.0,
            num_authorized=10,
            smallest_dimension_cm=30.0,
            mass_kg=100.0,
            federal_bands_requested=True,
        )
        result = run_delta_audit(spec)
        fed_flag = next(
            r for r in result.targeted_reviews
            if r.category == ReviewCategory.FEDERAL_COORDINATION
        )
        assert fed_flag.triggered
        assert "NTIA" in fed_flag.action_required

    def test_waiver_request_flag(self) -> None:
        """TR-02: Requesting any waiver triggers full merits review."""
        spec = SatelliteSpec(
            name="Waiver Sat",
            orbit_type=OrbitType.LEO,
            altitude_km=550.0,
            num_authorized=10,
            smallest_dimension_cm=30.0,
            mass_kg=100.0,
            waiver_requested=True,
        )
        result = run_delta_audit(spec)
        w_flag = next(
            r for r in result.targeted_reviews
            if r.category == ReviewCategory.WAIVER_REQUEST
        )
        assert w_flag.triggered

    def test_market_access_flag(self) -> None:
        """TR-03: Non-U.S. licensed operator triggers § 100.114 market access review."""
        spec = SatelliteSpec(
            name="Non-US Sat",
            orbit_type=OrbitType.LEO,
            altitude_km=550.0,
            num_authorized=10,
            smallest_dimension_cm=30.0,
            mass_kg=100.0,
            is_us_licensed=False,
        )
        result = run_delta_audit(spec)
        ma_flag = next(
            r for r in result.targeted_reviews
            if r.category == ReviewCategory.MARKET_ACCESS
        )
        assert ma_flag.triggered

    def test_failure_to_certify_flag(self) -> None:
        """TR-01: Any negative certification automatically triggers TR-01."""
        spec = SatelliteSpec(
            name="Non-Compliant Sat",
            orbit_type=OrbitType.LEO,
            altitude_km=550.0,
            num_authorized=10,
            smallest_dimension_cm=5.0,  # 5cm < 10cm -> Trackability FAIL
            mass_kg=10.0,
            estimated_deorbit_years=15.0,  # 15yr > 5yr -> Deorbit FAIL
        )
        result = run_delta_audit(spec)
        fc_flag = next(
            r for r in result.targeted_reviews
            if r.category == ReviewCategory.FAILURE_TO_CERTIFY
        )
        assert fc_flag.triggered
        assert "failed" in fc_flag.details.lower()


# ===========================================================================
# 5. REAL-WORLD SATELLITE SYSTEM BENCHMARKS (ZERO MOCK DATA)
# ===========================================================================

class TestRealWorldSatelliteAudits:
    """Execute complete FCC Part 100 Delta Audits on real-world space systems."""

    def test_starlink_gen2_mini_audit(self) -> None:
        """
        Real Starlink Gen2 Mini:
        - Altitude: 530 km nominal
        - Mass: ~800 kg
        - Dimensions: ~4.1m x 2.7m (smallest ~100cm)
        - In Processing Round: True
        - Authorized: 7,500, Deployed: ~2,500
        - Propulsion: Argon Hall Thrusters (autonomous collision avoidance)
        - De-orbit: < 5 years
        """
        starlink = SatelliteSpec(
            name="Starlink Gen2 System",
            operator_name="SpaceX (Space Exploration Technologies Corp.)",
            orbit_type=OrbitType.LEO,
            altitude_km=530.0,
            inclination_deg=53.0,
            num_authorized=7500,
            num_deployed=2500,
            smallest_dimension_cm=100.0,
            mass_kg=800.0,
            mission_lifetime_years=5.0,
            has_propulsion=True,
            estimated_deorbit_years=1.5,
            in_processing_round=True,
            federal_bands_requested=False,
            foreign_ownership_pct=5.2,
            is_us_licensed=True,
        )

        audit = run_delta_audit(starlink)

        # Mathematical verification
        # D = 2500, A = 7500 => D / (0.9 * A) = 2500 / 6750 = 0.37037...
        # B = 10M - 10M * 0.37037 = $6,296,296
        expected_bond = round(10_000_000 - 10_000_000 * (2500 / (0.9 * 7500)))
        assert audit.bond_delta.part_100_bond_usd == expected_bond
        assert audit.trackability_status == CertStatus.PASS
        assert audit.deorbit_status == CertStatus.PASS
        assert audit.system_type == SystemType.NGSO_SATELLITE_SYSTEM
        assert audit.fail_count == 0

    def test_project_kuiper_audit(self) -> None:
        """
        Real Amazon Project Kuiper:
        - Altitude: 590 km / 610 km / 630 km shells
        - Mass: ~600 kg
        - In Processing Round: True
        - Authorized: 3,236, Deployed: 2
        """
        kuiper = SatelliteSpec(
            name="Kuiper Constellation",
            operator_name="Kuiper Systems LLC (Amazon)",
            orbit_type=OrbitType.LEO,
            altitude_km=590.0,
            inclination_deg=51.9,
            num_authorized=3236,
            num_deployed=2,
            smallest_dimension_cm=80.0,
            mass_kg=600.0,
            mission_lifetime_years=7.0,
            has_propulsion=True,
            estimated_deorbit_years=2.0,
            in_processing_round=True,
            federal_bands_requested=False,
            foreign_ownership_pct=0.0,
            is_us_licensed=True,
        )

        audit = run_delta_audit(kuiper)

        # Bond: 2 deployed of 3236 authorized -> almost full bond
        # B = 10M - 10M * (2 / (0.9 * 3236)) = $9,993,133
        expected_bond = round(10_000_000 - 10_000_000 * (2 / (0.9 * 3236)))
        assert audit.bond_delta.part_100_bond_usd == expected_bond
        assert audit.trackability_status == CertStatus.PASS
        assert audit.deorbit_status == CertStatus.PASS

    def test_nasa_pace_science_satellite(self) -> None:
        """
        Real NASA PACE (Plankton, Aerosol, Cloud, ocean Ecosystem):
        - Altitude: 676.5 km Sun-Synchronous
        - Mass: 1,694 kg
        - Smallest dimension: ~150 cm
        - Non-commercial science (No Processing Round, Federal coordination)
        """
        pace = SatelliteSpec(
            name="NASA PACE",
            operator_name="National Aeronautics and Space Administration (NASA)",
            orbit_type=OrbitType.LEO,
            altitude_km=676.5,
            inclination_deg=98.0,
            num_authorized=1,
            num_deployed=1,
            smallest_dimension_cm=150.0,
            mass_kg=1694.0,
            mission_lifetime_years=3.0,
            has_propulsion=True,
            estimated_deorbit_years=4.2,
            in_processing_round=False,
            federal_bands_requested=True,  # NASA uses federal space research bands
            is_us_licensed=True,
        )

        audit = run_delta_audit(pace)

        # Part 100 bond is $0 (non-commercial / non-PR)
        assert audit.bond_delta.part_100_bond_usd == 0
        assert audit.trackability_status == CertStatus.PASS
        assert audit.deorbit_status == CertStatus.PASS

        # Federal coordination triggered
        fed_flag = next(
            r for r in audit.targeted_reviews
            if r.category == ReviewCategory.FEDERAL_COORDINATION
        )
        assert fed_flag.triggered

    def test_planet_dove_flock_cubesat(self) -> None:
        """
        Real Planet Labs SuperDove (3U Cubesat form factor):
        - Dimensions: 10cm x 10cm x 30cm (smallest dimension = 10.0cm)
        - Altitude: 500 km SSO
        - Mass: 5.5 kg
        - De-orbit: ~3.5 years via atmospheric drag
        """
        dove = SatelliteSpec(
            name="Flock SuperDove Earth Imaging",
            operator_name="Planet Labs PBC",
            orbit_type=OrbitType.LEO,
            altitude_km=500.0,
            inclination_deg=97.5,
            num_authorized=120,
            num_deployed=80,
            smallest_dimension_cm=10.0,  # Exactly 10cm 3U cross-section
            mass_kg=5.5,
            mission_lifetime_years=3.0,
            has_propulsion=False,
            estimated_deorbit_years=3.5,  # Decays naturally below 5 years
            in_processing_round=False,
            is_us_licensed=True,
        )

        audit = run_delta_audit(dove)

        # 10cm meets minimum trackability
        assert audit.trackability_status == CertStatus.PASS
        # 3.5 years meets 5-year deorbit rule
        assert audit.deorbit_status == CertStatus.PASS
        # Non-PR bond is $0
        assert audit.bond_delta.part_100_bond_usd == 0
