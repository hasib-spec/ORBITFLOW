"""
OrbitFlow Module 19: Schedule B XML Generator & Pre-Grant Validator
===================================================================
Serializes Nationwide Non-Site Earth Station Envelopes and Site Registrations
into validated FCC Form 312 Schedule B XML, and evaluates Pre-Grant NIB eligibility.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import List
from xml.dom import minidom

from backend.app.engines.earth_station.models import (
    FrequencyBandEnvelope,
    PreGrantVerificationResult,
    SiteRegistrationData,
)


class ScheduleBGenerator:
    @classmethod
    def generate_xml(
        cls,
        lead_callsign: str,
        applicant_name: str,
        frn: str,
        envelope_bands: List[FrequencyBandEnvelope],
        sites: List[SiteRegistrationData],
    ) -> str:
        root = ET.Element("Form312ScheduleB", {
            "xmlns": "http://transition.fcc.gov/space/part100/v1",
            "ruleSection": "47 CFR § 100.120 / § 100.121",
            "filingType": "NATIONWIDE_NON_SITE_REGISTRATION",
        })

        header = ET.SubElement(root, "LicenseHeader")
        ET.SubElement(header, "LeadLicenseCallSign").text = lead_callsign
        ET.SubElement(header, "ApplicantLegalName").text = applicant_name
        ET.SubElement(header, "FRN").text = frn
        ET.SubElement(header, "LicenseType").text = "NATIONWIDE_NON_SITE"
        ET.SubElement(header, "Regime").text = "FCC Part 100 (SB Docket 25-306)"
        ET.SubElement(header, "AuthorizedLicenseTermYears").text = "20"

        # Technical Envelope Authorized under § 100.120
        env_elem = ET.SubElement(root, "NationwideTechnicalEnvelope")
        for b in envelope_bands:
            b_elem = ET.SubElement(env_elem, "AuthorizedFrequencyBand", {"id": b.band_id})
            ET.SubElement(b_elem, "Direction").text = b.direction
            ET.SubElement(b_elem, "BandName").text = b.band_name
            ET.SubElement(b_elem, "LowerFrequencyMHz").text = f"{b.lower_freq_mhz:.2f}"
            ET.SubElement(b_elem, "UpperFrequencyMHz").text = f"{b.upper_freq_mhz:.2f}"
            ET.SubElement(b_elem, "MaxAggregateEIRP_dBW").text = f"{b.max_aggregate_eirp_dbw:.1f}"
            ET.SubElement(b_elem, "MaxEIRPDensity_dBW_4kHz").text = f"{b.max_eirp_density_dbw_4khz:.1f}"
            ET.SubElement(b_elem, "MaxEIRPDensity_dBW_1MHz").text = f"{b.max_eirp_density_dbw_1mhz:.1f}"
            emiss = ET.SubElement(b_elem, "AuthorizedEmissions")
            for em in b.emission_designators:
                ET.SubElement(emiss, "EmissionDesignator").text = em

        # Registered Sites under § 100.121
        sites_elem = ET.SubElement(root, "SiteRegistrations")
        for s in sites:
            s_elem = ET.SubElement(sites_elem, "SiteRegistration", {"siteId": s.site_id})
            ET.SubElement(s_elem, "SiteName").text = s.site_name
            ET.SubElement(s_elem, "SiteClassification").text = s.classification.value

            geo = ET.SubElement(s_elem, "GeographicCoordinates")
            ET.SubElement(geo, "Datum").text = "WGS-84"
            ET.SubElement(geo, "LatitudeDecimalDegrees").text = f"{s.latitude_deg:.6f}"
            ET.SubElement(geo, "LongitudeDecimalDegrees").text = f"{s.longitude_deg:.6f}"
            ET.SubElement(geo, "SiteElevationAMSL_m").text = f"{s.site_elevation_amsl_m:.1f}"

            ant_group = ET.SubElement(s_elem, "AntennaAssemblies")
            for a in s.antennas:
                a_elem = ET.SubElement(ant_group, "AntennaAssembly", {"antennaId": a.antenna_id})
                ET.SubElement(a_elem, "Manufacturer").text = a.manufacturer
                ET.SubElement(a_elem, "ModelNumber").text = a.model_number
                ET.SubElement(a_elem, "DiameterMeters").text = f"{a.diameter_meters:.2f}"
                ET.SubElement(a_elem, "CenterOfRadiationAGL_m").text = f"{a.center_of_radiation_agl_m:.2f}"
                ET.SubElement(a_elem, "Polarization").text = a.polarization.value
                ET.SubElement(a_elem, "FeedLoss_dB").text = f"{a.feed_loss_db:.2f}"
                ET.SubElement(a_elem, "LNA_NoiseTemperature_K").text = f"{a.lna_noise_temp_k:.1f}"

            # Frequency coordination record
            coord = ET.SubElement(s_elem, "FrequencyCoordinationRecord")
            ET.SubElement(coord, "CoordinationAgency").text = s.coordination_agency
            ET.SubElement(coord, "CoordinationCaseID").text = s.coordination_case_id
            ET.SubElement(coord, "PCN_Status").text = (
                "COMPLETED_NO_UNRESOLVED_OBJECTIONS" if s.pcn_completed_no_conflicts else "PENDING_RESOLUTIONS"
            )
            ET.SubElement(coord, "NTIA_Concurrence").text = (
                "CONCURRENCE_RECEIVED" if s.ntia_concurrence_received else "NOT_REQUIRED"
            )

            # 365-Day Bring Into Use Tracking (§ 100.121(d))
            biu = ET.SubElement(s_elem, "BringIntoUseTracking")
            ET.SubElement(biu, "RegistrationFilingDate").text = s.registration_date.isoformat()
            ET.SubElement(biu, "StatutoryDeadline365Days").text = (s.registration_date + timedelta(days=365)).isoformat()
            ET.SubElement(biu, "BIU_Status").text = s.biu_status.value

        xml_bytes = ET.tostring(root, encoding="utf-8")
        return minidom.parseString(xml_bytes).toprettyxml(indent="  ")


class PreGrantCertificationEngine:
    @classmethod
    def evaluate(
        cls,
        site: SiteRegistrationData,
        has_approved_form312: bool = True,
        days_on_public_notice: int = 16,
        attestation_nib_signed: bool = True,
        stop_buzzer_contact_ready: bool = True,
    ) -> PreGrantVerificationResult:
        c1 = has_approved_form312
        c2 = (not site.waiver_requested)
        c3 = (days_on_public_notice >= 15)
        c4 = site.pcn_completed_no_conflicts and site.ntia_concurrence_received
        c5 = attestation_nib_signed
        c6 = stop_buzzer_contact_ready

        authorized = all([c1, c2, c3, c4, c5, c6])
        summary = (
            "AUTHORIZED: Pre-grant non-interference operations fully certified under 47 CFR § 100.120(f)."
            if authorized
            else "NOT AUTHORIZED: Prerequisites pending (e.g. 15-day notice, PCN coordination, or NIB attestation)."
        )

        return PreGrantVerificationResult(
            is_authorized_pre_grant=authorized,
            public_notice_cleared=c3,
            zero_waiver_verified=c2,
            coordination_cleared=c4,
            nib_attestation_bound=c5,
            stop_buzzer_poc_ready=c6,
            status_summary=summary,
        )
