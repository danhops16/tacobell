"""Shared utilities for Taco Bell location auditing, scraping, and deduplication."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "exports"
DATA = ROOT / "data"

STANDARD_COLUMNS = [
    "internal_id",
    "store_id",
    "name",
    "address",
    "city",
    "region",
    "postal_code",
    "country",
    "latitude",
    "longitude",
    "phone",
    "source_url",
]

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
    "MY": "Malaysia",
    "MX": "Mexico",
    "RO": "Romania",
    "SE": "Sweden",
    "AE": "United Arab Emirates",
    "OM": "Oman",
    "KW": "Kuwait",
    "SA": "Saudi Arabia",
    "DO": "Dominican Republic",
    "GT": "Guatemala",
    "PA": "Panama",
    "PE": "Peru",
    "CO": "Colombia",
    "CR": "Costa Rica",
}


@dataclass
class Location:
    internal_id: str
    store_id: str = ""
    name: str = "Taco Bell"
    address: str = ""
    city: str = ""
    region: str = ""
    postal_code: str = ""
    country: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    phone: str = ""
    source_url: str = ""
    source_name: str = ""
    extra: dict = field(default_factory=dict)

    def to_row(self) -> dict[str, str]:
        return {
            "internal_id": self.internal_id,
            "store_id": self.store_id,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "region": self.region,
            "postal_code": self.postal_code,
            "country": self.country,
            "latitude": f"{self.latitude:.7f}" if self.latitude else "",
            "longitude": f"{self.longitude:.7f}" if self.longitude else "",
            "phone": self.phone,
            "source_url": self.source_url,
        }


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_address(address: str, city: str = "", postal_code: str = "") -> str:
    parts = [normalize_text(address), normalize_text(city), normalize_text(postal_code)]
    return " | ".join(part for part in parts if part)


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def address_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def slugify(value: str) -> str:
    value = normalize_text(value)
    return value.replace(" ", "-")[:64] or "unknown"


def make_internal_id(
    country: str,
    lat: float,
    lng: float,
    store_id: str = "",
    address: str = "",
    source_url: str = "",
) -> str:
    if store_id:
        return f"{country.lower()}-{slugify(store_id)}"
    if source_url:
        return f"{country.lower()}-{slugify(source_url)}"
    if address:
        digest = hashlib.sha1(normalize_text(address).encode()).hexdigest()[:10]
        return f"{country.lower()}-{digest}"
    digest = hashlib.sha1(f"{lat:.5f},{lng:.5f}".encode()).hexdigest()[:10]
    return f"{country.lower()}-{digest}"


def infer_source_url_from_legacy_id(legacy_id: str) -> str:
    if not legacy_id:
        return ""
    if legacy_id.startswith("http"):
        return legacy_id
    if "locations-tacobell-com" in legacy_id:
        slug = legacy_id.split("us-", 1)[-1].replace("https-locations-tacobell-com-", "")
        slug = slug.replace("-", "/")
        return f"https://locations.tacobell.com/{slug}.html"
    if "locations-tacobell-ca" in legacy_id:
        slug = legacy_id.split("ca-", 1)[-1].replace("https-locations-tacobell-ca-", "")
        slug = slug.replace("-", "/")
        return f"https://locations.tacobell.ca/{slug}"
    if "tacobell-com-au" in legacy_id:
        slug = legacy_id.split("au-", 1)[-1].replace("https-tacobell-com-au-", "")
        return f"https://tacobell.com.au/{slug.replace('-', '/')}/"
    return ""


def load_legacy_csv(path: Path) -> list[Location]:
    locations: list[Location] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            store_id = (row.get("Store ID") or "").strip()
            country = (row.get("Country") or "").strip()
            lat = float(row["Latitude"]) if row.get("Latitude") else 0.0
            lng = float(row["Longitude"]) if row.get("Longitude") else 0.0
            source_url = infer_source_url_from_legacy_id(store_id)
            locations.append(
                Location(
                    internal_id=make_internal_id(country, lat, lng, store_id=store_id),
                    store_id=store_id,
                    name=(row.get("Name") or "Taco Bell").strip(),
                    address=(row.get("Address") or "").strip(),
                    city=(row.get("City") or "").strip(),
                    region=(row.get("State/Region") or "").strip(),
                    postal_code=(row.get("Postal Code") or "").strip(),
                    country=country,
                    latitude=lat,
                    longitude=lng,
                    phone=(row.get("Phone") or "").strip(),
                    source_url=source_url,
                    source_name="legacy_csv",
                )
            )
    return locations


def load_locations_json(path: Path) -> list[Location]:
    payload = json.loads(path.read_text())
    locations: list[Location] = []
    for row in payload.get("locations", []):
        country = row.get("country", "")
        lat = float(row.get("lat") or 0)
        lng = float(row.get("lng") or 0)
        store_id = str(row.get("storeNum") or row.get("id") or "")
        source_url = row.get("source_url") or infer_source_url_from_legacy_id(row.get("id", ""))
        locations.append(
            Location(
                internal_id=row.get("id") or make_internal_id(country, lat, lng, store_id=store_id),
                store_id=store_id,
                name=row.get("name", "Taco Bell"),
                address=row.get("address", ""),
                city=row.get("city", ""),
                region=row.get("state", ""),
                postal_code=row.get("zip", ""),
                country=country,
                latitude=lat,
                longitude=lng,
                phone=row.get("phone", ""),
                source_url=source_url,
                source_name="locations_json",
            )
        )
    return locations


def save_csv(path: Path, locations: Iterable[Location]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [loc.to_row() for loc in locations]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STANDARD_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def count_by_country(locations: Iterable[Location]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for loc in locations:
        counts[loc.country] = counts.get(loc.country, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def exact_key(loc: Location) -> tuple:
    return (
        loc.country,
        normalize_address(loc.address, loc.city, loc.postal_code),
    )


def fuzzy_key(loc: Location) -> tuple:
    return (loc.country, normalize_text(loc.city))


def is_exact_duplicate(a: Location, b: Location) -> bool:
    if a.country != b.country:
        return False
    key_a = exact_key(a)
    if not key_a[1]:
        return False
    return key_a == exact_key(b)


def is_coordinate_duplicate(a: Location, b: Location, threshold_m: float = 25.0) -> bool:
    if a.country != b.country:
        return False
    if not a.latitude or not b.latitude:
        return False
    return haversine_meters(a.latitude, a.longitude, b.latitude, b.longitude) <= threshold_m


def is_fuzzy_duplicate(a: Location, b: Location, threshold: float = 0.9) -> bool:
    if a.country != b.country:
        return False
    if normalize_text(a.city) != normalize_text(b.city):
        return False
    if not a.address or not b.address:
        return False
    return address_similarity(a.address, b.address) >= threshold


def duplicate_reason(a: Location, b: Location) -> str | None:
    if is_exact_duplicate(a, b):
        return "exact"
    if is_coordinate_duplicate(a, b):
        return "coordinate"
    if is_fuzzy_duplicate(a, b):
        return "fuzzy"
    return None


def find_duplicate_groups(locations: list[Location]) -> list[dict]:
    groups: list[dict] = []
    seen_pairs: set[tuple[int, int]] = set()

    exact_buckets: dict[tuple, list[int]] = {}
    city_buckets: dict[tuple, list[int]] = {}
    for index, loc in enumerate(locations):
        exact_key_value = exact_key(loc)
        if exact_key_value[1]:
            exact_buckets.setdefault(exact_key_value, []).append(index)
        city_buckets.setdefault(fuzzy_key(loc), []).append(index)

    for indices in exact_buckets.values():
        if len(indices) < 2:
            continue
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                left, right = indices[i], indices[j]
                pair = (min(left, right), max(left, right))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                groups.append(
                    {
                        "reason": "exact",
                        "indices": [left, right],
                        "internal_ids": [locations[left].internal_id, locations[right].internal_id],
                        "country": locations[left].country,
                        "addresses": [locations[left].address, locations[right].address],
                        "cities": [locations[left].city, locations[right].city],
                    }
                )

    coord_buckets: dict[tuple, list[int]] = {}
    for index, loc in enumerate(locations):
        if not loc.latitude:
            continue
        bucket = (loc.country, round(loc.latitude, 4), round(loc.longitude, 4))
        coord_buckets.setdefault(bucket, []).append(index)

    for indices in coord_buckets.values():
        if len(indices) < 2:
            continue
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                left, right = indices[i], indices[j]
                pair = (min(left, right), max(left, right))
                if pair in seen_pairs:
                    continue
                if not is_coordinate_duplicate(locations[left], locations[right]):
                    continue
                seen_pairs.add(pair)
                groups.append(
                    {
                        "reason": "coordinate",
                        "indices": [left, right],
                        "internal_ids": [
                            locations[left].internal_id,
                            locations[right].internal_id,
                        ],
                        "country": locations[left].country,
                        "addresses": [locations[left].address, locations[right].address],
                        "cities": [locations[left].city, locations[right].city],
                    }
                )

    for indices in city_buckets.values():
        if len(indices) < 2:
            continue
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                left, right = indices[i], indices[j]
                pair = (min(left, right), max(left, right))
                if pair in seen_pairs:
                    continue
                if is_fuzzy_duplicate(locations[left], locations[right]):
                    seen_pairs.add(pair)
                    groups.append(
                        {
                            "reason": "fuzzy",
                            "indices": [left, right],
                            "internal_ids": [
                                locations[left].internal_id,
                                locations[right].internal_id,
                            ],
                            "country": locations[left].country,
                            "addresses": [locations[left].address, locations[right].address],
                            "cities": [locations[left].city, locations[right].city],
                        }
                    )

    return groups


def dedupe_locations(locations: list[Location]) -> tuple[list[Location], list[dict]]:
    kept: list[Location] = []
    removed: list[dict] = []
    exact_index: dict[tuple, int] = {}
    city_buckets: dict[tuple, list[int]] = {}

    for candidate in locations:
        reason = None
        duplicate_of_index = None

        exact = exact_key(candidate)
        if exact[1] and exact in exact_index:
            duplicate_of_index = exact_index[exact]
            reason = "exact"

        if duplicate_of_index is None and candidate.latitude:
            for index in city_buckets.get(fuzzy_key(candidate), []):
                existing = kept[index]
                if is_coordinate_duplicate(candidate, existing):
                    duplicate_of_index = index
                    reason = "coordinate"
                    break
                if is_fuzzy_duplicate(candidate, existing):
                    duplicate_of_index = index
                    reason = "fuzzy"
                    break

        if duplicate_of_index is not None:
            existing = kept[duplicate_of_index]
            removed.append(
                {
                    "reason": reason,
                    "removed_internal_id": candidate.internal_id,
                    "kept_internal_id": existing.internal_id,
                    "country": candidate.country,
                    "removed_address": candidate.address,
                    "kept_address": existing.address,
                    "removed_source_url": candidate.source_url,
                    "kept_source_url": existing.source_url,
                }
            )
            continue

        index = len(kept)
        kept.append(candidate)
        if exact[1]:
            exact_index[exact] = index
        city_buckets.setdefault(fuzzy_key(candidate), []).append(index)

    return kept, removed
