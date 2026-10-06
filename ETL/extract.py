"""
extract.py -- the "E" in ETL.

This module's ONLY job is fetching raw data from a source (the DBW
website). It does not clean, reshape, or interpret the data at all --
that's the Transform stage's job.
"""

import time
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (personal research project; contact: your_email@berkeley.edu)"
}

FACILITY_LIST_URL = "https://dbw.parks.ca.gov/BoatingFacilities/City/{city}"

# The Delta boating region spans several city boundaries in DBW's system --
# real competitors (Driftwood, Lauritzen, Big Break, etc.) are NOT all
# filed under "Antioch," even though they're right across the river.
# Searching just one city silently misses real competitors.
DELTA_REGION_CITIES = [
    "Antioch",
    "Oakley",
    "Bethel Island",
    "Pittsburg",
    "Discovery Bay",
    "Brentwood",
]


def extract_facility_list_html(city: str) -> str:
    """Fetch the raw HTML of the facility list page for a single city."""
    url = FACILITY_LIST_URL.format(city=city.replace(" ", "%20"))
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def extract_all_city_lists(cities: list[str] = None) -> dict[str, str]:
    """
    Fetch raw HTML for every city in the Delta region (or a custom list).
    Returns {city_name: raw_html}. One request per city, with a polite delay.
    """
    cities = cities or DELTA_REGION_CITIES
    pages = {}
    for city in cities:
        print(f"[extract] Fetching facility list for {city}")
        try:
            pages[city] = extract_facility_list_html(city)
        except requests.HTTPError as e:
            print(f"  [warning] Could not fetch {city}: {e}")
        time.sleep(1)
    return pages


def extract_facility_detail_html(detail_url: str) -> str:
    """Fetch the raw HTML of a single facility's detail page. Returns raw text only."""
    resp = requests.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def extract_all_detail_pages(detail_urls: list[str], delay_seconds: float = 1.5) -> dict[str, str]:
    """
    Fetch raw HTML for a list of detail page URLs, being polite to the server
    with a short delay between requests. Returns {url: raw_html}.
    """
    pages = {}
    for url in detail_urls:
        print(f"[extract] Fetching {url}")
        pages[url] = extract_facility_detail_html(url)
        time.sleep(delay_seconds)
    return pages
