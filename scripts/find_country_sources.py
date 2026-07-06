#!/usr/bin/env python3
"""Research and catalog official Taco Bell location sources by country."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from location_utils import COUNTRY_NAMES, DATA, EXPORTS, count_by_country, load_legacy_csv, save_json  # noqa: E402

DEFAULT_INPUT = EXPORTS / "all-tacobell-locations.csv"
DEFAULT_OUTPUT = DATA / "country_sources.json"

USER_AGENT = "tacobell-tracker/1.0 (location audit)"

# Curated from official Taco Bell/Yum country sites and All The Places spider coverage.
# status: active | blocked | unavailable | no_official_locations
COUNTRY_SOURCE_CATALOG = {
    "US": {
        "official_sources": [
            {
                "name": "Taco Bell US Store Locator",
                "url": "https://locations.tacobell.com/",
                "type": "sitemap",
                "scraper": "atp_geojson",
                "spider": "taco_bell_us",
            }
        ],
        "status": "active",
    },
    "CA": {
        "official_sources": [
            {
                "name": "Taco Bell Canada Store Locator",
                "url": "https://www.tacobell.ca/en/store-locator",
                "type": "embedded_json",
                "scraper": "ca_store_locator",
            },
            {
                "name": "Taco Bell Canada Locations Sitemap",
                "url": "https://locations.tacobell.ca/sitemap.xml",
                "type": "sitemap",
                "scraper": "atp_geojson",
                "spider": "taco_bell_ca",
            },
        ],
        "status": "active",
    },
    "GB": {
        "official_sources": [
            {
                "name": "Taco Bell UK Uberall Store Finder",
                "url": "https://www.tacobell.co.uk/restaurants",
                "type": "api",
                "scraper": "uberall_gb",
            },
            {
                "name": "ATP Taco Bell UK",
                "url": "https://data.alltheplaces.xyz/runs/latest/output/taco_bell_gb.geojson",
                "type": "geojson",
                "scraper": "atp_geojson",
                "spider": "taco_bell_gb",
            },
        ],
        "status": "active",
    },
    "ES": {
        "official_sources": [
            {
                "name": "Taco Bell Spain Store API",
                "url": "https://loyalty-customer-api.pro.tacobell.es/public/store/list",
                "type": "api",
                "scraper": "es_api",
            }
        ],
        "status": "active",
    },
    "AU": {
        "official_sources": [
            {
                "name": "Taco Bell Australia Locations",
                "url": "https://tacobell.com.au/order-now-locations/",
                "type": "html",
                "scraper": "atp_geojson",
                "spider": "taco_bell_au",
            },
        ],
        "status": "active",
    },
    "IN": {
        "official_sources": [
            {
                "name": "Taco Bell India Find Us",
                "url": "https://www.tacobell.co.in/find-us",
                "type": "html",
                "scraper": "atp_geojson",
                "spider": "taco_bell_in",
            },
        ],
        "status": "active",
    },
    "NL": {
        "official_sources": [
            {
                "name": "Taco Bell Netherlands Locations",
                "url": "https://tacobell.nl/en/locations/",
                "type": "html",
                "scraper": "atp_geojson",
                "spider": "taco_bell_nl",
            },
        ],
        "status": "active",
    },
    "PH": {
        "official_sources": [
            {
                "name": "Taco Bell Philippines Locations",
                "url": "https://tacobell.com.ph/locations/",
                "type": "html",
                "scraper": "atp_geojson",
                "spider": "taco_bell_ph",
            },
        ],
        "status": "active",
    },
    "FI": {
        "official_sources": [
            {
                "name": "Taco Bell Finland Restaurants",
                "url": "https://tacobell.fi/ravintolat/",
                "type": "html",
                "scraper": "atp_geojson",
                "spider": "taco_bell_fi",
            },
        ],
        "status": "active",
    },
    "MY": {
        "official_sources": [
            {
                "name": "Taco Bell Malaysia Locations",
                "url": "https://tacobell.com.my/locations/",
                "type": "html",
                "scraper": "my_locations",
            },
        ],
        "status": "blocked",
        "notes": "Cloudflare protection observed during probing; scraper may fail without browser automation.",
    },
    "TH": {
        "official_sources": [
            {
                "name": "Taco Bell Thailand",
                "url": "https://tacobell.co.th/",
                "type": "html",
                "scraper": "th_locations",
            },
        ],
        "status": "active",
    },
    "CL": {
        "official_sources": [
            {
                "name": "Taco Bell Chile",
                "url": "https://www.tacobell.cl/",
                "type": "embedded_json",
                "scraper": "cl_getjusto",
            },
        ],
        "status": "active",
    },
    "PE": {
        "official_sources": [
            {
                "name": "Taco Bell Peru",
                "url": "https://tacobell.com.pe/",
                "type": "embedded_json",
                "scraper": "pe_getjusto",
            },
        ],
        "status": "active",
    },
    "CO": {
        "official_sources": [
            {
                "name": "Taco Bell Colombia",
                "url": "https://tacobell.com.co/",
                "type": "html",
                "scraper": "co_locations",
            },
        ],
        "status": "blocked",
    },
    "CR": {
        "official_sources": [
            {
                "name": "Taco Bell Costa Rica",
                "url": "https://tacobell.cr/",
                "type": "html",
                "scraper": "cr_locations",
            },
        ],
        "status": "blocked",
    },
    "PA": {
        "official_sources": [
            {
                "name": "Taco Bell Panama",
                "url": "https://tacobell.com.pa/",
                "type": "html",
                "scraper": "pa_locations",
            },
        ],
        "status": "blocked",
    },
    "GT": {
        "official_sources": [
            {
                "name": "Taco Bell Guatemala",
                "url": "https://tacobell.com.gt/",
                "type": "html",
                "scraper": "gt_locations",
            },
        ],
        "status": "unknown",
    },
    "DO": {
        "official_sources": [
            {
                "name": "Taco Bell Dominican Republic",
                "url": "https://tacobell.com.do/",
                "type": "html",
                "scraper": "do_locations",
            },
        ],
        "status": "unknown",
    },
    "KR": {
        "official_sources": [],
        "status": "unavailable",
        "notes": "No official Taco Bell Korea locator URL found during research.",
    },
    "MX": {
        "official_sources": [],
        "status": "no_official_locations",
        "notes": "Taco Bell previously operated in Mexico but closed all locations; no official locator.",
    },
    "RO": {
        "official_sources": [
            {
                "name": "Taco Bell Romania",
                "url": "https://tacobell.ro/",
                "type": "html",
                "scraper": "ro_locations",
            },
        ],
        "status": "unavailable",
        "notes": "Domain appears parked/unavailable.",
    },
    "SE": {
        "official_sources": [
            {
                "name": "Taco Bell Sweden",
                "url": "https://tacobell.se/en/locations/",
                "type": "html",
                "scraper": "se_locations",
            },
        ],
        "status": "unavailable",
        "notes": "Domain appears parked/unavailable.",
    },
    "AE": {
        "official_sources": [
            {
                "name": "Taco Bell UAE",
                "url": "https://tacobell.ae/locations/",
                "type": "html",
                "scraper": "ae_locations",
            },
        ],
        "status": "unavailable",
    },
    "OM": {"official_sources": [], "status": "unknown", "notes": "No official locator URL confirmed."},
    "KW": {"official_sources": [], "status": "unknown", "notes": "No official locator URL confirmed."},
    "SA": {"official_sources": [], "status": "unknown", "notes": "No official locator URL confirmed."},
    "JP": {
        "official_sources": [],
        "status": "osm_only",
        "notes": "Current CSV uses OpenStreetMap supplement; no stable official locator confirmed.",
    },
    "BR": {
        "official_sources": [],
        "status": "osm_only",
        "notes": "Current CSV uses OpenStreetMap supplement; no stable official locator confirmed.",
    },
    "PT": {
        "official_sources": [],
        "status": "osm_only",
        "notes": "Current CSV uses OpenStreetMap supplement; no stable official locator confirmed.",
    },
}


def probe_url(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return {"url": url, "reachable": True, "http_status": resp.status}
    except Exception as exc:
        return {"url": url, "reachable": False, "error": str(exc)}


def build_source_list(input_path: Path, probe: bool = False) -> dict:
    csv_counts = {}
    if input_path.exists():
        csv_counts = count_by_country(load_legacy_csv(input_path))

    countries = {}
    for code, meta in COUNTRY_SOURCE_CATALOG.items():
        entry = {
            "country": code,
            "name": COUNTRY_NAMES.get(code, code),
            "in_csv": code in csv_counts,
            "csv_count": csv_counts.get(code, 0),
            "official_sources": meta.get("official_sources", []),
            "status": meta.get("status", "unknown"),
            "notes": meta.get("notes", ""),
            "source_checks": (
                [probe_url(src["url"]) for src in meta.get("official_sources", []) if src.get("url")]
                if probe
                else []
            ),
        }
        countries[code] = entry

    present = sorted(csv_counts.keys())
    missing_likely = [
        code for code, entry in countries.items()
        if not entry["in_csv"] and entry["status"] not in {"no_official_locations", "unavailable", "osm_only"}
    ]

    return {
        "generated_from_csv": str(input_path),
        "countries_in_csv": present,
        "countries_in_csv_count": len(present),
        "likely_missing_countries": missing_likely,
        "countries": countries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build official Taco Bell country source catalog")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--probe", action="store_true", help="Live-check each official source URL")
    args = parser.parse_args()

    payload = build_source_list(args.input, probe=args.probe)
    save_json(args.output, payload)

    print(f"Wrote source catalog for {len(payload['countries'])} countries to {args.output}")
    print(f"Countries in CSV: {payload['countries_in_csv_count']}")
    print(f"Likely missing with official sources to investigate: {', '.join(payload['likely_missing_countries'])}")


if __name__ == "__main__":
    main()
