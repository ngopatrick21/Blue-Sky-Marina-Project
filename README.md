## Blue Sky Marina: Competitor Analysis & Data Pipeline

* Full stack data engineering and competitive intelligence project built to guide
go-to-market strategy for newly launching family-owned marina (Blue Sky Marina).
Operating in Antioch, CA, and under very scarce amounts of data.

## Project Overview
* Data Ingestion: Built automated scraping pipeline using 'requests' 
and custom Python parsers to extract facility records across regional Delta cities.

* Database & Integrity: Designed a relational SQLite schema ('facilities', 'pricing', 'reviews') with
upsert logic and unique constraint on facility names to prevent data-orphaning bugs.

* Analysis & Visualization: Wrote SQL analytic queries and built interactive Tableau dashboards to
benchmark pricing, capacity, and customer sentiment against regional competitors.

* Strategic Outcome: Identified optimal pricing and capacity measures pre-launch and focal points 
of customer satisfaction, translating all quantitative findings into an executive visual report
in Figma.

## Project structure

```
ETL/
  extract.py      -- fetches raw HTML from CA DBW's facility directory
  transform.py    -- filters to the 9 named competitors, cleans fields
  load.py         -- upserts clean data into SQLite (facility_name is
                      UNIQUE, so re-running is always safe)
run_pipeline.py        -- orchestrates the automated scrape (extract -> transform -> load)
load_manual_data.py    -- loads your manually-researched spreadsheet (pricing,
                           phone, address, amenities, top complaint/praise)
seed_known_ratings.py  -- one-time seed for Google rating/review count/website
marina_analysis_queries.sql -- 9 comparison queries (capacity, pricing,
                                 ratings, complaint themes, etc.)
run_queries.py         -- runs every query in the .sql file, saves each as
                           a CSV in analysis_output/ for Tableau
Marina_Analysis_filled.csv -- your finished manual research
```


All four scripts are safe to re-run anytime, in any order, as many times
as you want -- facility_name is a UNIQUE key in the database, so nothing
ever gets duplicated or orphaned, which was the recurring bug in earlier
versions of this project.

## If updating spreadsheet later:

1. Re-export: `python3 convert_numbers_to_csv.py --in Marina_Analysis_filled.numbers --out Marina_Analysis_filled.csv`
2. Re-run: `python3 load_manual_data.py --csv Marina_Analysis_filled.csv --db marina_analysis.db`
3. Re-run: `python3 run_queries.py --db marina_analysis.db --sql marina_analysis_queries.sql`
4. In Tableau, click the refresh icon (or Data -> Refresh) to pick up the updated CSVs.

## Live links

- Tableau Dashboard: *(add after publishing)*
- Figma Positioning Summary: *(add after publishing)*

## Tech stack
* Language: Python 3.9
* Data Processing: Pandas, NumPy
* Database: SQLite(database engine), SQL
* Visualization: Tableau
* Design & Layout: Figma
