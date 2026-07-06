#!/usr/bin/env python3
"""Scrape or import official Taco Bell locations for countries missing from the CSV."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from location_utils import (  # noqa: E402
    DATA,
    EXPORTS,
    Location,
    make_internal_id,
    save_json,
)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
ATP_BASE = "https://data.alltheplaces.xyz/runs/latest/output"
ES_API_TOKEN = (
    "s1ktt2qz7tiis5sut4yer4gv7mx4qm6h3u4erplzs7avaopwv5wotdpzj9f6cg85gqydxk07md86f2n1ykvgxjizcpnx6hloa3pxkphdilsab5fwnn0o950y5xx4igio"
)
UBERALL_GB_KEY = "oeY9DoIkFdLIquGvE5IQNv9wW53kHs"

SCRAPED_DIR = EXPORTS / "scraped"
SOURCES_FILE = DATA / "country_sources.json"


def fetch(url: str, headers: dict | None = None) -> bytes:
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def atp_feature_to_location(feature: dict, country: str, source_name: str) -> Location | None:
    props = feature.get("properties", {})
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates")
    if not coords:
        return None
    lng, lat = float(coords[0]), float(coords[1])
    store_id = str(props.get("ref") or "")
    source_url = props.get("website") or props.get("@source_uri") or ""
    address = props.get("addr:street_address") or props.get("addr:full") or ""
    return Location(
        internal_id=make_internal_id(country, lat, lng, store_id=store_id, source_url=source_url),
        store_id=store_id,
        name=props.get("name") or props.get("branch") or "Taco Bell",
        address=address,
        city=props.get("addr:city", ""),
        region=props.get("addr:state", ""),
        postal_code=props.get("addr:postcode", ""),
        country=props.get("addr:country") or country,
        latitude=lat,
        longitude=lng,
        phone=props.get("phone", ""),
        source_url=source_url,
        source_name=source_name,
    )


def scrape_atp(spider: str, country: str) -> list[Location]:
    data = json.loads(fetch(f"{ATP_BASE}/{spider}.geojson"))
    locations = []
    for feature in data.get("features", []):
        loc = atp_feature_to_location(feature, country, f"atp:{spider}")
        if loc:
            locations.append(loc)
    return locations


def scrape_es_api() -> list[Location]:
    locations: list[Location] = []
    offset = 0
    while True:
        url = (
            "https://loyalty-customer-api.pro.tacobell.es/public/store/list?"
            f"paginationMaxItems=100&paginationOffset={offset}&showOrder=distance&model.idStoreStatusStore=1"
        )
        payload = json.loads(fetch(url, headers={"X-Auth-Token": ES_API_TOKEN}))
        batch = payload.get("data", {}).get("list", [])
        if not batch:
            break
        for store in batch:
            lat = float(store["latitudeStore"])
            lng = float(store["longitudeStore"])
            store_id = str(store.get("idStore", ""))
            source_url = (
                f"https://tacobell.es/es/restaurantes/{store.get('cityStore', '').lower()}/"
                f"{store.get('idStore')}"
            )
            locations.append(
                Location(
                    internal_id=make_internal_id("ES", lat, lng, store_id=store_id),
                    store_id=store_id,
                    name=store.get("descriptionStore") or store.get("nameStore") or "Taco Bell",
                    address=store.get("addressStore", ""),
                    city=store.get("cityStore", ""),
                    region=store.get("nameProvince", ""),
                    postal_code=store.get("postCodeStore", ""),
                    country="ES",
                    latitude=lat,
                    longitude=lng,
                    source_url=source_url,
                    source_name="es_api",
                )
            )
        offset += len(batch)
        if len(batch) < 100:
            break
    return locations


def scrape_uberall_gb() -> list[Location]:
    payload = json.loads(
        fetch(f"https://uberall.com/api/storefinders/{UBERALL_GB_KEY}/locations/all")
    )
    locations = []
    for store in payload.get("response", {}).get("locations", []):
        lat = float(store["lat"])
        lng = float(store["lng"])
        store_id = str(store.get("identifier") or store.get("id", ""))
        source_url = (
            f"https://www.tacobell.co.uk/locations/l/"
            f"{store.get('city', '').lower().replace(' ', '-')}/"
            f"{store.get('streetAndNumber', '').lower().replace(' ', '-')}/"
            f"{store.get('id')}"
        )
        locations.append(
            Location(
                internal_id=make_internal_id("GB", lat, lng, store_id=store_id),
                store_id=store_id,
                name=store.get("name", "Taco Bell"),
                address=store.get("streetAndNumber", ""),
                city=store.get("city", ""),
                region=store.get("province", ""),
                postal_code=store.get("zip", ""),
                country="GB",
                latitude=lat,
                longitude=lng,
                phone=store.get("phone", ""),
                source_url=source_url,
                source_name="uberall_gb",
            )
        )
    return locations


def scrape_ca_store_locator() -> list[Location]:
    html = fetch("https://www.tacobell.ca/en/store-locator").decode("utf-8")
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    page_data = next((json.loads(s) for s in scripts if s.startswith('{"props"')), None)
    if not page_data:
        return []
    stores = page_data["props"]["pageProps"]["data"]["chainStores"]["msg"]
    locations = []
    for store in stores:
        store_id = store["id"]
        addr = store.get("address", {})
        lat_lng = addr.get("latLng", {})
        lat = float(lat_lng["lat"])
        lng = float(lat_lng["lng"])
        title = store.get("title", {}).get("en_US", "Taco Bell")
        source_url = f"https://www.tacobell.ca/en/store-locator#{store_id}"
        locations.append(
            Location(
                internal_id=make_internal_id("CA", lat, lng, store_id=store_id),
                store_id=store_id,
                name=title,
                address=addr.get("formatted", "").split(",")[0].strip(),
                city=addr.get("city", ""),
                country="CA",
                latitude=lat,
                longitude=lng,
                phone=store.get("contact", {}).get("phone", ""),
                source_url=source_url,
                source_name="ca_store_locator",
            )
        )
    return locations


def scrape_getjusto_country(url: str, country: str, source_name: str) -> list[Location]:
    html = fetch(url).decode("utf-8")
    match = re.search(r"window\.__remixContext\s*=\s*(\{.*?\});\s*</script>", html, re.DOTALL)
    if not match:
        return []

    def walk(obj):
        if isinstance(obj, dict):
            if "stores" in obj and isinstance(obj["stores"], list):
                return obj["stores"]
            for value in obj.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = walk(value)
                if found:
                    return found
        return None

    stores = walk(json.loads(match.group(1))) or []
    locations = []
    for store in stores:
        address = store.get("address") or {}
        location = address.get("location") or {}
        lat = float(location.get("lat") or 0)
        lng = float(location.get("lng") or 0)
        if not lat:
            continue
        store_id = str(store.get("_id", ""))
        source_url = f"{url.rstrip('/')}/?store={store_id}"
        locations.append(
            Location(
                internal_id=make_internal_id(country, lat, lng, store_id=store_id),
                store_id=store_id,
                name=store.get("name", "Taco Bell"),
                address=address.get("streetAddress", ""),
                city=address.get("locality", ""),
                region=address.get("region", ""),
                postal_code=address.get("postalCode", ""),
                country=country,
                latitude=lat,
                longitude=lng,
                source_url=source_url,
                source_name=source_name,
            )
        )
    return locations


SCRAPER_MAP = {
    "atp_geojson": lambda source: scrape_atp(source["spider"], source["country"]),
    "es_api": lambda _source: scrape_es_api(),
    "uberall_gb": lambda _source: scrape_uberall_gb(),
    "ca_store_locator": lambda _source: scrape_ca_store_locator(),
    "cl_getjusto": lambda _source: scrape_getjusto_country("https://www.tacobell.cl/", "CL", "cl_getjusto"),
    "pe_getjusto": lambda _source: scrape_getjusto_country("https://tacobell.com.pe/", "PE", "pe_getjusto"),
}


def load_sources() -> dict:
    if not SOURCES_FILE.exists():
        raise SystemExit(f"Run find_country_sources.py first. Missing {SOURCES_FILE}")
    return json.loads(SOURCES_FILE.read_text())


def scrape_missing(present_countries: set[str]) -> dict:
    catalog = load_sources()
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}

    for code, entry in catalog["countries"].items():
        if entry["in_csv"] and code in present_countries:
            continue
        if entry["status"] in {"no_official_locations", "unavailable", "osm_only"}:
            summary[code] = {"skipped": True, "reason": entry["status"], "count": 0}
            continue

        country_locations: list[Location] = []
        errors = []
        for source in entry.get("official_sources", []):
            scraper_name = source.get("scraper")
            scraper = SCRAPER_MAP.get(scraper_name)
            if not scraper:
                errors.append(f"unsupported scraper: {scraper_name}")
                continue
            source_with_country = dict(source)
            source_with_country["country"] = code
            try:
                country_locations.extend(scraper(source_with_country))
            except Exception as exc:
                errors.append(f"{scraper_name}: {exc}")

        if country_locations:
            out = SCRAPED_DIR / f"{code.lower()}.json"
            save_json(out, {"country": code, "locations": [loc.__dict__ for loc in country_locations]})
        summary[code] = {
            "count": len(country_locations),
            "errors": errors,
            "output": str(SCRAPED_DIR / f"{code.lower()}.json") if country_locations else "",
        }
        print(f"{code}: scraped {len(country_locations)} locations")

    save_json(SCRAPED_DIR / "scrape_summary.json", summary)
    return summary


def scrape_official_refresh() -> dict:
    """Re-scrape official sources for all countries with supported scrapers."""
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}

    jobs = [
        ("US", "atp_geojson", {"spider": "taco_bell_us", "country": "US"}),
        ("CA", "ca_store_locator", {}),
        ("GB", "uberall_gb", {}),
        ("ES", "es_api", {}),
        ("AU", "atp_geojson", {"spider": "taco_bell_au", "country": "AU"}),
        ("IN", "atp_geojson", {"spider": "taco_bell_in", "country": "IN"}),
        ("NL", "atp_geojson", {"spider": "taco_bell_nl", "country": "NL"}),
        ("PH", "atp_geojson", {"spider": "taco_bell_ph", "country": "PH"}),
        ("FI", "atp_geojson", {"spider": "taco_bell_fi", "country": "FI"}),
        ("CL", "cl_getjusto", {}),
        ("PE", "pe_getjusto", {}),
    ]

    for country, scraper_name, source in jobs:
        scraper = SCRAPER_MAP[scraper_name]
        try:
            locations = scraper(source)
            out = SCRAPED_DIR / f"{country.lower()}.json"
            save_json(out, {"country": country, "locations": [loc.__dict__ for loc in locations]})
            summary[country] = {"count": len(locations), "output": str(out)}
            print(f"{country}: refreshed {len(locations)} official locations")
        except Exception as exc:
            summary[country] = {"count": 0, "error": str(exc)}
            print(f"{country}: failed ({exc})")

    save_json(SCRAPED_DIR / "scrape_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape official Taco Bell country sources")
    parser.add_argument("--missing-only", action="store_true", help="Only scrape countries not in CSV")
    parser.add_argument("--countries", nargs="*", help="Limit to specific country codes")
    args = parser.parse_args()

    if args.missing_only:
        catalog = load_sources()
        present = set(catalog["countries_in_csv"])
        scrape_missing(present)
    else:
        scrape_official_refresh()


if __name__ == "__main__":
    main()
