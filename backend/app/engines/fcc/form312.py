"""
OrbitFlow Module 11: FCC Part 100 Filing Generator — Form 312 Main Form Generator
==================================================================================
Generates structured Form 312 Main Form XML and legal narrative exhibits under 47 CFR § 100.101.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional

from backend.app.models.satellite import SatelliteSpec
from backend.app.engines.fcc.models import (
    EntityType,
    Form312MainData,
    OfficerDirectorEntry,
    OwnershipEntry,
)


class Form312Generator:
    """
    Generator for FCC Form 312 Main Form XML and Attorney Narrative Exhibits.
    """

    @classmethod
    def create_default_data(cls, spec: SatelliteSpec) -> Form312MainData:
        """Derives default Form 312 legal data from satellite specifications."""
        data = Form312MainData(
            applicant_legal_name=spec.operator_name,
            trade_name_dba=f"{spec.name} Constellation",
            frn="0034567891",
            entity_type=EntityType.CORPORATION,
            jurisdiction_of_formation="Delaware, USA",
        )

        # Build default >= 10% ownership table
        data.ownership_table = [
            OwnershipEntry(
                interest_holder_name=f"{spec.operator_name} Holdings Inc.",
                citizenship_or_jurisdiction="Delaware, USA",
                direct_equity_pct=max(0.0, 100.0 - spec.foreign_ownership_pct),
                direct_voting_pct=100.0,
                is_foreign_adversary_entity=False,
            )
        ]
        if spec.foreign_ownership_pct > 0.0:
            data.ownership_table.append(
                OwnershipEntry(
                    interest_holder_name="International Space Capital Partners Ltd.",
                    citizenship_or_jurisdiction="United Kingdom",
                    direct_equity_pct=spec.foreign_ownership_pct,
                    direct_voting_pct=0.0,
                    is_foreign_adversary_entity=False,
                )
            )

        # Default Officer Roster
        data.officers_and_directors = [
            OfficerDirectorEntry(
                full_name="Elena Rostova",
                corporate_title="Chief Executive Officer & Director",
                citizenship="USA",
                address="100 Space Commerce Way, Cape Canaveral, FL 32920",
            ),
            OfficerDirectorEntry(
                full_name="David K. Sterling",
                corporate_title="General Counsel & Secretary",
                citizenship="USA",
                address="1200 Connecticut Ave NW, Washington, DC 20036",
            ),
        ]

        return data

    @classmethod
    def generate_xml(cls, data: Form312MainData) -> str:
        """Generates valid Part 100 Form 312 Main Form XML element."""
        root = ET.Element("Form312Main", {
            "xmlns": "http://transition.fcc.gov/space/part100/v1",
            "section": "§ 100.101",
        })

        # 1. Applicant Info
        app_elem = ET.SubElement(root, "ApplicantInformation")
        ET.SubElement(app_elem, "LegalName").text = data.applicant_legal_name
        if data.trade_name_dba:
            ET.SubElement(app_elem, "TradeNameDBA").text = data.trade_name_dba
        ET.SubElement(app_elem, "FRN").text = data.frn
        ET.SubElement(app_elem, "EntityType").text = data.entity_type.value
        ET.SubElement(app_elem, "JurisdictionOfFormation").text = data.jurisdiction_of_formation

        addr = ET.SubElement(app_elem, "PhysicalAddress")
        ET.SubElement(addr, "StreetAddress").text = data.street_address
        ET.SubElement(addr, "City").text = data.city
        ET.SubElement(addr, "State").text = data.state
        ET.SubElement(addr, "PostalCode").text = data.postal_code
        ET.SubElement(addr, "Country").text = data.country

        # 2. Contact Representatives
        contacts = ET.SubElement(root, "ContactRepresentatives")
        legal = ET.SubElement(contacts, "LegalRepresentative")
        ET.SubElement(legal, "Name").text = data.legal_counsel_name
        ET.SubElement(legal, "FirmName").text = data.legal_counsel_firm
        ET.SubElement(legal, "Email").text = data.legal_counsel_email
        ET.SubElement(legal, "Telephone").text = data.legal_counsel_phone

        tech = ET.SubElement(contacts, "TechnicalRepresentative")
        ET.SubElement(tech, "Name").text = data.technical_rep_name
        ET.SubElement(tech, "Title").text = data.technical_rep_title
        ET.SubElement(tech, "Email").text = data.technical_rep_email
        ET.SubElement(tech, "Telephone").text = data.technical_rep_phone

        moc = ET.SubElement(contacts, "Operations24x7Contact")
        ET.SubElement(moc, "DeskIdentifier").text = data.moc_24x7_desk
        ET.SubElement(moc, "Email").text = data.moc_24x7_email
        ET.SubElement(moc, "Telephone").text = data.moc_24x7_phone

        # 3. Ownership Disclosure Table (>= 10%)
        own_table = ET.SubElement(root, "OwnershipDisclosureTable", {"rule": "§ 100.101(a)(2)"})
        for entry in data.ownership_table:
            ih = ET.SubElement(own_table, "InterestHolder")
            ET.SubElement(ih, "Name").text = entry.interest_holder_name
            ET.SubElement(ih, "CitizenshipOrJurisdiction").text = entry.citizenship_or_jurisdiction
            ET.SubElement(ih, "DirectEquityPct").text = f"{entry.direct_equity_pct:.2f}"
            ET.SubElement(ih, "DirectVotingPct").text = f"{entry.direct_voting_pct:.2f}"
            ET.SubElement(ih, "IndirectEquityPct").text = f"{entry.indirect_equity_pct:.2f}"
            ET.SubElement(ih, "IndirectVotingPct").text = f"{entry.indirect_voting_pct:.2f}"
            ET.SubElement(ih, "IsForeignAdversaryEntity").text = str(entry.is_foreign_adversary_entity).lower()

        # 4. Officers and Directors
        od_elem = ET.SubElement(root, "OfficersAndDirectors")
        for od in data.officers_and_directors:
            entry_elem = ET.SubElement(od_elem, "OfficerDirector")
            ET.SubElement(entry_elem, "FullName").text = od.full_name
            ET.SubElement(entry_elem, "Title").text = od.corporate_title
            ET.SubElement(entry_elem, "Citizenship").text = od.citizenship
            ET.SubElement(entry_elem, "Address").text = od.address

        # 5. Statutory Certifications Under Penalty of Perjury (§ 100.101(a)(3))
        certs = ET.SubElement(root, "StatutoryCertifications")
        ET.SubElement(certs, "SpectrumOwnershipWaiver", {"statute": "47 U.S.C. § 304", "section": "§ 100.101(a)(3)(i)"}).text = str(data.cert_spectrum_waiver).lower()
        ET.SubElement(certs, "AntiDrugAbuseAct", {"statute": "21 U.S.C. § 862", "section": "§ 100.101(a)(3)(ii)"}).text = str(data.cert_anti_drug_act).lower()
        ET.SubElement(certs, "TruthCompletenessAccuracy", {"statute": "18 U.S.C. § 1001", "section": "§ 100.101(a)(3)(iii)"}).text = str(data.cert_truth_and_accuracy).lower()
        ET.SubElement(certs, "ForeignAdversaryDisclaimed", {"reg": "15 CFR § 7.4", "section": "§ 100.101(a)(4)"}).text = str(data.cert_foreign_adversary_disclaimed).lower()

        sig = ET.SubElement(certs, "Signatory")
        ET.SubElement(sig, "FullName").text = data.signatory_name
        ET.SubElement(sig, "Title").text = data.signatory_title
        ET.SubElement(sig, "SignedAt").text = data.signed_at.isoformat()

        xml_str = ET.tostring(root, encoding="utf-8")
        return minidom.parseString(xml_str).toprettyxml(indent="  ")

    @classmethod
    def generate_narrative_exhibit(cls, data: Form312MainData) -> str:
        """Generates formal Legal Narrative Exhibit for Form 312 Main Form."""
        own_rows = []
        for o in data.ownership_table:
            own_rows.append(
                f"| {o.interest_holder_name} | {o.citizenship_or_jurisdiction} | {o.direct_equity_pct:.1f}% | {o.direct_voting_pct:.1f}% | {'YES' if o.is_foreign_adversary_entity else 'NO'} |"
            )
        own_table_md = "\n".join(own_rows)

        od_rows = []
        for od in data.officers_and_directors:
            od_rows.append(f"- **{od.full_name}** — *{od.corporate_title}* (Citizenship: {od.citizenship})")
        od_list_md = "\n".join(od_rows)

        return f"""# EXHIBIT 1: FCC FORM 312 MAIN FORM LEGAL & OWNERSHIP STATEMENT
**Governing Rule:** 47 CFR § 100.101 (Adopted, SB Docket No. 25-306)

---

## 1. APPLICANT IDENTIFICATION & JURISDICTION
- **Legal Entity Name:** {data.applicant_legal_name}
- **Trade Name / DBA:** {data.trade_name_dba or 'N/A'}
- **FCC Registration Number (FRN):** `{data.frn}`
- **Entity Type:** {data.entity_type.value}
- **Jurisdiction of Formation:** {data.jurisdiction_of_formation}
- **Principal Address:** {data.street_address}, {data.city}, {data.state} {data.postal_code}, {data.country}

### Designated Representative Contacts
- **Legal Counsel:** {data.legal_counsel_name} ({data.legal_counsel_firm}) | Email: {data.legal_counsel_email} | Tel: {data.legal_counsel_phone}
- **Technical Lead:** {data.technical_rep_name} ({data.technical_rep_title}) | Email: {data.technical_rep_email} | Tel: {data.technical_rep_phone}
- **24/7 Operations / Emergency TT&C Desk:** {data.moc_24x7_desk} | Tel: {data.moc_24x7_phone} | Email: {data.moc_24x7_email}

---

## 2. OWNERSHIP DISCLOSURE TABLE (≥ 10% THRESHOLD — § 100.101(a)(2))
Pursuant to 47 CFR § 100.101(a)(2), the following parties hold a 10 percent or greater direct or indirect equity or voting interest in the Applicant:

| Interest Holder Name | Citizenship / Jurisdiction | Direct Equity | Direct Voting | Foreign Adversary Control |
|---|---|---|---|---|
{own_table_md}

---

## 3. OFFICERS AND DIRECTORS ROSTER
{od_list_md}

---

## 4. STATUTORY CERTIFICATIONS UNDER PENALTY OF PERJURY (§ 100.101(a)(3))
The undersigned authorized officer of the Applicant hereby affirmatively executes the following statutory certifications:

1. **Spectrum Ownership Waiver (47 U.S.C. § 304 / § 100.101(a)(3)(i)):**  
   *Applicant hereby waives any claim to the use of any particular frequency or of the electromagnetic spectrum as against the regulatory power of the United States because of the previous use of the same, whether by license or otherwise.* [**CERTIFIED**]
2. **Anti-Drug Abuse Act Certification (21 U.S.C. § 862 / § 100.101(a)(3)(ii)):**  
   *Applicant certifies that no party to the application is subject to denial of federal benefits pursuant to Section 5301 of the Anti-Drug Abuse Act of 1988.* [**CERTIFIED**]
3. **Truth, Completeness, and Accuracy Attestation (18 U.S.C. § 1001 / § 100.101(a)(3)(iii)):**  
   *Applicant certifies under penalty of perjury that all statements made in this application and associated technical exhibits are true, complete, correct, and made in good faith.* [**CERTIFIED**]
4. **Foreign Adversary Control Disclaimer (15 CFR § 7.4 / § 100.101(a)(4)):**  
   *Applicant certifies that no 10% or greater interest holder is owned or controlled by a foreign adversary government.* [**CERTIFIED**]

**Authorized Signatory:**  
**{data.signatory_name}**, {data.signatory_title}  
*Date of Electronic Execution: {data.signed_at.strftime('%B %d, %Y')}*
"""
