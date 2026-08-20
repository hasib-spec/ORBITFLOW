"""
OrbitFlow Module 12: ITU Validation Engine
==========================================
Validates ITU Appendix 4 Notices against ITU Radio Regulations,
Article 21 PFD limits, and 47 CFR § 100.115 statutory rules.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict, List

from backend.app.engines.itu.models import (
    ITUAppendix4Notice,
    ITUNetworkOrbitType,
    ITUNoticeType,
)


class ITUValidationEngine:
    @staticmethod
    def validate_full_filing(
        notice: ITUAppendix4Notice,
        active_applicant_filing_count: int = 1,
        current_date: date | None = None,
    ) -> Dict[str, Any]:
        curr = current_date or date.today()
        issues: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        # 1. 47 CFR § 100.115(b) Max 5 Pending Filings Quota
        if active_applicant_filing_count > 5 and not notice.tracker.underlying_fcc_application_file_num:
            issues.append({
                "rule": "47 CFR § 100.115(b)",
                "category": "STATUTORY_QUOTA_EXCEEDED",
                "message": f"Applicant has {active_applicant_filing_count} active ITU filings without underlying space applications (maximum allowable is 5).",
            })

        # 2. 47 CFR § 100.115(c) 2-Year Clock Evaluation
        clock_status = notice.tracker.evaluate_2yr_clock(curr)
        if clock_status.get("status") == "EXPIRED_SUBJECT_TO_MANDATORY_WITHDRAWAL":
            issues.append({
                "rule": "47 CFR § 100.115(c)",
                "category": "TWO_YEAR_CLOCK_EXPIRED",
                "message": f"2-Year statutory clock expired {clock_status.get('days_expired')} days ago without space station application submission.",
            })

        # 3. 7-Year Regulatory BIU Clock (RR No. 11.44)
        days_to_biu = (notice.planned_biu_date - curr).days
        if days_to_biu > (7 * 365.25):
            issues.append({
                "rule": "ITU RR No. 11.44",
                "category": "BIU_EXCEEDS_7_YEARS",
                "message": f"Planned Bringing-Into-Use date ({notice.planned_biu_date}) exceeds 7-year regulatory ceiling from date of receipt.",
            })

        # 4. Station Class & Frequency Band Validation (ITU Article 5)
        for c in notice.carriers:
            f = c.center_frequency_mhz
            stn = c.station_class.value

            # Ku-band FSS Downlink check (10.7 - 12.75 GHz)
            if 10700.0 <= f <= 12750.0 and stn not in ["EC", "ET"]:
                warnings.append({
                    "rule": "ITU RR Article 5",
                    "category": "UNCONVENTIONAL_STATION_CLASS",
                    "message": f"Carrier {c.carrier_id} at {f} MHz is in Ku FSS band but specifies Station Class '{stn}' instead of 'EC'.",
                })

            # Ka-band FSS Uplink check (27.5 - 30.0 GHz)
            if 27500.0 <= f <= 30000.0 and c.direction.value != "R":
                issues.append({
                    "rule": "ITU RR Article 5",
                    "category": "INVALID_DIRECTION_FOR_ALLOCATION",
                    "message": f"Carrier {c.carrier_id} at {f} MHz is in Earth-to-space Ka band but specifies direction '{c.direction.value}' (Transmit).",
                })

        # 5. PFD Stepping Check for space-to-Earth downlinks (RR Article 21 / SF.1006)
        for c in notice.carriers:
            if c.direction.value == "E" and (10700.0 <= c.center_frequency_mhz <= 12750.0 or 17700.0 <= c.center_frequency_mhz <= 20200.0):
                if notice.orbit_type == ITUNetworkOrbitType.NON_GEO and notice.ngso_orbit:
                    h = notice.ngso_orbit.altitude_perigee_km
                    d_nadir = h * 1000.0
                    pfd_nadir = c.emission.max_psd_dbw_hz + 10.0 * math.log10(1e6) - 10.0 * math.log10(4.0 * math.pi * (d_nadir ** 2))
                    if pfd_nadir > -105.0:
                        issues.append({
                            "rule": "ITU RR Article 21.16 / ITU-R SF.1006",
                            "category": "PFD_LIMIT_EXCEEDED",
                            "message": f"Carrier {c.carrier_id} peak PFD at nadir ({pfd_nadir:.1f} dB(W/(m²·MHz))) exceeds -105.0 dBW/m² limit.",
                        })

        return {
            "is_valid": len(issues) == 0,
            "issues_count": len(issues),
            "warnings_count": len(warnings),
            "issues": issues,
            "warnings": warnings,
            "clock_status": clock_status,
        }
