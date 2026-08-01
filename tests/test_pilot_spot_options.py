from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from freshmanager.pilot_spot_options import (
    PILOT_SPOT_OPTION_HEADERS,
    PilotSpotOptionsError,
    load_pilot_spot_options,
)


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "data/prototype/pilot_spot_options.csv"
AREA_PANEL_PATH = ROOT / "data/reference/eg6_area_panel.csv"
ANCHOR_PATH = ROOT / "data/reference/eg6_spot_master.csv"

EXPECTED_OPTIONS = {
    "POI032-OPT-01": ("서울식물원 열린숲", "대한민국 서울특별시 강서구 가양제1동 678 서울식물원 열린숲", "37.5658219", "126.831933", "PARK_ZONE", "REPRESENTATIVE_POI_PIN"),
    "POI032-OPT-02": ("서울식물원 식물문화센터", "서울 강서구 마곡동 812", "37.5693507823043", "126.835026023981", "VENUE", "VENUE_ANCHOR"),
    "POI032-OPT-03": ("서울식물원 호수원", "서울 강서구 마곡동 812", "37.57195751126966", "126.83194015080619", "PARK_ZONE", "REPRESENTATIVE_POI_PIN"),
    "POI088-OPT-01": ("육조마당", "서울 종로구 세종로 1-68", "37.5741885600571", "126.97665327859869", "PUBLIC_SPACE", "REPRESENTATIVE_POI_PIN"),
    "POI088-OPT-02": ("해치마당", "서울 종로구 세종로 81-3", "37.57188566701743", "126.97690756151474", "PUBLIC_SPACE", "REPRESENTATIVE_POI_PIN"),
    "POI088-OPT-03": ("광장숲", "서울 종로구 세종로 1-68", "37.5708909077637", "126.976599973568", "PUBLIC_SPACE", "REPRESENTATIVE_POI_PIN"),
    "POI014-OPT-01": ("강남스퀘어", "서울 강남구 역삼동 804", "37.49835486341528", "127.02788728853392", "PUBLIC_SPACE", "PUBLIC_SPACE_PIN"),
    "POI014-OPT-02": ("CGV강남 앞", "대한민국 서울특별시 강남구 강남대로 438 스타플렉스", "37.5015586", "127.026319", "VENUE", "VENUE_ANCHOR"),
    "POI014-OPT-03": ("점프밀라노 앞", "대한민국 서울특별시 강남구 역삼동 619-4", "37.5012103", "127.0266055", "VENUE", "VENUE_ANCHOR"),
    "POI025-OPT-01": ("뚝섬역 4번 출구", "서울 성동구 성수동1가 14-17", "37.54687689826925", "127.04898713589128", "TRANSIT_EXIT", "TRANSIT_EXIT_PIN"),
    "POI025-OPT-02": ("뚝섬역 6번 출구", "서울 성동구 성수동1가 656-284", "37.54683220890765", "127.04811011414718", "TRANSIT_EXIT", "TRANSIT_EXIT_PIN"),
    "POI025-OPT-03": ("뚝섬역 8번 출구", "서울 성동구 성수동1가 656-853", "37.54753582441832", "127.04601142262756", "TRANSIT_EXIT", "TRANSIT_EXIT_PIN"),
    "POI072-OPT-01": ("여의도공원 문화의마당", "서울 영등포구 여의도동 17", "37.524630704323", "126.920336120685", "PARK_ZONE", "REPRESENTATIVE_POI_PIN"),
    "POI072-OPT-02": ("여의도공원 잔디마당", "서울 영등포구 여의도동 1", "37.5307652481477", "126.915894664452", "PARK_ZONE", "REPRESENTATIVE_POI_PIN"),
    "POI072-OPT-03": ("여의도공원 자연생태의숲", "서울 영등포구 여의도동 1-10", "37.5233674712091", "126.91766771733", "PARK_ZONE", "REPRESENTATIVE_POI_PIN"),
}


class PilotSpotOptionsTests(unittest.TestCase):
    def load(self, path: Path = MASTER_PATH) -> tuple[dict[str, str], ...]:
        return load_pilot_spot_options(
            path,
            area_panel_path=AREA_PANEL_PATH,
            anchor_path=ANCHOR_PATH,
        )

    def changed_master(
        self,
        mutate: Callable[[list[dict[str, str]]], None],
        headers: list[str] | None = None,
    ) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="pilot-spot-options-")
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "pilot_spot_options.csv"
        with MASTER_PATH.open("r", encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source, strict=True))
        mutate(rows)
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(
                target,
                fieldnames=headers or list(PILOT_SPOT_OPTION_HEADERS),
                extrasaction="ignore",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_master_matches_pm_coordinate_contract(self) -> None:
        self.assertFalse((ROOT / "data/reference/pilot_spot_options.csv").exists())
        self.assertEqual(
            hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest(),
            "754d4c57c07bf0fbee4b7b1190d2b65ef43fcf1e4a84380116868f51bb21a246",
        )
        rows = self.load()

        self.assertEqual(len(rows), 15)
        self.assertEqual(Counter(row["pilot_area_code"] for row in rows), Counter({
            "POI032": 3,
            "POI088": 3,
            "POI014": 3,
            "POI025": 3,
            "POI072": 3,
        }))
        self.assertEqual(
            {
                row["spot_option_id"]: (
                    row["spot_name"],
                    row["address"],
                    row["latitude"],
                    row["longitude"],
                    row["spot_type"],
                    row["pin_scope"],
                )
                for row in rows
            },
            EXPECTED_OPTIONS,
        )
        self.assertEqual({row["display_order"] for row in rows}, {"1", "2", "3"})
        self.assertEqual({row["spot_role"] for row in rows}, {"USER_SELECTABLE_OPTION"})
        self.assertEqual({row["spot_selection_mode"] for row in rows}, {"USER_CHOICE"})
        self.assertEqual({row["field_verification_status"] for row in rows}, {"UNAVAILABLE"})
        self.assertEqual({row["operational_suitability_status"] for row in rows}, {"NOT_VERIFIED"})

    def test_same_area_duplicate_coordinate_is_rejected(self) -> None:
        path = self.changed_master(
            lambda rows: rows[1].update({
                "latitude": rows[0]["latitude"],
                "longitude": rows[0]["longitude"],
            })
        )
        with self.assertRaises(PilotSpotOptionsError):
            self.load(path)

    def test_existing_anchor_coordinate_is_rejected(self) -> None:
        path = self.changed_master(
            lambda rows: rows[0].update({"latitude": "37.5661605", "longitude": "126.8273440"})
        )
        with self.assertRaises(PilotSpotOptionsError):
            self.load(path)

    def test_fixed_source_status_change_is_rejected(self) -> None:
        path = self.changed_master(
            lambda rows: rows[0].update({"coordinate_status": "UNVERIFIED"})
        )
        with self.assertRaises(PilotSpotOptionsError):
            self.load(path)

    def test_rank_field_is_rejected(self) -> None:
        path = self.changed_master(
            lambda rows: rows,
            [*PILOT_SPOT_OPTION_HEADERS, "rank"],
        )
        with self.assertRaises(PilotSpotOptionsError):
            self.load(path)

    def test_unapproved_url_or_local_path_is_rejected(self) -> None:
        path = self.changed_master(
            lambda rows: rows[0].update({"limitations": "file://local/reference"})
        )
        with self.assertRaises(PilotSpotOptionsError):
            self.load(path)


if __name__ == "__main__":
    unittest.main()
