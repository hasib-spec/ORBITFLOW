"""
OrbitFlow MVP — Streamlit Concierge Regulatory Dashboard
=========================================================

Autonomous FCC Part 100 Delta & Certification Audit Platform.
Powered by:
- Live CelesTrak GP OMM Satellite Telemetry
- Live NOAA SWPC Space Weather & Solar Radio Flux
- FCC Part 100 Knowledge Base (FCC 25-69, SB Docket 25-306)

Run with:
    streamlit run apps/mvp_streamlit/app.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Ensure project root is on sys.path for imports ──
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.engines.delta.engine import run_delta_audit  # noqa: E402
from backend.app.engines.doc_intel import (  # noqa: E402
    DocumentParser,
    get_doc_engine,
)
from backend.app.integrations.space_data import get_space_client  # noqa: E402
from backend.app.models.satellite import (  # noqa: E402
    CertStatus,
    OrbitType,
    SatelliteSpec,
)
from backend.app.pdf_gen.generator import generate_delta_report  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & STYLING
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="OrbitFlow Delta & ODAR Engine — FCC Part 100",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        background-color: #0F172A;
    }
    section[data-testid="stSidebar"] * {
        color: #E2E8F0 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stNumberInput label,
    section[data-testid="stSidebar"] .stTextInput label,
    section[data-testid="stSidebar"] .stCheckbox label,
    section[data-testid="stSidebar"] .stFileUploader label {
        color: #93C5FD !important;
        font-weight: 600;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .main-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
        padding: 1.5rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.25rem;
        border-left: 5px solid #0EA5E9;
    }
    .main-header h1 { color: #FFFFFF !important; margin: 0; font-size: 1.8rem; font-weight: 800; }
    .main-header p  { color: #93C5FD !important; margin: 0.25rem 0 0 0; font-size: 0.95rem; }

    .live-badge {
        background: #064E3B;
        color: #A7F3D0 !important;
        border: 1px solid #059669;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        margin-bottom: 1rem;
        font-size: 0.85rem;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION (REAL SATELLITE PRESETS)
# ═══════════════════════════════════════════════════════════════════════════

REAL_PRESETS = {
    "Starlink Gen2 (SpaceX)": {
        "name": "Starlink Gen2 System",
        "operator": "SpaceX (Space Exploration Technologies Corp.)",
        "orbit_type": "LEO",
        "altitude": 530.0,
        "inclination": 53.0,
        "num_auth": 7500,
        "num_dep": 2500,
        "dimension": 100.0,
        "mass": 800.0,
        "lifetime": 5.0,
        "has_prop": True,
        "deorbit_yrs": 1.5,
        "in_pr": True,
        "fed_bands": False,
        "foreign_pct": 5.2,
        "us_licensed": True,
        "waiver": False,
    },
    "Project Kuiper (Amazon)": {
        "name": "Kuiper Constellation",
        "operator": "Kuiper Systems LLC (Amazon)",
        "orbit_type": "LEO",
        "altitude": 590.0,
        "inclination": 51.9,
        "num_auth": 3236,
        "num_dep": 2,
        "dimension": 80.0,
        "mass": 600.0,
        "lifetime": 7.0,
        "has_prop": True,
        "deorbit_yrs": 2.0,
        "in_pr": True,
        "fed_bands": False,
        "foreign_pct": 0.0,
        "us_licensed": True,
        "waiver": False,
    },
    "NASA PACE (Science)": {
        "name": "NASA PACE",
        "operator": "National Aeronautics and Space Administration",
        "orbit_type": "LEO",
        "altitude": 676.5,
        "inclination": 98.0,
        "num_auth": 1,
        "num_dep": 1,
        "dimension": 150.0,
        "mass": 1694.0,
        "lifetime": 3.0,
        "has_prop": True,
        "deorbit_yrs": 4.2,
        "in_pr": False,
        "fed_bands": True,
        "foreign_pct": 0.0,
        "us_licensed": True,
        "waiver": False,
    },
    "Flock SuperDove (Planet)": {
        "name": "Flock SuperDove Constellation",
        "operator": "Planet Labs PBC",
        "orbit_type": "LEO",
        "altitude": 500.0,
        "inclination": 97.5,
        "num_auth": 120,
        "num_dep": 80,
        "dimension": 10.0,
        "mass": 5.5,
        "lifetime": 3.0,
        "has_prop": False,
        "deorbit_yrs": 3.5,
        "in_pr": False,
        "fed_bands": False,
        "foreign_pct": 0.0,
        "us_licensed": True,
        "waiver": False,
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="main-header">
    <h1>🛰️ OrbitFlow Regulatory &amp; ODAR Engine</h1>
    <p>FCC Part 25 → Part 100 Transition Readiness, Document Intelligence &amp; NASA DAS Debris Assessment</p>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR — DOCUMENT INGESTION, TELEMETRY & PRESETS
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 📄 Document Intelligence (Module 4)")
    st.caption("Upload technical specs (PDF, CSV, TXT) for instant Schedule O/F extraction.")
    uploaded_file = st.file_uploader("Upload Spec Sheet", type=["pdf", "txt", "csv", "md"])

    if uploaded_file is not None:
        try:
            doc_engine = get_doc_engine()
            file_bytes = uploaded_file.read()
            if uploaded_file.name.lower().endswith(".pdf"):
                parsed_doc = DocumentParser.parse_pdf_bytes(file_bytes, uploaded_file.name)
            else:
                text_content = file_bytes.decode("utf-8", errors="replace")
                parsed_doc = DocumentParser.parse_text(text_content, uploaded_file.name)

            ext_result = doc_engine.extract_from_document(parsed_doc)
            st.session_state["doc_extraction"] = ext_result

            # Populate session state from extracted fields with Tiered Confidence Gating
            o = ext_result.schedule_o
            
            def _safe_assign(field_obj, state_key, type_cast, min_val=None, max_val=None):
                if not field_obj:
                    return
                # Only auto-accept high confidence (>= 85%)
                if field_obj.confidence < 0.85:
                    st.warning(f"⚠️ {state_key}: Extracted '{field_obj.extracted_value}' with low confidence ({field_obj.confidence*100:.0f}%). Ignored.")
                    return
                
                try:
                    val = type_cast(field_obj.extracted_value)
                    # Physical sanity bounds
                    if min_val is not None and val < min_val:
                        st.warning(f"⚠️ {state_key}: {val} is physically implausible (min {min_val}). Ignored.")
                        return
                    if max_val is not None and val > max_val:
                        st.warning(f"⚠️ {state_key}: {val} is physically implausible (max {max_val}). Ignored.")
                        return
                    st.session_state[state_key] = val
                except ValueError:
                    st.warning(f"⚠️ {state_key}: Could not parse '{field_obj.extracted_value}'. Ignored.")

            _safe_assign(o.system_name, "name", str)
            _safe_assign(o.altitude_km, "altitude", float, 100.0, 500000.0)
            _safe_assign(o.inclination_deg, "inclination", float, 0.0, 180.0)
            _safe_assign(o.mass_kg, "mass", float, 0.1, 50000.0)
            _safe_assign(o.smallest_dimension_cm, "dimension", float, 1.0, 10000.0)
            _safe_assign(o.num_satellites, "num_auth", int, 1, 100000)
            
            # Booleans
            if o.has_propulsion and o.has_propulsion.confidence >= 0.85:
                st.session_state["has_prop"] = bool(o.has_propulsion.extracted_value)
            
            _safe_assign(o.estimated_deorbit_years, "deorbit_yrs", float, 0.1, 100.0)

            st.success(f"Extracted {len(ext_result.all_fields)} fields (Overall Confidence: {ext_result.confidence_score*100:.0f}%)")
        except Exception as e:
            st.error(f"Doc Intel Error: {e}")

    st.markdown("---")
    st.markdown("### 🌐 Live Autonomous Telemetry")
    live_norad_input = st.text_input("NORAD ID / Sat Name", value="44714", help="e.g. 44714 (Starlink), 25544 (ISS), 58926 (PACE)")
    fetch_live_btn = st.button("📡 Query Live Telemetry", use_container_width=True)

    st.markdown("---")
    st.markdown("### 🚀 Verified Spacecraft Presets")
    selected_preset = st.selectbox("Load Real Fleet Spec", options=["Custom"] + list(REAL_PRESETS.keys()))

    defaults = REAL_PRESETS.get(selected_preset, REAL_PRESETS["Starlink Gen2 (SpaceX)"])

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_live_telemetry_cached(identifier: str):
        client = get_space_client()
        return client.fetch_live_satellite_telemetry(identifier)
        
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_live_weather_cached():
        client = get_space_client()
        return client.fetch_live_space_weather()

    if fetch_live_btn and live_norad_input:
        with st.spinner("Connecting to CelesTrak GP & NOAA SWPC APIs..."):
            try:
                space_client = get_space_client()
                telem = get_live_telemetry_cached(live_norad_input)
                weather = get_live_weather_cached()
                st.session_state["live_telem"] = telem
                st.session_state["live_weather"] = weather
                st.session_state["name"] = f"{telem.name} (NORAD #{telem.norad_cat_id})"
                st.session_state["operator"] = f"COSPAR ID: {telem.cospar_id}"
                st.session_state["orbit_type"] = telem.orbit_type.value
                st.session_state["altitude"] = float(telem.mean_altitude_km)
                st.session_state["inclination"] = float(telem.inclination_deg)
                st.session_state["deorbit_yrs"] = space_client.estimate_deorbit_lifetime(
                    telem.mean_altitude_km, telem.bstar_drag_term, True, weather
                )
                st.success(f"Loaded {telem.name}!\n\n**Data Provenance:** {telem.status_badge}")
            except Exception as e:
                st.error(f"Live Telemetry Error: {e}")

    if "live_telem" in st.session_state:
        lt = st.session_state["live_telem"]
        st.info(f"**Active Telemetry:** {lt.name} (NORAD #{lt.norad_cat_id})  \n**Tier:** {lt.status_badge}")


    st.markdown("---")
    st.markdown("### ⚙️ Satellite Specifications")

    name = st.text_input(
        "System Name",
        value=st.session_state.get("name", defaults["name"]),
        help="Satellite system or constellation name",
    )
    operator = st.text_input(
        "Operator Legal Name",
        value=st.session_state.get("operator", defaults["operator"]),
    )

    orbit_type_val = st.selectbox(
        "Orbit Type (§ 100.3)",
        options=[e.value for e in OrbitType],
        index=[e.value for e in OrbitType].index(st.session_state.get("orbit_type", defaults["orbit_type"])),
    )
    altitude = st.number_input(
        "Altitude (km)",
        min_value=100.0,
        max_value=500000.0,
        value=float(st.session_state.get("altitude", defaults["altitude"])),
        step=25.0,
    )
    inclination = st.number_input(
        "Inclination (°)",
        min_value=0.0,
        max_value=180.0,
        value=float(st.session_state.get("inclination", defaults["inclination"])),
        step=1.0,
    )

    num_auth = st.number_input("Authorized Satellites (A)", min_value=0, value=int(st.session_state.get("num_auth", defaults["num_auth"])), step=10)
    num_dep = st.number_input("Deployed Satellites (D)", min_value=0, value=int(defaults["num_dep"]), step=10)

    dimension = st.number_input(
        "Smallest Dimension (cm)",
        min_value=0.1,
        max_value=10000.0,
        value=float(st.session_state.get("dimension", defaults["dimension"])),
        step=5.0,
        help="Trackability minimum: ≥10cm (LEO) / ≥1m (>2000km)",
    )
    mass = st.number_input("Wet Mass (kg)", min_value=0.1, max_value=100000.0, value=float(st.session_state.get("mass", defaults["mass"])), step=25.0)
    lifetime = st.number_input("Design Lifetime (years)", min_value=0.1, max_value=50.0, value=float(defaults["lifetime"]), step=0.5)

    has_prop = st.checkbox("Has Active Propulsion System", value=st.session_state.get("has_prop", defaults["has_prop"]))
    deorbit_yrs = st.number_input(
        "Estimated De-orbit Time (years)",
        min_value=0.1,
        max_value=100.0,
        value=float(st.session_state.get("deorbit_yrs", defaults["deorbit_yrs"])),
        step=0.5,
        help="Part 100 § 100.260(e) requires ≤ 5 years for LEO",
    )

    st.markdown("#### Regulatory Flags")
    in_pr = st.checkbox("Opt into Processing Round", value=defaults["in_pr"], help="Subject to § 100.148(d) $10M bond")
    fed_bands = st.checkbox("Shared Federal Bands Requested", value=defaults["fed_bands"], help="Shared NTIA coordination")
    foreign_pct = st.number_input("Foreign Ownership (%)", min_value=0.0, max_value=100.0, value=float(defaults["foreign_pct"]), step=1.0)
    us_licensed = st.checkbox("U.S. Licensed Operator", value=defaults["us_licensed"])
    waiver = st.checkbox("Waiver Requested", value=defaults["waiver"])

    st.markdown("---")
    run_btn = st.button("🚀 Run FCC Part 100 & ODAR Audit", type="primary", use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# MAIN AREA — REAL-TIME METRICS & AUDIT RESULTS
# ═══════════════════════════════════════════════════════════════════════════

# Display live space weather banner if available
if "live_weather" in st.session_state:
    w = st.session_state["live_weather"]
    st.markdown(f"""
    <div class="live-badge">
        ☀️ <strong>LIVE NOAA SPACE WEATHER:</strong> Penticton F10.7 Solar Radio Flux = <strong>{w.f107_solar_flux} sfu</strong> ({w.solar_activity_level}) | Thermospheric Drag Factor = <strong>{w.thermospheric_drag_multiplier}x</strong>
    </div>
    """, unsafe_allow_html=True)

if run_btn:
    try:
        spec = SatelliteSpec(
            name=name,
            operator_name=operator,
            orbit_type=OrbitType(orbit_type_val),
            altitude_km=altitude,
            inclination_deg=inclination,
            num_authorized=num_auth,
            num_deployed=num_dep,
            smallest_dimension_cm=dimension,
            mass_kg=mass,
            mission_lifetime_years=lifetime,
            has_propulsion=has_prop,
            estimated_deorbit_years=deorbit_yrs,
            in_processing_round=in_pr,
            federal_bands_requested=fed_bands,
            foreign_ownership_pct=foreign_pct,
            is_us_licensed=us_licensed,
            waiver_requested=waiver,
        )
    except Exception as e:
        st.error(f"❌ Input Validation Error: {e}")
        st.stop()

    with st.spinner("Evaluating against FCC Part 100 & Running NASA DAS Physics Simulation..."):
        result = run_delta_audit(spec)
        st.session_state["audit_result"] = result
        st.session_state["audit_spec"] = spec

if "audit_result" in st.session_state:
    result = st.session_state["audit_result"]
    spec = st.session_state["audit_spec"]

    st.success(f"✅ Audit Complete — Official Report ID: **{result.report_id}**")

    # ── Top KPI Bar ──
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("✅ Passed Certs", result.pass_count)
    col2.metric("❌ Failed Certs", result.fail_count)
    col3.metric("⚠️ Attestation Needed", result.insufficient_count)
    col4.metric("🔍 Reviews Triggered", sum(1 for r in result.targeted_reviews if r.triggered))
    col5.metric("💰 Part 100 Bond", f"${result.bond_delta.part_100_bond_usd:,}")

    st.markdown("---")

    # ── Tabs ──
    tab_delta, tab_odar, tab_spectrum, tab_filing, tab_itu, tab_es, tab_bond, tab_certs, tab_reviews, tab_strategy, tab_pdf = st.tabs([
        "📊 Part 25 vs 100 Delta",
        "🛰️ ODAR Debris Physics (Mod 9)",
        "📡 Spectrum & EPFD Physics (Mod 10)",
        "📦 FCC Part 100 Filing Package (Mod 11)",
        "🌐 ITU Filing Package (Mod 12)",
        "📡 Earth Station Schedule B (Mod 19)",
        "💰 Surety Bond & Milestones",
        "🔬 Certification Matrix",
        "🔍 7 Targeted Reviews",
        "📋 Filing Strategy",
        "📄 Law-Firm PDF Report",
    ])


    # ── TAB 1: Delta Matrix ──
    with tab_delta:
        st.subheader("Regulatory Regime Delta Analysis")
        delta_table = [
            {"Regulatory Dimension": "Governing Rule Part", "Part 25 (Legacy)": "47 CFR Part 25", "Part 100 (Adopted)": "Part 100 (Space & Earth Station Services)", "Impact Level": "STRUCTURAL"},
            {"Regulatory Dimension": "Application Architecture", "Part 25 (Legacy)": "Form 312 + Schedule S", "Part 100 (Adopted)": "Form 312 Main + Sched O/F/B", "Impact Level": "HIGH"},
            {"Regulatory Dimension": "Review Methodology", "Part 25 (Legacy)": "Bespoke narrative review", "Part 100 (Adopted)": "Certification-based 'Default to Yes'", "Impact Level": "EXPEDITION"},
            {"Regulatory Dimension": "Public Notice Window", "Part 25 (Legacy)": "30 Days", "Part 100 (Adopted)": "15 Days (Single Period)", "Impact Level": "50% FASTER"},
            {"Regulatory Dimension": "License Term", "Part 25 (Legacy)": result.license_term_part_25, "Part 100 (Adopted)": result.license_term_part_100, "Impact Level": "+33% DURATION"},
            {"Regulatory Dimension": "Surety Bond Requirement", "Part 25 (Legacy)": f"${result.bond_delta.part_25_bond_usd:,}", "Part 100 (Adopted)": f"${result.bond_delta.part_100_bond_usd:,}", "Impact Level": "CAPITAL RELIEF"},
            {"Regulatory Dimension": "Post-Mission De-orbit", "Part 25 (Legacy)": "25-year rule", "Part 100 (Adopted)": "5-year rule (§ 100.260(e))", "Impact Level": "STRICT GUILLOTINE"},
            {"Regulatory Dimension": "Trackability Obligation", "Part 25 (Legacy)": "Statement only", "Part 100 (Adopted)": "≥10cm LEO / ≥1m >2000km", "Impact Level": "AFFIRMATIVE"},
        ]
        st.dataframe(pd.DataFrame(delta_table), use_container_width=True, hide_index=True)

    # ── TAB 2: ODAR Debris Physics (Module 9) ──
    with tab_odar:
        st.subheader("Orbital Debris Assessment Report (NASA DAS Equivalent)")
        if result.odar_report:
            rep = result.odar_report
            if rep.all_debris_requirements_met:
                st.success(f"🟢 **ODAR STATUS: COMPLIANT** — {rep.summary_verdict}")
            else:
                st.error(f"🔴 **ODAR STATUS: DEFICIENT** — {rep.summary_verdict}")

            # Top Metrics Cards
            oc1, oc2, oc3, oc4 = st.columns(4)
            oc1.metric(
                "Natural Orbital Decay",
                f"{rep.orbital_lifetime.natural_decay_years:.1f} yrs",
                delta="≤ 5.0 yr rule" if rep.orbital_lifetime.compliant_with_5_year_rule else "Exceeds Limit",
                delta_color="normal" if rep.orbital_lifetime.compliant_with_5_year_rule else "inverse",
            )
            oc2.metric(
                "Small Debris Risk (≥1mm)",
                f"{rep.collision_probability.small_debris_collision_prob:.5f}",
                delta="≤ 0.01 threshold" if rep.collision_probability.small_debris_compliant else "Exceeds Limit",
                delta_color="normal" if rep.collision_probability.small_debris_compliant else "inverse",
            )
            oc3.metric(
                "Large Object Risk (≥10cm)",
                f"{rep.collision_probability.large_object_collision_prob_with_maneuver:.6f}",
                delta="≤ 0.001 threshold" if rep.collision_probability.large_object_compliant else "Exceeds Limit",
                delta_color="normal" if rep.collision_probability.large_object_compliant else "inverse",
            )
            oc4.metric(
                "Casualty Expectation (Ec)",
                f"{rep.casualty_risk.human_casualty_expectation:.2e}",
                delta="≤ 1:10,000" if rep.casualty_risk.casualty_risk_compliant else "Exceeds Limit",
                delta_color="normal" if rep.casualty_risk.casualty_risk_compliant else "inverse",
            )

            st.markdown("---")

            # RK4 Decay Curve Line Chart
            st.markdown("#### 📉 Runge-Kutta 4th Order (RK4) Orbital Decay Simulation")
            if rep.orbital_lifetime.decay_timeline_points:
                decay_df = pd.DataFrame(
                    rep.orbital_lifetime.decay_timeline_points,
                    columns=["Years Elapsed", "Altitude (km)"],
                ).set_index("Years Elapsed")
                st.line_chart(decay_df)

            st.markdown("---")
            # Debris Aerothermal Demise Table
            st.markdown("#### 🔬 Re-entry Aerothermal Demise & Surviving Fragment Inventory")
            frag_rows = []
            for f in rep.casualty_risk.fragments:
                frag_rows.append({
                    "Component": f.component_name,
                    "Material": f.material.value,
                    "Mass (kg)": f"{f.mass_kg:.2f}",
                    "Demise Alt (km)": f"{f.demise_altitude_km:.1f}" if f.demise_altitude_km else "SURVIVES TO SURFACE",
                    "Impact Velocity": f"{f.terminal_velocity_mps:.1f} m/s" if f.survives_to_surface else "N/A (Demised)",
                    "Impact Energy (J)": f"{f.impact_kinetic_energy_joules:,.0f} J" if f.survives_to_surface else "0 J",
                    "Casualty Area": f"{f.casualty_area_m2:.2f} m²" if f.survives_to_surface else "0 m²",
                })
            st.dataframe(pd.DataFrame(frag_rows), use_container_width=True, hide_index=True)

            st.markdown("---")
            # Passivation Checklist
            st.markdown("#### 🔋 Passivation & Stored Energy Removal Audit (§ 100.111(c)(2)(viii))")
            p1, p2, p3, p4 = st.columns(4)
            p1.checkbox("Propellant Venting", value=rep.stored_energy.propellant_depletion_passivation, disabled=True)
            p2.checkbox("Battery Disconnect", value=rep.stored_energy.battery_passivation, disabled=True)
            p3.checkbox("Pressurant Relieved", value=rep.stored_energy.pressurant_depletion, disabled=True)
            p4.checkbox("Momentum Wheels Spun Down", value=rep.stored_energy.reaction_wheel_spin_down, disabled=True)

    # ── TAB 3: Spectrum & EPFD Physics (Module 10) ──
    with tab_spectrum:
        st.subheader("RF Spectrum Sharing & EPFD Interference Audit (§§ 100.212, 100.222, 100.280)")
        if result.spectrum_report:
            srep = result.spectrum_report
            if srep.all_spectrum_requirements_met:
                st.success(f"🟢 **SPECTRUM STATUS: COMPLIANT** — {srep.summary_verdict}")
            else:
                st.error(f"🔴 **SPECTRUM STATUS: DEFICIENT** — {srep.summary_verdict}")

            # Top Spectrum Metrics
            sc1, sc2, sc3 = st.columns(3)
            min_pfd_margin = min((p.min_margin_db for p in srep.pfd_analysis), default=0.0)
            sc1.metric(
                "Min PFD Mask Margin (§ 100.212)",
                f"{min_pfd_margin:+.2f} dB",
                delta="Compliant" if min_pfd_margin >= 0 else "Exceeds Mask",
                delta_color="normal" if min_pfd_margin >= 0 else "inverse",
            )
            if srep.epfd_downlink_analysis:
                sc2.metric(
                    "Aggregate EPFDdown Margin",
                    f"{srep.epfd_downlink_analysis.margin_db:+.2f} dB",
                    delta="ITU Art. 22 Pass" if srep.epfd_downlink_analysis.compliant else "Exceeds Limit",
                    delta_color="normal" if srep.epfd_downlink_analysis.compliant else "inverse",
                )
            if srep.off_axis_eirp_analysis:
                sc3.metric(
                    "2° Off-Axis EIRP Density (§ 100.280)",
                    f"{srep.off_axis_eirp_analysis.actual_eirp_density_dbw:.1f} dBW",
                    delta="2° Spacing Pass" if srep.off_axis_eirp_analysis.two_degree_spacing_compliant else "Exceeds Mask",
                    delta_color="normal" if srep.off_axis_eirp_analysis.two_degree_spacing_compliant else "inverse",
                )

            st.markdown("---")
            # Frequency Channel Roster
            st.markdown("#### 📡 Authorized Frequency Assignments & Emission Designators")
            ch_rows = []
            for ch in srep.channels_analyzed:
                ch_rows.append({
                    "Channel ID": ch.channel_id,
                    "Direction": ch.direction.value,
                    "Band": ch.band.value,
                    "Center Freq (MHz)": f"{ch.center_frequency_mhz:,.1f}",
                    "Bandwidth (MHz)": f"{ch.bandwidth_mhz:,.1f}",
                    "Emission Designator": ch.emission_designator,
                    "Max EIRP (dBW)": f"{ch.max_eirp_dbw:.1f}",
                    "EIRP Density (dBW/MHz)": f"{ch.max_eirp_density_dbw_mhz:.1f}",
                    "Shared Federal": "YES (NTIA Coord)" if ch.is_shared_federal_band else "No",
                })
            st.dataframe(pd.DataFrame(ch_rows), use_container_width=True, hide_index=True)

            # PFD Mask Evaluation Curves
            st.markdown("---")
            st.markdown("#### 📈 Power Flux Density (PFD) Mask Analysis vs Arrival Angle (δ)")
            for pfd_res in srep.pfd_analysis:
                st.markdown(f"**Channel:** `{pfd_res.band.value}` ({pfd_res.center_frequency_ghz:.2f} GHz) — Mask: `{pfd_res.mask_type.value}`")
                pfd_df = pd.DataFrame([
                    {
                        "Elevation Angle (deg)": pt.elevation_deg,
                        "Calculated PFD (dBW/m²/MHz)": pt.pfd_calculated_dbw_m2_mhz,
                        "Statutory Limit (dBW/m²/MHz)": pt.pfd_limit_dbw_m2_mhz,
                    }
                    for pt in pfd_res.data_points
                ]).set_index("Elevation Angle (deg)")
                st.line_chart(pfd_df)

            # EPFD Breakdown Table
            if srep.epfd_downlink_analysis:
                st.markdown("---")
                st.markdown(f"#### 🛰️ ITU Article 22 Aggregate EPFDdown Satellite Breakdown ({srep.epfd_downlink_analysis.details})")
                epfd_rows = []
                for entry in srep.epfd_downlink_analysis.satellite_breakdown:
                    epfd_rows.append({
                        "Satellite": entry.satellite_id,
                        "Sub-Sat Lat/Lon": f"{entry.sub_satellite_lat:+.1f}°, {entry.sub_satellite_lon:+.1f}°",
                        "Slant Range": f"{entry.slant_range_km:.0f} km",
                        "Off-Axis θ": f"{entry.off_axis_angle_deg:.1f}°",
                        "Victim Gain": f"{entry.victim_antenna_gain_dbi:.1f} dBi",
                        "Weighted PFD (W/m²/BW)": f"{entry.weighted_pfd_w_m2_bw:.2e}",
                    })
                st.dataframe(pd.DataFrame(epfd_rows), use_container_width=True, hide_index=True)

    # ── TAB 4: FCC Part 100 Filing Package (Module 11) ──
    with tab_filing:
        st.subheader("Submission-Ready FCC Part 100 Legal Filing Package (§§ 100.101, 100.111, 100.112)")
        if result.filing_package:
            fp = result.filing_package
            st.success(f"📦 **PACKAGE ID:** `{fp.package_id}` — {fp.summary_verdict}")

            # Download XML payloads
            st.markdown("#### 📥 Direct XML Submission Artifacts")
            xc1, xc2, xc3, xc4 = st.columns(4)
            xc1.download_button(
                "📄 Form 312 Main XML",
                data=fp.form_312_xml,
                file_name=f"Form_312_Main_{spec.name}.xml",
                mime="application/xml",
                use_container_width=True,
            )
            xc2.download_button(
                "🛰️ Schedule O XML",
                data=fp.schedule_o_xml,
                file_name=f"Schedule_O_{spec.name}.xml",
                mime="application/xml",
                use_container_width=True,
            )
            xc3.download_button(
                "📡 Schedule F XML",
                data=fp.schedule_f_xml,
                file_name=f"Schedule_F_{spec.name}.xml",
                mime="application/xml",
                use_container_width=True,
            )
            xc4.download_button(
                "📦 Master Package XML",
                data=fp.master_combined_xml,
                file_name=f"Master_Part100_Filing_{spec.name}.xml",
                mime="application/xml",
                use_container_width=True,
            )

            st.markdown("---")
            # Narrative Legal Exhibits
            st.markdown("#### 📑 Attorney Narrative Exhibits & Transmittal Documents")
            with st.expander("📝 Official Transmittal Cover Letter to Space Bureau Secretary"):
                st.markdown(fp.transmittal_letter_text)
            with st.expander("🏛️ Exhibit 1: Form 312 Legal & Ownership Statement (§ 100.101)"):
                st.markdown(fp.form_312_narrative_exhibit)
            with st.expander("🛰️ Exhibit 2: Schedule O Orbital & ODMP Statement (§ 100.111 / § 100.260)"):
                st.markdown(fp.schedule_o_narrative_exhibit)
            with st.expander("📡 Exhibit 3: Schedule F Radio Frequency Spectrum Statement (§ 100.112)"):
                st.markdown(fp.schedule_f_narrative_exhibit)
            with st.expander("🌐 Exhibit 4: Public Interest Statement (47 U.S.C. § 309(a))"):
                st.markdown(fp.public_interest_statement)

            st.markdown("---")
            # Cryptographic SHA-256 Manifest
            st.markdown("#### 🔒 Cryptographic SHA-256 Audit Manifest")
            sha_rows = [{"Document Artifact": k, "SHA-256 Checksum": v} for k, v in fp.manifest_checksums_sha256.items()]
            st.dataframe(pd.DataFrame(sha_rows), use_container_width=True, hide_index=True)

    # ── TAB 10: ITU Filing Package (Module 12) ──
    with tab_itu:
        st.subheader("🌐 ITU Satellite Network Filing Package (Module 12)")
        st.caption("ITU Radio Regulations Appendix 4 (Annex 2B/2C), Article 9 Coordination, & 47 CFR § 100.115 Compliance")
        if result.itu_package:
            itu = result.itu_package
            ic1, ic2, ic3, ic4 = st.columns(4)
            ic1.metric("ITU Notice Type", itu.notice_type.value)
            ic2.metric("Orbit Classification", itu.orbit_type.value)
            ic3.metric("Validation Status", itu.validation_status)
            clock_info = itu.two_year_clock_status
            ic4.metric(
                "2-Year Clock (§ 100.115)",
                f"{clock_info.get('days_remaining', 730)} days left" if clock_info.get("clock_active") else clock_info.get("status", "OK"),
            )

            if itu.is_fully_compliant:
                st.success("🟢 **ITU APPENDIX 4 COMPLIANT** — All frequency groupings, PFD limits, and Article 5 allocations verified.")
            else:
                st.warning("⚠️ **ITU FILING DEFICIENCIES** — Check carrier frequency allocations or station class codes.")

            # ITU Group Table
            st.markdown("#### 🛰️ Radiocommunication Bureau Frequency Groups (`grp`)")
            grp_rows = []
            for g in itu.groups_formed:
                grp_rows.append({
                    "Group ID": f"GRP-{g.grp_id:02d}",
                    "Beam ID": g.beam_id,
                    "Direction": "Space-to-Earth (DL)" if g.direction == "E" else "Earth-to-Space (UL)",
                    "Station Class": g.station_class,
                    "Polarization": g.polarization,
                    "Max EIRP (dBW)": f"{g.eirp_max_dbw:.1f}",
                    "Max PSD (dBW/Hz)": f"{g.psd_max_dbw_hz:.1f}",
                    "Frequency Count": len(g.carrier_frequencies),
                    "Emissions": ", ".join(g.emissions),
                })
            st.dataframe(pd.DataFrame(grp_rows), use_container_width=True, hide_index=True)

            # SpaceCap XML Exporter
            st.markdown("#### 💾 SpaceCap / BR IFIC XML Electronic Notification")
            st.download_button(
                "⬇️ Download ITU SpaceCap XML Package",
                data=itu.spacecap_xml,
                file_name=f"ITU_SpaceCap_{itu.satellite_name}.xml",
                mime="application/xml",
                use_container_width=True,
            )
            with st.expander("📄 View SpaceCap Electronic XML Schema"):
                st.code(itu.spacecap_xml, language="xml")

    # ── TAB 11: Earth Station Schedule B (Module 19) ──
    with tab_es:
        st.subheader("📡 Earth Station Nationwide Non-Site Engine (Module 19)")
        st.caption("47 CFR § 100.120 (Nationwide Non-Site License) & § 100.121 (Site Registration within 365d BIU)")
        if result.earth_station_package:
            esp = result.earth_station_package
            ec1, ec2, ec3, ec4 = st.columns(4)
            ec1.metric("Lead License Call Sign", esp.license_callsign)
            ec2.metric("365-Day BIU Deadline", esp.biu_deadline.isoformat())
            ec3.metric("Rain-Faded Eb/N0 Margin", f"{esp.link_budget.link_margin_rain_db:.1f} dB", delta="Link Closed" if esp.link_budget.is_link_closed else "Link Margin Deficit")
            ec4.metric("Pre-Grant Operations", "AUTHORIZED" if esp.pre_grant_status.is_authorized_pre_grant else "PENDING")

            st.markdown("---")
            # RF Propagation & G/T Thermodynamics
            st.markdown("#### 🔬 RF Thermodynamics & Atmospheric Attenuation (ITU-R P.618 / P.676)")
            lb = esp.link_budget
            lcol1, lcol2, lcol3, lcol4 = st.columns(4)
            lcol1.metric("Free Space Loss (19.7 GHz)", f"{lb.free_space_loss_db:.1f} dB")
            lcol2.metric("Gaseous Absorption (P.676)", f"{lb.atmospheric_loss_db:.2f} dB")
            lcol3.metric("Rain Attenuation (P.618)", f"{lb.rain_attenuation_db:.2f} dB")
            lcol4.metric("Antenna G/T (Rain-Faded)", f"{lb.rain_faded_g_t_db_k:.1f} dB/K")

            # Registered Sites Registry
            st.markdown("#### 📍 Immovable Earth Station Site Registrations (§ 100.121)")
            site_rows = []
            for s in esp.registered_sites:
                site_rows.append({
                    "Site ID": s.site_id,
                    "Site Name": s.site_name,
                    "Classification": s.classification.value,
                    "Coordinates": f"{s.latitude_deg:.4f}°, {s.longitude_deg:.4f}°",
                    "Elevation AMSL": f"{s.site_elevation_amsl_m} m",
                    "Antenna Count": len(s.antennas),
                    "Prior PCN Status": "COMPLETED" if s.pcn_completed_no_conflicts else "PENDING",
                    "BIU Clock Status": s.biu_status.value,
                })
            st.dataframe(pd.DataFrame(site_rows), use_container_width=True, hide_index=True)

            # Schedule B XML Exporter
            st.markdown("#### 💾 FCC Form 312 Schedule B XML Electronic Export")
            st.download_button(
                "⬇️ Download Form 312 Schedule B XML",
                data=esp.schedule_b_xml,
                file_name=f"Schedule_B_{esp.license_callsign}.xml",
                mime="application/xml",
                use_container_width=True,
            )
            with st.expander("📄 View Form 312 Schedule B XML Document"):
                st.code(esp.schedule_b_xml, language="xml")

    # ── TAB 5: Bond & Milestones ──
    with tab_bond:
        st.subheader("Surety Bond Analysis (§ 100.148(d))")
        bcol1, bcol2, bcol3 = st.columns(3)
        bcol1.metric("Legacy Part 25 Bond", f"${result.bond_delta.part_25_bond_usd:,}")
        bcol2.metric("Adopted Part 100 Bond", f"${result.bond_delta.part_100_bond_usd:,}")
        savings = result.bond_delta.part_25_bond_usd - result.bond_delta.part_100_bond_usd
        bcol3.metric("Capital Delta", f"${abs(savings):,}", delta="Savings" if savings >= 0 else "PR Bond Surcharge", delta_color="normal" if savings >= 0 else "inverse")

        if spec.in_processing_round:
            st.info(f"📐 **De-escalation Formula:** `{result.bond_delta.part_100_formula}`  \n"
                    f"📊 **Current Deployment:** {result.bond_delta.deployment_pct}% ({spec.num_deployed}/{spec.num_authorized} authorized satellites)  \n"
                    f"🔓 **Full Bond Release Threshold:** {result.bond_delta.bond_relieved_at_pct}% deployment")
        else:
            st.success("✅ **Non-Processing Round Exemption:** Under Part 100, non-PR applicants are completely exempt from surety bond requirements ($0).")

        st.markdown("---")
        st.subheader("Statutory Milestone Schedule Comparison (§ 100.147)")
        mcol1, mcol2 = st.columns(2)
        with mcol1:
            st.markdown("#### Part 25 Milestones")
            for k, v in result.milestones_part_25.milestones.items():
                st.markdown(f"- **{k}:** {v}")
            if result.milestones_part_25.notes:
                st.caption(result.milestones_part_25.notes)
        with mcol2:
            st.markdown("#### Part 100 Milestones (Adopted)")
            for k, v in result.milestones_part_100.milestones.items():
                st.markdown(f"- **{k}:** {v}")
            if result.milestones_part_100.notes:
                st.caption(result.milestones_part_100.notes)

    # ── TAB 6: Certification Matrix ──
    with tab_certs:
        st.subheader("Schedule O & Schedule F Certification Readiness Matrix")
        for cert in result.certifications:
            if cert.status == CertStatus.PASS:
                icon, badge_color = "✅", "green"
            elif cert.status == CertStatus.FAIL:
                icon, badge_color = "❌", "red"
            elif cert.status == CertStatus.INSUFFICIENT_DATA:
                icon, badge_color = "⚠️", "orange"
            else:
                icon, badge_color = "➖", "gray"

            with st.expander(f"{icon} **{cert.cert_id}** — {cert.criterion} `{cert.section}`"):
                c1, c2 = st.columns(2)
                c1.markdown(f"**Evaluation Status:** :{badge_color}[{cert.status.value}]")
                if cert.value:
                    c1.markdown(f"**Measured Value:** `{cert.value}`")
                if cert.threshold:
                    c2.markdown(f"**Statutory Threshold:** `{cert.threshold}`")
                if cert.evidence:
                    c2.markdown(f"**Evidence Base:** {cert.evidence}")
                if cert.notes:
                    st.caption(cert.notes)

    # ── TAB 7: Targeted Reviews ──
    with tab_reviews:
        st.subheader("7 Targeted Review Categories Pre-Screen (§ 100.136(b))")
        st.markdown("Applications with zero triggered categories qualify for direct 15-day public notice grant.")

        for rev in result.targeted_reviews:
            if rev.triggered:
                st.error(f"🔴 **{rev.category.value}** — {rev.section}  \n**Trigger Detail:** {rev.details}  \n**Required Action:** {rev.action_required}")
            else:
                st.success(f"🟢 **{rev.category.value}** — {rev.section}  \n**Status:** Clear (No trigger)")

    # ── TAB 8: Filing Strategy ──
    with tab_strategy:
        st.subheader("Strategic Regulatory Counsel Memo")
        st.info(result.filing_strategy)

        if result.warnings:
            st.markdown("### ⚠️ Actionable Risk Flags")
            for w in result.warnings:
                st.warning(w)

        if result.missing_data:
            st.markdown("### 📋 Required Operator Attestations")
            for md in result.missing_data:
                st.markdown(f"- {md}")

    # ── TAB 9: PDF Download ──
    with tab_pdf:
        st.subheader("📄 Export Law-Firm-Grade Audit PDF")
        st.markdown("Generate a McKinsey-formatted **CONFIDENTIAL — ATTORNEY WORK PRODUCT** audit package.")
        
        @st.cache_data(show_spinner=False)
        def get_pdf_bytes(_res):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                pdf_path = generate_delta_report(_res, tmp.name)
            with open(pdf_path, "rb") as f:
                return f.read()

        with st.spinner("Compiling HTML template and rendering PDF via WeasyPrint..."):
            try:
                pdf_bytes = get_pdf_bytes(result)
                st.download_button(
                    label=f"⬇️ Download Official Report ({len(pdf_bytes) / 1024:.1f} KB)",
                    data=pdf_bytes,
                    file_name=f"OrbitFlow_Part100_Audit_{result.report_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
                st.success("✅ Audit PDF ready for download!")
            except Exception as e:
                st.error(f"PDF Rendering Error: {e}")
