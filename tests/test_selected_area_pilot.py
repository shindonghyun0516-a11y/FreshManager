from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from freshmanager.selected_area_pilot import (
    SPOT_POPULATION_HEADERS,
    AreaDataProvider,
    PilotSpotOptionRepository,
    SelectedAreaPilotError,
    SelectedAreaPilotService,
)


ROOT = Path(__file__).resolve().parents[1]
SPOT_MASTER = ROOT / "data/prototype/pilot_spot_options.csv"


class SelectedAreaPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="selected-area-pilot-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_population(self, rows: list[dict[str, str]]) -> Path:
        path = self.root / "pilot_spot_population.csv"
        with path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=SPOT_POPULATION_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    @staticmethod
    def row(**changes: str) -> dict[str, str]:
        row = {
            "pilot_area_code": "POI032",
            "spot_option_id": "POI032-OPT-01",
            "observed_at": "2026-08-01T12:00:00+09:00",
            "current_population_min": "100",
            "current_population_max": "120",
            "forecast_60_population_min": "130",
            "forecast_60_population_max": "150",
            "forecast_180_population_min": "80",
            "forecast_180_population_max": "100",
            "data_status": "PROTOTYPE",
            "input_method": "PM_MANUAL",
            "source_note": "PM approved prototype",
            "updated_at": "2026-08-01T12:05:00+09:00",
        }
        row.update(changes)
        return row

    def repository(self, population_path: Path | None = None) -> PilotSpotOptionRepository:
        return PilotSpotOptionRepository(
            master_path=SPOT_MASTER,
            population_path=population_path,
        )

    def test_missing_population_file_returns_three_unavailable_spots(self) -> None:
        spots, warnings = self.repository(self.root / "missing.csv").list_for_area("POI032")

        self.assertEqual(len(spots), 3)
        self.assertEqual(
            {spot["prototype_data_status"] for spot in spots},
            {"SPOT_PROTOTYPE_DATA_UNAVAILABLE"},
        )
        for spot in spots:
            for field in (
                "observed_at",
                "current_population",
                "forecast_60",
                "forecast_180",
                "change_amount_60",
                "change_rate_60",
                "change_amount_180",
                "change_rate_180",
            ):
                self.assertIsNone(spot[field])
        self.assertIn("SPOT_PROTOTYPE_DATA_UNAVAILABLE", warnings)

    def test_complete_row_calculates_each_horizon_from_spot_ranges(self) -> None:
        path = self.write_population([self.row()])
        spots, _warnings = self.repository(path).list_for_area("POI032")
        first = spots[0]

        self.assertEqual(first["current_population"], {"min": 100.0, "max": 120.0})
        self.assertEqual(first["forecast_60"], {"min": 130.0, "max": 150.0})
        self.assertEqual(first["forecast_180"], {"min": 80.0, "max": 100.0})
        self.assertEqual(first["change_amount_60"], 30.0)
        self.assertAlmostEqual(first["change_rate_60"], 30 / 110)
        self.assertEqual(first["change_amount_180"], -20.0)
        self.assertAlmostEqual(first["change_rate_180"], -20 / 110)
        self.assertEqual(first["spot_population_source"], "PM_MANUAL_PROTOTYPE")
        self.assertNotIn("source_note", first)
        self.assertNotIn("opportunity_score", first)
        self.assertNotIn("area_rank", first)
        self.assertEqual(
            [spot["prototype_data_status"] for spot in spots[1:]],
            ["SPOT_PROTOTYPE_DATA_UNAVAILABLE", "SPOT_PROTOTYPE_DATA_UNAVAILABLE"],
        )

    def test_missing_horizon_is_independently_unavailable(self) -> None:
        for horizon, other in (("60", "180"), ("180", "60")):
            with self.subTest(horizon=horizon):
                path = self.write_population([
                    self.row(**{
                        f"forecast_{horizon}_population_min": "",
                        f"forecast_{horizon}_population_max": "",
                    })
                ])
                first = self.repository(path).list_for_area("POI032")[0][0]

                self.assertIsNone(first[f"forecast_{horizon}"])
                self.assertIsNone(first[f"change_amount_{horizon}"])
                self.assertIsNone(first[f"change_rate_{horizon}"])
                self.assertIsNotNone(first[f"forecast_{other}"])

    def test_zero_current_midpoint_keeps_amount_and_nulls_rate(self) -> None:
        path = self.write_population([
            self.row(current_population_min="0", current_population_max="0")
        ])
        first = self.repository(path).list_for_area("POI032")[0][0]

        self.assertEqual(first["change_amount_60"], 140.0)
        self.assertIsNone(first["change_rate_60"])

    def test_row_without_population_values_is_unavailable(self) -> None:
        path = self.write_population([
            self.row(
                current_population_min="",
                current_population_max="",
                forecast_60_population_min="",
                forecast_60_population_max="",
                forecast_180_population_min="",
                forecast_180_population_max="",
            )
        ])

        spots, warnings = self.repository(path).list_for_area("POI032")

        self.assertTrue(
            all(
                spot["prototype_data_status"] == "SPOT_PROTOTYPE_DATA_UNAVAILABLE"
                for spot in spots
            )
        )
        self.assertTrue(all(spot["spot_population_source"] is None for spot in spots))
        self.assertIn("SPOT_PROTOTYPE_DATA_UNAVAILABLE", warnings)

    def test_partial_range_degrades_prototype_without_breaking_static_spots(self) -> None:
        path = self.write_population([self.row(forecast_60_population_max="")])
        spots, warnings = self.repository(path).list_for_area("POI032")

        self.assertEqual(len(spots), 3)
        self.assertEqual(
            {spot["prototype_data_status"] for spot in spots},
            {"SPOT_PROTOTYPE_DATA_UNAVAILABLE"},
        )
        self.assertIn("SPOT_PROTOTYPE_CONTRACT_INVALID", warnings)

    def test_invalid_rows_degrade_without_nan_or_area_copy(self) -> None:
        invalid_rows = (
            self.row(current_population_min="121", current_population_max="120"),
            self.row(spot_option_id="POI999-OPT-01"),
            self.row(pilot_area_code="POI088"),
            self.row(current_population_min="NaN"),
            self.row(current_population_max="1e99999"),
            self.row(
                current_population_min="1e-300",
                current_population_max="1e-300",
                forecast_60_population_min="1e300",
                forecast_60_population_max="1e300",
            ),
            self.row(data_status="FINAL"),
            self.row(input_method="AUTOMATED"),
            self.row(observed_at="2026-08-01T12:00:00"),
            self.row(source_note="file:///Users/example/private.csv"),
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                path = self.write_population([row])
                spots, warnings = self.repository(path).list_for_area("POI032")
                self.assertEqual(len(spots), 3)
                self.assertIn("SPOT_PROTOTYPE_CONTRACT_INVALID", warnings)
                json.dumps(spots, allow_nan=False)
                self.assertTrue(all(spot["current_population"] is None for spot in spots))

    def test_population_symlink_degrades_without_reading_target(self) -> None:
        target = self.write_population([self.row()])
        link = self.root / "population-link.csv"
        link.symlink_to(target)

        spots, warnings = self.repository(link).list_for_area("POI032")

        self.assertIn("SPOT_PROTOTYPE_CONTRACT_INVALID", warnings)
        self.assertTrue(all(spot["current_population"] is None for spot in spots))

    def test_duplicate_population_row_degrades_all_prototype_values(self) -> None:
        row = self.row()
        path = self.write_population([row, row])
        spots, warnings = self.repository(path).list_for_area("POI032")

        self.assertIn("SPOT_PROTOTYPE_CONTRACT_INVALID", warnings)
        self.assertTrue(all(spot["current_population"] is None for spot in spots))

    def test_duplicate_empty_population_row_is_also_rejected(self) -> None:
        empty = self.row(
            current_population_min="",
            current_population_max="",
            forecast_60_population_min="",
            forecast_60_population_max="",
            forecast_180_population_min="",
            forecast_180_population_max="",
        )
        for rows in ([empty, empty], [empty, self.row()]):
            with self.subTest(row_count=len(rows)):
                path = self.write_population(rows)
                spots, warnings = self.repository(path).list_for_area("POI032")
                self.assertIn("SPOT_PROTOTYPE_CONTRACT_INVALID", warnings)
                self.assertTrue(all(spot["current_population"] is None for spot in spots))

    def test_default_area_provider_returns_no_data_without_writes(self) -> None:
        before = set(self.root.rglob("*"))
        area = AreaDataProvider().get("POI032")
        after = set(self.root.rglob("*"))

        self.assertEqual(area["availability"], "DATA_UNAVAILABLE")
        self.assertEqual(area["freshness"], "NO_COMPLETE_SNAPSHOT")
        self.assertIsNone(area["current_population"])
        self.assertIsNone(area["forecast_60"])
        self.assertIsNone(area["forecast_180"])
        self.assertIsNone(area["forecast_60_target_at"])
        self.assertIsNone(area["forecast_180_target_at"])
        self.assertEqual(after, before)

    def test_service_returns_five_areas_and_selected_view(self) -> None:
        service = SelectedAreaPilotService(
            area_provider=AreaDataProvider(),
            spot_repository=self.repository(),
        )

        self.assertEqual(
            [area["area_code"] for area in service.list_areas()],
            ["POI032", "POI088", "POI014", "POI025", "POI072"],
        )
        view = service.get_pilot_view("POI032")
        self.assertEqual(view["view_status"], "DATA_UNAVAILABLE")
        self.assertEqual(len(view["spot_options"]), 3)
        self.assertFalse(view["area_auto_recommendation"])
        self.assertFalse(view["spot_auto_recommendation"])
        self.assertFalse(view["official_recommendation_allowed"])
        json.dumps(view, allow_nan=False)

    def test_missing_static_master_is_service_unavailable(self) -> None:
        repository = PilotSpotOptionRepository(
            master_path=self.root / "missing-master.csv",
            population_path=None,
        )

        with self.assertRaisesRegex(
            SelectedAreaPilotError,
            "AREA_DATA_PROVIDER_UNAVAILABLE",
        ):
            repository.list_for_area("POI032")

    def test_unsupported_area_is_rejected(self) -> None:
        service = SelectedAreaPilotService(
            area_provider=AreaDataProvider(),
            spot_repository=self.repository(),
        )
        with self.assertRaisesRegex(SelectedAreaPilotError, "AREA_NOT_SUPPORTED"):
            service.get_pilot_view("POI999")


if __name__ == "__main__":
    unittest.main()
