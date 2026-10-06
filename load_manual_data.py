"""
load_manual_data.py

Simple script to load manual competitor data and capacity into SQLite.
"""

import argparse
import sqlite3
import pandas as pd

EXPECTED_COLUMNS = [
    "facility_name", "address", "contact_info", "slip_price_raw",
    "size_covered_raw", "storage_price_raw", "launch_fee_raw",
    "fuel_available", "amenities_raw", "top_complaint", "top_praise"
]

# Explicit manual capacity mapping (easy to explain and maintain)
MANUAL_CAPACITIES = {
    "New Bridge Marina": 185,
    "Driftwood Marina": 210,
    "Holland Riverside Marina": 300,
    "Big Break Marina": 120,
    "Lauritzen Yacht Harbor": 138,
    "Cruiser Haven Marina": 130,
    "Sunset Harbor Marina & RV": 64,
    "Discovery Bay Marina": 263,
    "Lloyd's Holiday Harbor": 125
}

def load(csv_path, db_path):
    # Read the CSV with auto-detected delimiter to prevent column mismatch
    df = pd.read_csv(csv_path, sep=None, engine='python')

    # If the file header or columns are off, map them safely by position
    if len(df.columns) != len(EXPECTED_COLUMNS):
        # Fallback: assign expected columns by index if header count differs
        df = pd.read_csv(csv_path, sep=None, engine='python', header=None, skiprows=1)
        df.columns = EXPECTED_COLUMNS
    else:
        df.columns = EXPECTED_COLUMNS

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    updated_count = 0

    for index, row in df.iterrows():
        name = str(row["facility_name"]).strip()
        address = str(row["address"])
        phone = str(row["contact_info"])
        amenities = str(row["amenities_raw"])

        capacity = MANUAL_CAPACITIES.get(name)

        cur.execute("SELECT facility_id FROM facilities WHERE facility_name = ?", (name,))
        result = cur.fetchone()

        if result:
            facility_id = result[0]
            cur.execute("""
                        UPDATE facilities
                        SET address = ?, phone_number = ?, services_raw = ?, total_capacity = COALESCE(?, total_capacity)
                        WHERE facility_id = ?
                        """, (address, phone, amenities, capacity, facility_id))
        else:
            cur.execute("""
                        INSERT INTO facilities (facility_name, address, phone_number, services_raw, total_capacity, is_own_business)
                        VALUES (?, ?, ?, ?, ?, 0)
                        """, (name, address, phone, amenities, capacity))

        updated_count += 1

    conn.commit()
    conn.close()

    print(f"[load_manual_data] Successfully processed {updated_count} facilities with manual capacities.")