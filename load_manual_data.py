"""
load_manual_data.py

Loads your manually-researched competitor spreadsheet (exported as CSV,
same 11 columns as Marina_Analysis_filled.csv) into the database.

Expected columns, in order:
    Marina, Address, Contact Info, Slip Price (per month), Size Covered,
    Storage Price, Launch Fee, Fuel Type, Additional Amenities,
    Top Complaint, Top Praise

Handles facilities NOT already in the database (e.g. ones the automated
scraper never found, like Lauritzen Yacht Harbor) by inserting them fresh.
Handles facilities that already exist (from run_pipeline.py) by updating
them in place -- matched by facility_name, which is UNIQUE in the schema,
so this is always safe to re-run.

A lot of real marina pricing is NOT a single clean number -- it's a range
($120-$600), a per-foot rate, or an unverified estimate. This script
ALWAYS preserves the exact original text in *_raw columns, and ALSO fills
in a clean numeric min/max when the text is an unambiguous "$X - $Y"
range, for easy SQL sorting/comparison. Irregular pricing is left numeric-
NULL on purpose rather than guessed at -- check the *_raw column for those.

Usage:
    python3 load_manual_data.py --csv Marina_Analysis_filled.csv --db marina_analysis.db
"""

import argparse
import re
import sqlite3
import pandas as pd

EXPECTED_COLUMNS = ["facility_name", "address", "contact_info", "slip_price_raw",
                    "size_covered_raw", "storage_price_raw", "launch_fee_raw",
                    "fuel_available", "amenities_raw", "top_complaint", "top_praise"]

# Minimal schema needed if this script is run before run_pipeline.py has
# ever created the tables (e.g. you're starting purely from manual data).
CREATE_FACILITIES_TABLE = """
CREATE TABLE IF NOT EXISTS facilities (
    facility_id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_name TEXT NOT NULL UNIQUE,
    facility_type TEXT,
    access TEXT,
    source_city TEXT,
    is_own_business BOOLEAN,
    county TEXT,
    body_of_water TEXT,
    address TEXT,
    phone_number TEXT,
    website TEXT,
    total_capacity INTEGER,
    dry_storage_capacity INTEGER,
    min_boat_length INTEGER,
    max_boat_length INTEGER,
    size_covered_raw TEXT,
    services_raw TEXT,
    detail_url TEXT,
    capacity_data_missing BOOLEAN,
    google_rating REAL,
    google_review_count INTEGER
);
"""

CREATE_REVIEWS_TABLE = """
CREATE TABLE IF NOT EXISTS reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id INTEGER NOT NULL,
    source TEXT,
    sentiment TEXT,
    theme TEXT,
    note TEXT,
    FOREIGN KEY (facility_id) REFERENCES facilities (facility_id) ON DELETE CASCADE
);
"""

CREATE_PRICING_TABLE = """
CREATE TABLE IF NOT EXISTS pricing (
    pricing_id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id INTEGER NOT NULL,
    slip_price_min_monthly REAL,
    slip_price_max_monthly REAL,
    slip_price_raw TEXT,
    storage_price_per_month REAL,
    storage_price_raw TEXT,
    launch_fee REAL,
    launch_fee_raw TEXT,
    fuel_available TEXT,
    source_note TEXT,
    FOREIGN KEY (facility_id) REFERENCES facilities (facility_id) ON DELETE CASCADE
);
"""


def parse_slip_price_range(raw):
    """Extract a clean (min, max) from unambiguous '$X - $Y' text. None if irregular."""
    if not isinstance(raw, str):
        return None, None
    if any(flag in raw.lower() for flag in ["~", "unverified", "per foot", "minimum"]):
        return None, None
    match = re.match(r"^\$?([\d,]+)\s*-\s*\$?([\d,]+)", raw.strip())
    if match:
        return float(match.group(1).replace(",", "")), float(match.group(2).replace(",", ""))
    return None, None


def parse_simple_number(raw):
    """Parse a plain '$15.00'-style number. None if compound/irregular."""
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        match = re.match(r"^\$?([\d,]+(\.\d+)?)\s*$", raw.strip())
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def get_or_create_facility_id(cur, name):
    """Look up facility_id by name; create a bare-bones row if it doesn't exist yet
    (e.g. a marina the automated scraper never found)."""
    cur.execute("SELECT facility_id FROM facilities WHERE facility_name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0], False
    cur.execute("INSERT INTO facilities (facility_name, is_own_business) VALUES (?, 0)", (name,))
    return cur.lastrowid, True


def load(csv_path, db_path):
    df = pd.read_csv(csv_path)
    if len(df.columns) != len(EXPECTED_COLUMNS):
        raise ValueError(f"Expected {len(EXPECTED_COLUMNS)} columns, got {len(df.columns)}. "
                          f"Check your CSV matches the expected format (see docstring).")
    df.columns = EXPECTED_COLUMNS

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    cur.execute(CREATE_FACILITIES_TABLE)
    cur.execute(CREATE_REVIEWS_TABLE)
    cur.execute(CREATE_PRICING_TABLE)
    conn.commit()

    updated, created, parsed_ranges = 0, [], 0

    for _, row in df.iterrows():
        name = row["facility_name"].strip()
        fid, was_created = get_or_create_facility_id(cur, name)
        if was_created:
            created.append(name)

        cur.execute(
            """UPDATE facilities
               SET address = ?, phone_number = ?, services_raw = ?, size_covered_raw = ?
               WHERE facility_id = ?""",
            (row["address"], row["contact_info"], row["amenities_raw"],
             row["size_covered_raw"], fid),
        )

        slip_min, slip_max = parse_slip_price_range(row["slip_price_raw"])
        if slip_min is not None:
            parsed_ranges += 1
        storage_num = parse_simple_number(row["storage_price_raw"])
        launch_num = parse_simple_number(row["launch_fee_raw"])

        # Replace any existing pricing row for this facility -- always safe
        # since facility_id is now guaranteed stable across re-runs.
        cur.execute("DELETE FROM pricing WHERE facility_id = ?", (fid,))
        cur.execute(
            """INSERT INTO pricing
               (facility_id, slip_price_min_monthly, slip_price_max_monthly, slip_price_raw,
                storage_price_per_month, storage_price_raw, launch_fee, launch_fee_raw,
                fuel_available)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fid, slip_min, slip_max, row["slip_price_raw"], storage_num,
             row["storage_price_raw"], launch_num, row["launch_fee_raw"], row["fuel_available"]),
        )

        cur.execute("DELETE FROM reviews WHERE facility_id = ? AND source = 'Manual research'", (fid,))
        for note, sentiment in [(row["top_complaint"], "negative"), (row["top_praise"], "positive")]:
            if isinstance(note, str) and note.strip():
                cur.execute(
                    """INSERT INTO reviews (facility_id, source, sentiment, theme, note)
                       VALUES (?, ?, ?, ?, ?)""",
                    (fid, "Manual research", sentiment, "top theme", note),
                )

        updated += 1

    conn.commit()
    conn.close()

    print(f"[load_manual_data] Updated {updated} facilities "
          f"({len(created)} newly created: {created}).")
    print(f"[load_manual_data] Cleanly parsed a numeric slip price range for "
          f"{parsed_ranges}/{updated} (rest kept as raw text only -- check *_raw columns).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load the manually-researched competitor spreadsheet.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--db", default="marina_analysis.db")
    args = parser.parse_args()
    load(args.csv, args.db)
