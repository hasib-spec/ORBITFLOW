"""
OrbitFlow Document Intelligence Engine Schemas
==============================================

Pydantic v2 data models for extracted mission parameters, confidence scores,
source citations, contradiction detection, and Schedule O/F field mapping.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported document formats for ingestion."""
    PDF = "PDF"
    DOCX = "DOCX"
    XLSX = "XLSX"
    CSV = "CSV"
    TXT = "TXT"
    UNKNOWN = "UNKNOWN"


class ConfidenceLevel(str, Enum):
    """Confidence band for an extracted field."""
    HIGH = "HIGH"        # >= 0.85
    MEDIUM = "MEDIUM"    # 0.50 - 0.84
    LOW = "LOW"          # < 0.50
    UNSPECIFIED = "UNSPECIFIED"


class ExtractedField(BaseModel):
    """A single parameter extracted from a document with full traceability."""
    field_name: str = Field(..., description="Canonical field name, e.g. 'altitude_km'")
    extracted_value: Any = Field(..., description="Parsed and type-cast value")
    raw_text: str = Field(default="", description="Exact substring matched in source")
    unit: Optional[str] = Field(default=None, description="Original unit in text (e.g. 'km', 'kg', 'MHz')")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score 0.0 - 1.0")
    source_page: Optional[int] = Field(default=None, description="1-based page number")
    source_section: Optional[str] = Field(default=None, description="Heading or table title")
    extraction_method: str = Field(default="regex_pattern", description="regex_pattern | table_cell | heuristic")
    notes: Optional[str] = Field(default=None, description="Additional context or caveats")

    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence >= 0.85:
            return ConfidenceLevel.HIGH
        if self.confidence >= 0.50:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW


class ContradictionFlag(BaseModel):
    """Detected inconsistency between two or more values for the same parameter."""
    field_name: str
    values: list[ExtractedField]
    description: str
    severity: str = Field(default="WARNING", description="WARNING | ERROR | INFO")


class ScheduleOExtracted(BaseModel):
    """Schedule O (§ 100.111) specific parameters extracted from mission documents."""
    system_name: Optional[ExtractedField] = None
    operator_name: Optional[ExtractedField] = None
    orbit_type: Optional[ExtractedField] = None
    altitude_km: Optional[ExtractedField] = None
    apogee_km: Optional[ExtractedField] = None
    perigee_km: Optional[ExtractedField] = None
    inclination_deg: Optional[ExtractedField] = None
    eccentricity: Optional[ExtractedField] = None
    num_satellites: Optional[ExtractedField] = None
    num_deployed: Optional[ExtractedField] = None
    orbital_planes: Optional[ExtractedField] = None
    sats_per_plane: Optional[ExtractedField] = None
    mass_kg: Optional[ExtractedField] = None
    dry_mass_kg: Optional[ExtractedField] = None
    smallest_dimension_cm: Optional[ExtractedField] = None
    dimensions_m: Optional[ExtractedField] = None
    cross_section_area_m2: Optional[ExtractedField] = None
    drag_coefficient: Optional[ExtractedField] = None
    mission_lifetime_years: Optional[ExtractedField] = None
    has_propulsion: Optional[ExtractedField] = None
    propulsion_type: Optional[ExtractedField] = None
    fuel_mass_kg: Optional[ExtractedField] = None
    delta_v_ms: Optional[ExtractedField] = None
    disposal_method: Optional[ExtractedField] = None
    estimated_deorbit_years: Optional[ExtractedField] = None


class FrequencyChannel(BaseModel):
    """Individual RF channel extracted for Schedule F."""
    band_name: str = "Ku/Ka"
    direction: str = "Downlink"  # Uplink | Downlink | Bi-directional | ISL | TT&C
    center_frequency_mhz: float
    bandwidth_mhz: Optional[float] = None
    polarization: Optional[str] = None
    emission_designator: Optional[str] = None
    max_eirp_dbw: Optional[float] = None
    service_type: Optional[str] = None


class ScheduleFExtracted(BaseModel):
    """Schedule F (§ 100.112) technical RF specifications."""
    channels: list[FrequencyChannel] = Field(default_factory=list)
    has_federal_bands: Optional[ExtractedField] = None
    max_eirp_dbw: Optional[ExtractedField] = None
    total_bandwidth_mhz: Optional[ExtractedField] = None
    service_types: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """
    Top-level output of the Document Intelligence Engine.
    Contains complete field mapping, confidence metrics, missing fields, and contradictions.
    """
    document_name: str
    document_type: DocumentType
    page_count: int = 1
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Mapped parameter sets
    schedule_o: ScheduleOExtracted = Field(default_factory=ScheduleOExtracted)
    schedule_f: ScheduleFExtracted = Field(default_factory=ScheduleFExtracted)
    all_fields: dict[str, ExtractedField] = Field(default_factory=dict)
    
    # Quality & Review metrics
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall document extraction confidence")
    missing_critical_fields: list[str] = Field(default_factory=list)
    missing_optional_fields: list[str] = Field(default_factory=list)
    contradictions: list[ContradictionFlag] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    
    # Raw parsed text preview
    text_preview: str = Field(default="", description="First 1000 characters of extracted text")
