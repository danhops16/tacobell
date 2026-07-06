#!/usr/bin/env python3
"""Audit Taco Bell location CSV for duplicates and coverage gaps."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from location_utils import (  # noqa: E402
    COUNTRY_NAMES,
    EXPORTS,
    count_by_country,
    find_duplicate_groups,
    load_legacy_csv,
    save_json,
)

DEFAULT_INPUT = EXPORTS / "all-tacobell-locations.csv"
DEFAULT_REPORT = EXPORTS / "audit-report.json"

LIKELY_MISSING = [
    "MX", "KR", "MY", "RO", "SE", "AE", "OM", "KW", "SA",
    "DO", "GT", "PA", "PE", "CO", "CR", "CL",
]


def audit(input_path: Path) -> dict:
    locations = load_legacy_csv(input_path)
    duplicate_groups = find_duplicate_groups(locations)
    country_counts = count_by_country(locations)
    present = set(country_counts)
    missing = [code for code in LIKELY_MISSING if code not in present]

    missing_source_url = sum(1 for loc in locations if not loc.source_url)
    missing_address = sum(1 for loc in locations if not loc.address.strip())

    return {
        "input_file": str(input_path),
        "total_rows_before": len(locations),
        "total_rows_after": len(locations),
        "duplicate_groups_found": len(duplicate_groups),
        "duplicate_groups": duplicate_groups[:200],
        "duplicate_groups_truncated": len(duplicate_groups) > 200,
        "duplicate_reason_counts": dict(Counter(group["reason"] for group in duplicate_groups)),
        "count_by_country": country_counts,
        "countries_present": sorted(present),
        "countries_present_count": len(present),
        "likely_missing_countries": [
            {
                "country": code,
                "name": COUNTRY_NAMES.get(code, code),
                "reason": "not present in input CSV",
            }
            for code in missing
        ],
        "data_quality": {
            "missing_source_url": missing_source_url,
            "missing_address": missing_address,
        },
        "sources_used": ["legacy_csv"],
        "rows_added_per_source": {},
        "rows_rejected_as_duplicates": [],
        "notes": [
            "Audit is non-destructive; duplicates are reported but not removed.",
            "Run scripts/merge_and_dedupe.py to produce a cleaned CSV.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Taco Bell location CSV")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    report = audit(args.input)
    save_json(args.report, report)

    print(f"Audited {report['total_rows_before']} rows from {args.input}")
    print(f"Duplicate groups: {report['duplicate_groups_found']}")
    print(f"Duplicate reasons: {report['duplicate_reason_counts']}")
    print(f"Countries present ({report['countries_present_count']}): {', '.join(report['countries_present'])}")
    print(f"Likely missing countries: {len(report['likely_missing_countries'])}")
    print(f"Missing source_url: {report['data_quality']['missing_source_url']}")
    print(f"Missing address: {report['data_quality']['missing_address']}")
    print(f"Report written to {args.report}")


if __name__ == "__main__":
    main()
