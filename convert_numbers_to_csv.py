"""
convert_numbers_to_csv.py

Converts a Numbers spreadsheet directly to CSV, so you don't need to
manually do File -> Export To -> CSV in the Numbers app every time you
update your data. Reads the FIRST table on the FIRST sheet.

Usage:
    python3 convert_numbers_to_csv.py --in Marina_Analysis_filled.numbers --out Marina_Analysis_filled.csv
"""

import argparse
import csv
from numbers_parser import Document


def convert(numbers_path: str, csv_path: str):
    doc = Document(numbers_path)
    table = doc.sheets[0].tables[0]
    rows = list(table.rows(values_only=True))

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)

    print(f"Exported {len(rows) - 1} data rows (plus header) to {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a .numbers file to CSV.")
    parser.add_argument("--in", dest="in_path", required=True)
    parser.add_argument("--out", dest="out_path", required=True)
    args = parser.parse_args()
    convert(args.in_path, args.out_path)
