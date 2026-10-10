from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def para(value: object, style) -> Paragraph:
    return Paragraph(escape(str(value if value is not None else "—")).replace("\n", "<br/>"), style)


def render_report(source: Path, destination: Path) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=18, leading=22, spaceAfter=8))
    styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=7.5, leading=9))
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], spaceBefore=10, spaceAfter=5))
    story = [
        Paragraph(escape(str(data.get("title", "CYDRA QA Report"))), styles["ReportTitle"]),
        Paragraph("Evidence summary generated from the machine-readable QA run report.", styles["Normal"]),
        Spacer(1, 5 * mm),
    ]
    summary = data.get("summary", {})
    metadata = [
        ["Report field", "Value"],
        ["Target", str(data.get("target", "Controlled fixture / target not declared"))],
        ["Started (UTC)", str(data.get("started_at_utc", "—"))],
        ["Ended (UTC)", str(data.get("ended_at_utc", "—"))],
    ]
    for key, value in summary.items():
        metadata.append([str(key).replace("_", " ").title(), str(value)])
    table = Table([[para(cell, styles["SmallCell"]) for cell in row] for row in metadata], colWidths=[55 * mm, 115 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243447")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b7c1cc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f9")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([table, Paragraph("Test results", styles["SectionHeading"])])

    items = data.get("results") or data.get("tests") or []
    rows = [["Test / case", "Variant / status", "Outcome", "Evidence / notes"]]
    for item in items:
        name = item.get("case") or item.get("name") or item.get("id") or "Unnamed check"
        variant = item.get("variant") or item.get("status") or "—"
        outcome = item.get("observed") or item.get("status") or ("PASS" if item.get("benchmark_pass") else "FAIL")
        details = item.get("assertion") or item.get("failure_category") or "; ".join(item.get("notes", [])[:2]) or "—"
        rows.append([str(name), str(variant), str(outcome), str(details)])
    if len(rows) == 1:
        rows.append(["No test result entries were present in the source JSON.", "—", "INCONCLUSIVE", ""])
    result_table = Table([[para(cell, styles["SmallCell"]) for cell in row] for row in rows],
                         colWidths=[36 * mm, 31 * mm, 25 * mm, 78 * mm], repeatRows=1)
    result_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243447")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c7ced6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fa")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(result_table)

    interpretation = data.get("interpretation") or data.get("method")
    if interpretation:
        story.extend([Paragraph("Interpretation", styles["SectionHeading"]), para(interpretation, styles["BodyText"])])
    limitations = data.get("limitations", [])
    if limitations:
        story.append(Paragraph("Limitations", styles["SectionHeading"]))
        story.extend(Paragraph("• " + escape(str(item)), styles["BodyText"]) for item in limitations)

    story.extend([
        Spacer(1, 5 * mm),
        Paragraph(
            "Evidence boundary: a green controlled-fixture benchmark shows that the specified checks behaved as expected in this run. "
            "It does not, by itself, establish a production defect, a security vulnerability, or that an external customer application was tested.",
            styles["Italic"],
        ),
    ])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#66717d"))
        canvas.drawString(18 * mm, 10 * mm, "CYDRA QA evidence report")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(str(destination), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                                 topMargin=16 * mm, bottomMargin=18 * mm, title=str(data.get("title", "CYDRA QA Report")))
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a CYDRA QA JSON report as a readable PDF.")
    parser.add_argument("--input", required=True, type=Path, help="Path to report.json")
    parser.add_argument("--output", required=True, type=Path, help="Destination PDF path")
    args = parser.parse_args()
    render_report(args.input, args.output)
    print(f"PDF report written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
