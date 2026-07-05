#!/usr/bin/env python3
"""Build consolidated Taco Bell locations JSON from All The Places."""

import hashlib
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "locations.json"

ATP_BASE = "https://data.alltheplaces.xyz/runs/latest/output"
SPIDERS = [
    "taco_bell_us",
    "taco_bell_ca",
    "taco_bell_gb",
    "taco_bell_au",
    "taco_bell_es",
    "taco_bell_in",
    "taco_bell_nl",
    "taco_bell_ph",
    "taco_bell_fi",
]

SPIDER_COUNTRY = {
    "taco_bell_us": "US",
    "taco_bell_ca": "CA",
    "taco_bell_gb": "GB",
    "taco_bell_au": "AU",
    "taco_bell_es": "ES",
    "taco_bell_in": "IN",
    "taco_bell_nl": "NL",
    "taco_bell_ph": "PH",
    "taco_bell_fi": "FI",
}

COUNTRY_NAMES = {
    "US": "United States",
    "CA": "Canada",
    "GB": "United Kingdom",
    "AU": "Australia",
    "ES": "Spain",
    "IN": "India",
    "NL": "Netherlands",
    "PH": "Philippines",
    "FI": "Finland",
    "JP": "Japan",
    "BR": "Brazil",
    "KR": "South Korea",
    "TH": "Thailand",
    "ID": "Indonesia",
    "PT": "Portugal",
    "CL": "Chile",
    "SV": "El Salvador",
    "GU": "Guam",
    "BA": "Bosnia and Herzegovina",
    "CY": "Cyprus",
    "FR": "France",
    "AR": "Argentina",
}

ATP_COUNTRIES = set(SPIDER_COUNTRY.values())
# OpenStreetMap fills gaps for countries without an All The Places spider.
OSM_COUNTRIES = ["JP", "BR", "KR", "TH", "ID", "PT", "CL", "SV", "GU", "BA", "CY", "FR", "AR"]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tacobell-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return value.strip("-")[:48] or "unknown"


def make_id(country: str, ref: str, lat: float, lng: float) -> str:
    if ref:
        return f"{country.lower()}-{slugify(ref)}"
    digest = hashlib.sha1(f"{lat:.5f},{lng:.5f}".encode()).hexdigest()[:10]
    return f"{country.lower()}-{digest}"


def extract_store_num(ref: str, props: dict) -> str:
    if not ref:
        return ""
    if ref.isdigit():
        return ref
    match = re.search(r"/(\d{4,6})(?:\.html|#|$)", ref)
    if match:
        return match.group(1)
    match = re.search(r"(\d{4,6})$", ref.strip("/"))
    if match:
        return match.group(1)
    return ref[:24]


def feature_to_location(feature: dict) -> dict | None:
    props = feature.get("properties", {})
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates")
    if not coords or len(coords) < 2:
        return None

    spider = props.get("@spider", "")
    country = (
        props.get("addr:country")
        or SPIDER_COUNTRY.get(spider)
        or "XX"
    )
    if len(country) > 2:
        country = {"United States": "US", "Canada": "CA", "Great Britain": "GB"}.get(
            country, country[:2].upper()
        )

    lng, lat = float(coords[0]), float(coords[1])
    ref = str(props.get("ref") or feature.get("id") or "")
    loc_id = make_id(country, ref, lat, lng)

    address = (
        props.get("addr:street_address")
        or props.get("addr:full")
        or props.get("addr_full")
        or ""
    ).strip()
    if not address and props.get("addr:housenumber") and props.get("addr:street"):
        address = f"{props['addr:housenumber']} {props['addr:street']}".strip()

    return {
        "id": loc_id,
        "storeNum": extract_store_num(ref, props),
        "name": props.get("name") or props.get("branch") or "Taco Bell",
        "address": address,
        "city": (props.get("addr:city") or "").strip(),
        "state": (props.get("addr:state") or "").strip(),
        "zip": (props.get("addr:postcode") or "").strip(),
        "country": country,
        "lat": lat,
        "lng": lng,
        "phone": (props.get("phone") or "").strip(),
    }


def dedupe(locations: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    unique: list[dict] = []
    for loc in locations:
        key = (loc["country"], round(loc["lat"], 4), round(loc["lng"], 4))
        if key in seen:
            continue
        seen.add(key)
        unique.append(loc)
    return unique


def fetch_spider(spider: str) -> list[dict]:
    url = f"{ATP_BASE}/{spider}.geojson"
    data = json.loads(fetch(url))
    locations = []
    for feature in data.get("features", []):
        loc = feature_to_location(feature)
        if loc:
            locations.append(loc)
    return locations


def osm_element_to_location(element: dict, country: str) -> dict | None:
    tags = element.get("tags", {})
    lat = element.get("lat") or (element.get("center") or {}).get("lat")
    lon = element.get("lon") or (element.get("center") or {}).get("lon")
    if lat is None or lon is None:
        return None

    lat, lon = float(lat), float(lon)
    ref = str(element.get("id", ""))
    loc_id = make_id(country, ref, lat, lon)

    address = tags.get("addr:full", "")
    if not address and tags.get("addr:street"):
        parts = [tags.get("addr:housenumber", ""), tags.get("addr:street", "")]
        address = " ".join(p for p in parts if p).strip()

    return {
        "id": loc_id,
        "storeNum": ref,
        "name": tags.get("name") or tags.get("brand") or "Taco Bell",
        "address": address,
        "city": tags.get("addr:city", "").strip(),
        "state": tags.get("addr:state", "").strip(),
        "zip": tags.get("addr:postcode", "").strip(),
        "country": country,
        "lat": lat,
        "lng": lon,
        "phone": tags.get("phone", "").strip(),
    }


def fetch_osm_country(country: str) -> list[dict]:
    import urllib.parse
    import time

    query = f'''[out:json][timeout:25];
area["ISO3166-1"="{country}"]->.searchArea;
(nwr["brand:wikidata"="Q752941"](area.searchArea););
out center;'''
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=data,
        headers={"User-Agent": "tacobell-tracker/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())

    locations = []
    for element in payload.get("elements", []):
        loc = osm_element_to_location(element, country)
        if loc:
            locations.append(loc)
    time.sleep(1)
    return locations


def fetch_osm_supplement() -> list[dict]:
    locations = []
    for country in OSM_COUNTRIES:
        if country in ATP_COUNTRIES:
            continue
        label = COUNTRY_NAMES.get(country, country)
        print(f"Fetching {label} from OpenStreetMap...")
        try:
            found = fetch_osm_country(country)
            print(f"  {len(found)} locations")
            locations.extend(found)
        except Exception as exc:
            print(f"  Failed: {exc}", file=sys.stderr)
    return locations


def main() -> None:
    all_locations: list[dict] = []

    for spider in SPIDERS:
        country = SPIDER_COUNTRY[spider]
        label = COUNTRY_NAMES.get(country, country)
        print(f"Fetching {label} ({spider})...")
        try:
            locations = fetch_spider(spider)
            locations = dedupe(locations)
            print(f"  {len(locations)} locations")
            all_locations.extend(locations)
        except Exception as exc:
            print(f"  Failed: {exc}", file=sys.stderr)

    print("\nSupplementing with OpenStreetMap for countries not in All The Places...")
    oms_locations = fetch_osm_supplement()
    all_locations.extend(oms_locations)

    all_locations = dedupe(all_locations)
    country_counts: dict[str, int] = {}
    for loc in all_locations:
        country_counts[loc["country"]] = country_counts.get(loc["country"], 0) + 1

    all_locations.sort(key=lambda loc: (loc["country"], loc["state"], loc["city"], loc["name"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": date.today().isoformat(),
        "source": "All The Places + OpenStreetMap",
        "count": len(all_locations),
        "countries": dict(sorted(country_counts.items(), key=lambda item: -item[1])),
        "locations": all_locations,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"\nWrote {len(all_locations)} locations across {len(country_counts)} countries")
    print(f"  File: {OUT}")
    print(f"  Size: {OUT.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
