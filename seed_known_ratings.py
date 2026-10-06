"""
seed_known_ratings.py

Seeds google_rating / google_review_count / website -- the data you
originally gathered into competitor_manual_data_template.csv, before this
rebuild. Marina_Analysis_filled.csv (loaded by load_manual_data.py)
doesn't carry these fields, so this script fills them in separately.

Run this ONCE after your first load_manual_data.py run. Safe to re-run
anytime -- matches by facility_name, so it's unaffected by facility_id.

Usage:
    python3 seed_known_ratings.py --db marina_analysis.db
"""

import argparse
import sqlite3

DATA = {
    "New Bridge Marina": (4.1, 20, "https://www.newbridgemarinainc.com/"),
    "Driftwood Marina": (4.4, 75, "http://www.driftwoodmarina.com/"),
    "Holland Riverside Marina": (4.3, 149, "https://www.hollandriverside.com/"),
    "Big Break Marina": (4.3, 217, "http://bigbreakmarina.com/"),
    "Lauritzen Yacht Harbor": (4.7, 66, "https://www.lauritzens.com/"),
    "Cruiser Haven Marina": (4.5, 45, "https://www.cruiserhaven.com/"),
    "Sunset Harbor Marina & RV": (4.4, 71, "http://sunsetmarinaca.com/"),
    "Discovery Bay Marina": (4.5, 253, "https://dbyhmarina.com/"),
}


def seed(db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    seeded = 0
    for name, (rating, count, website) in DATA.items():
        cur.execute(
            """UPDATE facilities
               SET google_rating = ?, google_review_count = ?, website = ?
               WHERE facility_name = ?""",
            (rating, count, website, name),
        )
        if cur.rowcount == 0:
            print(f"WARNING: '{name}' not found in facilities table -- "
                  f"run load_manual_data.py or run_pipeline.py first.")
        else:
            seeded += 1

    conn.commit()
    print(f"\nSeeded rating/website for {seeded} facilities.")

    cur.execute("SELECT facility_name, google_rating, google_review_count FROM facilities ORDER BY facility_id")
    for row in cur.fetchall():
        print(row)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed known rating/review/website data.")
    parser.add_argument("--db", default="marina_analysis.db")
    args = parser.parse_args()
    seed(args.db)
