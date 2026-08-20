"""
OrbitFlow Module 12: ITU Filing Preparation Master Engine
=========================================================
Synthesizes satellite specifications into verified ITU Appendix 4 Notices,
executes Article 9 / 11 coordination trigger evaluations, enforces 47 CFR § 100.115
rules, and generates SpaceCap XML packages.
"""

from __future__ import annotations

import math
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional


from backend.app.core.config import get_logger
from backend.app.engines.itu.exporter import SpaceCapXMLExporter
from backend.app.engines.itu.grouping import partition_and_build_itu_groups
from backend.app.engines.itu.models import (
    BeamDirection,
    CostRecoveryDeclaration,
    GSOOrbitCharacteristics,
    ITUAppendix4Notice,
    ITUBeam,
    ITUCarrier,
    ITUEmission,
    ITUFilingPackageResult,
    ITUNetworkOrbitType,
    ITUNoticeType,
    NGSOOrbitCharacteristics,
    Part100ITUTracker,
    PolarizationType,
    StationClass,
)
from backend.app.engines.itu.validator import ITUValidationEngine
from backend.app.models.satellite import OrbitType, SatelliteSpec

log = get_logger(__name__)


class ITUFilingEngine:
    """Master engine for ITU satellite network filing generation and compliance."""

    def generate_filing_package(
        self,
        spec: SatelliteSpec,
        notice_type: ITUNoticeType = ITUNoticeType.CR_C,
        active_applicant_filings: int = 1,
        authorizing_officer: str = "Haseeb Ahmad",
        authorizing_title: str = "Lead Systems Architect & Regulatory Counsel",
        billing_email: str = "regulatory@orbitflow.io",
        custom_carriers: Optional[List[ITUCarrier]] = None,
        custom_beams: Optional[List[ITUBeam]] = None,
    ) -> ITUFilingPackageResult:
        """
        Generate a submission-ready ITU Appendix 4 / SpaceCap filing package from SatelliteSpec.
        """
        filing_id = f"ITU-{uuid.uuid4().hex[:8].upper()}"
        log.info("Generating ITU filing package %s for %s", filing_id, spec.name)

        # 1. Derive Orbit Characteristics
        if spec.orbit_type == OrbitType.GEO:
            orbit_type = ITUNetworkOrbitType.GEO
            gso_orbit = GSOOrbitCharacteristics(
                nominal_longitude_deg=-95.0,
                longitudinal_tolerance_deg=0.05,
                inclination_excursion_deg=0.05,
            )
            ngso_orbit = None
        else:
            orbit_type = ITUNetworkOrbitType.NON_GEO
            planes = max(1, min(72, int(math.ceil(spec.num_authorized / 50.0)))) if spec.num_authorized > 1 else 1
            sats_per_plane = max(1, int(math.ceil(spec.num_authorized / planes)))
            ngso_orbit = NGSOOrbitCharacteristics(
                num_planes=planes,
                sats_per_plane=sats_per_plane,
                num_spares=int(spec.num_authorized * 0.05),
                inclination_deg=spec.inclination_deg,
                altitude_perigee_km=spec.altitude_km,
                altitude_apogee_km=spec.altitude_km + 10.0,
                min_elevation_deg=10.0,
            )
            gso_orbit = None

        # 2. Derive Beams & Carriers if not custom supplied
        beams = custom_beams or self._derive_default_itu_beams(spec)
        carriers = custom_carriers or self._derive_default_itu_carriers(spec)

        # 3. Build Cost Recovery Declaration (§ 100.115(d))
        cost_recovery = CostRecoveryDeclaration(
            applicant_legal_name=spec.operator_name or "Commercial Space Operator",
            authorizing_officer_name=authorizing_officer,
            authorizing_officer_title=authorizing_title,
            billing_address="100 Space Modernization Way, Washington DC 20001",
            billing_email=billing_email,
            decision_482_acknowledgement=True,
        )

        # 4. Build Tracker (§ 100.115 state machine)
        tracker = Part100ITUTracker(
            project_id=filing_id,
            applicant_id=spec.operator_name,
            itu_filing_status="READY_FOR_FCC",
            fcc_itu_submission_date=date.today(),
            underlying_fcc_application_file_num=None,
        )

        # 5. Assemble Notice
        planned_biu = date.today() + timedelta(days=365 * 3)  # Nominal 3-year lead time
        sat_clean_name = spec.name.split("(")[0].strip()[:20].upper().replace(" ", "-")

        notice = ITUAppendix4Notice(
            satellite_name=sat_clean_name,
            notifying_administration="USA",
            notice_type=notice_type,
            orbit_type=orbit_type,
            planned_biu_date=planned_biu,
            ngso_orbit=ngso_orbit,
            gso_orbit=gso_orbit,
            beams=beams,
            carriers=carriers,
            cost_recovery=cost_recovery,
            tracker=tracker,
        )

        # 6. Validate Notice
        val_res = ITUValidationEngine.validate_full_filing(
            notice,
            active_applicant_filing_count=active_applicant_filings,
            current_date=date.today(),
        )

        # 7. Form Groups and Generate SpaceCap XML
        groups = partition_and_build_itu_groups(carriers)
        spacecap_xml = SpaceCapXMLExporter.generate_spacecap_xml(notice)

        return ITUFilingPackageResult(
            filing_id=filing_id,
            satellite_name=sat_clean_name,
            notice_type=notice_type,
            orbit_type=orbit_type,
            validation_status="VALIDATED" if val_res["is_valid"] else "DEFICIENCIES_DETECTED",
            is_fully_compliant=val_res["is_valid"],
            issues=val_res["issues"],
            warnings=val_res["warnings"],
            groups_formed=groups,
            spacecap_xml=spacecap_xml,
            cost_recovery_valid=True,
            two_year_clock_status=val_res["clock_status"],
        )

    def _derive_default_itu_beams(self, spec: SatelliteSpec) -> List[ITUBeam]:
        beams: list[ITUBeam] = []
        if spec.orbit_type == OrbitType.GEO:
            beams.append(
                ITUBeam(
                    beam_id="BM-GSO-KU-TX",
                    direction=BeamDirection.TRANSMIT,
                    peak_gain_dbi=38.5,
                    beamwidth_3db_deg=2.2,
                    pointing_type="STEERABLE",
                )
            )
            beams.append(
                ITUBeam(
                    beam_id="BM-GSO-KU-RX",
                    direction=BeamDirection.RECEIVE,
                    peak_gain_dbi=42.0,
                    beamwidth_3db_deg=1.8,
                    pointing_type="STEERABLE",
                    noise_temperature_k=450.0,
                    gt_ratio_db_k=15.5,
                )
            )
        else:
            beams.append(
                ITUBeam(
                    beam_id="BM-NGSO-KA-DL",
                    direction=BeamDirection.TRANSMIT,
                    peak_gain_dbi=36.0,
                    beamwidth_3db_deg=1.5,
                    pointing_type="STEERABLE",
                )
            )
            beams.append(
                ITUBeam(
                    beam_id="BM-NGSO-KA-UL",
                    direction=BeamDirection.RECEIVE,
                    peak_gain_dbi=39.0,
                    beamwidth_3db_deg=1.2,
                    pointing_type="STEERABLE",
                    noise_temperature_k=380.0,
                    gt_ratio_db_k=13.2,
                )
            )
        return beams

    def _derive_default_itu_carriers(self, spec: SatelliteSpec) -> List[ITUCarrier]:
        carriers: list[ITUCarrier] = []
        if spec.orbit_type == OrbitType.GEO:
            carriers.append(
                ITUCarrier(
                    carrier_id="CAR-GSO-DL-01",
                    beam_id="BM-GSO-KU-TX",
                    direction=BeamDirection.TRANSMIT,
                    station_class=StationClass.EC,
                    nature_of_service="CO",
                    polarization=PolarizationType.L,
                    service_area_id="USA",
                    center_frequency_mhz=11950.0,
                    bandwidth_mhz=250.0,
                    emission=ITUEmission(
                        designator="250MD7W",
                        peak_eirp_dbw=55.0,
                        max_psd_dbw_hz=-29.0,
                        min_psd_dbw_hz=-49.0,
                        bandwidth_khz=250000.0,
                        modulation_type="16APSK",
                    ),
                )
            )
        else:
            # NGSO Ka-band Downlink (Gateway & Broadband)
            carriers.append(
                ITUCarrier(
                    carrier_id="CAR-NGSO-DL-KA",
                    beam_id="BM-NGSO-KA-DL",
                    direction=BeamDirection.TRANSMIT,
                    station_class=StationClass.EC,
                    nature_of_service="CO",
                    polarization=PolarizationType.R,
                    service_area_id="GLOBAL",
                    center_frequency_mhz=19950.0,
                    bandwidth_mhz=500.0,
                    emission=ITUEmission(
                        designator="500MD7W",
                        peak_eirp_dbw=23.0,
                        max_psd_dbw_hz=-64.0,
                        min_psd_dbw_hz=-84.0,
                        bandwidth_khz=500000.0,
                        modulation_type="QPSK",
                    ),
                )
            )
            # NGSO Ka-band Uplink (Gateway & Broadband)
            carriers.append(
                ITUCarrier(
                    carrier_id="CAR-NGSO-UL-KA",
                    beam_id="BM-NGSO-KA-UL",
                    direction=BeamDirection.RECEIVE,
                    station_class=StationClass.EC,
                    nature_of_service="CO",
                    polarization=PolarizationType.L,
                    service_area_id="GLOBAL",
                    center_frequency_mhz=29750.0,
                    bandwidth_mhz=500.0,
                    emission=ITUEmission(
                        designator="500MD7W",
                        peak_eirp_dbw=58.0,
                        max_psd_dbw_hz=-29.0,
                        min_psd_dbw_hz=-49.0,
                        bandwidth_khz=500000.0,
                        modulation_type="16APSK",
                    ),
                )
            )
        return carriers


_itu_engine: Optional[ITUFilingEngine] = None


def get_itu_filing_engine() -> ITUFilingEngine:
    global _itu_engine
    if _itu_engine is None:
        _itu_engine = ITUFilingEngine()
    return _itu_engine
