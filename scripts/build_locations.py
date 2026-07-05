#!/usr/bin/env python3
"""Build consolidated Taco Bell locations JSON from public data sources."""

import csv
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "locations.json"

US_CSV_URL = (
    "https://raw.githubusercontent.com/stiles/locations/main/"
    "taco-bell/data/processed/taco-bell_locations.csv"
)
UK_JSON_URL = (
    "https://gist.githubusercontent.com/SteGriff/"
    "00ed26790b028c06200d56041e6ba23f/raw/tacobell-locations.json"
)
CA_LOCATOR_URL = "https://www.tacobell.ca/en/store-locator"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tacobell-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def parse_us_locations() -> list[dict]:
    raw = fetch(US_CSV_URL).decode("utf-8")
    locations = []
    for row in csv.DictReader(raw.splitlines()):
        store_num = row.get("store_num", "").strip()
        if not store_num:
            continue
        locations.append(
            {
                "id": f"us-{store_num}",
                "storeNum": store_num,
                "name": "Taco Bell",
                "address": row.get("address", "").strip(),
                "city": row.get("city", "").strip(),
                "state": row.get("state_abbr", "").strip(),
                "zip": row.get("zip", "").strip(),
                "country": "US",
                "lat": float(row["latitude"]),
                "lng": float(row["longitude"]),
                "phone": row.get("phone", "").strip(),
            }
        )
    return locations


def parse_uk_locations() -> list[dict]:
    data = json.loads(fetch(UK_JSON_URL))
    stores = data.get("data", data)
    locations = []
    for store in stores:
        store_num = str(store.get("store_number", store.get("id", "")))
        locations.append(
            {
                "id": f"uk-{store_num}",
                "storeNum": store_num,
                "name": store.get("name", "Taco Bell"),
                "address": store.get("address_line_1", "").strip(),
                "city": store.get("city", "").strip(),
                "state": store.get("county", "").strip(),
                "zip": store.get("post_code", "").strip(),
                "country": "GB",
                "lat": float(store["latitude"]),
                "lng": float(store["longitude"]),
                "phone": store.get("telephone", "").strip(),
            }
        )
    return locations


def parse_ca_locations() -> list[dict]:
    html = fetch(CA_LOCATOR_URL).decode("utf-8")
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    page_data = None
    for script in scripts:
        if script.startswith('{"props"'):
            page_data = json.loads(script)
            break
    if not page_data:
        raise RuntimeError("Could not find store data on tacobell.ca")

    stores = page_data["props"]["pageProps"]["data"]["chainStores"]["msg"]
    locations = []
    for store in stores:
        store_id = store["id"]
        title = store.get("title", {}).get("en_US", "Taco Bell")
        addr = store.get("address", {})
        lat_lng = addr.get("latLng", {})
        locations.append(
            {
                "id": f"ca-{store_id[:8]}",
                "storeNum": store_id[:8],
                "name": title,
                "address": addr.get("formatted", "").split(",")[0].strip(),
                "city": addr.get("city", "").strip(),
                "state": "",
                "zip": "",
                "country": "CA",
                "lat": float(lat_lng["lat"]),
                "lng": float(lat_lng["lng"]),
                "phone": store.get("contact", {}).get("phone", "").strip(),
            }
        )
    return locations


def main() -> None:
    print("Fetching US locations...")
    us = parse_us_locations()
    print(f"  {len(us)} US locations")

    print("Fetching UK locations...")
    uk = parse_uk_locations()
    print(f"  {len(uk)} UK locations")

    print("Fetching Canada locations...")
    ca = parse_ca_locations()
    print(f"  {len(ca)} Canada locations")

    all_locations = us + ca + uk
    all_locations.sort(key=lambda loc: (loc["country"], loc["state"], loc["city"], loc["name"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": date.today().isoformat(),
        "count": len(all_locations),
        "countries": {
            "US": len(us),
            "CA": len(ca),
            "GB": len(uk),
        },
        "locations": all_locations,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"\nWrote {len(all_locations)} locations to {OUT}")
    print(f"  File size: {OUT.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
