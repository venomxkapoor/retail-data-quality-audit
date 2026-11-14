"""Run a beginner-friendly data-quality audit on the supplied retail sample."""

from pathlib import Path
import json

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_DIR / "data" / "retail_sample_raw.csv"
REPORTING_FILE = PROJECT_DIR / "data" / "retail_reporting_view.csv"
OUTPUT_DIR = PROJECT_DIR / "outputs"

EXPECTED_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]

START_DATE = pd.Timestamp("2010-12-01 00:00:00")
END_DATE = pd.Timestamp("2011-12-09 23:59:59")


def load_sample(path=DATA_FILE):
    """Read the sample while preserving identifiers as text."""
    data = pd.read_csv(
        path,
        dtype={
            "InvoiceNo": "string",
            "StockCode": "string",
            "Description": "string",
            "CustomerID": "string",
            "Country": "string",
        },
    )
    missing_columns = [name for name in EXPECTED_COLUMNS if name not in data.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    data["InvoiceDate"] = pd.to_datetime(data["InvoiceDate"], errors="coerce")
    data["Quantity"] = pd.to_numeric(data["Quantity"], errors="coerce")
    data["UnitPrice"] = pd.to_numeric(data["UnitPrice"], errors="coerce")
    return data


def build_flags(data):
    """Create one True/False column for each validation rule."""
    invoice_text = data["InvoiceNo"].fillna("").str.upper()
    is_cancellation = invoice_text.str.startswith("C")

    flags = pd.DataFrame(index=data.index)
    flags["missing_description"] = data["Description"].isna()
    flags["missing_customer_id"] = data["CustomerID"].isna()
    flags["potential_duplicate_line"] = data[EXPECTED_COLUMNS].duplicated(keep=False)
    flags["zero_quantity"] = data["Quantity"].eq(0) | data["Quantity"].isna()
    flags["negative_quantity_non_cancellation"] = (
        data["Quantity"].lt(0) & ~is_cancellation
    )
    flags["non_positive_unit_price"] = (
        data["UnitPrice"].le(0) | data["UnitPrice"].isna()
    )
    flags["cancellation_quantity_mismatch"] = is_cancellation & data["Quantity"].ge(0)
    flags["invalid_or_out_of_range_date"] = (
        data["InvoiceDate"].isna()
        | data["InvoiceDate"].lt(START_DATE)
        | data["InvoiceDate"].gt(END_DATE)
    )
    return flags, is_cancellation


def validation_rules():
    """Return the plain-language rule definitions used in the report."""
    return [
        {
            "Rule": "missing_description",
            "Check": "Description is blank",
            "WhyItMatters": "The product line is harder to review and group.",
            "Interpretation": "Requires review; not automatically wrong.",
        },
        {
            "Rule": "missing_customer_id",
            "Check": "CustomerID is blank",
            "WhyItMatters": "Customer-level analysis is not possible for that line.",
            "Interpretation": "Informative limitation; keep for aggregate reporting.",
        },
        {
            "Rule": "potential_duplicate_line",
            "Check": "All eight source fields match another sample row",
            "WhyItMatters": "Counting both rows may overstate transaction values.",
            "Interpretation": "Potential duplicate; investigate before declaring an error.",
        },
        {
            "Rule": "zero_quantity",
            "Check": "Quantity is zero or cannot be read as a number",
            "WhyItMatters": "A zero-quantity product line has no clear reporting value.",
            "Interpretation": "Requires review.",
        },
        {
            "Rule": "negative_quantity_non_cancellation",
            "Check": "Quantity is negative but InvoiceNo does not start with C",
            "WhyItMatters": "It may be an adjustment that needs separate treatment.",
            "Interpretation": "Suspicious, but not automatically incorrect.",
        },
        {
            "Rule": "non_positive_unit_price",
            "Check": "UnitPrice is zero, negative or unreadable",
            "WhyItMatters": "The line cannot be treated as ordinary positive-price sales.",
            "Interpretation": "Requires review; free items or adjustments may be valid.",
        },
        {
            "Rule": "cancellation_quantity_mismatch",
            "Check": "InvoiceNo starts with C but Quantity is not negative",
            "WhyItMatters": "The cancellation marker and quantity direction disagree.",
            "Interpretation": "Likely inconsistent if found.",
        },
        {
            "Rule": "invalid_or_out_of_range_date",
            "Check": "InvoiceDate is invalid or outside the documented source period",
            "WhyItMatters": "The line may fall outside the intended reporting period.",
            "Interpretation": "Requires review.",
        },
    ]


def make_quality_summary(flags, rules):
    total_rows = len(flags)
    rows = []
    for rule in rules:
        count = int(flags[rule["Rule"]].sum())
        rows.append(
            {
                **rule,
                "AffectedRows": count,
                "AffectedPercent": count / total_rows if total_rows else 0,
            }
        )
    return pd.DataFrame(rows)


def make_exception_log(data, flags):
    """Create one record per flagged sample row with joined rule names."""
    flagged = flags.any(axis=1)
    exceptions = data.loc[flagged].copy()
    # SampleRowNumber counts data records from 1. It does not count the CSV header.
    exceptions.insert(0, "SampleRowNumber", exceptions.index + 1)
    exceptions["TriggeredRules"] = flags.loc[flagged].apply(
        lambda row: "; ".join(row.index[row].tolist()), axis=1
    )
    return exceptions


def make_reporting_view(data, flags, is_cancellation):
    """Create a positive-item sales view without changing the raw sample."""
    duplicate_extra = data[EXPECTED_COLUMNS].duplicated(keep="first")
    eligible = (
        ~is_cancellation
        & data["Quantity"].gt(0)
        & data["UnitPrice"].gt(0)
        & ~flags["missing_description"]
        & ~flags["invalid_or_out_of_range_date"]
        & ~duplicate_extra
    )
    reporting = data.loc[eligible].copy()
    reporting.insert(0, "SampleRowNumber", reporting.index + 1)
    reporting["LineValueGBP"] = reporting["Quantity"] * reporting["UnitPrice"]
    return reporting, eligible, duplicate_extra


def run_audit(data_file=DATA_FILE):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = load_sample(data_file)
    rules = validation_rules()
    flags, is_cancellation = build_flags(data)
    summary = make_quality_summary(flags, rules)
    exceptions = make_exception_log(data, flags)
    reporting, eligible, duplicate_extra = make_reporting_view(
        data, flags, is_cancellation
    )

    summary.to_csv(OUTPUT_DIR / "quality_summary.csv", index=False)
    exceptions.to_csv(OUTPUT_DIR / "exception_log.csv", index=False)
    reporting.to_csv(REPORTING_FILE, index=False, date_format="%Y-%m-%d %H:%M:%S")

    metadata = {
        "source_rows": 541909,
        "sample_rows": len(data),
        "sample_seed": 352,
        "base_random_rows": 4500,
        "sample_type": "4,500 simple random rows plus documented exception enrichment",
        "cancellation_rows": int(is_cancellation.sum()),
        "negative_quantity_rows": int(data["Quantity"].lt(0).sum()),
        "reporting_view_rows": len(reporting),
        "reporting_view_percent": len(reporting) / len(data),
        "exception_rows_any_rule": int(flags.any(axis=1).sum()),
        "potential_duplicate_rows": int(flags["potential_duplicate_line"].sum()),
        "duplicate_extra_rows_excluded": int(duplicate_extra.sum()),
        "reporting_value_gbp": float(reporting["LineValueGBP"].sum()),
        "date_min": data["InvoiceDate"].min().isoformat(),
        "date_max": data["InvoiceDate"].max().isoformat(),
        "countries": int(data["Country"].nunique(dropna=True)),
    }
    with open(OUTPUT_DIR / "audit_metadata.json", "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)

    print(summary[["Rule", "AffectedRows", "AffectedPercent"]].to_string(index=False))
    print(f"Reporting view: {len(reporting):,} of {len(data):,} rows")
    return data, flags, summary, exceptions, reporting, metadata


if __name__ == "__main__":
    run_audit()
