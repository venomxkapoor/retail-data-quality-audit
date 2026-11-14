# Retail Data Quality Assurance & Reporting - Python and Excel

This beginner-level project audits historical transaction lines before they are
used in a simple retail report. It demonstrates careful validation, transparent
exception handling and a documented reporting view. It is not an enterprise ETL
system and does not use machine learning.

## Business problem

A retailer exported transaction lines from an operational system. Before using
them for reporting, a junior analyst needs to identify incomplete fields,
suspicious values, cancellations, adjustments and duplicate-looking lines. The
raw records must remain traceable, and unusual records must not be silently
deleted or filled with invented values.

## Dataset and attribution

- Dataset: **Online Retail**, UCI Machine Learning Repository
- Creator: Daqing Chen, London South Bank University
- Citation: Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning
  Repository. https://doi.org/10.24432/C5BW33
- Official page: https://archive.ics.uci.edu/dataset/352/online-retail
- Licence: CC BY 4.0
- Original size: 541,909 transaction lines and eight columns
- Historical period: 1 December 2010 to 9 December 2011

The data is historical and should not be presented as current retail market
information.

## Sample design

The repository contains 5,000 authentic source rows. Source values were not
invented or edited.

1. Select 4,500 rows by simple random sampling with seed `352`.
2. Add complete exact-duplicate groups until at least 160 additional rows are
   represented.
3. Add up to 140 negative-quantity non-cancellation rows, 100 non-positive-price
   rows and 100 missing-description rows, using documented seed offsets.
4. Remove overlapping selections and fill any remaining places with unused
   random source rows.
5. Sort selected records by their original source row number.

This is a **deliberately enriched audit sample**. It is useful for demonstrating
validation logic, but its issue percentages are not estimates of the full
dataset. `data/sample_source_rows.csv` records the original workbook row for
each sample line. `src/create_sample.py` reproduces the selection when supplied
with the official UCI workbook.

## Tools

- Python 3
- pandas
- Python's built-in `unittest`
- matplotlib and ReportLab for the short PDF report
- Microsoft Excel-compatible `.xlsx` output

## Validation rules

| Rule | Treatment |
|---|---|
| Missing description | Flag for review; do not invent a description. |
| Missing CustomerID | Flag as a limitation; keep for aggregate reporting. |
| Exact duplicate-looking line | Flag for investigation; do not automatically call it an error. |
| Zero quantity | Flag for review. |
| Negative quantity without a cancellation prefix | Treat as a possible adjustment requiring review. |
| Non-positive unit price | Flag; a free item or adjustment may still be valid. |
| Cancellation/quantity mismatch | Check whether `C` invoices have a non-negative quantity. |
| Invalid or out-of-range date | Flag dates outside the documented source period. |

A cancellation invoice is identified by an `InvoiceNo` beginning with `C`. It
is not treated as an incorrect record. `InvoiceNo` can contain several product
lines and is not a unique row identifier.

## Principal findings

The final audit calculated these results from the included sample:

| Finding | Rows | Percent of sample |
|---|---:|---:|
| Missing CustomerID | 1,433 | 28.7% |
| Non-positive UnitPrice | 366 | 7.3% |
| Missing Description | 270 | 5.4% |
| Negative quantity without cancellation prefix | 261 | 5.2% |
| Exact duplicate-looking lines | 163 | 3.3% |
| Zero quantity | 0 | 0.0% |
| Cancellation/quantity mismatch | 0 | 0.0% |
| Invalid or out-of-range date | 0 | 0.0% |

There were 84 cancellation lines and 1,599 rows with at least one validation
flag. A zero result is reported rather than replaced by a fabricated finding.

## Reporting view

`data/retail_sample_raw.csv` is preserved. A separate positive-item sales view
contains 4,468 rows (89.4% of the sample). It requires:

- a non-cancellation invoice;
- positive quantity and UnitPrice;
- a present description;
- a valid date within the documented period; and
- exclusion of the second and later occurrence of an exact duplicate-looking
  line.

The last step is a conservative reporting assumption, not a declaration that a
repeated line is definitely erroneous. Missing CustomerID does not prevent
aggregate reporting, so those rows may remain in the reporting view. The
derived `LineValueGBP` totals GBP 86,231.75 within this enriched sample. It is
not total company revenue.

## Run the project

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/audit.py
python src/generate_report.py
python -m unittest discover -s tests -p "test_*.py" -v
```

To rebuild the sample, first download `Online Retail.xlsx` from the official UCI
page, then run:

```bash
python src/create_sample.py "/path/to/Online Retail.xlsx"
```

The audit script regenerates the two CSV outputs and the reporting view. The
repository includes the final formatted Excel workbook as a reviewable project
artifact.

## Repository contents

```text
data/       raw sample, source-row mapping and reporting view
docs/       short data dictionary
outputs/    exception log, quality summary and Excel workbook
reports/    two-page PDF report and its figures
src/        sampling, audit and report scripts
tests/      small tests for the core business rules
```

## Limitations

- The sample is deliberately enriched and is not statistically representative.
- Duplicate-looking lines can be legitimate and require business context.
- Returns are not matched to their original sales.
- The project does not validate product master data, accounting completeness or
  current business performance.
- The positive-item sales view supports one defined reporting purpose. Other
  purposes would require different inclusion rules.
