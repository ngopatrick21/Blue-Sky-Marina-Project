"""
load.py -- the "L" in ETL.

Writes already-clean data (from transform.py) into the SQLite database.
Does not fetch anything from the web, and does not clean or reshape data.

IMPORTANT DESIGN NOTE #1 (why facility_name has a UNIQUE constraint):
earlier versions of this project re-ran run_pipeline.py and ended up
creating brand-new facility_id numbers for the same marinas every time,
which silently orphaned all the pricing and review data linked to the
old ids. The UNIQUE constraint below plus the upsert(update if exists, insert if not)
logic makes that class of bug structurally impossible: a given facility_name can only
ever correspond to ONE row, ever, no matter how many times the pipeline runs.

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

# table for the facilities
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
# table for the reviews
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
# table for the pricing
# uses foreign key constraints on delete cascade, to ensure that if a facility is updated or removed
# the related pricing and review records stay properly linked
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

# conversion so that python is in its rawest form before SQL interaction
def to_native(value):
    """Convert a pandas/numpy value to a plain Python type SQLite can always bind,
    or None for any flavor of missing value (NaN, pandas.NA, numpy.nan)."""
    # if the value is already Python's standard missing value
    if value is None:
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    # catching boolean and integer types (np.bool and np.int64) and conerts
    # to True/False and int
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    # check NaN first to convert to None for SQL NULL
    # real number? float
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass  # pd.isna() chokes on some types (e.g. lists) -- just pass the value through
    # pd.isna is python's way of handling missing data but
    # try except will handle crashes from complex retrievals
    return value


def load_facilities(clean_df: pd.DataFrame, db_path: str):
    """Create the schema (if needed) and upsert clean facility data into SQLite."""

    # 1. Establish connection to the SQLite database file
    conn = sqlite3.connect(db_path)

    # Force SQLite to enforce foreign key rules (crucial for relational integrity)
    conn.execute("PRAGMA foreign_keys = ON")

    # Create a cursor object to execute SQL commands
    cur = conn.cursor()

    # 2. Run schema creation strings to build tables if they don't already exist
    cur.execute(CREATE_FACILITIES_TABLE)
    cur.execute(CREATE_REVIEWS_TABLE)
    cur.execute(CREATE_PRICING_TABLE)
    conn.commit()  # Save table creation changes to the database

    # 3. Align DataFrame columns with database column names using our mapping dictionary
    df_renamed = clean_df.rename(columns=COLUMN_MAP)

    # Filter down to only the columns that actually exist in the renamed dataframe
    keep_cols = [c for c in COLUMN_MAP.values() if c in df_renamed.columns]
    df_final = df_renamed[keep_cols]

    # DIAGNOSTIC: Check if any column names accidentally got duplicated
    # (Duplicate columns cause pandas row lookup to return a Series instead of a single value, crashing the loader)
    dupes = df_final.columns[df_final.columns.duplicated()].tolist()
    if dupes:
        print(f"[load] WARNING: duplicate column names detected: {dupes} -- "
              f"this WILL cause binding errors. Check transform.py for a field "
              f"name collision (e.g. 'Type' renaming to the same name as an "
              f"already-present 'facility_type' column).")

    # Track how many rows are brand new vs updated
    inserted, updated = 0, 0

    # 4. Iterate through every row of your clean dataframe one by one
    for idx, row in df_final.iterrows():
        # Clean the facility name to make sure it's a raw Python string
        name = to_native(row["facility_name"])

        # Check the database to see if this marina already exists (prevents duplicate rows)
        cur.execute("SELECT facility_id FROM facilities WHERE facility_name = ?", (name,))
        existing = cur.fetchone()

        # 5. UPSERT LOGIC: If the marina already exists, UPDATE its info
        if existing:
            other_cols = [c for c in keep_cols if c != "facility_name"]
            set_clause = ", ".join(f"{col} = ?" for col in other_cols)
            values = [to_native(row[col]) for col in other_cols]

            try:
                # Try running the SQL update query
                cur.execute(f"UPDATE facilities SET {set_clause} WHERE facility_id = ?",
                            values + [existing[0]])
            except (sqlite3.InterfaceError, sqlite3.ProgrammingError):
                # ERROR CATCHER: If SQL crashes on an update, print the exact column and data type that failed
                print(f"\n[load] FAILED on row {idx} (facility_name={name!r}), UPDATE. "
                      f"Column -> value -> type:")
                for col, val in zip(other_cols, values):
                    print(f"    {col:25s} -> {val!r:40} -> {type(val)}")
                raise
            updated += 1

        # 6. UPSERT LOGIC: If it doesn't exist yet, INSERT a brand new row
        else:
            cols_clause = ", ".join(keep_cols)
            placeholders = ", ".join("?" for _ in keep_cols)
            values = [to_native(row[col]) for col in keep_cols]

            try:
                # Try running the SQL insert query
                cur.execute(f"INSERT INTO facilities ({cols_clause}) VALUES ({placeholders})", values)
            except (sqlite3.InterfaceError, sqlite3.ProgrammingError):
                # ERROR CATCHER: If SQL crashes on an insert, print the exact column and data type that failed
                print(f"\n[load] FAILED on row {idx} (facility_name={name!r}), INSERT. "
                      f"Column -> value -> type:")
                for col, val in zip(keep_cols, values):
                    print(f"    {col:25s} -> {val!r:40} -> {type(val)}")
                raise
            inserted += 1

    # 7. Save all changes permanently to the database file and close the connection
    conn.commit()
    print(f"[load] {inserted} new facilities inserted, {updated} existing facilities updated "
          f"in {db_path}")
    conn.close()