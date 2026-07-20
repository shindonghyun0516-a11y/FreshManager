from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import os
import socket
import shutil
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from scripts import project_guard_check as project_guard


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    number = 1
    for category, count in project_guard.EXPECTED_CATEGORIES.items():
        for _ in range(count):
            code = f"TST-{number:03d}"
            name = f"테스트 장소 {number}"
            if number == 13:
                code = "POI013"
                name = "가산디지털단지역"
            elif number == 14:
                code = "POI014"
                name = "강남역"
            elif number == 19:
                code = "POI019"
                name = "구로디지털단지역"
            elif number == 72:
                code = "POI072"
                name = "여의도"
            rows.append(
                {
                    "CATEGORY": category,
                    "NO": str(number),
                    "AREA_CD": code,
                    "AREA_NM": name,
                    "ENG_NM": f"Test Place {number}",
                }
            )
            number += 1
    return rows


def valid_sample() -> dict[str, object]:
    current = {field: "1" for field in project_guard.CURRENT_POPULATION_FIELDS}
    current.update(
        {
            "AREA_NM": "여의도",
            "AREA_CD": "POI072",
            "AREA_CONGEST_LVL": "보통",
            "AREA_CONGEST_MSG": "테스트 메시지",
            "PPLTN_TIME": "2026-07-16 20:00",
            "FCST_YN": "Y",
            "FEMALE_PPLTN_RATE": "50.0",
            "FCST_PPLTN": [
                {
                    "FCST_TIME": "2026-07-16 21:00",
                    "FCST_CONGEST_LVL": "보통",
                    "FCST_PPLTN_MIN": "1000",
                    "FCST_PPLTN_MAX": "1200",
                }
            ],
        }
    )
    return {
        "SeoulRtd.citydata_ppltn": [current],
        "RESULT": {
            "RESULT.CODE": "INFO-000",
            "RESULT.MESSAGE": "정상 처리되었습니다",
        },
    }


def write_csv(path: Path, rows: list[dict[str, str]], headers: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = headers or list(project_guard.EXPECTED_HEADERS)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class TemporaryProject:
    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="freshmanager-test-")
        self.root = Path(self._temporary.name)
        self.csv_path = self.root / project_guard.CSV_RELATIVE_PATH
        self.json_path = self.root / project_guard.JSON_RELATIVE_PATH
        write_csv(self.csv_path, valid_rows())
        write_json(self.json_path, valid_sample())

    def context(self) -> project_guard.ProjectGuardContext:
        return project_guard.ProjectGuardContext(
            root=self.root,
            csv_hash_before=file_hash(self.csv_path),
            json_hash_before=file_hash(self.json_path),
        )

    def close(self) -> None:
        self._temporary.cleanup()


class TemporaryGitProject:
    """Synthetic Git repository for H-206; it never uses real protected entries."""

    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="freshmanager-h206-")
        self.root = Path(self._temporary.name)
        self.run("init", "-q")
        self.run("config", "user.name", "FreshManager Test")
        self.run("config", "user.email", "freshmanager-test@example.invalid")
        (self.root / ".gitignore").write_text(
            f"/{project_guard.PROTECTED_WORK_LOG_DIRECTORY}/\n",
            encoding="utf-8",
        )
        self.run("add", ".gitignore")
        self.run("commit", "-q", "-m", "synthetic baseline")

    def run(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            check=False,
            capture_output=True,
        )
        if check and result.returncode != 0:
            raise AssertionError("synthetic Git command failed; output intentionally hidden")
        return result

    def context(self) -> project_guard.ProjectGuardContext:
        return project_guard.ProjectGuardContext(
            root=self.root,
            csv_hash_before=None,
            json_hash_before=None,
        )

    def head(self) -> str:
        return self.run("rev-parse", "HEAD").stdout.decode("ascii").strip()

    def create_protected_file(self) -> Path:
        protected_root = self.root / project_guard.PROTECTED_WORK_LOG_DIRECTORY
        protected_root.mkdir(exist_ok=True)
        synthetic_file = protected_root / "synthetic-entry.txt"
        synthetic_file.write_text("synthetic only\n", encoding="utf-8")
        return synthetic_file

    def commit_protected_file(self) -> None:
        self.create_protected_file()
        self.run("add", "-f", "--", project_guard.PROTECTED_WORK_LOG_DIRECTORY)
        self.run("commit", "-q", "-m", "synthetic protected entry")

    def remove_protected_directory(self) -> None:
        shutil.rmtree(self.root / project_guard.PROTECTED_WORK_LOG_DIRECTORY)

    def close(self) -> None:
        self._temporary.cleanup()


def valid_h004_readme() -> str:
    return f"""# FreshManager Test

data/reference/seoul_121_places.csv
data/samples/population_yeouido_sample.json
| EG-1 통과 | PASS |
`H-301`~`H-304`

## 6. 현재 프로젝트 상태

- EG-3 Python Project Guard 구현 완료

## 9. 단계적 구현 순서

{project_guard.EG3_STATUS_ROW}

## 18. 현재 실행방법

```bash
{project_guard.STANDARD_PROJECT_GUARD_COMMAND}
```

## 19. 변경 이력

현재 상태만 검사한다.
"""


def quality_gate_status_fixture(extra_current_text: str = "") -> str:
    return f"""# Quality Gates

## 3. 전체 순서와 현재 상태

| 게이트 | 현재 상태 |
|---|---|
| EG-4 | 통과: Issue #43 완료 |
| EG-5 | 진행: 오프라인 구현 중; 실제 세 장소 호출 미실행 |
| EG-6 | 미구현 |

EG-4는 통과했고 EG-5는 오프라인 구현을 진행한다.
{extra_current_text}

## 4. 다음 절

후속 내용
"""


class H003CurrentGateStatusTests(unittest.TestCase):
    def test_current_gate_status_fixture_without_conflict_passes(self) -> None:
        self.assertEqual(
            project_guard.current_gate_status_conflicts(quality_gate_status_fixture()),
            [],
        )

    def test_current_gate_status_conflicts_are_detected(self) -> None:
        conflicts = {
            "eg4_not_passed": "EG-4 전체 통과 전 상태다.",
            "eg5_not_started": "EG-5는 아직 시작되지 않았다.",
            "actual_collection_complete": "EG-5 대표 3장소 정상 실응답 검증 완료.",
        }
        for case_name, text in conflicts.items():
            with self.subTest(case_name=case_name):
                self.assertTrue(
                    project_guard.current_gate_status_conflicts(
                        quality_gate_status_fixture(text)
                    )
                )

    def test_repository_quality_gate_current_state_has_no_conflict(self) -> None:
        text = (ROOT / "docs/testing/QUALITY_GATES.md").read_text(encoding="utf-8")
        self.assertEqual(project_guard.current_gate_status_conflicts(text), [])


class H004ReadmeStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()
        self.readme_path = self.project.root / "README.md"
        self.project_guard_path = self.project.root / "scripts/project_guard_check.py"
        self.project_guard_path.parent.mkdir(parents=True, exist_ok=True)
        self.project_guard_path.write_text("# test Project Guard\n", encoding="utf-8")
        self.readme_path.write_text(valid_h004_readme(), encoding="utf-8")

    def tearDown(self) -> None:
        self.project.close()

    def check(self) -> project_guard.CheckResult:
        return project_guard.check_h004(self.project.context())

    def test_missing_project_guard_file_fails(self) -> None:
        self.project_guard_path.unlink()
        self.assertEqual(self.check().status, project_guard.Status.FAIL)

    def test_missing_standard_command_fails(self) -> None:
        text = valid_h004_readme().replace(project_guard.STANDARD_PROJECT_GUARD_COMMAND, "명령 미기재")
        self.readme_path.write_text(text, encoding="utf-8")
        self.assertEqual(self.check().status, project_guard.Status.FAIL)

    def test_eg3_unimplemented_current_status_fails(self) -> None:
        text = valid_h004_readme().replace(
            project_guard.EG3_STATUS_ROW,
            "| EG-3 | Project Guard 구현 및 자동 재검증 | 미구현 |",
        )
        self.readme_path.write_text(text, encoding="utf-8")
        self.assertEqual(self.check().status, project_guard.Status.FAIL)

    def test_project_guard_code_missing_current_status_fails(self) -> None:
        text = valid_h004_readme().replace(
            "- EG-3 Python Project Guard 구현 완료",
            "- Project Guard 코드 없음",
        )
        self.readme_path.write_text(text, encoding="utf-8")
        self.assertEqual(self.check().status, project_guard.Status.FAIL)

    def test_matching_project_guard_and_readme_pass(self) -> None:
        result = self.check()
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_past_history_phrase_outside_current_sections_does_not_fail(self) -> None:
        text = valid_h004_readme().replace(
            "현재 상태만 검사한다.",
            "과거 이력: EG-3 미구현 상태에서 계획을 시작했다.",
        )
        self.readme_path.write_text(text, encoding="utf-8")
        result = self.check()
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)


class CsvContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()

    def tearDown(self) -> None:
        self.project.close()

    def assert_failed(self, result: project_guard.CheckResult) -> None:
        self.assertEqual(result.status, project_guard.Status.FAIL, result.evidence)

    def test_official_csv_passes_all_csv_contracts(self) -> None:
        context = project_guard.ProjectGuardContext(
            root=ROOT,
            csv_hash_before=file_hash(ROOT / project_guard.CSV_RELATIVE_PATH),
            json_hash_before=file_hash(ROOT / project_guard.JSON_RELATIVE_PATH),
        )
        for check_id in range(101, 113):
            result = getattr(project_guard, f"check_h{check_id}")(context)
            self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_missing_csv_is_a_validation_failure(self) -> None:
        self.project.csv_path.unlink()
        context = project_guard.ProjectGuardContext(
            root=self.project.root,
            csv_hash_before=None,
            json_hash_before=file_hash(self.project.json_path),
        )
        result = project_guard.check_h101(context)
        self.assert_failed(result)

    def test_missing_required_header_fails(self) -> None:
        shutil.copyfile(FIXTURES / "csv/missing_required_column.csv", self.project.csv_path)
        self.assert_failed(project_guard.check_h103(self.project.context()))

    def test_additional_header_fails(self) -> None:
        write_csv(self.project.csv_path, valid_rows(), project_guard.EXPECTED_HEADERS + ["EXTRA"])
        self.assert_failed(project_guard.check_h103(self.project.context()))

    def test_header_order_fails(self) -> None:
        headers = list(project_guard.EXPECTED_HEADERS)
        headers[0], headers[1] = headers[1], headers[0]
        write_csv(self.project.csv_path, valid_rows(), headers)
        self.assert_failed(project_guard.check_h103(self.project.context()))

    def test_wrong_record_count_fails(self) -> None:
        write_csv(self.project.csv_path, valid_rows()[:-1])
        self.assert_failed(project_guard.check_h104(self.project.context()))

    def test_missing_area_code_fails(self) -> None:
        rows = valid_rows()
        rows[0]["AREA_CD"] = ""
        write_csv(self.project.csv_path, rows)
        self.assert_failed(project_guard.check_h105(self.project.context()))

    def test_duplicate_area_code_fails(self) -> None:
        rows = valid_rows()
        rows[1]["AREA_CD"] = rows[0]["AREA_CD"]
        write_csv(self.project.csv_path, rows)
        self.assert_failed(project_guard.check_h106(self.project.context()))

    def test_missing_area_name_fails(self) -> None:
        rows = valid_rows()
        rows[0]["AREA_NM"] = ""
        write_csv(self.project.csv_path, rows)
        self.assert_failed(project_guard.check_h107(self.project.context()))

    def test_wrong_yeouido_code_fails(self) -> None:
        rows = valid_rows()
        rows[71]["AREA_CD"] = "WRONG-CODE"
        write_csv(self.project.csv_path, rows)
        self.assert_failed(project_guard.check_h108(self.project.context()))

    def test_wrong_category_count_fails(self) -> None:
        rows = valid_rows()
        rows[0]["CATEGORY"] = "공원"
        write_csv(self.project.csv_path, rows)
        self.assert_failed(project_guard.check_h112(self.project.context()))

    def test_invalid_utf8_fails(self) -> None:
        self.project.csv_path.write_bytes(b"CATEGORY,NO\n\xff,1\n")
        self.assert_failed(project_guard.check_h102(self.project.context()))

    def test_bom_and_no_bom_are_both_readable(self) -> None:
        write_csv(self.project.csv_path, valid_rows())
        self.assertEqual(project_guard.check_h102(self.project.context()).status, project_guard.Status.PASS)
        text = self.project.csv_path.read_text(encoding="utf-8-sig")
        with self.project.csv_path.open("w", encoding="utf-8", newline="") as target:
            target.write(text)
        self.assertEqual(project_guard.check_h102(self.project.context()).status, project_guard.Status.PASS)

    def test_area_codes_are_preserved_from_csv_not_no(self) -> None:
        expected = [row["AREA_CD"] for row in valid_rows()]
        self.assertEqual(project_guard.load_area_codes(self.project.csv_path), expected)

    def test_csv_check_does_not_modify_input(self) -> None:
        before = file_hash(self.project.csv_path)
        result = project_guard.check_h111(self.project.context())
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)
        self.assertEqual(file_hash(self.project.csv_path), before)


class JsonContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()

    def tearDown(self) -> None:
        self.project.close()

    def assert_failed(self, result: project_guard.CheckResult) -> None:
        self.assertEqual(result.status, project_guard.Status.FAIL, result.evidence)

    def use_fixture(self, relative_path: str) -> None:
        shutil.copyfile(FIXTURES / relative_path, self.project.json_path)

    def test_official_json_passes_h301_to_h304(self) -> None:
        context = project_guard.ProjectGuardContext(
            root=ROOT,
            csv_hash_before=file_hash(ROOT / project_guard.CSV_RELATIVE_PATH),
            json_hash_before=file_hash(ROOT / project_guard.JSON_RELATIVE_PATH),
        )
        for check_id in range(301, 305):
            result = getattr(project_guard, f"check_h{check_id}")(context)
            self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_missing_json_is_a_validation_failure(self) -> None:
        self.project.json_path.unlink()
        context = project_guard.ProjectGuardContext(
            root=self.project.root,
            csv_hash_before=file_hash(self.project.csv_path),
            json_hash_before=None,
        )
        self.assert_failed(project_guard.check_h301(context))

    def test_invalid_json_fails(self) -> None:
        self.use_fixture("json/invalid_json.json")
        self.assert_failed(project_guard.check_h301(self.project.context()))

    def test_missing_current_population_field_fails(self) -> None:
        self.use_fixture("json/missing_population_field.json")
        self.assert_failed(project_guard.check_h302(self.project.context()))

    def test_wrong_yeouido_code_fails(self) -> None:
        document = valid_sample()
        document["SeoulRtd.citydata_ppltn"][0]["AREA_CD"] = "WRONG-CODE"  # type: ignore[index]
        write_json(self.project.json_path, document)
        self.assert_failed(project_guard.check_h302(self.project.context()))

    def test_population_array_must_have_exactly_one_object(self) -> None:
        document = valid_sample()
        document["SeoulRtd.citydata_ppltn"].append(valid_sample()["SeoulRtd.citydata_ppltn"][0])  # type: ignore[union-attr,index]
        write_json(self.project.json_path, document)
        self.assert_failed(project_guard.check_h302(self.project.context()))

    def test_empty_forecast_array_fails(self) -> None:
        self.use_fixture("json/empty_forecast_array.json")
        self.assert_failed(project_guard.check_h303(self.project.context()))

    def test_missing_forecast_array_fails(self) -> None:
        document = valid_sample()
        del document["SeoulRtd.citydata_ppltn"][0]["FCST_PPLTN"]  # type: ignore[index]
        write_json(self.project.json_path, document)
        self.assert_failed(project_guard.check_h303(self.project.context()))

    def test_missing_forecast_field_fails(self) -> None:
        self.use_fixture("json/forecast_missing_field.json")
        self.assert_failed(project_guard.check_h303(self.project.context()))

    def test_forecast_minimum_greater_than_maximum_fails(self) -> None:
        document = valid_sample()
        forecast = document["SeoulRtd.citydata_ppltn"][0]["FCST_PPLTN"][0]  # type: ignore[index]
        forecast["FCST_PPLTN_MIN"] = "1300"
        forecast["FCST_PPLTN_MAX"] = "1200"
        write_json(self.project.json_path, document)
        self.assert_failed(project_guard.check_h303(self.project.context()))

    def test_forecast_count_is_informational(self) -> None:
        result = project_guard.check_h303(self.project.context())
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)
        self.assertIn("예측 객체 1개", result.evidence)


class SecurityAndOfflineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()

    def tearDown(self) -> None:
        self.project.close()

    def test_sensitive_assignment_is_detected_without_value_output(self) -> None:
        note = self.project.root / "note.md"
        variable = "SEOUL_OPEN" + "_API_KEY"
        fake_value = "FAKE_" + "TEST_VALUE_123456"
        note.write_text(f"{variable}={fake_value}\n", encoding="utf-8")
        result = project_guard.check_h203(self.project.context())
        self.assertEqual(result.status, project_guard.Status.FAIL)
        self.assertIn("note.md:1:환경변수 실제값 의심", result.evidence)
        self.assertNotIn(fake_value, result.evidence)

    def test_executable_auth_url_is_detected_without_value_output(self) -> None:
        note = self.project.root / "url.log"
        fake_value = "FAKE" + "TESTKEY123456"
        url = "http://" + "openapi.seoul.go.kr:8088/" + fake_value + "/json/example"
        note.write_text(url + "\n", encoding="utf-8")
        result = project_guard.check_h203(self.project.context())
        self.assertEqual(result.status, project_guard.Status.FAIL)
        self.assertIn("인증키 포함 실행 URL 의심", result.evidence)
        self.assertNotIn(fake_value, result.evidence)

    def test_json_secret_field_is_detected_without_value_output(self) -> None:
        note = self.project.root / "secret.json"
        key_name = "api" + "_key"
        fake_value = "FAKE_" + "JSON_VALUE_123456"
        note.write_text(json.dumps({key_name: fake_value}) + "\n", encoding="utf-8")
        result = project_guard.check_h203(self.project.context())
        self.assertEqual(result.status, project_guard.Status.FAIL)
        self.assertIn("JSON Secret 필드 실제값 의심", result.evidence)
        self.assertNotIn(fake_value, result.evidence)

    def test_non_executable_and_masked_examples_are_allowed(self) -> None:
        note = self.project.root / "safe.md"
        note.write_text(".../{API_KEY}/...\n.../********/...\n", encoding="utf-8")
        result = project_guard.check_h203(self.project.context())
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_real_env_is_never_selected_for_reading(self) -> None:
        env_path = self.project.root / ".env"
        env_path.write_text("DO_NOT_READ\n", encoding="utf-8")
        selected = list(project_guard.iter_security_files(self.project.root))
        self.assertNotIn(env_path, selected)

    def test_h203_never_opens_top_level_protected_work_log(self) -> None:
        protected_root = self.project.root / project_guard.PROTECTED_WORK_LOG_DIRECTORY
        protected_root.mkdir()
        protected_file = protected_root / "sentinel.md"
        protected_value = "PROTECTED_" + "VALUE_123456"
        env_name = "SEOUL_OPEN" + "_API_KEY"
        protected_file.write_text(
            f"{env_name}={protected_value}\n",
            encoding="utf-8",
        )
        visible_root = self.project.root / "other log"
        visible_root.mkdir()
        visible_file = visible_root / "visible-security-note.md"
        visible_value = "VISIBLE_" + "VALUE_123456"
        visible_file.write_text(
            f"{env_name}={visible_value}\n",
            encoding="utf-8",
        )
        original_open = Path.open

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            if path == protected_file:
                raise AssertionError("protected file must not be opened")
            return original_open(path, *args, **kwargs)  # type: ignore[arg-type]

        with mock.patch.object(Path, "open", new=guarded_open):
            result = project_guard.check_h203(self.project.context())

        self.assertEqual(result.status, project_guard.Status.FAIL)
        self.assertIn("other log/visible-security-note.md", result.evidence)
        self.assertNotIn("sentinel", result.evidence)
        self.assertNotIn(protected_value, result.evidence)
        self.assertNotIn(visible_value, result.evidence)

    def test_all_guard_walkers_prune_top_level_protected_python_before_open(self) -> None:
        protected_root = self.project.root / project_guard.PROTECTED_WORK_LOG_DIRECTORY
        protected_root.mkdir()
        protected_file = protected_root / "protected-python-sentinel.py"
        protected_value = "PROTECTED_" + "PYTHON_VALUE_123456"
        env_name = "SEOUL_OPEN" + "_API_KEY"
        protected_file.write_text(
            f"{env_name}={protected_value}\nimport requests\n",
            encoding="utf-8",
        )

        normal_file = self.project.root / "normal.py"
        normal_file.write_text("NORMAL_VALUE = 1\n", encoding="utf-8")
        visible_root = self.project.root / "other log"
        visible_root.mkdir()
        visible_file = visible_root / "visible-security.py"
        visible_value = "VISIBLE_" + "PYTHON_VALUE_123456"
        visible_file.write_text(
            f"{env_name}={visible_value}\nimport requests\n",
            encoding="utf-8",
        )
        nested_same_name = self.project.root / "nested" / project_guard.PROTECTED_WORK_LOG_DIRECTORY
        nested_same_name.mkdir(parents=True)
        nested_file = nested_same_name / "nested-visible.py"
        nested_file.write_text("NESTED_VALUE = 1\n", encoding="utf-8")

        context = self.project.context()
        original_open = Path.open
        original_scandir = project_guard.os.scandir

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            if path == protected_file:
                raise AssertionError("protected Python file must not be opened")
            return original_open(path, *args, **kwargs)  # type: ignore[arg-type]

        def guarded_scandir(path: object) -> object:
            if Path(path) == protected_root:  # type: ignore[arg-type]
                raise AssertionError("protected directory must not be entered")
            return original_scandir(path)  # type: ignore[arg-type]

        with (
            mock.patch.object(Path, "open", new=guarded_open),
            mock.patch.object(project_guard.os, "scandir", new=guarded_scandir),
        ):
            security_files = list(project_guard.iter_security_files(self.project.root))
            python_files = project_guard.project_python_files(self.project.root)
            h203 = project_guard.check_h203(context)
            h305 = project_guard.check_h305(context)
            h401 = project_guard.check_h401(context)

        self.assertNotIn(protected_file, security_files)
        self.assertIn(normal_file, security_files)
        self.assertIn(visible_file, security_files)
        self.assertIn(nested_file, security_files)
        self.assertNotIn(protected_file, python_files)
        self.assertIn(normal_file, python_files)
        self.assertIn(visible_file, python_files)
        self.assertIn(nested_file, python_files)
        self.assertEqual(h203.status, project_guard.Status.FAIL)
        self.assertIn("other log/visible-security.py", h203.evidence)
        self.assertEqual(h305.status, project_guard.Status.FAIL)
        self.assertIn("other log/visible-security.py", h305.evidence)
        self.assertEqual(h401.status, project_guard.Status.PASS, h401.evidence)
        combined_evidence = "\n".join((h203.evidence, h305.evidence, h401.evidence))
        self.assertNotIn(project_guard.PROTECTED_WORK_LOG_DIRECTORY, combined_evidence)
        self.assertNotIn(protected_file.name, combined_evidence)
        self.assertNotIn(protected_value, combined_evidence)
        self.assertNotIn(visible_value, combined_evidence)

    def test_full_project_guard_does_not_connect_to_network(self) -> None:
        with (
            mock.patch("socket.create_connection", side_effect=AssertionError("network forbidden")) as connection,
            mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")) as socket_connect,
            mock.patch("socket.getaddrinfo", side_effect=AssertionError("network forbidden")) as getaddrinfo,
            mock.patch(
                "freshmanager.http_adapter.UrllibTransport.open",
                side_effect=AssertionError("HTTP forbidden"),
            ) as transport_open,
        ):
            results = project_guard.run_project_guard(ROOT)
        connection.assert_not_called()
        socket_connect.assert_not_called()
        getaddrinfo.assert_not_called()
        transport_open.assert_not_called()
        result = next(item for item in results if item.check_id == "H-305")
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_h305_allows_network_code_only_in_approved_transport(self) -> None:
        path = self.project.root / project_guard.APPROVED_NETWORK_ADAPTER_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "import urllib.request\n"
            "class UrllibTransport:\n"
            "    def open(self, request):\n"
            "        return urllib.request.urlopen(request)\n",
            encoding="utf-8",
        )
        result = project_guard.check_h305(self.project.context())
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_h305_rejects_network_code_in_other_product_module(self) -> None:
        path = self.project.root / "freshmanager/other.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("import urllib.request\n", encoding="utf-8")
        result = project_guard.check_h305(self.project.context())
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_h305_rejects_network_code_in_scripts_and_tests(self) -> None:
        for relative_path in ["scripts/network_task.py", "tests/test_network.py"]:
            with self.subTest(relative_path=relative_path):
                project = TemporaryProject()
                try:
                    path = project.root / relative_path
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("import urllib.request\n", encoding="utf-8")
                    result = project_guard.check_h305(project.context())
                    self.assertEqual(result.status, project_guard.Status.FAIL)
                finally:
                    project.close()

    def test_h305_rejects_adapter_module_level_network_execution(self) -> None:
        path = self.project.root / project_guard.APPROVED_NETWORK_ADAPTER_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "import urllib.request\n"
            "urllib.request.urlopen('redacted')\n",
            encoding="utf-8",
        )
        result = project_guard.check_h305(self.project.context())
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_h205_adapter_error_hides_key_and_url(self) -> None:
        result = project_guard.check_h205(self.project.context())
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_h003_uses_received_at_metadata_contract(self) -> None:
        self.assertEqual(project_guard.METADATA_FIELDS, list(project_guard.EG4_METADATA_FIELDS))
        self.assertIn("received_at", project_guard.METADATA_FIELDS)
        self.assertNotIn("parser_version", project_guard.METADATA_FIELDS)


class H206ProtectedWorkLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = TemporaryGitProject()

    def tearDown(self) -> None:
        self.repository.close()

    def check_h206(self) -> project_guard.CheckResult:
        with mock.patch.dict(
            os.environ,
            {
                project_guard.PROTECTED_GIT_BASE_ENV: "",
                project_guard.PROTECTED_GIT_HEAD_ENV: "",
            },
        ):
            return project_guard.check_h206(self.repository.context())

    def write_ignore_rules(self, *rules: str) -> None:
        (self.repository.root / ".gitignore").write_text(
            "\n".join(rules) + "\n",
            encoding="utf-8",
        )

    def test_absent_protected_directory_passes(self) -> None:
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_recreated_protected_directory_fails(self) -> None:
        (self.repository.root / project_guard.PROTECTED_WORK_LOG_DIRECTORY).mkdir()
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_untracked_protected_entry_fails(self) -> None:
        self.repository.create_protected_file()
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_tracked_protected_entry_fails(self) -> None:
        self.repository.commit_protected_file()
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_staged_protected_entry_fails_even_when_directory_is_absent(self) -> None:
        synthetic_file = self.repository.create_protected_file()
        self.repository.run("add", "-f", "--", project_guard.PROTECTED_WORK_LOG_DIRECTORY)
        synthetic_file.unlink()
        synthetic_file.parent.rmdir()
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)
        self.assertIn("Stage", result.evidence)

    def test_approved_unstaged_removal_transition_passes(self) -> None:
        self.repository.commit_protected_file()
        self.repository.remove_protected_directory()
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)
        self.assertIn("approved_removal_transition", result.evidence)

    def test_base_to_head_deletion_only_transition_passes(self) -> None:
        self.repository.commit_protected_file()
        base_sha = self.repository.head()
        self.repository.remove_protected_directory()
        self.repository.run("add", "-u", "--", project_guard.PROTECTED_WORK_LOG_DIRECTORY)
        self.repository.run("commit", "-q", "-m", "synthetic protected removal")
        head_sha = self.repository.head()
        with mock.patch.dict(
            os.environ,
            {
                project_guard.PROTECTED_GIT_BASE_ENV: base_sha,
                project_guard.PROTECTED_GIT_HEAD_ENV: head_sha,
            },
        ):
            result = project_guard.check_h206(self.repository.context())
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)
        self.assertIn("approved_deletion_only", result.evidence)

    def test_base_to_head_protected_addition_fails(self) -> None:
        base_sha = self.repository.head()
        self.repository.commit_protected_file()
        head_sha = self.repository.head()
        self.repository.remove_protected_directory()
        with mock.patch.dict(
            os.environ,
            {
                project_guard.PROTECTED_GIT_BASE_ENV: base_sha,
                project_guard.PROTECTED_GIT_HEAD_ENV: head_sha,
            },
        ):
            result = project_guard.check_h206(self.repository.context())
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_virtual_probe_is_ignored_without_broad_log_ignore(self) -> None:
        protected_probe = self.repository.run(
            "check-ignore",
            "-q",
            "--no-index",
            "--",
            project_guard.PROTECTED_VIRTUAL_PROBE,
            check=False,
        )
        self.assertEqual(protected_probe.returncode, 0)
        for probe in project_guard.UNRELATED_IGNORE_PROBES:
            with self.subTest(probe_kind="unrelated"):
                unrelated_probe = self.repository.run(
                    "check-ignore",
                    "-q",
                    "--no-index",
                    "--",
                    probe,
                    check=False,
                )
                self.assertEqual(unrelated_probe.returncode, 1)

    def test_equivalent_but_non_exact_ignore_rule_fails(self) -> None:
        (self.repository.root / ".gitignore").write_text(
            f"/{project_guard.PROTECTED_WORK_LOG_DIRECTORY}/**\n",
            encoding="utf-8",
        )
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_broad_ignore_rule_fails(self) -> None:
        (self.repository.root / ".gitignore").write_text("/work*/\n", encoding="utf-8")
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_exact_rule_plus_broad_rule_fails(self) -> None:
        self.write_ignore_rules(
            f"/{project_guard.PROTECTED_WORK_LOG_DIRECTORY}/",
            "/work*/",
        )
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_exact_rule_plus_general_log_rule_fails(self) -> None:
        self.write_ignore_rules(
            f"/{project_guard.PROTECTED_WORK_LOG_DIRECTORY}/",
            "/*log*/",
        )
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_exact_rule_plus_parent_scope_rule_fails(self) -> None:
        self.write_ignore_rules(
            f"/{project_guard.PROTECTED_WORK_LOG_DIRECTORY}/",
            "/*",
        )
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_missing_protected_rule_fails(self) -> None:
        self.write_ignore_rules("/project notes/")
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_similar_path_rule_without_exact_rule_fails(self) -> None:
        self.write_ignore_rules(f"/{project_guard.PROTECTED_WORK_LOG_DIRECTORY}s/")
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_exact_rule_plus_nested_same_name_rule_fails(self) -> None:
        self.write_ignore_rules(
            f"/{project_guard.PROTECTED_WORK_LOG_DIRECTORY}/",
            f"**/{project_guard.PROTECTED_WORK_LOG_DIRECTORY}/",
        )
        result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_probe_details_are_not_exposed_on_ignore_failure(self) -> None:
        self.write_ignore_rules(
            f"/{project_guard.PROTECTED_WORK_LOG_DIRECTORY}/",
            "/*",
        )
        result = self.check_h206()
        report = project_guard.format_report([result])
        self.assertEqual(result.status, project_guard.Status.FAIL)
        self.assertNotIn(project_guard.PROTECTED_VIRTUAL_PROBE, report)
        for probe in project_guard.UNRELATED_IGNORE_PROBES:
            self.assertNotIn(probe, report)

    def test_git_stdout_and_stderr_are_never_exposed(self) -> None:
        hidden_name = b"synthetic-hidden-name"
        hidden_error = b"synthetic-hidden-error"
        unsafe = subprocess.CompletedProcess(
            args=["git"],
            returncode=128,
            stdout=hidden_name,
            stderr=hidden_error,
        )
        with mock.patch.object(project_guard, "run_git_bytes", return_value=unsafe):
            result = project_guard.check_h206(self.repository.context())
        report = project_guard.format_report([result])
        self.assertEqual(result.status, project_guard.Status.FAIL)
        self.assertNotIn(hidden_name.decode("ascii"), report)
        self.assertNotIn(hidden_error.decode("ascii"), report)

    def test_h206_does_not_open_read_or_scan_protected_directory(self) -> None:
        protected_root = self.repository.root / project_guard.PROTECTED_WORK_LOG_DIRECTORY
        original_open = Path.open
        original_read_text = Path.read_text
        original_scandir = project_guard.os.scandir

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            if path == protected_root or protected_root in path.parents:
                raise AssertionError("protected open forbidden")
            return original_open(path, *args, **kwargs)  # type: ignore[arg-type]

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            if path == protected_root or protected_root in path.parents:
                raise AssertionError("protected read forbidden")
            return original_read_text(path, *args, **kwargs)  # type: ignore[arg-type]

        def guarded_scandir(path: object) -> object:
            if Path(path) == protected_root:  # type: ignore[arg-type]
                raise AssertionError("protected scan forbidden")
            return original_scandir(path)  # type: ignore[arg-type]

        with (
            mock.patch.object(Path, "open", new=guarded_open),
            mock.patch.object(Path, "read_text", new=guarded_read_text),
            mock.patch.object(project_guard.os, "scandir", new=guarded_scandir),
        ):
            result = self.check_h206()
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_h206_is_unique_mandatory_and_ci_has_comparison_history(self) -> None:
        definitions = [item for item in project_guard.CHECK_DEFINITIONS if item.check_id == "H-206"]
        self.assertEqual(len(definitions), 1)
        self.assertIsNotNone(definitions[0].runner_name)
        self.assertIsNone(definitions[0].skip_reason)
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn(project_guard.PROTECTED_GIT_BASE_ENV, workflow)
        self.assertIn(project_guard.PROTECTED_GIT_HEAD_ENV, workflow)


class Eg4ProjectGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()

    def tearDown(self) -> None:
        self.project.close()

    def assert_passed(self, check_id: str) -> None:
        result = getattr(project_guard, f"check_{check_id.lower().replace('-', '')}")(self.project.context())
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_h204_minimal_env_loader(self) -> None:
        self.assert_passed("H-204")

    def test_h205_secret_masking(self) -> None:
        self.assert_passed("H-205")

    def test_h501_raw_non_overwrite(self) -> None:
        self.assert_passed("H-501")

    def test_h502_raw_filename_contract(self) -> None:
        self.assert_passed("H-502")

    def test_h503_metadata_contract(self) -> None:
        self.assert_passed("H-503")

    def test_h506_error_recording(self) -> None:
        self.assert_passed("H-506")

    def test_h506_fails_when_error_metadata_is_not_persisted(self) -> None:
        with mock.patch.object(
            project_guard.FileStorage,
            "save_metadata",
            side_effect=project_guard.StorageError("storage_error"),
        ):
            result = project_guard.check_h506(self.project.context())
        self.assertEqual(result.status, project_guard.Status.FAIL)

    def test_h701_single_yeouido_collection(self) -> None:
        self.assert_passed("H-701")

    def test_h701_fails_for_empty_normalized_population(self) -> None:
        with mock.patch("freshmanager.collector.parse_population_response", return_value={}):
            result = project_guard.check_h701(self.project.context())
        self.assertEqual(result.status, project_guard.Status.FAIL)


class Eg5ProjectGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()

    def tearDown(self) -> None:
        self.project.close()

    def assert_passed(self, check_id: str) -> None:
        result = getattr(project_guard, f"check_{check_id.lower().replace('-', '')}")(
            self.project.context()
        )
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)

    def test_h702_approved_three_places_and_stage_path(self) -> None:
        self.assert_passed("H-702")

    def test_h704_failure_isolation_and_zero_retries(self) -> None:
        self.assert_passed("H-704")

    def test_h705_round_summary_consistency(self) -> None:
        self.assert_passed("H-705")

    def test_h702_fails_for_changed_allowlist(self) -> None:
        with mock.patch.object(
            project_guard.eg5_cli,
            "EG5_AREA_CODES",
            ("POI019", "POI013", "POI072"),
        ):
            result = project_guard.check_h702(self.project.context())
        self.assertEqual(result.status, project_guard.Status.FAIL)


class RegistryAndExitCodeTests(unittest.TestCase):
    def test_all_46_ids_are_unique_and_in_spec_order(self) -> None:
        registry = [item.check_id for item in project_guard.CHECK_DEFINITIONS]
        spec = project_guard.ids_from_spec(ROOT / project_guard.SPEC_RELATIVE_PATH)
        self.assertEqual(len(registry), 46)
        self.assertEqual(len(set(registry)), 46)
        self.assertEqual(registry, spec)

    def test_expected_current_counts(self) -> None:
        results = project_guard.run_project_guard(ROOT)
        counts = Counter(item.status for item in results)
        self.assertEqual(counts[project_guard.Status.FAIL], 0)
        self.assertEqual(counts[project_guard.Status.WARN], 0)
        self.assertEqual(len(results), 46)
        self.assertEqual(sum(counts.values()), 46)
        status_by_id = {item.check_id: item.status for item in results}
        for check_id in ("H-206", "H-702", "H-704", "H-705"):
            self.assertEqual(status_by_id[check_id], project_guard.Status.PASS)
        self.assertEqual(status_by_id["H-707"], project_guard.Status.SKIP)

    def test_exit_code_zero_for_success(self) -> None:
        result = project_guard.make_result("H-404", project_guard.Status.PASS, "success")
        self.assertEqual(project_guard.exit_code_for([result]), 0)

    def test_exit_code_one_for_required_failure(self) -> None:
        result = project_guard.make_result("H-404", project_guard.Status.FAIL, "failure")
        self.assertEqual(project_guard.exit_code_for([result]), 1)

    def test_exit_code_two_for_internal_error(self) -> None:
        def raise_internal_error(root: Path) -> list[project_guard.CheckResult]:
            raise RuntimeError("sensitive details must not be printed")

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = project_guard.main(ROOT, runner=raise_internal_error)
        self.assertEqual(exit_code, 2)
        self.assertIn("EXIT_CODE=2", stderr.getvalue())
        self.assertNotIn("sensitive details", stderr.getvalue())

    def test_official_files_are_unchanged_by_full_run(self) -> None:
        csv_path = ROOT / project_guard.CSV_RELATIVE_PATH
        json_path = ROOT / project_guard.JSON_RELATIVE_PATH
        before = (file_hash(csv_path), file_hash(json_path))
        project_guard.run_project_guard(ROOT)
        after = (file_hash(csv_path), file_hash(json_path))
        self.assertEqual(after, before)

    def test_markdown_structure_detects_unclosed_fence_and_heading_jump(self) -> None:
        errors = project_guard.check_markdown("# Title\n### Jump\n```python\n")
        self.assertTrue(any("제목 단계" in item for item in errors))
        self.assertIn("닫히지 않은 코드 블록", errors)


if __name__ == "__main__":
    unittest.main()
