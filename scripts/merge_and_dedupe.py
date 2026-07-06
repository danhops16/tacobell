#!/usr/bin/env python3
"""Merge legacy CSV with scraped official data, dedupe, and output cleaned CSV + audit report."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from location_utils import (  # noqa: E402
    EXPORTS,
    Location,
    count_by_country,
    dedupe_locations,
    find_duplicate_groups,
    load_legacy_csv,
    save_csv,
    save_json,
)

DEFAULT_INPUT = EXPORTS / "all-tacobell-locations.csv"
SCRAPED_DIR = EXPORTS / "scraped"
CLEANED_CSV = EXPORTS / "tacobell-locations-cleaned.csv"
AUDIT_REPORT = EXPORTS / "audit-report.json"

# Countries where scraped official data should replace legacy CSV rows entirely.
OFFICIAL_REPLACE_COUNTRIES = {
    "US", "CA", "GB", "ES", "AU", "IN", "NL", "PH", "FI", "CL",
}


def load_scraped_locations() -> tuple[list[Location], dict[str, list[Location]]]:
    locations: list[Location] = []
    by_country: dict[str, list[Location]] = {}
    if not SCRAPED_DIR.exists():
        return locations, by_country
    for path in sorted(SCRAPED_DIR.glob("*.json")):
        if path.name == "scrape_summary.json":
            continue
        payload = json.loads(path.read_text())
        country = payload.get("country", "")
        country_rows = [Location(**row) for row in payload.get("locations", [])]
        if country_rows:
            by_country[country] = country_rows
            locations.extend(country_rows)
    return locations, by_country


def merge_locations(
    base: list[Location],
    scraped_by_country: dict[str, list[Location]],
) -> tuple[list[Location], list[dict], Counter[str]]:
    replaced_countries = {
        country for country in OFFICIAL_REPLACE_COUNTRIES if country in scraped_by_country
    }
    kept_base = [loc for loc in base if loc.country not in replaced_countries]
    merged = list(kept_base)
    added_by_source: Counter[str] = Counter()
    merge_notes: list[dict] = []

    for country in sorted(replaced_countries):
        merge_notes.append(
            {
                "action": "replace_country",
                "country": country,
                "removed_legacy_rows": sum(1 for loc in base if loc.country == country),
                "added_official_rows": len(scraped_by_country[country]),
            }
        )

    for country, rows in scraped_by_country.items():
        if country in replaced_countries:
            merged.extend(rows)
            source_name = rows[0].source_name if rows else "unknown"
            added_by_source[source_name] += len(rows)

    # Add scraped rows only for countries not already represented in base.
    present_countries = {loc.country for loc in merged}
    for country, rows in scraped_by_country.items():
        if country in replaced_countries or country in present_countries:
            continue
        merged.extend(rows)
        source_name = rows[0].source_name if rows else "unknown"
        added_by_source[source_name] += len(rows)
        merge_notes.append(
            {
                "action": "add_new_country",
                "country": country,
                "added_official_rows": len(rows),
            }
        )

    return merged, merge_notes, added_by_source


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge and dedupe Taco Bell locations")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=CLEANED_CSV)
    parser.add_argument("--report", type=Path, default=AUDIT_REPORT)
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    base_locations = load_legacy_csv(args.input)
    scraped_locations, scraped_by_country = load_scraped_locations()
    duplicate_groups_before = find_duplicate_groups(base_locations)

    merged, merge_notes, added_by_source = merge_locations(base_locations, scraped_by_country)
    cleaned, dedupe_removed = dedupe_locations(merged)

    sources_used = sorted({loc.source_name for loc in cleaned if loc.source_name})
    likely_missing = []
    sources_file = ROOT / "data" / "country_sources.json"
    if sources_file.exists():
        catalog = json.loads(sources_file.read_text())
        cleaned_countries = set(count_by_country(cleaned))
        likely_missing = [
            {
                "country": code,
                "name": entry["name"],
                "status": entry["status"],
            }
            for code, entry in catalog["countries"].items()
            if code not in cleaned_countries and entry["status"] not in {"no_official_locations"}
        ]

    report = {
        "total_rows_before": len(base_locations),
        "merged_rows_before_dedupe": len(merged),
        "total_rows_after": len(cleaned),
        "duplicate_groups_found_before_merge": len(duplicate_groups_before),
        "duplicate_groups": duplicate_groups_before[:200],
        "duplicate_groups_truncated": len(duplicate_groups_before) > 200,
        "duplicate_reason_counts_before_merge": dict(
            Counter(group["reason"] for group in duplicate_groups_before)
        ),
        "merge_actions": merge_notes,
        "rows_rejected_as_duplicates_during_merge": [],
        "rows_removed_during_final_dedupe": dedupe_removed,
        "duplicate_reason_counts_final_dedupe": dict(Counter(row["reason"] for row in dedupe_removed)),
        "count_by_country_before": count_by_country(base_locations),
        "count_by_country_after": count_by_country(cleaned),
        "likely_missing_countries": likely_missing,
        "sources_used": sources_used,
        "rows_added_per_source": dict(added_by_source),
        "scraped_rows_available": len(scraped_locations),
        "output_csv": str(args.output),
    }

    save_csv(args.output, cleaned)
    save_json(args.report, report)

    print(f"Input rows: {report['total_rows_before']}")
    print(f"Scraped rows available: {report['scraped_rows_available']}")
    print(f"Rows after merge: {report['merged_rows_before_dedupe']}")
    print(f"Final cleaned rows: {report['total_rows_after']}")
    print(f"Duplicates removed in final dedupe: {len(dedupe_removed)}")
    print(f"Cleaned CSV: {args.output}")
    print(f"Audit report: {args.report}")


if __name__ == "__main__":
    main()
