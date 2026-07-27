"""Locked EG-8C Dataset validation and provisional modeling."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import io
import json
import math
import platform
import re
import shutil
import stat
import statistics
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import eg8a
from . import eg8b_b2a
from . import eg8c_features


LOCKED_DATASET_RUN_ID = "eg8c-20260727T153257-kst"
LOCKED_MANIFEST_SHA256 = "388a5e6649e6e23d05a442ae9b4f8d0857f8ea382011c2ff07c0af64aae42771"
LOCKED_FORECAST_SHA256 = "a5c4aaa7d711d289ee05d4ed6903b91f4ea725252ff3b6bc8890b62146441649"
LOCKED_DATASET_FILES = frozenset(
    {
        "feature_dataset.csv",
        "label_dataset.csv",
        "split_assignment.csv",
        "feature_dictionary.json",
        "label_contract.json",
        "leakage_report.json",
        "dataset_coverage.json",
        "dataset_manifest.json",
    }
)
APPROVED_FEATURES = (
    "area_code",
    "horizon_minutes",
    "hour",
    "minute",
    "day_of_week",
    "is_weekend",
    "hour_sin",
    "hour_cos",
    "day_of_week_sin",
    "day_of_week_cos",
    "current_population_min",
    "current_population_max",
    "current_population_midpoint",
    "current_population_interval_width",
    "current_congestion_level",
    "population_lag_5m",
    "population_lag_15m",
    "population_lag_30m",
    "population_lag_60m",
    "population_delta_5m",
    "population_delta_15m",
    "population_delta_30m",
    "population_delta_60m",
    "rolling_mean_15m",
    "rolling_mean_30m",
    "rolling_mean_60m",
    "rolling_std_30m",
    "rolling_std_60m",
)
REQUIRED_LEAKAGE_CHECKS = frozenset(
    {
        "duplicate_row_id",
        "feature_timestamp_after_origin",
        "future_actual_used_as_feature",
        "label_target_before_origin",
        "label_target_wrong_area",
        "lag_timestamp_not_before_origin",
        "missing_value_silently_filled",
        "post_cutoff_forecast_used",
        "rolling_window_end_after_origin",
        "same_origin_split_across_boundary",
        "train_origin_not_earlier_than_validation",
        "validation_statistics_used_in_train",
    }
)
EXPECTED_COUNTS = {
    "candidate_row_count": 2236,
    "feature_valid_row_count": 2210,
    "label_valid_row_count": 2184,
    "training_eligible_row_count": 2158,
}
EXPECTED_SPLIT_COUNTS = {"TRAIN": 1742, "VALIDATION": 416, "EXCLUDED": 78}
BASELINE_CURRENT = "current_population_baseline"
BASELINE_SEOUL_FORECAST = "seoul_forecast_baseline"
MODEL_LINEAR = "linear_regression"
MODEL_RIDGE = "ridge_regression"
RIDGE_ALPHAS = (0.1, 1.0, 10.0, 100.0)
CATEGORICAL_FEATURES = ("area_code", "current_congestion_level")
BOOLEAN_FEATURES = ("is_weekend",)
NUMERIC_FEATURES = tuple(
    name for name in APPROVED_FEATURES if name not in CATEGORICAL_FEATURES + BOOLEAN_FEATURES
)
MODELING_CONTENT_FILES = frozenset(
    {
        "training_matrix.csv",
        "validation_predictions.csv",
        "model_metadata.json",
        "evaluation_report.json",
    }
)
MODELING_OUTPUT_FILES = MODELING_CONTENT_FILES | {"modeling_manifest.json"}
_RUN_ID_PATTERN = re.compile(r"eg8c-ml-\d{8}T\d{6}-kst\Z")


class ModelingContractError(ValueError):
    """Raised when locked inputs do not match the approved modeling contract."""


class ModelingWriteError(OSError):
    """Raised when a Modeling Run cannot be published safely."""


@dataclass(frozen=True)
class LockedDataset:
    phase_dir: Path
    manifest: Mapping[str, object]
    manifest_sha256: str
    feature_rows: tuple[dict[str, str], ...]
    label_rows: tuple[dict[str, str], ...]
    split_by_row_id: Mapping[str, str]
    split_counts: Mapping[str, int]
    approved_features: tuple[str, ...]
    label_name: str


@dataclass(frozen=True)
class ModelingRow:
    row_id: str
    split: str
    features: Mapping[str, str | int | float]
    label_value: float
    source_collection_run_id: str
    prediction_origin_at: str
    prediction_target_at: str

    @property
    def artifact_values(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "split": self.split,
            **self.features,
            "label_value": self.label_value,
        }


@dataclass(frozen=True)
class TrainedModels:
    linear: Pipeline
    ridge: Pipeline
    ridge_alpha: float
    ridge_cv_mae: Mapping[float, float]
    training_row_ids: frozenset[str]


@dataclass(frozen=True)
class ModelingResult:
    run_id: str
    run_dir: Path
    evaluation_report: Mapping[str, object]
    modeling_manifest: Mapping[str, object]


def _fail(reason: str) -> None:
    raise ModelingContractError(f"eg8c_modeling_contract_error: {reason}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        _fail("input_unreadable")
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("json_invalid")
    if not isinstance(value, dict):
        _fail("json_object_required")
    return value


def _read_csv(path: Path) -> tuple[dict[str, str], ...]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
                _fail("csv_header_invalid")
            rows = tuple(dict(row) for row in reader)
    except (OSError, UnicodeError, csv.Error):
        _fail("csv_invalid")
    return rows


def _require_regular_files(phase_dir: Path) -> None:
    try:
        root_status = phase_dir.lstat()
        entries = tuple(phase_dir.iterdir())
    except OSError:
        _fail("dataset_root_unreadable")
    if stat.S_ISLNK(root_status.st_mode) or not stat.S_ISDIR(root_status.st_mode):
        _fail("dataset_root_invalid")
    if {entry.name for entry in entries} != LOCKED_DATASET_FILES:
        _fail("dataset_file_set_mismatch")
    for entry in entries:
        try:
            mode = entry.lstat().st_mode
        except OSError:
            _fail("dataset_file_unreadable")
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            _fail("dataset_file_type_invalid")


def _validate_manifest(phase_dir: Path) -> tuple[dict[str, object], str]:
    manifest_path = phase_dir / "dataset_manifest.json"
    digest = _sha256(manifest_path)
    if digest != LOCKED_MANIFEST_SHA256:
        _fail("manifest_sha_mismatch")
    manifest = _read_json(manifest_path)
    expected_state = {
        "schema_version": "eg8c-output-manifest-v1",
        "eg8c_run_id": LOCKED_DATASET_RUN_ID,
        "evaluation_status": "PROVISIONAL",
        "data_sufficiency_status": "PROVISIONAL_SPLIT_ONLY",
        "supported_horizons_minutes": [60, 180],
        "test_split_created": False,
        "official_model_gate_judgment": None,
        "hash_algorithm": "sha256",
    }
    for field, expected in expected_state.items():
        if manifest.get(field) != expected:
            _fail(f"manifest_{field}_mismatch")
    artifacts = manifest.get("output_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 7:
        _fail("manifest_output_set_mismatch")
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            _fail("manifest_output_invalid")
        name = item.get("relative_path")
        if not isinstance(name, str) or name in seen or name == "dataset_manifest.json":
            _fail("manifest_output_invalid")
        seen.add(name)
        path = phase_dir / name
        if item.get("sha256") != _sha256(path) or item.get("byte_size") != path.stat().st_size:
            _fail("output_hash_mismatch")
    if seen != LOCKED_DATASET_FILES - {"dataset_manifest.json"}:
        _fail("manifest_output_set_mismatch")
    return manifest, digest


def _unique_row_index(rows: tuple[dict[str, str], ...], label: str) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        row_id = row.get("row_id", "")
        if not row_id or row_id in index:
            _fail(f"{label}_row_id_invalid")
        index[row_id] = row
    return index


def load_locked_dataset(phase_dir: Path) -> LockedDataset:
    """Load the approved Run #2 artifacts without modifying them."""
    _require_regular_files(phase_dir)
    manifest, manifest_sha = _validate_manifest(phase_dir)
    coverage = _read_json(phase_dir / "dataset_coverage.json")
    for field, expected in EXPECTED_COUNTS.items():
        if coverage.get(field) != expected:
            short = field.removesuffix("_row_count")
            _fail(f"{short}_count_mismatch")
    if coverage.get("split_row_counts") != EXPECTED_SPLIT_COUNTS:
        _fail("split_count_mismatch")
    area_coverage = coverage.get("area_coverage")
    if not isinstance(area_coverage, dict) or area_coverage.get("observed_area_count") != 13:
        _fail("area_count_mismatch")
    if coverage.get("horizon_coverage") != {"60": 1118, "180": 1118}:
        _fail("horizon_count_mismatch")
    if coverage.get("eg8c_run_id") != LOCKED_DATASET_RUN_ID:
        _fail("coverage_run_id_mismatch")

    feature_dictionary = _read_json(phase_dir / "feature_dictionary.json")
    dictionary_features = feature_dictionary.get("features")
    identifiers = feature_dictionary.get("identification_columns")
    if (
        not isinstance(dictionary_features, dict)
        or set(dictionary_features) != set(APPROVED_FEATURES[2:])
        or not isinstance(identifiers, dict)
        or not {"area_code", "horizon_minutes"}.issubset(identifiers)
    ):
        _fail("approved_feature_contract_mismatch")

    label_contract = _read_json(phase_dir / "label_contract.json")
    if label_contract.get("label_name") != "target_population_midpoint":
        _fail("label_contract_mismatch")

    leakage = _read_json(phase_dir / "leakage_report.json")
    checks = leakage.get("checks")
    if not isinstance(checks, dict):
        _fail("leakage_contract_mismatch")
    if (
        leakage.get("final_verdict") != "PASS"
        or leakage.get("total_violation_count") != 0
        or set(checks) != REQUIRED_LEAKAGE_CHECKS
        or len(checks) != len(REQUIRED_LEAKAGE_CHECKS)
        or any(
            not isinstance(item, dict)
            or item.get("violation_count") != 0
            or item.get("violation_row_ids") != []
            for item in checks.values()
        )
    ):
        _fail("leakage_contract_mismatch")

    feature_rows = _read_csv(phase_dir / "feature_dataset.csv")
    label_rows = _read_csv(phase_dir / "label_dataset.csv")
    split_rows = _read_csv(phase_dir / "split_assignment.csv")
    if not all(len(rows) == EXPECTED_COUNTS["candidate_row_count"] for rows in (feature_rows, label_rows, split_rows)):
        _fail("candidate_count_mismatch")
    feature_index = _unique_row_index(feature_rows, "feature")
    label_index = _unique_row_index(label_rows, "label")
    split_index = _unique_row_index(split_rows, "split")
    if set(feature_index) != set(label_index) or set(feature_index) != set(split_index):
        _fail("row_id_set_mismatch")
    split_by_row_id = {row_id: row.get("split", "") for row_id, row in split_index.items()}
    split_counts = dict(Counter(split_by_row_id.values()))
    if split_counts != EXPECTED_SPLIT_COUNTS:
        _fail("split_count_mismatch")
    if sum(row.get("feature_valid") == "true" for row in feature_rows) != EXPECTED_COUNTS["feature_valid_row_count"]:
        _fail("feature_valid_count_mismatch")
    if sum(row.get("label_valid") == "true" for row in label_rows) != EXPECTED_COUNTS["label_valid_row_count"]:
        _fail("label_valid_count_mismatch")
    for row in feature_rows:
        for feature in APPROVED_FEATURES:
            value = row.get(feature)
            if value is None:
                _fail("approved_feature_missing")
            if feature not in {"area_code", "current_congestion_level", "is_weekend"} and value:
                try:
                    if not math.isfinite(float(value)):
                        _fail("approved_feature_nonfinite")
                except ValueError:
                    _fail("approved_feature_invalid")
    return LockedDataset(
        phase_dir=phase_dir,
        manifest=manifest,
        manifest_sha256=manifest_sha,
        feature_rows=feature_rows,
        label_rows=label_rows,
        split_by_row_id=split_by_row_id,
        split_counts=split_counts,
        approved_features=APPROVED_FEATURES,
        label_name="target_population_midpoint",
    )


_INTEGER_FEATURES = frozenset(
    {
        "horizon_minutes",
        "hour",
        "minute",
        "day_of_week",
        "current_population_min",
        "current_population_max",
        "current_population_interval_width",
    }
)
_CATEGORICAL_FEATURES = frozenset({"area_code", "current_congestion_level"})


def _feature_value(name: str, value: str) -> str | int | float:
    if value == "":
        _fail("approved_feature_missing")
    if name in _CATEGORICAL_FEATURES:
        return value
    if name == "is_weekend":
        if value not in {"true", "false"}:
            _fail("boolean_feature_invalid")
        return int(value == "true")
    try:
        number = float(value)
    except ValueError:
        _fail("approved_feature_invalid")
    if not math.isfinite(number):
        _fail("approved_feature_nonfinite")
    if name in _INTEGER_FEATURES:
        if not number.is_integer():
            _fail("integer_feature_invalid")
        return int(number)
    return number


def build_training_matrix(dataset: LockedDataset) -> tuple[ModelingRow, ...]:
    """Join the locked Feature, Label, and Split rows exactly by ``row_id``."""
    feature_index = _unique_row_index(dataset.feature_rows, "feature")
    label_index = _unique_row_index(dataset.label_rows, "label")
    row_ids = set(feature_index)
    if row_ids != set(label_index) or row_ids != set(dataset.split_by_row_id):
        _fail("row_id_set_mismatch")
    rows: list[ModelingRow] = []
    metadata_fields = (
        "area_code",
        "prediction_origin_at",
        "prediction_target_at",
        "horizon_minutes",
    )
    for row_id in sorted(row_ids):
        split = dataset.split_by_row_id[row_id]
        if split == "EXCLUDED":
            continue
        if split not in {"TRAIN", "VALIDATION"}:
            _fail("split_value_invalid")
        feature_row = feature_index[row_id]
        label_row = label_index[row_id]
        if any(feature_row.get(field) != label_row.get(field) for field in metadata_fields):
            _fail("feature_label_metadata_mismatch")
        if feature_row.get("feature_valid") != "true" or label_row.get("label_valid") != "true":
            _fail("eligible_row_invalid")
        if label_row.get("label_name") != dataset.label_name:
            _fail("label_name_mismatch")
        try:
            label_value = float(label_row.get("label_value", ""))
        except ValueError:
            _fail("label_value_invalid")
        if not math.isfinite(label_value):
            _fail("label_value_nonfinite")
        features = {
            name: _feature_value(name, feature_row.get(name, ""))
            for name in APPROVED_FEATURES
        }
        source_run_id = feature_row.get("source_collection_run_id", "")
        origin = feature_row.get("prediction_origin_at", "")
        target = feature_row.get("prediction_target_at", "")
        if not source_run_id or not origin or not target:
            _fail("audit_metadata_missing")
        rows.append(
            ModelingRow(
                row_id=row_id,
                split=split,
                features=features,
                label_value=label_value,
                source_collection_run_id=source_run_id,
                prediction_origin_at=origin,
                prediction_target_at=target,
            )
        )
    if Counter(row.split for row in rows) != {"TRAIN": 1742, "VALIDATION": 416}:
        _fail("eligible_split_count_mismatch")
    return tuple(rows)


def _forecast_key(
    collection_run_id: str,
    area_code: str,
    observed_at: str,
    forecast_at: str,
) -> tuple[str, str, str, str]:
    try:
        origin = eg8a.to_iso8601(eg8a.parse_kst_datetime(observed_at))
        target = eg8a.to_iso8601(eg8a.parse_kst_datetime(forecast_at))
    except ValueError:
        _fail("forecast_time_invalid")
    return collection_run_id, area_code, origin, target


def _load_forecast_index(
    forecast_path: Path,
    expected_sha256: str,
) -> dict[tuple[str, str, str, str], float]:
    try:
        mode = forecast_path.lstat().st_mode
    except OSError:
        _fail("forecast_input_unreadable")
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        _fail("forecast_input_type_invalid")
    if _sha256(forecast_path) != expected_sha256:
        _fail("forecast_sha_mismatch")
    required = {
        "collection_run_id",
        "observed_at",
        "forecast_at",
        "area_code_requested",
        "area_code_returned",
        "forecast_population_min",
        "forecast_population_max",
    }
    try:
        with forecast_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                _fail("forecast_header_invalid")
            index: dict[tuple[str, str, str, str], float] = {}
            duplicate_keys: set[tuple[str, str, str, str]] = set()
            for row in reader:
                requested = row.get("area_code_requested", "")
                if not requested or requested != row.get("area_code_returned"):
                    _fail("forecast_area_invalid")
                key = _forecast_key(
                    row.get("collection_run_id", ""),
                    requested,
                    row.get("observed_at", ""),
                    row.get("forecast_at", ""),
                )
                try:
                    lower = float(row.get("forecast_population_min", ""))
                    upper = float(row.get("forecast_population_max", ""))
                except ValueError:
                    _fail("forecast_population_invalid")
                if not all(math.isfinite(value) for value in (lower, upper)) or lower > upper:
                    _fail("forecast_population_invalid")
                if key in index:
                    duplicate_keys.add(key)
                index[key] = (lower + upper) / 2
    except (OSError, UnicodeError, csv.Error):
        _fail("forecast_input_unreadable")
    if duplicate_keys:
        _fail("forecast_join_duplicate")
    return index


def build_baseline_predictions(
    rows: tuple[ModelingRow, ...],
    *,
    forecast_path: Path | None = None,
    expected_forecast_sha256: str | None = None,
) -> dict[str, dict[str, float]]:
    """Build B0 and, when supplied, exact-join Seoul Forecast predictions."""
    validation_rows = tuple(row for row in rows if row.split == "VALIDATION")
    current = {
        row.row_id: float(row.features["current_population_midpoint"])
        for row in validation_rows
    }
    predictions = {BASELINE_CURRENT: current}
    if forecast_path is None and expected_forecast_sha256 is None:
        return predictions
    if forecast_path is None or expected_forecast_sha256 is None:
        _fail("forecast_contract_incomplete")
    forecast_index = _load_forecast_index(forecast_path, expected_forecast_sha256)
    forecast: dict[str, float] = {}
    for row in validation_rows:
        key = (
            row.source_collection_run_id,
            str(row.features["area_code"]),
            row.prediction_origin_at,
            row.prediction_target_at,
        )
        if key not in forecast_index:
            _fail("forecast_join_missing")
        forecast[row.row_id] = forecast_index[key]
    if set(current) != set(forecast):
        _fail("forecast_join_row_set_mismatch")
    predictions[BASELINE_SEOUL_FORECAST] = forecast
    return predictions


def _x(rows: tuple[ModelingRow, ...]) -> list[list[str | int | float]]:
    values: list[list[str | int | float]] = []
    for row in rows:
        if set(row.features) != set(APPROVED_FEATURES):
            _fail("approved_feature_missing")
        item = [row.features[name] for name in APPROVED_FEATURES]
        if any(value == "" or value is None for value in item):
            _fail("approved_feature_missing")
        values.append(item)
    return values


def _pipeline(model: LinearRegression | Ridge) -> Pipeline:
    categorical_indices = [APPROVED_FEATURES.index(name) for name in CATEGORICAL_FEATURES]
    boolean_indices = [APPROVED_FEATURES.index(name) for name in BOOLEAN_FEATURES]
    numeric_indices = [APPROVED_FEATURES.index(name) for name in NUMERIC_FEATURES]
    preprocessor = ColumnTransformer(
        (
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical_indices,
            ),
            ("boolean", "passthrough", boolean_indices),
            ("numeric", StandardScaler(), numeric_indices),
        )
    )
    return Pipeline((("preprocessor", preprocessor), ("model", model)))


def build_expanding_origin_folds(
    rows: tuple[ModelingRow, ...],
) -> tuple[tuple[frozenset[str], frozenset[str]], ...]:
    train_rows = tuple(row for row in rows if row.split == "TRAIN")
    origins = sorted({row.prediction_origin_at for row in train_rows})
    if len(origins) < 4:
        _fail("ridge_origin_groups_insufficient")
    folds = []
    for train_indices, holdout_indices in TimeSeriesSplit(n_splits=3).split(origins):
        train_origins = {origins[index] for index in train_indices}
        holdout_origins = {origins[index] for index in holdout_indices}
        folds.append(
            (
                frozenset(row.row_id for row in train_rows if row.prediction_origin_at in train_origins),
                frozenset(row.row_id for row in train_rows if row.prediction_origin_at in holdout_origins),
            )
        )
    return tuple(folds)


def train_models(rows: tuple[ModelingRow, ...]) -> TrainedModels:
    """Fit approved preprocessing and models using TRAIN rows only."""
    if sklearn.__version__ != "1.6.1":
        _fail("sklearn_version_mismatch")
    _x(rows)
    train_rows = tuple(row for row in rows if row.split == "TRAIN")
    if not train_rows:
        _fail("training_rows_missing")
    by_id = {row.row_id: row for row in train_rows}
    folds = build_expanding_origin_folds(rows)
    cv_mae: dict[float, float] = {}
    for alpha in RIDGE_ALPHAS:
        scores = []
        for train_ids, holdout_ids in folds:
            fold_train = tuple(by_id[row_id] for row_id in sorted(train_ids))
            fold_holdout = tuple(by_id[row_id] for row_id in sorted(holdout_ids))
            pipeline = _pipeline(Ridge(alpha=alpha))
            pipeline.fit(_x(fold_train), [row.label_value for row in fold_train])
            predictions = pipeline.predict(_x(fold_holdout))
            scores.append(float(mean_absolute_error([row.label_value for row in fold_holdout], predictions)))
        cv_mae[alpha] = sum(scores) / len(scores)
    selected_alpha = min(RIDGE_ALPHAS, key=lambda alpha: (cv_mae[alpha], alpha))
    linear = _pipeline(LinearRegression())
    ridge = _pipeline(Ridge(alpha=selected_alpha))
    train_x = _x(train_rows)
    train_y = [row.label_value for row in train_rows]
    linear.fit(train_x, train_y)
    ridge.fit(train_x, train_y)
    return TrainedModels(
        linear=linear,
        ridge=ridge,
        ridge_alpha=selected_alpha,
        ridge_cv_mae=cv_mae,
        training_row_ids=frozenset(row.row_id for row in train_rows),
    )


def predict_models(
    models: TrainedModels,
    rows: tuple[ModelingRow, ...],
) -> dict[str, dict[str, float]]:
    validation_rows = tuple(row for row in rows if row.split == "VALIDATION")
    validation_x = _x(validation_rows)
    predictions = {
        MODEL_LINEAR: models.linear.predict(validation_x),
        MODEL_RIDGE: models.ridge.predict(validation_x),
    }
    result: dict[str, dict[str, float]] = {}
    for name, values in predictions.items():
        mapped = {row.row_id: float(value) for row, value in zip(validation_rows, values)}
        if not all(math.isfinite(value) for value in mapped.values()):
            _fail("model_prediction_nonfinite")
        result[name] = mapped
    return result


def compute_regression_metrics(
    actual_by_row_id: Mapping[str, float],
    prediction_by_row_id: Mapping[str, float],
) -> dict[str, int | float]:
    if not actual_by_row_id or set(actual_by_row_id) != set(prediction_by_row_id):
        _fail("validation_row_set_mismatch")
    errors = [
        abs(actual_by_row_id[row_id] - prediction_by_row_id[row_id])
        for row_id in sorted(actual_by_row_id)
    ]
    shared = eg8b_b2a._compute_metrics(errors, (), (), ())
    return {
        "row_count": len(errors),
        "mae": float(shared["mae"]),
        "rmse": float(shared["rmse"]),
        "median_absolute_error": float(statistics.median(errors)),
    }


def select_provisional_decision(
    overall_metrics: Mapping[str, Mapping[str, float]],
) -> dict[str, object]:
    required = {BASELINE_CURRENT, BASELINE_SEOUL_FORECAST, MODEL_LINEAR, MODEL_RIDGE}
    if set(overall_metrics) != required:
        _fail("evaluation_candidate_set_mismatch")
    strongest_baseline = min(
        (BASELINE_CURRENT, BASELINE_SEOUL_FORECAST),
        key=lambda name: (overall_metrics[name]["mae"], overall_metrics[name]["rmse"]),
    )
    baseline = overall_metrics[strongest_baseline]
    assessments: dict[str, dict[str, object]] = {}
    passed = []
    for model_name in (MODEL_LINEAR, MODEL_RIDGE):
        metrics = overall_metrics[model_name]
        mae_improved = metrics["mae"] < baseline["mae"]
        rmse_nonworse = metrics["rmse"] <= baseline["rmse"]
        model_passed = mae_improved and rmse_nonworse
        assessments[model_name] = {
            "mae_improved": mae_improved,
            "rmse_nonworse": rmse_nonworse,
            "passed": model_passed,
            "mae_difference_from_strongest_baseline": metrics["mae"] - baseline["mae"],
            "rmse_difference_from_strongest_baseline": metrics["rmse"] - baseline["rmse"],
        }
        if model_passed:
            passed.append(model_name)
    if passed:
        winner = min(
            passed,
            key=lambda name: (overall_metrics[name]["mae"], 0 if name == MODEL_LINEAR else 1),
        )
        decision_type = "PROVISIONAL_MODEL_WINNER"
    else:
        winner = strongest_baseline
        decision_type = "BASELINE_RETAINED"
    return {
        "strongest_baseline": strongest_baseline,
        "model_assessments": assessments,
        "provisional_winner": winner,
        "decision_type": decision_type,
        "evaluation_status": "PROVISIONAL",
        "official_model_gate_judgment": None,
    }


def evaluate_predictions(
    rows: tuple[ModelingRow, ...],
    predictions: Mapping[str, Mapping[str, float]],
) -> dict[str, object]:
    validation_rows = tuple(row for row in rows if row.split == "VALIDATION")
    actual = {row.row_id: row.label_value for row in validation_rows}
    if len(actual) != len(validation_rows):
        _fail("validation_row_id_duplicate")
    required = {BASELINE_CURRENT, BASELINE_SEOUL_FORECAST, MODEL_LINEAR, MODEL_RIDGE}
    if set(predictions) != required:
        _fail("evaluation_candidate_set_mismatch")
    if any(set(candidate) != set(actual) for candidate in predictions.values()):
        _fail("validation_row_set_mismatch")

    def grouped_metrics(row_ids: set[str]) -> dict[str, dict[str, int | float]]:
        actual_subset = {row_id: actual[row_id] for row_id in row_ids}
        return {
            name: compute_regression_metrics(
                actual_subset,
                {row_id: float(candidate[row_id]) for row_id in row_ids},
            )
            for name, candidate in predictions.items()
        }

    overall = grouped_metrics(set(actual))
    horizons = sorted({int(row.features["horizon_minutes"]) for row in validation_rows})
    areas = sorted({str(row.features["area_code"]) for row in validation_rows})
    metrics: dict[str, dict[str, object]] = {
        name: {"overall": overall[name], "by_horizon": {}, "by_area": {}}
        for name in required
    }
    for horizon in horizons:
        row_ids = {
            row.row_id
            for row in validation_rows
            if int(row.features["horizon_minutes"]) == horizon
        }
        grouped = grouped_metrics(row_ids)
        for name in required:
            metrics[name]["by_horizon"][str(horizon)] = grouped[name]
    for area in areas:
        row_ids = {
            row.row_id for row in validation_rows if str(row.features["area_code"]) == area
        }
        grouped = grouped_metrics(row_ids)
        for name in required:
            metrics[name]["by_area"][area] = grouped[name]
    decision = select_provisional_decision(overall)
    return {
        "schema_version": "eg8c-model-evaluation-v1",
        "evaluation_status": "PROVISIONAL",
        "data_sufficiency_status": "PROVISIONAL_SPLIT_ONLY",
        "test_split_created": False,
        "official_model_gate_judgment": None,
        "validation_row_count": len(validation_rows),
        "metrics": metrics,
        **decision,
        "limitations": [
            "No test split is available.",
            "The locked Snapshot covers a short provisional period.",
            "This result is not an official model gate decision.",
        ],
    }


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _csv_bytes(fieldnames: tuple[str, ...], rows: list[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _write_exclusive(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
    except OSError:
        raise ModelingWriteError("eg8c_modeling_write_error: artifact_write_failed") from None


def _runtime_versions() -> dict[str, object]:
    packages = {}
    for name in ("scikit-learn", "numpy", "scipy", "joblib", "threadpoolctl"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            _fail("runtime_package_missing")
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "packages": packages,
    }


def _dataset_hashes(phase_dir: Path) -> dict[str, str]:
    return {name: _sha256(phase_dir / name) for name in sorted(LOCKED_DATASET_FILES)}


def _publish_modeling_artifacts(
    output_root: Path,
    run_id: str,
    payloads: Mapping[str, bytes],
    source_dataset_manifest_sha256: str,
    source_forecast_sha256: str,
) -> tuple[Path, dict[str, object]]:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise ModelingWriteError("eg8c_modeling_write_error: run_id_invalid")
    if set(payloads) != MODELING_CONTENT_FILES:
        raise ModelingWriteError("eg8c_modeling_write_error: artifact_set_invalid")
    try:
        mode = output_root.lstat().st_mode
        resolved_root = output_root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ModelingWriteError("eg8c_modeling_write_error: output_root_invalid") from None
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ModelingWriteError("eg8c_modeling_write_error: output_root_invalid")
    if any((parent / ".git").exists() for parent in (resolved_root, *resolved_root.parents)):
        raise ModelingWriteError("eg8c_modeling_write_error: git_output_forbidden")
    final_run = resolved_root / run_id
    if final_run.exists() or final_run.is_symlink():
        raise ModelingWriteError("eg8c_modeling_write_error: run_exists")
    try:
        staging = Path(tempfile.mkdtemp(prefix=".eg8c-ml-staging-", dir=resolved_root))
    except OSError:
        raise ModelingWriteError("eg8c_modeling_write_error: staging_create_failed") from None
    published = False
    try:
        for name in sorted(payloads):
            _write_exclusive(staging / name, payloads[name])
        artifacts = [
            {
                "relative_path": name,
                "sha256": hashlib.sha256(payloads[name]).hexdigest(),
                "byte_size": len(payloads[name]),
            }
            for name in sorted(payloads)
        ]
        manifest = {
            "schema_version": "eg8c-modeling-manifest-v1",
            "hash_algorithm": "sha256",
            "source_dataset_manifest_sha256": source_dataset_manifest_sha256,
            "source_forecast_sha256": source_forecast_sha256,
            "output_artifacts": artifacts,
        }
        _write_exclusive(staging / "modeling_manifest.json", _json_bytes(manifest))
        if {path.name for path in staging.iterdir()} != MODELING_OUTPUT_FILES:
            raise ModelingWriteError("eg8c_modeling_write_error: staged_artifact_set_mismatch")
        for item in artifacts:
            path = staging / str(item["relative_path"])
            if _sha256(path) != item["sha256"] or path.stat().st_size != item["byte_size"]:
                raise ModelingWriteError("eg8c_modeling_write_error: staged_artifact_hash_mismatch")
        try:
            eg8c_features._rename_run_root_exclusive(staging, final_run)
        except OSError:
            raise ModelingWriteError("eg8c_modeling_write_error: publish_failed") from None
        published = True
        return final_run, manifest
    except BaseException as error:
        if not published and staging.exists():
            try:
                shutil.rmtree(staging)
            except OSError:
                raise ModelingWriteError("eg8c_modeling_write_error: staging_cleanup_failed") from None
        if isinstance(error, OSError) and not isinstance(error, ModelingWriteError):
            raise ModelingWriteError("eg8c_modeling_write_error: artifact_write_failed") from None
        raise


def _modeling_payloads(
    *,
    rows: tuple[ModelingRow, ...],
    predictions: Mapping[str, Mapping[str, float]],
    models: TrainedModels,
    evaluation_report: Mapping[str, object],
    run_id: str,
    generated_at: datetime,
    dataset_hashes: Mapping[str, str],
    forecast_sha256: str,
) -> dict[str, bytes]:
    matrix_fields = ("row_id", "split", *APPROVED_FEATURES, "label_value")
    matrix_payload = _csv_bytes(matrix_fields, [row.artifact_values for row in rows])
    validation_rows = tuple(row for row in rows if row.split == "VALIDATION")
    prediction_fields = (
        "row_id",
        "actual_value",
        BASELINE_CURRENT,
        BASELINE_SEOUL_FORECAST,
        MODEL_LINEAR,
        MODEL_RIDGE,
    )
    prediction_payload = _csv_bytes(
        prediction_fields,
        [
            {
                "row_id": row.row_id,
                "actual_value": row.label_value,
                **{name: candidate[row.row_id] for name, candidate in predictions.items()},
            }
            for row in validation_rows
        ],
    )
    metadata = {
        "schema_version": "eg8c-model-metadata-v1",
        "modeling_run_id": run_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "dataset_run_id": LOCKED_DATASET_RUN_ID,
        "dataset_manifest_sha256": LOCKED_MANIFEST_SHA256,
        "source_dataset_artifact_sha256": dict(dataset_hashes),
        "source_forecast_sha256": forecast_sha256,
        "features": list(APPROVED_FEATURES),
        "label_name": "target_population_midpoint",
        "preprocessing": {
            "categorical": {
                "features": list(CATEGORICAL_FEATURES),
                "method": "OneHotEncoder(handle_unknown=ignore)",
            },
            "boolean": {"features": list(BOOLEAN_FEATURES), "method": "0_or_1"},
            "numeric": {"features": list(NUMERIC_FEATURES), "method": "StandardScaler"},
            "fit_scope": "TRAIN_ONLY",
        },
        "models": {
            MODEL_LINEAR: {"parameters": {}},
            MODEL_RIDGE: {
                "alpha": models.ridge_alpha,
                "alpha_candidates": list(RIDGE_ALPHAS),
                "cv_mean_mae": {str(key): value for key, value in models.ridge_cv_mae.items()},
                "cv": "3_expanding_origin_folds_train_only",
            },
        },
        "training_row_count": len(models.training_row_ids),
        "validation_row_count": len(validation_rows),
        "runtime": _runtime_versions(),
        "model_serialized": False,
    }
    return {
        "training_matrix.csv": matrix_payload,
        "validation_predictions.csv": prediction_payload,
        "model_metadata.json": _json_bytes(metadata),
        "evaluation_report.json": _json_bytes(dict(evaluation_report)),
    }


def _run_eg8c_modeling(
    *,
    dataset_phase_dir: Path,
    forecast_path: Path,
    output_root: Path,
    run_id: str,
    generated_at: datetime | None = None,
) -> ModelingResult:
    """Run the approved provisional comparison once and publish five artifacts."""
    resolved_generated_at = generated_at or datetime.now(eg8a.SEOUL)
    dataset_before = _dataset_hashes(dataset_phase_dir)
    forecast_before = _sha256(forecast_path)
    if forecast_before != LOCKED_FORECAST_SHA256:
        _fail("forecast_sha_mismatch")
    dataset = load_locked_dataset(dataset_phase_dir)
    try:
        dataset_phase_dir.resolve(strict=True).relative_to(output_root.resolve(strict=True))
    except ValueError:
        pass
    else:
        raise ModelingWriteError("eg8c_modeling_write_error: dataset_output_overlap")
    rows = build_training_matrix(dataset)
    predictions = build_baseline_predictions(
        rows,
        forecast_path=forecast_path,
        expected_forecast_sha256=LOCKED_FORECAST_SHA256,
    )
    models = train_models(rows)
    predictions.update(predict_models(models, rows))
    evaluation_report = evaluate_predictions(rows, predictions)
    payloads = _modeling_payloads(
        rows=rows,
        predictions=predictions,
        models=models,
        evaluation_report=evaluation_report,
        run_id=run_id,
        generated_at=resolved_generated_at,
        dataset_hashes=dataset_before,
        forecast_sha256=forecast_before,
    )
    if _dataset_hashes(dataset_phase_dir) != dataset_before or _sha256(forecast_path) != forecast_before:
        _fail("source_changed_during_run")
    run_dir, manifest = _publish_modeling_artifacts(
        output_root,
        run_id,
        payloads,
        dataset.manifest_sha256,
        forecast_before,
    )
    return ModelingResult(
        run_id=run_id,
        run_dir=run_dir,
        evaluation_report=evaluation_report,
        modeling_manifest=manifest,
    )


def run_eg8c_modeling(
    *,
    dataset_phase_dir: Path,
    forecast_path: Path,
    output_root: Path,
    run_id: str,
    generated_at: datetime | None = None,
) -> ModelingResult:
    """Public bounded-error entry point for one approved provisional run."""
    try:
        return _run_eg8c_modeling(
            dataset_phase_dir=dataset_phase_dir,
            forecast_path=forecast_path,
            output_root=output_root,
            run_id=run_id,
            generated_at=generated_at,
        )
    except (ModelingContractError, ModelingWriteError):
        raise
    except Exception:
        raise ModelingWriteError("eg8c_modeling_write_error: execution_failed") from None
