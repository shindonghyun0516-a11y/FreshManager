from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import shutil
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
            if number == 72:
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

    def test_full_project_guard_does_not_connect_to_network(self) -> None:
        with mock.patch("socket.create_connection", side_effect=AssertionError("network forbidden")) as connection:
            results = project_guard.run_project_guard(ROOT)
        connection.assert_not_called()
        result = next(item for item in results if item.check_id == "H-305")
        self.assertEqual(result.status, project_guard.Status.PASS, result.evidence)


class RegistryAndExitCodeTests(unittest.TestCase):
    def test_all_45_ids_are_unique_and_in_spec_order(self) -> None:
        registry = [item.check_id for item in project_guard.CHECK_DEFINITIONS]
        spec = project_guard.ids_from_spec(ROOT / project_guard.SPEC_RELATIVE_PATH)
        self.assertEqual(len(registry), 45)
        self.assertEqual(len(set(registry)), 45)
        self.assertEqual(registry, spec)

    def test_expected_eg3_counts(self) -> None:
        results = project_guard.run_project_guard(ROOT)
        counts = Counter(item.status for item in results)
        self.assertEqual(counts[project_guard.Status.PASS], 28)
        self.assertEqual(counts[project_guard.Status.FAIL], 0)
        self.assertEqual(counts[project_guard.Status.WARN], 0)
        self.assertEqual(counts[project_guard.Status.SKIP], 17)
        self.assertEqual(len(results), 45)

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
