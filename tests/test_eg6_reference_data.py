from __future__ import annotations

import csv
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_PATH = ROOT / "data/reference/seoul_121_places.csv"
AREA_PATH = ROOT / "data/reference/eg6_area_panel.csv"
SPOT_PATH = ROOT / "data/reference/eg6_spot_master.csv"
SDOT_PATH = ROOT / "data/reference/eg6_sdot_links.csv"
PANEL_DOC_PATH = ROOT / "docs/product/EG6_AREA_SPOT_PANEL.md"
PANEL_VERSION = "eg6a-v1"
EXPECTED_APPROVED_COUNT = 13
RESOLVED_RELATED_MAPPINGS = {
    "삼성역": ("POI001", "강남 MICE 관광특구"),
    "광화문역": ("POI088", "광화문광장"),
    "을지로입구역": ("POI003", "명동 관광특구"),
}
AREA_HEADERS = [
    "panel_version", "panel_order", "service_area_name", "area_code",
    "official_area_name", "area_mapping_type", "mapping_confidence",
    "sdot_group", "approved", "active", "decision_note",
]
SPOT_HEADERS = [
    "spot_id", "service_area_name", "spot_name", "latitude", "longitude",
    "coordinate_source", "representative_coordinate_type", "connected_area_code",
    "connected_area_name", "spot_type", "business_reason",
    "selling_suitability_status", "field_verified", "active",
]
SDOT_HEADERS = [
    "spot_id", "nearest_sdot_id", "nearest_sdot_distance_m", "coverage_class",
    "sensor_recent_active", "activity_reference_period", "mapping_confidence",
    "source_report",
]
MAPPING_TYPES = {
    "EXACT_AREA_MATCH", "RELATED_AREA_MATCH", "NO_SAFE_AREA_MATCH",
    "REPLACEMENT_REQUIRED",
}
COVERAGE_CLASSES = {"DIRECT_COVERAGE", "NEARBY_SUPPORT", "NO_NEARBY_SDOT"}
BOOLEAN_VALUES = {"true", "false"}


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


class Eg6ReferenceDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.area_headers, cls.areas = load_csv(AREA_PATH)
        cls.spot_headers, cls.spots = load_csv(SPOT_PATH)
        cls.sdot_headers, cls.sdot_links = load_csv(SDOT_PATH)
        _, cls.official = load_csv(OFFICIAL_PATH)
        cls.official_by_code = {row["AREA_CD"]: row["AREA_NM"] for row in cls.official}

    def test_reference_files_exist_and_have_exact_headers(self) -> None:
        self.assertEqual(self.area_headers, AREA_HEADERS)
        self.assertEqual(self.spot_headers, SPOT_HEADERS)
        self.assertEqual(self.sdot_headers, SDOT_HEADERS)

    def test_panel_has_thirteen_ordered_proposals_and_one_version(self) -> None:
        self.assertEqual(len(self.areas), 13)
        self.assertEqual([int(row["panel_order"]) for row in self.areas], list(range(1, 14)))
        self.assertEqual({row["panel_version"] for row in self.areas}, {PANEL_VERSION})
        self.assertEqual(len({row["service_area_name"] for row in self.areas}), 13)

    def test_existing_eg5_places_and_ttukseom_replacement_are_preserved(self) -> None:
        by_name = {row["service_area_name"]: row for row in self.areas}
        self.assertEqual(by_name["구로디지털단지역"]["area_code"], "POI019")
        self.assertEqual(by_name["가산디지털단지역"]["area_code"], "POI013")
        self.assertEqual(by_name["강남역"]["area_code"], "POI014")
        self.assertEqual(by_name["뚝섬역"]["area_code"], "POI025")
        self.assertNotIn("판교역", by_name)

    def test_all_thirteen_safe_official_area_mappings_are_approved(self) -> None:
        approved = [row for row in self.areas if row["approved"] == "true"]
        pending = [row for row in self.areas if row["approved"] == "false"]
        self.assertEqual(len(approved), EXPECTED_APPROVED_COUNT)
        self.assertEqual(pending, [])
        self.assertTrue(all(row["active"] == "true" for row in approved))
        self.assertTrue(all(row["area_code"] and row["official_area_name"] for row in approved))

    def test_three_resolved_related_mappings_are_exactly_recorded(self) -> None:
        by_service = {row["service_area_name"]: row for row in self.areas}
        for service_name, (area_code, official_name) in RESOLVED_RELATED_MAPPINGS.items():
            row = by_service[service_name]
            self.assertEqual(row["area_code"], area_code)
            self.assertEqual(row["official_area_name"], official_name)
            self.assertEqual(row["area_mapping_type"], "RELATED_AREA_MATCH")
            self.assertEqual(row["approved"], "true")
            self.assertEqual(row["active"], "true")

    def test_approved_area_codes_and_names_match_official_reference(self) -> None:
        approved_codes: list[str] = []
        for row in self.areas:
            self.assertIn(row["area_mapping_type"], MAPPING_TYPES)
            self.assertIn(row["sdot_group"], COVERAGE_CLASSES)
            self.assertIn(row["approved"], BOOLEAN_VALUES)
            self.assertIn(row["active"], BOOLEAN_VALUES)
            if row["approved"] == "true":
                approved_codes.append(row["area_code"])
                self.assertEqual(self.official_by_code.get(row["area_code"]), row["official_area_name"])
                self.assertIn(row["area_mapping_type"], {"EXACT_AREA_MATCH", "RELATED_AREA_MATCH"})
        self.assertEqual(len(approved_codes), len(set(approved_codes)))

    def test_spot_ids_are_unique_and_cover_all_service_candidates(self) -> None:
        self.assertEqual(len(self.spots), 13)
        self.assertEqual(len({row["spot_id"] for row in self.spots}), 13)
        self.assertEqual(
            {row["service_area_name"] for row in self.spots},
            {row["service_area_name"] for row in self.areas},
        )

    def test_active_spots_reference_only_approved_areas(self) -> None:
        approved_by_service = {
            row["service_area_name"]: row
            for row in self.areas
            if row["approved"] == "true"
        }
        for spot in self.spots:
            self.assertIn(spot["active"], BOOLEAN_VALUES)
            if spot["active"] == "true":
                area = approved_by_service[spot["service_area_name"]]
                self.assertEqual(spot["connected_area_code"], area["area_code"])
                self.assertEqual(spot["connected_area_name"], area["official_area_name"])
            else:
                self.assertEqual(spot["connected_area_code"], "")
                self.assertEqual(spot["connected_area_name"], "")

    def test_station_centers_are_not_presented_as_verified_exits(self) -> None:
        for spot in self.spots:
            self.assertEqual(spot["representative_coordinate_type"], "STATION_CENTER_PROXY")
            self.assertEqual(spot["selling_suitability_status"], "FIELD_VALIDATION_REQUIRED")
            self.assertEqual(spot["field_verified"], "false")
            self.assertNotIn("출구", spot["spot_name"])

    def test_spot_coordinates_are_within_basic_seoul_bounds(self) -> None:
        for spot in self.spots:
            latitude = float(spot["latitude"])
            longitude = float(spot["longitude"])
            self.assertGreaterEqual(latitude, 37.41)
            self.assertLessEqual(latitude, 37.72)
            self.assertGreaterEqual(longitude, 126.73)
            self.assertLessEqual(longitude, 127.27)

    def test_sdot_links_cover_every_spot_and_follow_distance_thresholds(self) -> None:
        spot_ids = {row["spot_id"] for row in self.spots}
        self.assertEqual(len(self.sdot_links), 13)
        self.assertEqual({row["spot_id"] for row in self.sdot_links}, spot_ids)
        self.assertEqual(len({row["spot_id"] for row in self.sdot_links}), 13)
        for link in self.sdot_links:
            distance = float(link["nearest_sdot_distance_m"])
            expected = (
                "DIRECT_COVERAGE" if distance <= 150
                else "NEARBY_SUPPORT" if distance <= 300
                else "NO_NEARBY_SDOT"
            )
            self.assertEqual(link["coverage_class"], expected)
            self.assertGreaterEqual(distance, 0)

    def test_only_recent_active_sensors_are_linked(self) -> None:
        self.assertTrue(all(row["sensor_recent_active"] == "true" for row in self.sdot_links))
        self.assertEqual(
            {row["activity_reference_period"] for row in self.sdot_links},
            {"2026-07-06/2026-07-12"},
        )
        self.assertEqual({row["source_report"] for row in self.sdot_links}, {"EG6_AREA_SPOT_PANEL.md"})

    def test_reference_values_contain_no_secret_url_or_local_absolute_path(self) -> None:
        forbidden = re.compile(r"/Users/|file://|https?://|SEOUL_OPEN_API_KEY|API[_-]?KEY\s*=", re.IGNORECASE)
        for rows in (self.areas, self.spots, self.sdot_links):
            for row in rows:
                self.assertIsNone(forbidden.search("\n".join(row.values())))

    def test_batch_contract_is_documented_without_runtime_implementation(self) -> None:
        text = PANEL_DOC_PATH.read_text(encoding="utf-8")
        for field in (
            "batch_id", "panel_version", "collection_purpose", "expected_area_count",
            "scheduled_at", "started_at", "finished_at", "success_count",
            "failure_count", "exit_code",
        ):
            self.assertIn(f"`{field}`", text)
        self.assertIn("EG6A_IMPLEMENTED_READY_FOR_DIFF_REVIEW", text)
        self.assertIn("classifications_recalculated_from_station_center_proxy=true", text)


if __name__ == "__main__":
    unittest.main()
