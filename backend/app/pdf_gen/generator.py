"""
OrbitFlow Enterprise PDF Generator
===================================

Renders the "Law-Firm-Grade" Delta & Certification Audit PDF using
Jinja2 HTML templates with a robust dual rendering pipeline:
1. Primary: WeasyPrint (when GTK/Cairo runtime is available)
2. Native Fallback: xhtml2pdf / ReportLab (100% pure Python, zero C-dependencies)

Produces a McKinsey-quality, audit-ready PDF with:
- CONFIDENTIAL - ATTORNEY WORK PRODUCT watermark
- KPI Summary Cards
- Part 25 vs Part 100 Delta Matrix
- Surety Bond De-escalation Table
- Milestone Timeline Delta
- Certification Readiness Heatmap
- 7 Targeted Review Category Pre-screen
- Filing Strategy Recommendation
- Full Legal & Regulatory Disclaimer
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from backend.app.core.config import TEMPLATES_DIR, get_logger
from backend.app.models.satellite import AuditResult, CertStatus

log = get_logger(__name__)


def _status_color(status: CertStatus) -> str:
    """Map certification status to a CSS hex color."""
    return {
        CertStatus.PASS: "#059669",              # emerald-600
        CertStatus.FAIL: "#DC2626",              # red-600
        CertStatus.INSUFFICIENT_DATA: "#D97706", # amber-600
        CertStatus.NOT_APPLICABLE: "#6B7280",    # gray-500
    }.get(status, "#6B7280")


def _status_bg(status: CertStatus) -> str:
    """Map certification status to a background CSS hex color."""
    return {
        CertStatus.PASS: "#ECFDF5",              # emerald-50
        CertStatus.FAIL: "#FEF2F2",              # red-50
        CertStatus.INSUFFICIENT_DATA: "#FFFBEB", # amber-50
        CertStatus.NOT_APPLICABLE: "#F9FAFB",    # gray-50
    }.get(status, "#F9FAFB")


def _status_label(status: CertStatus) -> str:
    """Human-friendly status label."""
    return {
        CertStatus.PASS: "PASS",
        CertStatus.FAIL: "FAIL",
        CertStatus.INSUFFICIENT_DATA: "DATA NEEDED",
        CertStatus.NOT_APPLICABLE: "N/A",
    }.get(status, str(status.value))


def generate_delta_report(
    analysis: AuditResult,
    output_path: str | Path,
) -> Path:
    """
    Render the Delta & Certification Audit report as a PDF.

    Parameters
    ----------
    analysis : AuditResult
        Complete audit output from ``run_delta_audit()``.
    output_path : str | Path
        Filesystem path where the PDF will be written.

    Returns
    -------
    Path
        The path to the generated PDF file.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Set up Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    env.filters["status_color"] = _status_color
    env.filters["status_bg"] = _status_bg
    env.filters["status_label"] = _status_label
    env.filters["currency"] = lambda v: f"${v:,.0f}" if isinstance(v, (int, float)) else str(v)

    template = env.get_template("delta_audit.html")

    # Render complete HTML
    html_content = template.render(
        report=analysis,
        spec=analysis.spec,
        bond=analysis.bond_delta,
        ms_25=analysis.milestones_part_25,
        ms_100=analysis.milestones_part_100,
        certs=analysis.certifications,
        reviews=analysis.targeted_reviews,
        CertStatus=CertStatus,
    )

    # Attempt WeasyPrint first
    pdf_rendered = False
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
        log.info("Rendering PDF with WeasyPrint...")
        HTML(string=html_content).write_pdf(str(output))
        pdf_rendered = True
        log.info("WeasyPrint rendering succeeded: %s (%.1f KB)", output, output.stat().st_size / 1024)
    except (ImportError, OSError) as err:
        log.info("WeasyPrint unavailable (%s), falling back to pure-Python xhtml2pdf engine...", err)

    if not pdf_rendered:
        try:
            from xhtml2pdf import pisa  # type: ignore[import-untyped]
            log.info("Rendering PDF with xhtml2pdf / ReportLab engine...")
            with open(output, "wb") as pdf_file:
                pisa_status = pisa.CreatePDF(html_content, dest=pdf_file)
                if pisa_status.err:
                    raise RuntimeError(f"xhtml2pdf error code: {pisa_status.err}")
            pdf_rendered = True
            log.info("xhtml2pdf rendering succeeded: %s (%.1f KB)", output, output.stat().st_size / 1024)
        except Exception as pisa_err:
            log.error("xhtml2pdf rendering failed: %s", pisa_err)
            raise RuntimeError(f"Failed to generate PDF with both engines: {pisa_err}") from pisa_err

    return output
