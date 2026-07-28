from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from freshmanager import eg8c_modeling


FEATURE_NAMES = eg8c_modeling.APPROVED_FEATURES
OLD_PROFILE_ID = "eg8c-20260727T153257-kst"
NEW_PROFILE_ID = "d5e888ef-7514-4f3a-83f5-7820dec58088"


def _patched_profiles(
    profile_id: str,
    *,
    manifest_sha256: str | None = None,
    forecast_sha256: str | None = None,
) -> dict[str, eg8c_modeling.OfficialDatasetProfile]:
    profiles = dict(eg8c_modeling.OFFICIAL_DATASET_PROFILES)
    profile = profiles[profile_id]
    profiles[profile_id] = dataclasses.replace(
        profile,
        manifest_sha256=manifest_sha256 or profile.manifest_sha256,
        forecast_sha256=forecast_sha256 or profile.forecast_sha256,
    )
    return profiles


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refresh_manifest(phase_dir: Path) -> str:
    manifest_path = phase_dir / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["output_artifacts"]:
        path = phase_dir / item["relative_path"]
        item["sha256"] = _sha256(path)
        item["byte_size"] = path.stat().st_size
    manifest_path.write_bytes(_json_bytes(manifest))
    return _sha256(manifest_path)


def _modeling_row(
    *,
    row_id: str = "validation-row",
    split: str = "VALIDATION",
    run_id: str = "source-run",
    area_code: str = "POI001",
    origin: str = "2026-07-24T01:00:00+09:00",
    target: str = "2026-07-24T02:00:00+09:00",
    current: float = 110.0,
    label: float = 115.0,
) -> eg8c_modeling.ModelingRow:
    features: dict[str, str | int | float] = {name: 1.0 for name in FEATURE_NAMES}
    features.update(
        {
            "area_code": area_code,
            "horizon_minutes": 60,
            "is_weekend": 0,
            "current_congestion_level": "보통",
            "current_population_midpoint": current,
        }
    )
    return eg8c_modeling.ModelingRow(
        row_id=row_id,
        split=split,
        features=features,
        label_value=label,
        source_collection_run_id=run_id,
        prediction_origin_at=origin,
        prediction_target_at=target,
    )


def _write_forecast(path: Path, rows: list[dict[str, object]]) -> str:
    fieldnames = [
        "collection_run_id",
        "called_at",
        "observed_at",
        "forecast_at",
        "area_code_requested",
        "area_code_returned",
        "area_name",
        "forecast_congestion_level",
        "forecast_population_min",
        "forecast_population_max",
    ]
    _write_csv(path, fieldnames, rows)
    return _sha256(path)


def _forecast_row(
    *,
    run_id: str = "source-run",
    area_code: str = "POI001",
    observed_at: str = "2026-07-24 01:00",
    forecast_at: str = "2026-07-24 02:00",
    population_min: int = 100,
    population_max: int = 120,
) -> dict[str, object]:
    return {
        "collection_run_id": run_id,
        "called_at": observed_at,
        "observed_at": observed_at,
        "forecast_at": forecast_at,
        "area_code_requested": area_code,
        "area_code_returned": area_code,
        "area_name": "합성 Area",
        "forecast_congestion_level": "보통",
        "forecast_population_min": population_min,
        "forecast_population_max": population_max,
    }


def _training_rows(origin_count: int = 8) -> tuple[eg8c_modeling.ModelingRow, ...]:
    rows = []
    for index in range(origin_count):
        hour = index + 1
        origin = f"2026-07-24T{hour:02d}:00:00+09:00"
        target = f"2026-07-24T{hour + 1:02d}:00:00+09:00"
        rows.append(
            _modeling_row(
                row_id=f"train-{index}",
                split="TRAIN",
                run_id=f"source-{index}",
                origin=origin,
                target=target,
                current=float(index),
                label=float(index * 2 + 10),
            )
        )
    rows.append(
        _modeling_row(
            row_id="validation",
            split="VALIDATION",
            run_id="source-validation",
            origin="2026-07-25T01:00:00+09:00",
            target="2026-07-25T02:00:00+09:00",
            current=10_000.0,
            label=20_010.0,
        )
    )
    return tuple(rows)


class OfficialDatasetProfileTests(unittest.TestCase):
    def test_registry_contains_only_the_two_approved_official_datasets(self) -> None:
        old_id = OLD_PROFILE_ID
        new_id = NEW_PROFILE_ID
        profiles = eg8c_modeling.OFFICIAL_DATASET_PROFILES

        self.assertEqual(set(profiles), {old_id, new_id})
        self.assertEqual(
            dataclasses.asdict(profiles[old_id]),
            {
                "identifier": old_id,
                "run_id": old_id,
                "manifest_sha256": "388a5e6649e6e23d05a442ae9b4f8d0857f8ea382011c2ff07c0af64aae42771",
                "forecast_sha256": "a5c4aaa7d711d289ee05d4ed6903b91f4ea725252ff3b6bc8890b62146441649",
                "candidate_row_count": 2236,
                "feature_valid_row_count": 2210,
                "label_valid_row_count": 2184,
                "training_eligible_row_count": 2158,
                "train_row_count": 1742,
                "validation_row_count": 416,
                "excluded_row_count": 78,
                "area_count": 13,
                "horizon_60_row_count": 1118,
                "horizon_180_row_count": 1118,
            },
        )
        self.assertEqual(
            dataclasses.asdict(profiles[new_id]),
            {
                "identifier": new_id,
                "run_id": new_id,
                "manifest_sha256": "2980db976dcfedb7631706cba0ad333295a7df2379f5a35a7281c0efc8f5116f",
                "forecast_sha256": "756952169119e88e22f352a77678b9579bea8d37e20652a621c152957d3c3626",
                "candidate_row_count": 3042,
                "feature_valid_row_count": 2990,
                "label_valid_row_count": 2990,
                "training_eligible_row_count": 2938,
                "train_row_count": 2366,
                "validation_row_count": 572,
                "excluded_row_count": 104,
                "area_count": 13,
                "horizon_60_row_count": 1521,
                "horizon_180_row_count": 1521,
            },
        )

    def test_public_run_requires_an_approved_profile_identifier(self) -> None:
        arguments = {
            "dataset_phase_dir": Path("unused-dataset"),
            "forecast_path": Path("unused-forecast.csv"),
            "output_root": Path("unused-output"),
            "run_id": "eg8c-ml-20260729T120000-kst",
        }
        with self.assertRaisesRegex(
            eg8c_modeling.ModelingContractError, "official_dataset_profile_required"
        ):
            eg8c_modeling.run_eg8c_modeling(**arguments)
        with self.assertRaisesRegex(
            eg8c_modeling.ModelingContractError, "official_dataset_profile_unknown"
        ):
            eg8c_modeling.run_eg8c_modeling(
                **arguments,
                official_dataset_profile_id="caller-supplied-contract",
            )

    def test_public_run_does_not_accept_caller_supplied_hashes_or_counts(self) -> None:
        arguments = {
            "dataset_phase_dir": Path("unused-dataset"),
            "forecast_path": Path("unused-forecast.csv"),
            "output_root": Path("unused-output"),
            "run_id": "eg8c-ml-20260729T120000-kst",
            "official_dataset_profile_id": OLD_PROFILE_ID,
        }
        for field, value in (
            ("manifest_sha256", "caller-value"),
            ("candidate_row_count", 1),
        ):
            with self.subTest(field=field), self.assertRaises(TypeError):
                eg8c_modeling.run_eg8c_modeling(**arguments, **{field: value})


def _build_locked_dataset_fixture(
    root: Path,
    profile_id: str = OLD_PROFILE_ID,
) -> tuple[Path, str]:
    profile = eg8c_modeling.OFFICIAL_DATASET_PROFILES[profile_id]
    phase_dir = root / "phase-eg8c-v1"
    phase_dir.mkdir()
    feature_fieldnames = [
        "row_id",
        "area_code",
        "prediction_origin_at",
        "prediction_target_at",
        "horizon_minutes",
        "source_collection_run_id",
        *FEATURE_NAMES[2:],
        "feature_valid",
        "feature_missing_reason",
    ]
    feature_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []
    split_rows: list[dict[str, object]] = []
    split_names = (
        ["TRAIN"] * profile.train_row_count
        + ["VALIDATION"] * profile.validation_row_count
        + ["EXCLUDED"] * profile.excluded_row_count
    )
    first_origin = datetime.fromisoformat("2026-07-24T01:00:00+09:00")
    for index, split in enumerate(split_names):
        horizon = 60 if index < profile.horizon_60_row_count else 180
        area_code = f"POI{(index % profile.area_count) + 1:03d}"
        row_id = f"row-{index:04d}"
        feature_valid = index < profile.feature_valid_row_count
        label_valid = (
            index < profile.training_eligible_row_count
            or profile.feature_valid_row_count
            <= index
            < profile.feature_valid_row_count
            + profile.label_valid_row_count
            - profile.training_eligible_row_count
        )
        origin = first_origin + timedelta(minutes=5 * (index // 26))
        target = origin + timedelta(minutes=horizon)
        feature_rows.append(
            {
                "row_id": row_id,
                "area_code": area_code,
                "prediction_origin_at": origin.isoformat(),
                "prediction_target_at": target.isoformat(),
                "horizon_minutes": horizon,
                "source_collection_run_id": f"run-{index:04d}",
                "hour": 1,
                "minute": 0,
                "day_of_week": 4,
                "is_weekend": "false",
                "hour_sin": 0.1,
                "hour_cos": 0.9,
                "day_of_week_sin": 0.2,
                "day_of_week_cos": 0.8,
                "current_population_min": 100,
                "current_population_max": 120,
                "current_population_midpoint": 110,
                "current_population_interval_width": 20,
                "current_congestion_level": "보통",
                "population_lag_5m": 109,
                "population_lag_15m": 108,
                "population_lag_30m": 107,
                "population_lag_60m": 106,
                "population_delta_5m": 1,
                "population_delta_15m": 2,
                "population_delta_30m": 3,
                "population_delta_60m": 4,
                "rolling_mean_15m": 108,
                "rolling_mean_30m": 107,
                "rolling_mean_60m": 106,
                "rolling_std_30m": 1,
                "rolling_std_60m": 2,
                "feature_valid": str(feature_valid).lower(),
                "feature_missing_reason": "" if feature_valid else "missing",
            }
        )
        label_rows.append(
            {
                "row_id": row_id,
                "area_code": area_code,
                "prediction_origin_at": origin.isoformat(),
                "prediction_target_at": target.isoformat(),
                "horizon_minutes": horizon,
                "label_name": "target_population_midpoint",
                "label_value": 115,
                "label_valid": str(label_valid).lower(),
                "label_missing_reason": "" if label_valid else "missing",
            }
        )
        split_rows.append(
            {
                "row_id": row_id,
                "split": split,
                "split_reason": "fixed chronology",
                "split_boundary_version": "eg8c-provisional-split-v1",
            }
        )

    _write_csv(phase_dir / "feature_dataset.csv", feature_fieldnames, feature_rows)
    _write_csv(
        phase_dir / "label_dataset.csv",
        list(label_rows[0]),
        label_rows,
    )
    _write_csv(
        phase_dir / "split_assignment.csv",
        list(split_rows[0]),
        split_rows,
    )
    (phase_dir / "feature_dictionary.json").write_bytes(
        _json_bytes(
            {
                "schema_version": "eg8c-feature-dictionary-v1",
                "features": {name: {"status": "synthetic"} for name in FEATURE_NAMES[2:]},
                "identification_columns": {
                    "area_code": "model input candidate",
                    "horizon_minutes": "model input candidate",
                },
                "excluded_this_round": [],
            }
        )
    )
    (phase_dir / "label_contract.json").write_bytes(
        _json_bytes(
            {
                "schema_version": "eg8c-label-contract-v1",
                "label_name": "target_population_midpoint",
                "definition": "(target_population_min + target_population_max) / 2",
                "target_time": "prediction_target_at",
                "generation_condition": "exact match",
                "missing_condition": "missing target",
                "evaluation_metrics_candidates": ["MAE", "RMSE"],
                "excluded_labels_this_round": [],
            }
        )
    )
    (phase_dir / "leakage_report.json").write_bytes(
        _json_bytes(
            {
                "schema_version": "eg8c-leakage-report-v1",
                "checks": {
                    check_id: {"violation_count": 0, "violation_row_ids": []}
                    for check_id in eg8c_modeling.REQUIRED_LEAKAGE_CHECKS
                },
                "total_violation_count": 0,
                "final_verdict": "PASS",
            }
        )
    )
    (phase_dir / "dataset_coverage.json").write_bytes(
        _json_bytes(
            {
                "schema_version": "eg8c-dataset-coverage-v1",
                "candidate_row_count": profile.candidate_row_count,
                "feature_valid_row_count": profile.feature_valid_row_count,
                "label_valid_row_count": profile.label_valid_row_count,
                "training_eligible_row_count": profile.training_eligible_row_count,
                "split_row_counts": {
                    "TRAIN": profile.train_row_count,
                    "VALIDATION": profile.validation_row_count,
                    "EXCLUDED": profile.excluded_row_count,
                },
                "area_coverage": {
                    "areas": [f"POI{index:03d}" for index in range(1, profile.area_count + 1)],
                    "observed_area_count": profile.area_count,
                },
                "horizon_coverage": {
                    "60": profile.horizon_60_row_count,
                    "180": profile.horizon_180_row_count,
                },
                "eg8c_run_id": profile.run_id,
            }
        )
    )
    artifact_names = sorted(eg8c_modeling.LOCKED_DATASET_FILES - {"dataset_manifest.json"})
    manifest = {
        "schema_version": "eg8c-output-manifest-v1",
        "eg8c_run_id": profile.run_id,
        "evaluation_status": "PROVISIONAL",
        "data_sufficiency_status": "PROVISIONAL_SPLIT_ONLY",
        "supported_horizons_minutes": [60, 180],
        "test_split_created": False,
        "official_model_gate_judgment": None,
        "hash_algorithm": "sha256",
        "input_artifacts": [],
        "output_artifacts": [
            {
                "relative_path": name,
                "sha256": _sha256(phase_dir / name),
                "byte_size": (phase_dir / name).stat().st_size,
            }
            for name in artifact_names
        ],
    }
    (phase_dir / "dataset_manifest.json").write_bytes(_json_bytes(manifest))
    return phase_dir, _sha256(phase_dir / "dataset_manifest.json")


class LockedDatasetContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.phase_dir, self.manifest_sha = _build_locked_dataset_fixture(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _load(self) -> eg8c_modeling.LockedDataset:
        with mock.patch.object(
            eg8c_modeling,
            "OFFICIAL_DATASET_PROFILES",
            _patched_profiles(OLD_PROFILE_ID, manifest_sha256=self.manifest_sha),
        ):
            return eg8c_modeling.load_locked_dataset(
                self.phase_dir,
                official_dataset_profile_id=OLD_PROFILE_ID,
            )

    def test_locked_manifest_sha_must_match(self) -> None:
        with self.assertRaisesRegex(eg8c_modeling.ModelingContractError, "manifest_sha_mismatch"):
            eg8c_modeling.load_locked_dataset(
                self.phase_dir,
                official_dataset_profile_id=OLD_PROFILE_ID,
            )

    def test_locked_dataset_requires_exact_eight_files_and_hashes(self) -> None:
        self.assertEqual(len(self._load().feature_rows), 2236)
        for mutation in ("missing", "extra", "hash"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                copied = Path(directory) / "phase-eg8c-v1"
                shutil.copytree(self.phase_dir, copied)
                if mutation == "missing":
                    (copied / "feature_dictionary.json").unlink()
                elif mutation == "extra":
                    (copied / "unexpected.txt").write_text("unexpected", encoding="utf-8")
                else:
                    (copied / "feature_dictionary.json").write_text("{}\n", encoding="utf-8")
                copied_sha = _sha256(copied / "dataset_manifest.json")
                with mock.patch.object(
                    eg8c_modeling,
                    "OFFICIAL_DATASET_PROFILES",
                    _patched_profiles(OLD_PROFILE_ID, manifest_sha256=copied_sha),
                ):
                    with self.assertRaises(eg8c_modeling.ModelingContractError):
                        eg8c_modeling.load_locked_dataset(
                            copied,
                            official_dataset_profile_id=OLD_PROFILE_ID,
                        )

    def test_locked_contract_requires_run_counts_and_statuses(self) -> None:
        loaded = self._load()
        self.assertEqual(loaded.manifest["eg8c_run_id"], OLD_PROFILE_ID)
        self.assertEqual(loaded.split_counts, {"TRAIN": 1742, "VALIDATION": 416, "EXCLUDED": 78})
        self.assertEqual(tuple(loaded.approved_features), FEATURE_NAMES)
        self.assertEqual(loaded.label_name, "target_population_midpoint")

        coverage_path = self.phase_dir / "dataset_coverage.json"
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        coverage["candidate_row_count"] = 2235
        coverage_path.write_bytes(_json_bytes(coverage))
        self.manifest_sha = _refresh_manifest(self.phase_dir)
        with self.assertRaisesRegex(eg8c_modeling.ModelingContractError, "candidate_count_mismatch"):
            self._load()

    def test_each_approved_profile_validates_its_own_run_and_counts(self) -> None:
        for profile_id, profile in eg8c_modeling.OFFICIAL_DATASET_PROFILES.items():
            with self.subTest(profile_id=profile_id), tempfile.TemporaryDirectory() as directory:
                phase_dir, manifest_sha = _build_locked_dataset_fixture(
                    Path(directory), profile_id
                )
                profiles = dict(eg8c_modeling.OFFICIAL_DATASET_PROFILES)
                profiles[profile_id] = dataclasses.replace(
                    profile, manifest_sha256=manifest_sha
                )
                with mock.patch.object(
                    eg8c_modeling, "OFFICIAL_DATASET_PROFILES", profiles
                ):
                    loaded = eg8c_modeling.load_locked_dataset(
                        phase_dir,
                        official_dataset_profile_id=profile_id,
                    )
            self.assertEqual(loaded.manifest["eg8c_run_id"], profile.run_id)
            self.assertEqual(len(loaded.feature_rows), profile.candidate_row_count)
            self.assertEqual(
                loaded.split_counts,
                {
                    "TRAIN": profile.train_row_count,
                    "VALIDATION": profile.validation_row_count,
                    "EXCLUDED": profile.excluded_row_count,
                },
            )

    def test_selected_profile_rejects_a_different_official_run(self) -> None:
        new_id = NEW_PROFILE_ID
        new_profile = eg8c_modeling.OFFICIAL_DATASET_PROFILES[new_id]
        profiles = dict(eg8c_modeling.OFFICIAL_DATASET_PROFILES)
        profiles[new_id] = dataclasses.replace(
            new_profile, manifest_sha256=self.manifest_sha
        )
        with (
            mock.patch.object(eg8c_modeling, "OFFICIAL_DATASET_PROFILES", profiles),
            self.assertRaisesRegex(
                eg8c_modeling.ModelingContractError,
                "manifest_eg8c_run_id_mismatch",
            ),
        ):
            eg8c_modeling.load_locked_dataset(
                self.phase_dir,
                official_dataset_profile_id=new_id,
            )

    def test_selected_profile_rejects_count_area_and_horizon_mismatches(self) -> None:
        profile_id = OLD_PROFILE_ID
        profile = eg8c_modeling.OFFICIAL_DATASET_PROFILES[profile_id]
        mutations = {
            "candidate_row_count": ("candidate_row_count", 2235, "candidate_count_mismatch"),
            "split_row_counts": (
                "split_row_counts",
                {"TRAIN": 1741, "VALIDATION": 417, "EXCLUDED": 78},
                "split_count_mismatch",
            ),
            "area_count": (
                "area_coverage",
                {"areas": ["POI001"], "observed_area_count": 1},
                "area_count_mismatch",
            ),
            "horizon_coverage": (
                "horizon_coverage",
                {"60": 1117, "180": 1119},
                "horizon_count_mismatch",
            ),
        }
        for label, (field, value, reason) in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                copied = Path(directory) / "phase-eg8c-v1"
                shutil.copytree(self.phase_dir, copied)
                coverage_path = copied / "dataset_coverage.json"
                coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
                coverage[field] = value
                coverage_path.write_bytes(_json_bytes(coverage))
                manifest_sha = _refresh_manifest(copied)
                profiles = dict(eg8c_modeling.OFFICIAL_DATASET_PROFILES)
                profiles[profile_id] = dataclasses.replace(
                    profile, manifest_sha256=manifest_sha
                )
                with (
                    mock.patch.object(eg8c_modeling, "OFFICIAL_DATASET_PROFILES", profiles),
                    self.assertRaisesRegex(eg8c_modeling.ModelingContractError, reason),
                ):
                    eg8c_modeling.load_locked_dataset(
                        copied,
                        official_dataset_profile_id=profile_id,
                    )


class TrainingMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        phase_dir, manifest_sha = _build_locked_dataset_fixture(Path(self.temp.name))
        with mock.patch.object(
            eg8c_modeling,
            "OFFICIAL_DATASET_PROFILES",
            _patched_profiles(OLD_PROFILE_ID, manifest_sha256=manifest_sha),
        ):
            self.locked = eg8c_modeling.load_locked_dataset(
                phase_dir,
                official_dataset_profile_id=OLD_PROFILE_ID,
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_training_matrix_is_exact_row_id_join_with_28_x_and_one_y(self) -> None:
        rows = eg8c_modeling.build_training_matrix(self.locked)
        self.assertEqual(len(rows), 2158)
        self.assertEqual(
            set(rows[0].artifact_values),
            {"row_id", "split", *FEATURE_NAMES, "label_value"},
        )
        self.assertEqual(len(rows[0].features), 28)
        self.assertEqual(rows[0].label_value, 115.0)

    def test_duplicate_or_missing_row_id_fails(self) -> None:
        for label_rows in (
            self.locked.label_rows[:-1],
            (*self.locked.label_rows[:-1], self.locked.label_rows[0]),
        ):
            with self.subTest(row_count=len(label_rows)):
                changed = dataclasses.replace(self.locked, label_rows=tuple(label_rows))
                with self.assertRaisesRegex(eg8c_modeling.ModelingContractError, "row_id"):
                    eg8c_modeling.build_training_matrix(changed)

    def test_feature_label_metadata_mismatch_fails(self) -> None:
        labels = list(self.locked.label_rows)
        labels[0] = {**labels[0], "area_code": "POI999"}
        changed = dataclasses.replace(self.locked, label_rows=tuple(labels))
        with self.assertRaisesRegex(eg8c_modeling.ModelingContractError, "metadata_mismatch"):
            eg8c_modeling.build_training_matrix(changed)

    def test_excluded_rows_never_enter_matrix(self) -> None:
        rows = eg8c_modeling.build_training_matrix(self.locked)
        self.assertEqual({row.split for row in rows}, {"TRAIN", "VALIDATION"})
        self.assertFalse({row.row_id for row in rows} & {
            row_id for row_id, split in self.locked.split_by_row_id.items() if split == "EXCLUDED"
        })


class BaselineTests(unittest.TestCase):
    def test_current_population_baseline_uses_origin_midpoint(self) -> None:
        row = _modeling_row(current=123.5)
        predictions = eg8c_modeling.build_baseline_predictions((row,))
        self.assertEqual(predictions[eg8c_modeling.BASELINE_CURRENT][row.row_id], 123.5)

    def test_seoul_forecast_baseline_requires_exact_source_join(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecast.csv"
            digest = _write_forecast(path, [_forecast_row(population_min=120, population_max=140)])
            row = _modeling_row()
            predictions = eg8c_modeling.build_baseline_predictions(
                (row,), forecast_path=path, expected_forecast_sha256=digest
            )
        self.assertEqual(predictions[eg8c_modeling.BASELINE_SEOUL_FORECAST][row.row_id], 130.0)

    def test_seoul_forecast_missing_or_duplicate_join_fails(self) -> None:
        row = _modeling_row()
        for source_rows in ([], [_forecast_row(), _forecast_row()]):
            with self.subTest(source_count=len(source_rows)), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "forecast.csv"
                digest = _write_forecast(path, source_rows)
                with self.assertRaisesRegex(eg8c_modeling.ModelingContractError, "forecast_join"):
                    eg8c_modeling.build_baseline_predictions(
                        (row,), forecast_path=path, expected_forecast_sha256=digest
                    )

    def test_all_baselines_use_identical_validation_row_ids(self) -> None:
        rows = (
            _modeling_row(row_id="v1"),
            _modeling_row(row_id="v2", run_id="source-run-2", area_code="POI002"),
            _modeling_row(row_id="train", split="TRAIN"),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecast.csv"
            digest = _write_forecast(
                path,
                [_forecast_row(), _forecast_row(run_id="source-run-2", area_code="POI002")],
            )
            predictions = eg8c_modeling.build_baseline_predictions(
                rows, forecast_path=path, expected_forecast_sha256=digest
            )
        self.assertEqual(set(predictions[eg8c_modeling.BASELINE_CURRENT]), {"v1", "v2"})
        self.assertEqual(
            set(predictions[eg8c_modeling.BASELINE_CURRENT]),
            set(predictions[eg8c_modeling.BASELINE_SEOUL_FORECAST]),
        )


class PreprocessingTests(unittest.TestCase):
    def test_preprocessing_fits_train_only(self) -> None:
        bundle = eg8c_modeling.train_models(_training_rows())
        transformer = bundle.linear.named_steps["preprocessor"]
        scaler = transformer.named_transformers_["numeric"]
        feature_index = eg8c_modeling.NUMERIC_FEATURES.index("current_population_midpoint")
        self.assertAlmostEqual(scaler.mean_[feature_index], 3.5)

    def test_missing_approved_feature_fails_without_imputation(self) -> None:
        rows = list(_training_rows())
        features = dict(rows[0].features)
        features.pop("rolling_std_60m")
        rows[0] = dataclasses.replace(rows[0], features=features)
        with self.assertRaisesRegex(eg8c_modeling.ModelingContractError, "approved_feature_missing"):
            eg8c_modeling.train_models(tuple(rows))


class ModelTrainingTests(unittest.TestCase):
    def test_ridge_uses_only_the_pm_fixed_alpha_without_search(self) -> None:
        rows = _training_rows()
        real_ridge = eg8c_modeling.Ridge
        created_alphas = []

        def create_ridge(*args: object, **kwargs: object) -> object:
            created_alphas.append(kwargs.get("alpha", args[0] if args else 1.0))
            return real_ridge(*args, **kwargs)

        with mock.patch.object(eg8c_modeling, "Ridge", side_effect=create_ridge):
            bundle = eg8c_modeling.train_models(rows)

        self.assertEqual(bundle.ridge_alpha, 100.0)
        self.assertEqual(created_alphas, [100.0])
        self.assertEqual(bundle.ridge.named_steps["model"].alpha, 100.0)
        self.assertFalse(hasattr(eg8c_modeling, "build_expanding_origin_folds"))


class EvaluationTests(unittest.TestCase):
    def test_mae_rmse_and_median_absolute_error_match_known_fixture(self) -> None:
        metrics = eg8c_modeling.compute_regression_metrics(
            {"a": 0.0, "b": 10.0}, {"a": 2.0, "b": 6.0}
        )
        self.assertEqual(metrics["row_count"], 2)
        self.assertEqual(metrics["mae"], 3.0)
        self.assertAlmostEqual(metrics["rmse"], 10 ** 0.5)
        self.assertEqual(metrics["median_absolute_error"], 3.0)

    def test_all_candidates_use_identical_validation_row_ids(self) -> None:
        rows = (_modeling_row(row_id="a"), _modeling_row(row_id="b"))
        predictions = {
            name: {"a": 110.0, "b": 110.0}
            for name in (
                eg8c_modeling.BASELINE_CURRENT,
                eg8c_modeling.BASELINE_SEOUL_FORECAST,
                eg8c_modeling.MODEL_LINEAR,
                eg8c_modeling.MODEL_RIDGE,
            )
        }
        predictions[eg8c_modeling.MODEL_RIDGE].pop("b")
        with self.assertRaisesRegex(eg8c_modeling.ModelingContractError, "validation_row_set"):
            eg8c_modeling.evaluate_predictions(rows, predictions)

    def test_selection_requires_mae_improvement_and_nonworse_rmse(self) -> None:
        overall = {
            eg8c_modeling.BASELINE_CURRENT: {"mae": 5.0, "rmse": 6.0},
            eg8c_modeling.BASELINE_SEOUL_FORECAST: {"mae": 4.0, "rmse": 5.0},
            eg8c_modeling.MODEL_LINEAR: {"mae": 3.9, "rmse": 5.1},
            eg8c_modeling.MODEL_RIDGE: {"mae": 3.9, "rmse": 5.0},
        }
        decision = eg8c_modeling.select_provisional_decision(overall)
        self.assertEqual(decision["strongest_baseline"], eg8c_modeling.BASELINE_SEOUL_FORECAST)
        self.assertFalse(decision["model_assessments"][eg8c_modeling.MODEL_LINEAR]["passed"])
        self.assertTrue(decision["model_assessments"][eg8c_modeling.MODEL_RIDGE]["passed"])
        self.assertEqual(decision["provisional_winner"], eg8c_modeling.MODEL_RIDGE)

    def test_horizon_metrics_are_reported_but_not_used_as_success_gate(self) -> None:
        row_60 = _modeling_row(row_id="h60", label=100.0)
        row_180 = _modeling_row(row_id="h180", label=100.0)
        row_180 = dataclasses.replace(
            row_180,
            features={**row_180.features, "horizon_minutes": 180},
        )
        predictions = {
            eg8c_modeling.BASELINE_CURRENT: {"h60": 90.0, "h180": 90.0},
            eg8c_modeling.BASELINE_SEOUL_FORECAST: {"h60": 91.0, "h180": 91.0},
            eg8c_modeling.MODEL_LINEAR: {"h60": 100.0, "h180": 88.0},
            eg8c_modeling.MODEL_RIDGE: {"h60": 90.0, "h180": 90.0},
        }
        report = eg8c_modeling.evaluate_predictions((row_60, row_180), predictions)
        self.assertEqual(set(report["metrics"][eg8c_modeling.MODEL_LINEAR]["by_horizon"]), {"60", "180"})
        self.assertEqual(report["provisional_winner"], eg8c_modeling.MODEL_LINEAR)

    def test_failed_candidates_retain_best_baseline_and_null_official_gate(self) -> None:
        overall = {
            eg8c_modeling.BASELINE_CURRENT: {"mae": 4.0, "rmse": 5.0},
            eg8c_modeling.BASELINE_SEOUL_FORECAST: {"mae": 5.0, "rmse": 6.0},
            eg8c_modeling.MODEL_LINEAR: {"mae": 4.0, "rmse": 5.0},
            eg8c_modeling.MODEL_RIDGE: {"mae": 4.1, "rmse": 4.9},
        }
        decision = eg8c_modeling.select_provisional_decision(overall)
        self.assertEqual(decision["provisional_winner"], eg8c_modeling.BASELINE_CURRENT)
        self.assertEqual(decision["decision_type"], "BASELINE_RETAINED")
        self.assertIsNone(decision["official_model_gate_judgment"])


class ModelingArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.phase_dir, self.manifest_sha = _build_locked_dataset_fixture(self.root)
        with mock.patch.object(
            eg8c_modeling,
            "OFFICIAL_DATASET_PROFILES",
            _patched_profiles(OLD_PROFILE_ID, manifest_sha256=self.manifest_sha),
        ):
            self.locked = eg8c_modeling.load_locked_dataset(
                self.phase_dir,
                official_dataset_profile_id=OLD_PROFILE_ID,
            )
        self.matrix = eg8c_modeling.build_training_matrix(self.locked)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _forecast_path(self) -> tuple[Path, str]:
        source_rows = []
        for row in self.matrix:
            if row.split != "VALIDATION":
                continue
            origin = datetime.fromisoformat(row.prediction_origin_at).strftime("%Y-%m-%d %H:%M:%S")
            target = datetime.fromisoformat(row.prediction_target_at).strftime("%Y-%m-%d %H:%M:%S")
            source_rows.append(
                _forecast_row(
                    run_id=row.source_collection_run_id,
                    area_code=str(row.features["area_code"]),
                    observed_at=origin,
                    forecast_at=target,
                    population_min=100,
                    population_max=120,
                )
            )
        path = self.root / "forecast.csv"
        return path, _write_forecast(path, source_rows)

    def test_success_writes_exactly_five_artifacts_with_matching_manifest(self) -> None:
        forecast_path, forecast_sha = self._forecast_path()
        output_root = self.root / "modeling-output"
        output_root.mkdir()
        with mock.patch.object(
            eg8c_modeling,
            "OFFICIAL_DATASET_PROFILES",
            _patched_profiles(
                OLD_PROFILE_ID,
                manifest_sha256=self.manifest_sha,
                forecast_sha256=forecast_sha,
            ),
        ):
            result = eg8c_modeling.run_eg8c_modeling(
                dataset_phase_dir=self.phase_dir,
                forecast_path=forecast_path,
                output_root=output_root,
                run_id="eg8c-ml-20260727T170000-kst",
                official_dataset_profile_id=OLD_PROFILE_ID,
                generated_at=datetime.fromisoformat("2026-07-27T17:00:00+09:00"),
            )
        self.assertEqual({path.name for path in result.run_dir.iterdir()}, eg8c_modeling.MODELING_OUTPUT_FILES)
        manifest = json.loads((result.run_dir / "modeling_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["output_artifacts"]), 4)
        for item in manifest["output_artifacts"]:
            path = result.run_dir / item["relative_path"]
            self.assertEqual(item["sha256"], _sha256(path))
            self.assertEqual(item["byte_size"], path.stat().st_size)
        self.assertEqual(result.evaluation_report["validation_row_count"], 416)
        metadata = json.loads(
            (result.run_dir / "model_metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["schema_version"], "eg8c-model-metadata-v2")
        self.assertEqual(metadata["dataset_run_id"], OLD_PROFILE_ID)
        self.assertEqual(metadata["dataset_manifest_sha256"], self.manifest_sha)
        self.assertEqual(metadata["source_forecast_sha256"], forecast_sha)
        ridge_metadata = metadata["models"][eg8c_modeling.MODEL_RIDGE]
        self.assertEqual(
            ridge_metadata,
            {
                "alpha": 100.0,
                "selection_method": "PM_FIXED",
                "automatic_tuning_performed": False,
                "alpha_candidates": [100.0],
                "time_ordered_alpha_comparison_performed": False,
            },
        )

    def test_selected_profile_rejects_a_different_forecast_sha(self) -> None:
        forecast_path, _ = self._forecast_path()
        output_root = self.root / "modeling-output"
        output_root.mkdir()
        with (
            mock.patch.object(
                eg8c_modeling,
                "OFFICIAL_DATASET_PROFILES",
                _patched_profiles(OLD_PROFILE_ID, manifest_sha256=self.manifest_sha),
            ),
            self.assertRaisesRegex(
                eg8c_modeling.ModelingContractError,
                "forecast_sha_mismatch",
            ),
        ):
            eg8c_modeling.run_eg8c_modeling(
                dataset_phase_dir=self.phase_dir,
                forecast_path=forecast_path,
                output_root=output_root,
                run_id="eg8c-ml-20260729T120001-kst",
                official_dataset_profile_id=OLD_PROFILE_ID,
            )

    def test_existing_modeling_run_is_never_overwritten(self) -> None:
        output_root = self.root / "modeling-output"
        final = output_root / "eg8c-ml-20260727T170000-kst"
        final.mkdir(parents=True)
        sentinel = final / "sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(eg8c_modeling.ModelingWriteError):
            eg8c_modeling._publish_modeling_artifacts(
                output_root,
                final.name,
                {name: b"x" for name in eg8c_modeling.MODELING_CONTENT_FILES},
                self.manifest_sha,
                "forecast-sha",
            )
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_failure_removes_current_staging_only(self) -> None:
        output_root = self.root / "modeling-output"
        output_root.mkdir()
        existing = output_root / "existing-run"
        existing.mkdir()
        with (
            mock.patch.object(eg8c_modeling, "_write_exclusive", side_effect=OSError("private")),
            self.assertRaises(eg8c_modeling.ModelingWriteError),
        ):
            eg8c_modeling._publish_modeling_artifacts(
                output_root,
                "eg8c-ml-20260727T170001-kst",
                {name: b"x" for name in eg8c_modeling.MODELING_CONTENT_FILES},
                self.manifest_sha,
                "forecast-sha",
            )
        self.assertEqual({path.name for path in output_root.iterdir()}, {"existing-run"})

    def test_source_dataset_hashes_are_unchanged(self) -> None:
        before = {path.name: _sha256(path) for path in self.phase_dir.iterdir()}
        with mock.patch.object(
            eg8c_modeling,
            "OFFICIAL_DATASET_PROFILES",
            _patched_profiles(OLD_PROFILE_ID, manifest_sha256=self.manifest_sha),
        ):
            loaded = eg8c_modeling.load_locked_dataset(
                self.phase_dir,
                official_dataset_profile_id=OLD_PROFILE_ID,
            )
        eg8c_modeling.build_training_matrix(loaded)
        after = {path.name: _sha256(path) for path in self.phase_dir.iterdir()}
        self.assertEqual(before, after)

    def test_public_run_hides_unexpected_internal_path_errors(self) -> None:
        with (
            mock.patch.object(eg8c_modeling, "_dataset_hashes", side_effect=OSError("/private/path")),
            self.assertRaises(eg8c_modeling.ModelingWriteError) as caught,
        ):
            eg8c_modeling.run_eg8c_modeling(
                dataset_phase_dir=self.phase_dir,
                forecast_path=self.root / "forecast.csv",
                output_root=self.root,
                run_id="eg8c-ml-20260727T170002-kst",
                official_dataset_profile_id=OLD_PROFILE_ID,
            )
        self.assertNotIn("/private/path", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
