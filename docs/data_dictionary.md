# Data dictionary

The raw sample preserves the eight fields supplied in the UCI workbook.

| Column | Meaning | Project treatment |
|---|---|---|
| `InvoiceNo` | Invoice identifier. A value beginning with `C` marks a cancellation. It identifies an invoice, not a unique product line. | Stored as text. Used to identify cancellations. |
| `StockCode` | Product or item code. Some real values contain letters or special codes. | Stored as text. No numeric conversion is applied. |
| `Description` | Product description. | Missing values are flagged and preserved. |
| `Quantity` | Number of units on the line. Negative values can represent cancellations or adjustments. | Used with the invoice prefix to distinguish ordinary sales, cancellations and review cases. |
| `InvoiceDate` | Date and time recorded for the transaction line. | Parsed as a date and checked against 2010-12-01 to 2011-12-09. |
| `UnitPrice` | Price per unit in pounds sterling. | Non-positive values are flagged. They are not silently changed. |
| `CustomerID` | Customer identifier. | Stored as an identifier. Missing values remain missing. |
| `Country` | Customer country recorded in the source. | Preserved as supplied. |

The reporting view adds two derived fields:

| Column | Meaning |
|---|---|
| `SampleRowNumber` | Original row number in the supplied sample CSV, including the header offset. |
| `LineValueGBP` | `Quantity * UnitPrice` for rows accepted into the positive-item sales view. |

`data/sample_source_rows.csv` maps every sample record to its row number in the
original UCI workbook. This supports traceability without adding derived fields
to the unchanged raw sample.
