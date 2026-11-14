import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from audit import build_flags, make_reporting_view  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
