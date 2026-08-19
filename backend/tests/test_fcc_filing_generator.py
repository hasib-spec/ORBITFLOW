"""
Unit and Regulatory Verification Tests for Module 11 (FCC Part 100 Filing Generator)
===================================================================================
Tests Form 312 Main Form generation (§ 100.101), Schedule O XML & Exhibit (§ 100.111),
Schedule F XML & Exhibit (§ 100.112), and Master Filing Package assembly.
"""

import xml.etree.ElementTree as ET
import pytest

from backend.app.engines.epfd import get_spectrum_engine
from backend.app.engines.fcc import (
    EntityType,
    FCCFilingBundler,
    Form312Generator,
    ScheduleFGenerator,
    ScheduleOGenerator,
)
from backend.app.engines.odar import ODAREngine
from backend.app.models.satellite import OrbitType, SatelliteSpec

NS = "{http://transition.fcc.gov/space/part100/v1}"


def get_elem(root: ET.Element, tag: str) -> ET.Element | None:
    """Finds XML element matching tag either with or without namespace."""
    for path in [f"{NS}{tag}", tag, f".//{NS}{tag}", f".//{tag}"]:
        el = root.find(path)
        if el is not None:
            return el
    return None


def get_all_elems(root: ET.Element, tag: str) -> list[ET.Element]:
    """Finds all XML elements matching tag with or without namespace."""
    res = root.findall(f".//{NS}{tag}")
    return res if res else root.findall(f".//{tag}")


class TestFCCPart100FilingGenerators:
    """Rigorous tests for Module 11 XML schemas and legal exhibits."""

    @pytest.fixture
    def sample_leo_spec(self) -> SatelliteSpec:
        return SatelliteSpec(
            name="Aetheris LEO Constellation",
            operator_name="Aetheris Space Corp",
            orbit_type=OrbitType.LEO,
            altitude_km=550.0,
            inclination_deg=53.0,
            num_authorized=120,
            num_deployed=20,
            smallest_dimension_cm=85.0,
            mass_kg=320.0,
            mission_lifetime_years=5.0,
            has_propulsion=True,
            estimated_deorbit_years=2.1,
            foreign_ownership_pct=15.0,
        )

    def test_form_312_xml_and_certifications(self, sample_leo_spec):
        """Verifies Form 312 Main Form XML parses cleanly and contains all statutory certifications."""
        data = Form312Generator.create_default_data(sample_leo_spec)
        xml_str = Form312Generator.generate_xml(data)

        # Verify valid XML
        root = ET.fromstring(xml_str)
        assert "Form312Main" in root.tag

        # Verify Applicant & FRN
        app_elem = get_elem(root, "ApplicantInformation")
        assert app_elem is not None
        assert get_elem(app_elem, "LegalName").text == sample_leo_spec.operator_name
        assert get_elem(app_elem, "FRN").text == "0034567891"

        # Verify Ownership Table (>= 10%)
        own_table = get_elem(root, "OwnershipDisclosureTable")
        assert own_table is not None
        interest_holders = get_all_elems(own_table, "InterestHolder")
        assert len(interest_holders) >= 2  # Domestic parent + 15% foreign investor

        # Verify Statutory Certifications under Penalty of Perjury (§ 100.101(a)(3))
        certs = get_elem(root, "StatutoryCertifications")
        assert certs is not None
        assert get_elem(certs, "SpectrumOwnershipWaiver").text == "true"
        assert get_elem(certs, "AntiDrugAbuseAct").text == "true"
        assert get_elem(certs, "TruthCompletenessAccuracy").text == "true"
        assert get_elem(certs, "ForeignAdversaryDisclaimed").text == "true"

    def test_schedule_o_xml_and_embedded_odmp(self, sample_leo_spec):
        """Verifies Schedule O XML encodes orbital architecture and embeds ODMP findings."""
        odar = ODAREngine.evaluate_satellite_odar(sample_leo_spec)
        xml_str = ScheduleOGenerator.generate_xml(sample_leo_spec, odar)

        root = ET.fromstring(xml_str)
        assert "ScheduleO" in root.tag

        # Verify Orbital parameters
        arch = get_elem(root, "NGSOArchitecture")
        assert arch is not None
        assert get_elem(arch, "TotalAuthorizedSatellites").text == "120"
        assert get_elem(arch, "NominalAltitudeKm").text == "550.0"

        # Verify Trackability dimension
        phys = get_elem(root, "SpacecraftPhysicalCharacteristics")
        assert phys is not None
        assert float(get_elem(phys, "SmallestDimensionCm").text) >= 10.0

        # Verify Embedded ODMP Data
        odmp = get_elem(root, "OrbitalDebrisMitigationPlan")
        assert odmp is not None
        assert float(get_elem(odmp, "DeorbitTimelineYears").text) <= 5.0
        assert float(get_elem(odmp, "SmallDebrisCollisionProbability").text) <= 0.01
        assert float(get_elem(odmp, "LargeObjectCollisionProbability").text) <= 0.001
        assert float(get_elem(odmp, "DisposalSuccessReliability").text) >= 0.90

    def test_schedule_f_xml_and_embedded_spectrum(self, sample_leo_spec):
        """Verifies Schedule F XML encodes frequency tables and embeds PFD/EPFD findings."""
        spectrum = get_spectrum_engine().evaluate_satellite_spectrum(sample_leo_spec)
        xml_str = ScheduleFGenerator.generate_xml(sample_leo_spec, spectrum)

        root = ET.fromstring(xml_str)
        assert "ScheduleF" in root.tag

        # Verify Frequency Table
        freq_table = get_elem(root, "FrequencyAssignmentsTable")
        assert freq_table is not None
        entries = get_all_elems(freq_table, "FrequencyEntry")
        assert len(entries) >= 2

        # Verify Embedded Interference Exhibits
        interf = get_elem(root, "InterferenceMitigationExhibits")
        assert interf is not None
        pfd_elem = get_elem(interf, "PowerFluxDensityCompliance")
        assert get_elem(pfd_elem, "PFDStatus").text == "PASS"

        epfd_elem = get_elem(interf, "EPFDArticle22Compliance")
        assert get_elem(epfd_elem, "EPFDdownStatus").text == "PASS"

    def test_master_filing_bundler_and_checksums(self, sample_leo_spec):
        """Verifies master bundler produces complete legal package with SHA-256 manifest."""
        odar = ODAREngine.evaluate_satellite_odar(sample_leo_spec)
        spectrum = get_spectrum_engine().evaluate_satellite_spectrum(sample_leo_spec)

        package = FCCFilingBundler.assemble_package(
            spec=sample_leo_spec,
            odar=odar,
            spectrum=spectrum,
        )

        assert package.package_id.startswith("FCC-PKG-")
        assert package.system_name == sample_leo_spec.name
        assert len(package.form_312_xml) > 100
        assert len(package.schedule_o_xml) > 100
        assert len(package.schedule_f_xml) > 100
        assert len(package.master_combined_xml) > 200

        # Verify narrative exhibits
        assert "EXHIBIT 1: FCC FORM 312" in package.form_312_narrative_exhibit
        assert "EXHIBIT 2: SCHEDULE O" in package.schedule_o_narrative_exhibit
        assert "EXHIBIT 3: SCHEDULE F" in package.schedule_f_narrative_exhibit
        assert "EXHIBIT 4: PUBLIC INTEREST STATEMENT" in package.public_interest_statement
        assert "OFFICIAL TRANSMITTAL COVER LETTER" in package.transmittal_letter_text

        # Verify SHA-256 Manifest
        assert len(package.manifest_checksums_sha256) == 8
        for name, sha in package.manifest_checksums_sha256.items():
            assert len(sha) == 64  # valid 256-bit hex hash
