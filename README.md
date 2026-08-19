# OrbitFlow

**FCC Part 100 Regulatory Engine for Satellite Licensing**

> Automated regulatory analysis for the new FCC Part 100 (Space and Earth Station Services, SB Docket 25-306).

---

## Quick Start (MVP)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch the Streamlit dashboard
streamlit run apps/mvp_streamlit/app.py
```

## What This Does

The **7-Day Sprint MVP** generates a **Part 25 → Part 100 Transition Readiness Assessment** — a $3,000 deliverable for space law firms:

1. Input satellite specifications via the Streamlit UI
2. Engine evaluates against BOTH Part 25 (current) AND Part 100 (adopted)
3. Generates a professional PDF report with:
   - Side-by-side regulatory delta matrix
   - Surety bond impact analysis
   - Deployment milestone comparison
   - Certification readiness heatmap (color-coded PASS/FAIL)
   - Targeted review category pre-screen
   - Filing strategy recommendation
   - Legal disclaimer

## Architecture

```
orbitflow/
├── apps/mvp_streamlit/    → Streamlit dashboard (MVP UI)
├── backend/app/
│   ├── models/            → Pydantic v2 data schemas
│   ├── engines/
│   │   ├── rules/         → YAML rule loader
│   │   └── delta/         → Delta audit engine
│   └── pdf_gen/           → WeasyPrint PDF generator
├── rules/                 → FCC Part 100 rules (YAML)
└── templates/             → Jinja2 HTML templates
```

## License

Proprietary — OrbitFlow Inc.

## ⚠️ Disclaimer

OrbitFlow is an assistive regulatory analysis tool. It does not provide legal advice, engineering certification, or regulatory compliance guarantees. All outputs require review by qualified legal counsel and licensed engineers.
