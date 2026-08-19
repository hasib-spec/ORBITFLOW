"""
OrbitFlow Module 11: FCC Part 100 Filing Generator — Data Models
================================================================
Pydantic models for FCC Form 312 Main Form, Schedule O (Orbital Information),
Schedule F (Frequency Information), and Master Legal Filing Packages.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    CORPORATION = "Corporation"
    LLC = "Limited Liability Company (LLC)"
    LIMITED_PARTNERSHIP = "Limited Partnership (LP)"
    GENERAL_PARTNERSHIP = "General Partnership (GP)"
    INDIVIDUAL = "Individual / Sole Proprietorship"
    GOVERNMENT = "Government / Municipal Entity"


class OwnershipEntry(BaseModel):
    """
    Ownership disclosure entry for entities/individuals with >= 10% direct or indirect equity/voting interest.
    """
    interest_holder_name: str
    citizenship_or_jurisdiction: str
    direct_equity_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    direct_voting_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    indirect_equity_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    indirect_voting_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    ownership_chain_description: Optional[str] = None
    is_foreign_adversary_entity: bool = False


class OfficerDirectorEntry(BaseModel):
    full_name: str
    corporate_title: str
    citizenship: str = "USA"
    address: str


class Form312MainData(BaseModel):
    applicant_legal_name: str
    trade_name_dba: Optional[str] = None
    frn: str = Field(default="0034567891", description="10-digit FCC Registration Number")
    entity_type: EntityType = EntityType.CORPORATION
    jurisdiction_of_formation: str = "Delaware, USA"
    street_address: str = "100 Space Commerce Way, Suite 400"
    city: str = "Cape Canaveral"
    state: str = "FL"
    postal_code: str = "32920"
    country: str = "USA"

    # Contact Representatives
    legal_counsel_name: str = "Cassandra Vance, Esq."
    legal_counsel_firm: str = "Vance & Sterling Space Law LLP"
    legal_counsel_email: str = "cvance@vancespace.com"
    legal_counsel_phone: str = "+1-202-555-0199"

    technical_rep_name: str = "Dr. Marcus Thorne"
    technical_rep_title: str = "Chief Mission Architect"
    technical_rep_email: str = "m.thorne@orbitalflow.com"
    technical_rep_phone: str = "+1-321-555-0144"

    moc_24x7_desk: str = "Mission Operations Center (MOC) Emergency TT&C Desk"
    moc_24x7_phone: str = "+1-800-555-MOC1"
    moc_24x7_email: str = "moc-alerts@orbitalflow.com"

    # Ownership & Leadership Tables
    ownership_table: List[OwnershipEntry] = Field(default_factory=list)
    officers_and_directors: List[OfficerDirectorEntry] = Field(default_factory=list)

    # Statutory Certifications (§ 100.101(a)(3))
    cert_spectrum_waiver: bool = True  # 47 U.S.C. § 304
    cert_anti_drug_act: bool = True    # 21 U.S.C. § 862
    cert_truth_and_accuracy: bool = True  # 18 U.S.C. § 1001
    cert_foreign_adversary_disclaimed: bool = True  # 15 CFR § 7.4

    signatory_name: str = "Elena Rostova"
    signatory_title: str = "Chief Executive Officer"
    signed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FilingPackage(BaseModel):
    """
    Master Submission-Ready FCC Part 100 Filing Package.
    """
    package_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    system_name: str
    operator_name: str
    orbit_type: str
    target_fcc_regime: str = "FCC Part 100 (Adopted, SB Docket 25-306)"

    # XML Artifacts
    form_312_xml: str
    schedule_o_xml: str
    schedule_f_xml: str
    master_combined_xml: str

    # Narrative Legal Exhibits (Markdown & HTML)
    transmittal_letter_text: str
    form_312_narrative_exhibit: str
    schedule_o_narrative_exhibit: str
    schedule_f_narrative_exhibit: str
    public_interest_statement: str

    # Cryptographic Manifest
    manifest_checksums_sha256: Dict[str, str] = Field(default_factory=dict)
    summary_verdict: str
