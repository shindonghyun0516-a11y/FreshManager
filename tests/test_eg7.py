from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping
from unittest import mock

from freshmanager import eg6b, eg7
from freshmanager.collector import CURRENT_POPULATION_FIELDS


ROOT = Path(__file__).resolve().parents[1]
PILOT_RUN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
START = datetime(2026, 8, 1, 10, 0, tzinfo=eg7.SEOUL_TIMEZONE)


def batch_id(slot_index: int) -> str:
    return f"00000000-0000-4000-8000-{slot_index + 1:012d}"


def plan_document(
    *,
    start: datetime = START,
    max_api_calls: int = eg7.MAX_API_CALLS,
    quota_status: str = eg7.DEFAULT_QUOTA_CONFIRMATION_STATUS,
    live_status: str = eg7.DEFAULT_LIVE_APPROVAL_STATUS,
) -> dict[str, object]:
    end = start + timedelta(minutes=eg7.PILOT_DURATION_MINUTES)
    return {
        "schema_version": eg7.PLAN_SCHEMA_VERSION,
        "pilot_run_id": PILOT_RUN_ID,
        "timezone": eg7.TIMEZONE_NAME,
        "cadence_minutes": eg7.CADENCE_MINUTES,
        "cadence_decision_status": eg7.CADENCE_DECISION_STATUS,
        "long_term_baseline_status": eg7.LONG_TERM_BASELINE_STATUS,
        "cadence_scope": eg7.CADENCE_SCOPE,
        "cadence_change_allowed": eg7.CADENCE_CHANGE_ALLOWED,
        "planned_start_at": start.isoformat(),
        "planned_end_at": end.isoformat(),
        "planned_slot_count": eg7.PLANNED_SLOT_COUNT,
        "max_api_calls": max_api_calls,
        "retry_count": eg7.RETRY_COUNT,
        "area_count": eg7.AREA_COUNT,
        "area_order_contract": list(eg6b.EG6B_AREA_CODES),
        "quota_confirmation_status": quota_status,
        "live_approval_status": live_status,
        "slots": [
            {
                "slot_index": index,
                "scheduled_at": (
                    start + timedelta(minutes=eg7.CADENCE_MINUTES * index)
                ).isoformat(),
                "batch_id": batch_id(index),
                "planned_status": eg7.PLANNED_STATUS,
            }
            for index in range(eg7.PLANNED_SLOT_COUNT)
        ],
    }


class FakeClock:
    def __init__(self, current: datetime = START) -> None:
        self.current = current
        self.sleeps: list[float] = []

    def __call__(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


def collection_log(
    *,
    attempted: int = eg7.AREA_COUNT,
    successes: int = eg7.AREA_COUNT,
    failures: int = 0,
) -> dict[str, object]:
    return {
        "attempted_count": attempted,
        "success_count": successes,
        "failure_count": failures,
        "area_results": [],
    }


def success_runners(
    clock: FakeClock,
    *,
    partial: bool = False,
    first_duration_seconds: float = 1.0,
) -> tuple[
    list[int],
    list[int],
    object,
    object,
]:
    collector_calls: list[int] = []
    backup_calls: list[int] = []

    def collector(slot: eg7.PilotSlot) -> eg7.CollectorExecution:
        collector_calls.append(slot.slot_index)
        started = clock()
        clock.advance(first_duration_seconds if slot.slot_index == 0 else 1)
        failures = 1 if partial else 0
        return eg7.CollectorExecution(
            exit_code=1 if partial else 0,
            started_at=started,
            ended_at=clock(),
            collection_log=collection_log(
                successes=eg7.AREA_COUNT - failures,
                failures=failures,
            ),
        )

    def backup_runner(slot: eg7.PilotSlot) -> eg7.BackupExecution:
        backup_calls.append(slot.slot_index)
        started = clock()
        clock.advance(1)
        return eg7.BackupExecution(
            eligible=True,
            execution_count=1,
            status=eg7.BackupIndexStatus.LOCAL_SYNC_COPY_VERIFIED,
            started_at=started,
            ended_at=clock(),
            source_bytes=100,
            backup_bytes=100,
        )

    return collector_calls, backup_calls, collector, backup_runner


def execute_with_fakes(
    plan: eg7.PilotPlan,
    clock: FakeClock,
    collector: object,
    backup_runner: object,
) -> tuple[eg7.PilotRunResult, list[dict[str, object]]]:
    events: list[dict[str, object]] = []
    result = eg7.run_scheduled_pilot(
        plan,
        fingerprint=plan.fingerprint,
        clock=clock,
        sleeper=clock.sleep,
        collector_runner=collector,  # type: ignore[arg-type]
        backup_runner=backup_runner,  # type: ignore[arg-type]
        event_sink=lambda event: events.append(dict(event)),
    )
    return result, events


def official_names() -> dict[str, str]:
    with (ROOT / "data/reference/seoul_121_places.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as source:
        return {row["AREA_CD"]: row["AREA_NM"] for row in csv.DictReader(source)}


AREA_NAMES = official_names()


def synthetic_population(
    area_code: str,
    *,
    forecast_targets: list[str] | None = None,
) -> bytes:
    targets = forecast_targets or ["2026-08-01 11:00"]
    current = {field: "1" for field in CURRENT_POPULATION_FIELDS}
    current.update(
        {
            "AREA_NM": AREA_NAMES[area_code],
            "AREA_CD": area_code,
            "AREA_CONGEST_LVL": "보통",
            "AREA_CONGEST_MSG": "합성 테스트 응답",
            "AREA_PPLTN_MIN": "1000",
            "AREA_PPLTN_MAX": "1200",
            "PPLTN_TIME": "2026-08-01 10:00",
            "FCST_YN": "Y",
            "FCST_PPLTN": [
                {
                    "FCST_TIME": target,
                    "FCST_CONGEST_LVL": "보통",
                    "FCST_PPLTN_MIN": "1100",
                    "FCST_PPLTN_MAX": "1300",
                }
                for target in targets
            ],
        }
    )
    return json.dumps(
        {
            "SeoulRtd.citydata_ppltn": [current],
            "RESULT": {
                "RESULT.CODE": "INFO-000",
                "RESULT.MESSAGE": "합성 정상 응답",
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")


def write_batch_evidence(
    stage_root: Path,
    record: eg7.SlotRecord,
    *,
    failure_panel: int | None = None,
    common_request_time: bool = False,
    forecast_targets: list[str] | None = None,
) -> None:
    artifacts: list[dict[str, object]] = []
    area_results: list[dict[str, object]] = []
    for panel_order, area_code in enumerate(eg6b.EG6B_AREA_CODES, start=1):
        request_id = f"request-{record.slot.slot_index:02d}-{panel_order:02d}"
        requested_at = (
            START if common_request_time else record.slot.scheduled_at
        ) + timedelta(seconds=panel_order)
        received_at = requested_at + timedelta(milliseconds=500)
        metadata_relative = (
            f"data/metadata/population/{record.slot.batch_id}/{area_code}.json"
        )
        metadata_path = stage_root / metadata_relative
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_payload = json.dumps(
            {
                "request_id": request_id,
                "requested_at": requested_at.isoformat(),
                "received_at": received_at.isoformat(),
            }
        ).encode("utf-8")
        metadata_path.write_bytes(metadata_payload)
        artifacts.append(
            {
                "relative_path": metadata_relative,
                "sha256": hashlib.sha256(metadata_payload).hexdigest(),
            }
        )
        if failure_panel == panel_order:
            raw_relative = None
            status = "timeout"
        else:
            raw_relative = f"data/raw/population/{record.slot.batch_id}/{area_code}.json"
            raw_path = stage_root / raw_relative
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            payload = synthetic_population(
                area_code,
                forecast_targets=forecast_targets,
            )
            raw_path.write_bytes(payload)
            artifacts.append(
                {
                    "relative_path": raw_relative,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
            status = "success"
        area_results.append(
            {
                "panel_order": panel_order,
                "area_code": area_code,
                "request_id": request_id,
                "attempted": True,
                "collection_status": status,
                "raw_file": raw_relative,
                "metadata_file": metadata_relative,
            }
        )
    manifest_path = (
        stage_root
        / "data/processed/batches"
        / record.slot.batch_id
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "batch_id": record.slot.batch_id,
                "artifacts": artifacts,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    record.collection_log = {
        "attempted_count": eg7.AREA_COUNT,
        "success_count": eg7.AREA_COUNT - int(failure_panel is not None),
        "failure_count": int(failure_panel is not None),
        "area_results": area_results,
    }


def completed_records(plan: eg7.PilotPlan) -> list[eg7.SlotRecord]:
    return [
        eg7.SlotRecord(
            slot=slot,
            status=eg7.SlotStatus.COMPLETED_SUCCESS,
            collection_started_at=slot.scheduled_at,
            collection_ended_at=slot.scheduled_at + timedelta(seconds=13),
            attempted_area_count=eg7.AREA_COUNT,
            successful_area_count=eg7.AREA_COUNT,
            failed_area_count=0,
            actual_api_calls=eg7.AREA_COUNT,
            collector_execution_count=1,
            backup_eligible=True,
            backup_status=eg7.BackupIndexStatus.LOCAL_SYNC_COPY_VERIFIED,
            backup_started_at=slot.scheduled_at + timedelta(seconds=13),
            backup_ended_at=slot.scheduled_at + timedelta(seconds=14),
            backup_execution_count=1,
            source_bytes=100,
            backup_bytes=100,
        )
        for slot in plan.slots
    ]


class Eg7PlanTests(unittest.TestCase):
    def test_valid_plan_has_exact_12_slots_without_drift(self) -> None:
        plan = eg7.validate_plan(plan_document())
        self.assertEqual(len(plan.slots), 12)
        self.assertEqual(
            [slot.scheduled_at for slot in plan.slots],
            [START + timedelta(minutes=5 * index) for index in range(12)],
        )
        self.assertEqual(
            plan.planned_end_at,
            plan.planned_start_at + timedelta(minutes=60),
        )
        self.assertEqual(len(eg7.dry_run_preview(plan)), 12)

    def test_json_field_order_does_not_change_plan_contract_or_fingerprint(self) -> None:
        document = plan_document()
        reordered = dict(reversed(list(document.items())))
        reordered["slots"] = [
            dict(reversed(list(slot.items())))
            for slot in reordered["slots"]  # type: ignore[union-attr]
        ]
        self.assertEqual(
            eg7.validate_plan(document).fingerprint,
            eg7.validate_plan(reordered).fingerprint,
        )

    def test_semantically_equivalent_timestamp_format_has_same_fingerprint(self) -> None:
        canonical = plan_document()
        space_separated = deepcopy(canonical)
        space_separated["planned_start_at"] = str(
            space_separated["planned_start_at"]
        ).replace("T", " ")
        space_separated["planned_end_at"] = str(
            space_separated["planned_end_at"]
        ).replace("T", " ")
        for slot in space_separated["slots"]:  # type: ignore[union-attr]
            slot["scheduled_at"] = str(slot["scheduled_at"]).replace("T", " ")

        self.assertEqual(
            eg7.plan_fingerprint(canonical),
            eg7.plan_fingerprint(space_separated),
        )
        canonical_document = json.loads(
            eg7.canonical_plan_bytes(space_separated).decode("utf-8")
        )
        self.assertEqual(
            canonical_document["planned_start_at"],
            "2026-08-01T10:00:00+09:00",
        )
        self.assertTrue(
            all(
                "T" in slot["scheduled_at"]
                and slot["scheduled_at"].endswith("+09:00")
                for slot in canonical_document["slots"]
            )
        )

    def test_contract_changes_change_fingerprint(self) -> None:
        original = plan_document()
        shifted = plan_document(start=START + timedelta(minutes=5))
        changed_batch = deepcopy(original)
        changed_batch["slots"][0]["batch_id"] = (  # type: ignore[index]
            "99999999-9999-4999-8999-999999999999"
        )
        changed_live_approval = deepcopy(original)
        changed_live_approval["live_approval_status"] = (
            eg7.LiveApprovalStatus.PM_APPROVED.value
        )

        original_fingerprint = eg7.plan_fingerprint(original)
        for changed in (shifted, changed_batch, changed_live_approval):
            with self.subTest(changed=changed):
                self.assertNotEqual(
                    original_fingerprint,
                    eg7.plan_fingerprint(changed),
                )

    def test_invalid_timestamp_and_self_fingerprint_field_are_rejected(self) -> None:
        invalid_timestamp = plan_document()
        invalid_timestamp["planned_start_at"] = "2026-08-01T10:00:00"
        with self.assertRaisesRegex(eg7.PilotPlanError, "PLAN_TIME_INVALID"):
            eg7.plan_fingerprint(invalid_timestamp)

        self_referential = plan_document()
        self_referential["plan_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(eg7.PilotPlanError, "PLAN_FIELDS_INVALID"):
            eg7.plan_fingerprint(self_referential)
        self.assertNotIn(
            b"plan_fingerprint",
            eg7.canonical_plan_bytes(plan_document()),
        )

    def test_runtime_cadence_override_is_not_supported(self) -> None:
        for option, value in (
            ("--cadence", "10"),
            ("--cadence", "15"),
            ("--interval", "10"),
        ):
            with self.subTest(option=option, value=value):
                with self.assertRaises(eg7.PilotPlanError) as raised:
                    eg7.build_parser().parse_args(
                        [
                            "--plan",
                            "synthetic-plan.json",
                            "--dry-run",
                            option,
                            value,
                        ]
                    )
                self.assertEqual(str(raised.exception), "CLI_INPUT_ERROR")

    def test_plan_v1_and_prohibited_cadence_value_matrix_are_rejected(self) -> None:
        prohibited: tuple[object, ...] = (1, 10, 15, None, "5", 5.0, True, False)
        for value in prohibited:
            document = plan_document()
            document["cadence_minutes"] = value
            with self.subTest(value=value):
                with self.assertRaises(eg7.PilotPlanError):
                    eg7.validate_plan(document)

        omitted = plan_document()
        del omitted["cadence_minutes"]
        with self.assertRaisesRegex(eg7.PilotPlanError, "PLAN_FIELDS_INVALID"):
            eg7.validate_plan(omitted)

        version_one = plan_document()
        version_one["schema_version"] = "eg7-pilot-plan-v1"
        with self.assertRaisesRegex(eg7.PilotPlanError, "PLAN_SCHEMA_INVALID"):
            eg7.validate_plan(version_one)
        self.assertEqual(version_one["schema_version"], "eg7-pilot-plan-v1")

    def test_permanent_decision_fields_are_required_and_fixed(self) -> None:
        mutations: list[dict[str, object]] = []
        for field in (
            "cadence_decision_status",
            "long_term_baseline_status",
            "cadence_scope",
        ):
            missing = plan_document()
            del missing[field]
            mutations.append(missing)

        wrong_approval = plan_document()
        wrong_approval["cadence_decision_status"] = "PILOT_ONLY"
        mutations.append(wrong_approval)
        wrong_baseline = plan_document()
        wrong_baseline["long_term_baseline_status"] = "PROVISIONAL"
        mutations.append(wrong_baseline)
        wrong_scope = plan_document()
        wrong_scope["cadence_scope"] = "ONE_HOUR_PILOT_ONLY"
        mutations.append(wrong_scope)
        change_allowed = plan_document()
        change_allowed["cadence_change_allowed"] = True
        mutations.append(change_allowed)

        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(eg7.PilotPlanError):
                    eg7.validate_plan(mutation)

    def test_invalid_plan_variants_are_rejected(self) -> None:
        mutations = []

        wrong_timezone = plan_document()
        wrong_timezone["timezone"] = "UTC"
        mutations.append(wrong_timezone)

        wrong_cadence = plan_document()
        wrong_cadence["cadence_minutes"] = 10
        mutations.append(wrong_cadence)

        wrong_decision = plan_document()
        wrong_decision["cadence_decision_status"] = "PILOT_ONLY"
        mutations.append(wrong_decision)

        wrong_baseline = plan_document()
        wrong_baseline["long_term_baseline_status"] = "PROVISIONAL"
        mutations.append(wrong_baseline)

        wrong_scope = plan_document()
        wrong_scope["cadence_scope"] = "ONE_HOUR_PILOT_ONLY"
        mutations.append(wrong_scope)

        cadence_change_allowed = plan_document()
        cadence_change_allowed["cadence_change_allowed"] = True
        mutations.append(cadence_change_allowed)

        wrong_count = plan_document()
        wrong_count["planned_slot_count"] = 11
        mutations.append(wrong_count)

        too_many_calls = plan_document()
        too_many_calls["max_api_calls"] = 157
        mutations.append(too_many_calls)

        retry = plan_document()
        retry["retry_count"] = 1
        mutations.append(retry)

        duplicate_batch = plan_document()
        duplicate_batch["slots"][1]["batch_id"] = batch_id(0)  # type: ignore[index]
        mutations.append(duplicate_batch)

        duplicate_time = plan_document()
        duplicate_time["slots"][1]["scheduled_at"] = duplicate_time["slots"][0][  # type: ignore[index]
            "scheduled_at"
        ]
        mutations.append(duplicate_time)

        drift = plan_document()
        drift["slots"][5]["scheduled_at"] = (START + timedelta(minutes=26)).isoformat()  # type: ignore[index]
        mutations.append(drift)

        non_uuid4 = plan_document()
        non_uuid4["slots"][0]["batch_id"] = "00000000-0000-1000-8000-000000000001"  # type: ignore[index]
        mutations.append(non_uuid4)

        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(eg7.PilotPlanError):
                    eg7.validate_plan(mutation)

    def test_live_gate_rejects_unconfirmed_quota_and_missing_pm_approval(self) -> None:
        unconfirmed = eg7.validate_plan(plan_document())
        with self.assertRaisesRegex(eg7.LiveGateError, "QUOTA_UNCONFIRMED"):
            eg7.validate_live_approval(unconfirmed, unconfirmed.fingerprint, START)

        no_pm = eg7.validate_plan(
            plan_document(quota_status=eg7.QuotaConfirmationStatus.CONFIRMED.value)
        )
        with self.assertRaisesRegex(eg7.LiveGateError, "LIVE_NOT_PM_APPROVED"):
            eg7.validate_live_approval(no_pm, no_pm.fingerprint, START)

    def test_live_gate_rejects_fingerprint_mutation_and_wrong_window(self) -> None:
        plan = eg7.validate_plan(
            plan_document(
                quota_status=eg7.QuotaConfirmationStatus.CONFIRMED.value,
                live_status=eg7.LiveApprovalStatus.PM_APPROVED.value,
            )
        )
        with self.assertRaisesRegex(eg7.LiveGateError, "PLAN_FINGERPRINT_MISMATCH"):
            eg7.validate_live_approval(plan, "0" * 64, START)
        with self.assertRaisesRegex(eg7.LiveGateError, "OUTSIDE_APPROVED_WINDOW"):
            eg7.validate_live_approval(
                plan,
                plan.fingerprint,
                START + timedelta(minutes=60),
            )


class Eg7SchedulingTests(unittest.TestCase):
    def test_success_runs_one_collector_and_one_backup_per_slot(self) -> None:
        plan = eg7.validate_plan(plan_document())
        clock = FakeClock()
        collectors, backups, collector, backup_runner = success_runners(clock)
        result, events = execute_with_fakes(plan, clock, collector, backup_runner)

        self.assertEqual(collectors, list(range(12)))
        self.assertEqual(backups, list(range(12)))
        self.assertTrue(
            all(
                record.status == eg7.SlotStatus.COMPLETED_SUCCESS
                for record in result.records
            )
        )
        self.assertEqual(result.total_budget_debit, 156)
        terminal_events = [
            event
            for event in events
            if event["state_after"] == eg7.SlotStatus.COMPLETED_SUCCESS.value
        ]
        self.assertEqual(len(terminal_events), 12)
        self.assertTrue(
            all(event["actual_api_call_count"] == 13 for event in terminal_events)
        )
        self.assertTrue(
            all(record.collector_execution_count == 1 for record in result.records)
        )

    def test_duplicate_results_do_not_suppress_following_planned_calls(self) -> None:
        plan = eg7.validate_plan(plan_document())
        clock = FakeClock()
        collector_calls: list[int] = []
        preserved_logs: list[Mapping[str, object]] = []

        def collector(slot: eg7.PilotSlot) -> eg7.CollectorExecution:
            collector_calls.append(slot.slot_index)
            started_at = clock()
            clock.advance(1)
            duplicate_evidence = {
                "attempted_count": eg7.AREA_COUNT,
                "success_count": eg7.AREA_COUNT,
                "failure_count": 0,
                "area_results": [
                    {
                        "synthetic_observation_time": "2026-08-01 10:00",
                        "synthetic_raw_hash": "a" * 64,
                        "synthetic_forecast_signature": [
                            "2026-08-01T11:00:00+09:00"
                        ],
                    }
                ],
            }
            preserved_logs.append(duplicate_evidence)
            return eg7.CollectorExecution(
                exit_code=0,
                started_at=started_at,
                ended_at=clock(),
                collection_log=duplicate_evidence,
            )

        backup_calls: list[int] = []

        def backup_runner(slot: eg7.PilotSlot) -> eg7.BackupExecution:
            backup_calls.append(slot.slot_index)
            started_at = clock()
            clock.advance(1)
            return eg7.BackupExecution(
                eligible=True,
                execution_count=1,
                status=eg7.BackupIndexStatus.LOCAL_SYNC_COPY_VERIFIED,
                started_at=started_at,
                ended_at=clock(),
                source_bytes=1,
                backup_bytes=1,
            )

        result, _ = execute_with_fakes(plan, clock, collector, backup_runner)

        self.assertEqual(collector_calls, list(range(12)))
        self.assertEqual(backup_calls, list(range(12)))
        self.assertEqual(
            [record.collection_log for record in result.records],
            preserved_logs,
        )
        self.assertEqual(eg7.CADENCE_MINUTES, 5)
        self.assertFalse(eg7.DUPLICATE_TRIGGERED_CADENCE_CHANGE)

    def test_missed_slot_is_not_caught_up(self) -> None:
        plan = eg7.validate_plan(plan_document())
        clock = FakeClock(START + timedelta(seconds=1))
        collectors, backups, collector, backup_runner = success_runners(clock)
        result, _ = execute_with_fakes(plan, clock, collector, backup_runner)

        self.assertEqual(result.records[0].status, eg7.SlotStatus.SKIPPED_MISSED)
        self.assertEqual(result.records[0].actual_api_calls, 0)
        self.assertEqual(collectors, list(range(1, 12)))
        self.assertEqual(backups, list(range(1, 12)))

    def test_overlapping_slot_is_skipped_without_catch_up(self) -> None:
        plan = eg7.validate_plan(plan_document())
        clock = FakeClock()
        collectors, backups, collector, backup_runner = success_runners(
            clock,
            first_duration_seconds=360,
        )
        result, _ = execute_with_fakes(plan, clock, collector, backup_runner)

        self.assertEqual(result.records[1].status, eg7.SlotStatus.SKIPPED_OVERLAP)
        self.assertEqual(result.records[1].actual_api_calls, 0)
        self.assertEqual(collectors, [0, *range(2, 12)])
        self.assertEqual(backups, [0, *range(2, 12)])

    def test_area_level_partial_failure_continues_all_slots(self) -> None:
        plan = eg7.validate_plan(plan_document())
        clock = FakeClock()
        collectors, backups, collector, backup_runner = success_runners(
            clock,
            partial=True,
        )
        result, _ = execute_with_fakes(plan, clock, collector, backup_runner)

        self.assertEqual(collectors, list(range(12)))
        self.assertEqual(backups, list(range(12)))
        self.assertTrue(
            all(
                record.status == eg7.SlotStatus.COMPLETED_PARTIAL
                for record in result.records
            )
        )
        self.assertIsNone(result.fatal_failure)

    def test_common_api_failure_stops_remaining_slots(self) -> None:
        plan = eg7.validate_plan(plan_document())
        clock = FakeClock()
        collector_calls: list[int] = []
        backup_calls: list[int] = []

        def collector(slot: eg7.PilotSlot) -> eg7.CollectorExecution:
            collector_calls.append(slot.slot_index)
            return eg7.CollectorExecution(
                exit_code=2,
                started_at=clock(),
                ended_at=clock(),
                collection_log=collection_log(attempted=0, successes=0),
                failure_class=eg7.FailureClass.COMMON_API_FAILURE_FATAL,
            )

        def backup_runner(slot: eg7.PilotSlot) -> eg7.BackupExecution:
            backup_calls.append(slot.slot_index)
            raise AssertionError("fatal Collector 뒤에는 Backup을 실행하면 안 됨")

        result, _ = execute_with_fakes(plan, clock, collector, backup_runner)
        self.assertEqual(collector_calls, [0])
        self.assertEqual(backup_calls, [])
        self.assertEqual(result.records[0].status, eg7.SlotStatus.STOPPED_FATAL)
        self.assertTrue(
            all(
                record.status == eg7.SlotStatus.NOT_RUN_AFTER_FATAL_STOP
                for record in result.records[1:]
            )
        )

    def test_backup_failure_stops_without_recollection(self) -> None:
        plan = eg7.validate_plan(plan_document())
        clock = FakeClock()
        collectors, backups, collector, _ = success_runners(clock)

        def failed_backup(slot: eg7.PilotSlot) -> eg7.BackupExecution:
            backups.append(slot.slot_index)
            return eg7.BackupExecution(
                eligible=True,
                execution_count=1,
                status=eg7.BackupIndexStatus.FAILED,
                started_at=clock(),
                ended_at=clock(),
                source_bytes=0,
                backup_bytes=0,
                failure_class=eg7.FailureClass.BACKUP_FAILURE_FATAL,
            )

        result, _ = execute_with_fakes(plan, clock, collector, failed_backup)
        self.assertEqual(collectors, [0])
        self.assertEqual(backups, [0])
        self.assertEqual(
            result.records[0].failure_reason,
            eg7.FailureClass.BACKUP_FAILURE_FATAL.value,
        )
        self.assertTrue(
            all(record.collector_execution_count == 0 for record in result.records[1:])
        )

    def test_storage_failure_and_budget_exhaustion_are_fatal(self) -> None:
        for failure_class in (
            eg7.FailureClass.STORAGE_FAILURE_FATAL,
            eg7.FailureClass.CREDENTIAL_FAILURE_FATAL,
            eg7.FailureClass.SCHEMA_FAILURE_FATAL,
            eg7.FailureClass.QUOTA_FAILURE_FATAL,
        ):
            plan = eg7.validate_plan(plan_document())
            clock = FakeClock()

            def collector(
                slot: eg7.PilotSlot,
                active_failure: eg7.FailureClass = failure_class,
            ) -> eg7.CollectorExecution:
                del slot
                return eg7.CollectorExecution(
                    exit_code=2,
                    started_at=clock(),
                    ended_at=clock(),
                    collection_log=None,
                    failure_class=active_failure,
                )

            result, _ = execute_with_fakes(
                plan,
                clock,
                collector,
                lambda slot: (_ for _ in ()).throw(AssertionError(slot)),
            )
            self.assertEqual(result.fatal_failure, failure_class)
            self.assertEqual(result.records[0].status, eg7.SlotStatus.STOPPED_FATAL)

        budget_plan = eg7.validate_plan(plan_document(max_api_calls=143))
        clock = FakeClock()
        collectors, backups, collector, backup_runner = success_runners(clock)
        result, _ = execute_with_fakes(
            budget_plan,
            clock,
            collector,
            backup_runner,
        )
        self.assertEqual(collectors, list(range(11)))
        self.assertEqual(backups, list(range(11)))
        self.assertEqual(
            result.records[11].failure_reason,
            eg7.FailureClass.QUOTA_FAILURE_FATAL.value,
        )

    def test_collector_report_above_13_calls_is_fatal_and_not_backed_up(self) -> None:
        plan = eg7.validate_plan(plan_document())
        clock = FakeClock()
        backup_calls: list[int] = []

        def collector(slot: eg7.PilotSlot) -> eg7.CollectorExecution:
            del slot
            return eg7.CollectorExecution(
                exit_code=0,
                started_at=clock(),
                ended_at=clock(),
                collection_log=collection_log(
                    attempted=14,
                    successes=14,
                    failures=0,
                ),
            )

        def backup_runner(slot: eg7.PilotSlot) -> eg7.BackupExecution:
            backup_calls.append(slot.slot_index)
            raise AssertionError("호출 상한 위반 Batch는 Backup 성공으로 승격하면 안 됨")

        result, _ = execute_with_fakes(plan, clock, collector, backup_runner)
        self.assertEqual(backup_calls, [])
        self.assertEqual(
            result.records[0].failure_reason,
            eg7.FailureClass.QUOTA_FAILURE_FATAL.value,
        )
        self.assertTrue(
            all(record.collector_execution_count == 0 for record in result.records[1:])
        )


class Eg7LockAndDryRunTests(unittest.TestCase):
    def test_global_lock_has_one_winner_and_never_deletes_stale_lock(self) -> None:
        plan = eg7.validate_plan(plan_document())
        with tempfile.TemporaryDirectory() as temp:
            output_root = Path(temp)
            first = eg7.acquire_pilot_lock(
                output_root,
                plan=plan,
                fingerprint=plan.fingerprint,
                event_at=START,
            )
            with self.assertRaisesRegex(eg7.PilotLockError, "PILOT_LOCK_HELD"):
                eg7.acquire_pilot_lock(
                    output_root,
                    plan=plan,
                    fingerprint=plan.fingerprint,
                    event_at=START,
                )
            first.release()
            self.assertFalse((output_root / eg7.PILOT_LOCK_PATH).exists())

            stale = output_root / eg7.PILOT_LOCK_PATH
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_text("stale-owner-evidence", encoding="utf-8")
            with self.assertRaisesRegex(eg7.PilotLockError, "PILOT_LOCK_HELD"):
                eg7.acquire_pilot_lock(
                    output_root,
                    plan=plan,
                    fingerprint=plan.fingerprint,
                    event_at=START,
                )
            self.assertEqual(stale.read_text(encoding="utf-8"), "stale-owner-evidence")

    def test_skipped_batch_ids_cannot_be_reused_by_another_pilot_plan(self) -> None:
        prior = eg7.validate_plan(plan_document())
        current_document = plan_document()
        current_document["pilot_run_id"] = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        current = eg7.validate_plan(current_document)
        with tempfile.TemporaryDirectory() as temp:
            output_root = Path(temp)
            prior_root = output_root / eg7.PILOT_RUNS_PATH / prior.pilot_run_id
            prior_root.mkdir(parents=True)
            prior_plan_path = prior_root / "pilot_plan.json"
            prior_plan_path.write_text(
                json.dumps(prior.document, ensure_ascii=False),
                encoding="utf-8",
            )
            before = prior_plan_path.read_bytes()
            with self.assertRaisesRegex(
                eg7.LiveGateError,
                "APPROVED_BATCH_ID_COLLISION",
            ):
                eg7._ensure_no_pilot_identity_collision(output_root, current)
            self.assertEqual(prior_plan_path.read_bytes(), before)

    def test_lock_loser_executes_no_collector_or_backup(self) -> None:
        plan = eg7.validate_plan(
            plan_document(
                quota_status=eg7.QuotaConfirmationStatus.CONFIRMED.value,
                live_status=eg7.LiveApprovalStatus.PM_APPROVED.value,
            )
        )
        with tempfile.TemporaryDirectory() as temp:
            output_root = Path(temp)
            lock_path = output_root / eg7.PILOT_LOCK_PATH
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text("active-owner", encoding="utf-8")
            collector = mock.Mock()
            backup_runner = mock.Mock()
            with (
                mock.patch.object(
                    eg7,
                    "validate_operational_environment",
                    return_value=output_root,
                ),
                self.assertRaisesRegex(eg7.PilotLockError, "PILOT_LOCK_HELD"),
            ):
                eg7.execute_live_pilot(
                    plan,
                    approved_fingerprint=plan.fingerprint,
                    env_file=output_root / "unused.env",
                    output_root=output_root,
                    timeout_seconds=10,
                    environ={},
                    clock=lambda: START,
                    sleeper=lambda seconds: None,
                    collector_runner=collector,
                    backup_runner=backup_runner,
                )
            collector.assert_not_called()
            backup_runner.assert_not_called()
            self.assertEqual(lock_path.read_text(encoding="utf-8"), "active-owner")

    def test_dry_run_has_no_operational_side_effects(self) -> None:
        class ForbiddenEnvironment(dict[str, str]):
            def get(self, key: str, default: object = None) -> object:
                raise AssertionError(f"환경변수 접근 금지: {key}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan_path = root / "synthetic-plan.json"
            plan_path.write_text(
                json.dumps(plan_document(), ensure_ascii=False),
                encoding="utf-8",
            )
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            output = io.StringIO()
            with (
                mock.patch.object(eg7.eg6b, "run") as collector,
                mock.patch.object(eg7.backup, "backup_batch") as backup_worker,
                redirect_stdout(output),
            ):
                code = eg7.run(
                    ["--plan", str(plan_path), "--dry-run"],
                    environ=ForbiddenEnvironment(),
                )
            after = sorted(path.relative_to(root) for path in root.rglob("*"))

        self.assertEqual(code, 0)
        self.assertEqual(before, after)
        collector.assert_not_called()
        backup_worker.assert_not_called()
        report = output.getvalue()
        self.assertIn("cadence_minutes=5", report)
        self.assertIn("cadence_decision_status=PM_APPROVED_FIXED", report)
        self.assertIn("cadence_scope=LONG_TERM_OPERATING_BASELINE", report)
        self.assertIn("cadence_change_allowed=false", report)
        self.assertIn("alternative_cadences_supported=false", report)
        self.assertIn("duplicate_triggered_cadence_change=false", report)
        self.assertIn("transport_calls=0", report)
        self.assertIn("credential_access=0", report)
        self.assertIn("operational_batch_ids_generated=0", report)
        self.assertNotIn("dummy-key", report)


class Eg7IndexTests(unittest.TestCase):
    def test_slot_index_is_exactly_12_rows_and_preserves_nulls(self) -> None:
        plan = eg7.validate_plan(plan_document())
        records = completed_records(plan)
        records[1] = eg7.SlotRecord(
            slot=plan.slots[1],
            status=eg7.SlotStatus.SKIPPED_OVERLAP,
            actual_api_calls=0,
            backup_eligible=False,
            failure_reason=eg7.FailureClass.OVERLAP_SKIP.value,
        )
        rows = eg7.build_slot_index(plan, records)
        self.assertEqual(len(rows), 12)
        self.assertEqual([row["slot_index"] for row in rows], list(range(12)))
        self.assertIsNone(rows[1]["collection_started_at"])
        self.assertEqual(rows[1]["actual_api_calls"], 0)

    def test_area_index_has_at_most_156_ordered_rows_and_duplicate_flags(self) -> None:
        plan = eg7.validate_plan(plan_document())
        records = completed_records(plan)
        with tempfile.TemporaryDirectory() as temp:
            stage_root = Path(temp) / "stages/eg6b"
            for record in records:
                write_batch_evidence(
                    stage_root,
                    record,
                    common_request_time=True,
                )
            rows = eg7.build_area_observation_index(
                plan,
                records,
                stage_root=stage_root,
                official_csv=ROOT / "data/reference/seoul_121_places.csv",
            )

        self.assertEqual(len(rows), 156)
        self.assertEqual(
            [row["area_code"] for row in rows[:13]],
            list(eg6b.EG6B_AREA_CODES),
        )
        self.assertFalse(rows[0]["duplicate_collection_time"])
        self.assertTrue(rows[13]["duplicate_collection_time"])
        self.assertTrue(rows[13]["duplicate_observation_time"])
        self.assertTrue(rows[13]["duplicate_raw_hash"])
        self.assertTrue(rows[13]["duplicate_forecast_targets"])
        self.assertEqual(
            [slot.scheduled_at for slot in plan.slots],
            [START + timedelta(minutes=5 * index) for index in range(12)],
        )
        summary = eg7.build_pilot_summary(
            plan,
            eg7.build_slot_index(plan, records),
            rows,
            records,
        )
        self.assertFalse(summary["duplicate_triggered_cadence_change"])
        self.assertFalse(summary["cadence_change_allowed"])
        self.assertEqual(summary["cadence_minutes"], 5)
        self.assertTrue(all(not str(row["raw_relative_path"]).startswith("/") for row in rows))
        self.assertTrue(all("FreshManager-Data" not in str(row) for row in rows))

    def test_forecast_duplicate_signature_is_normalized_sorted_set_and_area_scoped(
        self,
    ) -> None:
        plan = eg7.validate_plan(plan_document())
        records = completed_records(plan)
        first = [
            "2026-08-01 11:00",
            "2026-08-01 12:00",
            "2026-08-01 13:00",
        ]
        permuted_and_formatted = [
            "2026-08-01T13:00:00+09:00",
            "2026-08-01T11:00:00+09:00",
            "2026-08-01T12:00:00+09:00",
        ]
        repeated = [
            "2026-08-01 11:00",
            "2026-08-01 12:00",
            "2026-08-01 12:00",
            "2026-08-01 13:00",
        ]
        different = [
            "2026-08-01 11:00",
            "2026-08-01 12:00",
            "2026-08-01 13:05",
        ]

        expected_signature = (
            "2026-08-01T11:00:00+09:00",
            "2026-08-01T12:00:00+09:00",
            "2026-08-01T13:00:00+09:00",
        )
        self.assertEqual(
            eg7.canonical_forecast_target_signature(first),
            expected_signature,
        )
        self.assertEqual(
            eg7.canonical_forecast_target_signature(permuted_and_formatted),
            expected_signature,
        )
        self.assertEqual(
            eg7.canonical_forecast_target_signature(repeated),
            expected_signature,
        )
        self.assertNotEqual(
            eg7.canonical_forecast_target_signature(different),
            expected_signature,
        )

        with tempfile.TemporaryDirectory() as temp:
            stage_root = Path(temp) / "stages/eg6b"
            for record, targets in zip(
                records[:4],
                (first, permuted_and_formatted, repeated, different),
            ):
                write_batch_evidence(
                    stage_root,
                    record,
                    forecast_targets=targets,
                )
            first_raw_path = (
                stage_root
                / "data/raw/population"
                / records[0].slot.batch_id
                / f"{eg6b.EG6B_AREA_CODES[0]}.json"
            )
            second_raw_path = (
                stage_root
                / "data/raw/population"
                / records[1].slot.batch_id
                / f"{eg6b.EG6B_AREA_CODES[0]}.json"
            )
            raw_before = {
                first_raw_path: first_raw_path.read_bytes(),
                second_raw_path: second_raw_path.read_bytes(),
            }
            rows = eg7.build_area_observation_index(
                plan,
                records[:4],
                stage_root=stage_root,
                official_csv=ROOT / "data/reference/seoul_121_places.csv",
            )
            raw_after = {path: path.read_bytes() for path in raw_before}

        self.assertFalse(rows[0]["duplicate_forecast_targets"])
        self.assertFalse(rows[1]["duplicate_forecast_targets"])
        self.assertTrue(rows[13]["duplicate_forecast_targets"])
        self.assertTrue(rows[26]["duplicate_forecast_targets"])
        self.assertFalse(rows[39]["duplicate_forecast_targets"])
        self.assertEqual(rows[26]["forecast_record_count"], 4)
        self.assertEqual(raw_before, raw_after)
        raw_forecasts = json.loads(raw_before[second_raw_path])[
            "SeoulRtd.citydata_ppltn"
        ][0]["FCST_PPLTN"]
        self.assertEqual(
            [item["FCST_TIME"] for item in raw_forecasts],
            permuted_and_formatted,
        )

    def test_invalid_forecast_target_timestamp_is_not_repaired(self) -> None:
        for invalid in ("not-a-timestamp", "2026-08-01"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CANONICAL_EVIDENCE_INVALID",
                ):
                    eg7.canonical_forecast_target_signature(
                        ["2026-08-01 11:00", invalid]
                    )

    def test_failed_area_row_uses_native_nulls(self) -> None:
        plan = eg7.validate_plan(plan_document())
        records = completed_records(plan)
        with tempfile.TemporaryDirectory() as temp:
            stage_root = Path(temp) / "stages/eg6b"
            write_batch_evidence(stage_root, records[0], failure_panel=2)
            rows = eg7.build_area_observation_index(
                plan,
                records[:1],
                stage_root=stage_root,
                official_csv=ROOT / "data/reference/seoul_121_places.csv",
            )
        failed = rows[1]
        self.assertEqual(failed["area_status"], "timeout")
        self.assertIsNone(failed["raw_relative_path"])
        self.assertIsNone(failed["population_min"])
        self.assertIsNone(failed["api_observation_at"])

    def test_area_index_rejects_tampered_canonical_evidence(self) -> None:
        plan = eg7.validate_plan(plan_document())
        records = completed_records(plan)
        with tempfile.TemporaryDirectory() as temp:
            stage_root = Path(temp) / "stages/eg6b"
            write_batch_evidence(stage_root, records[0])
            first_raw = next((stage_root / "data/raw/population").rglob("*.json"))
            first_raw.write_bytes(first_raw.read_bytes() + b"tampered")
            with self.assertRaisesRegex(
                RuntimeError,
                "CANONICAL_EVIDENCE_INVALID",
            ):
                eg7.build_area_observation_index(
                    plan,
                    records[:1],
                    stage_root=stage_root,
                    official_csv=ROOT / "data/reference/seoul_121_places.csv",
                )

    def test_fatal_incomplete_batch_does_not_invent_area_rows(self) -> None:
        plan = eg7.validate_plan(plan_document())
        record = eg7.SlotRecord(
            slot=plan.slots[0],
            status=eg7.SlotStatus.STOPPED_FATAL,
            attempted_area_count=1,
            successful_area_count=0,
            failed_area_count=1,
            actual_api_calls=1,
            collector_execution_count=1,
            failure_reason=eg7.FailureClass.STORAGE_FAILURE_FATAL.value,
            collection_log={
                "attempted_count": 1,
                "success_count": 0,
                "failure_count": 1,
                "area_results": [],
            },
        )
        with tempfile.TemporaryDirectory() as temp:
            rows = eg7.build_area_observation_index(
                plan,
                [record],
                stage_root=Path(temp) / "missing-canonical-stage",
            )
        self.assertEqual(rows, [])
        summary = eg7.build_pilot_summary(plan, [], rows, [record])
        self.assertEqual(summary["attempted_area_count"], 1)
        self.assertEqual(summary["failed_area_count"], 1)
        self.assertIsNone(summary["source_storage_growth_bytes"])

    def test_jsonl_and_csv_contracts_preserve_types_without_absolute_paths(self) -> None:
        plan = eg7.validate_plan(plan_document())
        records = completed_records(plan)
        slot_rows = eg7.build_slot_index(plan, records)
        summary = eg7.build_pilot_summary(plan, slot_rows, [], records)
        with tempfile.TemporaryDirectory() as temp:
            run_root = Path(temp) / "derived"
            eg7.write_derived_outputs(
                run_root,
                slot_rows=slot_rows,
                area_rows=[],
                summary=summary,
            )
            jsonl_row = json.loads(
                (run_root / "slot_index.jsonl").read_text(encoding="utf-8").splitlines()[0]
            )
            with (run_root / "slot_index.csv").open(
                "r", encoding="utf-8", newline=""
            ) as source:
                csv_row = next(csv.DictReader(source))
            rendered = b"".join(path.read_bytes() for path in run_root.iterdir())

        self.assertIs(jsonl_row["backup_eligible"], True)
        self.assertEqual(csv_row["backup_eligible"], "true")
        self.assertNotIn(str(ROOT).encode("utf-8"), rendered)
        self.assertNotIn(b"SEOUL_OPEN", rendered)

    def test_summary_marks_ml_performance_out_of_scope(self) -> None:
        plan = eg7.validate_plan(plan_document())
        records = completed_records(plan)
        slot_rows = eg7.build_slot_index(plan, records)
        summary = eg7.build_pilot_summary(plan, slot_rows, [], records)
        self.assertEqual(summary["planned_slot_count"], 12)
        self.assertEqual(summary["cadence_decision_status"], "PM_APPROVED_FIXED")
        self.assertEqual(summary["long_term_baseline_status"], "ACTIVE")
        self.assertEqual(summary["cadence_scope"], "LONG_TERM_OPERATING_BASELINE")
        self.assertFalse(summary["alternative_cadences_supported"])
        self.assertFalse(summary["duplicate_triggered_cadence_change"])
        self.assertEqual(summary["total_actual_seoul_api_calls"], 156)
        self.assertTrue(summary["no_recollection_confirmation"])
        self.assertFalse(summary["ml_model_performance_assessed"])


if __name__ == "__main__":
    unittest.main()
