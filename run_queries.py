"""
run_queries.py

Runs every query in marina_analysis_queries.sql against marina_analysis.db
and saves each result as its own CSV in an `analysis_output/` folder --
ready to import into Tableau Public.

Usage:
    python run_queries.py --db marina_analysis.db --sql marina_analysis_queries.sql
"""

import argparse
import os
import re
import sqlite3
import pandas as pd


def split_queries(sql_text: str):
    """
    Split the .sql file into (title, statement) pairs using the
    '-- N. TITLE' comment headers already in the file.
    """
    # Each query block starts with a line like "-- 1. CAPACITY COMPARISON"
    blocks = re.split(r"\n-- (\d+)\. ", sql_text)
    # blocks[0] is the file header before query 1 -- discard it
    pairs = []
    for i in range(1, len(blocks), 2):
        number = blocks[i]
        rest = blocks[i + 1]
        title_line, _, remainder = rest.partition("\n")
        title = title_line.strip()
        # Strip any remaining comment lines, keep the actual SQL
        sql_lines = [line for line in remainder.split("\n") if not line.strip().startswith("--")]
        statement = "\n".join(sql_lines).strip().rstrip(";")
        pairs.append((f"{number}_{title}", statement))
    return pairs


def run_all(db_path: str, sql_path: str, out_dir: str = "analysis_output"):
    os.makedirs(out_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)

    sql_text = open(sql_path).read()
    queries = split_queries(sql_text)

    for name, statement in queries:
        safe_name = re.sub(r"[^\w]+", "_", name).strip("_").lower()
        try:
            df = pd.read_sql_query(statement, conn)
            out_path = os.path.join(out_dir, f"{safe_name}.csv")
            df.to_csv(out_path, index=False)
            print(f"[{name}] {len(df)} rows -> {out_path}")
        except Exception as e:
            print(f"[{name}] ERROR: {e}")

    conn.close()
    print(f"\nDone. All CSVs are in ./{out_dir}/ -- import these into Tableau Public.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run all marina analysis SQL queries and export to CSV.")
    parser.add_argument("--db", default="marina_analysis.db")
    parser.add_argument("--sql", default="marina_analysis_queries.sql")
    parser.add_argument("--out", default="analysis_output")
    args = parser.parse_args()

    run_all(args.db, args.sql, args.out)
