# ORBITFLOW FULL — DEFINITIVE BUILD PLAN v3.0
## Post-FCC 25-69 Report & Order (Part 100 ADOPTED)

---

# EXECUTIVE SUMMARY: WHAT CHANGED

| Element | Old (Part 25) | New (Part 100 — ADOPTED) |
|---|---|---|
| Rule Part | Part 25 | **Part 100 (Space and Earth Station Services)** |
| Application Form | Form 312 + Schedule S | **Form 312 Main + Schedule O + Schedule F + Schedule B** |
| Review Approach | Bespoke narrative review | **Certification-based, "Default to Yes"** |
| Public Notice | 30 days | **15 days (single period)** |
| Exceptions | N/A | **7 Targeted Review Categories** |
| Expedited Processing | N/A | **NOT adopted (removed)** |
| Conditional Grants | Ad hoc | **3 types codified (OD deferral, commercial coord, federal coord)** |
| Surety Bonds | All space stations, escalating | **Processing round participants only, $10M flat, deescalating** |
| Milestones (NGSO non-PR) | 6yr 50%, 9yr 100% | **7yr BIU, 9yr 10%, 12yr 50%, 14yr 100% (ITU-aligned)** |
| Milestones (NGSO in PR) | 6yr 50%, 9yr 100% | **6yr 50%, 9yr 100% (retained)** |
| Milestones (GSO) | 5 years | **5 years (retained)** |
| Milestones (VTSS) | N/A | **None** |
| License Term | 15 years (GSO/NGSO), 6yr small sat | **20 years default** |
| Small Sat/Spacecraft Process | §§ 25.122, 25.123 | **ELIMINATED** |
| VTSS Category | N/A | **NEW category created** |
| MOSS Category | N/A | **NEW category created** |
| GSO Satellite System | Single sat per license | **Multiple sats at single location allowed** |
| Earth Station Licensing | Site-by-site | **Nationwide Non-Site License + Registration** |
| Ephemeris Sharing | Disclosure only | **REQUIRED (to SSA provider)** |
| Space Safety Reports | None | **Semi-annual (NGSO operators)** |
| De-orbit Rule | 25-year (phasing to 5) | **5-year post-mission (firm)** |
| Trackability | Statement | **10cm LEO / 1m above 2000km (affirmative obligation)** |
| ITU Filings | Required underlying application | **Can file without application (max 5, 2-year deadline)** |
| Two-Degree Spacing | All operations | **RETAINED (not changed to U.S.-only)** |
| Receive-Only Earth Stations | Licensed/registered | **RETAINED** |

---

# ARCHITECTURE: RULES-AS-DATA FOUNDATION

This is the **single most critical architectural decision**. Everything else sits on top of it.

## Regime Versioning Schema

```yaml
regimes:
  - regime_id: "fcc_part_25_active"
    status: "ACTIVE_SUNSETTING"
    source: "47 CFR Part 25"
    effective_date: "current"
    sunset_trigger: "Part 100 effective date"
    note: "Space Bureau managing transition"

  - regime_id: "fcc_part_100_adopted"
    status: "ADOPTED_PRE_EFFECTIVE"
    source: "FCC 25-69 Report & Order, SB Docket 25-306"
    adopted_date: "2026-07-22"  # Tentative consideration date
    effective_date: "60 days after Federal Register publication"
    omb_review: "Some sections pending OMB/PRA review"
    subparts:
      - "Subpart A – General"
      - "Subpart B – Applications and Licenses"
      - "Subpart C – Operational Rules"
      - "Subpart D – Compliance"

  - regime_id: "fcc_part_100_effective"
    status: "PENDING_ACTIVATION"
    trigger: "Federal Register publication"

  - regime_id: "fcc_fnprm_pending"
    status: "PENDING_COMMENT"
    source: "FCC 25-69 FNPRM"
    items:
      - "Operational envelopes"
      - "Space-based experimental licensing under Part 100"
      - "NGSO call sign merging"
      - "Hosted space stations (non-U.S.)"
      - "Ephemeris data sharing (expanded)"
      - "ISLs between U.S. and non-U.S. satellites"
      - "Frequency reuse (expanded)"
      - "Orbital debris (LEO collision avoidance, beyond-LEO trackability)"
      - "Two-degree GSO spacing (potential revision)"
      - "Secondary markets (processing round status exchange)"
      - "Renewal/replacement expectancies"
      - "U.S.-based control point requirement"
      - "Transfer of control efficiency"
      - "Export control compliance"
      - "Radio astronomy coexistence"
```

## Individual Rule Schema

```yaml
rule:
  rule_id: "deorbit_timeline"
  regime_id: "fcc_part_100_adopted"
  section: "§ 100.260(e)"
  title: "Low-Earth Orbit De-orbit Requirement"
  text: "Spacecraft ending mission in or passing through LEO below 2000km 
         must de-orbit within 5 years after end of mission"
  status: "ADOPTED"
  effective_date: "TBD (Federal Register)"
  applicability: ["NGSO", "VTSS (if terminating in LEO)", "GSO (N/A)"]
  certification_required: true
  schedule: "Schedule O"
  bright_line: true
  threshold: "5 years post-mission"
  previous_rule:
    regime: "fcc_part_25_active"
    section: "§ 25.114(d)(14)(vii)(D)(1)"
    text: "25-year rule (being phased to 5)"
  fnprm_revision: null
  confidence: "HIGH"
```

---

# MODULE 1: RULES-AS-DATA ENGINE (FOUNDATIONAL)

## Purpose
Central knowledge graph of all regulatory rules, versioned across regimes. Every other module queries this engine.

## Data Model

```
regulations
├── regime_id (FK)
├── rule_id (unique)
├── section_number
├── title
├── full_text
├── status (active/adopted/proposed/sunset)
├── effective_date
├── applicability[] (GSO/NGSO/VTSS/MOSS/Earth Station)
├── schedule_reference (O/F/B/Main Form)
├── certification_required (bool)
├── bright_line (bool)
├── threshold_value
├── threshold_unit
├── previous_rule_id (FK, nullable)
├── fnprm_item_id (FK, nullable)
├── citation_format
└── last_updated

fnprm_items
├── item_id
├── topic
├── status (comment/reply/adopted/rejected)
├── comment_deadline
├── reply_deadline
├── potential_impact
└── affected_rules[]
```

## Key Rules to Encode (Part 100 Adopted)

### Schedule O Certifications (NGSO) — § 100.111(c)(2)
1. Operates only in NGSO
2. Identifiable by unique signal-based telemetry marker
3. ≥10cm smallest dimension (LEO) OR ≥1m (above 2000km)
4. Will assess/mitigate collision risk on conjunction warning
5. Small debris collision probability ≤ 0.01 (NASA DAS)
6. Large object collision probability ≤ 0.001 (NASA DAS)
7. Human casualty risk ≤ 0.0001 (NASA DAS)
8. Stored energy removed at EOL
9. Disposed via atmospheric re-entry
10. Designed and operated to de-orbit ≤ 5 years post-mission
11. Probability of disposal success ≥ 0.9

### Schedule O Certifications (GSO) — § 100.111(b)(2)
1. Two-degree spacing compliance (§§ 100.230, 100.278, 100.279)
2. Orbital debris rules compliance (§ 100.260)
3. Small object collision probability ≤ 0.01
4. Stored energy removed at EOL
5. ≥1m smallest dimension

### Schedule O Certifications (VTSS) — § 100.111(d)(2)
1. Identifiable by unique telemetry marker
2. ≥10cm (LEO) or ≥1m (above 2000km)
3. Collision avoidance on conjunction warning
4. Share propagated ephemeris + covariance during maneuvers/RPO
5. Stored energy removed at EOL
6. Client servicing only with consent
7. Consult relevant federal agencies
8. LEO termination: comply with § 100.260(e)
9. GSO-arc termination: comply with § 100.260(b)
10. Beyond-GSO termination: dispose beyond Earth's orbit
11. Human casualty risk ≤ 0.0001 (if re-entry disposal)
12. Register with SSA provider ≥30 days pre-launch

### Schedule F Certifications — § 100.112(c)
1. Comply with all applicable technical/operational rules
2. Operate under ITU coordination procedures
3. Can be commanded to cease transmissions

### Form 312 Main Form Certifications — § 100.101(a)(3)
1. Waiver of frequency/spectrum ownership claims
2. Anti-Drug Act certification
3. Accuracy attestation (penalty of perjury)

## Targeted Review Categories — § 100.136(b)
1. **Failure to Certify** — any negative certification
2. **Waiver Requests** — any rule waiver
3. **Market Access** — non-U.S. licensed space station
4. **Foreign Ownership** — reportable foreign ownership
5. **Processing Round** — PR-eligible band + opt-in
6. **Spectral Constraints** — limited by rule/existing users/international
7. **Federal Coordination** — shared federal bands

## Build Priority: DAYS 1–7

---

# MODULE 2: ORGANIZATION & WORKSPACE SYSTEM

## Purpose
Multi-tenant foundation for all users.

## Features
- User accounts (email, password, 2FA)
- Organizations (law firms, startups, manufacturers)
- Teams within organizations
- Role-based access control
- Projects (one per satellite/earth station/mission)
- Client workspaces (law firm → client separation)
- Invitations
- Activity logs
- API key management

## Roles
| Role | Permissions |
|---|---|
| Owner | Full access, billing, delete |
| Admin | Full access except billing |
| Engineer | Create/edit projects, run calculations |
| Legal Reviewer | Review, approve, certify documents |
| Client Viewer | Read-only access to own projects |
| Partner Reseller | White-label, client management |
| Concierge Operator | Internal OrbitFlow staff |

## Database Tables
```
users
organizations
organization_members (user_id, org_id, role)
projects (org_id, name, type, status, created_at)
project_members (project_id, user_id, role)
invitations (org_id, email, role, token, expires_at)
activity_logs (user_id, org_id, action, entity, timestamp)
api_keys (org_id, key_hash, permissions, created_at, last_used)
```

## Build Priority: DAYS 8–12

---

# MODULE 3: PROJECT INTAKE WIZARD

## Purpose
Guided flow to create a new regulatory project. Determines system type and required filings.

## Intake Flow

```
Step 1: Select System Type
├── GSO Satellite System (one or more sats at single orbital location)
├── NGSO Satellite System (one or more sats, not VTSS)
├── VTSS (Variable Trajectory Spacecraft System)
├── MOSS (Multi-Orbit Satellite System)
├── Earth Station (Immovable, User Terminal, ESIM, Mobile)
├── Hosted Space Station
├── Amendment/Modification
├── Renewal
└── Transfer of Control / Assignment

Step 2: Operator Type
├── U.S. Licensed Operator
├── Non-U.S. Operator seeking U.S. Market Access
└── New Applicant (no prior FCC authorization)

Step 3: Mission Parameters (basic)
├── Number of satellites
├── Orbital regime (LEO/MEO/GEO/HEO/Cislunar/Beyond)
├── Frequency bands needed
├── Service type (FSS/MSS/BSS/ISL/TT&C)
├── Earth station requirements
└── Launch timeline

Step 4: Regulatory Pathway Determination (auto)
├── Required forms (Form 312 + Schedule O/F/B)
├── Processing round eligibility check
├── Surety bond requirement check
├── Milestone schedule assignment
├── Conditional grant eligibility
├── Targeted review category pre-screen
└── Estimated complexity score

Step 5: Output
├── Project ID
├── Regulatory pathway summary
├── Required filings checklist
├── Missing data list (pre-populated)
├── Estimated timeline
└── Estimated cost (filing fees, bond if applicable)
```

## System Type Determination Logic (from Part 100 definitions)

```python
def determine_system_type(params):
    if params.orbit == "geostationary":
        if params.num_satellites >= 1:
            return "GSO_SATELLITE_SYSTEM"  # § 100.3
    
    if params.orbit in ["beyond_geosynchronous", "variable_trajectory"]:
        return "VTSS"  # § 100.3
    
    if params.has_multiple_orbit_types:
        return "MOSS"  # § 100.3
    
    if params.orbit in ["LEO", "MEO", "HEO"] and params.orbit != "geostationary":
        return "NGSO_SATELLITE_SYSTEM"  # § 100.3
    
    return "UNKNOWN"  # Requires manual review
```

## Processing Round Eligibility Check

```python
def check_processing_round(params):
    # § 100.140(c)(4)(ii)
    pr_eligible_bands = get_current_pr_bands()  # Ka, Ku, Q, V initially
    
    if params.frequency_band in pr_eligible_bands:
        if params.requests_pr_inclusion:  # Opt-in required
            return {
                "eligible": True,
                "bond_required": True,
                "bond_amount": 10_000_000,  # § 100.148(d)
                "milestones": "6yr_50pct_9yr_100pct",  # § 100.147(d)
            }
    
    return {
        "eligible": False,
        "bond_required": False,
        "milestones": "7yr_BIU_9yr_10pct_12yr_50pct_14yr_100pct",  # § 100.147(b)
    }
```

## Build Priority: DAYS 13–18

---

# MODULE 4: DOCUMENT INTELLIGENCE ENGINE

## Purpose
AI-powered extraction of mission parameters from uploaded documents.

## Supported Inputs
- Satellite spec sheet (PDF)
- Mission concept deck (PDF/PPTX)
- Excel parameter sheet (XLSX/CSV)
- Previous FCC filing (PDF)
- ITU filing excerpt
- Engineering memo (DOCX)
- Plain text
- ZIP archive

## Extraction Targets (mapped to Part 100 fields)

### Schedule O Fields (§ 100.111)
```yaml
ngso_technical:
  - num_satellites
  - num_in_orbit_spares
  - orbital_planes
  - sats_per_plane
  - inclination_deg
  - orbital_period
  - apogee_km
  - perigee_km
  - argument_of_perigee
  - active_service_arcs
  - raan
  - initial_phase_angle
  - orbital_tolerances
  - estimated_operational_lifetime_years

gso_technical:
  - orbital_location
  - station_keeping_range_ew
  - station_keeping_range_ns
  - antenna_axis_attitude_accuracy

vtss_technical:
  - num_spacecraft_total
  - max_spacecraft_operating
  - operational_envelope_altitudes
  - operational_envelope_inclinations
  - initial_deployment_apogee
  - initial_deployment_perigee
  - initial_deployment_inclination
  - mission_phase_durations

orbital_debris:
  - mass_kg
  - dimensions_m
  - cross_section_area_m2
  - drag_coefficient
  - propulsion_type
  - fuel_mass_kg
  - delta_v_m_s
  - disposal_method
  - reentry_target
```

### Schedule F Fields (§ 100.112)
```yaml
frequency:
  - transmit_frequencies_mhz[]
  - receive_frequencies_mhz[]
  - polarization
  - channelization_plan
  - bandwidth_mhz
  - emission_designator
  - max_eirp_dbw
  - max_eirp_density_dbw_per_mhz
  - receive_antenna_gain_dbi
  - gain_to_temp_ratio_db_k
  - antenna_gain_contours
  - pfd_values
  - services[]
  - federal_allocation_bands[]
```

## AI Behavior Rules
1. Extract fields with confidence scores (0.0–1.0)
2. Flag missing fields explicitly
3. Flag contradictions between sources
4. Suggest assumptions for missing values (NEVER silently fill)
5. Require user confirmation for all extracted values
6. Every assumed value must be visible and editable
7. Citation: link extracted value to source document + page/section

## Technology Stack
- Claude 3.5 Sonnet or GPT-4o for extraction
- Structured output via function calling
- Pydantic validation schemas for every field
- PDF parsing: PyMuPDF + pdfplumber
- Table extraction: Camelot / Tabula
- OCR fallback: Tesseract for scanned documents

## Build Priority: DAYS 19–28

---

# MODULE 5: MISSION REGISTRY

## Purpose
Structured database of all mission parameters. Single source of truth for all calculations and document generation.

## Entity Schema

```
projects
├── id, org_id, name, system_type, status
├── regime_applicable (part_25 / part_100 / both)
├── created_at, updated_at
│
satellites (for NGSO/GSO)
├── project_id, name, designation
├── mass_kg, dry_mass_kg, wet_mass_kg
├── dimensions_l_m, dimensions_w_m, dimensions_h_m
├── cross_section_area_m2, drag_coefficient
├── propulsion_type, fuel_mass_kg, delta_v_m_s
├── power_w, mission_lifetime_years
├── disposal_method, reentry_target
├── trackability_dimension_cm
├── is_technically_identical (bool, for blanket)
│
orbits
├── satellite_id / project_id
├── orbit_type (LEO/MEO/GEO/HEO/VTSS_envelope)
├── altitude_km, inclination_deg, eccentricity
├── raan, arg_perigee, mean_anomaly, epoch
├── orbital_period_min
├── apogee_km, perigee_km
├── num_planes, sats_per_plane
├── station_keeping_ew_deg, station_keeping_ns_deg
│
frequencies
├── project_id, band_name, direction (uplink/downlink)
├── center_freq_mhz, bandwidth_mhz
├── emission_designator, polarization
├── power_w, eirp_dbw, eirp_density_dbw_mhz
├── antenna_id, modulation
├── service_type (FSS/MSS/BSS/ISL)
├── federal_allocation (bool)
│
earth_stations
├── project_id, type (Immovable/UserTerminal/ESIM/Mobile)
├── latitude, longitude, altitude_m
├── antenna_type, antenna_gain_dbi
├── num_antennas
├── frequencies[]
├── nationwide_non_site (bool)
│
antennas
├── id, type, gain_pattern_file
├── beamwidth_deg, sidelobe_level_db
│
filings
├── project_id, filing_type
├── form (312_Main / Schedule_O / Schedule_F / Schedule_B)
├── status (draft/review/submitted/granted)
├── fcc_file_number
├── submitted_at, granted_at
│
calculations
├── project_id, calc_type (ODAR/EPFD/PFD/collision/casualty)
├── inputs_json, outputs_json
├── engine_version, timestamp
│
documents
├── project_id, doc_type, template_id
├── version, status, file_path
├── review_status, reviewer_id
│
reviews
├── document_id, reviewer_id, role
├── status (pending/approved/rejected)
├── comments, approved_at
│
issues
├── project_id, severity, title, description
├── field, source, suggested_fix
├── status, assigned_to, resolved_by
```

## Build Priority: DAYS 29–35

---

# MODULE 6: REGULATORY PATHFINDING ENGINE

## Purpose
Determines which filings, rules, and processes apply to a given mission. Implements the Part 100 "licensing assembly line" logic.

## Decision Tree

```
INPUT: Mission parameters from Module 5

STEP 1: Determine System Type
├── GSO Satellite System → § 100.111(b)
├── NGSO Satellite System → § 100.111(c)
├── VTSS → § 100.111(d)
├── MOSS → § 100.111 (per component)
└── Earth Station → § 100.120

STEP 2: Determine Required Forms
├── ALL: FCC Form 312 – Main Form (§ 100.101)
├── Space Station: Schedule O (§ 100.111)
├── Space Station: Schedule F (§ 100.112)
├── Earth Station: Schedule B (§ 100.120)
├── Hosted Space Station: Form 312 + Schedule F + host's Schedule O ref
└── SCS: § 100.113 additional requirements

STEP 3: Determine Processing Pathway
├── Check Targeted Review Categories (§ 100.136(b))
│   ├── Failure to Certify? → Additional info required
│   ├── Waiver Request? → Merits review
│   ├── Market Access? → § 100.114 review
│   ├── Foreign Ownership? → Executive Branch referral possible
│   ├── Processing Round? → § 100.141 procedures
│   ├── Spectral Constraints? → Focused review
│   └── Federal Coordination? → NTIA coordination
│
├── IF zero categories → 15-day public notice → Grant
└── IF one or more → 15-day public notice → Focused review

STEP 4: Determine Conditional Grant Eligibility (§ 100.139)
├── Orbital Debris Deferral? (§ 100.139(a)(3))
│   ├── Must certify compliance with §§ 100.260, 100.111
│   ├── Must submit ODMP ≥6 months before launch integration
│   └── Cannot launch/operate until ODMP approved
├── Commercial Coordination? (§ 100.139(a)(4))
│   └── Grant non-coordinated bands, condition coordinated bands
└── Federal Coordination? (§ 100.139(a)(5))
    └── Grant non-federal bands, condition federal bands

STEP 5: Determine Bond & Milestones
├── Processing Round participant?
│   ├── YES → $10M bond (§ 100.148), 6yr/9yr milestones (§ 100.147(d))
│   └── NO → No bond, ITU milestones (§ 100.147(b))
├── GSO? → 5-year milestone (§ 100.147(a) retained)
├── VTSS? → No milestones, no bond
└── MOSS? → Per component

STEP 6: Determine Additional Requirements
├── Ephemeris sharing (§ 100.200(c))
├── Space safety reports (semi-annual, NGSO) (§ 100.200(d))
├── ITU filing requirements (§ 100.115)
├── NOAA remote sensing (if applicable)
├── FAA launch/reentry (if applicable)
└── State-level requirements

OUTPUT:
├── Required filings list
├── Processing pathway
├── Conditional grant options
├── Bond amount (if applicable)
├── Milestone schedule
├── Targeted review categories identified
├── Estimated timeline
└── Missing data list
```

## Build Priority: DAYS 36–45

---

# MODULE 7: CERTIFICATION DETERMINATION ENGINE

## Purpose
Evaluates whether available evidence supports affirmative certification for each bright-line criterion. **Does NOT make legal determinations.**

## Critical Language Rule

```
NEVER output: "You CAN certify this."
NEVER output: "You are compliant."

ALWAYS output:
"Based on supplied evidence [X] evaluated against [Rule § 100.YYY],
 the criterion evaluates: PASS/FAIL/INSUFFICIENT_DATA.
 
 Evidence used: [specific values]
 Assumptions: [specific assumptions]
 Confidence: HIGH/MEDIUM/LOW
 
 ⚠️ QUALIFIED HUMAN REVIEW REQUIRED BEFORE CERTIFICATION.
 OrbitFlow does not provide legal advice."
```

## Certification Evaluation Logic

```python
def evaluate_certification(cert_id, mission_data):
    rule = get_rule(cert_id)
    
    # Check if we have sufficient data
    required_fields = rule.required_evidence_fields
    missing = [f for f in required_fields if f not in mission_data]
    
    if missing:
        return {
            "status": "INSUFFICIENT_DATA",
            "missing_fields": missing,
            "message": f"Cannot evaluate. Missing: {missing}"
        }
    
    # Run deterministic calculation
    result = run_calculation(rule.calculation_engine, mission_data)
    
    # Compare against threshold
    if result.value <= rule.threshold:
        status = "PASS"
    else:
        status = "FAIL"
    
    return {
        "status": status,
        "value": result.value,
        "threshold": rule.threshold,
        "evidence": mission_data.relevant_fields,
        "assumptions": result.assumptions,
        "calculation_trace": result.trace,
        "confidence": result.confidence,
        "human_review_required": True,  # ALWAYS
        "citation": rule.citation_format,
    }
```

## Certifications to Evaluate

| ID | Criterion | Engine | Threshold |
|---|---|---|---|
| NGSO-01 | Operates only in NGSO | Orbit check | orbit ≠ GSO |
| NGSO-02 | Unique telemetry marker | User input | N/A |
| NGSO-03 | Trackability (≥10cm LEO / ≥1m >2000km) | Dimension check | Per altitude |
| NGSO-04 | Collision avoidance capability | User input | N/A |
| NGSO-05 | Small debris collision ≤ 0.01 | NASA DAS / poliastro | ≤ 0.01 |
| NGSO-06 | Large object collision ≤ 0.001 | NASA DAS / poliastro | ≤ 0.001 |
| NGSO-07 | Human casualty ≤ 0.0001 | NASA DAS | ≤ 0.0001 |
| NGSO-08 | Stored energy removed at EOL | Design check | N/A |
| NGSO-09 | Atmospheric re-entry disposal | Orbit check | Disposal = re-entry |
| NGSO-10 | De-orbit ≤ 5 years | Orbital mechanics | ≤ 5 years |
| NGSO-11 | Disposal success ≥ 0.9 | Engineering calc | ≥ 0.9 |
| GSO-01 | Two-degree spacing | Orbital location check | ≥ 2° |
| GSO-02 | Orbital debris compliance | ODAR engine | Per rules |
| GSO-03 | Small object collision ≤ 0.01 | NASA DAS | ≤ 0.01 |
| GSO-04 | Stored energy removed | Design check | N/A |
| GSO-05 | ≥ 1m smallest dimension | Dimension check | ≥ 1m |
| VTSS-01 through VTSS-12 | (per § 100.111(d)(2)) | Various | Various |
| FREQ-01 | Comply with technical rules | Multi-check | Per rules |
| FREQ-02 | ITU coordination | User input | N/A |
| FREQ-03 | Cease transmission capability | User input | N/A |

## Build Priority: DAYS 46–55

---

# MODULE 8: TARGETED REVIEW CATEGORY IDENTIFIER

## Purpose
Automatically identifies which of the 7 Targeted Review Categories apply to a given application.

## Logic

```python
def identify_targeted_review_categories(mission_data, certifications):
    categories = []
    
    # 1. Failure to Certify
    negative_certs = [c for c in certifications if c.status == "FAIL"]
    if negative_certs:
        categories.append({
            "category": "FAILURE_TO_CERTIFY",
            "section": "§ 100.136(b)(1)",
            "details": negative_certs,
            "action": "Additional information/waiver required"
        })
    
    # 2. Waiver Requests
    if mission_data.waiver_requests:
        categories.append({
            "category": "WAIVER_REQUEST",
            "section": "§ 100.136(b)(2)",
            "details": mission_data.waiver_requests,
            "action": "Merits review"
        })
    
    # 3. Market Access
    if mission_data.operator_type == "NON_US_MARKET_ACCESS":
        categories.append({
            "category": "MARKET_ACCESS",
            "section": "§ 100.136(b)(3)",
            "details": "Non-U.S. licensed space station",
            "action": "§ 100.114 review"
        })
    
    # 4. Foreign Ownership
    if mission_data.foreign_ownership_reportable:
        categories.append({
            "category": "FOREIGN_OWNERSHIP",
            "section": "§ 100.136(b)(4)",
            "details": mission_data.foreign_ownership_details,
            "action": "Possible Executive Branch referral"
        })
    
    # 5. Processing Round
    if mission_data.processing_round_requested:
        categories.append({
            "category": "PROCESSING_ROUND",
            "section": "§ 100.136(b)(5)",
            "details": f"Band: {mission_data.frequency_band}",
            "action": "§ 100.141 procedures"
        })
    
    # 6. Spectral Constraints
    if mission_data.spectral_constraints:
        categories.append({
            "category": "SPECTRAL_CONSTRAINTS",
            "section": "§ 100.136(b)(6)",
            "details": mission_data.spectral_constraint_details,
            "action": "Focused review"
        })
    
    # 7. Federal Coordination
    if mission_data.federal_bands:
        categories.append({
            "category": "FEDERAL_COORDINATION",
            "section": "§ 100.136(b)(7)",
            "details": mission_data.federal_bands,
            "action": "NTIA coordination"
        })
    
    return categories
```

## Build Priority: DAYS 56–60

---

# MODULE 9: ORBITAL DEBRIS ASSESSMENT ENGINE

## Purpose
Calculates all orbital debris metrics required by Part 100 Subpart C.

## Calculations

### 1. Orbital Lifetime (§ 100.260(e))
- Input: mass, area, Cd, altitude, inclination, solar activity
- Engine: `poliastro` / `skyfield` + atmospheric density model (HWM14/NRLMSISE-00)
- Output: Time from end-of-mission to re-entry
- Threshold: ≤ 5 years for LEO

### 2. Collision Probability — Small Debris (§ 100.111(c)(2)(v))
- Input: mass, area, orbit, mission lifetime
- Engine: NASA DAS equivalent / ORDEM
- Output: Probability of collision with small debris causing loss of control
- Threshold: ≤ 0.01

### 3. Collision Probability — Large Objects (§ 100.111(c)(2)(vi))
- Input: orbit, mission lifetime, maneuverability
- Engine: NASA DAS equivalent
- Output: Probability of collision with objects ≥ 10cm
- Threshold: ≤ 0.001
- Note: May assume zero during periods of effective maneuvering

### 4. Human Casualty Risk (§ 100.111(c)(2)(vii))
- Input: mass, dimensions, material composition, re-entry parameters
- Engine: NASA DAS casualty risk module
- Output: Probability of human casualty from surviving debris > 15 joules
- Threshold: ≤ 0.0001 (1 in 10,000)

### 5. Disposal Success Probability (§ 100.111(c)(2)(xi))
- Input: propulsion system reliability, fuel margin, disposal maneuver design
- Engine: Engineering reliability calculation
- Output: Probability of successful disposal
- Threshold: ≥ 0.9

### 6. Stored Energy Assessment (§ 100.111(c)(2)(viii))
- Input: fuel type, tank pressure, battery type, pressurant systems
- Engine: Checklist-based assessment
- Output: PASS/FAIL + mitigation recommendations

## Output Report Sections
1. Executive Summary
2. Applicant Information
3. Satellite Description
4. Orbit Description
5. Mission Lifetime
6. Debris Release Assessment
7. Passivation Plan
8. Post-Mission Disposal Plan
9. Orbital Lifetime Estimate
10. 5-Year Rule Compliance
11. Collision Avoidance Capability
12. Reentry Risk Summary
13. Assumptions
14. Methodology
15. Missing Data
16. Human Review Required
17. Disclaimer

## Scientific Libraries
```
poliastro  — Orbital mechanics
skyfield   — Ephemeris, Earth orientation
astropy    — Coordinate transforms, time
numpy      — Numerical computation
scipy      — Optimization, integration
pandas     — Data handling
```

## Build Priority: DAYS 61–75

---

# MODULE 10: SPECTRUM INTERFERENCE ENGINE

## Purpose
Calculates EPFD, PFD, I/N, and coordination metrics required by Part 100.

## Calculations

### 1. EPFD (Equivalent Power Flux Density) — § 100.222
- ITU-R S.1432 methodology
- NGSO into GSO interference
- Per beam, per frequency
- Threshold: ITU limits per Article 22

### 2. PFD (Power Flux Density) — § 100.212
- At Earth's surface
- Per angle of arrival (0-5°, 5-25°, 25-90°)
- Per bandwidth (4 kHz / 1 MHz)
- Band-specific thresholds

### 3. I/N (Interference-to-Noise Ratio)
- For coordination assessments
- Terrestrial interference potential
- Earth station interference potential

### 4. Coordination Distance
- ITU-R P.618 (rain attenuation)
- ITU-R P.1546 (point-to-area)
- ITU-R P.1812 (terrestrial)
- Terrain data integration

### 5. Off-Axis EIRP Density — § 100.280
- GSO: tangent and perpendicular planes
- NGSO: all angles
- Threshold: per § 100.280 tables

## ITU Recommendations to Implement
```
ITU-R P.618   — Propagation for Earth-space links
ITU-R S.1432  — EPFD calculation
ITU-R SF.1602 — PFD limits
ITU-R M.1642  — Sharing methodology
ITU-R P.1546  — Point-to-area propagation
ITU-R P.1812  — Terrestrial propagation
```

## Libraries
```
itu-rpy    — ITU recommendation implementations
Py1546     — ITU-R P.1546
Py1812     — ITU-R P.1812
geopy      — Geodesic calculations
shapely    — Geometry operations
```

## Build Priority: DAYS 76–90

---

# MODULE 11: FCC FILING GENERATOR

## Purpose
Generates all FCC filing documents in Part 100 format.

## Documents Generated

### 1. FCC Form 312 – Main Form (§ 100.101)
```
- Contact information
- Ownership information (10% threshold)
- Officers and directors
- Ownership diagram (vertical structure)
- Certifications:
  - Spectrum ownership waiver
  - Anti-Drug Act
  - Accuracy attestation
- Foreign ownership disclosure
- Foreign Adversary Control attestation
```

### 2. Schedule O — Orbital Information (§ 100.111)
```
GSO Section:
- Orbital location
- Station-keeping parameters
- Certifications (5 items)

NGSO Section:
- Technical information (13 fields)
- Certifications (11 items)
- Additional information (if applicable)

VTSS Section:
- Technical information (4 fields)
- Certifications (12 items)
- Additional information

Orbital Debris Mitigation Plan (attached)
```

### 3. Schedule F — Frequency Information (§ 100.112)
```
- Services identified
- Frequency table (uplink/downlink)
- Federal allocation identification
- EIRP / EIRP density per beam
- Receive antenna parameters
- Antenna gain contours
- PFD values
- Transmitter/receiver characteristics
- Spectrum sharing description
- Common carrier status
- Certifications (3 items)
```

### 4. Schedule B — Earth Station (§ 100.120)
```
- Type of application
- Technical information
- Service-specific requirements
- Certifications
- Coordination report reference
```

### 5. Supplemental Documents
- Orbital Debris Mitigation Plan (ODMP)
- End-of-Life Disposal Plan
- Spectrum Coordination Exhibit
- Comprehensive System Description
- Public Interest Statement
- Conditional Grant Request (if applicable)

## Output Formats
- PDF (primary, professional formatting)
- DOCX (editable)
- JSON (machine-readable, for future ICFS integration)
- XML (ITU-compatible export)
- CSV (data tables)

## Build Priority: DAYS 91–105

---

# MODULE 12: ITU FILING PREPARATION ENGINE

## Purpose
Prepares ITU filing materials. Note: Under Part 100, ITU filings can be submitted WITHOUT an underlying space station application (max 5 filings, 2-year deadline to file application).

## Documents
1. Advance Publication Information (API) package
2. Coordination Request (CR/C) preparation
3. Notification preparation
4. Frequency assignment tables
5. Network parameter validation
6. ITU e-submission compatible exports
7. Coordination trigger report
8. Missing coordination data report

## Key Part 100 Provisions (§ 100.115)
- Max 5 ITU filings without underlying application
- 2-year deadline to file space station application
- Form 312 Main Form required before ITU submission
- Cost recovery responsibility declaration

## Build Priority: DAYS 106–115

---

# MODULE 13: CONDITIONAL GRANT ELIGIBILITY ENGINE

## Purpose
Determines eligibility for the 3 types of conditional grants under § 100.139.

## Types

### 1. Orbital Debris Deferral (§ 100.139(a)(3))
```python
def check_od_deferral_eligibility(mission_data):
    requirements = {
        "all_app_info_provided": check_sections_100_110_through_113(mission_data),
        "certifies_compliance_100_260": mission_data.certifies_od_compliance,
        "certifies_compliance_100_111": mission_data.certifies_schedule_o,
        "will_submit_odmp_6mo_pre_launch": mission_data.commits_to_odmp_timeline,
    }
    
    if all(requirements.values()):
        return {
            "eligible": True,
            "conditions": [
                "Cannot launch/operate until ODMP approved",
                "Must submit ODMP ≥6 months before launch integration",
                "If ODMP non-compliant → major modification required",
                "Conditional grant void if major modification filed",
            ],
            "citation": "§ 100.139(a)(3)"
        }
    return {"eligible": False, "missing": [k for k,v in requirements.items() if not v]}
```

### 2. Commercial Coordination (§ 100.139(a)(4))
- Grant non-coordinated bands immediately
- Condition coordinated bands on notice of completion
- Not available for processing round NGSO FSS (§ 100.139(a)(4)(i))

### 3. Federal Coordination (§ 100.139(a)(5))
- Grant non-federal bands immediately
- Condition federal bands on NTIA coordination
- Available for both space and earth stations

## Build Priority: DAYS 116–120

---

# MODULE 14: PROCESSING ROUND & SURETY BOND CALCULATOR

## Purpose
Calculates bond amounts, determines PR status, tracks deployment.

## Surety Bond Formula (§ 100.148(d))

```python
def calculate_bond(num_authorized, num_deployed):
    """
    § 100.148(d) — Processing Round Participants Only
    B = $10,000,000 - $10,000,000 * (D / (0.9 * A))
    Rounded to nearest dollar.
    Reaches $0 at 90% deployment.
    """
    A = num_authorized  # excluding replacements
    D = num_deployed
    
    B = 10_000_000 - 10_000_000 * (D / (0.9 * A))
    B = max(0, round(B))
    
    return {
        "bond_amount": B,
        "deployment_pct": D / A * 100,
        "bond_relieved_at_pct": 90.0,
        "formula": "B = $10M - $10M * (D/(0.9*A))",
        "citation": "§ 100.148(d)",
    }
```

## Milestone Schedules

```python
def get_milestone_schedule(system_type, in_processing_round):
    if system_type == "VTSS":
        return None  # No milestones (§ 100.147)
    
    if system_type == "GSO":
        return {"5yr": "Launch, position, operate at assigned location"}
    
    if system_type in ["NGSO", "MOSS_NGSO_component"]:
        if in_processing_round:
            return {
                "6yr": "50% deployed and operating",
                "9yr": "100% deployed and operating",
                "note": "Failure at 6yr → reassignment to later PR (§ 100.147(d))"
            }
        else:
            return {
                "7yr": "≥1 satellite deployed, operating 90 days continuous (BIU)",
                "9yr": "10% deployed and operating",
                "12yr": "50% deployed and operating",
                "14yr": "100% deployed and operating",
                "note": "Failure at 7yr → automatic termination (§ 100.147(d)(1))"
            }
```

## Processing Round Calendar (§ 100.141)
- Opens: January 1, 12:00 AM ET
- Closes: October 31, 11:59 PM ET
- Bands: Ka, Ku, Q, V (initially; Space Bureau adds annually)
- Priority: Based on filing date (not grant date)

## Build Priority: DAYS 121–128

---

# MODULE 15: EPHEMERIS & SPACE SAFETY REPORTING

## Purpose
Tracks ephemeris sharing obligations and generates semi-annual space safety reports.

## Ephemeris Requirements (§ 100.200(c))
- Submit to: 18th Space Control Squadron OR Commission-designated SSA provider
- Include: propagated ephemeris + covariance for planned maneuvers
- VTSS: Share prior to and during maneuvers/RPO (§ 100.111(d)(2)(iv))
- VTSS: Register with SSA provider ≥30 days pre-launch (§ 100.111(d)(2)(xii))

## Space Safety Report (§ 100.200(d))
- Frequency: Semi-annual (January 1 and July 1)
- Coverage: Preceding 6 months (Jun 1–Nov 30, Dec 1–May 31)
- Applies to: NGSO operators after first satellite launch
- Contents:
  1. Number of conjunction events (including those resulting in maneuver/coordination)
  2. Number of satellites removed from operation or screened from deployment
  3. Number of satellites that re-entered atmosphere

## Build Priority: DAYS 129–135

---

# MODULE 16: ISSUE & MISSING-DATA ENGINE

## Purpose
Tracks all gaps, assumptions, warnings, and required human review items.

## Issue Types
| Type | Severity | Action |
|---|---|---|
| Missing field | Medium | Prompt user |
| Low confidence extraction | Medium | Flag for review |
| Regulatory conflict | High | Escalate |
| Failed calculation | High | Investigate |
| Assumption used | Low | Document |
| Data out of range | High | Validate |
| Unsupported filing type | High | Manual review |
| Human review required | Always | Block until reviewed |
| Agency risk flag | High | Escalate |
| Negative certification | High | Waiver/additional info |

## Build Priority: DAYS 136–140

---

# MODULE 17: HUMAN REVIEW & CERTIFICATION ENGINE

## Purpose
Workflow for expert review, approval, and certification of generated documents.

## Features
- Review task assignment
- Reviewer comments (inline)
- Approval states (pending → approved / rejected → revision needed)
- Electronic sign-off
- Review certificate generation
- Review history (immutable log)
- Document version locking after approval
- Multi-reviewer workflows (engineer + legal)

## Review Certificate Contents
```
- Reviewer name, role, organization
- Document ID, version
- Timestamp of approval
- Approved scope (which sections)
- Assumptions accepted
- Signature hash
- Disclaimer: "This document was generated with automated assistance
  and reviewed by qualified personnel. OrbitFlow does not provide
  legal advice or certify regulatory approval."
```

## Build Priority: DAYS 141–148

---

# MODULE 18: DOCUMENT GENERATION ENGINE

## Purpose
Final assembly of all output documents with professional formatting.

## Template System
- HTML/CSS → PDF (via WeasyPrint)
- DOCX templates (via python-docx)
- JSON schemas (for machine-readable export)
- XML schemas (ITU-compatible)

## Required Qualities
- Professional formatting (law-firm quality)
- Page numbers, headers, footers
- Table of contents
- Citation blocks (rule + section + effective date)
- Calculation tables with full traceability
- Version number, project ID, generation timestamp
- Review status watermark
- Disclaimer on every page
- "PROPOSED/ADOPTED" regime indicator

## Complete Bundle Contents
1. Executive Summary
2. Regulatory Pathway Memo
3. Certification Determination Matrix
4. Targeted Review Category Analysis
5. Missing Data Report
6. Assumptions Report
7. ODMP / ODAR Report
8. FCC Form 312 Main Form (draft)
9. Schedule O (draft)
10. Schedule F (draft)
11. Schedule B (draft, if earth station)
12. Spectrum Interference Report
13. ITU Preparation Package
14. Conditional Grant Eligibility Report
15. Bond & Milestone Schedule
16. Filing Checklist
17. Review Certificate
18. Audit Log
19. Export Metadata

## Build Priority: DAYS 149–158

---

# MODULE 19: EARTH STATION MODULE (Nationwide Non-Site)

## Purpose
Handles the new Nationwide Non-Site License + Registration workflow.

## Key Provisions (§ 100.120, § 100.121)
- Two-step process: License → Register sites
- Immovable earth stations only (not ESIM, VSAT, SCS, MES, User Terminal)
- No waivers allowed for NNS registration
- Coordination required before operation at registered site
- 365-day bring-into-use deadline per registration
- Pre-grant operations: Non-waiver applications with approved Form 312 can operate on non-interference basis once on public notice

## Build Priority: DAYS 159–165

---

# MODULE 20: CLIENT & PARTNER PORTALS

## Startup Portal
- Project status dashboard
- Missing data list
- Generated documents (download)
- Payment history
- Support tickets
- Filing deadline tracker
- Milestone progress tracker
- Bond status tracker

## Law Firm Portal
- White-label branding
- Client folder management
- Unlimited/credit-based generation
- Margin dashboard
- Template customization
- Client sharing (read-only links)
- Review workflow
- Batch generation

## Manufacturer Portal
- Customer project management
- Regulatory fast-track packages
- Deal status tracking
- Bulk generation
- API access
- Usage billing
- Integration with sales CRM

## Launch Integrator Portal
- Customer readiness dashboard
- Filing status visibility
- Risk flags
- Upload requests
- Deadline alerts
- Coordination status

## Build Priority: DAYS 166–180

---

# MODULE 21: BILLING & CREDIT SYSTEM

## Pricing Products

| Product | Price | Target |
|---|---|---|
| ODAR/ODMP Draft | $499 | Startups |
| Certification Assessment (Part 25→100 Delta) | $1,500 | Startups/Law firms |
| FCC Filing Package (Schedule O+F+Form 312) | $2,500–$5,000 | Startups |
| ITU Prep Package | $1,500 | Startups |
| EPFD/Spectrum Report | $1,500 | Startups |
| Full Filing Bundle | $5,000 | Startups |
| Startup Subscription | $999/month | Startups |
| Law Firm Starter | $999/month | Small firms |
| Law Firm Pro | $15,000/year | Mid firms |
| White-Label Add-on | $5,000/year | Firms |
| Manufacturer Platform | $25,000/year | Manufacturers |
| Per-Customer Filing Fee | $1,000–$3,000 | Manufacturers |
| Enterprise/API | Usage-based | Large operators |
| Concierge Retainer | $5,000–$10,000/month | Complex cases |

## Credit Actions
- Generate ODAR: 1 credit
- Generate EPFD report: 2 credits
- Generate FCC package: 3 credits
- Generate ITU package: 2 credits
- Run constellation batch: 5 credits
- Export white-label PDF: 1 credit
- API call: 0.1 credits
- Concierge review unit: 5 credits

## Payment Stack
- Stripe (subscriptions, one-time, invoices)
- Usage metering
- Credit ledger
- Tax handling
- Invoice generation

## Build Priority: DAYS 181–190

---

# MODULE 22: API & INTEGRATION LAYER

## API Endpoints

```
POST   /api/v1/projects
GET    /api/v1/projects/{id}
POST   /api/v1/projects/{id}/documents/upload
POST   /api/v1/projects/{id}/extract
POST   /api/v1/projects/{id}/validate
POST   /api/v1/projects/{id}/calculations/odar
POST   /api/v1/projects/{id}/calculations/epfd
POST   /api/v1/projects/{id}/generate/fcc-package
POST   /api/v1/projects/{id}/generate/itu-package
GET    /api/v1/projects/{id}/issues
POST   /api/v1/projects/{id}/review
POST   /api/v1/projects/{id}/approve
GET    /api/v1/projects/{id}/status
GET    /api/v1/projects/{id}/download
GET    /api/v1/regimes
GET    /api/v1/rules?regime={id}&section={section}
POST   /api/v1/bonds/calculate
GET    /api/v1/milestones?system_type={type}&pr={bool}
```

## Integrations
- Stripe (payments)
- CRM (Salesforce, HubSpot)
- Slack (notifications)
- Email alerts (SendGrid)
- Space-Track.org (TLE data)
- FCC ICFS (future, when API available)
- ITU e-submission (export format)
- Google Drive / Dropbox (document storage)
- DocuSign / equivalent (e-signature)

## Build Priority: DAYS 191–200

---

# MODULE 23: AUDIT, SECURITY & COMPLIANCE

## Security
- Encrypted storage (AES-256 at rest, TLS 1.3 in transit)
- Role-based access control
- SSO (SAML, OIDC)
- 2FA (TOTP, hardware keys)
- Session management
- Secrets management (Vault / AWS Secrets Manager)
- API key rotation
- Rate limiting
- IP allowlisting (enterprise)

## Audit
- Every calculation logged (inputs, outputs, engine version)
- Every assumption logged
- Every document version stored
- Every user action logged
- Every export logged
- Every review decision logged
- Immutable audit trail (append-only)

## Compliance Posture
- Assistive tool disclaimer (every screen, every document)
- Human review required (enforced in workflow)
- No unauthorized legal advice
- No unauthorized engineering certification
- Data retention controls (configurable per client)
- Client data isolation (tenant separation)
- GDPR-ready data deletion
- Export control awareness (ITAR/EAR flag)

## Build Priority: DAYS 201–210

---

# BUILD SEQUENCE SUMMARY

| Phase | Days | Modules | Milestone |
|---|---|---|---|
| **Phase 0** | 1–7 | Rules-as-Data Engine (core) | Rules encoded |
| **Phase 1** | 8–35 | Org System, Intake, Doc Intelligence, Mission Registry | User can upload spec → structured data |
| **Phase 2** | 36–60 | Regulatory Pathfinding, Certification Engine, Targeted Review | User gets pathway + certification matrix |
| **Phase 3** | 61–90 | ODAR Engine, Spectrum Engine | Calculations working |
| **Phase 4** | 91–120 | FCC Filing Generator, ITU Prep, Conditional Grants | Documents generated |
| **Phase 5** | 121–148 | Bond/Milestone, Ephemeris, Issues, Human Review | Full workflow |
| **Phase 6** | 149–165 | Document Gen, Earth Station Module | Complete bundle output |
| **Phase 7** | 166–210 | Portals, Billing, API, Audit/Security | Platform complete |

**Total: ~210 days (7 months) for full platform**

---

# VERTICAL SLICE (FIRST 30 DAYS — SELL THIS)

While building the full platform, ship the **Part 25 → Part 100 Transition Readiness Assessment** in 30 days:

## What It Does
1. User uploads satellite spec sheet
2. AI extracts parameters
3. Engine evaluates against BOTH Part 25 (current) AND Part 100 (adopted)
4. Generates a Delta Report showing:
   - What changes for this specific mission
   - Which certifications can/cannot be met
   - Bond requirement (old vs new)
   - Milestone schedule (old vs new)
   - Conditional grant eligibility
   - Targeted review categories
   - Missing data
   - Recommended filing strategy (file now under Part 25 vs wait for Part 100)

## Price
$1,500–$3,000 per assessment

## Target
- Space law firms (5 free assessments → $15K/year license)
- NewSpace startups with pending filings
- Satellite manufacturers with customer pipelines

## Tech Stack for Vertical Slice
```
Frontend: Next.js + Tailwind + shadcn/ui
Backend: Python FastAPI
Database: PostgreSQL
AI: Claude 3.5 Sonnet (extraction)
Calculations: poliastro, skyfield
PDF: WeasyPrint
Payments: Stripe
Hosting: Railway/Render
```

---

# REPO STRUCTURE

```
orbitflow/
├── apps/
│   ├── web/                    # Next.js frontend
│   ├── admin/                  # Internal admin panel
│   └── partner/                # White-label partner portal
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI routes
│   │   ├── core/              # Config, security, deps
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   ├── engines/
│   │   │   ├── rules/         # Rules-as-data engine
│   │   │   ├── odar/          # Orbital debris calculations
│   │   │   ├── epfd/          # Spectrum interference
│   │   │   ├── itu/           # ITU prep
│   │   │   ├── fcc/           # FCC form generation
│   │   │   ├── faa/           # FAA readiness
│   │   │   ├── certification/ # Certification evaluation
│   │   │   ├── pathway/       # Regulatory pathfinding
│   │   │   ├── bonds/         # Bond/milestone calculator
│   │   │   └── conditional/   # Conditional grant logic
│   │   ├── ai/               # Document extraction
│   │   ├── documents/         # Template rendering
│   │   ├── billing/           # Stripe integration
│   │   └── audit/             # Audit logging
│   ├── workers/               # Celery/ARQ background jobs
│   └── tests/
├── rules/                     # YAML/JSON rule definitions
│   ├── part_25/
│   ├── part_100/
│   └── fnprm/
├── templates/
│   ├── pdf/
│   ├── docx/
│   ├── html/
│   ├── fcc/
│   ├── itu/
│   └── odar/
├── research/
│   ├── fcc/
│   ├── faa/
│   ├── itu/
│   ├── nasa/
│   └── examples/
├── docs/
├── scripts/
└── infra/
```

---

# FINAL DEFINITION OF DONE

The product is complete when a user can:

1. ✅ Create an organization
2. ✅ Invite team members
3. ✅ Create a satellite project (GSO/NGSO/VTSS/MOSS)
4. ✅ Upload a spec sheet
5. ✅ Extract mission data automatically
6. ✅ Confirm and correct fields
7. ✅ Receive regulatory pathway (Part 100)
8. ✅ Receive certification determination matrix
9. ✅ Receive targeted review category analysis
10. ✅ Run ODAR calculations
11. ✅ Run EPFD calculations
12. ✅ Generate FCC Form 312 Main Form draft
13. ✅ Generate Schedule O draft
14. ✅ Generate Schedule F draft
15. ✅ Generate Schedule B draft (earth station)
16. ✅ Generate ITU preparation packages
17. ✅ Determine conditional grant eligibility
18. ✅ Calculate surety bond amount
19. ✅ Determine milestone schedule
20. ✅ See all missing data and warnings
21. ✅ Assign human review
22. ✅ Approve and lock documents
23. ✅ Download complete filing bundle
24. ✅ Pay through Stripe
25. ✅ Manage clients through partner portal
26. ✅ Export audit logs
27. ✅ Use the API
28. ✅ Track filing status through lifecycle
29. ✅ Track milestone compliance
30. ✅ Generate space safety reports

---

# START NOW

**Day 1 task:** Initialize the repo. Create the `rules/` directory. Begin encoding the first 10 Part 100 rules in YAML. Set up PostgreSQL schema for the `regulations` table.

**Day 7 task:** Have 50 core Part 100 rules encoded. Rules-as-data engine querying them.

**Day 30 task:** Ship the Part 25 → Part 100 Delta Report. Send it to 5 space law firms. Get first paying customer.

**This is the plan. Build it.**
