"""
OrbitFlow Module 12: SpaceCap XML Exporter
==========================================
Serializes validated ITU Appendix 4 Notices into standard SpaceCap / BR IFIC XML.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from backend.app.engines.itu.grouping import partition_and_build_itu_groups
from backend.app.engines.itu.models import ITUAppendix4Notice, ITUNetworkOrbitType


class SpaceCapXMLExporter:
    @staticmethod
    def generate_spacecap_xml(notice: ITUAppendix4Notice) -> str:
        root = ET.Element("SpaceCapNotice", {
            "xmlns": "http://www.itu.int/ITU-R/space/srs/v2024",
            "schemaVersion": "2024.1",
            "adm": notice.notifying_administration,
            "satName": notice.satellite_name,
            "noticeType": notice.notice_type.value,
            "orbitType": notice.orbit_type.value,
        })

        # 1. General Info
        general = ET.SubElement(root, "GeneralInfo")
        ET.SubElement(general, "SatName").text = notice.satellite_name
        ET.SubElement(general, "Adm").text = notice.notifying_administration
        ET.SubElement(general, "PlannedBIU").text = notice.planned_biu_date.isoformat()

        # 2. Orbital Characteristics
        if notice.orbit_type == ITUNetworkOrbitType.NON_GEO and notice.ngso_orbit:
            ngso_elem = ET.SubElement(root, "NonGeoOrbit")
            orb = notice.ngso_orbit
            ET.SubElement(ngso_elem, "NumPlanes").text = str(orb.num_planes)
            ET.SubElement(ngso_elem, "SatsPerPlane").text = str(orb.sats_per_plane)
            ET.SubElement(ngso_elem, "TotalActiveSats").text = str(orb.total_active_satellites)
            ET.SubElement(ngso_elem, "NumSpares").text = str(orb.num_spares)
            ET.SubElement(ngso_elem, "Inclination").text = f"{orb.inclination_deg:.4f}"
            ET.SubElement(ngso_elem, "AltPerigeeKm").text = f"{orb.altitude_perigee_km:.2f}"
            ET.SubElement(ngso_elem, "AltApogeeKm").text = f"{orb.altitude_apogee_km:.2f}"
            ET.SubElement(ngso_elem, "OrbitalPeriodMin").text = f"{orb.orbital_period_minutes:.3f}"
            ET.SubElement(ngso_elem, "PhasingF").text = str(orb.phasing_param_f)
            ET.SubElement(ngso_elem, "MinElevationDeg").text = f"{orb.min_elevation_deg:.1f}"
        elif notice.orbit_type == ITUNetworkOrbitType.GEO and notice.gso_orbit:
            gso_elem = ET.SubElement(root, "GeoOrbit")
            gso = notice.gso_orbit
            ET.SubElement(gso_elem, "NominalLongitude").text = f"{gso.nominal_longitude_deg:.4f}"
            ET.SubElement(gso_elem, "LongTolerance").text = f"{gso.longitudinal_tolerance_deg:.4f}"
            ET.SubElement(gso_elem, "IncExcursion").text = f"{gso.inclination_excursion_deg:.4f}"

        # 3. Beams
        beams_elem = ET.SubElement(root, "Beams")
        for b in notice.beams:
            b_elem = ET.SubElement(beams_elem, "Beam", {"beamId": b.beam_id, "direction": b.direction.value})
            ET.SubElement(b_elem, "PeakGain").text = f"{b.peak_gain_dbi:.1f}"
            ET.SubElement(b_elem, "Beamwidth3dB").text = f"{b.beamwidth_3db_deg:.2f}"
            ET.SubElement(b_elem, "PointingType").text = b.pointing_type
            if b.noise_temperature_k is not None:
                ET.SubElement(b_elem, "NoiseTempK").text = f"{b.noise_temperature_k:.1f}"

        # 4. Form Groups via the Grouping Algorithm
        itu_groups = partition_and_build_itu_groups(notice.carriers)

        groups_elem = ET.SubElement(root, "Groups")
        for g in itu_groups:
            g_elem = ET.SubElement(groups_elem, "Group", {
                "grpId": str(g.grp_id),
                "beamId": g.beam_id,
                "direction": g.direction,
            })
            ET.SubElement(g_elem, "StationClass").text = g.station_class
            ET.SubElement(g_elem, "NatureOfService").text = g.nature_of_service
            ET.SubElement(g_elem, "Polarization").text = g.polarization
            ET.SubElement(g_elem, "ServiceAreaId").text = g.service_area_id
            ET.SubElement(g_elem, "EIRPMax").text = f"{g.eirp_max_dbw:.2f}"
            ET.SubElement(g_elem, "PSDMax").text = f"{g.psd_max_dbw_hz:.2f}"
            ET.SubElement(g_elem, "PSDMin").text = f"{g.psd_min_dbw_hz:.2f}"

            freqs_elem = ET.SubElement(g_elem, "FrequencyAssignments")
            for f_min, f_max, f_center in g.carrier_frequencies:
                f_elem = ET.SubElement(freqs_elem, "Freq")
                f_elem.set("centerMHz", f"{f_center:.4f}")
                f_elem.set("minMHz", f"{f_min:.4f}")
                f_elem.set("maxMHz", f"{f_max:.4f}")

            emiss_elem = ET.SubElement(g_elem, "Emissions")
            for em in g.emissions:
                ET.SubElement(emiss_elem, "EmissionDesignator").text = em

        # 5. Cost Recovery & Statutory Declaration (§ 100.115(d))
        cr_elem = ET.SubElement(root, "CostRecoveryDeclaration")
        ET.SubElement(cr_elem, "Applicant").text = notice.cost_recovery.applicant_legal_name
        ET.SubElement(cr_elem, "Officer").text = (
            f"{notice.cost_recovery.authorizing_officer_name} "
            f"({notice.cost_recovery.authorizing_officer_title})"
        )
        ET.SubElement(cr_elem, "Decision482Acknowledged").text = "true"
        ET.SubElement(cr_elem, "BillingEmail").text = notice.cost_recovery.billing_email
        ET.SubElement(cr_elem, "Timestamp").text = notice.cost_recovery.declaration_timestamp.isoformat()

        xml_bytes = ET.tostring(root, encoding="utf-8")
        return minidom.parseString(xml_bytes).toprettyxml(indent="  ")
