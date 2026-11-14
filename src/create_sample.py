"""Create the documented 5,000-row sample from the full UCI workbook.

The source workbook is not redistributed in this repository. Download it from
the UCI page and pass its path to this script.
"""

from pathlib import Path
import argparse

import pandas as pd


SEED = 352
TARGET_ROWS = 5000
BASE_RANDOM_ROWS = 4500


def select_extra_rows(data, already_selected, condition, number, random_state):
    """Return up to ``number`` unused source indexes meeting ``condition``."""
    candidates = data.index[condition & ~data.index.isin(already_selected)]
    if len(candidates) == 0:
        return []
    take = min(number, len(candidates))
    return list(pd.Series(candidates).sample(n=take, random_state=random_state))


def select_complete_duplicate_groups(
    data, already_selected, minimum_rows, random_state, target_rows=TARGET_ROWS
):
    """Select complete unused duplicate groups without exceeding the target."""
    duplicate_rows = data.duplicated(keep=False)
    row_signatures = pd.util.hash_pandas_object(data, index=False)
    signatures = row_signatures[duplicate_rows].drop_duplicates()
    signatures = signatures.sample(frac=1, random_state=random_state)

    selected_groups = []
    for signature in signatures:
        group_indexes = list(data.index[row_signatures.eq(signature)])
        unused_group = [index for index in group_indexes if index not in already_selected]
        remaining_capacity = target_rows - len(already_selected) - len(selected_groups)

        # Adding only part of a duplicate group would weaken traceability.
        if len(unused_group) >= 2 and len(unused_group) <= remaining_capacity:
            selected_groups.extend(unused_group)
        if len(selected_groups) >= minimum_rows or remaining_capacity < 2:
            break
    return selected_groups


def add_rows_up_to_target(selected, new_rows, target_rows=TARGET_ROWS):
    """Append rows in their sampled order without exceeding the target size."""
    remaining_capacity = max(target_rows - len(selected), 0)
    selected.extend(new_rows[:remaining_capacity])


def create_sample(source_file, output_file, selection_log_file):
    data = pd.read_excel(source_file)

    # Start with a broad simple random sample.
    selected = list(data.sample(n=BASE_RANDOM_ROWS, random_state=SEED).index)

    # Add authentic review cases so the small portfolio sample demonstrates
    # several important rules. No source values are changed.
    duplicate_indexes = select_complete_duplicate_groups(
        data, selected, minimum_rows=160, random_state=SEED + 1
    )
    selected += duplicate_indexes

    invoice_text = data["InvoiceNo"].astype(str).str.upper()
    non_cancel_negative = (data["Quantity"] < 0) & ~invoice_text.str.startswith("C")
    extra_rows = select_extra_rows(
        data, selected, non_cancel_negative, 140, SEED + 2
    )
    add_rows_up_to_target(selected, extra_rows)

    extra_rows = select_extra_rows(
        data, selected, data["UnitPrice"] <= 0, 100, SEED + 3
    )
    add_rows_up_to_target(selected, extra_rows)

    extra_rows = select_extra_rows(
        data, selected, data["Description"].isna(), 100, SEED + 4
    )
    add_rows_up_to_target(selected, extra_rows)

    # Overlap between groups can leave fewer than 5,000 rows. Fill the gap
    # with additional random source rows.
    selected = list(dict.fromkeys(selected))
    remaining = TARGET_ROWS - len(selected)
    if remaining > 0:
        available = data.index[~data.index.isin(selected)]
        fill = pd.Series(available).sample(n=remaining, random_state=SEED + 5)
        selected += list(fill)

    selected = sorted(selected)
    sample = data.loc[selected].copy()

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(output_file, index=False, date_format="%Y-%m-%d %H:%M:%S")

    selection_log = pd.DataFrame(
        {
            "SampleRowNumber": range(1, len(selected) + 1),
            # Add 2 because the source workbook has a header in row 1.
            "SourceWorkbookRow": [source_index + 2 for source_index in selected],
        }
    )
    selection_log.to_csv(selection_log_file, index=False)
    return sample


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_file", help="Path to the downloaded UCI XLSX file")
    parser.add_argument(
        "--output", default="data/retail_sample_raw.csv", help="Sample CSV path"
    )
    parser.add_argument(
        "--selection-log",
        default="data/sample_source_rows.csv",
        help="CSV mapping sample rows to source workbook rows",
    )
    args = parser.parse_args()
    sample = create_sample(args.source_file, args.output, args.selection_log)
    print(f"Created sample with {len(sample):,} authentic source rows.")


if __name__ == "__main__":
    main()
