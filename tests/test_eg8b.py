from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from freshmanager import eg8a, eg8b


RAW_LOG_HEADER = list(eg8a.RAW_LOG_REQUIRED_COLUMNS)
CURRENT_HEADER = list(eg8a.CURRENT_REQUIRED_COLUMNS)
FORECAST_HEADER = list(eg8a.FORECAST_REQUIRED_COLUMNS)

RUN_A = "11111111-1111-4111-8111-111111111111"
RUN_B = "22222222-2222-4222-8222-222222222222"


def write_csv(directory: Path, name: str, header: list[str], rows: list[list[str]]) -> Path:
    path = directory / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def raw_log_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 08:00:05",
    area: str = "POI072",
    area_name: str = "여의도",
    http_code: str = "200",
    status: str = "SUCCESS",
    raw_json: str = '{"ok":true}',
) -> list[str]:
    return [run_id, called_at, area, area_name, http_code, status, raw_json]


def current_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 08:00:05",
    observed_at: str = "2026-07-24 08:00",
    area: str = "POI072",
    area_name: str = "여의도",
    congestion: str = "여유",
    pop_min: str = "30000",
    pop_max: str = "32000",
) -> list[str]:
    return [run_id, called_at, observed_at, area, area, area_name, congestion, pop_min, pop_max]


def forecast_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 08:00:05",
    observed_at: str = "2026-07-24 08:00",
    forecast_at: str = "2026-07-24 10:00",
    area: str = "POI072",
    area_name: str = "여의도",
    congestion: str = "여유",
    pop_min: str = "29000",
    pop_max: str = "31000",
) -> list[str]:
    return [
        run_id, called_at, observed_at, forecast_at, area, area,
        area_name, congestion, pop_min, pop_max,
    ]


def build_upstream_dataset(
    *,
    staging_dir: Path,
    output_root: Path,
    current_rows: list[list[str]],
    forecast_rows: list[list[str]],
    raw_log_rows: list[list[str]] | None = None,
    dataset_id: str | None = None,
) -> eg8a.DatasetExportResult:
    """Build a real EG-8A dataset via normalize_v3_sources + export_dataset,
    using tiny synthetic input CSVs -- more integration-realistic than
    hand-faking a Manifest shape that could drift from eg8a's real one."""
    if raw_log_rows is None:
        seen: set[tuple[str, str]] = set()
        raw_log_rows = []
        for row in current_rows:
            key = (row[0], row[3])
            if key not in seen:
                seen.add(key)
                raw_log_rows.append(raw_log_row(run_id=row[0], called_at=row[1], area=row[3]))

    raw_path = write_csv(staging_dir, "raw.csv", RAW_LOG_HEADER, raw_log_rows)
    current_path = write_csv(staging_dir, "current.csv", CURRENT_HEADER, current_rows)
    forecast_path = write_csv(staging_dir, "forecast.csv", FORECAST_HEADER, forecast_rows)
    result = eg8a.normalize_v3_sources(
        raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path
    )
    return eg8a.export_dataset(
        result,
        output_root=output_root,
        input_paths={
            "raw_log_v3": raw_path,
            "population_current_v3": current_path,
            "population_forecast_v3": forecast_path,
        },
        dataset_id=dataset_id,
    )


class DatasetBundleValidationTests(unittest.TestCase):
    def test_valid_dataset_loads_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertEqual(bundle.dataset_id, export.dataset_id)
            self.assertEqual(len(bundle.current_rows), 1)
            self.assertEqual(len(bundle.forecast_rows), 1)
            self.assertEqual(bundle.error_row_count, 0)

    def test_expected_dataset_id_match_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            bundle = eg8b.load_dataset_bundle(
                export.dataset_dir, expected_dataset_id=export.dataset_id
            )
            self.assertEqual(bundle.dataset_id, export.dataset_id)

    def test_dataset_id_mismatch_raises(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(export.dataset_dir, expected_dataset_id="not-the-real-id")
            self.assertIn(eg8b.ERROR_DATASET_ID_MISMATCH, str(ctx.exception))

    def test_missing_dataset_directory_raises(self) -> None:
        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(Path(output_root) / "does-not-exist")
            self.assertIn(eg8b.ERROR_DATASET_FILE_MISSING, str(ctx.exception))

    def test_missing_output_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            (export.dataset_dir / eg8a.ERROR_ROWS_OUTPUT_FILENAME).unlink()
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertIn(eg8b.ERROR_DATASET_FILE_MISSING, str(ctx.exception))

    def test_hash_mismatch_raises(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            current_csv_path = export.dataset_dir / eg8a.CURRENT_OUTPUT_FILENAME
            content = current_csv_path.read_text(encoding="utf-8")
            self.assertIn("여유", content)
            current_csv_path.write_text(content.replace("여유", "붐빔"), encoding="utf-8")
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertIn(eg8b.ERROR_DATASET_HASH_MISMATCH, str(ctx.exception))

    def test_row_count_mismatch_raises(self) -> None:
        """Only reachable by tampering the Manifest's own recorded counts --
        tampering a CSV's row content instead would already fail the Hash
        check first, since eg8a.export_dataset hashes the actual bytes."""
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            manifest_path = export.dataset_dir / eg8a.DATASET_MANIFEST_OUTPUT_FILENAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_row_counts"]["current_normal_rows"] = 999
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertIn(eg8b.ERROR_DATASET_ROW_COUNT_MISMATCH, str(ctx.exception))


class DatasetProfileTests(unittest.TestCase):
    def test_profile_fields(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[
                    current_row(run_id=RUN_A, area="POI072"),
                    current_row(run_id=RUN_B, area="POI019", called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05"),
                ],
                forecast_rows=[
                    forecast_row(run_id=RUN_A, area="POI072"),
                    forecast_row(run_id=RUN_B, area="POI019", called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05", forecast_at="2026-07-24 10:05"),
                ],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            profile = eg8b.build_dataset_profile(
                bundle, generated_at=eg8a.parse_kst_datetime("2026-07-24 12:00:00")
            )
            self.assertEqual(profile["schema_version"], eg8b.DATASET_PROFILE_SCHEMA_VERSION)
            self.assertEqual(profile["dataset_id"], export.dataset_id)
            self.assertTrue(profile["provenance_validation"]["all_files_present"])
            self.assertTrue(profile["provenance_validation"]["all_output_hashes_match"])
            self.assertTrue(profile["provenance_validation"]["row_counts_match_manifest"])
            self.assertEqual(profile["row_counts"]["current_rows"], 2)
            self.assertEqual(profile["row_counts"]["forecast_rows"], 2)
            self.assertEqual(profile["row_counts"]["error_rows"], 0)
            self.assertEqual(profile["area_coverage"]["unexpected_areas"], [])
            self.assertEqual(profile["collection_run_count"], 2)


class AreaCurrentSummaryTests(unittest.TestCase):
    def test_per_area_statistics(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[
                    current_row(run_id=RUN_A, area="POI072", observed_at="2026-07-24 08:00", pop_min="30000", pop_max="32000", congestion="여유"),
                    current_row(run_id=RUN_B, area="POI072", called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05", pop_min="34000", pop_max="36000", congestion="보통"),
                ],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            rows = eg8b.build_area_current_summary_rows(bundle)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["area_code"], "POI072")
            self.assertEqual(row["row_count"], 2)
            self.assertEqual(row["population_min_min"], 30000)
            self.assertEqual(row["population_min_max"], 34000)
            self.assertEqual(row["population_mid_median"], 33000.0)
            self.assertEqual(row["consecutive_pairs_within_6min"], 1)
            self.assertEqual(row["consecutive_pairs_total"], 1)
            congestion_counts = json.loads(row["congestion_level_counts_json"])
            self.assertEqual(congestion_counts, {"여유": 1, "보통": 1})

    def test_no_areas_produces_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertEqual(eg8b.build_area_current_summary_rows(bundle), [])


class TimeCoverageTests(unittest.TestCase):
    def test_run_gaps_and_hour_of_day(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[
                    current_row(run_id=RUN_A, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00"),
                    current_row(run_id=RUN_B, called_at="2026-07-24 08:15:05", observed_at="2026-07-24 08:15"),
                ],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            rows = eg8b.build_time_coverage_rows(bundle)
            self.assertEqual(len(rows), 2)
            self.assertIsNone(rows[0]["gap_from_previous_run_minutes"])
            self.assertAlmostEqual(rows[1]["gap_from_previous_run_minutes"], 15.0)
            self.assertEqual(rows[0]["distinct_observed_at_count_in_run"], 1)
            self.assertEqual(rows[0]["hour_of_day"], 8)
            self.assertEqual(rows[0]["area_count"], 1)


class ForecastMatchTests(unittest.TestCase):
    def test_distinguishes_exact_match_gap_miss_and_boundary_miss(self) -> None:
        """가장 중요한 회귀 테스트: Dataset 경계로 인한 Miss와, 경계가
        아닌 진짜 관측 공백으로 인한 Miss를 정확히 구분해야 한다."""
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                raw_log_rows=[
                    raw_log_row(run_id=RUN_A, called_at="2026-07-24 08:00:05"),
                    raw_log_row(run_id=RUN_B, called_at="2026-07-24 08:10:05"),
                ],
                current_rows=[
                    # 08:05 is deliberately absent -- a genuine gap, not the
                    # dataset's time boundary (08:10 is later and present).
                    current_row(run_id=RUN_A, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00"),
                    current_row(run_id=RUN_B, called_at="2026-07-24 08:10:05", observed_at="2026-07-24 08:10", pop_min="31000", pop_max="33000"),
                ],
                forecast_rows=[
                    forecast_row(run_id=RUN_A, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00", forecast_at="2026-07-24 08:05"),
                    forecast_row(run_id=RUN_A, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00", forecast_at="2026-07-24 08:10"),
                    forecast_row(run_id=RUN_A, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00", forecast_at="2026-07-24 08:20"),
                ],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            summary = eg8b.build_forecast_match_summary(bundle)
            self.assertEqual(summary["total_forecast_rows"], 3)
            self.assertEqual(summary["exact_match_rows"], 1)
            self.assertEqual(summary["no_match_dataset_boundary_rows"], 1)
            self.assertEqual(summary["no_match_other_rows"], 1)

            pairs = eg8b.build_forecast_evaluation_pairs_rows(bundle)
            self.assertEqual(len(pairs), 1)
            self.assertEqual(pairs[0]["forecast_at"], "2026-07-24T08:10:00+09:00")
            self.assertEqual(pairs[0]["current_population_min"], 31000)
            self.assertEqual(pairs[0]["horizon_minutes"], 10)

    def test_no_forecast_rows_yields_zero_totals(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            summary = eg8b.build_forecast_match_summary(bundle)
            self.assertEqual(summary["total_forecast_rows"], 0)
            self.assertIsNone(summary["exact_match_rate"])
            self.assertEqual(eg8b.build_forecast_evaluation_pairs_rows(bundle), [])


class OutputWriterTests(unittest.TestCase):
    def test_run_phase1_creates_five_files(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as upstream_root, tempfile.TemporaryDirectory() as eg8b_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(upstream_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row(forecast_at="2026-07-24 09:00")],
            )
            result = eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            for filename in (
                eg8b.DATASET_PROFILE_FILENAME,
                eg8b.AREA_CURRENT_SUMMARY_FILENAME,
                eg8b.TIME_COVERAGE_FILENAME,
                eg8b.FORECAST_MATCH_SUMMARY_FILENAME,
                eg8b.FORECAST_EVALUATION_PAIRS_FILENAME,
            ):
                self.assertTrue((result.phase_dir / filename).is_file())
            self.assertEqual(result.phase_dir.name, eg8b.PHASE1_VERSION)
            self.assertEqual(result.phase_dir.parent.name, export.dataset_id)

    def test_upstream_dataset_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as upstream_root, tempfile.TemporaryDirectory() as eg8b_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(upstream_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row(forecast_at="2026-07-24 09:00")],
            )
            before = {
                path.name: path.read_bytes() for path in export.dataset_dir.iterdir() if path.is_file()
            }
            eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            after = {
                path.name: path.read_bytes() for path in export.dataset_dir.iterdir() if path.is_file()
            }
            self.assertEqual(before, after)

    def test_phase1_directory_collision_raises_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as upstream_root, tempfile.TemporaryDirectory() as eg8b_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(upstream_root),
                current_rows=[current_row()],
                forecast_rows=[],
            )
            first = eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            profile_before = (first.phase_dir / eg8b.DATASET_PROFILE_FILENAME).read_bytes()
            with self.assertRaises(eg8b.EvidenceWriteError):
                eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            profile_after = (first.phase_dir / eg8b.DATASET_PROFILE_FILENAME).read_bytes()
            self.assertEqual(profile_before, profile_after)

    def test_dataset_id_directory_may_preexist(self) -> None:
        """<dataset_id> is allowed to already exist so a later phase/version
        can coexist under the same parent; only phase1-v1 is exclusive."""
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as upstream_root, tempfile.TemporaryDirectory() as eg8b_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(upstream_root),
                current_rows=[current_row()],
                forecast_rows=[],
            )
            (Path(eg8b_root) / export.dataset_id).mkdir()
            result = eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            self.assertTrue(result.phase_dir.is_dir())

    def test_write_exclusive_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.txt"
            eg8b._write_exclusive(path, b"first")
            with self.assertRaises(eg8b.EvidenceWriteError):
                eg8b._write_exclusive(path, b"second")
            self.assertEqual(path.read_bytes(), b"first")


class ResolveOutputRootTests(unittest.TestCase):
    def test_missing_env_raises(self) -> None:
        with self.assertRaises(eg8b.OutputRootConfigurationError):
            eg8b.resolve_output_root_from_env({})

    def test_nonexistent_path_raises(self) -> None:
        with self.assertRaises(eg8b.OutputRootConfigurationError):
            eg8b.resolve_output_root_from_env(
                {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV: "/no/such/path/at/all/eg8b"}
            )

    def test_valid_directory_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolved = eg8b.resolve_output_root_from_env({eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV: tmp})
            self.assertTrue(resolved.is_dir())


if __name__ == "__main__":
    unittest.main()
