import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from audit import build_flags, make_exception_log, make_reporting_view  # noqa: E402
from generate_report import build_key_findings, register_report_fonts  # noqa: E402
from generate_workbook import build_workbook  # noqa: E402


def small_data():
    return pd.DataFrame(
        [
            ["100001", "A1", "ITEM", 2, pd.Timestamp("2011-01-01"), 3.0, "10", "UK"],
            ["C10002", "A1", "ITEM", -2, pd.Timestamp("2011-01-02"), 3.0, "10", "UK"],
            ["100003", "A2", None, 1, pd.Timestamp("2011-01-03"), 2.0, None, "UK"],
            ["100004", "A3", "ADJUST", -1, pd.Timestamp("2011-01-04"), 0.0, None, "UK"],
        ],
        columns=[
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
            "UnitPrice",
            "CustomerID",
            "Country",
        ],
    )


class BasicChecksTest(unittest.TestCase):
    def test_valid_cancellation_is_identified_but_not_a_mismatch(self):
        data = small_data()
        flags, is_cancellation = build_flags(data)
        self.assertTrue(bool(is_cancellation.iloc[1]))
        self.assertFalse(bool(flags.loc[1, "cancellation_quantity_mismatch"]))

    def test_missing_values_are_not_filled_with_invented_data(self):
        data = small_data()
        flags, _ = build_flags(data)
        self.assertTrue(bool(flags.loc[2, "missing_description"]))
        self.assertTrue(bool(flags.loc[2, "missing_customer_id"]))
        self.assertTrue(pd.isna(data.loc[2, "CustomerID"]))

    def test_reporting_view_keeps_only_justified_positive_sales_rows(self):
        data = small_data()
        flags, is_cancellation = build_flags(data)
        reporting, eligible, _ = make_reporting_view(data, flags, is_cancellation)
        self.assertEqual(eligible.tolist(), [True, False, False, False])
        self.assertEqual(len(reporting), 1)
        self.assertEqual(reporting.iloc[0]["LineValueGBP"], 6.0)

    def test_sample_row_number_is_one_based_and_excludes_the_header(self):
        data = small_data()
        flags, is_cancellation = build_flags(data)
        exceptions = make_exception_log(data, flags)
        reporting, _, _ = make_reporting_view(data, flags, is_cancellation)

        self.assertEqual(exceptions["SampleRowNumber"].tolist(), [3, 4])
        self.assertEqual(reporting["SampleRowNumber"].tolist(), [1])

        mapping = pd.read_csv(PROJECT_DIR / "data" / "sample_source_rows.csv")
        self.assertEqual(mapping["SampleRowNumber"].iloc[0], 1)
        self.assertEqual(mapping["SampleRowNumber"].iloc[-1], len(mapping))

    def test_pdf_findings_are_derived_from_the_summary(self):
        summary = pd.DataFrame(
            {
                "Rule": [
                    "missing_customer_id",
                    "non_positive_unit_price",
                    "missing_description",
                    "negative_quantity_non_cancellation",
                    "potential_duplicate_line",
                    "zero_quantity",
                    "cancellation_quantity_mismatch",
                    "invalid_or_out_of_range_date",
                ],
                "AffectedRows": [9, 8, 7, 6, 5, 0, 0, 0],
                "AffectedPercent": [0.30, 0.27, 0.23, 0.20, 0.17, 0, 0, 0],
            }
        )
        findings = build_key_findings(summary)
        self.assertIn("9 rows; 30.0%", findings)
        self.assertIn("8 non-positive-price rows", findings)
        self.assertNotIn("1,433", findings)

    def test_pdf_fonts_are_discovered_without_a_fixed_linux_path(self):
        font_paths = register_report_fonts()
        self.assertTrue(all(path.exists() for path in font_paths))

    def test_workbook_can_be_regenerated_from_published_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_file = Path(temporary_directory) / "audit.xlsx"
            build_workbook(output_file=output_file)
            workbook = load_workbook(output_file, read_only=False, data_only=False)
            self.assertEqual(
                workbook.sheetnames,
                [
                    "Quality Summary",
                    "Validation Rules",
                    "Exceptions",
                    "Reporting View",
                    "Source Sample",
                ],
            )
            self.assertEqual(workbook["Quality Summary"]["F12"].value, "=E12/$B$4")
            workbook.close()


if __name__ == "__main__":
    unittest.main()
