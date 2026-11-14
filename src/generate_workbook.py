"""Create the Excel audit workbook from the final CSV and JSON outputs."""

from pathlib import Path
import json

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from audit import DATA_FILE, OUTPUT_DIR, REPORTING_FILE, validation_rules


PROJECT_DIR = Path(__file__).resolve().parents[1]
WORKBOOK_FILE = OUTPUT_DIR / "retail_audit.xlsx"
BLUE = "17365D"
LIGHT_BLUE = "D9EAF7"


def excel_value(value):
    """Convert pandas missing values into blank Excel cells."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def style_title(worksheet, title, last_column):
    worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_column)
    cell = worksheet.cell(1, 1, title)
    cell.font = Font(size=16, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor=BLUE)
    cell.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[1].height = 26


def add_dataframe(worksheet, data, start_row, table_name):
    """Write a DataFrame and add a filterable Excel table."""
    for column_number, column_name in enumerate(data.columns, start=1):
        cell = worksheet.cell(start_row, column_number, column_name)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.alignment = Alignment(wrap_text=True, vertical="top")

    for row_number, row in enumerate(data.itertuples(index=False, name=None), start=start_row + 1):
        for column_number, value in enumerate(row, start=1):
            cell = worksheet.cell(row_number, column_number, excel_value(value))
            cell.alignment = Alignment(vertical="top")

    end_row = start_row + len(data)
    end_column = len(data.columns)
    table = Table(
        displayName=table_name,
        ref=f"A{start_row}:{worksheet.cell(end_row, end_column).coordinate}",
    )
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    worksheet.add_table(table)


def finish_sheet(worksheet, data, header_row):
    """Apply readable widths and common formats."""
    for column_number, column_name in enumerate(data.columns, start=1):
        values = [str(column_name)]
        values.extend(str(value) for value in data[column_name].dropna().head(200))
        width = min(max(len(value) for value in values) + 2, 42)
        worksheet.column_dimensions[get_column_letter(column_number)].width = width

        if column_name in {"AffectedPercent", "ReportingPercent"}:
            for row in range(header_row + 1, header_row + len(data) + 1):
                worksheet.cell(row, column_number).number_format = "0.0%"
        elif column_name in {"UnitPrice", "LineValueGBP"}:
            for row in range(header_row + 1, header_row + len(data) + 1):
                worksheet.cell(row, column_number).number_format = "#,##0.00"
        elif column_name == "InvoiceDate":
            for row in range(header_row + 1, header_row + len(data) + 1):
                worksheet.cell(row, column_number).number_format = "yyyy-mm-dd hh:mm"

        if column_name in {"Check", "WhyItMatters", "Interpretation"}:
            for row in range(header_row + 1, header_row + len(data) + 1):
                worksheet.cell(row, column_number).alignment = Alignment(
                    wrap_text=True, vertical="top"
                )
                worksheet.row_dimensions[row].height = 32

    worksheet.freeze_panes = f"A{header_row + 1}"
    worksheet.auto_filter.ref = worksheet.tables[next(iter(worksheet.tables))].ref


def read_transaction_csv(path):
    return pd.read_csv(
        path,
        dtype={
            "InvoiceNo": "string",
            "StockCode": "string",
            "Description": "string",
            "CustomerID": "string",
            "Country": "string",
        },
        parse_dates=["InvoiceDate"],
    )


def build_workbook(
    output_file=WORKBOOK_FILE,
    source_file=DATA_FILE,
    summary_file=OUTPUT_DIR / "quality_summary.csv",
    exceptions_file=OUTPUT_DIR / "exception_log.csv",
    reporting_file=REPORTING_FILE,
    metadata_file=OUTPUT_DIR / "audit_metadata.json",
):
    """Build and save the five-sheet workbook."""
    source = read_transaction_csv(source_file)
    summary = pd.read_csv(summary_file)
    exceptions = read_transaction_csv(exceptions_file)
    reporting = read_transaction_csv(reporting_file)
    rules = pd.DataFrame(validation_rules())
    metadata = json.loads(Path(metadata_file).read_text(encoding="utf-8"))

    workbook = Workbook()
    workbook.remove(workbook.active)

    summary_sheet = workbook.create_sheet("Quality Summary")
    style_title(summary_sheet, "Retail data quality summary", len(summary.columns))
    overview = [
        ("Original source rows", metadata["source_rows"]),
        ("Sample rows", metadata["sample_rows"]),
        ("Rows with at least one flag", metadata["exception_rows_any_rule"]),
        ("Cancellation rows", metadata["cancellation_rows"]),
        ("Reporting view rows", metadata["reporting_view_rows"]),
        ("Reporting view percent", metadata["reporting_view_percent"]),
    ]
    summary_sheet.append([])
    for row_number, (label, value) in enumerate(overview, start=3):
        summary_sheet.cell(row_number, 1, label).font = Font(bold=True)
        summary_sheet.cell(row_number, 2, value)
    summary_sheet["B8"].number_format = "0.0%"
    summary_start = 11
    add_dataframe(summary_sheet, summary, summary_start, "QualitySummaryTable")
    percent_column = list(summary.columns).index("AffectedPercent") + 1
    count_column = list(summary.columns).index("AffectedRows") + 1
    for row in range(summary_start + 1, summary_start + len(summary) + 1):
        count_cell = summary_sheet.cell(row, count_column).coordinate
        summary_sheet.cell(row, percent_column, f"={count_cell}/$B$4")
        summary_sheet.cell(row, percent_column).number_format = "0.0%"
    finish_sheet(summary_sheet, summary, summary_start)
    summary_sheet.column_dimensions["A"].width = 38
    summary_sheet.column_dimensions["B"].width = 28

    sheet_inputs = [
        ("Validation Rules", rules, "ValidationRulesTable"),
        ("Exceptions", exceptions, "ExceptionsTable"),
        ("Reporting View", reporting, "ReportingViewTable"),
        ("Source Sample", source, "SourceSampleTable"),
    ]
    for sheet_name, data, table_name in sheet_inputs:
        worksheet = workbook.create_sheet(sheet_name)
        style_title(worksheet, sheet_name, len(data.columns))
        worksheet.cell(2, 1, "Generated from the included audit data and outputs.")
        worksheet.cell(2, 1).font = Font(italic=True, color="666666")
        header_row = 4
        add_dataframe(worksheet, data, header_row, table_name)
        finish_sheet(worksheet, data, header_row)

    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    print(f"Created {output_path}")
    return output_path


if __name__ == "__main__":
    build_workbook()
