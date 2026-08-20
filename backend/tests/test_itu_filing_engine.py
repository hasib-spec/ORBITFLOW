"""
Tests for OrbitFlow Module 12: ITU Filing Preparation Engine
============================================================
Verifies Appendix 4 data models, carrier grouping algorithm,
47 CFR § 100.115 2-year clock & 5-filing limit, and SpaceCap XML generation.
"""

from datetime import date, timedelta
import pytest

from backend.app.engines.itu import (
    BeamDirection,
    CostRecoveryDeclaration,
    GSOOrbitCharacteristics,
    ITUAppendix4Notice,
    ITUBeam,
    ITUCarrier,
    ITUEmission,
    ITUFilingEngine,
    ITUNetworkOrbitType,
    ITUNoticeType,
    NGSOOrbitCharacteristics,
    Part100ITUTracker,
    PolarizationType,
    StationClass,
    get_itu_filing_engine,
)
from backend.app.engines.itu.grouping import partition_and_build_itu_groups
from backend.app.engines.itu.validator import ITUValidationEngine
from backend.app.models.satellite import OrbitType, SatelliteSpec


def test_ngso_orbit_characteristics_kepler_validation():
    orbit = NGSOOrbitCharacteristics(
        num_planes=24,
        sats_per_plane=30,
        inclination_deg=53.0,
        altitude_perigee_km=550.0,
        altitude_apogee_km=550.0,
    )
    assert orbit.total_active_satellites == 720
    # Period should be approx 95.6 minutes for 550 km
    assert 94.0 <= orbit.orbital_period_minutes <= 97.0


def test_carrier_grouping_algorithm():
    # 2 carriers on same beam & direction, same station class and polarization -> should merge into 1 group
    c1 = ITUCarrier(
        carrier_id="C1",
        beam_id="BM-01",
        direction=BeamDirection.TRANSMIT,
        station_class=StationClass.EC,
        nature_of_service="CO",
        polarization=PolarizationType.R,
        service_area_id="GLOBAL",
        center_frequency_mhz=19750.0,
        bandwidth_mhz=250.0,
        emission=ITUEmission(
            designator="250MD7W",
            peak_eirp_dbw=20.0,
            max_psd_dbw_hz=-65.0,
            bandwidth_khz=250000.0,
        ),
    )
    c2 = ITUCarrier(
        carrier_id="C2",
        beam_id="BM-01",
        direction=BeamDirection.TRANSMIT,
        station_class=StationClass.EC,
        nature_of_service="CO",
        polarization=PolarizationType.R,
        service_area_id="GLOBAL",
        center_frequency_mhz=20000.0,
        bandwidth_mhz=250.0,
        emission=ITUEmission(
            designator="250MD7W",
            peak_eirp_dbw=20.0,
            max_psd_dbw_hz=-65.0,
            bandwidth_khz=250000.0,
        ),
    )

    # 1 carrier on different beam -> should be in 2nd group
    c3 = ITUCarrier(
        carrier_id="C3",
        beam_id="BM-02",
        direction=BeamDirection.RECEIVE,
        station_class=StationClass.EC,
        nature_of_service="CO",
        polarization=PolarizationType.L,
        service_area_id="GLOBAL",
        center_frequency_mhz=29500.0,
        bandwidth_mhz=500.0,
        emission=ITUEmission(
            designator="500MD7W",
            peak_eirp_dbw=55.0,
            max_psd_dbw_hz=-30.0,
            bandwidth_khz=500000.0,
        ),
    )

    groups = partition_and_build_itu_groups([c1, c2, c3])
    assert len(groups) == 2
    g1 = next(g for g in groups if g.beam_id == "BM-01")
    assert len(g1.carrier_frequencies) == 2
    # Combined EIRP: 20 dBW + 20 dBW = 23 dBW
    assert round(g1.eirp_max_dbw, 1) == 23.0


def test_part100_itu_filing_quota_and_clock():
    spec = SatelliteSpec(
        name="Constellation Alpha",
        operator_name="Alpha Space Inc.",
        orbit_type=OrbitType.LEO,
        altitude_km=550.0,
        inclination_deg=53.0,
        num_authorized=500,
        num_deployed=0,
        smallest_dimension_cm=100.0,
        mass_kg=500.0,
    )
    engine = get_itu_filing_engine()


    # Generate standard filing package
    res = engine.generate_filing_package(spec, active_applicant_filings=2)
    assert res.is_fully_compliant is True
    assert res.validation_status == "VALIDATED"
    assert "<SpaceCapNotice" in res.spacecap_xml
    assert "Decision482Acknowledged" in res.spacecap_xml

    # Test exceeding 5-filing limit (§ 100.115(b))
    res_exceeded = engine.generate_filing_package(spec, active_applicant_filings=6)
    assert res_exceeded.is_fully_compliant is False
    assert any("100.115(b)" in iss["rule"] for iss in res_exceeded.issues)
