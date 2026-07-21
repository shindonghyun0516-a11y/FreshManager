#!/usr/bin/env python3
"""FreshManager EG-3 offline Project Guard.

This module uses only the Python standard library. It never reads the real
``.env`` file, performs network requests, or writes to the official CSV/JSON.
"""

from __future__ import annotations

import ast
import contextlib
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Sequence
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from freshmanager.collector import METADATA_FIELDS as EG4_METADATA_FIELDS  # noqa: E402
from freshmanager.collector import Collector, HttpResponse  # noqa: E402
from freshmanager.config import ConfigError, load_api_key, mask_secret  # noqa: E402
from freshmanager import eg5 as eg5_cli  # noqa: E402
from freshmanager.http_adapter import BASE_URL, SeoulPopulationHttpClient  # noqa: E402
from freshmanager.offline import run as run_offline  # noqa: E402
from freshmanager.storage import FileStorage, StorageError  # noqa: E402

CSV_RELATIVE_PATH = Path("data/reference/seoul_121_places.csv")
JSON_RELATIVE_PATH = Path("data/samples/population_yeouido_sample.json")
SPEC_RELATIVE_PATH = Path("docs/testing/PROJECT_GUARD_SPEC.md")
EG6_AREA_PANEL_RELATIVE_PATH = Path("data/reference/eg6_area_panel.csv")
EG6_SPOT_MASTER_RELATIVE_PATH = Path("data/reference/eg6_spot_master.csv")
EG6_SDOT_LINKS_RELATIVE_PATH = Path("data/reference/eg6_sdot_links.csv")

EXPECTED_HEADERS = ["CATEGORY", "NO", "AREA_CD", "AREA_NM", "ENG_NM"]
EXPECTED_CATEGORIES = {
    "관광특구": 7,
    "고궁·문화유산": 5,
    "인구밀집지역": 48,
    "발달상권": 28,
    "공원": 33,
}
CURRENT_POPULATION_FIELDS = [
    "AREA_NM",
    "AREA_CD",
    "AREA_CONGEST_LVL",
    "AREA_CONGEST_MSG",
    "AREA_PPLTN_MIN",
    "AREA_PPLTN_MAX",
    "MALE_PPLTN_RATE",
    "FEMALE_PPLTN_RATE",
    "PPLTN_RATE_0",
    "PPLTN_RATE_10",
    "PPLTN_RATE_20",
    "PPLTN_RATE_30",
    "PPLTN_RATE_40",
    "PPLTN_RATE_50",
    "PPLTN_RATE_60",
    "PPLTN_RATE_70",
    "RESNT_PPLTN_RATE",
    "NON_RESNT_PPLTN_RATE",
    "REPLACE_YN",
    "PPLTN_TIME",
    "FCST_YN",
]
FORECAST_FIELDS = [
    "FCST_TIME",
    "FCST_CONGEST_LVL",
    "FCST_PPLTN_MIN",
    "FCST_PPLTN_MAX",
]
METADATA_FIELDS = list(EG4_METADATA_FIELDS)
EG4_FIXED_TIME = datetime(2026, 7, 20, 9, 10, 11, tzinfo=ZoneInfo("Asia/Seoul"))
EG4_DUMMY_KEY = "dummy-key-for-project-guard"
EG5_DUMMY_KEY = "dummy-key-for-eg5-project-guard"
EG5_APPROVED_AREA_CODES = ("POI019", "POI013", "POI014")
EG5_APPROVED_AREA_NAMES = {
    "POI019": "구로디지털단지역",
    "POI013": "가산디지털단지역",
    "POI014": "강남역",
}
EG6_PANEL_VERSION = "eg6a-v1"
EG6_PROPOSED_AREA_COUNT = 13
EG6_APPROVED_AREA_COUNT = 13
EG6_PENDING_SERVICE_AREAS: set[str] = set()
EG6_AREA_HEADERS = [
    "panel_version", "panel_order", "service_area_name", "area_code",
    "official_area_name", "area_mapping_type", "mapping_confidence",
    "sdot_group", "approved", "active", "decision_note",
]
EG6_SPOT_HEADERS = [
    "spot_id", "service_area_name", "spot_name", "latitude", "longitude",
    "coordinate_source", "representative_coordinate_type", "connected_area_code",
    "connected_area_name", "spot_type", "business_reason",
    "selling_suitability_status", "field_verified", "active",
]
EG6_SDOT_HEADERS = [
    "spot_id", "nearest_sdot_id", "nearest_sdot_distance_m", "coverage_class",
    "sensor_recent_active", "activity_reference_period", "mapping_confidence",
    "source_report",
]
EG6_MAPPING_TYPES = {
    "EXACT_AREA_MATCH", "RELATED_AREA_MATCH", "NO_SAFE_AREA_MATCH",
    "REPLACEMENT_REQUIRED",
}
EG6_COVERAGE_CLASSES = {"DIRECT_COVERAGE", "NEARBY_SUPPORT", "NO_NEARBY_SDOT"}
EG6_MAPPING_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "UNRESOLVED"}
EG6_SPOT_STATUSES = {
    "COORDINATE_VERIFIED", "BUSINESS_REVIEW_REQUIRED", "FIELD_VALIDATION_REQUIRED",
}
EG6_COORDINATE_TYPES = {"OFFICIAL_STATION_EXIT", "STATION_CENTER_PROXY"}
EG6_BOOLEAN_VALUES = {"true", "false"}
EG6_SEOUL_LATITUDE_RANGE = (37.41, 37.72)
EG6_SEOUL_LONGITUDE_RANGE = (126.73, 127.27)
DOCUMENT_PATHS = [
    Path("AGENTS.md"),
    Path("README.md"),
    Path("docs/rules/CODING_RULES.md"),
    Path("docs/testing/PROJECT_GUARD_SPEC.md"),
    Path("docs/testing/QUALITY_GATES.md"),
    Path("docs/testing/PROJECT_GUARD_REPORT_TEMPLATE.md"),
]
STANDARD_PROJECT_GUARD_COMMAND = "python3 scripts/project_guard_check.py"
EG3_STATUS_ROW = "| EG-3 | Project Guard 구현 및 자동 재검증 | 구현·로컬 검증 완료: PASS 28, SKIP 17 |"


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    name: str
    gate: str
    input_files: tuple[str, ...]
    status: Status
    evidence: str


@dataclass(frozen=True)
class CheckDefinition:
    check_id: str
    name: str
    gate: str
    runner_name: str | None = None
    skip_reason: str | None = None


@dataclass(frozen=True)
class CsvInspection:
    fieldnames: tuple[str, ...]
    rows: tuple[dict[str | None, str | list[str] | None], ...]


@dataclass(frozen=True)
class JsonInspection:
    document: object


@dataclass(frozen=True)
class ProjectGuardContext:
    root: Path
    csv_hash_before: str | None
    json_hash_before: str | None

    @property
    def csv_path(self) -> Path:
        return self.root / CSV_RELATIVE_PATH

    @property
    def json_path(self) -> Path:
        return self.root / JSON_RELATIVE_PATH


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_if_file(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def inspect_csv(path: Path) -> CsvInspection:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        rows = tuple(reader)
        fieldnames = tuple(reader.fieldnames or ())
    return CsvInspection(fieldnames=fieldnames, rows=rows)


def load_area_codes(path: Path) -> list[str]:
    inspection = inspect_csv(path)
    return [str(row.get("AREA_CD") or "").strip() for row in inspection.rows]


def inspect_json(path: Path) -> JsonInspection:
    with path.open("r", encoding="utf-8-sig") as source:
        return JsonInspection(document=json.load(source))


def make_result(
    check_id: str,
    status: Status,
    evidence: str,
    *input_files: str,
) -> CheckResult:
    definition = DEFINITION_BY_ID[check_id]
    return CheckResult(
        check_id=check_id,
        name=definition.name,
        gate=definition.gate,
        input_files=tuple(input_files),
        status=status,
        evidence=evidence,
    )


def passed(check_id: str, evidence: str, *input_files: str) -> CheckResult:
    return make_result(check_id, Status.PASS, evidence, *input_files)


def failed(check_id: str, evidence: str, *input_files: str) -> CheckResult:
    return make_result(check_id, Status.FAIL, evidence, *input_files)


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_markdown(text: str) -> list[str]:
    errors: list[str] = []
    in_fence = False
    previous_level = 0
    saw_h1 = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^(#{1,6})\s+\S", line)
        if not match:
            continue
        level = len(match.group(1))
        if not saw_h1:
            if level != 1:
                errors.append(f"첫 제목이 H1이 아님({line_number}행)")
            saw_h1 = True
        if previous_level and level > previous_level + 1:
            errors.append(f"제목 단계 건너뜀({line_number}행)")
        previous_level = level
    if in_fence:
        errors.append("닫히지 않은 코드 블록")
    if not saw_h1:
        errors.append("H1 제목 없음")
    return errors


def markdown_section(text: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, flags=re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^##\s+", text[match.end():], flags=re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.start():end]


def current_gate_status_conflicts(text: str) -> list[str]:
    section = markdown_section(text, "3. 전체 순서와 현재 상태")
    if not section:
        return ["현재 게이트 상태 절 누락"]

    table_status: dict[str, str] = {}
    for gate in ("EG-4", "EG-5", "EG-6"):
        match = re.search(
            rf"^\|\s*{re.escape(gate)}\s*\|\s*([^|\n]+)\|",
            section,
            flags=re.MULTILINE,
        )
        if match:
            table_status[gate] = match.group(1).strip()

    prose = "\n".join(
        line for line in section.splitlines() if not line.lstrip().startswith("|")
    )
    issues: list[str] = []
    eg4_status = table_status.get("EG-4", "")
    if "통과" in eg4_status and "미통과" not in eg4_status:
        eg4_stale = re.search(
            r"EG-4[^\n]*(?:미통과|통과\s*전|통과하지\s*않|아직[^\n]*진행하지)",
            prose,
        )
        if eg4_stale:
            issues.append("EG-4 통과 상태와 본문 미통과 표현 충돌")

    eg5_status = table_status.get("EG-5", "")
    if "통과" in eg5_status and "미통과" not in eg5_status:
        eg5_stale = re.search(
            r"EG-5[^\n]*(?:미통과|미구현|미진행|미실행|진입\s*전|통과\s*전|"
            r"완료되지\s*않|시작(?:하지|되지)\s*않|아직[^\n]*진행하지)",
            prose,
        )
        if eg5_stale:
            issues.append("EG-5 통과 상태와 본문 미완료 표현 충돌")

    eg6_status = table_status.get("EG-6", "")
    if "진행" in eg6_status and not any(value in eg6_status for value in ("미진행", "미구현")):
        eg6_stale = re.search(
            r"EG-6A?[^\n]*(?:미구현|미진행|진입\s*전|시작(?:하지|되지)\s*않|"
            r"아직[^\n]*진행하지)",
            prose,
        )
        if eg6_stale:
            issues.append("EG-6 진행 상태와 본문 미시작 표현 충돌")

    actual_not_run = "미실행" in eg5_status or re.search(
        r"EG-5[^\n]*(?:실제|실응답)[^\n]*미실행", prose
    )
    actual_completed = re.search(
        r"(?:EG-5|대표\s*3장소)[^\n]*(?:실제|실응답)[^\n]*(?:수집|호출|응답|검증)[^\n]*(?:완료|성공|확인)",
        prose,
    )
    if actual_not_run and actual_completed:
        issues.append("EG-5 실제 호출 미실행 상태와 실제 수집 완료 표현 충돌")
    return issues


def check_h001(context: ProjectGuardContext) -> CheckResult:
    missing = []
    empty = []
    for relative_path in DOCUMENT_PATHS:
        path = context.root / relative_path
        if not path.is_file():
            missing.append(relative_path.as_posix())
        elif path.stat().st_size == 0:
            empty.append(relative_path.as_posix())
    if missing or empty:
        return failed("H-001", f"누락={missing}, 빈 파일={empty}", *map(str, DOCUMENT_PATHS))
    return passed("H-001", "필수 문서 6개가 존재하고 비어 있지 않음", *map(str, DOCUMENT_PATHS))


def check_h002(context: ProjectGuardContext) -> CheckResult:
    errors = []
    for relative_path in DOCUMENT_PATHS:
        path = context.root / relative_path
        if not path.is_file():
            errors.append(f"{relative_path}: 파일 없음")
            continue
        for issue in check_markdown(read_text(path)):
            errors.append(f"{relative_path}: {issue}")
    if errors:
        return failed("H-002", "; ".join(errors), *map(str, DOCUMENT_PATHS))
    return passed("H-002", "필수 문서의 코드 블록과 제목 계층 정상", *map(str, DOCUMENT_PATHS))


def check_h003(context: ProjectGuardContext) -> CheckResult:
    required_text = {
        Path("AGENTS.md"): [
            "data/reference/seoul_121_places.csv",
            "EG-1 통과: PASS",
        ],
        Path("README.md"): [
            "data/reference/seoul_121_places.csv",
            "| EG-1 통과 | PASS |",
            "data/samples/population_yeouido_sample.json",
        ],
        Path("docs/rules/CODING_RULES.md"): [
            "data/reference/seoul_121_places.csv",
            "EG-1을 통과했다",
            "SEOUL_OPEN_API_KEY",
        ],
        Path("docs/testing/PROJECT_GUARD_SPEC.md"): [
            "data/reference/seoul_121_places.csv",
            "data/samples/population_yeouido_sample.json",
            "EG-1: 공식 CSV 정비",
        ],
        Path("docs/testing/QUALITY_GATES.md"): [
            "data/reference/seoul_121_places.csv",
            "data/samples/population_yeouido_sample.json",
            "EG-1 | 통과:",
        ],
        Path("docs/testing/PROJECT_GUARD_REPORT_TEMPLATE.md"): ["PROJECT_GUARD_SPEC.md"],
    }
    forbidden = [
        "헤더 제외 CSV 레코드 989개",
        "전 필드 공백 레코드 868개",
        "EG-1도 통과하지 않았다",
        "| EG-1 통과 | 미통과 |",
    ]
    issues = []
    texts: dict[Path, str] = {}
    for path, required in required_text.items():
        absolute = context.root / path
        if not absolute.is_file():
            issues.append(f"{path}: 파일 없음")
            continue
        text = read_text(absolute)
        texts[path] = text
        missing = [item for item in required if item not in text]
        if missing:
            issues.append(f"{path}: 승인 문자열 누락={missing}")
        present_forbidden = [item for item in forbidden if item in text]
        if present_forbidden:
            issues.append(f"{path}: 과거 상태 문구 잔존={present_forbidden}")

    for path in [Path("AGENTS.md"), Path("README.md"), Path("docs/rules/CODING_RULES.md"), SPEC_RELATIVE_PATH]:
        text = texts.get(path, "")
        missing_metadata = [field for field in METADATA_FIELDS if field not in text]
        if missing_metadata:
            issues.append(f"{path}: 최소 메타데이터 누락={missing_metadata}")

    expected_order = [f"EG-{number}" for number in range(9)]
    for path in [Path("AGENTS.md"), Path("README.md"), Path("docs/testing/QUALITY_GATES.md")]:
        text = texts.get(path, "")
        cursor = 0
        positions = []
        for item in expected_order:
            position = text.find(item, cursor)
            positions.append(position)
            if position >= 0:
                cursor = position + len(item)
        if any(position < 0 for position in positions):
            issues.append(f"{path}: EG-0~EG-8 순서 확인 실패")

    quality_path = Path("docs/testing/QUALITY_GATES.md")
    for issue in current_gate_status_conflicts(texts.get(quality_path, "")):
        issues.append(f"{quality_path}: {issue}")

    if issues:
        return failed("H-003", "; ".join(issues), *map(str, DOCUMENT_PATHS))
    return passed("H-003", "승인된 경로·EG 상태·메타데이터·게이트 순서 일치", *map(str, DOCUMENT_PATHS))


def check_h004(context: ProjectGuardContext) -> CheckResult:
    readme_path = context.root / "README.md"
    project_guard_path = context.root / "scripts/project_guard_check.py"
    if not readme_path.is_file():
        return failed("H-004", "README.md가 없음", "README.md")
    readme = read_text(readme_path)
    required = [
        "data/reference/seoul_121_places.csv",
        "data/samples/population_yeouido_sample.json",
        "| EG-1 통과 | PASS |",
        "H-301`~`H-304`",
    ]
    missing = [item for item in required if item not in readme]
    status_section = markdown_section(readme, "9. 단계적 구현 순서")
    execution_section = markdown_section(readme, "18. 현재 실행방법")
    current_state = "\n".join(
        [
            markdown_section(readme, "6. 현재 프로젝트 상태"),
            status_section,
            execution_section,
        ]
    )
    forbidden_patterns = {
        "EG-3 미구현": r"\|\s*EG-3\s*\|[^\n]*\|\s*미구현\s*\|",
        "Project Guard 코드 없음": r"Project Guard[^\n]*코드[^\n]*(?:없음|구현되지)",
        "Project Guard 파일 없음": r"Project Guard 파일 없음",
        "Project Guard 실행 불가": r"Project Guard 실행 불가",
    }
    stale = [label for label, pattern in forbidden_patterns.items() if re.search(pattern, current_state)]
    if not project_guard_path.is_file():
        missing.append("scripts/project_guard_check.py 일반 파일")
    if EG3_STATUS_ROW not in status_section:
        missing.append("README EG-3 구현·로컬 검증 완료 상태")
    if STANDARD_PROJECT_GUARD_COMMAND not in execution_section:
        missing.append("README 표준 Project Guard 실행 명령")
    actual_missing = [
        path.as_posix()
        for path in [CSV_RELATIVE_PATH, JSON_RELATIVE_PATH]
        if not (context.root / path).is_file()
    ]
    if missing or actual_missing or stale:
        return failed(
            "H-004",
            f"README·구현 누락={missing}, 실제 파일 누락={actual_missing}, 과거 상태={stale}",
            "README.md",
            "scripts/project_guard_check.py",
        )
    return passed(
        "H-004",
        "실행 파일·표준 명령·EG-3 구현 상태와 공식 데이터 경로 일치",
        "README.md",
        "scripts/project_guard_check.py",
    )


def check_h101(context: ProjectGuardContext) -> CheckResult:
    if not context.csv_path.is_file():
        return failed("H-101", "공식 CSV가 없거나 일반 파일이 아님", str(CSV_RELATIVE_PATH))
    return passed("H-101", "공식 CSV 일반 파일 존재", str(CSV_RELATIVE_PATH))


def check_h102(context: ProjectGuardContext) -> CheckResult:
    try:
        inspection = inspect_csv(context.csv_path)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        return failed("H-102", f"CSV 읽기 실패({type(error).__name__})", str(CSV_RELATIVE_PATH))
    bom = context.csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    return passed(
        "H-102",
        f"utf-8-sig/newline='' 읽기 성공, BOM={'있음' if bom else '없음(허용)'}, 헤더={len(inspection.fieldnames)}개",
        str(CSV_RELATIVE_PATH),
    )


def csv_or_failure(context: ProjectGuardContext, check_id: str) -> CsvInspection | CheckResult:
    try:
        return inspect_csv(context.csv_path)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        return failed(check_id, f"선행 CSV 읽기 실패({type(error).__name__})", str(CSV_RELATIVE_PATH))


def check_h103(context: ProjectGuardContext) -> CheckResult:
    inspected = csv_or_failure(context, "H-103")
    if isinstance(inspected, CheckResult):
        return inspected
    actual = list(inspected.fieldnames)
    if actual != EXPECTED_HEADERS:
        return failed("H-103", f"헤더 불일치: 실제={actual}", str(CSV_RELATIVE_PATH))
    return passed("H-103", f"정확한 5개 헤더와 순서 확인: {actual}", str(CSV_RELATIVE_PATH))


def check_h104(context: ProjectGuardContext) -> CheckResult:
    inspected = csv_or_failure(context, "H-104")
    if isinstance(inspected, CheckResult):
        return inspected
    count = len(inspected.rows)
    if count != 121:
        return failed("H-104", f"레코드 수={count}, 기대=121", str(CSV_RELATIVE_PATH))
    return passed("H-104", "헤더 제외 레코드 121개", str(CSV_RELATIVE_PATH))


def normalized_cell(row: dict[str | None, str | list[str] | None], key: str) -> str:
    value = row.get(key)
    return value.strip() if isinstance(value, str) else ""


def check_h105(context: ProjectGuardContext) -> CheckResult:
    inspected = csv_or_failure(context, "H-105")
    if isinstance(inspected, CheckResult):
        return inspected
    missing = [index for index, row in enumerate(inspected.rows, start=2) if not normalized_cell(row, "AREA_CD")]
    if missing:
        return failed("H-105", f"AREA_CD 결측 {len(missing)}건, 행={missing}", str(CSV_RELATIVE_PATH))
    return passed("H-105", "AREA_CD 결측 0건", str(CSV_RELATIVE_PATH))


def check_h106(context: ProjectGuardContext) -> CheckResult:
    inspected = csv_or_failure(context, "H-106")
    if isinstance(inspected, CheckResult):
        return inspected
    counts = Counter(normalized_cell(row, "AREA_CD") for row in inspected.rows)
    duplicates = sorted(code for code, count in counts.items() if code and count > 1)
    if duplicates:
        return failed("H-106", f"AREA_CD 중복={duplicates}", str(CSV_RELATIVE_PATH))
    return passed("H-106", "AREA_CD 중복 0건", str(CSV_RELATIVE_PATH))


def check_h107(context: ProjectGuardContext) -> CheckResult:
    inspected = csv_or_failure(context, "H-107")
    if isinstance(inspected, CheckResult):
        return inspected
    missing = [index for index, row in enumerate(inspected.rows, start=2) if not normalized_cell(row, "AREA_NM")]
    if missing:
        return failed("H-107", f"AREA_NM 결측 {len(missing)}건, 행={missing}", str(CSV_RELATIVE_PATH))
    return passed("H-107", "AREA_NM 결측 0건", str(CSV_RELATIVE_PATH))


def check_h108(context: ProjectGuardContext) -> CheckResult:
    inspected = csv_or_failure(context, "H-108")
    if isinstance(inspected, CheckResult):
        return inspected
    codes = [normalized_cell(row, "AREA_CD") for row in inspected.rows if normalized_cell(row, "AREA_NM") == "여의도"]
    if codes != ["POI072"]:
        return failed("H-108", f"여의도 AREA_CD={codes or '없음'}", str(CSV_RELATIVE_PATH))
    return passed("H-108", "여의도 AREA_CD=POI072", str(CSV_RELATIVE_PATH))


def qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def find_area_code_generation(source: str) -> list[int]:
    tree = ast.parse(source)
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            has_poi = any(isinstance(value, ast.Constant) and "POI" in str(value.value) for value in node.values)
            has_dynamic = any(isinstance(value, ast.FormattedValue) for value in node.values)
            if has_poi and has_dynamic:
                lines.append(node.lineno)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            constants = [child for child in ast.walk(node) if isinstance(child, ast.Constant)]
            if any("POI" in str(item.value) for item in constants) and not all(
                isinstance(side, ast.Constant) for side in (node.left, node.right)
            ):
                lines.append(node.lineno)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            if isinstance(node.func.value, ast.Constant) and "POI" in str(node.func.value.value):
                lines.append(node.lineno)
    return sorted(set(lines))


def check_h109(context: ProjectGuardContext) -> CheckResult:
    inspected = csv_or_failure(context, "H-109")
    if isinstance(inspected, CheckResult):
        return inspected
    source_path = context.root / "scripts/project_guard_check.py"
    source = read_text(source_path)
    generated_lines = find_area_code_generation(source)
    expected = [normalized_cell(row, "AREA_CD") for row in inspected.rows]
    actual = load_area_codes(context.csv_path)
    if generated_lines or actual != expected:
        return failed(
            "H-109",
            f"코드 생성 의심 행={generated_lines}, CSV 코드 보존={actual == expected}",
            str(CSV_RELATIVE_PATH),
            "scripts/project_guard_check.py",
        )
    return passed("H-109", "대상 코드는 CSV AREA_CD에서 순서대로 읽으며 자동생성 없음", str(CSV_RELATIVE_PATH), "scripts/project_guard_check.py")


def check_h110(context: ProjectGuardContext) -> CheckResult:
    source_path = context.root / "scripts/project_guard_check.py"
    source = read_text(source_path)
    tree = ast.parse(source)
    imports = set()
    has_dict_reader = False
    has_read_contract = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            name = qualified_name(node.func)
            if name == "csv.DictReader":
                has_dict_reader = True
            if name.endswith(".open"):
                keywords = {item.arg: item.value for item in node.keywords if item.arg}
                encoding = keywords.get("encoding")
                newline = keywords.get("newline")
                if (
                    isinstance(encoding, ast.Constant)
                    and encoding.value == "utf-8-sig"
                    and isinstance(newline, ast.Constant)
                    and newline.value == ""
                ):
                    has_read_contract = True
    forbidden = sorted(name for name in imports if name.split(".")[0] in {"openpyxl", "pandas"})
    dependency_hits = []
    for relative_name in ["requirements.txt", "pyproject.toml", "Pipfile"]:
        path = context.root / relative_name
        if path.is_file() and re.search(r"(?i)openpyxl|pandas", read_text(path)):
            dependency_hits.append(relative_name)
    if "csv" not in imports or not has_dict_reader or not has_read_contract or forbidden or dependency_hits:
        return failed(
            "H-110",
            f"csv import={('csv' in imports)}, DictReader={has_dict_reader}, utf-8-sig/newline={has_read_contract}, 금지 import={forbidden}, 의존성={dependency_hits}",
            "scripts/project_guard_check.py",
        )
    return passed("H-110", "표준 csv.DictReader와 utf-8-sig/newline='' 사용, openpyxl·pandas 없음", "scripts/project_guard_check.py")


def check_h111(context: ProjectGuardContext) -> CheckResult:
    if not context.csv_path.is_file():
        return failed("H-111", "공식 CSV가 없어 불변성 검사 불가", str(CSV_RELATIVE_PATH))
    official_before = sha256_file(context.csv_path)
    with tempfile.TemporaryDirectory(prefix="freshmanager-eg3-") as temporary:
        copied = Path(temporary) / context.csv_path.name
        shutil.copy2(context.csv_path, copied)
        copy_before = sha256_file(copied)
        inspect_csv(copied)
        copy_after = sha256_file(copied)
    official_after = sha256_file(context.csv_path)
    if official_before != official_after or copy_before != copy_after or official_before != context.csv_hash_before:
        return failed(
            "H-111",
            "공식 CSV 또는 임시 복사본의 실행 전후 SHA-256 불일치",
            str(CSV_RELATIVE_PATH),
        )
    return passed("H-111", f"공식 CSV·임시 복사본 SHA-256 불변({official_after})", str(CSV_RELATIVE_PATH))


def check_h112(context: ProjectGuardContext) -> CheckResult:
    inspected = csv_or_failure(context, "H-112")
    if isinstance(inspected, CheckResult):
        return inspected
    categories = [normalized_cell(row, "CATEGORY") for row in inspected.rows]
    counts = Counter(categories)
    missing = counts.get("", 0)
    unexpected = sorted(category for category in counts if category not in EXPECTED_CATEGORIES and category)
    actual = {category: counts.get(category, 0) for category in EXPECTED_CATEGORIES}
    if missing or unexpected or actual != EXPECTED_CATEGORIES or sum(actual.values()) != 121:
        return failed(
            "H-112",
            f"결측={missing}, 허용 외={unexpected}, 분류별={actual}, 합계={sum(actual.values())}",
            str(CSV_RELATIVE_PATH),
        )
    return passed("H-112", f"분류별={actual}, 합계=121", str(CSV_RELATIVE_PATH))


def run_git(root: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def check_h201(context: ProjectGuardContext) -> CheckResult:
    gitignore = context.root / ".gitignore"
    if not gitignore.is_file():
        return failed("H-201", ".gitignore 없음", ".gitignore")
    ignored = run_git(context.root, ["check-ignore", "-q", "--", ".env"])
    tracked = run_git(context.root, ["ls-files", "--cached", "--", ".env"])
    if ignored.returncode != 0 or tracked.returncode != 0 or tracked.stdout.strip():
        return failed(
            "H-201",
            f".env 제외={ignored.returncode == 0}, Git 추적={bool(tracked.stdout.strip())}",
            ".gitignore",
        )
    return passed("H-201", ".env는 Git에서 제외되고 추적되지 않음(내용 미열람)", ".gitignore")


SAFE_ENV_VALUES = {"your_api_key_here", "********"}


def check_h202(context: ProjectGuardContext) -> CheckResult:
    path = context.root / ".env.example"
    if not path.is_file():
        return failed("H-202", ".env.example 없음", ".env.example")
    assignments = []
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            return failed("H-202", "등호 없는 설정 행 존재", ".env.example")
        key, value = stripped.split("=", 1)
        assignments.append((key.strip(), value.strip()))
    expected = [("SEOUL_OPEN_API_KEY", "your_api_key_here")]
    if assignments != expected:
        return failed("H-202", "공식 환경변수명 또는 안전한 placeholder 불일치", ".env.example")
    return passed("H-202", "SEOUL_OPEN_API_KEY에 안전한 placeholder만 포함", ".env.example")


SECURITY_SUFFIXES = {".md", ".py", ".json", ".csv", ".txt", ".log", ".example"}
SKIP_DIRECTORY_NAMES = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
PROTECTED_WORK_LOG_DIRECTORY = "work log"
PROTECTED_GIT_BASE_ENV = "PROJECT_GUARD_BASE_SHA"
PROTECTED_GIT_HEAD_ENV = "PROJECT_GUARD_HEAD_SHA"
PROTECTED_VIRTUAL_PROBE = f"{PROTECTED_WORK_LOG_DIRECTORY}/.project-guard-probe"
UNRELATED_IGNORE_PROBES = (
    "project notes/.project-guard-probe",
    f"{PROTECTED_WORK_LOG_DIRECTORY}s/.project-guard-probe",
    f"nested/{PROTECTED_WORK_LOG_DIRECTORY}/.project-guard-probe",
    "audit log/.project-guard-probe",
    "src/.project-guard-probe",
)
FULL_COMMIT_SHA = re.compile(r"[0-9a-fA-F]{40}")
ENV_ASSIGNMENT = re.compile(r"SEOUL_OPEN_API_KEY\s*=\s*([^\s`'\"<>]+)")
JSON_SECRET_FIELD = re.compile(
    r"[\"'](?:SEOUL_OPEN_API_KEY|API_KEY|api_key|token|authorization)[\"']\s*:\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
SEOUL_KEY_SEGMENT = re.compile(r"openapi\.seoul\.go\.kr(?::\d+)?/([^/]+)/(?:(?:json)|(?:xml))(?:/|$)", re.IGNORECASE)
SAFE_URL_SEGMENTS = {"********", "{API_KEY}", "your_api_key_here", "..."}


def is_safe_url_segment(value: str) -> bool:
    if value in SAFE_URL_SEGMENTS:
        return True
    if value.startswith("{") and value.endswith("}"):
        return True
    return any("가" <= character <= "힣" for character in value)


def prune_traversal_directories(root: Path, current: Path, directory_names: list[str]) -> None:
    """Prevent traversal into caches and the exact protected top-level work log."""

    directory_names[:] = [
        name
        for name in directory_names
        if name not in SKIP_DIRECTORY_NAMES
        and not (current == root and name == PROTECTED_WORK_LOG_DIRECTORY)
    ]


def iter_security_files(root: Path) -> Iterable[Path]:
    for current_root, directory_names, file_names in os.walk(root):
        current = Path(current_root)
        prune_traversal_directories(root, current, directory_names)
        relative_parts = current.relative_to(root).parts if current != root else ()
        if relative_parts[:2] in {("data", "raw"), ("data", "processed"), ("data", "quality")}:
            directory_names[:] = []
            continue
        for file_name in file_names:
            if file_name == ".env" or (file_name.startswith(".env.") and file_name != ".env.example"):
                continue
            path = current / file_name
            if path.suffix.lower() in SECURITY_SUFFIXES or file_name in {".gitignore", ".env.example"}:
                yield path


def sensitive_findings(path: Path, root: Path) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []
    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in ENV_ASSIGNMENT.finditer(line):
            if match.group(1) not in SAFE_ENV_VALUES:
                findings.append((line_number, "환경변수 실제값 의심"))
        for match in JSON_SECRET_FIELD.finditer(line):
            if match.group(1) not in SAFE_ENV_VALUES:
                findings.append((line_number, "JSON Secret 필드 실제값 의심"))
        for url_match in URL_PATTERN.finditer(line):
            url = url_match.group(0)
            key_match = SEOUL_KEY_SEGMENT.search(url)
            if key_match and not is_safe_url_segment(key_match.group(1)):
                findings.append((line_number, "인증키 포함 실행 URL 의심"))
    return findings


def check_h203(context: ProjectGuardContext) -> CheckResult:
    findings = []
    for path in iter_security_files(context.root):
        for line_number, finding_type in sensitive_findings(path, context.root):
            findings.append(f"{relative(path, context.root)}:{line_number}:{finding_type}")
    if findings:
        return failed("H-203", "; ".join(findings), "저장소 문서·코드·테스트·샘플·로그")
    return passed("H-203", "실제 키·인증키 포함 실행 URL 없음(.env 내용 미열람)", "저장소 문서·코드·테스트·샘플·로그")


def run_git_bytes(root: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[bytes] | None:
    """Run Git without decoding or exposing path-bearing output."""

    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return None


def git_nul_count(result: subprocess.CompletedProcess[bytes] | None) -> int | None:
    if result is None or result.returncode != 0:
        return None
    return sum(bool(record) for record in result.stdout.split(b"\0"))


def protected_ref_count(root: Path, commit_sha: str) -> int | None:
    return git_nul_count(
        run_git_bytes(
            root,
            ["ls-tree", "-r", "--name-only", "-z", commit_sha, "--", PROTECTED_WORK_LOG_DIRECTORY],
        )
    )


def protected_diff_count(
    root: Path,
    base_sha: str,
    head_sha: str,
    diff_filter: str | None = None,
) -> int | None:
    arguments = ["diff", "--name-only", "-z"]
    if diff_filter is not None:
        arguments.append(f"--diff-filter={diff_filter}")
    arguments.extend([base_sha, head_sha, "--", PROTECTED_WORK_LOG_DIRECTORY])
    return git_nul_count(run_git_bytes(root, arguments))


def has_exact_protected_ignore_rule(root: Path) -> bool:
    try:
        lines = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    active_rules = [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return active_rules.count(f"/{PROTECTED_WORK_LOG_DIRECTORY}/") == 1


def ignore_probe_matches(root: Path, probe: str) -> bool | None:
    result = run_git_bytes(
        root,
        ["check-ignore", "-q", "--no-index", "--", probe],
    )
    if result is None or result.returncode not in (0, 1):
        return None
    return result.returncode == 0


def check_h206(context: ProjectGuardContext) -> CheckResult:
    """Validate the retired top-level work-log path without traversing it."""

    protected_root = context.root / PROTECTED_WORK_LOG_DIRECTORY
    if os.path.lexists(protected_root):
        return failed(
            "H-206",
            "보호 경로가 재생성됨(내부 정보 미열람)",
            ".gitignore",
            "Git 메타데이터",
        )
    if not has_exact_protected_ignore_rule(context.root):
        return failed("H-206", "보호 경로의 정확한 ignore 규칙 불일치", ".gitignore", "Git 메타데이터")

    repository = run_git_bytes(context.root, ["rev-parse", "--is-inside-work-tree"])
    if repository is None or repository.returncode != 0 or repository.stdout.strip() != b"true":
        return failed("H-206", "안전한 Git 비교 불가", ".gitignore", "Git 메타데이터")

    protected_probe_ignored = ignore_probe_matches(context.root, PROTECTED_VIRTUAL_PROBE)
    unrelated_probe_results = tuple(
        ignore_probe_matches(context.root, probe)
        for probe in UNRELATED_IGNORE_PROBES
    )
    if protected_probe_ignored is not True or any(
        result is not False for result in unrelated_probe_results
    ):
        return failed("H-206", "보호 경로 전용 ignore 규칙 불일치", ".gitignore", "Git 메타데이터")

    tracked_count = git_nul_count(
        run_git_bytes(context.root, ["ls-files", "-z", "--", PROTECTED_WORK_LOG_DIRECTORY])
    )
    untracked_count = git_nul_count(
        run_git_bytes(
            context.root,
            ["ls-files", "--others", "-z", "--", PROTECTED_WORK_LOG_DIRECTORY],
        )
    )
    staged_count = git_nul_count(
        run_git_bytes(
            context.root,
            ["diff", "--cached", "--name-only", "-z", "--", PROTECTED_WORK_LOG_DIRECTORY],
        )
    )
    worktree_count = git_nul_count(
        run_git_bytes(context.root, ["diff", "--name-only", "-z", "--", PROTECTED_WORK_LOG_DIRECTORY])
    )
    deleted_count = git_nul_count(
        run_git_bytes(
            context.root,
            ["diff", "--diff-filter=D", "--name-only", "-z", "--", PROTECTED_WORK_LOG_DIRECTORY],
        )
    )
    missing_count = git_nul_count(
        run_git_bytes(
            context.root,
            ["ls-files", "--deleted", "-z", "--", PROTECTED_WORK_LOG_DIRECTORY],
        )
    )
    counts = (
        tracked_count,
        untracked_count,
        staged_count,
        worktree_count,
        deleted_count,
        missing_count,
    )
    if any(value is None for value in counts):
        return failed("H-206", "안전한 Git 비교 불가", ".gitignore", "Git 메타데이터")

    assert tracked_count is not None
    assert untracked_count is not None
    assert staged_count is not None
    assert worktree_count is not None
    assert deleted_count is not None
    assert missing_count is not None

    if untracked_count != 0:
        return failed("H-206", "보호 경로에 미추적 항목이 존재함(개수만 확인)", ".gitignore", "Git 메타데이터")
    if staged_count != 0:
        return failed("H-206", "보호 경로가 Stage에 포함됨(개수만 확인)", ".gitignore", "Git 메타데이터")

    if tracked_count == 0 and worktree_count == 0:
        local_state = "normal"
    elif (
        tracked_count > 0
        and missing_count == tracked_count
        and worktree_count == tracked_count
        and deleted_count == tracked_count
    ):
        local_state = "approved_removal_transition"
    else:
        return failed("H-206", "보호 경로 Git 상태가 허용 계약과 불일치", ".gitignore", "Git 메타데이터")

    base_sha = os.environ.get(PROTECTED_GIT_BASE_ENV, "").strip()
    head_sha = os.environ.get(PROTECTED_GIT_HEAD_ENV, "").strip()
    comparison_state = "local_only"
    if base_sha or head_sha:
        if not FULL_COMMIT_SHA.fullmatch(base_sha) or not FULL_COMMIT_SHA.fullmatch(head_sha):
            return failed("H-206", "안전한 Base·Head 비교 불가", ".gitignore", "Git 메타데이터")
        base_object = run_git_bytes(context.root, ["cat-file", "-e", f"{base_sha}^{{commit}}"])
        head_object = run_git_bytes(context.root, ["cat-file", "-e", f"{head_sha}^{{commit}}"])
        if (
            base_object is None
            or base_object.returncode != 0
            or head_object is None
            or head_object.returncode != 0
        ):
            return failed("H-206", "안전한 Base·Head 비교 불가", ".gitignore", "Git 메타데이터")
        base_count = protected_ref_count(context.root, base_sha)
        head_count = protected_ref_count(context.root, head_sha)
        comparison_count = protected_diff_count(context.root, base_sha, head_sha)
        comparison_deleted_count = protected_diff_count(context.root, base_sha, head_sha, "D")
        if None in (base_count, head_count, comparison_count, comparison_deleted_count):
            return failed("H-206", "안전한 Base·Head 비교 불가", ".gitignore", "Git 메타데이터")
        if comparison_count == 0 and head_count == 0:
            comparison_state = "clean"
        elif (
            base_count is not None
            and head_count is not None
            and comparison_count is not None
            and comparison_deleted_count is not None
            and base_count > 0
            and head_count == 0
            and comparison_count == base_count
            and comparison_deleted_count == comparison_count
        ):
            comparison_state = "approved_deletion_only"
        else:
            return failed("H-206", "대상 Commit·PR에 금지된 보호 경로 변경이 포함됨", ".gitignore", "Git 메타데이터")

    return passed(
        "H-206",
        f"보호 경로 안전성 확인(state={local_state}, comparison={comparison_state}, exposed_names=0)",
        ".gitignore",
        "Git 메타데이터",
    )


class GuardSampleClient:
    def __init__(self, payload: bytes, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.calls: list[str] = []

    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        del api_key, timeout_seconds
        self.calls.append(area_code)
        return HttpResponse(self.status_code, self.payload)


class GuardTimeoutClient:
    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        del area_code, api_key, timeout_seconds
        raise TimeoutError


class GuardEg5Response:
    def __init__(self, payload: bytes) -> None:
        self.status = 200
        self.payload = payload
        self.offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.payload) - self.offset
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    def close(self) -> None:
        return None


class GuardEg5Transport:
    def __init__(self, failures: set[str] | None = None) -> None:
        self.failures = failures or set()
        self.calls: list[str] = []

    def open(self, request: object, timeout_seconds: float) -> GuardEg5Response:
        del timeout_seconds
        selector = str(getattr(request, "selector", ""))
        area_code = selector.rsplit("/", 1)[-1]
        self.calls.append(area_code)
        if area_code in self.failures:
            raise TimeoutError("synthetic timeout detail")
        return GuardEg5Response(synthetic_eg5_payload(area_code))


@dataclass(frozen=True)
class Eg5GuardExecution:
    exit_code: int
    output: str
    calls: tuple[str, ...]
    raw_area_codes: tuple[str, ...]
    metadata: tuple[dict[str, object], ...]
    stage_only: bool


def synthetic_eg5_payload(area_code: str) -> bytes:
    area_name = EG5_APPROVED_AREA_NAMES[area_code]
    current = {field: "1" for field in CURRENT_POPULATION_FIELDS}
    current.update(
        {
            "AREA_NM": area_name,
            "AREA_CD": area_code,
            "AREA_CONGEST_LVL": "보통",
            "AREA_CONGEST_MSG": "Project Guard 합성 응답",
            "AREA_PPLTN_MIN": "1000",
            "AREA_PPLTN_MAX": "1200",
            "PPLTN_TIME": "2026-07-21 10:00",
            "FCST_YN": "Y",
            "FCST_PPLTN": [
                {
                    "FCST_TIME": "2026-07-21 11:00",
                    "FCST_CONGEST_LVL": "보통",
                    "FCST_PPLTN_MIN": "1100",
                    "FCST_PPLTN_MAX": "1300",
                }
            ],
        }
    )
    document = {
        "SeoulRtd.citydata_ppltn": [current],
        "RESULT": {
            "RESULT.CODE": "INFO-000",
            "RESULT.MESSAGE": "정상 처리되었습니다",
        },
    }
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


def run_eg5_guard(context: ProjectGuardContext, failures: set[str] | None = None) -> Eg5GuardExecution:
    with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-guard-") as temporary:
        root = Path(temporary)
        env_path = root / "dummy.env"
        env_name = "SEOUL_OPEN" + "_API_KEY"
        env_path.write_text(f"{env_name}={EG5_DUMMY_KEY}\n", encoding="utf-8")
        output_root = root / "output"
        transport = GuardEg5Transport(failures)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
            exit_code = eg5_cli.run(
                [
                    "--env-file",
                    str(env_path),
                    "--output-root",
                    str(output_root),
                    "--execute-live",
                ],
                transport_factory=lambda: transport,
                official_csv_path=context.csv_path,
            )
        raw_files = sorted((output_root / eg5_cli.RAW_OUTPUT_PATH).rglob("*.json"))
        metadata_files = sorted(
            (output_root / eg5_cli.METADATA_OUTPUT_PATH).rglob("*.metadata.json")
        )
        created_files = [path for path in output_root.rglob("*") if path.is_file()]
        stage_only = all(
            path.relative_to(output_root).parts[:2] == eg5_cli.STAGE_PATH.parts
            for path in created_files
        )
        metadata = tuple(
            json.loads(path.read_text(encoding="utf-8")) for path in metadata_files
        )
        raw_area_codes = tuple(path.name.split("_", 1)[0] for path in raw_files)
        return Eg5GuardExecution(
            exit_code=exit_code,
            output=stdout.getvalue(),
            calls=tuple(transport.calls),
            raw_area_codes=raw_area_codes,
            metadata=metadata,
            stage_only=stage_only,
        )


def eg5_summary(output: str) -> dict[str, str]:
    lines = output.splitlines()
    try:
        start = lines.index("EG5_COLLECTION_SUMMARY") + 1
    except ValueError:
        return {}
    return dict(line.split("=", 1) for line in lines[start:] if "=" in line)


class GuardConnectionFailureTransport:
    def open(self, request: object, timeout_seconds: float) -> object:
        del request, timeout_seconds
        raise OSError("unsafe transport detail")


class GuardRawFailStorage(FileStorage):
    def save_raw(self, area_code: str, requested_at: datetime, request_id: str, payload: bytes) -> Path:
        del area_code, requested_at, request_id, payload
        raise StorageError("storage_error")


class GuardMetadataFailStorage(FileStorage):
    def __init__(self, raw_root: Path, metadata_root: Path) -> None:
        super().__init__(raw_root, metadata_root)
        self.metadata_calls = 0

    def save_metadata(self, requested_at: datetime, request_id: str, metadata: dict[str, object]) -> Path:
        self.metadata_calls += 1
        del requested_at, request_id, metadata
        raise StorageError("storage_error")


def guard_collector(
    context: ProjectGuardContext,
    output_root: Path,
    client: GuardSampleClient,
    request_id_factory: Callable[[], uuid.UUID],
) -> Collector:
    return Collector(
        context.csv_path,
        client,
        FileStorage(output_root / "raw", output_root / "metadata"),
        clock=lambda: EG4_FIXED_TIME,
        request_id_factory=request_id_factory,
    )


def check_h204(context: ProjectGuardContext) -> CheckResult:
    del context
    env_name = "SEOUL_OPEN" + "_API_KEY"
    with tempfile.TemporaryDirectory(prefix="freshmanager-h204-") as temporary:
        root = Path(temporary)
        valid = root / "valid.env"
        valid.write_text(f"# comment\n\n {env_name} = {EG4_DUMMY_KEY}=suffix \n", encoding="utf-8")
        if load_api_key(valid) != f"{EG4_DUMMY_KEY}=suffix":
            return failed("H-204", "최초 등호 분리·공백 제거 결과 불일치", "freshmanager/config.py", "임시 .env")
        invalid_paths = [root / "missing.env", root / "empty.env"]
        invalid_paths[1].write_text(f"{env_name}=   \n", encoding="utf-8")
        for path in invalid_paths:
            try:
                load_api_key(path)
            except ConfigError:
                continue
            return failed("H-204", "누락·빈 설정을 config_error로 처리하지 않음", "freshmanager/config.py", "임시 .env")
    return passed("H-204", "임시 .env에서 주석·공백·최초 등호 처리 및 누락·빈 값 config_error 확인", "freshmanager/config.py", "임시 .env")


def check_h205(context: ProjectGuardContext) -> CheckResult:
    del context
    source = f"request failed /{EG4_DUMMY_KEY}/"
    masked = mask_secret(source, EG4_DUMMY_KEY)
    if EG4_DUMMY_KEY in masked or "********" not in masked:
        return failed("H-205", "Dummy Key 마스킹 실패", "freshmanager/config.py")
    try:
        raise ConfigError("config_error: 인증정보 누락")
    except ConfigError as error:
        if EG4_DUMMY_KEY in str(error):
            return failed("H-205", "오류 메시지에 Dummy Key 노출", "freshmanager/config.py")
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            SeoulPopulationHttpClient(GuardConnectionFailureTransport()).fetch_population(
                "POI072",
                EG4_DUMMY_KEY,
                10.0,
            )
    except OSError as error:
        rendered = output.getvalue() + str(error)
        if EG4_DUMMY_KEY in rendered or BASE_URL in rendered:
            return failed("H-205", "Adapter 오류에 Dummy Key 또는 인증 URL 노출", "freshmanager/http_adapter.py")
    else:
        return failed("H-205", "Adapter 연결 오류가 안전한 OSError로 변환되지 않음", "freshmanager/http_adapter.py")
    return passed(
        "H-205",
        "Dummy Key와 인증 URL이 출력·예외에서 비노출되고 마스킹됨",
        "freshmanager/config.py",
        "freshmanager/http_adapter.py",
    )


def json_or_failure(context: ProjectGuardContext, check_id: str) -> JsonInspection | CheckResult:
    try:
        return inspect_json(context.json_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return failed(check_id, f"샘플 JSON 읽기 실패({type(error).__name__})", str(JSON_RELATIVE_PATH))


def check_h301(context: ProjectGuardContext) -> CheckResult:
    if not context.json_path.is_file():
        return failed("H-301", "공식 샘플 JSON 없음", str(JSON_RELATIVE_PATH))
    inspected = json_or_failure(context, "H-301")
    if isinstance(inspected, CheckResult):
        return inspected
    return passed("H-301", f"JSON 문법 정상, SHA-256={sha256_file(context.json_path)}", str(JSON_RELATIVE_PATH))


def population_items(document: object) -> list[object] | None:
    if not isinstance(document, dict):
        return None
    value = document.get("SeoulRtd.citydata_ppltn")
    return value if isinstance(value, list) else None


def check_h302(context: ProjectGuardContext) -> CheckResult:
    inspected = json_or_failure(context, "H-302")
    if isinstance(inspected, CheckResult):
        return inspected
    document = inspected.document
    items = population_items(document)
    issues = []
    if items is None:
        issues.append("SeoulRtd.citydata_ppltn이 배열이 아님")
    elif len(items) != 1:
        issues.append(f"장소 객체 수={len(items)}, 기대=1")
    item = items[0] if items and isinstance(items[0], dict) else None
    if item is None:
        issues.append("첫 장소 객체 없음")
    else:
        if item.get("AREA_NM") != "여의도":
            issues.append(f"AREA_NM={item.get('AREA_NM')!r}")
        if item.get("AREA_CD") != "POI072":
            issues.append(f"AREA_CD={item.get('AREA_CD')!r}")
        missing = [field for field in CURRENT_POPULATION_FIELDS if field not in item]
        if missing:
            issues.append(f"현재 인구 필드 누락={missing}")
        if "FEMALE_PPLTN_RATE" not in item:
            issues.append("FEMALE_PPLTN_RATE 누락")
    result = document.get("RESULT") if isinstance(document, dict) else None
    if not isinstance(result, dict):
        issues.append("RESULT 객체 없음")
    else:
        missing_result = [field for field in ["RESULT.CODE", "RESULT.MESSAGE"] if field not in result]
        if missing_result:
            issues.append(f"RESULT 필드 누락={missing_result}")
    if issues:
        return failed("H-302", "; ".join(issues), str(JSON_RELATIVE_PATH))
    return passed("H-302", "여의도/POI072, 장소 객체 1개, 현재 인구·RESULT 필드 확인", str(JSON_RELATIVE_PATH))


def parse_integer(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer field")
    return int(str(value).strip())


def check_h303(context: ProjectGuardContext) -> CheckResult:
    inspected = json_or_failure(context, "H-303")
    if isinstance(inspected, CheckResult):
        return inspected
    items = population_items(inspected.document)
    if not items or not isinstance(items[0], dict):
        return failed("H-303", "현재 인구 장소 객체 없음", str(JSON_RELATIVE_PATH))
    item = items[0]
    if item.get("FCST_YN") != "Y":
        return passed("H-303", f"FCST_YN={item.get('FCST_YN')!r}: 예측 배열 필수조건 비적용", str(JSON_RELATIVE_PATH))
    forecasts = item.get("FCST_PPLTN")
    if not isinstance(forecasts, list) or not forecasts:
        return failed("H-303", "FCST_YN=Y이나 FCST_PPLTN이 비어 있지 않은 배열이 아님", str(JSON_RELATIVE_PATH))
    issues = []
    for index, forecast in enumerate(forecasts):
        if not isinstance(forecast, dict):
            issues.append(f"예측[{index}] 객체 아님")
            continue
        missing = [field for field in FORECAST_FIELDS if field not in forecast]
        if missing:
            issues.append(f"예측[{index}] 필드 누락={missing}")
            continue
        try:
            minimum = parse_integer(forecast["FCST_PPLTN_MIN"])
            maximum = parse_integer(forecast["FCST_PPLTN_MAX"])
        except (TypeError, ValueError):
            issues.append(f"예측[{index}] 최소·최대 정수 해석 실패")
            continue
        if minimum > maximum:
            issues.append(f"예측[{index}] 최소값이 최대값보다 큼")
    if issues:
        return failed("H-303", "; ".join(issues), str(JSON_RELATIVE_PATH))
    return passed("H-303", f"예측 객체 {len(forecasts)}개, 필수필드·정수 범위 정상(개수는 정보성)", str(JSON_RELATIVE_PATH))


def check_h304(context: ProjectGuardContext) -> CheckResult:
    path = context.json_path
    findings = sensitive_findings(path, context.root)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        return failed("H-304", f"샘플 읽기 실패({type(error).__name__})", str(JSON_RELATIVE_PATH))
    for line_number, line in enumerate(text.splitlines(), start=1):
        if "http://" in line.lower() or "https://" in line.lower():
            findings.append((line_number, "샘플 JSON URL 포함"))
    if findings:
        safe = [f"{relative(path, context.root)}:{line}:{kind}" for line, kind in findings]
        return failed("H-304", "; ".join(safe), str(JSON_RELATIVE_PATH))
    return passed("H-304", "샘플 JSON에 실제 키·URL 없음", str(JSON_RELATIVE_PATH))


APPROVED_NETWORK_ADAPTER_PATH = Path("freshmanager/http_adapter.py")
FORBIDDEN_NETWORK_MODULES = {"requests", "urllib.request", "http.client"}
FORBIDDEN_NETWORK_CALLS = {
    "requests.get",
    "requests.post",
    "requests.request",
    "urllib.request.urlopen",
    "http.client.HTTPConnection",
    "http.client.HTTPSConnection",
    "socket.create_connection",
}


class NetworkCodeVisitor(ast.NodeVisitor):
    def __init__(self, *, approved_adapter: bool) -> None:
        self.approved_adapter = approved_adapter
        self.findings: list[str] = []
        self.scope: list[tuple[str, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(("class", node.name))
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(("function", node.name))
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in FORBIDDEN_NETWORK_MODULES and not self.approved_adapter:
                self.findings.append(f"{node.lineno}행:network import {alias.name}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module in FORBIDDEN_NETWORK_MODULES and not self.approved_adapter:
            self.findings.append(f"{node.lineno}행:network import {node.module}")

    def visit_Call(self, node: ast.Call) -> None:
        name = qualified_name(node.func)
        if self.approved_adapter and not self.scope:
            self.findings.append(f"{node.lineno}행:adapter module-level call {name or '<unknown>'}")
        elif name in FORBIDDEN_NETWORK_CALLS:
            allowed_scope = self.approved_adapter and self.scope[-2:] == [
                ("class", "UrllibTransport"),
                ("function", "open"),
            ]
            if not allowed_scope:
                self.findings.append(f"{node.lineno}행:network call {name}")
        self.generic_visit(node)


def network_code_findings(path: Path, root: Path) -> list[str]:
    try:
        tree = ast.parse(read_text(path), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    visitor = NetworkCodeVisitor(approved_adapter=path.relative_to(root) == APPROVED_NETWORK_ADAPTER_PATH)
    visitor.visit(tree)
    return visitor.findings


def project_python_files(root: Path) -> list[Path]:
    files = []
    for current_root, directory_names, file_names in os.walk(root):
        current = Path(current_root)
        prune_traversal_directories(root, current, directory_names)
        files.extend(current / name for name in file_names if Path(name).suffix == ".py")
    return sorted(files)


def check_h305(context: ProjectGuardContext) -> CheckResult:
    findings = []
    for path in project_python_files(context.root):
        for finding in network_code_findings(path, context.root):
            findings.append(f"{relative(path, context.root)}:{finding}")
    if findings:
        return failed("H-305", "; ".join(findings), "freshmanager/http_adapter.py", "scripts/", "tests/")
    return passed(
        "H-305",
        "승인 Adapter 외 네트워크 코드와 Adapter module-level 실행 없음",
        "freshmanager/http_adapter.py",
        "scripts/",
        "tests/",
    )


def check_h401(context: ProjectGuardContext) -> CheckResult:
    errors = []
    files = project_python_files(context.root)
    for path in files:
        try:
            source = read_text(path)
            compile(source, str(path), "exec")
        except (OSError, UnicodeDecodeError, SyntaxError) as error:
            errors.append(f"{relative(path, context.root)}:{type(error).__name__}")
    if errors:
        return failed("H-401", "; ".join(errors), "프로젝트 *.py")
    return passed("H-401", f"Python 파일 {len(files)}개 메모리 컴파일 성공", "프로젝트 *.py")


def ids_from_spec(path: Path) -> list[str]:
    text = read_text(path)
    return re.findall(r"^\| `(H-\d{3})` \|", text, flags=re.MULTILINE)


def check_h402(context: ProjectGuardContext) -> CheckResult:
    spec_ids = ids_from_spec(context.root / SPEC_RELATIVE_PATH)
    registry_ids = [definition.check_id for definition in CHECK_DEFINITIONS]
    if len(spec_ids) != len(set(spec_ids)) or spec_ids != registry_ids:
        return failed(
            "H-402",
            f"spec={len(spec_ids)}개/고유={len(set(spec_ids))}개, registry={len(registry_ids)}개, 순서일치={spec_ids == registry_ids}",
            str(SPEC_RELATIVE_PATH),
            "scripts/project_guard_check.py",
        )
    return passed("H-402", "PROJECT_GUARD_SPEC와 registry의 46개 ID·순서가 정확히 일치", str(SPEC_RELATIVE_PATH), "scripts/project_guard_check.py")


def check_h403(context: ProjectGuardContext) -> CheckResult:
    return passed("H-403", "최종 결과 생성 후 상태·건수 정합성 재검증 예정", "Project Guard 실행 결과")


def exit_code_for(results: Sequence[CheckResult]) -> int:
    return 1 if any(result.status is Status.FAIL for result in results) else 0


def check_h404(context: ProjectGuardContext) -> CheckResult:
    synthetic_pass = [make_result("H-404", Status.PASS, "synthetic")]
    synthetic_fail = [make_result("H-404", Status.FAIL, "synthetic")]
    if exit_code_for(synthetic_pass) != 0 or exit_code_for(synthetic_fail) != 1:
        return failed("H-404", "성공·실패 종료 코드 매핑 오류", "scripts/project_guard_check.py")
    return passed("H-404", "성공=0, 필수실패=1, 내부오류=2 계약 확인", "scripts/project_guard_check.py")


def check_h501(context: ProjectGuardContext) -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="freshmanager-h501-") as temporary:
        root = Path(temporary)
        client = GuardSampleClient(context.json_path.read_bytes())
        identifiers = iter(
            [
                uuid.UUID("11111111-1111-4111-8111-111111111111"),
                uuid.UUID("22222222-2222-4222-8222-222222222222"),
            ]
        )
        collector = guard_collector(context, root, client, lambda: next(identifiers))
        first = collector.collect(EG4_DUMMY_KEY)
        first_path = Path(str(first.metadata["raw_file_path"]))
        first_hash = sha256_file(first_path)
        second = collector.collect(EG4_DUMMY_KEY)
        second_path = Path(str(second.metadata["raw_file_path"]))
        if first.status != "success" or second.status != "success":
            return failed("H-501", "반복 오프라인 저장 실패", "freshmanager/storage.py", "임시 출력")
        if first_path == second_path or not second_path.is_file() or sha256_file(first_path) != first_hash:
            return failed("H-501", "기존 원본 보존 또는 새 파일 생성 실패", "freshmanager/storage.py", "임시 출력")
    return passed("H-501", "원본 bytes 유지, 반복 요청은 기존 파일을 보존하고 새 파일 생성", "freshmanager/storage.py", "임시 출력")


def check_h502(context: ProjectGuardContext) -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="freshmanager-h502-") as temporary:
        root = Path(temporary)
        request_id = uuid.UUID("33333333-3333-4333-8333-333333333333")
        collector = guard_collector(
            context,
            root,
            GuardSampleClient(context.json_path.read_bytes()),
            lambda: request_id,
        )
        result = collector.collect(EG4_DUMMY_KEY)
        raw_path = Path(str(result.metadata["raw_file_path"]))
        expected = ".".join(["_".join(["POI072", "20260720", "091011", str(request_id)]), "json"])
        if result.status != "success" or raw_path.name != expected or raw_path.parts[-4:-1] != ("2026", "07", "20"):
            return failed("H-502", f"원본 경로·파일명 계약 불일치: {raw_path.name}", "freshmanager/storage.py")
    return passed("H-502", "AREA_CD·요청시각·request_id 파일명과 YYYY/MM/DD 경로 확인", "freshmanager/storage.py")


def check_h503(context: ProjectGuardContext) -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="freshmanager-h503-") as temporary:
        root = Path(temporary)
        collector = guard_collector(
            context,
            root,
            GuardSampleClient(context.json_path.read_bytes()),
            lambda: uuid.UUID("44444444-4444-4444-8444-444444444444"),
        )
        result = collector.collect(EG4_DUMMY_KEY)
        if tuple(result.metadata) != tuple(EG4_METADATA_FIELDS):
            return failed("H-503", f"메타데이터 필드 불일치={list(result.metadata)}", "freshmanager/collector.py")
        if "raw_payload" in result.metadata or result.metadata.get("endpoint_name") != "citydata_ppltn":
            return failed("H-503", "금지 필드 또는 endpoint 논리명 위반", "freshmanager/collector.py")
        raw_path = Path(str(result.metadata.get("raw_file_path")))
        if result.metadata_path is None or not raw_path.is_file():
            return failed("H-503", "메타데이터와 원본 파일 경로 연결 실패", "freshmanager/storage.py")
        stored = json.loads(result.metadata_path.read_text(encoding="utf-8"))
        if stored != result.metadata:
            return failed("H-503", "저장된 메타데이터 내용 불일치", "freshmanager/storage.py")
    return passed("H-503", "승인된 8개 필드와 논리 endpoint·원본 경로 연결 확인", "freshmanager/collector.py", "freshmanager/storage.py")


def check_h506(context: ProjectGuardContext) -> CheckResult:
    def metadata_issue(
        result: object,
        expected_status: str,
        *,
        raw_expected: bool,
        expected_raw: bytes | None = None,
    ) -> str | None:
        metadata = result.metadata
        if result.status != expected_status or metadata.get("collection_status") != expected_status:
            return f"상태 불일치: expected={expected_status}, actual={result.status}"
        if tuple(metadata) != tuple(EG4_METADATA_FIELDS):
            return f"메타데이터 필드 불일치: {list(metadata)}"
        if metadata.get("http_status") == 0:
            return "http_status를 임의의 0으로 보정함"
        rendered = json.dumps(metadata, ensure_ascii=False)
        if EG4_DUMMY_KEY in rendered or "http://" in rendered or "https://" in rendered or "raw_payload" in metadata:
            return "메타데이터에 Dummy Key·URL 또는 raw_payload 포함"
        if result.metadata_path is None or not result.metadata_path.is_file():
            return "오류 메타데이터 파일 누락"
        stored = json.loads(result.metadata_path.read_text(encoding="utf-8"))
        if stored != metadata:
            return "저장된 오류 메타데이터 내용 불일치"
        raw_value = metadata.get("raw_file_path")
        if not raw_expected:
            return None if raw_value is None else "원본 미저장 경로에 raw_file_path가 존재함"
        raw_path = Path(str(raw_value))
        if not raw_path.is_file():
            return "받은 원본 파일 누락"
        if expected_raw is not None and raw_path.read_bytes() != expected_raw:
            return "받은 원본 bytes가 변경됨"
        return None

    invalid_payload = b'{"SeoulRtd.citydata_ppltn": ['
    validation_document = json.loads(context.json_path.read_text(encoding="utf-8-sig"))
    validation_document["SeoulRtd.citydata_ppltn"][0]["AREA_CD"] = "POI999"
    validation_payload = json.dumps(validation_document, ensure_ascii=False).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="freshmanager-h506-") as temporary:
        root = Path(temporary)
        config_root = root / "config"
        invalid_env = config_root / "invalid.env"
        invalid_env.parent.mkdir(parents=True, exist_ok=True)
        private_setting = "private-dummy-config-content"
        invalid_env.write_text(f"OTHER_SETTING={private_setting}\n", encoding="utf-8")
        config_stdout = io.StringIO()
        with contextlib.redirect_stdout(config_stdout):
            config_exit = run_offline(
                [
                    "--env-file",
                    str(invalid_env),
                    "--csv",
                    str(context.csv_path),
                    "--sample",
                    str(context.json_path),
                    "--raw-root",
                    str(config_root / "raw"),
                    "--metadata-root",
                    str(config_root / "metadata"),
                ]
            )
        config_files = list((config_root / "metadata").rglob("*.metadata.json"))
        if config_exit == 0 or len(config_files) != 1:
            return failed("H-506", "CLI config_error 메타데이터 기록 또는 비정상 종료 실패", "freshmanager/offline.py")
        config_metadata = json.loads(config_files[0].read_text(encoding="utf-8"))
        config_rendered = config_stdout.getvalue() + json.dumps(config_metadata, ensure_ascii=False)
        if (
            tuple(config_metadata) != tuple(EG4_METADATA_FIELDS)
            or config_metadata.get("collection_status") != "config_error"
            or config_metadata.get("http_status") is not None
            or config_metadata.get("raw_file_path") is not None
            or str(invalid_env) in config_rendered
            or private_setting in config_rendered
            or EG4_DUMMY_KEY in config_rendered
            or "http://" in config_rendered
            or "https://" in config_rendered
        ):
            return failed("H-506", "CLI config_error 8개 필드·null·비노출 계약 위반", "freshmanager/offline.py")

        identifiers = iter(
            uuid.UUID(value)
            for value in [
                "50000000-0000-4000-8000-000000000002",
                "50000000-0000-4000-8000-000000000003",
                "50000000-0000-4000-8000-000000000004",
                "50000000-0000-4000-8000-000000000005",
            ]
        )
        cases = [
            (
                "api_error",
                guard_collector(context, root / "api", GuardSampleClient(b'{"error":true}', 500), lambda: next(identifiers)),
                EG4_DUMMY_KEY,
                True,
                b'{"error":true}',
            ),
            (
                "timeout",
                guard_collector(context, root / "timeout", GuardTimeoutClient(), lambda: next(identifiers)),
                EG4_DUMMY_KEY,
                False,
                None,
            ),
            (
                "parse_error",
                guard_collector(context, root / "parse", GuardSampleClient(invalid_payload), lambda: next(identifiers)),
                EG4_DUMMY_KEY,
                True,
                invalid_payload,
            ),
            (
                "validation_error",
                guard_collector(context, root / "validation", GuardSampleClient(validation_payload), lambda: next(identifiers)),
                EG4_DUMMY_KEY,
                True,
                validation_payload,
            ),
        ]
        for expected_status, collector, key, raw_expected, expected_raw in cases:
            result = collector.collect(key)
            issue = metadata_issue(
                result,
                expected_status,
                raw_expected=raw_expected,
                expected_raw=expected_raw,
            )
            if issue:
                return failed("H-506", f"{expected_status}: {issue}", "freshmanager/collector.py", "freshmanager/storage.py")

        raw_failure_storage = GuardRawFailStorage(root / "raw-failure/raw", root / "raw-failure/metadata")
        raw_failure_collector = Collector(
            context.csv_path,
            GuardSampleClient(context.json_path.read_bytes()),
            raw_failure_storage,
            clock=lambda: EG4_FIXED_TIME,
            request_id_factory=lambda: uuid.UUID("50000000-0000-4000-8000-000000000006"),
        )
        raw_failure = raw_failure_collector.collect(EG4_DUMMY_KEY)
        issue = metadata_issue(raw_failure, "storage_error", raw_expected=False)
        if issue:
            return failed("H-506", f"원본 저장 실패: {issue}", "freshmanager/collector.py", "freshmanager/storage.py")

        env_path = root / "metadata-failure/dummy.env"
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("SEOUL_OPEN_API_KEY=" + EG4_DUMMY_KEY + "\n", encoding="utf-8")
        metadata_failure_storage = GuardMetadataFailStorage(
            root / "metadata-failure/raw",
            root / "metadata-failure/metadata",
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = run_offline(
                [
                    "--env-file",
                    str(env_path),
                    "--csv",
                    str(context.csv_path),
                    "--sample",
                    str(context.json_path),
                    "--raw-root",
                    str(metadata_failure_storage.raw_root),
                    "--metadata-root",
                    str(metadata_failure_storage.metadata_root),
                ],
                storage_factory=lambda raw_root, metadata_root: metadata_failure_storage,
            )
        output = stdout.getvalue()
        output_lines = [line for line in output.splitlines() if line]
        if exit_code == 0 or metadata_failure_storage.metadata_calls != 1:
            return failed("H-506", "메타데이터 writer 실패의 비정상 종료·단일 시도 계약 위반", "freshmanager/offline.py")
        if len(output_lines) != 2 or not output_lines[0].startswith("request_id=") or output_lines[1] != "collection_status=storage_error":
            return failed("H-506", "메타데이터 writer 실패 출력이 request_id·상태로 제한되지 않음", "freshmanager/offline.py")
        if EG4_DUMMY_KEY in output or "http://" in output or "https://" in output:
            return failed("H-506", "메타데이터 writer 실패 출력에 Dummy Key·URL 노출", "freshmanager/offline.py")
        if list(metadata_failure_storage.metadata_root.rglob("*.json")) or list(
            metadata_failure_storage.metadata_root.rglob("*.partial")
        ):
            return failed("H-506", "메타데이터 writer 실패 후 최종·partial 파일 잔존", "freshmanager/storage.py")
    return passed(
        "H-506",
        "6개 오류 메타데이터 기록과 metadata writer 반환-only 예외·비노출·비재귀 확인",
        "freshmanager/collector.py",
        "freshmanager/storage.py",
        "freshmanager/offline.py",
    )


def check_h701(context: ProjectGuardContext) -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="freshmanager-h701-") as temporary:
        root = Path(temporary)
        client = GuardSampleClient(context.json_path.read_bytes())
        collector = guard_collector(
            context,
            root,
            client,
            lambda: uuid.UUID("77777777-7777-4777-8777-777777777777"),
        )
        result = collector.collect(EG4_DUMMY_KEY)
        raw_path = Path(str(result.metadata["raw_file_path"]))
        if client.calls != ["POI072"] or result.status != "success":
            return failed("H-701", f"처리 호출={client.calls}, 상태={result.status}", "freshmanager/collector.py")
        if not result.population or result.metadata_path is None or not raw_path.is_file():
            return failed("H-701", "원본·파싱 결과·상태 메타데이터 누락", "freshmanager/collector.py", "freshmanager/storage.py")
        required_population = {
            "area_code",
            "area_name",
            "population_reference_time",
            "congestion_level",
            "population_min",
            "population_max",
            "forecast_available",
            "forecasts",
        }
        if not required_population.issubset(result.population):
            return failed("H-701", "정규화 현재 인구 필수 값 누락", "freshmanager/collector.py")
        forecasts = result.population.get("forecasts")
        if (
            result.population.get("area_code") != "POI072"
            or result.population.get("area_name") != "여의도"
            or not result.population.get("population_reference_time")
            or not isinstance(forecasts, list)
            or not forecasts
        ):
            return failed("H-701", "정규화 장소·현재 인구·예측 구조 불일치", "freshmanager/collector.py")
        stored_metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
        if (
            stored_metadata != result.metadata
            or stored_metadata.get("collection_status") != "success"
            or stored_metadata.get("area_code") != result.population.get("area_code")
            or Path(str(stored_metadata.get("raw_file_path"))) != raw_path
            or raw_path.read_bytes() != context.json_path.read_bytes()
        ):
            return failed("H-701", "원본·정규화·상태 결과 연결 불일치", "freshmanager/collector.py", "freshmanager/storage.py")
    return passed("H-701", "공식 CSV의 POI072 1건과 원본·정규화 현재/예측·상태 결과 연결 확인", "freshmanager/collector.py", "freshmanager/storage.py")


def check_h702(context: ProjectGuardContext) -> CheckResult:
    inspected = csv_or_failure(context, "H-702")
    if isinstance(inspected, CheckResult):
        return inspected
    names_by_code = {
        normalized_cell(row, "AREA_CD"): normalized_cell(row, "AREA_NM")
        for row in inspected.rows
    }
    if (
        tuple(eg5_cli.EG5_AREA_CODES) != EG5_APPROVED_AREA_CODES
        or len(set(eg5_cli.EG5_AREA_CODES)) != 3
        or any(names_by_code.get(code) != EG5_APPROVED_AREA_NAMES[code] for code in EG5_APPROVED_AREA_CODES)
    ):
        return failed(
            "H-702",
            "승인 Allowlist 또는 공식 CSV 장소명 불일치",
            str(CSV_RELATIVE_PATH),
            "freshmanager/eg5.py",
        )

    execution = run_eg5_guard(context)
    metadata_codes = tuple(str(item.get("area_code")) for item in execution.metadata)
    metadata_is_valid = all(
        tuple(item) == tuple(EG4_METADATA_FIELDS)
        and item.get("collection_status") == "success"
        for item in execution.metadata
    )
    if (
        execution.exit_code != 0
        or execution.calls != EG5_APPROVED_AREA_CODES
        or len(execution.raw_area_codes) != 3
        or set(execution.raw_area_codes) != set(EG5_APPROVED_AREA_CODES)
        or len(metadata_codes) != 3
        or set(metadata_codes) != set(EG5_APPROVED_AREA_CODES)
        or not metadata_is_valid
        or not execution.stage_only
    ):
        return failed(
            "H-702",
            "승인 3장소 처리 또는 전용 단계 원본·메타데이터 계약 불일치",
            str(CSV_RELATIVE_PATH),
            "freshmanager/eg5.py",
            "임시 출력",
        )
    rendered_metadata = json.dumps(execution.metadata, ensure_ascii=False)
    if EG5_DUMMY_KEY in execution.output or EG5_DUMMY_KEY in rendered_metadata or BASE_URL in execution.output:
        return failed(
            "H-702",
            "EG-5 출력·메타데이터에 Dummy Key 또는 인증 URL 노출",
            "freshmanager/eg5.py",
            "임시 출력",
        )
    return passed(
        "H-702",
        "POI019·POI013·POI014를 고정 순서로 각각 1회 처리하고 전용 단계에 분리 저장",
        str(CSV_RELATIVE_PATH),
        "freshmanager/eg5.py",
        "임시 출력",
    )


def check_h703(context: ProjectGuardContext) -> CheckResult:
    input_paths = (
        EG6_AREA_PANEL_RELATIVE_PATH,
        EG6_SPOT_MASTER_RELATIVE_PATH,
        EG6_SDOT_LINKS_RELATIVE_PATH,
    )
    inspections: dict[Path, CsvInspection] = {}
    for relative_path in input_paths:
        path = context.root / relative_path
        if not path.is_file():
            return failed("H-703", "EG-6A 필수 참조 CSV 누락", *(str(item) for item in input_paths))
        try:
            inspections[relative_path] = inspect_csv(path)
        except (OSError, UnicodeError, csv.Error):
            return failed("H-703", "EG-6A 참조 CSV 읽기 실패", *(str(item) for item in input_paths))

    areas = inspections[EG6_AREA_PANEL_RELATIVE_PATH]
    spots = inspections[EG6_SPOT_MASTER_RELATIVE_PATH]
    links = inspections[EG6_SDOT_LINKS_RELATIVE_PATH]
    if (
        list(areas.fieldnames) != EG6_AREA_HEADERS
        or list(spots.fieldnames) != EG6_SPOT_HEADERS
        or list(links.fieldnames) != EG6_SDOT_HEADERS
    ):
        return failed("H-703", "EG-6A 참조 CSV 헤더 계약 불일치", *(str(item) for item in input_paths))

    area_rows = list(areas.rows)
    spot_rows = list(spots.rows)
    link_rows = list(links.rows)
    try:
        panel_orders = [int(normalized_cell(row, "panel_order")) for row in area_rows]
    except ValueError:
        return failed("H-703", "패널 순서가 정수가 아님", str(EG6_AREA_PANEL_RELATIVE_PATH))
    service_names = [normalized_cell(row, "service_area_name") for row in area_rows]
    area_codes = [normalized_cell(row, "area_code") for row in area_rows]
    nonempty_codes = [code for code in area_codes if code]
    approved_rows = [row for row in area_rows if normalized_cell(row, "approved") == "true"]
    pending_rows = [row for row in area_rows if normalized_cell(row, "approved") == "false"]
    if (
        len(area_rows) != EG6_PROPOSED_AREA_COUNT
        or panel_orders != list(range(1, EG6_PROPOSED_AREA_COUNT + 1))
        or {normalized_cell(row, "panel_version") for row in area_rows} != {EG6_PANEL_VERSION}
        or not all(service_names)
        or len(service_names) != len(set(service_names))
        or len(nonempty_codes) != len(set(nonempty_codes))
        or len(approved_rows) != EG6_APPROVED_AREA_COUNT
        or {normalized_cell(row, "service_area_name") for row in pending_rows} != EG6_PENDING_SERVICE_AREAS
    ):
        return failed("H-703", "패널 수·순서·버전·중복·승인 수 계약 불일치", str(EG6_AREA_PANEL_RELATIVE_PATH))

    official = csv_or_failure(context, "H-703")
    if isinstance(official, CheckResult):
        return official
    official_names = {
        normalized_cell(row, "AREA_CD"): normalized_cell(row, "AREA_NM")
        for row in official.rows
    }
    approved_by_service: dict[str, dict[str | None, str | list[str] | None]] = {}
    for row in area_rows:
        service = normalized_cell(row, "service_area_name")
        area_code = normalized_cell(row, "area_code")
        official_name = normalized_cell(row, "official_area_name")
        mapping_type = normalized_cell(row, "area_mapping_type")
        confidence = normalized_cell(row, "mapping_confidence")
        coverage = normalized_cell(row, "sdot_group")
        approved = normalized_cell(row, "approved")
        active = normalized_cell(row, "active")
        if (
            mapping_type not in EG6_MAPPING_TYPES
            or confidence not in EG6_MAPPING_CONFIDENCE
            or coverage not in EG6_COVERAGE_CLASSES
            or approved not in EG6_BOOLEAN_VALUES
            or active not in EG6_BOOLEAN_VALUES
        ):
            return failed("H-703", "Area Enum 또는 Boolean 계약 불일치", str(EG6_AREA_PANEL_RELATIVE_PATH))
        if approved == "true":
            if (
                active != "true"
                or mapping_type not in {"EXACT_AREA_MATCH", "RELATED_AREA_MATCH"}
                or not area_code
                or official_names.get(area_code) != official_name
            ):
                return failed("H-703", "승인 Area의 공식 코드·장소명·활성 상태 불일치", str(EG6_AREA_PANEL_RELATIVE_PATH), str(CSV_RELATIVE_PATH))
            approved_by_service[service] = row
        elif (
            active != "false"
            or mapping_type not in {"NO_SAFE_AREA_MATCH", "REPLACEMENT_REQUIRED"}
            or area_code
            or official_name
        ):
            return failed("H-703", "미승인 Area가 코드 또는 활성 상태를 보유함", str(EG6_AREA_PANEL_RELATIVE_PATH))

    spot_ids = [normalized_cell(row, "spot_id") for row in spot_rows]
    if (
        len(spot_rows) != EG6_PROPOSED_AREA_COUNT
        or not all(spot_ids)
        or len(spot_ids) != len(set(spot_ids))
        or {normalized_cell(row, "service_area_name") for row in spot_rows} != set(service_names)
    ):
        return failed("H-703", "Spot 수·식별자·서비스 지역 연결 불일치", str(EG6_SPOT_MASTER_RELATIVE_PATH))

    spot_by_id: dict[str, dict[str | None, str | list[str] | None]] = {}
    spot_by_service: dict[str, dict[str | None, str | list[str] | None]] = {}
    for row in spot_rows:
        spot_id = normalized_cell(row, "spot_id")
        service = normalized_cell(row, "service_area_name")
        connected_code = normalized_cell(row, "connected_area_code")
        connected_name = normalized_cell(row, "connected_area_name")
        coordinate_type = normalized_cell(row, "representative_coordinate_type")
        suitability = normalized_cell(row, "selling_suitability_status")
        field_verified = normalized_cell(row, "field_verified")
        active = normalized_cell(row, "active")
        try:
            latitude = float(normalized_cell(row, "latitude"))
            longitude = float(normalized_cell(row, "longitude"))
        except ValueError:
            return failed("H-703", "Spot 좌표가 숫자가 아님", str(EG6_SPOT_MASTER_RELATIVE_PATH))
        if (
            not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
            or coordinate_type not in EG6_COORDINATE_TYPES
            or suitability not in EG6_SPOT_STATUSES
            or field_verified not in EG6_BOOLEAN_VALUES
            or active not in EG6_BOOLEAN_VALUES
        ):
            return failed("H-703", "Spot 좌표·Enum·Boolean 계약 불일치", str(EG6_SPOT_MASTER_RELATIVE_PATH))
        if active == "true":
            area = approved_by_service.get(service)
            if (
                area is None
                or connected_code != normalized_cell(area, "area_code")
                or connected_name != normalized_cell(area, "official_area_name")
                or not EG6_SEOUL_LATITUDE_RANGE[0] <= latitude <= EG6_SEOUL_LATITUDE_RANGE[1]
                or not EG6_SEOUL_LONGITUDE_RANGE[0] <= longitude <= EG6_SEOUL_LONGITUDE_RANGE[1]
            ):
                return failed("H-703", "활성 Spot의 Area 참조 또는 서울 범위 불일치", str(EG6_SPOT_MASTER_RELATIVE_PATH), str(EG6_AREA_PANEL_RELATIVE_PATH))
        elif connected_code or connected_name:
            return failed("H-703", "미승인 Spot이 Area 참조를 보유함", str(EG6_SPOT_MASTER_RELATIVE_PATH))
        if coordinate_type == "STATION_CENTER_PROXY" and (
            suitability != "FIELD_VALIDATION_REQUIRED" or field_verified != "false"
        ):
            return failed("H-703", "역 중심 대용점이 검증된 출구로 표현됨", str(EG6_SPOT_MASTER_RELATIVE_PATH))
        spot_by_id[spot_id] = row
        spot_by_service[service] = row

    link_spot_ids = [normalized_cell(row, "spot_id") for row in link_rows]
    if (
        len(link_rows) != EG6_PROPOSED_AREA_COUNT
        or len(link_spot_ids) != len(set(link_spot_ids))
        or set(link_spot_ids) != set(spot_ids)
    ):
        return failed("H-703", "S-DoT Link와 Spot 참조 무결성 불일치", str(EG6_SDOT_LINKS_RELATIVE_PATH), str(EG6_SPOT_MASTER_RELATIVE_PATH))

    link_by_spot: dict[str, dict[str | None, str | list[str] | None]] = {}
    for row in link_rows:
        spot_id = normalized_cell(row, "spot_id")
        coverage = normalized_cell(row, "coverage_class")
        recent_active = normalized_cell(row, "sensor_recent_active")
        confidence = normalized_cell(row, "mapping_confidence")
        source_report = normalized_cell(row, "source_report")
        try:
            distance = float(normalized_cell(row, "nearest_sdot_distance_m"))
        except ValueError:
            return failed("H-703", "S-DoT 거리가 숫자가 아님", str(EG6_SDOT_LINKS_RELATIVE_PATH))
        expected_coverage = (
            "DIRECT_COVERAGE" if distance <= 150
            else "NEARBY_SUPPORT" if distance <= 300
            else "NO_NEARBY_SDOT"
        )
        if (
            not normalized_cell(row, "nearest_sdot_id")
            or distance < 0
            or coverage not in EG6_COVERAGE_CLASSES
            or coverage != expected_coverage
            or recent_active != "true"
            or confidence not in EG6_MAPPING_CONFIDENCE
            or source_report != "EG6_AREA_SPOT_PANEL.md"
        ):
            return failed("H-703", "S-DoT 거리·활성·등급·출처 계약 불일치", str(EG6_SDOT_LINKS_RELATIVE_PATH))
        link_by_spot[spot_id] = row

    for area in area_rows:
        service = normalized_cell(area, "service_area_name")
        spot_id = normalized_cell(spot_by_service[service], "spot_id")
        if normalized_cell(area, "sdot_group") != normalized_cell(link_by_spot[spot_id], "coverage_class"):
            return failed("H-703", "Area와 S-DoT Link의 커버리지 불일치", str(EG6_AREA_PANEL_RELATIVE_PATH), str(EG6_SDOT_LINKS_RELATIVE_PATH))

    forbidden = re.compile(r"/Users/|file://|https?://|SEOUL_OPEN_API_KEY|API[_-]?KEY\s*=", re.IGNORECASE)
    for inspection in (areas, spots, links):
        for row in inspection.rows:
            rendered = "\n".join(normalized_cell(row, key) for key in inspection.fieldnames)
            if forbidden.search(rendered):
                return failed("H-703", "EG-6A 참조 CSV에 비밀정보·URL·로컬 절대경로 패턴 존재", *(str(item) for item in input_paths))

    return passed(
        "H-703",
        "13개 제안·13개 고유 공식 Area 승인과 Area–Spot–S-DoT 참조 무결성 확인",
        str(CSV_RELATIVE_PATH),
        *(str(item) for item in input_paths),
    )


def check_h704(context: ProjectGuardContext) -> CheckResult:
    execution = run_eg5_guard(context, {"POI013"})
    summary = eg5_summary(execution.output)
    status_by_code = {
        str(item.get("area_code")): str(item.get("collection_status"))
        for item in execution.metadata
    }
    if (
        execution.exit_code != 1
        or execution.calls != EG5_APPROVED_AREA_CODES
        or any(execution.calls.count(code) != 1 for code in EG5_APPROVED_AREA_CODES)
        or status_by_code
        != {"POI019": "success", "POI013": "timeout", "POI014": "success"}
        or summary.get("retry_count") != "0"
    ):
        return failed(
            "H-704",
            "가운데 장소 실패 후 계속 처리 또는 재시도 0회 계약 불일치",
            "freshmanager/eg5.py",
            "가짜 Transport",
            "임시 출력",
        )
    return passed(
        "H-704",
        "POI013 실패 후 POI014 계속 처리, 세 장소 각 1회, 재시도 0회 확인",
        "freshmanager/eg5.py",
        "가짜 Transport",
        "임시 출력",
    )


def check_h705(context: ProjectGuardContext) -> CheckResult:
    success_execution = run_eg5_guard(context)
    failure_execution = run_eg5_guard(context, {"POI013"})
    success_summary = eg5_summary(success_execution.output)
    failure_summary = eg5_summary(failure_execution.output)
    expected_success = {
        "target_count": "3",
        "success_count": "3",
        "failure_count": "0",
        "failed_area_codes": "",
        "retry_count": "0",
        "stage": "eg5_representative_3",
        "exit_code": "0",
    }
    expected_failure = {
        "target_count": "3",
        "success_count": "2",
        "failure_count": "1",
        "failed_area_codes": "POI013",
        "retry_count": "0",
        "stage": "eg5_representative_3",
        "exit_code": "1",
    }
    if success_summary != expected_success or failure_summary != expected_failure:
        return failed(
            "H-705",
            "정상·부분실패 회차 요약의 대상·성공·실패·목록 정합성 불일치",
            "freshmanager/eg5.py",
            "임시 출력",
        )
    return passed(
        "H-705",
        "정상·부분실패 회차에서 대상=성공+실패와 실패 목록·종료코드 정합성 확인",
        "freshmanager/eg5.py",
        "임시 출력",
    )


RUNNERS: dict[str, Callable[[ProjectGuardContext], CheckResult]] = {
    f"check_{check_id.lower().replace('-', '')}": globals()[f"check_{check_id.lower().replace('-', '')}"]
    for check_id in [
        "H-001", "H-002", "H-003", "H-004",
        "H-101", "H-102", "H-103", "H-104", "H-105", "H-106",
        "H-107", "H-108", "H-109", "H-110", "H-111", "H-112",
        "H-201", "H-202", "H-203",
        "H-204", "H-205", "H-206",
        "H-301", "H-302", "H-303", "H-304", "H-305",
        "H-401", "H-402", "H-403", "H-404",
        "H-501", "H-502", "H-503", "H-506", "H-701", "H-702", "H-703", "H-704", "H-705",
    ]
}


def definition(check_id: str, name: str, gate: str, implemented: bool = True, skip_reason: str | None = None) -> CheckDefinition:
    runner_name = f"check_{check_id.lower().replace('-', '')}" if implemented else None
    return CheckDefinition(check_id, name, gate, runner_name, skip_reason)


CHECK_DEFINITIONS = [
    definition("H-001", "필수 문서 존재", "EG-0, EG-3 이후"),
    definition("H-002", "Markdown 구조", "EG-0, EG-3 이후"),
    definition("H-003", "문서 규칙 일치", "EG-0, EG-3 이후"),
    definition("H-004", "README 상태·실행방법 정확성", "EG-0, EG-3 이후"),
    definition("H-101", "공식 CSV 파일 존재", "EG-1, EG-3 이후"),
    definition("H-102", "CSV 인코딩 읽기", "EG-1, EG-3 이후"),
    definition("H-103", "CSV 필수 컬럼", "EG-1, EG-3 이후"),
    definition("H-104", "CSV 121행", "EG-1, EG-3 이후"),
    definition("H-105", "AREA_CD 결측", "EG-1, EG-3 이후"),
    definition("H-106", "AREA_CD 중복", "EG-1, EG-3 이후"),
    definition("H-107", "AREA_NM 결측", "EG-1, EG-3 이후"),
    definition("H-108", "여의도 장소코드", "EG-1, EG-3 이후"),
    definition("H-109", "장소코드 비생성", "EG-3 이후"),
    definition("H-110", "표준 CSV 사용", "EG-3 이후"),
    definition("H-111", "공식 CSV 불변", "EG-1, EG-3 이후"),
    definition("H-112", "장소 분류 무결성", "EG-1, EG-3 이후"),
    definition("H-201", ".env Git 제외", "EG-3 이후"),
    definition("H-202", ".env.example 계약", "EG-3 이후"),
    definition("H-203", "비밀정보 노출 검사", "EG-3 이후"),
    definition("H-204", "최소 .env 로더", "EG-4 이후"),
    definition("H-205", "URL·오류 마스킹", "EG-4 이후"),
    definition("H-206", "보호 작업일지 경로 안전성", "EG-3 이후"),
    definition("H-301", "샘플 JSON 존재·문법", "EG-2, EG-3 이후"),
    definition("H-302", "샘플 장소·인구 구조", "EG-2, EG-3 이후"),
    definition("H-303", "샘플 미래예측 구조", "EG-2, EG-3 이후"),
    definition("H-304", "샘플 비밀정보 제거", "EG-2, EG-3 이후"),
    definition("H-305", "Project Guard·테스트 오프라인", "EG-3 이후"),
    definition("H-401", "Python 문법", "EG-3 이후"),
    definition("H-402", "검사 ID 등록 정합성", "EG-3 이후"),
    definition("H-403", "상태·건수 정합성", "EG-3 이후"),
    definition("H-404", "종료 코드 계약", "EG-3 이후"),
    definition("H-501", "원본 JSON 불변·비덮어쓰기", "EG-4 이후"),
    definition("H-502", "원본 파일명 계약", "EG-4 이후"),
    definition("H-503", "최소 메타데이터 계약", "EG-4 이후"),
    definition("H-504", "예측 스냅샷 보존", "EG-4 이후", False, "EG-4 예측 저장 코드 구현 후 적용"),
    definition("H-505", "날씨 관측·예보 분리", "EG-4 이후", False, "EG-4 날씨 writer 구현 후 적용"),
    definition("H-506", "이상값·오류 별도 기록", "EG-4 이후"),
    definition("H-601", "상권현황 표현", "EG-4 이후", False, "EG-4 상권 파서·출력 구현 후 적용"),
    definition("H-602", "상태값 구분", "EG-4 이후", False, "EG-4 상권 상태 처리 구현 후 적용"),
    definition("H-701", "여의도 1장소", "EG-4 이후"),
    definition("H-702", "EG-5 대표 3장소", "EG-5 이후"),
    definition("H-703", "EG-6A 13지역 참조데이터", "EG-6A 이후"),
    definition("H-704", "실패 격리·재시도 제한", "EG-5 이후"),
    definition("H-705", "회차 결과 요약", "EG-5 이후"),
    definition(
        "H-706",
        "EG-6B 13지역 1회 완전성",
        "EG-6B 이후",
        False,
        "EG-6B 13지역 단일 수집 구현 후 적용",
    ),
    definition(
        "H-707",
        "EG-7 반복주기 승인 준수",
        "EG-7 이후",
        False,
        "반복수집 전 PM 주기 승인과 외장 저장장치 또는 승인된 클라우드 폴더 백업 Gate 필요",
    ),
]
DEFINITION_BY_ID = {item.check_id: item for item in CHECK_DEFINITIONS}


def skipped(definition_item: CheckDefinition) -> CheckResult:
    return CheckResult(
        check_id=definition_item.check_id,
        name=definition_item.name,
        gate=definition_item.gate,
        input_files=(),
        status=Status.SKIP,
        evidence=definition_item.skip_reason or "현재 EG 비적용",
    )


def replace_result(results: list[CheckResult], replacement: CheckResult) -> None:
    for index, result in enumerate(results):
        if result.check_id == replacement.check_id:
            results[index] = replacement
            return
    raise RuntimeError(f"registered result not found: {replacement.check_id}")


def validate_final_results(results: list[CheckResult]) -> CheckResult:
    ids = [result.check_id for result in results]
    expected_ids = [item.check_id for item in CHECK_DEFINITIONS]
    valid_statuses = set(Status)
    issues = []
    if ids != expected_ids:
        issues.append("결과 ID 또는 순서 불일치")
    if len(ids) != 46 or len(set(ids)) != 46:
        issues.append(f"결과 수={len(ids)}, 고유={len(set(ids))}")
    if any(result.status not in valid_statuses for result in results):
        issues.append("허용되지 않은 상태값")
    counts = Counter(result.status for result in results)
    if sum(counts.values()) != len(results):
        issues.append("상태별 합계 불일치")
    if issues:
        return failed("H-403", "; ".join(issues), "Project Guard 실행 결과")
    return passed(
        "H-403",
        f"상태별 합계={len(results)}, ID·순서·상태값 정상",
        "Project Guard 실행 결과",
    )


def enforce_official_file_immutability(context: ProjectGuardContext, results: list[CheckResult]) -> None:
    csv_after = sha256_if_file(context.csv_path)
    json_after = sha256_if_file(context.json_path)
    if context.csv_hash_before is not None and csv_after != context.csv_hash_before:
        replace_result(results, failed("H-111", "Project Guard 전체 실행 전후 공식 CSV SHA-256 불일치", str(CSV_RELATIVE_PATH)))
    if context.json_hash_before is not None and json_after != context.json_hash_before:
        replace_result(results, failed("H-301", "Project Guard 전체 실행 전후 공식 JSON SHA-256 불일치", str(JSON_RELATIVE_PATH)))


def run_project_guard(root: Path = PROJECT_ROOT) -> list[CheckResult]:
    root = root.resolve()
    csv_path = root / CSV_RELATIVE_PATH
    json_path = root / JSON_RELATIVE_PATH
    context = ProjectGuardContext(
        root=root,
        csv_hash_before=sha256_if_file(csv_path),
        json_hash_before=sha256_if_file(json_path),
    )
    results: list[CheckResult] = []
    for item in CHECK_DEFINITIONS:
        if item.runner_name is None:
            results.append(skipped(item))
        else:
            results.append(RUNNERS[item.runner_name](context))
    replace_result(results, validate_final_results(results))
    enforce_official_file_immutability(context, results)
    return results


def status_counts(results: Sequence[CheckResult]) -> Counter[Status]:
    counts: Counter[Status] = Counter(result.status for result in results)
    for status in Status:
        counts.setdefault(status, 0)
    return counts


def format_report(results: Sequence[CheckResult]) -> str:
    lines = []
    for result in results:
        inputs = f" | 입력={','.join(result.input_files)}" if result.input_files else ""
        lines.append(f"[{result.status.value}] {result.check_id} {result.name} — {result.evidence}{inputs}")
    counts = status_counts(results)
    exit_code = exit_code_for(results)
    lines.append("")
    lines.append(
        "SUMMARY "
        f"PASS={counts[Status.PASS]} "
        f"FAIL={counts[Status.FAIL]} "
        f"WARN={counts[Status.WARN]} "
        f"SKIP={counts[Status.SKIP]} "
        f"TOTAL={len(results)}"
    )
    lines.append(f"EXIT_CODE={exit_code}")
    return "\n".join(lines)


def main(
    root: Path = PROJECT_ROOT,
    runner: Callable[[Path], list[CheckResult]] = run_project_guard,
) -> int:
    try:
        results = runner(root)
        print(format_report(results))
        return exit_code_for(results)
    except Exception as error:  # Project Guard failures must map to the documented code 2.
        print(
            f"[PROJECT_GUARD_ERROR] 내부 오류({type(error).__name__}); 민감값은 출력하지 않음",
            file=sys.stderr,
        )
        print("EXIT_CODE=2", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
