# Blue Sky Marina Competitor Analysis

Competitor pricing/positioning analysis for Blue Sky Marina (formerly
Lloyd's Holiday Harbor), built from public boating-facility data plus
manually-researched pricing, ratings, and reviews.

## Project structure

```
ETL/
  extract.py      -- fetches raw HTML from CA DBW's facility directory
  transform.py    -- filters to the 8 named competitors, cleans fields
  load.py         -- upserts clean data into SQLite (facility_name is
                      UNIQUE, so re-running is always safe)
run_pipeline.py        -- orchestrates the automated scrape (extract -> transform -> load)
load_manual_data.py    -- loads your manually-researched spreadsheet (pricing,
                           phone, address, amenities, top complaint/praise)
seed_known_ratings.py  -- one-time seed for Google rating/review count/website
convert_numbers_to_csv.py -- converts a .numbers file to CSV directly
marina_analysis_queries.sql -- 8 comparison queries (capacity, pricing,
                                 ratings, complaint themes, etc.)
run_queries.py         -- runs every query in the .sql file, saves each as
                           a CSV in analysis_output/ for Tableau
Marina_Analysis_filled.csv -- your finished manual research
```

## Run order (first time)

```bash
pip install -r requirements.txt

# 1. Automated scrape (requires internet access to dbw.parks.ca.gov)
python3 run_pipeline.py --db marina_analysis.db

# 2. Your manually-researched pricing/reviews data
python3 load_manual_data.py --csv Marina_Analysis_filled.csv --db marina_analysis.db

# 3. One-time: seed the Google rating/review/website data
python3 seed_known_ratings.py --db marina_analysis.db

# 4. Run all analysis queries, export CSVs for Tableau
python3 run_queries.py --db marina_analysis.db --sql marina_analysis_queries.sql
```

All four scripts are safe to re-run anytime, in any order, as many times
as you want -- facility_name is a UNIQUE key in the database, so nothing
ever gets duplicated or orphaned, which was the recurring bug in earlier
versions of this project.

## If you update your spreadsheet later

1. Re-export: `python3 convert_numbers_to_csv.py --in Marina_Analysis_filled.numbers --out Marina_Analysis_filled.csv`
2. Re-run: `python3 load_manual_data.py --csv Marina_Analysis_filled.csv --db marina_analysis.db`
3. Re-run: `python3 run_queries.py --db marina_analysis.db --sql marina_analysis_queries.sql`
4. In Tableau, click the refresh icon (or Data -> Refresh) to pick up the updated CSVs.

## Live links

- Tableau Dashboard: *(add after publishing)*
- Figma Positioning Summary: *(add after publishing)*

## Tech stack

Python (requests, BeautifulSoup, pandas), SQLite, Tableau Public, Figma.
