from __future__ import annotations

import csv
import hashlib
import json
import os
import socket
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from freshmanager import eg8a
from freshmanager import manual_snapshot_intake as intake


SEOUL = ZoneInfo("Asia/Seoul")
RUN_ID = "11111111-1111-4111-8111-111111111111"
OTHER_RUN_ID = "22222222-2222-4222-8222-222222222222"
AREA_CODE = "POI019"


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _manifest_row(
    *,
    purpose: str = "DATA_QUALITY_VALIDATION",
    exported_at: str = "2026-07-27T12:00:00+09:00",
    contract: str = "V3",
    confirmed: str = "true",
    note: str = "manual export",
) -> list[str]:
    return [purpose, exported_at, contract, confirmed, note]


class Package:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.input_dir = root / "inputs"
        self.output_root = root / "external-output"
        self.input_dir.mkdir()
        self.output_root.mkdir()
        self.raw = self.input_dir / "raw.csv"
        self.current = self.input_dir / "current.csv"
        self.forecast = self.input_dir / "forecast.csv"
        self.upload_manifest = self.input_dir / "upload_manifest.csv"

        called_at = "2026-07-27 09:00:00"
        observed_at = "2026-07-27 09:00:00"
        forecast_at = "2026-07-27 10:00:00"
        self.raw_rows = [
            [
                RUN_ID,
                called_at,
                AREA_CODE,
                "강남 MICE 관광특구",
                "200",
                "success",
                '{"ok":true}',
            ]
        ]
        self.current_rows = [
            [
                RUN_ID,
                called_at,
                observed_at,
                AREA_CODE,
                AREA_CODE,
                "강남 MICE 관광특구",
                "보통",
                "1000",
                "1200",
            ]
        ]
        self.forecast_rows = [
            [
                RUN_ID,
                called_at,
                observed_at,
                forecast_at,
                AREA_CODE,
                AREA_CODE,
                "강남 MICE 관광특구",
                "약간 붐빔",
                "1100",
                "1300",
            ]
        ]
        self.write_sources()
        self.write_manifest()

    def write_sources(self) -> None:
        _write_csv(self.raw, list(eg8a.RAW_LOG_REQUIRED_COLUMNS), self.raw_rows)
        _write_csv(self.current, list(eg8a.CURRENT_REQUIRED_COLUMNS), self.current_rows)
        _write_csv(self.forecast, list(eg8a.FORECAST_REQUIRED_COLUMNS), self.forecast_rows)

    def write_manifest(
        self,
        *,
        header: list[str] | None = None,
        rows: list[list[str]] | None = None,
    ) -> None:
        manifest_header = [
            "snapshot_intake_purpose",
            "exported_at",
            "source_sheet_contract",
            "source_origin_confirmed_by_pm",
            "note",
        ]
        _write_csv(
            self.upload_manifest,
            manifest_header if header is None else header,
            [_manifest_row()] if rows is None else rows,
        )

    def run(self) -> intake.SnapshotIntakeResult:
        return intake.run_manual_snapshot_intake(
            raw_path=self.raw,
            current_path=self.current,
            forecast_path=self.forecast,
            upload_manifest_path=self.upload_manifest,
            output_root=self.output_root,
        )


class ManualSnapshotIntakeTests(unittest.TestCase):
    def test_valid_package_is_published_with_exact_source_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            expected = {
                "raw_log_v3": package.raw.read_bytes(),
                "population_current_v3": package.current.read_bytes(),
                "population_forecast_v3": package.forecast.read_bytes(),
                "upload_manifest": package.upload_manifest.read_bytes(),
            }

            result = package.run()

            self.assertTrue(result.published)
            self.assertIsNotNone(result.final_path)
            assert result.final_path is not None
            manifest = json.loads((result.final_path / "snapshot_manifest.json").read_text())
            report = json.loads((result.final_path / "validation_report.json").read_text())
            self.assertEqual(manifest["validation_status"], "PASS")
            self.assertTrue(report["final_publish_eligible"])
            self.assertFalse(manifest["source_files_modified"])
            for field in intake.OPERATIONAL_FALSE_FIELDS:
                self.assertIs(manifest[field], False)
            for role, payload in expected.items():
                source_path = result.final_path / manifest["relative_paths"][role]
                self.assertEqual(source_path.read_bytes(), payload)
                self.assertEqual(manifest["artifacts"][role]["sha256"], hashlib.sha256(payload).hexdigest())
                self.assertEqual(manifest["artifacts"][role]["byte_size"], len(payload))
            self.assertEqual(
                sorted(path.name for path in result.final_path.rglob("*") if path.is_file()),
                [
                    "current.csv",
                    "forecast.csv",
                    "raw.csv",
                    "snapshot_manifest.json",
                    "upload_manifest.csv",
                    "validation_report.json",
                ],
            )

    def test_each_original_role_is_opened_once_and_remains_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            sources = {
                package.raw.resolve(),
                package.current.resolve(),
                package.forecast.resolve(),
                package.upload_manifest.resolve(),
            }
            before = {path: path.read_bytes() for path in sources}

            with mock.patch.object(intake.os, "open", wraps=os.open) as tracked_open:
                result = package.run()

            self.assertTrue(result.published)
            opened_sources = [
                Path(call.args[0]).resolve()
                for call in tracked_open.call_args_list
                if Path(call.args[0]).resolve() in sources
            ]
            self.assertCountEqual(opened_sources, sources)
            self.assertEqual({path: path.read_bytes() for path in sources}, before)

    def test_manifest_requires_exact_known_header(self) -> None:
        cases = [
            ["snapshot_intake_purpose", "exported_at", "source_sheet_contract"],
            [
                "snapshot_intake_purpose",
                "exported_at",
                "source_sheet_contract",
                "source_origin_confirmed_by_pm",
                "unknown",
            ],
        ]
        for header in cases:
            with self.subTest(header=header), tempfile.TemporaryDirectory() as temp_dir:
                package = Package(Path(temp_dir))
                package.write_manifest(header=header, rows=[["x"] * len(header)])
                self._assert_error(package, "UPLOAD_MANIFEST_INVALID")

    def test_manifest_requires_exactly_one_data_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            for rows in ([], [_manifest_row(), _manifest_row()]):
                with self.subTest(row_count=len(rows)):
                    package.write_manifest(rows=rows)
                    self._assert_error(package, "UPLOAD_MANIFEST_INVALID")

    def test_manifest_note_column_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.write_manifest(
                header=list(intake.MANIFEST_REQUIRED_COLUMNS),
                rows=[_manifest_row()[:-1]],
            )
            result = package.run()
            self.assertTrue(result.published)

    def test_manifest_rejects_invalid_enum_contract_boolean_and_time(self) -> None:
        cases = [
            (_manifest_row(purpose="OPERATIONAL_OBSERVATION"), "UPLOAD_MANIFEST_INVALID"),
            (_manifest_row(contract="V2"), "UPLOAD_MANIFEST_INVALID"),
            (_manifest_row(confirmed="TRUE"), "UPLOAD_MANIFEST_INVALID"),
            (_manifest_row(exported_at="2026-07-27T12:00:00"), "UPLOAD_MANIFEST_INVALID"),
            (_manifest_row(exported_at="2026-07-27T12:00:00+08:00"), "UPLOAD_MANIFEST_INVALID"),
            (
                _manifest_row(exported_at=(datetime.now(SEOUL) + timedelta(days=1)).isoformat()),
                "UPLOAD_MANIFEST_INVALID",
            ),
        ]
        for row, code in cases:
            with self.subTest(row=row), tempfile.TemporaryDirectory() as temp_dir:
                package = Package(Path(temp_dir))
                package.write_manifest(rows=[row])
                self._assert_error(package, code)

    def test_all_approved_purposes_are_accepted_and_required_values_cannot_be_empty(self) -> None:
        for purpose in sorted(intake.PURPOSES):
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as temp_dir:
                package = Package(Path(temp_dir))
                package.write_manifest(rows=[_manifest_row(purpose=purpose)])
                self.assertTrue(package.run().published)

        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.write_manifest(rows=[_manifest_row(purpose="")])
            self._assert_error(package, "UPLOAD_MANIFEST_INVALID")

    def test_unconfirmed_origin_returns_report_without_final(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.write_manifest(rows=[_manifest_row(confirmed="false")])

            result = package.run()

            self.assertFalse(result.published)
            self.assertIsNone(result.final_path)
            self.assertFalse(result.validation_report["final_publish_eligible"])
            self.assertEqual(
                result.validation_report["blocking_reason_codes"],
                ["SOURCE_ORIGIN_NOT_CONFIRMED"],
            )
            self.assertEqual(list((package.output_root / "manual-snapshots").glob("snapshot-*")), [])
            self.assertEqual(list((package.output_root / "manual-snapshots").glob(".staging-*")), [])

    def test_input_symlink_and_role_aliases_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            symlink = package.input_dir / "raw-link.csv"
            try:
                symlink.symlink_to(package.raw)
            except OSError:
                self.skipTest("symlink unavailable")
            package.raw = symlink
            self._assert_error(package, "INPUT_FILE_INVALID")

        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.current = package.raw
            self._assert_error(package, "INPUT_ROLE_COLLISION")

    def test_hard_link_role_alias_is_rejected_by_file_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            alias = package.input_dir / "current-hard-link.csv"
            try:
                os.link(package.raw, alias)
            except OSError:
                self.skipTest("hard links unavailable")
            package.current = alias
            self._assert_error(package, "INPUT_ROLE_COLLISION")

    def test_empty_input_and_v1_header_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.raw.write_bytes(b"")
            self._assert_error(package, "INPUT_FILE_INVALID")

        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            _write_csv(package.raw, ["called_at", "area_code_requested"], [["x", AREA_CODE]])
            self._assert_error(package, "V3_HEADER_INVALID")

    def test_all_three_source_roles_require_the_exact_v3_header(self) -> None:
        cases = (
            ("raw", list(eg8a.RAW_LOG_REQUIRED_COLUMNS), self._raw_row),
            ("current", list(eg8a.CURRENT_REQUIRED_COLUMNS), self._current_row),
            ("forecast", list(eg8a.FORECAST_REQUIRED_COLUMNS), self._forecast_row),
        )
        for attribute, header, row_factory in cases:
            with self.subTest(role=attribute), tempfile.TemporaryDirectory() as temp_dir:
                package = Package(Path(temp_dir))
                path = getattr(package, attribute)
                row = row_factory(package)
                _write_csv(path, header + ["unexpected"], [row + ["x"]])
                self._assert_error(package, "V3_HEADER_INVALID")

    def test_invalid_uuid_and_three_way_link_failure_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.current_rows[0][0] = "not-a-uuid"
            package.write_sources()
            self._assert_error(package, "DATA_VALIDATION_FAILED")

        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.current_rows[0][0] = OTHER_RUN_ID
            package.write_sources()
            self._assert_error(package, "SOURCE_LINK_MISMATCH")

    def test_area_time_population_and_forecast_boundaries_are_enforced(self) -> None:
        cases = (
            ("current_rows", 3, "POI999"),
            ("current_rows", 4, "POI013"),
            ("raw_rows", 1, "not-a-time"),
            ("current_rows", 7, "-1"),
            ("current_rows", 7, "1300"),
            ("forecast_rows", 3, "2026-07-27 09:00:00"),
        )
        for rows_name, column, value in cases:
            with self.subTest(case=(rows_name, column, value)), tempfile.TemporaryDirectory() as temp_dir:
                package = Package(Path(temp_dir))
                getattr(package, rows_name)[0][column] = value
                package.write_sources()
                self._assert_error(package, "DATA_VALIDATION_FAILED")

        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.raw_rows[0][1] = "2026-07-27 9:00"
            package.current_rows[0][1] = "2026-07-27 9:00"
            package.current_rows[0][2] = "2026-07-27 9:00"
            package.forecast_rows[0][1] = "2026-07-27 9:00"
            package.forecast_rows[0][2] = "2026-07-27 9:00"
            package.forecast_rows[0][3] = "2026-07-27 10:00"
            package.write_sources()
            self.assertTrue(package.run().published)

    def test_validation_failure_exposes_only_a_bounded_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.current_rows[0][0] = "not-a-uuid"
            package.write_sources()

            with self.assertRaises(intake.SnapshotIntakeError) as caught:
                package.run()

            report = caught.exception.validation_report
            self.assertIsNotNone(report)
            assert report is not None
            self.assertEqual(report["validation_status"], "FAIL")
            self.assertEqual(report["blocking_reason_codes"], ["DATA_VALIDATION_FAILED"])
            self.assertEqual(report["file_checks"]["raw_log_v3"], "NOT_EVALUATED")
            self.assertEqual(report["source_links"]["raw_current"], "NOT_EVALUATED")
            self.assertIsNone(report["conflict_count"])
            self.assertIsNone(caught.exception.__cause__)
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn("not-a-uuid", serialized)
            self.assertNotIn(str(Path(temp_dir)), serialized)

    def test_exact_duplicate_is_retained_and_counted_once_for_unique_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.current_rows.append(list(package.current_rows[0]))
            package.write_sources()

            result = package.run()

            assert result.final_path is not None
            manifest = json.loads((result.final_path / "snapshot_manifest.json").read_text())
            current = manifest["artifacts"]["population_current_v3"]
            self.assertEqual(current["row_count"], 2)
            self.assertEqual(current["unique_row_count"], 1)
            self.assertEqual(current["duplicate_row_count"], 1)
            with (result.final_path / manifest["relative_paths"]["population_current_v3"]).open(
                encoding="utf-8", newline=""
            ) as handle:
                self.assertEqual(len(list(csv.reader(handle))), 3)

    def test_conflicting_duplicate_key_blocks_final_and_cleans_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            conflicting = list(package.current_rows[0])
            conflicting[-1] = "1400"
            package.current_rows.append(conflicting)
            package.write_sources()

            self._assert_error(package, "CONFLICTING_DUPLICATE_KEY")

            manual_root = package.output_root / "manual-snapshots"
            self.assertEqual(list(manual_root.glob("snapshot-*")), [])
            self.assertEqual(list(manual_root.glob(".staging-*")), [])

    def test_raw_exact_duplicate_and_forecast_conflict_follow_the_same_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            package.raw_rows.append(list(package.raw_rows[0]))
            package.write_sources()
            result = package.run()
            self.assertEqual(
                result.snapshot_manifest["artifacts"]["raw_log_v3"]["duplicate_row_count"],
                1,
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            conflicting = list(package.forecast_rows[0])
            conflicting[-1] = "1400"
            package.forecast_rows.append(conflicting)
            package.write_sources()
            self._assert_error(package, "CONFLICTING_DUPLICATE_KEY")

    def test_fingerprints_and_snapshot_id_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Package(Path(first_dir)).run()
            second = Package(Path(second_dir)).run()
            self.assertEqual(first.source_content_fingerprint, second.source_content_fingerprint)
            self.assertEqual(first.intake_metadata_fingerprint, second.intake_metadata_fingerprint)
            self.assertEqual(first.snapshot_id, second.snapshot_id)
            self.assertEqual(first.snapshot_id, f"snapshot-{first.source_content_fingerprint}")

    def test_same_source_duplicate_and_reclassification_are_distinct_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            first = package.run()
            assert first.final_path is not None
            before = {
                path.relative_to(first.final_path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in first.final_path.rglob("*")
                if path.is_file()
            }

            self._assert_error(package, "DUPLICATE_SNAPSHOT_BLOCKED")

            package.write_manifest(rows=[_manifest_row(purpose="HISTORICAL_ANALYSIS")])
            self._assert_error(package, "SOURCE_RECLASSIFICATION_BLOCKED")
            after = {
                path.relative_to(first.final_path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in first.final_path.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_changed_source_creates_an_independent_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            first = package.run()
            package.current_rows[0][-1] = "1201"
            package.write_sources()

            second = package.run()

            self.assertNotEqual(first.snapshot_id, second.snapshot_id)
            assert first.final_path is not None and second.final_path is not None
            self.assertTrue(first.final_path.is_dir())
            self.assertTrue(second.final_path.is_dir())

    def test_stale_staging_does_not_block_safe_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            manual_root = package.output_root / "manual-snapshots"
            manual_root.mkdir()
            stale = manual_root / ".staging-prior-failure"
            stale.mkdir()

            result = package.run()

            self.assertTrue(result.published)
            self.assertTrue(stale.is_dir())

    def test_final_integrity_recheck_blocks_staging_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            real_verify = intake._verify_staged_artifacts

            def mutate_then_verify(*args: object, **kwargs: object) -> None:
                staging_paths = args[0]
                staging_paths["raw_log_v3"].write_bytes(b"changed")
                real_verify(*args, **kwargs)

            with mock.patch.object(intake, "_verify_staged_artifacts", side_effect=mutate_then_verify):
                self._assert_error(package, "STAGING_INTEGRITY_FAILED")
            manual_root = package.output_root / "manual-snapshots"
            self.assertEqual(list(manual_root.glob("snapshot-*")), [])
            self.assertEqual(list(manual_root.glob(".staging-*")), [])

    def test_exclusive_publish_race_never_overwrites_existing_final(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))

            def create_competing_final(_staging: Path, final: Path) -> None:
                final.mkdir()
                (final / "sentinel").write_text("existing", encoding="utf-8")
                raise FileExistsError("race")

            with mock.patch.object(
                intake.eg8c_features,
                "_rename_run_root_exclusive",
                side_effect=create_competing_final,
            ):
                self._assert_error(package, "FINAL_PUBLISH_CONFLICT")

            final = next((package.output_root / "manual-snapshots").glob("snapshot-*"))
            self.assertEqual((final / "sentinel").read_text(encoding="utf-8"), "existing")
            self.assertEqual(list((package.output_root / "manual-snapshots").glob(".staging-*")), [])

    def test_output_root_must_be_existing_external_real_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            invalid_roots = [Path("/"), Path(temp_dir) / "missing"]
            regular_file = Path(temp_dir) / "file"
            regular_file.write_text("x")
            invalid_roots.append(regular_file)
            for root in invalid_roots:
                with self.subTest(root=root):
                    package.output_root = root
                    self._assert_error(package, "OUTPUT_ROOT_INVALID")

        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repository_root) as repo_temp:
            with tempfile.TemporaryDirectory() as temp_dir:
                package = Package(Path(temp_dir))
                package.output_root = Path(repo_temp)
                self._assert_error(package, "OUTPUT_ROOT_INVALID")

        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            real_root = Path(temp_dir) / "real-root"
            real_root.mkdir()
            link_root = Path(temp_dir) / "linked-root"
            try:
                link_root.symlink_to(real_root, target_is_directory=True)
            except OSError:
                self.skipTest("symlink unavailable")
            package.output_root = link_root
            self._assert_error(package, "OUTPUT_ROOT_INVALID")

    def test_eg8a_adapter_revalidates_hash_and_returns_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            result = package.run()
            assert result.final_path is not None

            adapter = intake.normalize_final_snapshot_for_eg8a(result.final_path)

            self.assertEqual(len(adapter.normalization.current_records), 1)
            self.assertEqual(len(adapter.normalization.forecast_records), 1)
            self.assertEqual(
                set(adapter.input_artifacts),
                {"raw_log_v3", "population_current_v3", "population_forecast_v3"},
            )

            manifest = json.loads((result.final_path / "snapshot_manifest.json").read_text())
            raw_path = result.final_path / manifest["relative_paths"]["raw_log_v3"]
            raw_path.write_bytes(raw_path.read_bytes() + b"tampered")
            with self.assertRaises(intake.SnapshotIntakeError) as caught:
                intake.normalize_final_snapshot_for_eg8a(result.final_path)
            self.assertEqual(caught.exception.code, "SNAPSHOT_SOURCE_INTEGRITY_FAILED")

    def test_eg8a_adapter_blocks_source_change_during_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            result = package.run()
            assert result.final_path is not None
            manifest = json.loads((result.final_path / "snapshot_manifest.json").read_text())
            raw_path = result.final_path / manifest["relative_paths"]["raw_log_v3"]
            real_normalize = eg8a.normalize_v3_sources

            def normalize_then_mutate(**paths: Path) -> eg8a.NormalizationResult:
                normalization = real_normalize(**paths)
                raw_path.write_bytes(raw_path.read_bytes() + b"tampered")
                return normalization

            with mock.patch.object(
                eg8a, "normalize_v3_sources", side_effect=normalize_then_mutate
            ), self.assertRaises(intake.SnapshotIntakeError) as caught:
                intake.normalize_final_snapshot_for_eg8a(result.final_path)

            self.assertEqual(caught.exception.code, "SNAPSHOT_SOURCE_INTEGRITY_FAILED")

    def test_eg8a_adapter_rejects_tampered_source_fingerprint_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            result = package.run()
            assert result.final_path is not None
            manifest_path = result.final_path / "snapshot_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["source_content_fingerprint"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(intake.SnapshotIntakeError) as caught:
                intake.normalize_final_snapshot_for_eg8a(result.final_path)

            self.assertEqual(caught.exception.code, "SNAPSHOT_MANIFEST_INVALID")

    def test_eg8a_adapter_revalidates_upload_manifest_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            result = package.run()
            assert result.final_path is not None
            manifest_path = result.final_path / "snapshot_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["snapshot_intake_purpose"] = "HISTORICAL_ANALYSIS"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(intake.SnapshotIntakeError) as caught:
                intake.normalize_final_snapshot_for_eg8a(result.final_path)

            self.assertEqual(caught.exception.code, "SNAPSHOT_MANIFEST_INVALID")

        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            result = package.run()
            assert result.final_path is not None
            manifest = json.loads((result.final_path / "snapshot_manifest.json").read_text())
            upload_path = result.final_path / manifest["relative_paths"]["upload_manifest"]
            upload_path.write_bytes(upload_path.read_bytes() + b"tampered")

            with self.assertRaises(intake.SnapshotIntakeError) as caught:
                intake.normalize_final_snapshot_for_eg8a(result.final_path)

            self.assertEqual(caught.exception.code, "SNAPSHOT_SOURCE_INTEGRITY_FAILED")

    def test_validation_report_does_not_include_raw_payload_or_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            result = package.run()
            report = json.dumps(result.validation_report, ensure_ascii=False)
            self.assertNotIn('{"ok":true}', report)
            self.assertNotIn(str(Path(temp_dir)), report)

    def test_staging_creation_failure_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            with mock.patch.object(tempfile, "mkdtemp", side_effect=OSError("private path")):
                with self.assertRaises(intake.SnapshotIntakeError) as caught:
                    package.run()

            self.assertEqual(caught.exception.code, "STAGING_CREATE_FAILED")
            self.assertIsNotNone(caught.exception.validation_report)
            self.assertIsNone(caught.exception.__cause__)
            self.assertNotIn(str(Path(temp_dir)), str(caught.exception))

    def test_intake_uses_no_network_and_creates_no_dataset_or_model_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Package(Path(temp_dir))
            with mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
                result = package.run()
            assert result.final_path is not None
            names = {path.name for path in package.output_root.rglob("*")}
            self.assertNotIn("dataset_manifest.json", names)
            self.assertFalse(any("model" in name for name in names))
            self.assertFalse(any("apps" in name.lower() for name in names))

    def _assert_error(self, package: Package, code: str) -> None:
        with self.assertRaises(intake.SnapshotIntakeError) as caught:
            package.run()
        self.assertEqual(caught.exception.code, code)
        self.assertIsNotNone(caught.exception.validation_report)
        self.assertIsNone(caught.exception.__cause__)

    @staticmethod
    def _raw_row(package: Package) -> list[str]:
        return list(package.raw_rows[0])

    @staticmethod
    def _current_row(package: Package) -> list[str]:
        return list(package.current_rows[0])

    @staticmethod
    def _forecast_row(package: Package) -> list[str]:
        return list(package.forecast_rows[0])


if __name__ == "__main__":
    unittest.main()
