"""
load.py -- the "L" in ETL.

Writes already-clean data (from transform.py) into the SQLite database.
Does not fetch anything from the web, and does not clean or reshape data.

IMPORTANT DESIGN NOTE #1 (why facility_name has a UNIQUE constraint):
earlier versions of this project re-ran run_pipeline.py and ended up
creating brand-new facility_id numbers for the same marinas every time,
which silently orphaned all the pricing and review data linked to the
old ids. The UNIQUE constraint below plus the upsert logic makes that
class of bug structurally impossible: a given facility_name can only
ever correspond to ONE row, ever, no matter how many times the pipeline
runs.

IMPORTANT DESIGN NOTE #2 (why every value goes through to_native() before
binding): pandas gives back values as numpy types (numpy.bool_,
numpy.int64, numpy.float64) rather than plain Python types. Depending on
the exact sqlite3/Python build, binding those directly can raise
"sqlite3.InterfaceError: probably unsupported type". to_native() converts
everything to a plain Python type (or None for any kind of missing value)
before it ever reaches a SQL statement.
"""

import sqlite3
import numpy as np
import pandas as pd

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

COLUMN_MAP = {
    "Facility Name": "facility_name",
    "Type": "facility_type",
    "Access": "access",
    "source_city": "source_city",
    "is_own_business": "is_own_business",
    "county": "county",
    "body_of_water": "body_of_water",
    "address": "address",
    "total_capacity": "total_capacity",
    "dry_storage_capacity": "dry_storage_capacity",
    "min_boat_length": "min_boat_length",
    "max_boat_length": "max_boat_length",
    "services_raw": "services_raw",
    "detail_url": "detail_url",
    "capacity_data_missing": "capacity_data_missing",
}


def to_native(value):
    """Convert a pandas/numpy value to a plain Python type SQLite can always bind,
    or None for any flavor of missing value (NaN, pandas.NA, numpy.nan)."""
    if value is None:
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass  # pd.isna() chokes on some types (e.g. lists) -- just pass the value through
    return value


def load_facilities(clean_df: pd.DataFrame, db_path: str):
    """Create the schema (if needed) and upsert clean facility data into SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.execute(CREATE_FACILITIES_TABLE)
    cur.execute(CREATE_REVIEWS_TABLE)
    cur.execute(CREATE_PRICING_TABLE)
    conn.commit()

    df_renamed = clean_df.rename(columns=COLUMN_MAP)
    keep_cols = [c for c in COLUMN_MAP.values() if c in df_renamed.columns]
    df_final = df_renamed[keep_cols]

    # DIAGNOSTIC: check for duplicate column names, a common cause of
    # "row[col] returns a Series instead of a scalar" bugs.
    dupes = df_final.columns[df_final.columns.duplicated()].tolist()
    if dupes:
        print(f"[load] WARNING: duplicate column names detected: {dupes} -- "
              f"this WILL cause binding errors. Check transform.py for a field "
              f"name collision (e.g. 'Type' renaming to the same name as an "
              f"already-present 'facility_type' column).")

    inserted, updated = 0, 0
    for idx, row in df_final.iterrows():
        name = to_native(row["facility_name"])
        cur.execute("SELECT facility_id FROM facilities WHERE facility_name = ?", (name,))
        existing = cur.fetchone()

        if existing:
            other_cols = [c for c in keep_cols if c != "facility_name"]
            set_clause = ", ".join(f"{col} = ?" for col in other_cols)
            values = [to_native(row[col]) for col in other_cols]
            try:
                cur.execute(f"UPDATE facilities SET {set_clause} WHERE facility_id = ?",
                            values + [existing[0]])
            except (sqlite3.InterfaceError, sqlite3.ProgrammingError):
                print(f"\n[load] FAILED on row {idx} (facility_name={name!r}), UPDATE. "
                      f"Column -> value -> type:")
                for col, val in zip(other_cols, values):
                    print(f"    {col:25s} -> {val!r:40} -> {type(val)}")
                raise
            updated += 1
        else:
            cols_clause = ", ".join(keep_cols)
            placeholders = ", ".join("?" for _ in keep_cols)
            values = [to_native(row[col]) for col in keep_cols]
            try:
                cur.execute(f"INSERT INTO facilities ({cols_clause}) VALUES ({placeholders})", values)
            except (sqlite3.InterfaceError, sqlite3.ProgrammingError):
                print(f"\n[load] FAILED on row {idx} (facility_name={name!r}), INSERT. "
                      f"Column -> value -> type:")
                for col, val in zip(keep_cols, values):
                    print(f"    {col:25s} -> {val!r:40} -> {type(val)}")
                raise
            inserted += 1

    conn.commit()
    print(f"[load] {inserted} new facilities inserted, {updated} existing facilities updated "
          f"in {db_path}")
    conn.close()
