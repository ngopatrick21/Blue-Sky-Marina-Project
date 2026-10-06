"""
transform.py -- the "T" in ETL.

Turns raw HTML (from extract.py) into clean, structured pandas DataFrames,
and filters the combined multi-city results down to just the specific
competitors relevant to Blue Sky Marina's business.

Nothing in this file makes network requests, and nothing in this file
writes to a database.
"""

import re
import pandas as pd
from bs4 import BeautifulSoup

FIELD_PATTERNS = {
    "address": r"Facility Address:\s*(.+)",
    "body_of_water": r"Body of Water:\s*(.+)",
    "county": r"County:\s*(.+)",
    "facility_type": r"Type of Facility:\s*(.+)",
    "open_to": r"Open To:\s*(.+)",
    "total_capacity": r"Total Capacity for Slips or Tie Ups:\s*(\d+)",
    "dry_storage_capacity": r"Dry Storage Capacity:\s*(\d+)",
    "min_boat_length": r"Minimum Boat Length:\s*(\d+)",
    "max_boat_length": r"Maximum Boat Length:\s*(\d+)",
}

# Confirmed via direct research (Google/business listings), not just DBW's
# directory -- some smaller private marinas aren't registered with the
# state at all, in which case the scraper simply won't find them, and
# that's expected, not a bug (use load_manual_data.py for those).
# "Lloyd's Holiday Harbor" (415 Fleming Lane, Antioch) IS Blue Sky Marina,
# confirmed by matching street address -- it's the baseline facility,
# not a competitor.
TARGET_FACILITIES = {
    "lloyd's holiday harbor": {"is_own_business": True},
    "new bridge marina": {"is_own_business": False},
    "driftwood marina": {"is_own_business": False},
    "lauritzen yacht harbor": {"is_own_business": False},
    "big break marina": {"is_own_business": False},
    "holland riverside marina": {"is_own_business": False},
    "cruiser haven marina": {"is_own_business": False},
    "sunset harbor marina & rv": {"is_own_business": False},
    "sunset harbor marina": {"is_own_business": False},  # name variant safeguard
    "discovery bay marina": {"is_own_business": False},
}


def transform_facility_list(raw_html: str) -> pd.DataFrame:
    """Turn one city's raw facility-list page HTML into a clean DataFrame of facilities + links."""
    soup = BeautifulSoup(raw_html, "html.parser")

    tables = pd.read_html(str(raw_html))
    if not tables:
        return pd.DataFrame(columns=["Facility Name", "detail_url"])
    facilities = tables[0]

    links = []
    for a_tag in soup.select("table a[href*='/BoatingFacilities/f/']"):
        name = a_tag.get_text(strip=True)
        href = a_tag.get("href")
        if not href.startswith("http"):
            href = "https://dbw.parks.ca.gov" + href
        links.append({"Facility Name": name, "detail_url": href})

    links_df = pd.DataFrame(links).drop_duplicates(subset="Facility Name")
    merged = facilities.merge(links_df, on="Facility Name", how="left")
    return merged


def transform_all_city_lists(city_html_map: dict[str, str]) -> pd.DataFrame:
    """
    Combine facility lists from multiple cities into one DataFrame, then
    filter down to ONLY the specific competitors in TARGET_FACILITIES.
    """
    all_frames = []
    for city, html in city_html_map.items():
        df = transform_facility_list(html)
        df["source_city"] = city
        all_frames.append(df)

    combined = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
    if combined.empty:
        return combined

    combined["_name_lower"] = combined["Facility Name"].str.lower().str.strip()
    filtered = combined[combined["_name_lower"].isin(TARGET_FACILITIES.keys())].copy()

    filtered["is_own_business"] = filtered["_name_lower"].map(
        lambda n: TARGET_FACILITIES[n]["is_own_business"]
    )
    filtered = filtered.drop(columns=["_name_lower"])

    found_names = set(filtered["Facility Name"].str.lower().str.strip())
    missing = set(TARGET_FACILITIES.keys()) - found_names
    if missing:
        print(f"[transform] Warning: these target facilities were not found "
              f"in any searched city and may need manual lookup via "
              f"load_manual_data.py: {missing}")

    return filtered.reset_index(drop=True)


def transform_facility_detail(raw_html: str) -> dict:
    """Turn one facility's raw detail-page HTML into a clean dict of fields."""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator="\n")

    result = {}
    for field, pattern in FIELD_PATTERNS.items():
        match = re.search(pattern, text)
        result[field] = match.group(1).strip() if match else None

    services_section = re.search(r"Services\s*\n(.*?)(?:Environmental Services|$)",
                                  text, re.DOTALL)
    services = []
    if services_section:
        raw = services_section.group(1)
        services = [s.strip() for s in raw.split("\n") if s.strip()]
    result["services_raw"] = "; ".join(services)

    return result


def transform_and_merge(facility_list_df: pd.DataFrame,
                         detail_pages: dict[str, str]) -> pd.DataFrame:
    """
    Combine the filtered facility list with parsed detail data into one
    clean, final DataFrame -- ready for the Load stage.
    """
    records = []
    for _, row in facility_list_df.iterrows():
        url = row.get("detail_url")
        if pd.isna(url) or url not in detail_pages:
            continue
        details = transform_facility_detail(detail_pages[url])
        details["Facility Name"] = row["Facility Name"]
        records.append(details)

    detail_df = pd.DataFrame(records)
    merged = facility_list_df.merge(detail_df, on="Facility Name", how="left")

    merged["capacity_data_missing"] = merged["total_capacity"].isna() & (
        merged["Type"].isin(["Marina", "Marina/DryStorage", "Yacht Club"])
    )

    return merged
