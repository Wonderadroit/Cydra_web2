from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#245A81")
PALE_BLUE = colors.HexColor("#EAF2F8")
LIGHT = colors.HexColor("#F4F7FA")
MID = colors.HexColor("#D5DEE7")
INK = colors.HexColor("#243447")
MUTED = colors.HexColor("#5A6876")
GREEN = colors.HexColor("#24734D")
RED = colors.HexColor("#A33131")
AMBER = colors.HexColor("#8A5A00")


def _plain(value: object, default: str = "Not provided") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _p(value: object, style) -> Paragraph:
    return Paragraph(escape(_plain(value)).replace("\\n", "<br/>"), style)


def _status(report: dict) -> tuple[str, str, colors.Color]:
    summary = report.get("summary") or {}
    tests = report.get("tests") or report.get("results") or []
    statuses = [str(item.get("status") or item.get("observed") or "").upper() for item in tests]
    failed = int(summary.get("failed", summary.get("failed_expectations", 0)) or 0)
    inconclusive = int(summary.get("inconclusive", 0) or 0)
    if failed or "FAIL" in statuses or any(item == "ATTENTION REQUIRED" for item in statuses):
        return ("FAIL", "One or more checks failed. Review the evidence and reproduce before deciding whether this is a product defect.", RED)
    if inconclusive or "INCONCLUSIVE" in statuses:
        return ("INCONCLUSIVE", "The run could not reach a reliable verdict for at least one check. Resolve the execution blocker and rerun.", AMBER)
    benchmark_failures = int(summary.get("failed_expectations", 0) or 0)
    if "PASS" in statuses or (summary and (("passed" in summary and "total" in summary) or ("passed_expectations" in summary and "total_variants" in summary))):
        return ("PASS", "The reported checks met their expected outcomes in this run. This does not certify the entire application.", GREEN)
    if report.get("summary") and benchmark_failures == 0:
        return ("REVIEW", "A report was generated, but the result format did not provide enough information for an overall verdict.", AMBER)
    return ("INCONCLUSIVE", "There is not enough result data to assign a reliable overall verdict.", AMBER)


def _humanize(value: object) -> str:
    return str(value).replace("_", " ").strip().capitalize()


def render_report(source: Path, destination: Path) -> None:
    """Render a machine-readable CYDRA report into an executive-friendly PDF."""
    data = json.loads(source.read_text(encoding="utf-8"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                              textColor=NAVY, alignment=TA_CENTER, fontSize=23, leading=28, spaceAfter=8))
    styles.add(ParagraphStyle(name="Subtitle", parent=styles["Normal"], textColor=MUTED,
                              alignment=TA_CENTER, fontSize=10, leading=14, spaceAfter=10))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], textColor=NAVY,
                              fontSize=13, leading=16, spaceBefore=10, spaceAfter=5, keepWithNext=True))
    styles.add(ParagraphStyle(name="Subsection", parent=styles["Heading3"], textColor=BLUE,
                              fontSize=10, leading=13, spaceBefore=6, spaceAfter=3, keepWithNext=True))
    styles.add(ParagraphStyle(name="BodyReadable", parent=styles["BodyText"], textColor=INK,
                              fontSize=9.2, leading=13, spaceAfter=5))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], textColor=INK,
                              fontSize=7.4, leading=9.2))
    styles.add(ParagraphStyle(name="SmallWhite", parent=styles["BodyText"], textColor=colors.white,
                              fontSize=7.4, leading=9.2))
    styles.add(ParagraphStyle(name="Status", parent=styles["Heading2"], fontSize=15, leading=18,
                              textColor=colors.white, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Note", parent=styles["BodyText"], textColor=MUTED,
                              fontSize=8, leading=11, leftIndent=4, rightIndent=4))
    styles.add(ParagraphStyle(name="BulletReadable", parent=styles["BodyText"], textColor=INK,
                              fontSize=8.8, leading=12, leftIndent=12, firstLineIndent=-8, spaceAfter=3))

    status, explanation, status_color = _status(data)
    summary = data.get("summary") or {}
    tests = data.get("tests") or data.get("results") or []
    title = _plain(data.get("title"), "CYDRA Quality Assurance Report")
    target = _plain(data.get("target") or data.get("target_type"), "Not specified in source report")
    started = _plain(data.get("started_at_utc"), "Not recorded")
    ended = _plain(data.get("ended_at_utc"), "Not recorded")
    passed = summary.get("passed", summary.get("passed_expectations"))
    failed = summary.get("failed", summary.get("failed_expectations"))
    inconclusive = summary.get("inconclusive", 0)
    total = summary.get("total", summary.get("total_variants", len(tests)))
    if passed is None:
        passed = sum(str(item.get("status") or item.get("observed") or "").upper() == "PASS" for item in tests)
    if failed is None:
        failed = sum(str(item.get("status") or item.get("observed") or "").upper() == "FAIL" for item in tests)
    inconclusive = int(inconclusive or sum(str(item.get("status") or item.get("observed") or "").upper() == "INCONCLUSIVE" for item in tests))

    story = [
        Spacer(1, 8 * mm),
        Paragraph("CYDRA", styles["CoverTitle"]),
        Paragraph(escape(title), styles["Subtitle"]),
        Spacer(1, 2 * mm),
    ]
    status_box = Table([[Paragraph(status, styles["Status"])]], colWidths=[170 * mm], rowHeights=[13 * mm])
    status_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), status_color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, status_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([status_box, Spacer(1, 3 * mm), _p(explanation, styles["BodyReadable"]), Spacer(1, 2 * mm)])

    story.append(Paragraph("Executive summary", styles["Section"]))
    story.append(_p(
        f"This report summarizes {total} recorded check(s). It is designed to help a non-technical reader understand the overall outcome while preserving the evidence developers need to investigate. The detailed results below describe only the checks that were actually run.",
        styles["BodyReadable"]))
    metric_rows = [
        [Paragraph("TOTAL CHECKS", styles["SmallWhite"]), Paragraph("PASSED", styles["SmallWhite"]),
         Paragraph("FAILED", styles["SmallWhite"]), Paragraph("INCONCLUSIVE", styles["SmallWhite"])],
        [str(total), str(passed), str(failed), str(inconclusive)],
    ]
    metrics = Table(metric_rows, colWidths=[42.5 * mm] * 4, rowHeights=[8 * mm, 12 * mm])
    metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT),
        ("TEXTCOLOR", (0, 1), (-1, 1), INK),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 15),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, MID),
    ]))
    story.extend([metrics, Spacer(1, 3 * mm)])

    story.append(Paragraph("What this means", styles["Section"]))
    meaning_rows = [
        [Paragraph("Result", styles["SmallWhite"]), Paragraph("Plain-language meaning", styles["SmallWhite"]), Paragraph("Suggested next step", styles["SmallWhite"])],
        [Paragraph("PASS", styles["Small"]), Paragraph("The checks that ran behaved as expected.", styles["Small"]),
         Paragraph("Review coverage and limitations before accepting the application as ready.", styles["Small"])],
        [Paragraph("FAIL", styles["Small"]), Paragraph("A specific expected behavior did not happen.", styles["Small"]),
         Paragraph("Inspect the reproduction steps and evidence; confirm whether it is a product bug.", styles["Small"])],
        [Paragraph("INCONCLUSIVE", styles["Small"]), Paragraph("The test could not safely decide, often because of a timeout or environment issue.", styles["Small"]),
         Paragraph("Fix the blocker and rerun. Do not label this a confirmed defect.", styles["Small"])],
    ]
    meanings = Table(meaning_rows, colWidths=[27 * mm, 70 * mm, 73 * mm], repeatRows=1)
    meanings.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("GRID", (0, 0), (-1, -1), 0.35, MID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meanings)

    story.append(Paragraph("Run details", styles["Section"]))
    metadata = [
        ["Application / test target", target],
        ["Run started (UTC)", started],
        ["Run ended (UTC)", ended],
        ["Environment", _plain(data.get("environment"), "Not recorded")],
    ]
    meta = Table([[ _p(k, styles["Small"]), _p(v, styles["Small"])] for k, v in metadata],
                 colWidths=[48 * mm, 122 * mm])
    meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.35, MID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta)

    story.append(Paragraph("Detailed check results", styles["Section"]))
    rows = [[Paragraph("Check", styles["SmallWhite"]), Paragraph("Outcome", styles["SmallWhite"]),
             Paragraph("What happened / evidence", styles["SmallWhite"])]]
    for item in tests:
        name = item.get("name") or item.get("case") or item.get("id") or "Unnamed check"
        outcome = item.get("status") or item.get("observed") or ("PASS" if item.get("benchmark_pass") else "FAIL")
        details = item.get("assertion") or item.get("failure_category") or item.get("notes") or item.get("description") or "No detail provided."
        if isinstance(details, list):
            details = "; ".join(str(part) for part in details[:3]) or "No detail provided."
        rows.append([_p(name, styles["Small"]), _p(outcome, styles["Small"]), _p(details, styles["Small"])])
    if len(rows) == 1:
        rows.append([_p("No individual test entries were included in the source report.", styles["Small"]),
                     _p("INCONCLUSIVE", styles["Small"]), _p("The source report did not include test-level results.", styles["Small"])])
    detail_table = Table(rows, colWidths=[48 * mm, 25 * mm, 97 * mm], repeatRows=1, splitByRow=1)
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, MID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(detail_table)

    story.append(Paragraph("Technical notes", styles["Section"]))
    interpretation = data.get("interpretation") or data.get("method")
    if interpretation:
        story.append(_p(interpretation, styles["BodyReadable"]))
    env = data.get("environment") or {}
    if env:
        story.append(_p("Execution environment: " + json.dumps(env, ensure_ascii=False, sort_keys=True), styles["Small"]))
    if data.get("cases"):
        story.append(Paragraph("Benchmark scenarios", styles["Subsection"]))
        for case in data["cases"]:
            story.append(Paragraph("• " + escape(str(case.get("name", "Scenario"))) + ": " +
                                   escape(str(case.get("description", "No description supplied."))),
                                   styles["BulletReadable"]))

    limitations = data.get("limitations") or []
    if limitations:
        story.append(Paragraph("Limitations and scope", styles["Section"]))
        for item in limitations:
            story.append(Paragraph("• " + escape(str(item)), styles["BulletReadable"]))
    story.append(Paragraph("Evidence boundary", styles["Section"]))
    story.append(_p(
        "A passing automated check proves only that the specified assertion passed in the recorded test environment. "
        "A seeded-defect benchmark uses intentionally broken sample pages and is useful for validating the test harness; it is not a real customer finding. "
        "A failed assertion needs human review before it is reported as a confirmed product defect. An inconclusive run is not evidence that a defect exists or does not exist.",
        styles["BodyReadable"]))
    story.append(Paragraph("How to use this report", styles["Section"]))
    story.append(_p(
        "For product owners and non-technical readers: start with the overall status, summary counts, and “What this means.” "
        "For developers and QA engineers: use “Detailed check results,” technical notes, screenshots, and the accompanying JSON/Markdown artifacts to reproduce and diagnose behavior.",
        styles["BodyReadable"]))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(MID)
        canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 9 * mm, "CYDRA • Quality evidence, not a security certification")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(str(destination), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
                                 topMargin=16 * mm, bottomMargin=19 * mm, title=title,
                                 author="CYDRA QA", subject="Automated software quality assurance evidence")
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a plain-language and technical CYDRA QA report as a PDF.")
    parser.add_argument("--input", required=True, type=Path, help="Path to machine-readable report.json")
    parser.add_argument("--output", required=True, type=Path, help="Destination PDF path")
    args = parser.parse_args()
    render_report(args.input, args.output)
    print(f"PDF report written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
