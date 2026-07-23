"""EG-7 approved one-hour pilot orchestration and derived observation indexes.

Dry-run is intentionally separated from the Live execution path.  It validates
only an explicit plan and never discovers credentials, output roots, transports,
collectors, backup workers, or operational locks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping, Sequence, TextIO
from zoneinfo import ZoneInfo

from . import backup, eg6b
from .batch_id import BatchIdValidationError, canonical_batch_id
from .collector import load_place, parse_population_response


PLAN_SCHEMA_VERSION = "eg7-pilot-plan-v2"
EVENT_SCHEMA_VERSION = "eg7-execution-event-v1"
SLOT_INDEX_SCHEMA_VERSION = "eg7-slot-index-v1"
AREA_INDEX_SCHEMA_VERSION = "eg7-area-observation-index-v1"
SUMMARY_SCHEMA_VERSION = "eg7-pilot-summary-v2"
TIMEZONE_NAME = "Asia/Seoul"
SEOUL_TIMEZONE = ZoneInfo(TIMEZONE_NAME)
CADENCE_MINUTES = 5
CADENCE_DECISION_STATUS = "PM_APPROVED_FIXED"
CADENCE_SCOPE = "LONG_TERM_OPERATING_BASELINE"
CADENCE_CHANGE_ALLOWED = False
ALTERNATIVE_CADENCES_SUPPORTED = False
DUPLICATE_TRIGGERED_CADENCE_CHANGE = False
PILOT_DURATION_MINUTES = 60
PLANNED_SLOT_COUNT = 12
AREA_COUNT = 13
MAX_API_CALLS = 156
RETRY_COUNT = 0
PLANNED_STATUS = "PLANNED"
DEFAULT_QUOTA_CONFIRMATION_STATUS = "UNCONFIRMED"
DEFAULT_LIVE_APPROVAL_STATUS = "NOT_APPROVED"
PILOT_STAGE_PATH = Path("stages/eg7_one_hour_pilot")
PILOT_RUNS_PATH = PILOT_STAGE_PATH / "runs"
PILOT_LOCK_PATH = PILOT_STAGE_PATH / "pilot-controller.lock"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

PLAN_FIELDS = (
    "schema_version",
    "pilot_run_id",
    "timezone",
    "cadence_minutes",
    "cadence_decision_status",
    "cadence_scope",
    "cadence_change_allowed",
    "planned_start_at",
    "planned_end_at",
    "planned_slot_count",
    "max_api_calls",
    "retry_count",
    "area_count",
    "area_order_contract",
    "quota_confirmation_status",
    "live_approval_status",
    "slots",
)
SLOT_FIELDS = ("slot_index", "scheduled_at", "batch_id", "planned_status")

EXECUTION_EVENT_FIELDS = (
    "schema_version",
    "pilot_run_id",
    "plan_fingerprint",
    "slot_index",
    "scheduled_at",
    "batch_id",
    "state_before",
    "state_after",
    "event_at",
    "reason",
    "collector_execution_count",
    "actual_api_call_count",
    "backup_execution_count",
    "backup_status",
)
SLOT_INDEX_FIELDS = (
    "schema_version",
    "pilot_run_id",
    "slot_index",
    "scheduled_at",
    "batch_id",
    "slot_status",
    "collection_started_at",
    "collection_ended_at",
    "collection_duration_ms",
    "attempted_area_count",
    "successful_area_count",
    "failed_area_count",
    "actual_api_calls",
    "backup_eligible",
    "backup_status",
    "failure_reason",
)
AREA_INDEX_FIELDS = (
    "schema_version",
    "pilot_run_id",
    "slot_index",
    "scheduled_at",
    "slot_status",
    "batch_id",
    "request_id",
    "panel_order",
    "area_code",
    "area_status",
    "failure_reason",
    "requested_at",
    "received_at",
    "collection_started_at",
    "collection_ended_at",
    "collection_duration_ms",
    "api_observation_at",
    "population_min",
    "population_max",
    "congestion_level",
    "forecast_record_count",
    "forecast_first_target_at",
    "forecast_last_target_at",
    "raw_relative_path",
    "metadata_relative_path",
    "raw_sha256",
    "manifest_sha256",
    "duplicate_collection_time",
    "duplicate_observation_time",
    "duplicate_raw_hash",
    "duplicate_forecast_targets",
    "backup_eligible",
    "backup_status",
)


class PilotPlanError(ValueError):
    """Raised for a non-sensitive plan contract violation."""


class LiveGateError(RuntimeError):
    """Raised before operational execution when a Live gate is not satisfied."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class PilotLockError(RuntimeError):
    """Raised when the global pilot lock cannot be acquired safely."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class QuotaConfirmationStatus(str, Enum):
    UNCONFIRMED = "UNCONFIRMED"
    CONFIRMED = "CONFIRMED"


class LiveApprovalStatus(str, Enum):
    NOT_APPROVED = "NOT_APPROVED"
    PM_APPROVED = "PM_APPROVED"


class SlotStatus(str, Enum):
    COMPLETED_SUCCESS = "COMPLETED_SUCCESS"
    COMPLETED_PARTIAL = "COMPLETED_PARTIAL"
    SKIPPED_MISSED = "SKIPPED_MISSED"
    SKIPPED_OVERLAP = "SKIPPED_OVERLAP"
    STOPPED_FATAL = "STOPPED_FATAL"
    NOT_RUN_AFTER_FATAL_STOP = "NOT_RUN_AFTER_FATAL_STOP"


class ActiveState(str, Enum):
    PLANNED = "PLANNED"
    COLLECTION_ACTIVE = "COLLECTION_ACTIVE"
    BACKUP_ACTIVE = "BACKUP_ACTIVE"


class FailureClass(str, Enum):
    AREA_FAILURE_NONFATAL = "AREA_FAILURE_NONFATAL"
    COMMON_API_FAILURE_FATAL = "COMMON_API_FAILURE_FATAL"
    CREDENTIAL_FAILURE_FATAL = "CREDENTIAL_FAILURE_FATAL"
    SCHEMA_FAILURE_FATAL = "SCHEMA_FAILURE_FATAL"
    QUOTA_FAILURE_FATAL = "QUOTA_FAILURE_FATAL"
    BACKUP_FAILURE_FATAL = "BACKUP_FAILURE_FATAL"
    STORAGE_FAILURE_FATAL = "STORAGE_FAILURE_FATAL"
    OVERLAP_SKIP = "OVERLAP_SKIP"
    MISSED_SLOT_SKIP = "MISSED_SLOT_SKIP"

    @property
    def fatal(self) -> bool:
        return self not in {
            FailureClass.AREA_FAILURE_NONFATAL,
            FailureClass.OVERLAP_SKIP,
            FailureClass.MISSED_SLOT_SKIP,
        }


class BackupIndexStatus(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    LOCAL_SYNC_COPY_VERIFIED = "LOCAL_SYNC_COPY_VERIFIED"
    FAILED = "FAILED"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class PilotSlot:
    slot_index: int
    scheduled_at: datetime
    batch_id: str
    planned_status: str


@dataclass(frozen=True)
class PilotPlan:
    document: Mapping[str, object]
    pilot_run_id: str
    planned_start_at: datetime
    planned_end_at: datetime
    max_api_calls: int
    slots: tuple[PilotSlot, ...]

    @property
    def fingerprint(self) -> str:
        return plan_fingerprint(self.document)


@dataclass(frozen=True)
class CollectorExecution:
    exit_code: int
    started_at: datetime
    ended_at: datetime
    collection_log: Mapping[str, object] | None
    failure_class: FailureClass | None = None

    @property
    def actual_api_calls(self) -> int | None:
        if self.collection_log is None:
            return None
        value = self.collection_log.get("attempted_count")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return None

    @property
    def budget_debit(self) -> int:
        return self.actual_api_calls if self.actual_api_calls is not None else AREA_COUNT


@dataclass(frozen=True)
class BackupExecution:
    eligible: bool
    execution_count: int
    status: BackupIndexStatus
    started_at: datetime | None
    ended_at: datetime | None
    source_bytes: int | None
    backup_bytes: int | None
    failure_class: FailureClass | None = None


@dataclass
class SlotRecord:
    slot: PilotSlot
    status: SlotStatus
    collection_started_at: datetime | None = None
    collection_ended_at: datetime | None = None
    attempted_area_count: int | None = None
    successful_area_count: int | None = None
    failed_area_count: int | None = None
    actual_api_calls: int | None = None
    collector_execution_count: int = 0
    backup_eligible: bool | None = None
    backup_status: BackupIndexStatus = BackupIndexStatus.NOT_APPLICABLE
    backup_started_at: datetime | None = None
    backup_ended_at: datetime | None = None
    backup_execution_count: int = 0
    failure_reason: str | None = None
    collection_log: Mapping[str, object] | None = field(default=None, repr=False)
    source_bytes: int | None = None
    backup_bytes: int | None = None

    @property
    def collection_duration_ms(self) -> int | None:
        return duration_ms(self.collection_started_at, self.collection_ended_at)

    @property
    def backup_duration_ms(self) -> int | None:
        return duration_ms(self.backup_started_at, self.backup_ended_at)


@dataclass(frozen=True)
class PilotRunResult:
    records: tuple[SlotRecord, ...]
    total_budget_debit: int
    fatal_failure: FailureClass | None


@dataclass
class PilotLock:
    path: Path
    descriptor: int | None
    owner_pid: int
    fingerprint: str

    def release(self) -> None:
        if self.descriptor is not None:
            try:
                os.close(self.descriptor)
            finally:
                self.descriptor = None
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                isinstance(document, dict)
                and document.get("process_id") == self.owner_pid
                and document.get("plan_fingerprint") == self.fingerprint
            ):
                self.path.unlink()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise PilotPlanError("CLI_INPUT_ERROR")


class AppendOnlyEventLog:
    """Append one UTF-8 JSON object per event without rewriting prior bytes."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, document: Mapping[str, object]) -> None:
        if tuple(document) != EXECUTION_EVENT_FIELDS:
            raise RuntimeError("EVENT_CONTRACT_ERROR")
        payload = (
            json.dumps(dict(document), ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        try:
            descriptor = os.open(
                self.path,
                os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                0o600,
            )
            try:
                _write_all(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as error:
            raise RuntimeError("EVENT_APPEND_FAILED") from error


def now_seoul() -> datetime:
    return datetime.now(SEOUL_TIMEZONE)


def _integer(value: object, reason: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PilotPlanError(reason)
    return value


def _canonical_uuid4(value: object, reason: str) -> str:
    if not isinstance(value, str):
        raise PilotPlanError(reason)
    try:
        canonical = canonical_batch_id(value)
        parsed = uuid.UUID(canonical)
    except (BatchIdValidationError, ValueError) as error:
        raise PilotPlanError(reason) from error
    if parsed.version != 4:
        raise PilotPlanError(reason)
    return canonical


def _timestamp(value: object, reason: str) -> datetime:
    if not isinstance(value, str):
        raise PilotPlanError(reason)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise PilotPlanError(reason) from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(hours=9):
        raise PilotPlanError(reason)
    normalized = parsed.astimezone(SEOUL_TIMEZONE)
    if normalized.second or normalized.microsecond:
        raise PilotPlanError(reason)
    return normalized


def validate_plan(document: Mapping[str, object]) -> PilotPlan:
    """Validate the complete immutable one-hour plan without side effects."""

    if len(document) != len(PLAN_FIELDS) or set(document) != set(PLAN_FIELDS):
        raise PilotPlanError("PLAN_FIELDS_INVALID")
    if document.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise PilotPlanError("PLAN_SCHEMA_INVALID")
    pilot_run_id = _canonical_uuid4(document.get("pilot_run_id"), "PILOT_RUN_ID_INVALID")
    if document.get("timezone") != TIMEZONE_NAME:
        raise PilotPlanError("TIMEZONE_INVALID")
    if _integer(document.get("cadence_minutes"), "CADENCE_INVALID") != CADENCE_MINUTES:
        raise PilotPlanError("CADENCE_INVALID")
    if document.get("cadence_decision_status") != CADENCE_DECISION_STATUS:
        raise PilotPlanError("CADENCE_DECISION_STATUS_INVALID")
    if document.get("cadence_scope") != CADENCE_SCOPE:
        raise PilotPlanError("CADENCE_SCOPE_INVALID")
    if document.get("cadence_change_allowed") is not CADENCE_CHANGE_ALLOWED:
        raise PilotPlanError("CADENCE_CHANGE_POLICY_INVALID")
    if _integer(document.get("planned_slot_count"), "SLOT_COUNT_INVALID") != PLANNED_SLOT_COUNT:
        raise PilotPlanError("SLOT_COUNT_INVALID")
    max_api_calls = _integer(document.get("max_api_calls"), "CALL_BUDGET_INVALID")
    if not 0 < max_api_calls <= MAX_API_CALLS:
        raise PilotPlanError("CALL_BUDGET_INVALID")
    if _integer(document.get("retry_count"), "RETRY_INVALID") != RETRY_COUNT:
        raise PilotPlanError("RETRY_INVALID")
    if _integer(document.get("area_count"), "AREA_COUNT_INVALID") != AREA_COUNT:
        raise PilotPlanError("AREA_COUNT_INVALID")
    area_contract = document.get("area_order_contract")
    if not isinstance(area_contract, list) or tuple(area_contract) != tuple(eg6b.EG6B_AREA_CODES):
        raise PilotPlanError("AREA_CONTRACT_INVALID")
    try:
        QuotaConfirmationStatus(str(document.get("quota_confirmation_status")))
        LiveApprovalStatus(str(document.get("live_approval_status")))
    except ValueError as error:
        raise PilotPlanError("APPROVAL_STATUS_INVALID") from error

    planned_start = _timestamp(document.get("planned_start_at"), "PLAN_TIME_INVALID")
    planned_end = _timestamp(document.get("planned_end_at"), "PLAN_TIME_INVALID")
    if (
        planned_start.minute % CADENCE_MINUTES
        or planned_end != planned_start + timedelta(minutes=PILOT_DURATION_MINUTES)
    ):
        raise PilotPlanError("PLAN_TIME_INVALID")

    raw_slots = document.get("slots")
    if not isinstance(raw_slots, list) or len(raw_slots) != PLANNED_SLOT_COUNT:
        raise PilotPlanError("SLOT_COUNT_INVALID")
    slots: list[PilotSlot] = []
    seen_times: set[datetime] = set()
    seen_batch_ids: set[str] = set()
    for expected_index, raw_slot in enumerate(raw_slots):
        if (
            not isinstance(raw_slot, dict)
            or len(raw_slot) != len(SLOT_FIELDS)
            or set(raw_slot) != set(SLOT_FIELDS)
        ):
            raise PilotPlanError("SLOT_FIELDS_INVALID")
        slot_index = _integer(raw_slot.get("slot_index"), "SLOT_INDEX_INVALID")
        if slot_index != expected_index:
            raise PilotPlanError("SLOT_INDEX_INVALID")
        scheduled_at = _timestamp(raw_slot.get("scheduled_at"), "SLOT_TIME_INVALID")
        expected_time = planned_start + timedelta(minutes=CADENCE_MINUTES * expected_index)
        if (
            scheduled_at != expected_time
            or not planned_start <= scheduled_at < planned_end
            or scheduled_at in seen_times
        ):
            raise PilotPlanError("SLOT_TIME_INVALID")
        batch_id = _canonical_uuid4(raw_slot.get("batch_id"), "BATCH_ID_INVALID")
        if batch_id in seen_batch_ids:
            raise PilotPlanError("BATCH_ID_DUPLICATE")
        if raw_slot.get("planned_status") != PLANNED_STATUS:
            raise PilotPlanError("PLANNED_STATUS_INVALID")
        slots.append(PilotSlot(slot_index, scheduled_at, batch_id, PLANNED_STATUS))
        seen_times.add(scheduled_at)
        seen_batch_ids.add(batch_id)
    return PilotPlan(
        document=dict(document),
        pilot_run_id=pilot_run_id,
        planned_start_at=planned_start,
        planned_end_at=planned_end,
        max_api_calls=max_api_calls,
        slots=tuple(slots),
    )


def load_plan(path: Path) -> PilotPlan:
    try:
        with path.open("r", encoding="utf-8") as source:
            document = json.load(source)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PilotPlanError("PLAN_READ_FAILED") from error
    if not isinstance(document, dict):
        raise PilotPlanError("PLAN_FIELDS_INVALID")
    return validate_plan(document)


def canonical_plan_bytes(document: Mapping[str, object]) -> bytes:
    validate_plan(document)
    return json.dumps(
        dict(document),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def plan_fingerprint(document: Mapping[str, object]) -> str:
    """Return a deterministic traceability digest, not an authentication tag."""

    return hashlib.sha256(canonical_plan_bytes(document)).hexdigest()


def dry_run_preview(plan: PilotPlan) -> tuple[dict[str, object], ...]:
    """Return a synthetic, no-I/O transition preview."""

    return tuple(
        {
            "slot_index": slot.slot_index,
            "scheduled_at": slot.scheduled_at.isoformat(),
            "planned_transition": "PLANNED→COLLECTION_ACTIVE→BACKUP_ACTIVE→TERMINAL",
            "maximum_api_calls": AREA_COUNT,
            "retry_count": RETRY_COUNT,
        }
        for slot in plan.slots
    )


def validate_live_approval(
    plan: PilotPlan,
    approved_fingerprint: str,
    current_time: datetime,
) -> None:
    if (
        not SHA256_PATTERN.fullmatch(approved_fingerprint)
        or approved_fingerprint != plan.fingerprint
    ):
        raise LiveGateError("PLAN_FINGERPRINT_MISMATCH")
    if (
        plan.document.get("quota_confirmation_status")
        != QuotaConfirmationStatus.CONFIRMED.value
    ):
        raise LiveGateError("QUOTA_UNCONFIRMED")
    if plan.document.get("live_approval_status") != LiveApprovalStatus.PM_APPROVED.value:
        raise LiveGateError("LIVE_NOT_PM_APPROVED")
    if current_time.tzinfo is None:
        raise LiveGateError("CURRENT_TIME_INVALID")
    current_seoul = current_time.astimezone(SEOUL_TIMEZONE)
    if not plan.planned_start_at <= current_seoul < plan.planned_end_at:
        raise LiveGateError("OUTSIDE_APPROVED_WINDOW")


def _safe_output_root(output_root: Path) -> tuple[Path, Path]:
    try:
        resolved, stage_root, _, _, batch_root = eg6b._validated_output_paths(output_root)
    except Exception as error:
        raise LiveGateError("WORKING_ENVIRONMENT_INVALID") from error
    if not resolved.exists() or not resolved.is_dir():
        raise LiveGateError("WORKING_ENVIRONMENT_INVALID")
    return resolved, batch_root


def _ensure_no_pilot_identity_collision(output_root: Path, plan: PilotPlan) -> None:
    """Reject reuse of any Batch ID recorded in a prior immutable pilot plan."""

    runs_root = output_root / PILOT_RUNS_PATH
    if not runs_root.exists():
        return
    if not runs_root.is_dir() or runs_root.is_symlink():
        raise LiveGateError("PILOT_HISTORY_INVALID")
    approved_batch_ids = {slot.batch_id for slot in plan.slots}
    try:
        prior_runs = sorted(runs_root.iterdir(), key=lambda path: path.name)
    except OSError as error:
        raise LiveGateError("PILOT_HISTORY_INVALID") from error
    for prior_run in prior_runs:
        if not prior_run.is_dir() or prior_run.is_symlink():
            raise LiveGateError("PILOT_HISTORY_INVALID")
        prior_plan_path = prior_run / "pilot_plan.json"
        if not prior_plan_path.is_file() or prior_plan_path.is_symlink():
            raise LiveGateError("PILOT_HISTORY_INVALID")
        try:
            prior_plan = load_plan(prior_plan_path)
        except PilotPlanError as error:
            raise LiveGateError("PILOT_HISTORY_INVALID") from error
        if prior_plan.pilot_run_id == plan.pilot_run_id:
            raise LiveGateError("PILOT_RUN_ID_COLLISION")
        if approved_batch_ids.intersection(slot.batch_id for slot in prior_plan.slots):
            raise LiveGateError("APPROVED_BATCH_ID_COLLISION")


def validate_operational_environment(
    *,
    plan: PilotPlan,
    output_root: Path,
    env_file: Path,
    environ: Mapping[str, str],
) -> Path:
    """Perform read-only Live preflight without loading credential values."""

    resolved_output, batch_root = _safe_output_root(output_root)
    try:
        if not env_file.is_file():
            raise LiveGateError("WORKING_ENVIRONMENT_INVALID")
        source_value = environ.get(backup.SOURCE_ROOT_ENV)
        sync_value = environ.get(backup.SYNC_ROOT_ENV)
        if not source_value or not sync_value:
            raise LiveGateError("WORKING_ENVIRONMENT_INVALID")
        source_root = Path(source_value).expanduser().resolve(strict=True)
        sync_root = Path(sync_value).expanduser().resolve(strict=True)
        if (
            source_root != resolved_output
            or not sync_root.is_dir()
            or sync_root == sync_root.parent
        ):
            raise LiveGateError("WORKING_ENVIRONMENT_INVALID")
        snapshot = eg6b._validate_references(eg6b.DEFAULT_REFERENCE_PATHS)
        if tuple(place.area_code for place in snapshot.places) != tuple(eg6b.EG6B_AREA_CODES):
            raise LiveGateError("AREA_CONTRACT_INVALID")
        _ensure_no_pilot_identity_collision(resolved_output, plan)
        for slot in plan.slots:
            eg6b._ensure_batch_id_available(
                output_root=resolved_output,
                batch_root=batch_root,
                batch_id=slot.batch_id,
                environ=environ,
            )
    except LiveGateError:
        raise
    except Exception as error:
        raise LiveGateError("WORKING_ENVIRONMENT_INVALID") from error
    lock_path = resolved_output / PILOT_LOCK_PATH
    if os.path.lexists(lock_path):
        raise LiveGateError("PILOT_LOCK_HELD")
    return resolved_output


def acquire_pilot_lock(
    output_root: Path,
    *,
    plan: PilotPlan,
    fingerprint: str,
    event_at: datetime,
) -> PilotLock:
    lock_path = output_root / PILOT_LOCK_PATH
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = (
            json.dumps(
                {
                    "pilot_run_id": plan.pilot_run_id,
                    "plan_fingerprint": fingerprint,
                    "created_at": event_at.isoformat(),
                    "process_id": os.getpid(),
                    "controller_version": PLAN_SCHEMA_VERSION,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        descriptor = os.open(
            lock_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            _write_all(descriptor, payload)
            os.fsync(descriptor)
        except OSError:
            os.close(descriptor)
            raise
    except FileExistsError as error:
        raise PilotLockError("PILOT_LOCK_HELD") from error
    except OSError as error:
        raise PilotLockError("PILOT_LOCK_CREATE_FAILED") from error
    return PilotLock(lock_path, descriptor, os.getpid(), fingerprint)


def duration_ms(started_at: datetime | None, ended_at: datetime | None) -> int | None:
    if started_at is None or ended_at is None:
        return None
    return max(0, round((ended_at - started_at).total_seconds() * 1000))


def _event(
    *,
    plan: PilotPlan,
    fingerprint: str,
    slot: PilotSlot,
    state_before: str,
    state_after: str,
    event_at: datetime,
    reason: str | None,
    collector_count: int,
    actual_calls: int | None,
    backup_count: int,
    backup_status: BackupIndexStatus,
) -> dict[str, object]:
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "pilot_run_id": plan.pilot_run_id,
        "plan_fingerprint": fingerprint,
        "slot_index": slot.slot_index,
        "scheduled_at": slot.scheduled_at.isoformat(),
        "batch_id": slot.batch_id,
        "state_before": state_before,
        "state_after": state_after,
        "event_at": event_at.isoformat(),
        "reason": reason,
        "collector_execution_count": collector_count,
        "actual_api_call_count": actual_calls,
        "backup_execution_count": backup_count,
        "backup_status": backup_status.value,
    }


def _counts(log: Mapping[str, object] | None) -> tuple[int | None, int | None, int | None]:
    if log is None:
        return None, None, None
    values: list[int | None] = []
    for name in ("attempted_count", "success_count", "failure_count"):
        value = log.get(name)
        values.append(
            value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        )
    return values[0], values[1], values[2]


def _collector_failure(execution: CollectorExecution) -> FailureClass | None:
    if execution.failure_class is not None:
        return execution.failure_class
    if execution.exit_code == 0:
        return None
    if execution.exit_code == 1:
        return FailureClass.AREA_FAILURE_NONFATAL
    if execution.exit_code != 2:
        return FailureClass.COMMON_API_FAILURE_FATAL
    if execution.collection_log is not None:
        results = execution.collection_log.get("area_results")
        if isinstance(results, list):
            statuses = {
                str(item.get("collection_status"))
                for item in results
                if isinstance(item, dict)
            }
            if "storage_error" in statuses:
                return FailureClass.STORAGE_FAILURE_FATAL
            if "config_error" in statuses:
                return FailureClass.CREDENTIAL_FAILURE_FATAL
    return FailureClass.COMMON_API_FAILURE_FATAL


def run_scheduled_pilot(
    plan: PilotPlan,
    *,
    fingerprint: str,
    clock: Callable[[], datetime],
    sleeper: Callable[[float], None],
    collector_runner: Callable[[PilotSlot], CollectorExecution],
    backup_runner: Callable[[PilotSlot], BackupExecution],
    event_sink: Callable[[Mapping[str, object]], None],
) -> PilotRunResult:
    """Execute exactly one approved plan through injected orchestration boundaries."""

    records: list[SlotRecord] = []
    fatal_failure: FailureClass | None = None
    previous_active_until: datetime | None = None
    budget_debit = 0

    for slot in plan.slots:
        if fatal_failure is not None:
            record = SlotRecord(
                slot=slot,
                status=SlotStatus.NOT_RUN_AFTER_FATAL_STOP,
                failure_reason=fatal_failure.value,
            )
            records.append(record)
            event_sink(
                _event(
                    plan=plan,
                    fingerprint=fingerprint,
                    slot=slot,
                    state_before=ActiveState.PLANNED.value,
                    state_after=record.status.value,
                    event_at=clock(),
                    reason=fatal_failure.value,
                    collector_count=0,
                    actual_calls=0,
                    backup_count=0,
                    backup_status=record.backup_status,
                )
            )
            continue

        if previous_active_until is not None and previous_active_until > slot.scheduled_at:
            record = SlotRecord(
                slot=slot,
                status=SlotStatus.SKIPPED_OVERLAP,
                actual_api_calls=0,
                backup_eligible=False,
                failure_reason=FailureClass.OVERLAP_SKIP.value,
            )
            records.append(record)
            event_sink(
                _event(
                    plan=plan,
                    fingerprint=fingerprint,
                    slot=slot,
                    state_before=ActiveState.PLANNED.value,
                    state_after=record.status.value,
                    event_at=clock(),
                    reason=record.failure_reason,
                    collector_count=0,
                    actual_calls=0,
                    backup_count=0,
                    backup_status=record.backup_status,
                )
            )
            continue

        current = clock().astimezone(SEOUL_TIMEZONE)
        waited = current < slot.scheduled_at
        if waited:
            sleeper(max(0.0, (slot.scheduled_at - current).total_seconds()))
            current = clock().astimezone(SEOUL_TIMEZONE)
        slot_end = slot.scheduled_at + timedelta(minutes=CADENCE_MINUTES)
        missed = (not waited and current > slot.scheduled_at) or current >= slot_end
        if missed:
            record = SlotRecord(
                slot=slot,
                status=SlotStatus.SKIPPED_MISSED,
                actual_api_calls=0,
                backup_eligible=False,
                failure_reason=FailureClass.MISSED_SLOT_SKIP.value,
            )
            records.append(record)
            event_sink(
                _event(
                    plan=plan,
                    fingerprint=fingerprint,
                    slot=slot,
                    state_before=ActiveState.PLANNED.value,
                    state_after=record.status.value,
                    event_at=current,
                    reason=record.failure_reason,
                    collector_count=0,
                    actual_calls=0,
                    backup_count=0,
                    backup_status=record.backup_status,
                )
            )
            continue

        if budget_debit + AREA_COUNT > plan.max_api_calls:
            fatal_failure = FailureClass.QUOTA_FAILURE_FATAL
            record = SlotRecord(
                slot=slot,
                status=SlotStatus.STOPPED_FATAL,
                actual_api_calls=0,
                backup_eligible=False,
                failure_reason=fatal_failure.value,
            )
            records.append(record)
            event_sink(
                _event(
                    plan=plan,
                    fingerprint=fingerprint,
                    slot=slot,
                    state_before=ActiveState.PLANNED.value,
                    state_after=record.status.value,
                    event_at=current,
                    reason=record.failure_reason,
                    collector_count=0,
                    actual_calls=0,
                    backup_count=0,
                    backup_status=record.backup_status,
                )
            )
            continue

        event_sink(
            _event(
                plan=plan,
                fingerprint=fingerprint,
                slot=slot,
                state_before=ActiveState.PLANNED.value,
                state_after=ActiveState.COLLECTION_ACTIVE.value,
                event_at=current,
                reason=None,
                collector_count=1,
                actual_calls=None,
                backup_count=0,
                backup_status=BackupIndexStatus.NOT_APPLICABLE,
            )
        )
        try:
            collection = collector_runner(slot)
        except Exception:
            collection = CollectorExecution(
                exit_code=2,
                started_at=current,
                ended_at=clock(),
                collection_log=None,
                failure_class=FailureClass.COMMON_API_FAILURE_FATAL,
            )
        budget_debit += collection.budget_debit
        attempted, successes, failures = _counts(collection.collection_log)
        record = SlotRecord(
            slot=slot,
            status=SlotStatus.STOPPED_FATAL,
            collection_started_at=collection.started_at,
            collection_ended_at=collection.ended_at,
            attempted_area_count=attempted,
            successful_area_count=successes,
            failed_area_count=failures,
            actual_api_calls=collection.actual_api_calls,
            collector_execution_count=1,
            collection_log=collection.collection_log,
        )
        collector_failure = _collector_failure(collection)

        if (
            collector_failure is None
            or collector_failure == FailureClass.AREA_FAILURE_NONFATAL
        ) and (
            attempted is None
            or successes is None
            or failures is None
            or successes + failures != attempted
        ):
            collector_failure = FailureClass.SCHEMA_FAILURE_FATAL
        if attempted is not None and attempted > AREA_COUNT:
            collector_failure = FailureClass.QUOTA_FAILURE_FATAL
        if budget_debit > plan.max_api_calls:
            collector_failure = FailureClass.QUOTA_FAILURE_FATAL
        if collector_failure is not None and collector_failure.fatal:
            record.failure_reason = collector_failure.value
            fatal_failure = collector_failure
            previous_active_until = collection.ended_at
            records.append(record)
            event_sink(
                _event(
                    plan=plan,
                    fingerprint=fingerprint,
                    slot=slot,
                    state_before=ActiveState.COLLECTION_ACTIVE.value,
                    state_after=record.status.value,
                    event_at=collection.ended_at,
                    reason=record.failure_reason,
                    collector_count=1,
                    actual_calls=record.actual_api_calls,
                    backup_count=0,
                    backup_status=record.backup_status,
                )
            )
            continue

        event_sink(
            _event(
                plan=plan,
                fingerprint=fingerprint,
                slot=slot,
                state_before=ActiveState.COLLECTION_ACTIVE.value,
                state_after=ActiveState.BACKUP_ACTIVE.value,
                event_at=collection.ended_at,
                reason=collector_failure.value if collector_failure else None,
                collector_count=1,
                actual_calls=record.actual_api_calls,
                backup_count=0,
                backup_status=BackupIndexStatus.NOT_APPLICABLE,
            )
        )
        try:
            backup_execution = backup_runner(slot)
        except Exception:
            backup_execution = BackupExecution(
                eligible=False,
                execution_count=0,
                status=BackupIndexStatus.FAILED,
                started_at=None,
                ended_at=clock(),
                source_bytes=None,
                backup_bytes=None,
                failure_class=FailureClass.BACKUP_FAILURE_FATAL,
            )
        record.backup_eligible = backup_execution.eligible
        record.backup_status = backup_execution.status
        record.backup_started_at = backup_execution.started_at
        record.backup_ended_at = backup_execution.ended_at
        record.backup_execution_count = backup_execution.execution_count
        record.source_bytes = backup_execution.source_bytes
        record.backup_bytes = backup_execution.backup_bytes
        backup_ok = (
            backup_execution.eligible
            and backup_execution.execution_count == 1
            and backup_execution.status == BackupIndexStatus.LOCAL_SYNC_COPY_VERIFIED
        )
        if not backup_ok:
            fatal_failure = backup_execution.failure_class or FailureClass.BACKUP_FAILURE_FATAL
            if not fatal_failure.fatal:
                fatal_failure = FailureClass.BACKUP_FAILURE_FATAL
            record.status = SlotStatus.STOPPED_FATAL
            record.failure_reason = fatal_failure.value
        else:
            record.status = (
                SlotStatus.COMPLETED_PARTIAL
                if collector_failure == FailureClass.AREA_FAILURE_NONFATAL
                else SlotStatus.COMPLETED_SUCCESS
            )
            record.failure_reason = (
                FailureClass.AREA_FAILURE_NONFATAL.value
                if collector_failure == FailureClass.AREA_FAILURE_NONFATAL
                else None
            )
        previous_active_until = backup_execution.ended_at or collection.ended_at
        records.append(record)
        event_sink(
            _event(
                plan=plan,
                fingerprint=fingerprint,
                slot=slot,
                state_before=ActiveState.BACKUP_ACTIVE.value,
                state_after=record.status.value,
                event_at=previous_active_until,
                reason=record.failure_reason,
                collector_count=1,
                actual_calls=record.actual_api_calls,
                backup_count=record.backup_execution_count,
                backup_status=record.backup_status,
            )
        )

    if len(records) != PLANNED_SLOT_COUNT:
        raise RuntimeError("SLOT_TERMINAL_CONTRACT_ERROR")
    return PilotRunResult(tuple(records), budget_debit, fatal_failure)


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as source:
            document = json.load(source)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("CANONICAL_EVIDENCE_INVALID") from error
    if not isinstance(document, dict):
        raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
    return document


def _canonical_evidence_path(stage_root: Path, relative_path: str) -> Path:
    pure = PurePosixPath(relative_path)
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
    candidate = stage_root.joinpath(*pure.parts)
    try:
        resolved_stage = stage_root.resolve(strict=True)
        current = stage_root
        for part in pure.parts:
            current = current / part
            if current.is_symlink():
                raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_stage)
    except (OSError, RuntimeError, ValueError) as error:
        raise RuntimeError("CANONICAL_EVIDENCE_INVALID") from error
    if not resolved.is_file():
        raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_optional_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _manifest_artifacts(document: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw = document.get("artifacts")
    if not isinstance(raw, list):
        raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
    result: dict[str, Mapping[str, object]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str):
            raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
        result[str(item["relative_path"])] = item
    return result


def build_slot_index(
    plan: PilotPlan,
    records: Sequence[SlotRecord],
) -> list[dict[str, object]]:
    if len(records) != PLANNED_SLOT_COUNT:
        raise RuntimeError("SLOT_INDEX_ROW_COUNT_INVALID")
    rows = []
    for expected_index, record in enumerate(records):
        if record.slot.slot_index != expected_index:
            raise RuntimeError("SLOT_INDEX_ORDER_INVALID")
        rows.append(
            {
                "schema_version": SLOT_INDEX_SCHEMA_VERSION,
                "pilot_run_id": plan.pilot_run_id,
                "slot_index": record.slot.slot_index,
                "scheduled_at": record.slot.scheduled_at.isoformat(),
                "batch_id": record.slot.batch_id,
                "slot_status": record.status.value,
                "collection_started_at": (
                    record.collection_started_at.isoformat()
                    if record.collection_started_at
                    else None
                ),
                "collection_ended_at": (
                    record.collection_ended_at.isoformat()
                    if record.collection_ended_at
                    else None
                ),
                "collection_duration_ms": record.collection_duration_ms,
                "attempted_area_count": record.attempted_area_count,
                "successful_area_count": record.successful_area_count,
                "failed_area_count": record.failed_area_count,
                "actual_api_calls": record.actual_api_calls,
                "backup_eligible": record.backup_eligible,
                "backup_status": record.backup_status.value,
                "failure_reason": record.failure_reason,
            }
        )
    return rows


def build_area_observation_index(
    plan: PilotPlan,
    records: Sequence[SlotRecord],
    *,
    stage_root: Path,
    official_csv: Path = eg6b.OFFICIAL_CSV_PATH,
) -> list[dict[str, object]]:
    """Derive attempted Area rows from immutable Batch evidence."""

    rows: list[dict[str, object]] = []
    seen_collection: set[tuple[str, str]] = set()
    seen_observation: set[tuple[str, str]] = set()
    seen_raw: set[tuple[str, str]] = set()
    seen_forecasts: set[tuple[str, tuple[str, ...]]] = set()

    for record in records:
        log = record.collection_log
        if log is None:
            continue
        batch_id = record.slot.batch_id
        manifest_relative = f"data/processed/batches/{batch_id}/manifest.json"
        try:
            manifest_path = _canonical_evidence_path(stage_root, manifest_relative)
        except RuntimeError:
            if record.status == SlotStatus.STOPPED_FATAL:
                continue
            raise
        manifest = _read_json_object(manifest_path)
        if manifest.get("batch_id") != batch_id:
            raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
        manifest_sha256 = _sha256_file(manifest_path)
        artifacts = _manifest_artifacts(manifest)
        area_results = log.get("area_results")
        if not isinstance(area_results, list):
            raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
        for item in area_results:
            if not isinstance(item, dict) or item.get("attempted") is not True:
                continue
            panel_order = item.get("panel_order")
            area_code = item.get("area_code")
            request_id = item.get("request_id")
            if (
                not isinstance(panel_order, int)
                or isinstance(panel_order, bool)
                or not 1 <= panel_order <= AREA_COUNT
                or area_code != eg6b.EG6B_AREA_CODES[panel_order - 1]
                or not isinstance(request_id, str)
            ):
                raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
            metadata_relative = item.get("metadata_file")
            raw_relative = item.get("raw_file")
            metadata: dict[str, object] | None = None
            if isinstance(metadata_relative, str):
                metadata_path = _canonical_evidence_path(stage_root, metadata_relative)
                metadata_artifact = artifacts.get(metadata_relative)
                if (
                    metadata_artifact is None
                    or not isinstance(metadata_artifact.get("sha256"), str)
                    or _sha256_file(metadata_path) != metadata_artifact["sha256"]
                ):
                    raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
                metadata = _read_json_object(metadata_path)
            requested_at = metadata.get("requested_at") if metadata else None
            received_at = metadata.get("received_at") if metadata else None
            requested_time = _parse_optional_time(requested_at)
            received_time = _parse_optional_time(received_at)

            raw_sha256: str | None = None
            population: Mapping[str, object] | None = None
            forecast_targets: tuple[str, ...] = ()
            if isinstance(raw_relative, str):
                artifact = artifacts.get(raw_relative)
                if artifact is None or not isinstance(artifact.get("sha256"), str):
                    raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
                raw_sha256 = str(artifact["sha256"])
                raw_path = _canonical_evidence_path(stage_root, raw_relative)
                if _sha256_file(raw_path) != raw_sha256:
                    raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
                if item.get("collection_status") == "success":
                    place = load_place(official_csv, str(area_code))
                    population = parse_population_response(raw_path.read_bytes(), place)
                    forecasts = population.get("forecasts")
                    if not isinstance(forecasts, list):
                        raise RuntimeError("CANONICAL_EVIDENCE_INVALID")
                    forecast_targets = tuple(
                        str(forecast["forecast_target_time"])
                        for forecast in forecasts
                        if isinstance(forecast, dict)
                        and isinstance(forecast.get("forecast_target_time"), str)
                    )

            observation_at = (
                str(population.get("population_reference_time"))
                if population is not None
                and isinstance(population.get("population_reference_time"), str)
                else None
            )
            collection_key = (
                (str(area_code), str(requested_at))
                if isinstance(requested_at, str)
                else None
            )
            observation_key = (
                (str(area_code), observation_at) if observation_at is not None else None
            )
            raw_key = (
                (str(area_code), raw_sha256) if raw_sha256 is not None else None
            )
            forecast_key = (
                (str(area_code), forecast_targets) if forecast_targets else None
            )
            row = {
                "schema_version": AREA_INDEX_SCHEMA_VERSION,
                "pilot_run_id": plan.pilot_run_id,
                "slot_index": record.slot.slot_index,
                "scheduled_at": record.slot.scheduled_at.isoformat(),
                "slot_status": record.status.value,
                "batch_id": batch_id,
                "request_id": request_id,
                "panel_order": panel_order,
                "area_code": area_code,
                "area_status": item.get("collection_status"),
                "failure_reason": (
                    None
                    if item.get("collection_status") == "success"
                    else item.get("collection_status")
                ),
                "requested_at": requested_at,
                "received_at": received_at,
                "collection_started_at": requested_at,
                "collection_ended_at": received_at,
                "collection_duration_ms": duration_ms(requested_time, received_time),
                "api_observation_at": observation_at,
                "population_min": (
                    population.get("population_min") if population is not None else None
                ),
                "population_max": (
                    population.get("population_max") if population is not None else None
                ),
                "congestion_level": (
                    population.get("congestion_level") if population is not None else None
                ),
                "forecast_record_count": (
                    len(forecast_targets) if population is not None else None
                ),
                "forecast_first_target_at": (
                    forecast_targets[0] if forecast_targets else None
                ),
                "forecast_last_target_at": (
                    forecast_targets[-1] if forecast_targets else None
                ),
                "raw_relative_path": raw_relative,
                "metadata_relative_path": metadata_relative,
                "raw_sha256": raw_sha256,
                "manifest_sha256": manifest_sha256,
                "duplicate_collection_time": (
                    collection_key in seen_collection if collection_key else False
                ),
                "duplicate_observation_time": (
                    observation_key in seen_observation if observation_key else False
                ),
                "duplicate_raw_hash": raw_key in seen_raw if raw_key else False,
                "duplicate_forecast_targets": (
                    forecast_key in seen_forecasts if forecast_key else False
                ),
                "backup_eligible": record.backup_eligible,
                "backup_status": record.backup_status.value,
            }
            rows.append(row)
            if collection_key:
                seen_collection.add(collection_key)
            if observation_key:
                seen_observation.add(observation_key)
            if raw_key:
                seen_raw.add(raw_key)
            if forecast_key:
                seen_forecasts.add(forecast_key)
    if len(rows) > PLANNED_SLOT_COUNT * AREA_COUNT:
        raise RuntimeError("AREA_INDEX_ROW_COUNT_INVALID")
    rows.sort(key=lambda item: (int(item["slot_index"]), int(item["panel_order"])))
    return rows


def _mean(values: Iterable[int | float]) -> float | None:
    items = list(values)
    return round(sum(items) / len(items), 3) if items else None


def build_pilot_summary(
    plan: PilotPlan,
    slot_rows: Sequence[Mapping[str, object]],
    area_rows: Sequence[Mapping[str, object]],
    records: Sequence[SlotRecord],
) -> dict[str, object]:
    observation_values = [
        str(row["api_observation_at"])
        for row in area_rows
        if row.get("api_observation_at") is not None
    ]
    raw_hashes = [
        str(row["raw_sha256"]) for row in area_rows if row.get("raw_sha256") is not None
    ]
    duplicate_observations = sum(
        row.get("duplicate_observation_time") is True for row in area_rows
    )
    duplicate_raw = sum(row.get("duplicate_raw_hash") is True for row in area_rows)
    forecast_shapes = {
        (
            row.get("forecast_record_count"),
            row.get("forecast_first_target_at") is not None,
            row.get("forecast_last_target_at") is not None,
        )
        for row in area_rows
        if row.get("area_status") == "success"
    }
    collection_durations = [
        int(row["collection_duration_ms"])
        for row in slot_rows
        if isinstance(row.get("collection_duration_ms"), int)
    ]
    backup_durations = [
        value
        for value in (record.backup_duration_ms for record in records)
        if value is not None
    ]
    known_api_calls = [
        int(row["actual_api_calls"])
        for row in slot_rows
        if isinstance(row.get("actual_api_calls"), int)
    ]
    api_calls_known = all(
        row.get("actual_api_calls") is not None
        for row in slot_rows
        if row.get("slot_status")
        not in {
            SlotStatus.SKIPPED_MISSED.value,
            SlotStatus.SKIPPED_OVERLAP.value,
            SlotStatus.NOT_RUN_AFTER_FATAL_STOP.value,
        }
    )
    source_growth_known = all(
        record.source_bytes is not None
        for record in records
        if record.collector_execution_count > 0
    )
    backup_growth_known = all(
        record.backup_bytes is not None
        for record in records
        if record.backup_execution_count > 0
    )
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "pilot_run_id": plan.pilot_run_id,
        "plan_fingerprint": plan.fingerprint,
        "cadence_minutes": CADENCE_MINUTES,
        "cadence_decision_status": CADENCE_DECISION_STATUS,
        "cadence_scope": CADENCE_SCOPE,
        "cadence_change_allowed": CADENCE_CHANGE_ALLOWED,
        "alternative_cadences_supported": ALTERNATIVE_CADENCES_SUPPORTED,
        "duplicate_triggered_cadence_change": DUPLICATE_TRIGGERED_CADENCE_CHANGE,
        "planned_slot_count": PLANNED_SLOT_COUNT,
        "executed_batch_count": sum(record.collector_execution_count for record in records),
        "skipped_missed_count": sum(
            record.status == SlotStatus.SKIPPED_MISSED for record in records
        ),
        "skipped_overlap_count": sum(
            record.status == SlotStatus.SKIPPED_OVERLAP for record in records
        ),
        "fatal_stop_count": sum(
            record.status == SlotStatus.STOPPED_FATAL for record in records
        ),
        "attempted_area_count": sum(
            record.attempted_area_count
            for record in records
            if record.attempted_area_count is not None
        ),
        "successful_area_count": sum(
            record.successful_area_count
            for record in records
            if record.successful_area_count is not None
        ),
        "failed_area_count": sum(
            record.failed_area_count
            for record in records
            if record.failed_area_count is not None
        ),
        "total_actual_seoul_api_calls": (
            sum(known_api_calls) if api_calls_known else None
        ),
        "retry_count": RETRY_COUNT,
        "distinct_api_observation_timestamp_count": len(set(observation_values)),
        "duplicate_observation_timestamp_count": duplicate_observations,
        "duplicate_observation_timestamp_rate": (
            round(duplicate_observations / len(observation_values), 6)
            if observation_values
            else None
        ),
        "distinct_raw_hash_count": len(set(raw_hashes)),
        "duplicate_raw_hash_count": duplicate_raw,
        "duplicate_raw_hash_rate": (
            round(duplicate_raw / len(raw_hashes), 6) if raw_hashes else None
        ),
        "forecast_structure_consistency": (
            "NOT_AVAILABLE"
            if not forecast_shapes
            else "CONSISTENT"
            if len(forecast_shapes) == 1
            else "INCONSISTENT"
        ),
        "average_collector_duration_ms": _mean(collection_durations),
        "maximum_collector_duration_ms": (
            max(collection_durations) if collection_durations else None
        ),
        "average_backup_duration_ms": _mean(backup_durations),
        "maximum_backup_duration_ms": (
            max(backup_durations) if backup_durations else None
        ),
        "source_storage_growth_bytes": (
            sum(record.source_bytes or 0 for record in records)
            if source_growth_known
            else None
        ),
        "backup_storage_growth_bytes": (
            sum(record.backup_bytes or 0 for record in records)
            if backup_growth_known
            else None
        ),
        "eligible_backup_count": sum(record.backup_eligible is True for record in records),
        "verified_backup_count": sum(
            record.backup_status == BackupIndexStatus.LOCAL_SYNC_COPY_VERIFIED
            for record in records
        ),
        "no_recollection_confirmation": all(
            record.collector_execution_count <= 1 for record in records
        ),
        "ml_model_performance_assessed": False,
    }


def _write_all(descriptor: int, payload: bytes) -> None:
    written = 0
    while written < len(payload):
        count = os.write(descriptor, payload[written:])
        if count <= 0:
            raise OSError("파일 쓰기가 완료되지 않았습니다.")
        written += count


def _exclusive_write(path: Path, payload: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            _write_all(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise RuntimeError("DERIVED_OUTPUT_WRITE_FAILED") from error


def _json_bytes(document: object, *, compact: bool = False) -> bytes:
    if compact:
        rendered = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    else:
        rendered = json.dumps(document, ensure_ascii=False, indent=2)
    return (rendered + "\n").encode("utf-8")


def _jsonl_bytes(rows: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(_json_bytes(dict(row), compact=True) for row in rows)


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _csv_bytes(
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> bytes:
    from io import StringIO

    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field)) for field in fields})
    return output.getvalue().encode("utf-8")


def write_derived_outputs(
    run_root: Path,
    *,
    slot_rows: Sequence[Mapping[str, object]],
    area_rows: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
) -> None:
    _exclusive_write(run_root / "slot_index.jsonl", _jsonl_bytes(slot_rows))
    _exclusive_write(run_root / "slot_index.csv", _csv_bytes(slot_rows, SLOT_INDEX_FIELDS))
    _exclusive_write(run_root / "area_observation_index.jsonl", _jsonl_bytes(area_rows))
    _exclusive_write(
        run_root / "area_observation_index.csv",
        _csv_bytes(area_rows, AREA_INDEX_FIELDS),
    )
    _exclusive_write(run_root / "pilot_summary.json", _json_bytes(dict(summary)))


def _load_collection_log(output_root: Path, batch_id: str) -> Mapping[str, object] | None:
    path = output_root / eg6b.BATCH_OUTPUT_PATH / batch_id / "collection_log.json"
    if not path.is_file():
        return None
    return _read_json_object(path)


def default_collector_runner(
    *,
    env_file: Path,
    output_root: Path,
    timeout_seconds: float,
    environ: Mapping[str, str],
    clock: Callable[[], datetime],
) -> Callable[[PilotSlot], CollectorExecution]:
    def execute(slot: PilotSlot) -> CollectorExecution:
        started_at = clock()
        exit_code = eg6b.run(
            [
                "--env-file",
                str(env_file),
                "--output-root",
                str(output_root),
                "--batch-id",
                slot.batch_id,
                "--timeout",
                str(timeout_seconds),
                "--execute-live",
            ],
            environ=environ,
        )
        ended_at = clock()
        log = _load_collection_log(output_root, slot.batch_id)
        return CollectorExecution(exit_code, started_at, ended_at, log)

    return execute


def default_backup_runner(
    *,
    output_root: Path,
    environ: Mapping[str, str],
    clock: Callable[[], datetime],
) -> Callable[[PilotSlot], BackupExecution]:
    def execute(slot: PilotSlot) -> BackupExecution:
        stage_root = output_root / eg6b.STAGE_PATH
        eligibility = backup.assess_batch(stage_root, slot.batch_id)
        if not eligibility.eligible:
            return BackupExecution(
                eligible=False,
                execution_count=0,
                status=BackupIndexStatus.NOT_ELIGIBLE,
                started_at=None,
                ended_at=clock(),
                source_bytes=None,
                backup_bytes=None,
                failure_class=FailureClass.BACKUP_FAILURE_FATAL,
            )
        sync_value = environ.get(backup.SYNC_ROOT_ENV)
        if not sync_value:
            return BackupExecution(
                eligible=True,
                execution_count=0,
                status=BackupIndexStatus.FAILED,
                started_at=None,
                ended_at=clock(),
                source_bytes=None,
                backup_bytes=None,
                failure_class=FailureClass.BACKUP_FAILURE_FATAL,
            )
        sync_root = Path(sync_value).expanduser()
        ledger_root = output_root / backup.LEDGER_RELATIVE_PATH
        started_at = clock()
        result = backup.backup_batch(stage_root, sync_root, ledger_root, slot.batch_id)
        ended_at = clock()
        source_bytes: int | None = None
        try:
            plan = backup._inspect_batch(stage_root, slot.batch_id)
            source_bytes = plan.source_file_bytes
        except Exception:
            source_bytes = None
        status_map = {
            backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED: BackupIndexStatus.LOCAL_SYNC_COPY_VERIFIED,
            backup.BackupStatus.CONFLICT: BackupIndexStatus.CONFLICT,
            backup.BackupStatus.FAILED: BackupIndexStatus.FAILED,
        }
        status = status_map.get(result.backup_status, BackupIndexStatus.FAILED)
        verified = status == BackupIndexStatus.LOCAL_SYNC_COPY_VERIFIED
        return BackupExecution(
            eligible=True,
            execution_count=1,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            source_bytes=source_bytes,
            backup_bytes=source_bytes if verified else 0,
            failure_class=None if verified else FailureClass.BACKUP_FAILURE_FATAL,
        )

    return execute


def execute_live_pilot(
    plan: PilotPlan,
    *,
    approved_fingerprint: str,
    env_file: Path,
    output_root: Path,
    timeout_seconds: float,
    environ: Mapping[str, str],
    clock: Callable[[], datetime] = now_seoul,
    sleeper: Callable[[float], None] = time.sleep,
    collector_runner: Callable[[PilotSlot], CollectorExecution] | None = None,
    backup_runner: Callable[[PilotSlot], BackupExecution] | None = None,
) -> PilotRunResult:
    current = clock()
    validate_live_approval(plan, approved_fingerprint, current)
    resolved_output = validate_operational_environment(
        plan=plan,
        output_root=output_root,
        env_file=env_file,
        environ=environ,
    )
    pilot_lock = acquire_pilot_lock(
        resolved_output,
        plan=plan,
        fingerprint=approved_fingerprint,
        event_at=current,
    )
    try:
        run_root = resolved_output / PILOT_RUNS_PATH / plan.pilot_run_id
        try:
            run_root.mkdir(parents=True, exist_ok=False, mode=0o700)
        except OSError as error:
            raise LiveGateError("PILOT_RUN_CONFLICT") from error
        _exclusive_write(run_root / "pilot_plan.json", _json_bytes(dict(plan.document)))
        events = AppendOnlyEventLog(run_root / "execution_events.jsonl")
        active_collector = collector_runner or default_collector_runner(
            env_file=env_file,
            output_root=resolved_output,
            timeout_seconds=timeout_seconds,
            environ=environ,
            clock=clock,
        )
        active_backup = backup_runner or default_backup_runner(
            output_root=resolved_output,
            environ=environ,
            clock=clock,
        )
        result = run_scheduled_pilot(
            plan,
            fingerprint=approved_fingerprint,
            clock=clock,
            sleeper=sleeper,
            collector_runner=active_collector,
            backup_runner=active_backup,
            event_sink=events.append,
        )
        slot_rows = build_slot_index(plan, result.records)
        area_rows = build_area_observation_index(
            plan,
            result.records,
            stage_root=resolved_output / eg6b.STAGE_PATH,
        )
        summary = build_pilot_summary(plan, slot_rows, area_rows, result.records)
        write_derived_outputs(
            run_root,
            slot_rows=slot_rows,
            area_rows=area_rows,
            summary=summary,
        )
    except Exception:
        pilot_lock.release()
        raise
    else:
        pilot_lock.release()
        return result


def _timeout_value(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("invalid timeout") from error
    if not math.isfinite(parsed) or not 0 < parsed <= eg6b.MAX_TIMEOUT_SECONDS:
        raise argparse.ArgumentTypeError("invalid timeout")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(description="EG-7 승인형 5분·1시간 반복수집 파일럿")
    parser.add_argument("--plan", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--execute-live", action="store_true")
    parser.add_argument("--approved-plan-fingerprint")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--timeout", type=_timeout_value, default=eg6b.DEFAULT_TIMEOUT_SECONDS)
    return parser


def _report_dry_run(plan: PilotPlan) -> None:
    print("EG7_DRY_RUN")
    print("plan_valid=true")
    print(f"plan_fingerprint={plan.fingerprint}")
    print(f"cadence_minutes={CADENCE_MINUTES}")
    print(f"cadence_decision_status={CADENCE_DECISION_STATUS}")
    print(f"cadence_scope={CADENCE_SCOPE}")
    print(f"cadence_change_allowed={str(CADENCE_CHANGE_ALLOWED).lower()}")
    print(
        "alternative_cadences_supported="
        f"{str(ALTERNATIVE_CADENCES_SUPPORTED).lower()}"
    )
    print(
        "duplicate_triggered_cadence_change="
        f"{str(DUPLICATE_TRIGGERED_CADENCE_CHANGE).lower()}"
    )
    print(f"planned_slot_count={len(plan.slots)}")
    print(f"maximum_api_calls={plan.max_api_calls}")
    print(f"quota_confirmation_status={plan.document['quota_confirmation_status']}")
    print(f"live_approval_status={plan.document['live_approval_status']}")
    print("transport_calls=0")
    print("credential_access=0")
    print("collector_executions=0")
    print("backup_executions=0")
    print("operational_directories_created=0")
    print("operational_batch_ids_generated=0")
    print("operational_batch_ids_reserved=0")
    print("google_drive_access=0")


def run(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] = now_seoul,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        plan = load_plan(arguments.plan)
        if arguments.dry_run:
            dry_run_preview(plan)
            _report_dry_run(plan)
            return 0
        if (
            not arguments.approved_plan_fingerprint
            or arguments.env_file is None
            or arguments.output_root is None
        ):
            raise LiveGateError("LIVE_INPUT_REQUIRED")
        execute_live_pilot(
            plan,
            approved_fingerprint=arguments.approved_plan_fingerprint,
            env_file=arguments.env_file,
            output_root=arguments.output_root,
            timeout_seconds=arguments.timeout,
            environ=os.environ if environ is None else environ,
            clock=clock,
            sleeper=sleeper,
        )
        print("EG7_PILOT_RESULT")
        print("status=TERMINAL")
        print("seoul_api_calls_within_plan=true")
        return 0
    except PilotPlanError as error:
        print(f"eg7_status={error}")
        return 2
    except LiveGateError as error:
        print(f"eg7_status={error.reason_code}")
        return 2
    except PilotLockError as error:
        print(f"eg7_status={error.reason_code}")
        return 2
    except Exception:
        print("eg7_status=INTERNAL_ERROR")
        return 2


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
