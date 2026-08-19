"""
OrbitFlow Document Intelligence Parameter Extractor
===================================================

Deterministic, high-precision extraction engine for satellite mission parameters
from unstructured and semi-structured documents (PDF, DOCX, CSV, TXT).

Converts raw text into validated Schedule O (§ 100.111) and Schedule F (§ 100.112)
parameters with 100% mathematical auditability, confidence scoring, and source citations.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from backend.app.core.config import get_logger
from backend.app.engines.doc_intel.parsers import DocumentParser, ParsedDocument
from backend.app.engines.doc_intel.schemas import (
    ContradictionFlag,
    ExtractedField,
    ExtractionResult,
    FrequencyChannel,
    ScheduleFExtracted,
    ScheduleOExtracted,
)
from backend.app.models.satellite import OrbitType, SatelliteSpec

log = get_logger(__name__)


class DocumentIntelligenceEngine:
    """
    Core extraction engine for converting raw mission documents into
    structured regulatory schemas for FCC Part 100 evaluations.
    """

    def __init__(self) -> None:
        self._init_patterns()

    def _init_patterns(self) -> None:
        """Initialize comprehensive regulatory parameter regex patterns."""
        # 1. Altitude patterns (km, nmi, mi)
        self.re_altitude = re.compile(
            r'(?:(?:altitude|orbit|orbit(?:al)?\s+height|operating\s+altitude|nominal\s+altitude|apogee|perigee|semi-major\s+axis)(?:[\s:=–—]|is|at|of)+?(?:approx(?:imately)?\s*)?(\d{2,6}(?:\.\d+)?)\s*(km|kilometers?|nmi|nm|nautical\s+miles?|miles?|mi)\b)|(?:(\d{2,6}(?:\.\d+)?)\s*(km|kilometers?|nmi|nm|nautical\s+miles?|miles?|mi)\s*(?:altitude|orbit|circular))',
            re.IGNORECASE,
        )

        # 2. Inclination patterns
        self.re_inclination = re.compile(
            r'(?:(?:inclination|orbit(?:al)?\s+inclination|inc\.?)(?:[\s:=–—]|is|at|of)+?(\d{1,3}(?:\.\d+)?)\s*(?:°|deg(?:rees?)?)\b)|(?:(\d{1,3}(?:\.\d+)?)\s*(?:°|deg(?:rees?)?)\s*(?:inclination|inc\.?))',
            re.IGNORECASE,
        )

        # 3. Mass patterns (kg, grams, lbs)
        self.re_mass = re.compile(
            r'(?:wet\s+mass|launch\s+mass|spacecraft\s+mass|satellite\s+mass|total\s+mass|dry\s+mass|mass|weight)(?:[\s:=–—]|is|at|of)+?'
            r'(\d+(?:\.\d+)?)\s*(kg|kilograms?|g|grams?|lbs?|pounds?)\b',
            re.IGNORECASE,
        )

        # 4. Dimension patterns (e.g. 10 x 20 x 30 cm, 1.2m, 3U, 6U, 12U)
        self.re_dimensions_3d = re.compile(
            r'(?:dimensions?|size|form\s+factor)(?:[\s:=–—]|is|at|of)+?(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*(cm|mm|m|meters?|inches?|in)\b',
            re.IGNORECASE,
        )
        self.re_cubesat_u = re.compile(
            r'\b(1U|2U|3U|6U|12U|16U|24U|27U)\s*(?:cubesat|nano-satellite|nanosatellite|class|form\s+factor)?\b',
            re.IGNORECASE,
        )
        self.re_smallest_dim = re.compile(
            r'(?:smallest\s+dimension|minimum\s+dimension|cross-section\s+min|width|depth|height)(?:[\s:=–—]|is|at|of)+?(\d+(?:\.\d+)?)\s*(cm|mm|m|meters?|inches?|in)\b',
            re.IGNORECASE,
        )

        # 5. Constellation / Sat Count
        self.re_sat_count = re.compile(
            r'(?:number\s+of\s+satellites|constellation\s+size|total\s+spacecraft|authorized\s+satellites|fleet\s+size|satellites\s+authorized)(?:[\s:=–—]|is|at|of)+?'
            r'(\d+)\b',
            re.IGNORECASE,
        )
        self.re_deployed_count = re.compile(
            r'(?:currently\s+deployed|deployed\s+satellites|operating\s+satellites|in-orbit\s+satellites)(?:[\s:=–—]|is|at|of)+?'
            r'(\d+)\b',
            re.IGNORECASE,
        )

        # 6. Mission Lifetime
        self.re_lifetime = re.compile(
            r'(?:mission\s+lifetime|design\s+life|operational\s+lifetime|lifetime|mission\s+duration)(?:[\s:=–—]|is|at|of)+?'
            r'(\d+(?:\.\d+)?)\s*(years?|yrs?|months?|mos?)\b',
            re.IGNORECASE,
        )

        # 7. Propulsion & Passivation
        self.re_propulsion = re.compile(
            r'(?:propulsion(?:\s+system)?|thruster(?:s)?)[\s:=–—]+([A-Za-z0-9\s\-–/]+?)(?=[,;\.\n]|$)',
            re.IGNORECASE,
        )
        self.re_propulsion_keywords = re.compile(
            r'\b(electric\s+propulsion|hall\s+effect|gridded\s+ion|chemical\s+propulsion|monopropellant|bipropellant|cold\s+gas|hydrazine|krypton|xenon|green\s+propellant|water\s+plasma|none|no\s+propulsion)\b',
            re.IGNORECASE,
        )
        self.re_fuel_mass = re.compile(
            r'(?:propellant\s+mass|fuel\s+mass|propellant\s+capacity|fuel\s+load)[\s:=–—]+(\d+(?:\.\d+)?)\s*(kg|kilograms?|g|grams?)\b',
            re.IGNORECASE,
        )
        self.re_delta_v = re.compile(
            r'(?:delta[- ]?v(?:\s+capability)?|velocity\s+increment|\u0394v)(?:[\s:=–—]|is|at|of)+?(\d+(?:\.\d+)?)\s*(m/s|km/s|mps)\b',
            re.IGNORECASE,
        )

        # 8. De-orbit Timeline
        self.re_deorbit = re.compile(
            r'(?:de-?orbit\s+duration|time\s+to\s+de-?orbit|re-?entry\s+timeline|disposal\s+timeline|post-mission\s+decay|estimated\s+disposal)(?:[\s:=–—]|is|at|of)+?'
            r'(\d+(?:\.\d+)?)\s*(years?|yrs?|months?|mos?|days?)\b',
            re.IGNORECASE,
        )

        # 9. Frequency & Bands (Schedule F)
        self.re_frequencies = re.compile(
            r'(?:frequency|transmit\s+frequency|receive\s+frequency|downlink|uplink|center\s+frequency|rf\s+band)[\s:=–—]+'
            r'(\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?)\s*(ghz|mhz|khz)\b',
            re.IGNORECASE,
        )
        self.re_eirp = re.compile(
            r'(?:eirp|equivalent\s+isotropically\s+radiated\s+power|max\s+eirp)[\s:=–—]+'
            r'([+-]?\d+(?:\.\d+)?)\s*(dbw|dbm|w|watts?)\b',
            re.IGNORECASE,
        )

        # 10. Regulatory & Legal Flags
        self.re_foreign_ownership = re.compile(
            r'(?:foreign\s+ownership|indirect\s+foreign\s+investment|non-u\.s\.\s+ownership)[\s:=–—]+'
            r'(\d+(?:\.\d+)?)\s*%\b',
            re.IGNORECASE,
        )

    def extract_from_file(self, file_path: str) -> ExtractionResult:
        """Parse file and extract all regulatory fields."""
        doc = DocumentParser.parse_file(file_path)
        return self.extract_from_document(doc)

    def extract_from_text(self, text: str, document_name: str = "raw_input.txt") -> ExtractionResult:
        """Parse raw text and extract all regulatory fields."""
        doc = DocumentParser.parse_text(text, document_name=document_name)
        return self.extract_from_document(doc)

    def extract_from_document(self, doc: ParsedDocument) -> ExtractionResult:
        """Master extraction pipeline applying multi-page analysis and field mapping."""
        log.info("Starting document intelligence extraction on '%s' (%d pages)", doc.document_name, doc.page_count)
        
        all_fields: dict[str, ExtractedField] = {}
        schedule_o = ScheduleOExtracted()
        schedule_f = ScheduleFExtracted()
        contradictions: list[ContradictionFlag] = []
        warnings: list[str] = []

        # Iterate through pages to preserve source citation
        for page_num, page_text in enumerate(doc.pages, start=1):
            self._extract_page_fields(page_text, page_num, all_fields, contradictions)

        # Synthesize Schedule O parameters
        self._synthesize_schedule_o(all_fields, schedule_o, doc)

        # Synthesize Schedule F parameters
        self._synthesize_schedule_f(all_fields, schedule_f, doc)

        # Detect missing critical fields for FCC filing
        missing_critical = self._check_missing_critical(schedule_o)
        missing_optional = self._check_missing_optional(schedule_o, schedule_f)

        # Calculate overall confidence score
        if all_fields:
            avg_conf = sum(f.confidence for f in all_fields.values()) / len(all_fields)
            # Penalty for missing critical fields
            penalty = len(missing_critical) * 0.10
            overall_confidence = max(0.1, min(1.0, avg_conf - penalty))
        else:
            overall_confidence = 0.0
            warnings.append("No technical satellite parameters could be automatically identified.")

        text_preview = doc.full_text[:1200].strip()

        result = ExtractionResult(
            document_name=doc.document_name,
            document_type=doc.document_type,
            page_count=doc.page_count,
            schedule_o=schedule_o,
            schedule_f=schedule_f,
            all_fields=all_fields,
            confidence_score=round(overall_confidence, 2),
            missing_critical_fields=missing_critical,
            missing_optional_fields=missing_optional,
            contradictions=contradictions,
            warnings=warnings,
            text_preview=text_preview,
        )

        log.info(
            "Extraction complete: %d fields extracted, %d critical missing, confidence=%.2f",
            len(all_fields), len(missing_critical), overall_confidence
        )
        return result

    def _extract_page_fields(
        self,
        text: str,
        page_num: int,
        all_fields: dict[str, ExtractedField],
        contradictions: list[ContradictionFlag],
    ) -> None:
        """Extract parameters from a single page's text."""
        # 1. System / Mission Name heuristic
        name_match = re.search(r'(?:mission\s+name|satellite\s+name|system\s+name|constellation\s+name|project)[\s:=–—]+([A-Za-z0-9\s\-–_\.]+?)(?=[,\.\n]|$)', text, re.IGNORECASE)
        if name_match and "system_name" not in all_fields:
            val = name_match.group(1).strip()
            if len(val) > 1 and len(val) < 60:
                all_fields["system_name"] = ExtractedField(
                    field_name="system_name",
                    extracted_value=val,
                    raw_text=name_match.group(0),
                    confidence=0.90,
                    source_page=page_num,
                )

        # 2. Altitude (km conversion)
        for m in self.re_altitude.finditer(text):
            val_str = m.group(1) or m.group(3)
            unit_str = (m.group(2) or m.group(4) or "km").lower()
            if not val_str:
                continue
            raw_val = float(val_str)
            if "nautic" in unit_str or "nmi" in unit_str or "nm" in unit_str:
                alt_km = raw_val * 1.852
            elif "mi" in unit_str:
                alt_km = raw_val * 1.60934
            else:
                alt_km = raw_val

            field = ExtractedField(
                field_name="altitude_km",
                extracted_value=round(alt_km, 2),
                raw_text=m.group(0),
                unit="km",
                confidence=0.95,
                source_page=page_num,
            )
            self._register_or_check_contradiction("altitude_km", field, all_fields, contradictions)

        # 3. Inclination
        for m in self.re_inclination.finditer(text):
            inc_str = m.group(1) or m.group(2)
            if not inc_str:
                continue
            inc = float(inc_str)
            if 0.0 <= inc <= 180.0:
                field = ExtractedField(
                    field_name="inclination_deg",
                    extracted_value=inc,
                    raw_text=m.group(0),
                    unit="deg",
                    confidence=0.95,
                    source_page=page_num,
                )
                self._register_or_check_contradiction("inclination_deg", field, all_fields, contradictions)

        # 4. Mass (kg conversion)
        for m in self.re_mass.finditer(text):
            raw_val = float(m.group(1))
            unit = m.group(2).lower()
            if "g" == unit or "gram" in unit:
                mass_kg = raw_val / 1000.0
            elif "lb" in unit or "pound" in unit:
                mass_kg = raw_val * 0.453592
            else:
                mass_kg = raw_val

            field = ExtractedField(
                field_name="mass_kg",
                extracted_value=round(mass_kg, 2),
                raw_text=m.group(0),
                unit="kg",
                confidence=0.92,
                source_page=page_num,
            )
            self._register_or_check_contradiction("mass_kg", field, all_fields, contradictions)

        # 5. CubeSat standard form factors
        for m in self.re_cubesat_u.finditer(text):
            u_tag = m.group(1).upper()
            u_num = int(u_tag.replace("U", ""))
            # 1U is 10x10x10 cm -> smallest dimension is 10 cm
            # 3U is 10x10x30 cm -> smallest dimension is 10 cm
            # 6U is 10x20x30 cm -> smallest dimension is 10 cm
            # 12U is 20x20x30 cm -> smallest dimension is 20 cm
            smallest_cm = 20.0 if u_num >= 12 else 10.0
            approx_mass = u_num * 1.5  # ~1.5 kg per U standard
            
            if "smallest_dimension_cm" not in all_fields:
                all_fields["smallest_dimension_cm"] = ExtractedField(
                    field_name="smallest_dimension_cm",
                    extracted_value=smallest_cm,
                    raw_text=m.group(0),
                    unit="cm",
                    confidence=0.88,
                    source_page=page_num,
                    notes=f"Derived from standard {u_tag} CubeSat specification (10 cm base width)",
                )
            if "mass_kg" not in all_fields:
                all_fields["mass_kg"] = ExtractedField(
                    field_name="mass_kg",
                    extracted_value=approx_mass,
                    raw_text=m.group(0),
                    unit="kg",
                    confidence=0.70,
                    source_page=page_num,
                    notes=f"Estimated from {u_tag} form factor (~1.5 kg/U). Confirm exact wet mass.",
                )

        # 6. 3D Dimensions
        for m in self.re_dimensions_3d.finditer(text):
            d1, d2, d3 = float(m.group(1)), float(m.group(2)), float(m.group(3))
            unit = m.group(4).lower()
            if unit == "mm":
                scale = 0.1
            elif unit == "cm":
                scale = 1.0
            elif unit in ["m", "meter", "meters"]:
                scale = 100.0
            elif "in" in unit:
                scale = 2.54
            else:
                scale = 1.0
            dims_cm = sorted([d1 * scale, d2 * scale, d3 * scale])
            smallest_cm = dims_cm[0]
            area_m2 = (dims_cm[1] / 100.0) * (dims_cm[2] / 100.0)  # Max cross-section

            all_fields["dimensions_cm"] = ExtractedField(
                field_name="dimensions_cm",
                extracted_value=f"{dims_cm[0]:.1f} x {dims_cm[1]:.1f} x {dims_cm[2]:.1f} cm",
                raw_text=m.group(0),
                confidence=0.96,
                source_page=page_num,
            )
            all_fields["smallest_dimension_cm"] = ExtractedField(
                field_name="smallest_dimension_cm",
                extracted_value=round(smallest_cm, 2),
                raw_text=m.group(0),
                unit="cm",
                confidence=0.96,
                source_page=page_num,
            )
            all_fields["cross_section_area_m2"] = ExtractedField(
                field_name="cross_section_area_m2",
                extracted_value=round(area_m2, 4),
                raw_text=m.group(0),
                unit="m2",
                confidence=0.90,
                source_page=page_num,
                notes="Calculated from largest two geometric dimensions",
            )

        # Single smallest dimension pattern
        for m in self.re_smallest_dim.finditer(text):
            val = float(m.group(1))
            unit = m.group(2).lower()
            if unit == "mm":
                val_cm = val * 0.1
            elif unit == "cm":
                val_cm = val
            elif unit in ["m", "meter", "meters"]:
                val_cm = val * 100.0
            elif "in" in unit:
                val_cm = val * 2.54
            else:
                val_cm = val
            if "smallest_dimension_cm" not in all_fields or all_fields["smallest_dimension_cm"].confidence < 0.90:
                all_fields["smallest_dimension_cm"] = ExtractedField(
                    field_name="smallest_dimension_cm",
                    extracted_value=round(val_cm, 2),
                    raw_text=m.group(0),
                    unit="cm",
                    confidence=0.94,
                    source_page=page_num,
                )

        # 7. Satellite Count
        for m in self.re_sat_count.finditer(text):
            num = int(m.group(1))
            field = ExtractedField(
                field_name="num_authorized",
                extracted_value=num,
                raw_text=m.group(0),
                confidence=0.92,
                source_page=page_num,
            )
            self._register_or_check_contradiction("num_authorized", field, all_fields, contradictions)

        for m in self.re_deployed_count.finditer(text):
            num = int(m.group(1))
            all_fields["num_deployed"] = ExtractedField(
                field_name="num_deployed",
                extracted_value=num,
                raw_text=m.group(0),
                confidence=0.90,
                source_page=page_num,
            )

        # 8. Mission Lifetime (years)
        for m in self.re_lifetime.finditer(text):
            raw_val = float(m.group(1))
            unit = m.group(2).lower()
            years = raw_val / 12.0 if "mo" in unit else raw_val
            field = ExtractedField(
                field_name="mission_lifetime_years",
                extracted_value=round(years, 2),
                raw_text=m.group(0),
                unit="years",
                confidence=0.92,
                source_page=page_num,
            )
            self._register_or_check_contradiction("mission_lifetime_years", field, all_fields, contradictions)

        # 9. Propulsion Presence and Type
        for m in self.re_propulsion_keywords.finditer(text):
            prop_str = m.group(1).strip()
            has_prop = "no propulsion" not in prop_str.lower() and "none" not in prop_str.lower()
            all_fields["has_propulsion"] = ExtractedField(
                field_name="has_propulsion",
                extracted_value=has_prop,
                raw_text=m.group(0),
                confidence=0.92,
                source_page=page_num,
            )
            all_fields["propulsion_type"] = ExtractedField(
                field_name="propulsion_type",
                extracted_value=prop_str.title(),
                raw_text=m.group(0),
                confidence=0.90,
                source_page=page_num,
            )

        # 10. Fuel Mass & Delta-V
        for m in self.re_fuel_mass.finditer(text):
            fuel_kg = float(m.group(1)) / 1000.0 if "g" == m.group(2).lower() else float(m.group(1))
            all_fields["fuel_mass_kg"] = ExtractedField(
                field_name="fuel_mass_kg",
                extracted_value=round(fuel_kg, 3),
                raw_text=m.group(0),
                unit="kg",
                confidence=0.90,
                source_page=page_num,
            )

        for m in self.re_delta_v.finditer(text):
            dv = float(m.group(1)) * 1000.0 if "km" in m.group(2).lower() else float(m.group(1))
            all_fields["delta_v_ms"] = ExtractedField(
                field_name="delta_v_ms",
                extracted_value=round(dv, 1),
                raw_text=m.group(0),
                unit="m/s",
                confidence=0.90,
                source_page=page_num,
            )

        # 11. De-orbit Timeline
        for m in self.re_deorbit.finditer(text):
            val = float(m.group(1))
            unit = m.group(2).lower()
            if "mo" in unit:
                deorbit_yrs = val / 12.0
            elif "day" in unit:
                deorbit_yrs = val / 365.25
            else:
                deorbit_yrs = val
            all_fields["estimated_deorbit_years"] = ExtractedField(
                field_name="estimated_deorbit_years",
                extracted_value=round(deorbit_yrs, 2),
                raw_text=m.group(0),
                unit="years",
                confidence=0.90,
                source_page=page_num,
            )

        # 12. Foreign Ownership
        for m in self.re_foreign_ownership.finditer(text):
            pct = float(m.group(1))
            all_fields["foreign_ownership_pct"] = ExtractedField(
                field_name="foreign_ownership_pct",
                extracted_value=pct,
                raw_text=m.group(0),
                unit="%",
                confidence=0.95,
                source_page=page_num,
            )

    def _register_or_check_contradiction(
        self,
        field_name: str,
        new_field: ExtractedField,
        all_fields: dict[str, ExtractedField],
        contradictions: list[ContradictionFlag],
    ) -> None:
        """Detect and log value contradictions across document sections."""
        if field_name not in all_fields:
            all_fields[field_name] = new_field
            return

        existing = all_fields[field_name]
        # Compare numerical values
        if isinstance(existing.extracted_value, (int, float)) and isinstance(new_field.extracted_value, (int, float)):
            diff_pct = abs(existing.extracted_value - new_field.extracted_value) / max(1e-5, abs(existing.extracted_value))
            if diff_pct > 0.15:  # > 15% discrepancy
                contradictions.append(ContradictionFlag(
                    field_name=field_name,
                    values=[existing, new_field],
                    description=f"Contradiction found for {field_name}: page {existing.source_page} ({existing.extracted_value}) vs page {new_field.source_page} ({new_field.extracted_value})"
                ))
        # Keep higher confidence
        if new_field.confidence > existing.confidence:
            all_fields[field_name] = new_field

    def _synthesize_schedule_o(
        self,
        fields: dict[str, ExtractedField],
        schedule_o: ScheduleOExtracted,
        doc: ParsedDocument,
    ) -> None:
        """Map extracted raw fields into Schedule O schema."""
        schedule_o.system_name = fields.get("system_name")
        schedule_o.altitude_km = fields.get("altitude_km")
        schedule_o.inclination_deg = fields.get("inclination_deg")
        schedule_o.mass_kg = fields.get("mass_kg")
        schedule_o.smallest_dimension_cm = fields.get("smallest_dimension_cm")
        schedule_o.dimensions_m = fields.get("dimensions_cm")
        schedule_o.cross_section_area_m2 = fields.get("cross_section_area_m2")
        schedule_o.num_satellites = fields.get("num_authorized")
        schedule_o.num_deployed = fields.get("num_deployed")
        schedule_o.mission_lifetime_years = fields.get("mission_lifetime_years")
        schedule_o.has_propulsion = fields.get("has_propulsion")
        schedule_o.propulsion_type = fields.get("propulsion_type")
        schedule_o.fuel_mass_kg = fields.get("fuel_mass_kg")
        schedule_o.delta_v_ms = fields.get("delta_v_ms")
        schedule_o.estimated_deorbit_years = fields.get("estimated_deorbit_years")

        # Classify orbit type
        alt = schedule_o.altitude_km.extracted_value if schedule_o.altitude_km else None
        if alt is not None:
            if alt < 2000.0:
                orbit = OrbitType.LEO
            elif 35500.0 <= alt <= 36500.0:
                orbit = OrbitType.GEO
            else:
                orbit = OrbitType.MEO
            schedule_o.orbit_type = ExtractedField(
                field_name="orbit_type",
                extracted_value=orbit,
                confidence=0.98,
                notes="Inferred from operational altitude",
            )
            fields["orbit_type"] = schedule_o.orbit_type

    def _synthesize_schedule_f(
        self,
        fields: dict[str, ExtractedField],
        schedule_f: ScheduleFExtracted,
        doc: ParsedDocument,
    ) -> None:
        """Extract RF frequency bands and channel plans."""
        full_text = doc.full_text
        channels: list[FrequencyChannel] = []

        for m in self.re_frequencies.finditer(full_text):
            freq_str = m.group(1)
            unit = m.group(2).lower()
            scale = 1000.0 if unit == "ghz" else (0.001 if unit == "khz" else 1.0)

            # Handle ranges like 14.0 - 14.5 GHz
            if "-" in freq_str:
                parts = [float(p.strip()) for p in freq_str.split("-")]
                center_freq = (parts[0] + parts[1]) / 2.0 * scale
                bw = (parts[1] - parts[0]) * scale
            else:
                center_freq = float(freq_str) * scale
                bw = None

            # Determine band name
            if center_freq > 26000:
                bname = "Ka/Q/V-Band"
            elif center_freq > 12000:
                bname = "Ku-Band"
            elif center_freq > 4000:
                bname = "C-Band"
            elif center_freq > 1000:
                bname = "L/S-Band"
            elif center_freq > 300:
                bname = "UHF"
            else:
                bname = "VHF"

            channels.append(FrequencyChannel(
                band_name=bname,
                direction="Downlink" if "downlink" in m.group(0).lower() else "Uplink",
                center_frequency_mhz=round(center_freq, 3),
                bandwidth_mhz=round(bw, 3) if bw else None,
            ))

        schedule_f.channels = channels

    def _check_missing_critical(self, o: ScheduleOExtracted) -> list[str]:
        """Identify missing mandatory fields for FCC Part 100 Schedule O."""
        missing = []
        if not o.altitude_km:
            missing.append("altitude_km (Operational Altitude)")
        if not o.smallest_dimension_cm:
            missing.append("smallest_dimension_cm (Trackability Dimension)")
        if not o.mass_kg:
            missing.append("mass_kg (Wet Mass)")
        if not o.num_satellites:
            missing.append("num_authorized (Number of Satellites)")
        return missing

    def _check_missing_optional(self, o: ScheduleOExtracted, f: ScheduleFExtracted) -> list[str]:
        """Identify missing technical or non-critical fields."""
        missing = []
        if not o.inclination_deg:
            missing.append("inclination_deg")
        if not o.has_propulsion:
            missing.append("propulsion_system")
        if not o.mission_lifetime_years:
            missing.append("mission_lifetime_years")
        if not f.channels:
            missing.append("frequency_channels")
        return missing

    def build_satellite_spec(
        self,
        extraction: ExtractionResult,
        default_name: str = "Extracted Mission",
        default_operator: str = "Applicant Operator",
    ) -> SatelliteSpec:
        """
        Convert ExtractionResult into a validated SatelliteSpec for downstream engines.
        Applies standard physics defaults for missing optional values.
        """
        o = extraction.schedule_o
        name = o.system_name.extracted_value if o.system_name else default_name
        operator = o.operator_name.extracted_value if o.operator_name else default_operator
        orbit = o.orbit_type.extracted_value if o.orbit_type else OrbitType.LEO
        altitude = float(o.altitude_km.extracted_value) if o.altitude_km else 550.0
        inclination = float(o.inclination_deg.extracted_value) if o.inclination_deg else 45.0
        num_auth = int(o.num_satellites.extracted_value) if o.num_satellites else 1
        num_dep = int(o.num_deployed.extracted_value) if o.num_deployed else 0
        dim = float(o.smallest_dimension_cm.extracted_value) if o.smallest_dimension_cm else 10.0
        mass = float(o.mass_kg.extracted_value) if o.mass_kg else 12.0
        lifetime = float(o.mission_lifetime_years.extracted_value) if o.mission_lifetime_years else 5.0
        has_prop = bool(o.has_propulsion.extracted_value) if o.has_propulsion else False
        deorbit_yrs = float(o.estimated_deorbit_years.extracted_value) if o.estimated_deorbit_years else 3.5

        return SatelliteSpec(
            name=str(name),
            operator_name=str(operator),
            orbit_type=orbit,
            altitude_km=altitude,
            inclination_deg=inclination,
            num_authorized=num_auth,
            num_deployed=num_dep,
            smallest_dimension_cm=dim,
            mass_kg=mass,
            mission_lifetime_years=lifetime,
            has_propulsion=has_prop,
            estimated_deorbit_years=deorbit_yrs,
            foreign_ownership_pct=float(extraction.all_fields.get("foreign_ownership_pct", ExtractedField(field_name="", extracted_value=0.0)).extracted_value),
        )


# Singleton instance
_doc_engine: DocumentIntelligenceEngine | None = None


def get_doc_engine() -> DocumentIntelligenceEngine:
    """Return singleton DocumentIntelligenceEngine."""
    global _doc_engine  # noqa: PLW0603
    if _doc_engine is None:
        _doc_engine = DocumentIntelligenceEngine()
    return _doc_engine
