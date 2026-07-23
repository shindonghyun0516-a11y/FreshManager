# Project Guard Specification

## 1. 문서 목적과 기준 권한

이 문서는 Freshmanager 데이터 타당성 PoC의 자동검사 항목과 검사 ID를
정의하는 유일한 기준이다. 다른 문서와 보고 템플릿은 이 문서에 정의된
검사 ID를 참조만 하며 새 ID를 정의하지 않는다.

EG-0부터 EG-2까지는 Project Guard 구현 전 단계다. 각 게이트에 적용되는 검사 ID만
읽기 전용으로 사전검증하고, EG-3에서 같은 내용을 Project Guard로 자동 재검증한다.
판정할 코드가 없는 `H-109`와 `H-110`은 EG-1에서 `SKIP`한다.

---

## 2. 실행 원칙

Project Guard가 구현된 뒤 전체 실행 명령은 다음 하나로 통일한다.

```bash
python3 scripts/project_guard_check.py
```

`scripts/project_guard_check.py`는 EG-3의 현재 구현체이며 위 명령으로 실행한다.
실행 결과는 `docs/testing/PROJECT_GUARD_REPORT_TEMPLATE.md` 형식으로 기록한다.

제품 기준은 `docs/product/FreshManager_PRD_v1.0.md`, 기술 기준은
`docs/engineering/FreshManager_TRD_v1.0.md`다. 현재 H-001·H-002의 자동검사 입력은
아래 명세의 기존 여섯 문서를 유지하며, PRD·TRD의 Git 포함 여부·Markdown 구조·링크는
이번 문서 정렬에서 별도로 확인한다. 자동검사 입력 확대는 코드 변경 승인을 받은 별도
작업에서만 수행한다.

- 일반 Project Guard와 일반 테스트에서는 네트워크 연결과 실제 서울시 API 호출을 금지한다.
- 저장된 샘플 JSON, 가짜 응답과 임시 파일만 사용한다.
- 실제 API 호출은 EG-3 오프라인 Project Guard 통과 후 PM 승인을 받아
  EG-4 여의도 1장소 단계에서 Project Guard 밖의 별도 수동 실행으로 수행한다.
- Project Guard는 실제 호출을 시작하지 않고, 호출 후 저장된 결과만 오프라인으로 검사한다.
- 적용 대상 필수검사 하나라도 FAIL이면 완료 또는 게이트 통과로 보고하지 않는다.

---

## 3. 상태값과 종료 코드

### 상태값

| 상태 | 의미 |
|---|---|
| `PASS` | 적용 게이트의 필수조건을 충족함 |
| `FAIL` | 적용 대상 필수조건을 충족하지 못함 |
| `WARN` | 필수조건은 충족했지만 PM 확인이 필요한 비차단 상태 |
| `SKIP` | 현재 게이트에 아직 적용되지 않아 실행하지 않음 |

- 필수조건 실패를 `WARN`으로 낮추지 않는다.
- `SKIP`에는 사유를 반드시 기록한다.
- 해당 게이트에 진입했거나 구현 완료로 보고한 기능의 필수검사는 `SKIP`할 수 없다.

### 종료 코드

| 종료 코드 | 의미 |
|---:|---|
| `0` | 적용 대상 필수검사가 모두 통과함. 명시적으로 허용된 WARN은 있을 수 있음 |
| `1` | 한 개 이상의 적용 대상 필수검사가 실패함 |
| `2` | Project Guard 로딩·실행·결과 집계 등 Project Guard 자체 오류가 발생함 |

---

## 4. 검사 ID 목록

아래 표의 `WARN·SKIP` 열이 `불가`이면 두 상태를 모두 사용할 수 없다.
`이전 EG에서 SKIP`은 적용 게이트 진입 전까지만 SKIP할 수 있다는 뜻이다.
이 문서는 총 47개의 고유한 검사 ID를 정의한다. EG-6 MVP 전략 변경에 따라 기존
`H-703`의 시험용 10장소 계약을 EG-6A 13지역 참조데이터 계약으로 전환하며 새 ID를
추가하지 않는다.

### 4.1 문서 기준선

| 검사 ID | 검사명 | 검사 목적 | 입력 파일 | PASS 조건 | FAIL 조건 | WARN·SKIP 가능 여부 | 적용 엔지니어링 게이트 |
|---|---|---|---|---|---|---|---|
| `H-001` | 필수 문서 존재 | 문서 기준선 확보 | `AGENTS.md`, `README.md`, `docs/rules/CODING_RULES.md`, `docs/testing/PROJECT_GUARD_SPEC.md`, `docs/testing/QUALITY_GATES.md`, `docs/testing/PROJECT_GUARD_REPORT_TEMPLATE.md` | 여섯 파일이 존재하고 비어 있지 않음 | 파일 누락 또는 빈 파일 | 불가 | EG-0 사전검증, EG-3 이후 회귀 |
| `H-002` | Markdown 구조 | 제목과 코드 블록 손상 방지 | 위 여섯 문서 | 모든 코드 블록이 닫히고 제목 계층이 정상 | 미종료 코드 블록 또는 제목 계층 손상 | 불가 | EG-0, EG-3 이후 |
| `H-003` | 문서 규칙 일치 | 핵심 계약 충돌 방지 | 위 여섯 문서 | 기준파일 역할, EG 순서, PM 승인, 메타데이터, 보안, 오프라인 테스트와 호출주기가 일치하고 현재 상태 절의 완료·진행·대기 표현이 상충하지 않음 | 한 항목 이상 상충하거나 현재 상태표와 본문이 직접 충돌 | 불가 | EG-0, EG-3 이후 |
| `H-004` | README 상태·실행방법 정확성 | 허위 완료와 허위 실행 명령 방지 | `README.md`, 실제 프로젝트 파일 | 완료·미완료 상태가 실제와 맞고 구현된 기능만 실행방법 제공 | 없는 기능을 완료·실행 가능으로 표현하거나 구현 기능 안내 누락 | 불가 | EG-0, EG-3 이후 모든 게이트 |

### 4.2 장소 기준데이터

| 검사 ID | 검사명 | 검사 목적 | 입력 파일 | PASS 조건 | FAIL 조건 | WARN·SKIP 가능 여부 | 적용 엔지니어링 게이트 |
|---|---|---|---|---|---|---|---|
| `H-101` | 공식 CSV 파일 존재 | 단일 기준파일 배치 확인 | `data/reference/seoul_121_places.csv` | 지정 경로에 일반 파일이 존재 | 파일이 없거나 경로가 파일이 아님 | 불가 | EG-1 사전검증, EG-3 이후 |
| `H-102` | CSV 인코딩 읽기 | UTF-8과 UTF-8 BOM 수용 | 공식 CSV | BOM 유무와 관계없이 `encoding="utf-8-sig"`, `newline=""`로 오류 없이 읽힘 | UTF-8 디코딩 또는 CSV 읽기 오류 | 불가 | EG-1, EG-3 이후 |
| `H-103` | CSV 필수 컬럼 | 기준 스키마 확인 | 공식 CSV | `CATEGORY`, `NO`, `AREA_CD`, `AREA_NM`, `ENG_NM`의 정확한 5개 헤더가 이 순서로 존재 | 추가·이름 없는 컬럼, 순서 변경 또는 한 개 이상 누락 | 불가 | EG-1, EG-3 이후 |
| `H-104` | CSV 121행 | 전체 장소 수 확인 | 공식 CSV | 헤더 제외 정확히 121행 | 121행이 아님 | 불가 | EG-1, EG-3 이후 |
| `H-105` | AREA_CD 결측 | 호출 코드 결측 방지 | 공식 CSV | 모든 `AREA_CD`가 비어 있지 않음 | 한 개 이상 결측 | 불가 | EG-1, EG-3 이후 |
| `H-106` | AREA_CD 중복 | 장소코드 고유성 확인 | 공식 CSV | 모든 `AREA_CD`가 서로 고유 | 한 개 이상 중복 | 불가 | EG-1, EG-3 이후 |
| `H-107` | AREA_NM 결측 | 장소명 결측 방지 | 공식 CSV | 모든 `AREA_NM`이 비어 있지 않음 | 한 개 이상 결측 | 불가 | EG-1, EG-3 이후 |
| `H-108` | 여의도 장소코드 | 여의도 공식 코드 확인 | 공식 CSV | `AREA_NM`이 여의도인 행의 `AREA_CD`가 `POI072` | 여의도 행이 없거나 해당 행의 `AREA_CD`가 `POI072`가 아님 | 불가 | EG-1, EG-3 이후 |
| `H-109` | 장소코드 비생성 | 임의 코드 생성 방지 | 장소 Project Guard·로더, 존재하는 수집기·테스트 | 모든 대상 코드가 CSV에서만 유래하고 `NO`를 코드로 쓰지 않음 | 범위 반복·문자열 조합·`NO`로 코드 생성 | EG-1에서는 사유를 기록해 SKIP, EG-3 이후 WARN·SKIP 불가 | EG-1 SKIP, EG-3 이후 필수 |
| `H-110` | 표준 CSV 사용 | 단일 입력과 외부 의존성 금지 확인 | 장소 로더·Project Guard·의존성 파일 | 표준 `csv`와 `utf-8-sig`를 사용하고 `openpyxl` 사용·설치 없음 | 다른 장소 입력, 다른 인코딩 또는 `openpyxl` 사용·설치 | EG-1에서는 사유를 기록해 SKIP, EG-3 이후 WARN·SKIP 불가 | EG-1 SKIP, EG-3 이후 필수 |
| `H-111` | 공식 CSV 불변 | 기준파일 자동수정 방지 | 공식 CSV, EG-3 이후 Project Guard·수집기 | EG-1은 검증 직전·직후 공식 CSV의 SHA-256이 같고, EG-3 이후에는 임시 복사본의 실행 전후 SHA-256도 같으며 쓰기·보정·교체·변환 코드가 없음 | SHA-256 불일치 또는 EG-3 이후 쓰기·보정·교체·변환 동작 발견 | 불가 | EG-1, EG-3 이후 |
| `H-112` | 장소 분류 무결성 | 허용 분류와 분류별 장소 수 확인 | 공식 CSV | `CATEGORY` 결측이 없고 값이 `관광특구`, `고궁·문화유산`, `인구밀집지역`, `발달상권`, `공원` 중 하나이며 각각 7·5·48·28·33건이고 합계가 121 | `CATEGORY` 결측, 허용값 외 항목, 기대 건수 불일치 또는 합계가 121이 아님 | 불가 | EG-1, EG-3 이후 |

`H-101`부터 `H-108`, `H-111`, `H-112`까지는 EG-1의 필수 CSV 읽기 전용
사전검증 기준이다. `H-109`와 `H-110`은 판정할 코드가 없으므로 EG-1에서
사유를 기록해 `SKIP`하고, EG-3부터 PASS·FAIL 필수검사로 적용해 `WARN`이나
`SKIP`으로 처리하지 않는다. `H-111`은 EG-1에서 공식 CSV의 검증 직전·직후
SHA-256을 비교하고, EG-3부터 임시 복사본 실행과 코드 검사를 함께 수행한다.
공식 CSV 자체는 테스트 출력으로 사용하지 않는다.

### 4.3 환경변수와 보안

| 검사 ID | 검사명 | 검사 목적 | 입력 파일 | PASS 조건 | FAIL 조건 | WARN·SKIP 가능 여부 | 적용 엔지니어링 게이트 |
|---|---|---|---|---|---|---|---|
| `H-201` | `.env` Git 제외 | 비밀파일 커밋 방지 | `.gitignore`, Git 추적 목록 | `.env`가 제외되고 추적되지 않음 | 제외 규칙 누락 또는 Git 추적됨 | EG-3 전 SKIP만 가능 | EG-3 이후 |
| `H-202` | `.env.example` 계약 | 안전한 설정 안내 | `.env.example` | `SEOUL_OPEN_API_KEY` 자리표시자가 있고 실제 키가 없음 | 키 항목 누락 또는 실제 키 포함 | EG-3 전 SKIP만 가능 | EG-3 이후 |
| `H-203` | 비밀정보 노출 검사 | 코드·문서·테스트·로그의 키 유출 방지 | `.env`와 최상위 보호 `work log/`를 제외한 문서, 코드, 테스트, 샘플, 로그 | 실제 키와 인증키가 포함된 전체 URL이 없음 | 실제 키 또는 비마스킹 URL 발견 | EG-3 전 SKIP만 가능 | EG-3 이후 |
| `H-204` | 최소 `.env` 로더 | 표준 라이브러리 설정 계약 확인 | 설정 코드, 임시 `.env` fixture | 빈 줄·주석 무시, 최초 `=` 분리, 공백 제거, `SEOUL_OPEN_API_KEY` 반환, 누락·빈 값은 `config_error` | 규칙 위반, 누락을 정상 처리, 실제 키 출력 | EG-4 전 SKIP만 가능 | EG-4 이후 |
| `H-205` | URL·오류 마스킹 | 런타임 키 유출 방지 | 설정·HTTP Adapter·URL·로그·예외 코드, 가짜 키 fixture | 출력·로그·예외에 가짜 키와 완성 인증 URL이 없고 필요한 표시는 `********`로 치환 | 가짜 키 또는 완성 인증 URL이 평문으로 노출 | EG-4 전 SKIP만 가능 | EG-4 이후 |
| `H-206` | 보호 작업일지 경로 안전성 | 폐기한 저장소 작업일지 경로의 재유입과 정보 노출 방지 | `.gitignore`, 보호 경로 존재 여부, Git Index·Working Tree·Base·Head 메타데이터 | 병합 후에는 디렉터리·추적·미추적·Stage·Working Tree 항목이 모두 0이고 보호 가상 probe만 ignore되며 일반·유사·중첩·로그·정상 프로젝트 probe는 ignore되지 않음. Issue #47 삭제 전환 중에는 기존 추적 항목 전부가 이름 비노출 삭제 Diff인 경우만 한시적으로 허용하며 Base→Head도 deletion-only여야 함 | 경로 재생성, 추적·미추적·Stage·신규 Commit 항목 존재, 정확 규칙과 함께 존재하는 추가 광범위 ignore, 안전한 비교 불가 또는 Git 원본 출력 가능성 | EG-3 이후 WARN·SKIP 불가 | EG-3 이후 |

EG-3까지는 실제 `.env`와 실제 인증키를 사용하지 않는다.
EG-3 Project Guard는 임시 `.env` fixture와 가짜 키만 사용하고 네트워크를 호출하지 않는다.
실제 `.env`와 인증키는 EG-3 오프라인 Project Guard 통과 및 별도 PM 외부 실행 승인 후에만 사용한다.
H-203·H-305·H-401은 최상위의 정확한 `work log/` 디렉터리를 순회 대상에서
제거하며, 같은 이름이 아닌 다른 로그·문서 디렉터리의 기존 검사는 유지한다.
H-206은 보호 경로를 열거나 순회하지 않고 존재 여부와 캡처된 Git 메타데이터의
상태·개수만 판정한다. Git stdout·stderr와 내부 파일명·내용은 보고하지 않는다.
`.gitignore`의 정확한 최상위 규칙은 하나만 존재해야 하며 복수의 가상 probe로
유사·중첩·일반 로그와 다른 정상 프로젝트 경로까지 제외하는 추가 광범위 규칙을
거부한다. 실패 근거는 probe 상세 경로나 Git 오류 원문이 없는 고정 문구만 사용한다.
정상 병합 상태에서는 보호 경로 항목이 0이어야 하며, Issue #47의 승인된 삭제
Diff는 모든 기존 항목이 삭제-only인 전환 상태로만 구분해 허용한다.
H-206은 EG-3 이후 활성 상태로 `SKIP`할 수 없고 현재 Project Guard는 `TOTAL=47`이다.

### 4.4 샘플 JSON과 오프라인 실행

여의도 샘플 JSON의 기준 경로는 다음과 같다.

```text
data/samples/population_yeouido_sample.json
```

이 파일은 공식 여의도 실응답 샘플이며 현재 배치돼 있다. `tests/fixtures/`는
결측 필드, 잘못된 JSON, 빈 예측 배열 등 오류 테스트 입력에만 사용한다.
공식 실응답 샘플을 `tests/fixtures/`로 이동하거나 복사하지 않는다.

| 검사 ID | 검사명 | 검사 목적 | 입력 파일 | PASS 조건 | FAIL 조건 | WARN·SKIP 가능 여부 | 적용 엔지니어링 게이트 |
|---|---|---|---|---|---|---|---|
| `H-301` | 샘플 JSON 존재·문법 | 반복 가능한 오프라인 입력 확보 | 기준 경로의 여의도 샘플 JSON | 파일이 존재하고 표준 `json` 파싱 성공 | 미배치 또는 JSON 문법 오류 | 불가 | EG-2 사전검증, EG-3 이후 |
| `H-302` | 샘플 장소·인구 구조 | 실제 응답 기반 파서 기준 확보 | 여의도 샘플 JSON | `AREA_NM`, `AREA_CD=POI072`와 확인된 인구 필드 존재 | 핵심 장소·인구 구조 누락 | 불가 | EG-2, EG-3 이후 |
| `H-303` | 샘플 미래예측 구조 | 예측 저장 기준 확보 | 여의도 샘플 JSON | `FCST_YN=Y`이면 예측 배열과 확인된 필수 예측 필드 존재 | 표시와 구조 불일치 | 불가 | EG-2, EG-3 이후 |
| `H-304` | 샘플 비밀정보 제거 | fixture를 통한 키 유출 방지 | 여의도 샘플 JSON | 실제 키와 인증키 포함 URL이 없음 | 비밀정보 발견 | 불가 | EG-2, EG-3 이후 |
| `H-305` | Project Guard·테스트 오프라인 | 일반 검사에서 실 API 호출 방지 | 승인 HTTP Adapter, Project Guard, 테스트, 테스트 설정 | 네트워크 가능 코드는 승인 Transport에만 있고 Project Guard·테스트는 샘플·가짜 응답으로 DNS·소켓·HTTP 접근 0회 | 승인 경계 밖 네트워크 코드, import·module-level 실행 또는 자동검사 중 네트워크 접근 | EG-3 전 SKIP만 가능 | EG-3 이후 |

네트워크 가능 표준 모듈은 `freshmanager/http_adapter.py`의 승인된 Transport
구현에서만 허용한다. `scripts/`, `tests/`, 다른 제품 모듈과 Adapter의 module-level
실행은 FAIL이다. H-305는 AST 경계 검사와 Unit Tests의 DNS·소켓·HTTP 동적 차단을
함께 사용하며 Project Guard 자체는 실제 Adapter를 실행하지 않는다.

경로 변경 전 `H-301`은 문서의 공식 경로와 실제 파일 경로가 달라 FAIL이었다.
공식 경로를 위 파일로 통일한 뒤 같은 파일을 읽기 전용으로 재검증한 결과
`H-301`부터 `H-304`까지 PASS이며 공식 샘플은 변경되지 않았다.

### 4.5 Project Guard 자체와 Python

| 검사 ID | 검사명 | 검사 목적 | 입력 파일 | PASS 조건 | FAIL 조건 | WARN·SKIP 가능 여부 | 적용 엔지니어링 게이트 |
|---|---|---|---|---|---|---|---|
| `H-401` | Python 문법 | 기본 실행 가능성 확인 | 프로젝트의 모든 `*.py` | 표준 컴파일 검사 성공 | 한 개 이상 문법 오류 | EG-3 전 SKIP만 가능 | EG-3 이후 |
| `H-402` | 검사 ID 등록 정합성 | 이 문서를 유일한 ID 기준으로 유지 | 이 문서, Project Guard 코드 | 이 문서의 ID가 중복 없이 한 번씩 등록되고 미정의 ID 없음 | 누락·중복·미정의 ID | EG-3 전 SKIP만 가능 | EG-3 이후 |
| `H-403` | 상태·건수 정합성 | 결과 보고 오류 방지 | Project Guard 실행 결과 | 상태가 네 값 중 하나이며 상태별 합계가 전체 검사 수와 일치 | 잘못된 상태 또는 집계 불일치 | EG-3 전 SKIP만 가능 | EG-3 이후 |
| `H-404` | 종료 코드 계약 | 자동 판정 안정화 | Project Guard와 성공·실패·자체오류 fixture | 성공=`0`, 필수 실패=`1`, Project Guard 자체 오류=`2` | 계약과 다른 종료 코드 | EG-3 전 SKIP만 가능 | EG-3 이후 |

### 4.6 원본·메타데이터·예측·날씨

| 검사 ID | 검사명 | 검사 목적 | 입력 파일 | PASS 조건 | FAIL 조건 | WARN·SKIP 가능 여부 | 적용 엔지니어링 게이트 |
|---|---|---|---|---|---|---|---|
| `H-501` | 원본 JSON 불변·비덮어쓰기 | 원본 보존 | 원본 저장 코드, 가짜 응답, 임시 출력 | 반복 저장해도 기존 파일이 유지되고 새 파일 생성 | 기존 파일 변경·삭제·덮어쓰기 | EG-4 전 SKIP만 가능 | EG-4 이후 |
| `H-502` | 원본 파일명 계약 | 장소·요청시각 추적 | 원본 저장 코드와 임시 출력 | 파일명에 실제 `AREA_CD`, 요청시각과 `request_id` 포함 | 셋 중 하나 누락 또는 임의 코드 사용 | EG-4 전 SKIP만 가능 | EG-4 이후 |
| `H-503` | 최소 메타데이터 계약 | 수집 결과 추적 | 결과·로그 writer와 fixture | 승인된 8개 필드 존재, `raw_payload` 없음, `endpoint_name`은 논리명, `raw_file_path`는 원본 경로 | 필드 누락, 금지 필드·URL·잘못된 원본 경로 | EG-4 전 SKIP만 가능 | EG-4 이후 |
| `H-504` | 예측 스냅샷 보존 | 같은 대상시각의 다중 예측 보존 | 예측 저장 코드, 복수 스냅샷 fixture | 요청·스냅샷·대상·관측시각을 구분하고 기존 예측 유지 | 최신값 덮어쓰기 또는 시각 혼합 | EG-4 전 SKIP만 가능 | EG-4 이후 |
| `H-505` | 날씨 관측·예보 분리 | 시점 누수 방지 | 날씨 writer, 관측·예보 fixture | 서로 분리 저장하고 예보 발행·대상시각 보존, 상호 대체 없음 | 같은 CSV 혼합 또는 관측값으로 예보 대체 | EG-4 전 SKIP만 가능 | EG-4 이후 |
| `H-506` | 이상값·오류 별도 기록 | 원본 삭제·은폐 방지 | Collector, Storage, 오프라인 CLI와 7개 오류 경로 | 메타데이터 저장소가 정상이면 6개 오류를 요청별 8개 필드 JSON으로 기록하고, writer 자체 실패는 비재귀 반환-only 예외로 안전하게 종료 | 원본 변경, 오류 무기록, writer 재귀 호출, 불완전 최종 파일 또는 비밀정보 노출 | EG-4 전 SKIP만 가능 | EG-4 이후 |

`H-503`의 Issue #32 필수 필드는 `request_id`, `area_code`, `endpoint_name`,
`requested_at`, `received_at`, `http_status`, `collection_status`, `raw_file_path`다.
이 계약은 이전 최소 계약의 `parser_version`을 `received_at`으로 대체한다.

`H-506`은 `config_error`, `api_error`, `timeout`, `parse_error`,
`validation_error`와 원본 저장 단계의 `storage_error`를 검사한다. 메타데이터
저장소를 사용할 수 있으면 각 오류는 승인된 8개 필드만 가진 요청별 JSON으로
기록한다. 요청 전 오류의 `http_status`와 원본 미저장 오류의 `raw_file_path`는
`null`이며 숫자 `0`이나 임의 경로로 보정하지 않는다. 응답을 받은
`parse_error`와 `validation_error`는 받은 원본 bytes를 별도 원본 파일로 유지한다.

메타데이터 writer 자체가 실패하면 같은 writer를 재귀 호출하지 않는다. 이 예외는
`collection_status=storage_error`, `metadata_path=None`으로 반환하고 CLI는 안전한
`request_id`와 상태만 출력한 뒤 비정상 종료한다. 최종 메타데이터 파일과 불완전한
정상 확장자 파일을 남기지 않으며 API Key·인증 URL을 출력하지 않는다.

### 4.7 상권현황과 결측

| 검사 ID | 검사명 | 검사 목적 | 입력 파일 | PASS 조건 | FAIL 조건 | WARN·SKIP 가능 여부 | 적용 엔지니어링 게이트 |
|---|---|---|---|---|---|---|---|
| `H-601` | 상권현황 표현 | 소비활동 대리변수 과대해석 방지 | 파서 출력, 분석 데이터, 로그, README | 카드소비 기반 소비활동 대리변수로만 표현 | 실제 매출·판매실적·구매전환율로 표현 | EG-4 전 SKIP만 가능 | EG-4 이후 |
| `H-602` | 상태값 구분 | 미지원·결측·실제 0 혼동 방지 | 파서, 세 상태의 가짜 응답 | `not_supported`, `missing`, `0`을 구별하고 앞의 두 값을 `0`·`한산`으로 변환하지 않음 | 상태 병합 또는 임의 변환 | EG-4 전 SKIP만 가능 | EG-4 이후 |

### 4.8 단계별 수집과 배치

| 검사 ID | 검사명 | 검사 목적 | 입력 파일 | PASS 조건 | FAIL 조건 | WARN·SKIP 가능 여부 | 적용 엔지니어링 게이트 |
|---|---|---|---|---|---|---|---|
| `H-701` | 여의도 1장소 | 첫 수집 단위 확인 | 공식 CSV, 샘플·가짜 응답, 결과·로그 | CSV의 `POI072` 한 건만 처리하고 원본·정규화·상태 결과 생성 | 다른 코드, 0건·복수건 또는 결과 누락 | EG-4 전 SKIP만 가능 | EG-4 이후 회귀 |
| `H-702` | EG-5 대표 3장소 | 소규모 확대 검증 | 공식 CSV, `freshmanager/eg5.py`, 가짜 응답과 임시 결과·로그 | `POI019`, `POI013`, `POI014`가 공식 CSV의 코드·장소명과 일치하고 고정 순서로 각각 1회 처리되며 `stages/eg5_representative_3` 아래에 분리 저장 | 임의 코드, 순서·장소명·대상 수 불일치 또는 전용 단계 밖 저장 | EG-5 전 SKIP만 가능 | EG-5 이후 |
| `H-703` | EG-6A 13지역 참조데이터 | 승인되지 않은 Area·Spot·센서 연결의 실행 유입 방지 | 공식 CSV, `eg6_area_panel.csv`, `eg6_spot_master.csv`, `eg6_sdot_links.csv` | 정확한 헤더와 13개 제안행, 13개 서로 다른 공식 Area 승인, 고유 Spot, 모든 활성 Spot의 공식 Area 참조, 서울 좌표 기본범위, 최근 활성 센서와 역 중심 대리좌표 거리별 S-DoT 등급, 비밀정보·URL·로컬 절대경로 없음 | 필수 CSV·헤더 누락, 중복, 승인 수 불일치, 잘못된 Area 참조·Enum·좌표·센서 등급, 서울시 범위 밖 활성 Spot 또는 민감 경로·정보 포함 | EG-6A 전 SKIP만 가능 | EG-6A 이후 |
| `H-704` | 실패 격리·재시도 제한 | 한 장소 실패의 전체 중단 방지 | 가운데 장소 실패를 삽입한 가짜 응답, EG-5 코드·결과·로그 | 실패한 장소를 재호출하지 않고 다음 장소를 처리하며 세 장소를 각각 최대 1회 처리하고 `retry_count=0` | 실패 후 즉시 전체 중단, 한 장소 재호출 또는 재시도 수 불일치 | EG-5 전 SKIP만 가능 | EG-5 이후 |
| `H-705` | 회차 결과 요약 | 성공·실패 추적 | 정상·부분실패 가짜 회차의 결과·로그 | 두 회차 모두 대상=성공+실패이며 실패 수·실패 목록·종료코드가 실제 처리 결과와 일치 | 집계 누락, 대상≠성공+실패, 실패 목록 또는 종료코드 불일치 | 실제 승인 호출에서 실패가 1건 이상이고 집계·목록이 정확하면 WARN, EG-5 전 SKIP 가능 | EG-5 이후 |
| `H-706` | EG-6B 13지역 1회 완전성 | 승인 Batch ID와 패널의 단일 순차수집 검증 | 공통 Batch ID validator, 승인된 EG-6A Area 패널, 단일 회차 결과·로그 | PM 승인 형식의 Batch ID를 변경 없이 Log·Manifest에 전파하고 승인된 13개 Area를 중복·누락 없이 각각 최대 1회 시도하며 소요시간·성공·실패를 기록 | Batch ID 누락·변경·불일치, 대상 누락·중복·임의 코드, 재시도 또는 소요시간 미기록 | EG-6B 전 SKIP만 가능 | EG-6B 이후 |
| `H-707` | EG-7 반복주기 승인 준수 | 승인 없는 반복수집·임의 주기, 문서·스키마 이탈과 백업 없는 반복 실행 방지 | `freshmanager/eg7.py`, `PROJECT_STATUS.md`, `docs/data/FIELD_DICTIONARY.md`, TRD·수집규칙·Quality Gate·이 명세·Decision Log·ADR, 합성 계획·Clock·Collector·Backup 결과 | Plan v2 필드·`PM_APPROVED_FIXED`·`ACTIVE`·`LONG_TERM_OPERATING_BASELINE`·변경 불가 5분을 코드·Field Dictionary·정본 문서에서 일치시키고 1·10·15·누락·null·문자열·실수·boolean 주기와 CLI·환경 override를 거부한다. Forecast 중복은 Area별 의미 정규화 canonical 정렬 집합으로 비교하면서 Raw와 다음 계획 호출을 보존한다. `UNCONFIRMED` Live 차단과 1시간·12회차·13 Area·전체 최대 156호출·재시도 0회에서 합성 Collector와 Backup이 회차별 최대 1회 실행되고 12개 종결상태와 `LOCAL_SYNC_COPY_VERIFIED`를 기록 | 필수 정본 누락, 코드·Plan v2·Field Dictionary·정본 계약 불일치, 금지 주기·override 허용, Forecast source-order 비교, 중복 기반 다음 호출 억제·주기 변경·증거 손실, 할당량 미확인 Live 허용, 회차·Area·호출 상한·재시도·종결상태 불일치, Collector·Backup 중복 또는 검증되지 않은 Backup 성공 처리 | EG-7 구현 전 SKIP 가능, 구현 후 불가 | EG-7 이후 |
| `H-708` | Backup Worker 로컬 복사 무결성 | 완료 Batch의 안전한 동기화 폴더 복사와 원격 완료 오표현 방지 | `freshmanager/backup.py`, 성공·부분실패 Fake Batch, 임시 Sync·Ledger Root | 성공·증거 완결 부분실패 Batch가 파일 수·크기·Manifest SHA-256 검증 후 게시되고 동일 Batch는 멱등 성공, 상이한 내용은 `CONFLICT`, Receipt는 비민감하며 Worker가 원격 완료 상태를 생성하지 않음 | 불완전 복사 성공 처리, 해시·파일 수 불일치 미검출, 덮어쓰기, 민감 경로 기록, Collector·네트워크 호출 또는 원격 완료 상태 생성 | 구현 전 SKIP 가능, Backup Worker 구현 후 불가 | Backup Readiness 이후 |

`H-702`, `H-704`, `H-705`는 EG-5부터 활성화한다. `H-703`은 EG-6A 참조데이터
구현부터 활성화하며 13개 승인행의 공식 Area 코드 고유성, Area–Spot 연결과 역 중심
대리좌표 기준 S-DoT 분류를 PASS·FAIL로 판정한다. H-705의 가짜 부분실패는
실패 격리와 집계 정합성을 검증하기 위한 입력이므로 조건을 충족하면 `PASS`다.
실제 승인 호출 결과의 실패는 집계가 정확해도 `WARN`으로 별도 보고한다.
`H-701`부터 `H-708`까지의 일반 테스트는 샘플 또는 가짜 응답만 사용한다.
PM 승인된 실제 호출은 별도 수동 단계이며 Project Guard가 호출을 시작하면 `H-305`는 FAIL이다.

---

## 5. 현재 적용 상태

- EG-0: 통과, PM 승인 완료
- EG-1: 공식 CSV 정비·`main` 반영 및 읽기 전용 재검증 완료로 통과
- EG-2: 공식 샘플 배치 및 `H-301`~`H-304` PASS로 통과
- EG-3: `scripts/project_guard_check.py` 구현 및 로컬 검증 완료
- EG-4: POI072 오프라인 수집기, 명시적 Transport 기반 HTTP Adapter와 단일 실행
  CLI를 `main`에 반영했다. Issue #43에서 PM 승인 범위의 실제 POI072 정상 JSON
  수집과 원본·메타데이터 저장을 확인해 EG-4를 통과했다.
- EG-5: 대표 3장소 실제 수집과 데이터 구조·Feature 분석을 완료했다.
- EG-6A: 13개 서비스 지역 제안, Area 매핑, Spot과 S-DoT 연결 참조데이터를 구현해
  PR #52로 `main`에 반영하고 통과했다.
- EG-6B: 13개 Area 단일 순차수집·실패 격리·Batch Log·Manifest·SHA-256 구현,
  첫 실제 Batch 13/13·품질·백업 무결성·PM 원격 동기화 확인과 Closeout을 완료했다.
- EG-7: PM이 5분을 장기 기준으로 확정했고 Issue #70에서 첫 1시간 Controller·파생
  인덱스를 오프라인 구현해 H-707을 활성화했다. 실제 날짜·시각·운영시간대·할당량·
  운영 ID와 PM Live 승인은 열려 있으며 실제 반복수집은 수행하지 않았다.
- EG-8: 미진행

현재 `H-206`, `H-702`, `H-703`, `H-704`, `H-705`, `H-706`, `H-707`, `H-708`을
활성화한다. 총 검사 ID는 47개다.
`H-504`, `H-505`, `H-601`, `H-602`는 Issue #32 결정에 따라 계속 `SKIP`한다.
정확 규칙 외의 광범위 ignore는 허용하지 않으며 보호 Git 상태는 원본 stdout·stderr를
출력하지 않고 Boolean·개수로만 보고한다.

표준 실행 명령은 `python3 scripts/project_guard_check.py`다.
