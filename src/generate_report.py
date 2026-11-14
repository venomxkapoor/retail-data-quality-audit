"""Create the two-page PDF summary from the final audit outputs."""

from pathlib import Path
import json

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "outputs"
REPORT_DIR = PROJECT_DIR / "reports"
FIGURE_DIR = REPORT_DIR / "figures"

pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))


def make_charts(summary, metadata):
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    chart_data = summary[summary["AffectedRows"] > 0].copy()
    labels = {
        "missing_description": "Missing description",
        "missing_customer_id": "Missing customer ID",
        "potential_duplicate_line": "Duplicate-looking line",
        "negative_quantity_non_cancellation": "Negative non-cancellation",
        "non_positive_unit_price": "Non-positive price",
    }
    chart_data["Label"] = chart_data["Rule"].map(labels).fillna(chart_data["Rule"])
    chart_data = chart_data.sort_values("AffectedRows")

    plt.figure(figsize=(7.2, 2.6))
    bars = plt.barh(chart_data["Label"], chart_data["AffectedRows"], color="#4472C4")
    plt.xlabel("Flagged sample rows")
    plt.title("Observed exceptions in the deliberately enriched sample", loc="left")
    plt.grid(axis="x", alpha=0.2)
    plt.bar_label(bars, padding=3, fontsize=8)
    plt.tight_layout()
    issue_chart = FIGURE_DIR / "issue_counts.png"
    plt.savefig(issue_chart, dpi=160, bbox_inches="tight")
    plt.close()

    counts = [metadata["reporting_view_rows"], metadata["sample_rows"] - metadata["reporting_view_rows"]]
    plt.figure(figsize=(6.4, 2.4))
    bars = plt.barh(
        ["Reporting view", "Excluded from view"],
        counts,
        color=["#70AD47", "#ED7D31"],
    )
    plt.xlabel("Rows")
    plt.title("Rows used for the defined positive-item sales view", loc="left")
    plt.grid(axis="x", alpha=0.2)
    plt.bar_label(bars, padding=3, fontsize=8)
    plt.tight_layout()
    reporting_chart = FIGURE_DIR / "reporting_view_rows.png"
    plt.savefig(reporting_chart, dpi=160, bbox_inches="tight")
    plt.close()
    return issue_chart, reporting_chart


def add_page_number(canvas, document):
    canvas.saveState()
    canvas.setFont("DejaVuSans", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawRightString(195 * mm, 10 * mm, f"Page {document.page}")
    canvas.restoreState()


def build_report():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = pd.read_csv(OUTPUT_DIR / "quality_summary.csv")
    metadata = json.loads((OUTPUT_DIR / "audit_metadata.json").read_text())
    issue_chart, reporting_chart = make_charts(summary, metadata)

    pdf_file = REPORT_DIR / "data_quality_report.pdf"
    document = SimpleDocTemplate(
        str(pdf_file),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="DejaVuSans-Bold",
            fontSize=18,
            leading=21,
            textColor=colors.HexColor("#17365D"),
            alignment=TA_LEFT,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontName="DejaVuSans-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#17365D"),
            spaceBefore=6,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontName="DejaVuSans",
            fontSize=8.5,
            leading=11,
            spaceAfter=4,
        )
    )

    story = [
        Paragraph("Retail Data Quality Assurance &amp; Reporting", styles["ReportTitle"]),
        Paragraph(
            "Python and Excel audit of a 5,000-row sample from the UCI Online Retail dataset",
            styles["BodySmall"],
        ),
        Paragraph("Dataset and purpose", styles["Section"]),
        Paragraph(
            "The source contains 541,909 historical UK online-retail transaction lines from "
            "December 2010 to December 2011. This audit checks whether a smaller sample is "
            "suitable for a defined positive-item sales report. It does not treat cancellations, "
            "adjustments or missing customer IDs as errors automatically.",
            styles["BodySmall"],
        ),
    ]

    overview = [
        ["Measure", "Result"],
        ["Original dataset", f'{metadata["source_rows"]:,} rows'],
        ["Audit sample", f'{metadata["sample_rows"]:,} authentic rows'],
        ["Rows with at least one flag", f'{metadata["exception_rows_any_rule"]:,}'],
        ["Cancellation rows", f'{metadata["cancellation_rows"]:,}'],
        ["Reporting view", f'{metadata["reporting_view_rows"]:,} rows ({metadata["reporting_view_percent"]:.1%})'],
    ]
    overview_table = Table(overview, colWidths=[70 * mm, 45 * mm])
    overview_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B4C6E7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FB")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story += [overview_table, Spacer(1, 6), Image(str(issue_chart), width=172 * mm, height=62 * mm)]

    story += [
        Paragraph("Key findings", styles["Section"]),
        Paragraph(
            "Missing CustomerID was the most common flag (1,433 rows; 28.7%). It limits "
            "customer-level analysis but does not prevent aggregate product or country reporting. "
            "The sample also contained 366 non-positive-price rows, 270 missing descriptions, "
            "261 negative-quantity non-cancellations and 163 duplicate-looking rows. No zero "
            "quantities, cancellation/quantity mismatches or invalid dates were observed.",
            styles["BodySmall"],
        ),
        PageBreak(),
        Paragraph("Reporting treatment and conclusion", styles["ReportTitle"]),
        Paragraph("Reporting view", styles["Section"]),
        Paragraph(
            "The reporting view is designed for positive-item sales analysis. It keeps rows with "
            "positive quantity and price, a valid in-range date and a description. It excludes "
            "cancellation invoices and later occurrences of exact duplicate-looking lines. This "
            "is a reporting assumption, not a claim that excluded source records are incorrect.",
            styles["BodySmall"],
        ),
        Image(str(reporting_chart), width=165 * mm, height=60 * mm),
        Paragraph("Operational interpretation", styles["Section"]),
        Paragraph(
            f'The defined view contains {metadata["reporting_view_rows"]:,} rows and a derived '
            f'positive line value of GBP {metadata["reporting_value_gbp"]:,.2f}. The value is '
            "calculated as Quantity x UnitPrice within this sample. It is not total company "
            "revenue and does not include cancellations or excluded review cases.",
            styles["BodySmall"],
        ),
        Paragraph("Limitations", styles["Section"]),
        Paragraph(
            "The sample is deliberately enriched with authentic exception cases after an initial "
            "4,500-row random selection, using seed 352. Its exception percentages are therefore "
            "not estimates of the full dataset's rates. Duplicate-looking lines may represent "
            "legitimate repeated purchases. The audit does not match returns to original sales, "
            "validate product master data or assess accounting completeness.",
            styles["BodySmall"],
        ),
        Paragraph("Conclusion", styles["Section"]),
        Paragraph(
            "The raw sample should be retained unchanged for traceability. The positive-item sales "
            "view is suitable for limited descriptive reporting under its stated rules. Exception "
            "records should remain available for review rather than being silently deleted or "
            "filled with invented values.",
            styles["BodySmall"],
        ),
        Paragraph("Source and licence", styles["Section"]),
        Paragraph(
            "Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. "
            "DOI: 10.24432/C5BW33. Licensed CC BY 4.0. Dataset creator: Daqing Chen, "
            "London South Bank University.",
            styles["BodySmall"],
        ),
    ]
    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"Created {pdf_file}")


if __name__ == "__main__":
    build_report()
