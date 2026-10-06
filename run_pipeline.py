"""
run_pipeline.py -- orchestrates the full ETL pipeline, one stage at a time.

Searches multiple Delta-region cities (since real competitors span city
boundaries) and filters down to your specific named competitor list.

Safe to re-run anytime: load.py upserts by facility_name, so re-running
this will refresh existing facilities in place rather than creating
duplicates or orphaning pricing/review data.

Usage:
    python run_pipeline.py --db marina_analysis.db
"""

import argparse
from ETL import extract, transform, load


def run(db_path: str):
    print("=== ETL Pipeline: Blue Sky Marina Competitor Analysis ===\n")

    print("[1/4] EXTRACT: fetching facility lists across Delta-region cities...")
    city_html_map = extract.extract_all_city_lists()

    print("\n[2/4] TRANSFORM: combining cities and filtering to target competitors...")
    facility_list_df = transform.transform_all_city_lists(city_html_map)
    print(facility_list_df[["Facility Name", "source_city", "is_own_business"]])

    detail_urls = facility_list_df["detail_url"].dropna().tolist()

    print(f"\n[3/4] EXTRACT: fetching detail pages for {len(detail_urls)} target facilities...")
    raw_detail_pages = extract.extract_all_detail_pages(detail_urls)

    clean_df = transform.transform_and_merge(facility_list_df, raw_detail_pages)

    missing_count = clean_df["capacity_data_missing"].sum()
    if missing_count > 0:
        print(f"  [data quality] {missing_count} facilities are missing capacity data "
              f"-- these will need manual follow-up (check their own website).")

    print("\n[4/4] LOAD: writing clean data into the database...")
    load.load_facilities(clean_df, db_path)

    print("\n=== Pipeline complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Blue Sky Marina competitor ETL pipeline.")
    parser.add_argument("--db", default="marina_analysis.db", help="Output SQLite database path")
    args = parser.parse_args()

    run(args.db)
