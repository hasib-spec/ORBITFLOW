"""
Unit Tests for Module 4: Document Intelligence Engine
=====================================================

Validates multi-format parsing, parameter extraction, unit conversion,
confidence scoring, contradiction detection, and Schedule O/F mapping.
"""

from __future__ import annotations

import pytest

from backend.app.engines.doc_intel import (
    DocumentIntelligenceEngine,
    DocumentParser,
    DocumentType,
    get_doc_engine,
)
from backend.app.models.satellite import OrbitType


SAMPLE_MISSION_SPEC_TEXT = """
PROJECT AURA-1 SATELLITE SYSTEM SPECIFICATION SHEET
Applicant Legal Name: Aura Space Communications LLC
System Classification: Commercial LEO Earth Observation and Telecommunications Constellation

1. ORBITAL PARAMETERS:
- Operating Altitude: 550.0 km circular orbit
- Orbital Inclination: 53.2 degrees
- Total Constellation Size: 72 satellites authorized
- Currently Deployed: 12 satellites in operational orbit
- Design Mission Lifetime: 5.0 years

2. PHYSICAL SPECIFICATIONS:
- Satellite Wet Mass: 165.5 kg
- Spacecraft Dimensions: 80.0 x 60.0 x 45.0 cm (smallest dimension: 45.0 cm)
- Cross-Sectional Area: 0.48 m^2
- Drag Coefficient (Cd): 2.2

3. PROPULSION & DISPOSAL:
- Propulsion: Krypton Hall-Effect Electric Propulsion Thruster (45 mN thrust)
- Propellant Fuel Mass: 15.0 kg
- Total Delta-V Capability: 210.0 m/s
- Disposal Method: Controlled perigee lowering to rapid atmospheric re-entry
- Estimated Time to De-orbit: 0.4 years post-mission

4. RF FREQUENCY ALLOCATIONS:
- Downlink Center Frequency: 14.25 GHz (Ku-Band)
- Downlink Bandwidth: 250.0 MHz
- Max EIRP: 34.5 dBW
- Uplink Center Frequency: 29.5 GHz (Ka-Band)

5. OWNERSHIP & REGULATORY:
- Foreign Ownership: 4.5% aggregate foreign equity
- U.S. Licensed Operator: Yes
"""

SAMPLE_CUBESAT_TEXT = """
UNIVERSITY RESEARCH NANOSATELLITE PROPOSAL
Satellite Name: CubeSense-3
Form Factor: 3U CubeSat nanosatellite class
Orbit: 420 km altitude, 51.6 deg inclination
Spacecraft Mass: 4.2 kg
Propulsion: None (no propulsion system)
Estimated post-mission decay: 1.8 years
Transmit frequency: 437.5 MHz UHF
"""


@pytest.fixture
def engine() -> DocumentIntelligenceEngine:
    return get_doc_engine()


class TestDocumentIntelligence:
    """Test suite for Document Intelligence parser and parameter extraction."""

    def test_text_parser_basic(self) -> None:
        doc = DocumentParser.parse_text("Sample text content", "test.txt")
        assert doc.document_type == DocumentType.TXT
        assert doc.page_count == 1
        assert "Sample text content" in doc.full_text

    def test_csv_parser_basic(self) -> None:
        csv_content = "parameter,value,unit\naltitude,550,km\nmass,150,kg"
        doc = DocumentParser.parse_csv_text(csv_content, "test.csv")
        assert doc.document_type == DocumentType.CSV
        assert len(doc.tables) == 1
        assert doc.tables[0][1][0] == "altitude"

    def test_full_mission_extraction(self, engine: DocumentIntelligenceEngine) -> None:
        result = engine.extract_from_text(SAMPLE_MISSION_SPEC_TEXT, "Aura_Spec.txt")
        
        assert result.confidence_score >= 0.80
        assert len(result.missing_critical_fields) == 0

        # Schedule O checks
        sched_o = result.schedule_o
        assert sched_o.system_name is not None
        assert "aura" in sched_o.system_name.extracted_value.lower()
        assert sched_o.altitude_km is not None
        assert sched_o.altitude_km.extracted_value == 550.0
        assert sched_o.inclination_deg is not None
        assert sched_o.inclination_deg.extracted_value == 53.2
        assert sched_o.mass_kg is not None
        assert sched_o.mass_kg.extracted_value == 165.5
        assert sched_o.smallest_dimension_cm is not None
        assert sched_o.smallest_dimension_cm.extracted_value == 45.0
        assert sched_o.num_satellites is not None
        assert sched_o.num_satellites.extracted_value == 72
        assert sched_o.num_deployed is not None
        assert sched_o.num_deployed.extracted_value == 12
        assert sched_o.has_propulsion is not None
        assert sched_o.has_propulsion.extracted_value is True
        assert sched_o.fuel_mass_kg is not None
        assert sched_o.fuel_mass_kg.extracted_value == 15.0
        assert sched_o.delta_v_ms is not None
        assert sched_o.delta_v_ms.extracted_value == 210.0
        assert sched_o.estimated_deorbit_years is not None
        assert sched_o.estimated_deorbit_years.extracted_value == 0.4

        # Schedule F checks
        sched_f = result.schedule_f
        assert len(sched_f.channels) >= 2

    def test_cubesat_form_factor_derivation(self, engine: DocumentIntelligenceEngine) -> None:
        result = engine.extract_from_text(SAMPLE_CUBESAT_TEXT, "CubeSat.txt")
        
        sched_o = result.schedule_o
        assert sched_o.altitude_km is not None
        assert sched_o.altitude_km.extracted_value == 420.0
        assert sched_o.smallest_dimension_cm is not None
        assert sched_o.smallest_dimension_cm.extracted_value == 10.0  # 3U base width
        assert sched_o.mass_kg is not None
        assert sched_o.mass_kg.extracted_value == 4.2
        assert sched_o.has_propulsion is not None
        assert sched_o.has_propulsion.extracted_value is False

    def test_unit_conversions(self, engine: DocumentIntelligenceEngine) -> None:
        text = """
        Orbit: altitude 300 nautical miles
        Weight: launch mass 330 lbs
        Lifetime: operational lifetime 36 months
        Deorbit: estimated disposal 18 months
        """
        result = engine.extract_from_text(text, "units.txt")
        
        # 300 nmi ~ 555.6 km
        assert result.schedule_o.altitude_km is not None
        assert 550.0 <= result.schedule_o.altitude_km.extracted_value <= 560.0

        # 330 lbs ~ 149.68 kg
        assert result.schedule_o.mass_kg is not None
        assert 145.0 <= result.schedule_o.mass_kg.extracted_value <= 155.0

        # 36 months = 3.0 years
        assert result.schedule_o.mission_lifetime_years is not None
        assert result.schedule_o.mission_lifetime_years.extracted_value == 3.0

        # 18 months = 1.5 years
        assert result.schedule_o.estimated_deorbit_years is not None
        assert result.schedule_o.estimated_deorbit_years.extracted_value == 1.5

    def test_contradiction_detection(self, engine: DocumentIntelligenceEngine) -> None:
        text_with_contradiction = """
        SECTION 1: Primary altitude is 500 km.
        --- PAGE BREAK ---
        SECTION 2: Primary altitude is 1200 km.
        """
        result = engine.extract_from_text(text_with_contradiction, "contradiction.txt")
        assert len(result.contradictions) >= 1
        assert result.contradictions[0].field_name == "altitude_km"

    def test_spec_builder_conversion(self, engine: DocumentIntelligenceEngine) -> None:
        result = engine.extract_from_text(SAMPLE_MISSION_SPEC_TEXT, "Aura_Spec.txt")
        spec = engine.build_satellite_spec(result, default_name="Aura-Constellation")
        
        assert spec.altitude_km == 550.0
        assert spec.num_authorized == 72
        assert spec.num_deployed == 12
        assert spec.mass_kg == 165.5
        assert spec.smallest_dimension_cm == 45.0
        assert spec.orbit_type == OrbitType.LEO
        assert spec.has_propulsion is True
