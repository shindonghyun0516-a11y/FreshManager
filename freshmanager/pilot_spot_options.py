"""Validated static Spot options for the five-Area initial pilot."""

from __future__ import annotations

import csv
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PILOT_SPOT_OPTIONS_PATH = PROJECT_ROOT / "data/prototype/pilot_spot_options.csv"
EG6_AREA_PANEL_PATH = PROJECT_ROOT / "data/reference/eg6_area_panel.csv"
EG6_SPOT_MASTER_PATH = PROJECT_ROOT / "data/reference/eg6_spot_master.csv"

PILOT_SPOT_OPTION_HEADERS = (
    "pilot_area_code",
    "pilot_area_name",
    "spot_option_id",
    "spot_name",
    "spot_type",
    "address",
    "latitude",
    "longitude",
    "coordinate_status",
    "coordinate_source_type",
    "pin_scope",
    "location_source_name",
    "location_source_url",
    "location_source_checked_at",
    "spot_role",
    "spot_selection_mode",
    "display_order",
    "field_verification_status",
    "operational_suitability_status",
    "limitations",
)
PILOT_AREA_NAMES = {
    "POI032": "서울식물원·마곡나루역",
    "POI088": "광화문광장",
    "POI014": "강남역",
    "POI025": "뚝섬역",
    "POI072": "여의도",
}
SPOT_TYPE_SCOPES = {
    "TRANSIT_EXIT": {"TRANSIT_EXIT_PIN"},
    "PUBLIC_SPACE": {"REPRESENTATIVE_POI_PIN", "PUBLIC_SPACE_PIN"},
    "PARK_ZONE": {"REPRESENTATIVE_POI_PIN"},
    "VENUE": {"VENUE_ANCHOR"},
}
SOURCE_COMMENT_URL = (
    "https://github.com/shindonghyun0516-a11y/FreshManager/"
    "issues/132#issuecomment-5115241852"
)
FIXED_VALUES = {
    "coordinate_status": "PM_CONFIRMED",
    "coordinate_source_type": "PM_PROVIDED_PUBLIC_MAP_LOOKUP",
    "location_source_name": "PM_PROVIDED_PUBLIC_MAP_LOOKUP",
    "location_source_url": SOURCE_COMMENT_URL,
    "location_source_checked_at": "2026-07-29",
    "spot_role": "USER_SELECTABLE_OPTION",
    "spot_selection_mode": "USER_CHOICE",
    "field_verification_status": "UNAVAILABLE",
    "operational_suitability_status": "NOT_VERIFIED",
}
SEOUL_LATITUDE_RANGE = (Decimal("37.41"), Decimal("37.72"))
SEOUL_LONGITUDE_RANGE = (Decimal("126.73"), Decimal("127.27"))
FORBIDDEN_TEXT = re.compile(
    r"/Users/|file://|https?://|SEOUL_OPEN_API_KEY|API[_-]?KEY\s*=",
    re.IGNORECASE,
)


class PilotSpotOptionsError(ValueError):
    """Raised when the pilot Spot master violates its fixed contract."""


def _read_csv(path: Path, expected_headers: tuple[str, ...] | None = None) -> tuple[dict[str, str], ...]:
    if path.is_symlink() or not path.is_file():
        raise PilotSpotOptionsError("reference_file_invalid")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            if expected_headers is not None and tuple(reader.fieldnames or ()) != expected_headers:
                raise PilotSpotOptionsError("header_contract_mismatch")
            raw_rows = tuple(reader)
            if any(None in row for row in raw_rows):
                raise PilotSpotOptionsError("unexpected_csv_field")
            rows = tuple(
                {str(key): (value or "").strip() for key, value in row.items() if key is not None}
                for row in raw_rows
            )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise PilotSpotOptionsError("reference_file_unreadable") from exc
    return rows


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise PilotSpotOptionsError("coordinate_not_numeric") from exc
    if not result.is_finite():
        raise PilotSpotOptionsError("coordinate_not_numeric")
    return result


def load_pilot_spot_options(
    path: Path = PILOT_SPOT_OPTIONS_PATH,
    *,
    area_panel_path: Path = EG6_AREA_PANEL_PATH,
    anchor_path: Path = EG6_SPOT_MASTER_PATH,
) -> tuple[dict[str, str], ...]:
    """Load and validate the PM-approved static user-choice Spot options."""

    rows = _read_csv(path, PILOT_SPOT_OPTION_HEADERS)
    if len(rows) != 15 or any(not all(row.get(field, "") for field in PILOT_SPOT_OPTION_HEADERS) for row in rows):
        raise PilotSpotOptionsError("row_count_or_required_value_mismatch")

    area_panel = _read_csv(area_panel_path)
    approved_areas = {
        row.get("area_code", ""): row.get("official_area_name", "")
        for row in area_panel
        if row.get("approved") == "true" and row.get("active") == "true"
    }
    if any(approved_areas.get(code) != name for code, name in PILOT_AREA_NAMES.items()):
        raise PilotSpotOptionsError("approved_area_reference_mismatch")

    anchors = _read_csv(anchor_path)
    anchor_coordinates = {
        (_decimal(row.get("latitude", "")), _decimal(row.get("longitude", "")))
        for row in anchors
    }

    ids: set[str] = set()
    coordinates_by_area: dict[str, set[tuple[Decimal, Decimal]]] = {
        code: set() for code in PILOT_AREA_NAMES
    }
    area_counts: Counter[str] = Counter()
    actual_order: list[tuple[str, int]] = []
    for row in rows:
        if any(
            FORBIDDEN_TEXT.search(value)
            for field, value in row.items()
            if field != "location_source_url"
        ):
            raise PilotSpotOptionsError("forbidden_reference_text")
        area_code = row["pilot_area_code"]
        if PILOT_AREA_NAMES.get(area_code) != row["pilot_area_name"]:
            raise PilotSpotOptionsError("pilot_area_contract_mismatch")
        try:
            display_order = int(row["display_order"])
        except ValueError as exc:
            raise PilotSpotOptionsError("display_order_invalid") from exc
        expected_id = f"{area_code}-OPT-{display_order:02d}"
        if display_order not in {1, 2, 3} or row["spot_option_id"] != expected_id:
            raise PilotSpotOptionsError("spot_option_identity_mismatch")
        if expected_id in ids:
            raise PilotSpotOptionsError("duplicate_spot_option_id")
        ids.add(expected_id)

        spot_type = row["spot_type"]
        if row["pin_scope"] not in SPOT_TYPE_SCOPES.get(spot_type, set()):
            raise PilotSpotOptionsError("spot_type_or_pin_scope_invalid")
        if any(row[field] != value for field, value in FIXED_VALUES.items()):
            raise PilotSpotOptionsError("fixed_contract_value_mismatch")

        coordinate = (_decimal(row["latitude"]), _decimal(row["longitude"]))
        if (
            not SEOUL_LATITUDE_RANGE[0] <= coordinate[0] <= SEOUL_LATITUDE_RANGE[1]
            or not SEOUL_LONGITUDE_RANGE[0] <= coordinate[1] <= SEOUL_LONGITUDE_RANGE[1]
        ):
            raise PilotSpotOptionsError("coordinate_outside_seoul")
        if coordinate in coordinates_by_area[area_code]:
            raise PilotSpotOptionsError("duplicate_coordinate_within_area")
        if coordinate in anchor_coordinates:
            raise PilotSpotOptionsError("existing_anchor_coordinate_reused")
        coordinates_by_area[area_code].add(coordinate)
        area_counts[area_code] += 1
        actual_order.append((area_code, display_order))

    expected_order = [
        (area_code, display_order)
        for area_code in PILOT_AREA_NAMES
        for display_order in (1, 2, 3)
    ]
    if area_counts != Counter({code: 3 for code in PILOT_AREA_NAMES}) or actual_order != expected_order:
        raise PilotSpotOptionsError("five_area_three_option_order_mismatch")
    return rows
