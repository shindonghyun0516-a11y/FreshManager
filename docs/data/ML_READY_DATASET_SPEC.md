# ML-ready Dataset Spec

- 문서 상태: Draft
- 버전: v0.7.4
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-24
- 최종 수정일: 2026-07-31
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - `AGENTS.md`
  - `docs/testing/QUALITY_GATES.md`(EG-8A/EG-8B 진입·통과조건 정본)
  - `docs/rules/DATA_COLLECTION_RULES.md`(§3.6 v3 source sheets 읽기 전용 원칙)
  - `docs/data/FIELD_DICTIONARY.md`(EG-6B/EG-7 원본·메타데이터 필드 정본)
  - `docs/analysis/ANALYSIS_PLAN.md`(EDA·Forecast 평가·Baseline 방법론)
  - `docs/engineering/FreshManager_TRD_v1.0.md`(§14 목표 정규화 데이터 모델 요약)
  - `etc/데이터수집 실행 가이드.md`(§8 v3 sheets 수동 Export 실행 절차)
  - `ai-context/DECISION_LOG.md`의 D-015
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 EG-8A(Python Loader·정규화·데이터 품질)와 EG-8B(Feature Dataset 구성)가
`Spreadsheet v3 source sheets`에서 Python 분석·ML에 사용할 데이터셋으로 변환하는
계약을 정의한다. `docs/data/FIELD_DICTIONARY.md`가 EG-6B/EG-7 로컬 Python
수집기의 원본·메타데이터 필드를 소유하는 것과 별도로, 이 문서는 Apps Script
Runtime이 쓰는 v3 source sheets를 입력으로 하는 ML-ready 데이터셋의 스키마·버전·
품질 계약만 소유한다.

## 2. 현재 구현 상태

- Python Loader·Schema Validation·Normalization: `IMPLEMENTATION_AVAILABLE_ON_MAIN`
- Quality Report·Dataset Manifest·최종 Output Writer:
  `IMPLEMENTATION_AVAILABLE_ON_MAIN`
- EG-8A Gate: `IN_PROGRESS`
- 공식 EG-8C Dataset·Manifest: `AVAILABLE_AS_EXTERNAL_IMMUTABLE_OUTPUT`
- EG-8C 모델 비교: `COMPLETED` · 서울시 Forecast
  `BASELINE_RETAINED` · 자체 ML `NOT_ADOPTED`
- Production Model·Serving·Registry·Monitoring: `NOT_IMPLEMENTED`

이 문서는 Dataset 계약을 소유하며 변동하는 Run·Issue·PR 상태는
`PROJECT_STATUS.md`를 단일 기준으로 확인한다. 기존 공식 Dataset Profile과 신규
공식 재평가 Dataset Profile은 서로 다른 불변 Run으로 공존하며, 신규 Profile이
기존 Profile을 수정·삭제·대체하지 않는다. 공식 Dataset·Manifest와 모델 비교
산출물은 저장소 밖 실행 Output이며 Git에 추적하지 않는다.

## 3. 입력 Source와 용어

입력은 `PoC 상시 수집 Runtime`(Apps Script, `ACTIVE`)이 쓰는 다음 세 탭이다.

- `raw_log_v3`
- `population_current_v3`
- `population_forecast_v3`

Source 역할은 다음처럼 구분한다.

| Source Type | 역할 |
|---|---|
| `SPREADSHEET_V3_SOURCE` | 읽기 전용 원본 입력 |
| `GIT_TEST_FIXTURE` | 합성 정상·오류·경계 시험 입력이며 운영 증거가 아님 |
| `EXTERNAL_IMMUTABLE_DATASET_OUTPUT` | 저장소 밖 공식 Dataset·Manifest Run; no-overwrite |
| `EXTERNAL_MODELING_OUTPUT` | 잠정 모델 비교 산출물; Production Model이 아님 |

이 문서와 후속 구현에서는 다음 용어만 정본으로 사용한다.

- `Spreadsheet v3 source sheets`
- `v3 source sheets`
- `Apps Script collection runtime`

`Google Sheets v3`는 정본 용어로 사용하지 않는다. 저장소 안 유일한 "Google
Sheets" 용례는 SUPERSEDED된 TRD ADR-08("Google Sheets 수집 미채택")뿐이며,
현재 ACTIVE Runtime은 "Apps Script"/"Spreadsheet"로만 표현한다(D-014, TRD
ADR-15).

### 3.1 V0 Loader 입력 방식(PM 결정)

EG-8A Loader V0의 입력 방식은 **수동 Spreadsheet CSV Export**로 확정한다.
대상은 `raw_log_v3`·`population_current_v3`·`population_forecast_v3` 세
시트 각각의 CSV Export 파일이다. 수동 Export는 초기 Schema 확인과 Loader
V0 검증을 위한 읽기 전용 Snapshot 방식이며, 실제 Export 절차는
`etc/데이터수집 실행 가이드.md` §8이 소유한다.

V0 범위에서 사용하지 않는 방식:

- Spreadsheet 공개 게시 URL
- Python의 Google Spreadsheet 직접 접근(Google Sheets API)
- Google OAuth·서비스 계정·신규 Google Secret
- Apps Script Export 기능 추가·Trigger 수정
- EG-6B·EG-7 직접 Seoul API 산출물을 v3 sheets 샘플의 대체로 사용 — 두
  Runtime은 서로 다른 파이프라인이며 필드 체계가 다르다

장기 자동화 방식(위 제외 후보 포함)은 V0 검증 결과를 확인한 뒤 별도 PM
결정으로 검토한다. 이 결정은 §12/§12.1의 출력 형식·구성과 독립적이다.

## 4. 필수 원칙

- v3 source sheets는 **읽기 전용**으로만 접근한다.
- 원본 행을 수정하지 않는다.
- 원본 행을 삭제하지 않는다.
- 원본 행의 정렬을 변경하지 않는다.
- Raw와 정제 데이터를 분리한다. 정규화 작업은 Raw를 덮어쓰지 않고 별도
  데이터셋으로 파생한다.
- 중복 관측은 Raw(v3 source sheets)에서 삭제하지 않는다. 후속 데이터셋에서
  `duplicate_flag`로 표시한다.
- 모든 시각은 `Asia/Seoul`(KST) 기준으로 통일한다.
- 동일 입력에서 동일 출력을 재현할 수 있어야 한다(실행 재현 가능성).
- 데이터셋마다 버전을 기록한다.

이 원칙은 `docs/rules/DATA_COLLECTION_RULES.md` §3.6이 이미 정의한 v3 source
sheets 읽기 전용 원칙과 동일하며, 이 문서는 그 원칙을 스키마 수준에서
구체화한다.

### 4.1 V0 실행 방식(PM 결정)

Loader V0은 전체 Snapshot 단위의 결정적(deterministic) 변환으로
구현한다.

- 입력은 §3.1의 CSV Snapshot 전체다.
- 입력 파일을 수정·삭제·재정렬하지 않는다.
- 실행마다 새 `dataset_version`을 생성하고 기존 출력을 덮어쓰지 않는다.
- 동일 입력 + 동일 Loader 버전이면 항상 동일 출력을 생성한다(재현
  가능성).
- 입력·출력 파일의 SHA-256을 Manifest에 기록한다(§12.1).

V0에서는 증분 적재를 구현하지 않는다. 다음은 후속 `OPEN_DECISION`이다.

- 증분 적재 방식
- 마지막 처리행 추적
- Overlapping Export(중복 구간) 처리
- 자동 Snapshot 생성
- 주기적 Loader 실행

이 절은 위 필수 원칙의 읽기 전용·비덮어쓰기·재현 가능성을 V0 실행 범위에서
구체화한 것이며 새 원칙을 추가하지 않는다.

## 5. 시간 필드

다음 세 시각을 명확히 구분한다.

| 필드 | 의미 |
|---|---|
| `called_at` | Apps Script가 서울시 API를 호출한 시각 |
| `observed_at` | 응답이 가리키는 관측 기준시각(현재값의 경우 `PPLTN_TIME` 기반) |
| `forecast_at` | Forecast 레코드가 가리키는 미래 대상시각(`FCST_TIME` 기반) |

Forecast 평가에서 다음을 금지한다.

- 호출시각(`called_at`)과 관측시각(`observed_at`)을 혼동하는 것
- Forecast 생성시각과 Forecast 대상시각(`forecast_at`)을 혼동하는 것
- 미래 `forecast_at` 시점의 정보를 그 이전 시점의 Feature에 사용하는 것
- 시간 순서를 무시한 Join(예: 미래 레코드를 과거 Feature와 임의로 연결)

이 금지 원칙은 `docs/analysis/ANALYSIS_PLAN.md` §26 "미래정보 누수 금지"와
동일한 원칙을 데이터셋 스키마 수준에서 반복한 것이며, 서로 다른 규칙을
정의하지 않는다.

### 5.1 시간 표현 규칙과 검증(실 데이터 확인)

- Raw 계층(`raw_log_v3`)과 Normalized Source(`population_current_v3`/
  `population_forecast_v3`)는 원본 시간 표현을 그대로 유지한다. 실제 v3
  sheets 샘플에서 `observed_at`/`forecast_at`는 시(hour)가 한 자리일 때
  0-padding이 없는 형태(예: `2026-07-24 0:35`)로 관측됐다 — Loader가 이
  표현을 임의로 통일하지 않고 그대로 반출한다.
- Loader가 만드는 Normalized(§12.1 산출물) 계층에서만 ISO 8601 형식으로
  표준화한다.
- 검증 규칙: `forecast_at`는 반드시 `observed_at`보다 이후여야 한다
  (`forecast_at > observed_at`). 위반 시 Data Quality Error로 분류한다
  (§11 "시간 순서 위반").
- 실제 v3 sheets 샘플(Forecast 19,032행)에서는 이 조건을 100% 충족했다.
  이 확인은 2026-07-24 하루·122회차 표본 기준이며, 장기간 반복 관측에서도
  항상 성립한다고 확정하지 않는다.
- Source 해석: `called_at`/`observed_at`/`forecast_at`의 원본 문자열은
  timezone Offset이 없지만 전부 `Asia/Seoul`(KST) 기준이다(§4가 이미
  정의한 원칙과 동일하며 새 규칙을 추가하지 않는다).
- Normalized 출력 계약: ISO 8601이며 명시적 Offset을 포함한다(예:
  `2026-07-24T01:06:06+09:00`). UTC로 임의 변환하지 않고, Offset이 없는
  naive datetime으로 출력하지 않는다.
- 파싱 방법: 고정폭 문자열 슬라이싱을 금지하고 `datetime.strptime` 등
  포맷 기반 파싱만 사용한다 — 위 첫 항목처럼 `observed_at`/`forecast_at`의
  시(hour) 자릿수가 15자/16자로 혼재하기 때문이다.
- 필드 의미(§5 표와 동일, 재정의 아님): `called_at`=API 호출 실행 시각,
  `observed_at`=현재 인구 데이터 기준시각, `forecast_at`=예측 대상시각.
- `called_at`이 `observed_at`보다 늦는 것(수집 지연)은 그 자체로 오류가
  아니다. Quality Metric으로만 산출하며(§10 "수집 지연"), 임계값은 §13에
  따라 계속 `OPEN_DECISION`이다.

## 6. 데이터 계층

실제 v3 sheets CSV Export(2026-07-24, 122회차)로 확인한 결과, 세 시트는
균등한 Raw가 아니다. `raw_log_v3`만 순수 Raw이며, `population_current_v3`/
`population_forecast_v3`는 Apps Script가 이미 1차 파싱해 필드명을 통일한
**Normalized Source**다.

| 계층 | 정의 | 대응 시트 |
|---|---|---|
| Raw | Apps Script가 서울시 API 원본 응답 전문을 그대로 기록한 계층. 셀 값을 변형하지 않는다 | `raw_log_v3`(원본 JSON 전문 포함) |
| Normalized Source | Apps Script가 원본 응답에서 1차 파싱해 필드명을 통일한 계층. Python Loader의 **입력**이며 Python이 만든 산출물이 아니다 | `population_current_v3`·`population_forecast_v3` |
| Feature | 시간·시계열·변화율·Baseline 비교용 Feature가 추가된 계층(EG-8B 산출물) | 후속 EG-8B |

Python Loader의 책임은 CSV Schema Validation·Quality Validation·Dataset
생성이다(출력 구성은 §12.1). Normalized Source를 새로 파싱하지 않고 검증·
정렬해 Loader 출력을 만들며, 필요하면 `raw_log_v3`(Raw)와 대조해 정합성을
확인할 수 있다. 세 시트 모두 읽기 전용으로만 접근하며 원본 셀 값을 변형하지
않는다.

## 7. Current Population 필드 후보

| 필드 | 의미 | 실제 상태 |
|---|---|---|
| `collection_run_id` | Apps Script 실행 단위 식별자(D-014 근거) | `CONFIRMED_SOURCE_FIELD` |
| `called_at` | API 호출시각 | `CONFIRMED_SOURCE_FIELD` |
| `observed_at` | 관측 기준시각 | `CONFIRMED_SOURCE_FIELD`(§5.1 포맷 주의) |
| `area_code_requested` | 요청한 공식 `AREA_CD`(POI 코드). Source Correlation Key 기준(§8.1) | `CONFIRMED_SOURCE_FIELD`(§7.1) |
| `area_code_returned` | 응답이 실제로 반환한 공식 `AREA_CD` | `CONFIRMED_SOURCE_FIELD`(§7.1) |
| `area_name` | 공식 `AREA_NM` | `CONFIRMED_SOURCE_FIELD` |
| `congestion_level` | 혼잡도 | `CONFIRMED_SOURCE_FIELD` |
| `population_min` | 추정 인구 하한 | `CONFIRMED_SOURCE_FIELD` |
| `population_max` | 추정 인구 상한 | `CONFIRMED_SOURCE_FIELD` |
| `population_mid` | §9 정의의 파생 대표값 | `DERIVED_FIELD`(원본에 없음, Loader 산출) |
| `duplicate_flag` | 동일 관측의 중복 여부 | `LOADER_DERIVED_FIELD`(원본에 없음, Loader가 중복 검증 결과로 생성) |
| `error_flag` | 오류행 여부 | `LOADER_DERIVED_FIELD`(원본에 없음, Loader가 Schema·시간·Area·숫자 검증 결과로 생성) |
| `source_status` | 원본 응답 상태(success/오류 분류) | `JOINED_FROM_RAW_LOG`(Current 파일에는 없음. `raw_log_v3.result_status`를 Source Correlation Key(§8.1)로 Join) |

이 상태는 PM이 제공한 실제 v3 sheets CSV Export(2026-07-24, 122회차·13개
Area·약 10시간 12분 구간)를 기준으로 확인했다. 이 표본에는 `result_status`가
`SUCCESS`가 아닌 행이 하나도 없어, 오류·실패 응답에서 각 필드가 실제로 어떻게
나타나는지는 이 표본만으로 확인하지 못했다. 표본 기간·시나리오가 제한적이므로
장기 안정성이나 오류 경로까지 확정됐다고 표현하지 않는다.

### 7.1 `area_code` 이중 컬럼 구조(실 데이터 확인)

v3 source sheets는 `area_code`를 단일 필드로 기록하지 않는다. Current·
Forecast 두 시트 모두 다음 두 컬럼으로 분리돼 있다. `raw_log_v3`에는
`area_code_requested`만 있고 `area_code_returned`는 없다(§8.1).

| 컬럼 | 정의 |
|---|---|
| `area_code_requested` | Apps Script가 API에 요청한 대상 Area 코드 |
| `area_code_returned` | API 응답이 실제로 반환한 Area 코드(Current·Forecast에만 존재) |

Response Integrity Check(정합성 규칙):

```text
area_code_requested == area_code_returned
```

이 등식이 성립하지 않으면 Data Quality Error로 분류한다(§11 "Area 코드
불일치"). 실제 v3 sheets 샘플(Current 1,586행·Forecast 19,032행)에서는
불일치가 0건이었다. Source Correlation Key(§8.1)는 `area_code_requested`를
기준으로 한다 — `raw_log_v3`가 `area_code_returned`를 갖지 않기 때문이다.

Normalized 계층의 canonical `area_code`는 다음 규칙을 따른다.

- 두 값이 일치하는 행만 Normalized Dataset에 포함하고, canonical
  `area_code = area_code_requested`로 기록한다.
- `area_code_requested`/`area_code_returned` 두 원본 필드는 Lineage
  추적을 위해 Normalized 행에도 별도로 보존할 수 있다.
- 두 값이 다른 행은 정상 Normalized Dataset에 포함하지 않고 Error Rows로
  격리하며(§12.1), 요청값·응답값을 모두 보존한다. 둘 중 하나를 임의로
  정답으로 선택하지 않는다.

## 8. Forecast 필드 후보

| 필드 | 의미 | 실제 상태 |
|---|---|---|
| `collection_run_id` | Apps Script 실행 단위 식별자 | `CONFIRMED_SOURCE_FIELD` |
| `called_at` | API 호출시각 | `CONFIRMED_SOURCE_FIELD` |
| `observed_at` | 예측 스냅샷을 확보한 시점의 관측 기준시각 | `CONFIRMED_SOURCE_FIELD`(§5.1 포맷 주의) |
| `forecast_at` | 예측 대상시각 | `CONFIRMED_SOURCE_FIELD`(§5.1 포맷 주의·검증 규칙) |
| `area_code_requested` | 요청한 공식 `AREA_CD`. Source Correlation Key 기준(§8.1) | `CONFIRMED_SOURCE_FIELD`(§7.1) |
| `area_code_returned` | 응답이 실제로 반환한 공식 `AREA_CD` | `CONFIRMED_SOURCE_FIELD`(§7.1) |
| `area_name` | 공식 `AREA_NM` | `CONFIRMED_SOURCE_FIELD` |
| `forecast_congestion_level` | 예측 혼잡도 | `CONFIRMED_SOURCE_FIELD` |
| `forecast_population_min` | 예측 인구 하한 | `CONFIRMED_SOURCE_FIELD` |
| `forecast_population_max` | 예측 인구 상한 | `CONFIRMED_SOURCE_FIELD` |
| `forecast_population_mid` | 예측 대표값(§9와 동일 계산식) | `DERIVED_FIELD`(원본에 없음, Loader 산출) |
| `duplicate_flag` | 동일 대상시각 예측의 중복 여부 | `LOADER_DERIVED_FIELD`(원본에 없음, Loader가 중복 검증 결과로 생성) |
| `error_flag` | 오류행 여부 | `LOADER_DERIVED_FIELD`(원본에 없음, Loader가 Schema·시간·Area·숫자 검증 결과로 생성) |
| `source_status` | 원본 응답 상태 | `JOINED_FROM_RAW_LOG`(Forecast 파일에는 없음. `raw_log_v3.result_status`를 Source Correlation Key(§8.1)로 Join) |

상태 확인 근거와 표본 한계는 §7의 확인 문단과 동일하다(중복 서술하지
않는다).

### 8.1 Source Correlation Key와 Response Integrity(실 데이터 확인)

세 v3 sheets(`raw_log_v3`·`population_current_v3`·`population_forecast_v3`)
전체를 연결하는 정식 Source Correlation Key는 다음과 같다.

```text
collection_run_id + area_code_requested
```

**`area_code_returned`가 아니라 `area_code_requested`를 쓰는 이유**:
`raw_log_v3`에는 `area_code_returned` 컬럼 자체가 없다(§7.1). Current·
Forecast 두 시트만 보면 두 Key 후보가 같은 결과를 내지만(불일치 0건이기
때문, 아래 참조), `raw_log_v3`까지 포함하는 세 시트 공통 Key는
`area_code_requested`만 가능하다.

**용도**: `raw_log_v3` ↔ `population_current_v3` 연결, `raw_log_v3` ↔
`population_forecast_v3` 연결, `population_current_v3` ↔
`population_forecast_v3` 요청 계보 연결에 모두 이 Key를 사용한다.

Response Integrity Check(`area_code_requested == area_code_returned`)는
Join Key와 별개의 검증이다(§7.1).

실제 v3 sheets 샘플(122회차·13개 Area)로 재검증한 결과:

- `(collection_run_id, area_code_requested)`는 `raw_log_v3`·
  `population_current_v3`에서 각각 정확히 1행(고유 키 1,586개)이고,
  `population_forecast_v3`에서는 키마다 정확히 12행(`forecast_at`별
  1행씩, 총 19,032행)이다. 이는 정상적인 1:12 관계이며 "중복 요청"이
  아니다.
- 세 파일의 `(collection_run_id, area_code_requested)` 키 집합은 완전히
  동일하다(어느 방향으로도 누락 없음).
- `area_code_requested`≠`area_code_returned` 불일치는 Current·Forecast
  모두 0건이었다(§7.1).
- 이 표본에서 `area_code_returned` 기준 Join과 `area_code_requested`
  기준 Join이 같은 결과를 낸 이유는 위 불일치가 0건이기 때문일 뿐이다 —
  구조적으로 항상 같다는 뜻이 아니며, `raw_log_v3`를 포함하는 순간
  `area_code_returned` 기준은 애초에 성립하지 않는다.

**`source_status`/`http_code` Join 가능성**: `raw_log_v3`의
`(collection_run_id, area_code_requested)` → `result_status`/`http_code`
매핑은 이 표본에서 유일하다(같은 키에 서로 다른 상태값이 없음) — 따라서
이 Key로 `source_status`(§7/§8)를 `raw_log_v3`에서 Join해 오는 것이
안전하다. `http_code`도 같은 방식으로 Join할지는 품질·추적 목적의 후속
검토 대상이다 — 이번 표본은 값이 전부 `200`뿐이라 필요성을 판단하기
어렵다.

## 9. `population_mid` 정의

```text
population_mid = (population_min + population_max) / 2
```

이 값은 실제 인구의 확정값이 아니라 서울시 API가 제공한 범위의 분석용 대표값이다.
`docs/rules/DATA_COLLECTION_RULES.md`의 `population_midpoint`와 동일한 성격의
파생필드이며 원본 필드가 아니다.

## 10. 품질 항목

- 필수 컬럼 존재 여부
- 13개 Area 코드 정합성(공식 CSV 대비)
- 요청 Area 코드와 반환 코드 일치 여부(`area_code_requested`/`area_code_returned`, §7.1)
- 시간 파싱 성공률
- 숫자형 변환 성공률
- 결측률
- 오류행 수
- 중복률
- 수집 지연(호출시각 대비 관측시각)
- Forecast 대상시각 중복
- Area별 데이터 커버리지
- 시간대별 데이터 커버리지

## 11. 오류 및 결측 분류

다음을 구분한다.

- API 오류
- HTTP 오류
- JSON 파싱 오류
- Schema 오류
- Area 코드 불일치(`area_code_requested` ≠ `area_code_returned`, §7.1)
- 필수값 결측
- 숫자 변환 실패
- 시간 변환 실패
- 시간 순서 위반(`forecast_at` ≤ `observed_at`, §5.1)

오류행을 정상 데이터에 조용히 포함하지 않는다. 오류·결측 레코드는 `error_flag`로
표시해 보존하며, `docs/analysis/ANALYSIS_PLAN.md` §14의 결측 처리 원칙(결측을
숫자 0으로 바꾸지 않음)을 그대로 따른다.

## 12. 데이터셋 출력 형식

**V0 출력 형식은 CSV·JSON(Python 표준 라이브러리)으로 확정한다.**
Parquet·`pyarrow`·`pandas`·SQLite·외부 Database·신규 Orchestrator는 V0에서
사용하지 않는다. 세부 산출물 구성은 §12.1이 소유한다.

장기·대용량 국면의 최종 정본 형식(Parquet·Database 채택 여부 포함)은 아직
확정하지 않는다.

**상태(장기 정본 형식): `OPEN_DECISION`**

후보와 특성만 기록하며 임의로 확정하지 않는다.

| 후보 | 특성 | V0 채택 |
|---|---|---|
| CSV | 표준 라이브러리로 처리 가능, 사람이 직접 열람 가능, 대용량·타입 보존에 약함 | 채택 |
| JSON | 표준 라이브러리로 처리 가능, 구조화된 리포트·Manifest에 적합 | 채택(리포트·Manifest 전용) |
| Parquet | 컬럼 지향, 압축·타입 보존 우수, 표준 라이브러리만으로는 처리 어려움 | 미채택(신규 의존성) |
| Database(SQLite 등) | 쿼리·조인 편리, 표준 라이브러리(`sqlite3`) 사용 가능, 운영 복잡도 증가 | 미채택(V0 범위 밖) |

### 12.1 V0 산출물 구성(PM 결정)

Loader V0은 다음 다섯 파일을 산출한다. 전부 Python 표준 라이브러리
(`csv`, `json`)로 작성한다.

| 산출물 | 형식 | 역할 |
|---|---|---|
| Current Population 정규화 데이터 | CSV | §7 필드 후보 기준 정규화 결과 |
| Forecast 정규화 데이터 | CSV | §8 필드 후보 기준 정규화 결과 |
| Error Rows | CSV | §11 오류·결측 분류로 격리된 행 |
| Quality Report | JSON | §10/§13 품질 항목 산출 결과 |
| Dataset Manifest | JSON | 입력·출력 파일 SHA-256, `dataset_version`, Loader 버전(§4.1) |

공식 실행의 저장 위치는 PM이 승인한 저장소 밖 기존 output-root다. Source
Snapshot과 Loader Output은 분리된 하위 경로에 두고, 실행마다 새 Run을 배타적으로
생성하며 기존 Final Dataset·Manifest를 수정·삭제·덮어쓰지 않는다. 저장소 내부
`data/`는 공식 Dataset·Manifest 공개 위치로 사용하지 않는다.

### 12.2 EG-8C 공식 Output Run 실행 경계

EG-8C 1차 Output의 공식 지원 실행 진입점은 표준 CLI
`python3 -m freshmanager.eg8c_features`와 공개 Builder
`run_eg8c_dataset_build` 두 가지다. CLI는 Builder를 호출하는 어댑터이며 별도 Final
공개 생명주기를 구현하지 않는다. 최종 공개 생명주기의 구현 진입점은 Builder 하나다.
CLI와 Library 호출 모두 세 입력과 기존
외부 Output Root, 비어 있지 않은 단일 경로 구간 Run ID, PM이 승인한 외부
Acceptance Contract를 모두 명시해야 하며, Contract가 없으면 Final 공개 전에
전용 승인 오류로 중단한다. `--error-path`는 오류 메시지 파일이
아니라 입력 Source인 `raw_log_v3.csv`를 받는다.

```bash
python3 -m freshmanager.eg8c_features \
  --current-path path/to/population_current_v3.csv \
  --forecast-path path/to/population_forecast_v3.csv \
  --error-path path/to/raw_log_v3.csv \
  --output-root path/to/existing-output-root \
  --run-id eg8c-20260726T190000-kst \
  --acceptance-contract path/to/pm-approved-acceptance.json
```

Acceptance Contract의 목적은 Dataset별 승인 수치를 제품 코드에 하드코딩하지 않고
실행마다 PM 승인값과 Staging 결과를 비교하는 것이다. 실제 Contract는 저장소에
Commit하지 않는 외부 JSON 파일이며 다음 필드를 정확히 한 번씩 포함한다.

- `contract_version`
- `expected_dataset_counts`: `candidate_row_count`, `feature_valid_row_count`,
  `label_valid_row_count`, `training_eligible_row_count`
- `expected_split_counts`: `TRAIN`, `VALIDATION`, `EXCLUDED`
- `expected_area_count`
- `expected_horizon_counts`: `60`, `180`
- `required_leakage_check_ids`, `required_leakage_violation_count`,
  `required_final_verdict`
- `required_evaluation_status`, `required_data_sufficiency_status`,
  `required_test_split_created`, `required_official_model_gate_judgment`

Contract는 모든 JSON Object 계층의 중복 Key, Version·필수/알 수 없는 Key·자료형·
음수·12개 누수검사 식별자 집합·`PASS`·위반 0·지원 상태값을 엄격히 검사한다.
정수와 Boolean은 서로 대체할 수 없다. Dataset별 개수는 외부 Contract가 소유하며
Production 상수로 두지 않는다. Builder는 Contract 파일을 이진 모드로 한 번 열어
확보한 동일 바이트로 SHA-256·크기를 계산하고 JSON을 해석한다. 따라서 Hash 계산
바이트, JSON 해석 바이트, 승인 판단 바이트는 항상 동일하다. 승인 판단은 이 불변
Snapshot에서 생성한 내부 전용 승인자료에만 연결한다.

기존 공개 Writer와 외부 호출자가 승인 완료 객체를 직접 전달하던 방식은 제거한다.
`_write_unpublished_dataset`, `_rename_run_root_exclusive`와 그 밖의 밑줄 함수·자료구조는
지원하지 않는 내부 구현 세부사항이며 다른 모듈이나 `__all__`을 통해 공식 API로
재노출하지 않는다. 내부 Writer는 호출자가 지정한 미공개 Staging 디렉터리에 8개
산출물을 작성·검증할 뿐 Acceptance Contract, 승인 표식, 외부 Output Root 또는 Final
Run 경로를 받지 않고 Rename을 호출하거나 공식 실행 완료 결과를 반환하지 않는다.

이 계약은 같은 Python 프로세스에서 임의 코드를 실행하는 악의적 호출자, 밑줄 내부
함수를 의도적으로 조합하는 공격자 또는 같은 운영체제 파일 쓰기 권한으로 표준 파일
함수를 직접 호출하는 공격자까지 기술적으로 차단하는 보안 경계가 아니다. 해당 방어가
필요하면 별도 프로세스·운영체제 계정·파일 권한 또는 서명 검증 경계를 설계해야 한다.
현재 PoC는 공식 CLI·Builder의 잘못된 사용, 승인 정의서 누락·변조·교체, 승인 기준
불일치, Final 덮어쓰기, 중간 산출물의 잘못된 공개와 일반적인 개발 실수를 방어한다.
공식 CLI·Builder 경로에서는 승인 정의서와 Pre-publish 검증을 생략할 수 없다. 이
변경은 공식 공개 안전성을 위한 의도된 Library 호환성 변경이다.

공식 Pre-publish 순서는 다음과 같다.

1. Acceptance Contract를 일반 파일·Symlink 금지 정책으로 확인하고 한 번 연 파일의
   동일 바이트, SHA-256, 크기와 파일 identity를 불변 Snapshot으로 확보
2. 동일 Snapshot 바이트의 JSON 중복 Key·자료형·상태 검증과 내부 승인자료 생성
3. 입력 3개의 SHA-256·크기·파일 identity 기록
4. 숨김 Staging Run Root 생성과 내부 Writer의 Output 7개 작성
5. 입력 3개 불변 재검증과 Manifest 작성
6. 정확한 Output 8개 확인
7. Manifest·Staging 파일 무결성, 누수검사, Dataset·Split·Area·Horizon 수치,
   Candidate·Eligible·Excluded·Train·Validation 행 식별자 집합 관계와 평가 상태를
   Contract와 대조
8. Builder의 Final 공개 경계 안에서 Acceptance Contract 존재·일반 파일·Symlink 정책·
   SHA-256·크기·파일 identity를 마지막 재검증
9. 재검증 뒤 추가 파일 읽기·쓰기·해석 없이 즉시 Run Root를 배타적 Rename으로 공개

Leakage 최종판정이 `PASS`가 아니거나 위반이 0이 아니거나 기존 12개 검사 집합이
다르면 Contract가 이를 완화할 수 없다. Candidate·Feature-valid·Label-valid·Eligible·
TRAIN·VALIDATION·EXCLUDED·Area·60/180분 Horizon 수치 또는 평가 상태가 다를 때도
Final을 공개하지 않는다. 실패 시 현재 실행의 미공개 Staging만 정리하고 기존 Final
Run은 삭제·덮어쓰지 않으며, CLI는 제한된 불일치 요약만 stderr에 출력하고 0이 아닌
종료값으로 끝난다. 한 실행에서 불일치는 정렬된 최대 10건만 표시한다. 표시 가능한
값은 정수, Boolean, `null`, 사전 정의 상태·최종판정, 공개 누수검사 식별자뿐이다.
원문 행·JSON·임의 Key/문자열·전체 경로·환경값·비밀정보·중첩 객체·배열·전체 Hash는
표시하지 않는다. 누수검사 집합 차이는 수량과 공개 식별자 최대 5개만 표시한다.
CLI 인수 오류를 포함한 모든 실패는 단일 제한 stderr 경계를 통과한다. 사용자 중단은
고정된 비민감 메시지와 종료코드 `130`으로 보고하며 전체 Traceback을 출력하지 않는다.

공개 Builder는 Output Root 부재·비디렉터리·Symlink·권한·경로 해석 오류와 그 밖의
일반 파일 작업 오류를 전용 `OfficialRunPathError`로 변환한다. Library 호출자는
전체 경로 대신 `field`와 제한된 `reason` 분류만 받는다. Acceptance Contract의
부재·비일반파일·Symlink·권한·읽기 오류는 별도 `OfficialRunAcceptanceError`로
분류한다. 두 오류 모두 사용자 홈 경로·원본 JSON·실제 데이터·환경값·비밀정보와
내부 예외 원문을 메시지에 포함하지 않으며, CLI는 기존 제한 오류 출력 규칙을 유지한다.

성공한 CLI는 실행 Evidence에 기록할 수 있도록 Acceptance Contract SHA-256을
제공한다. 이 Hash를 기존 `dataset_manifest.json`에 추가하지 않으며, 공개 산출물 8개와
각 공개 Schema는 변경하지 않는다.

이 명령의 문서화는 실제 운영 Dataset 실행 승인이 아니다. 공개 상태는 계속
`PROVISIONAL`·`PROVISIONAL_SPLIT_ONLY`·`test_split_created=false`·
`official_model_gate_judgment=null`을 유지하며, Output 발행은 공식 Model Gate 통과를
뜻하지 않는다.

## 13. 품질 Gate(EG-8A 통과 조건 연결)

EG-8A Quality Report(§12.1)가 반드시 산출해야 하는 항목과 권장 항목을
구분한다. §10의 품질 항목을 다음과 같이 분류한다.

| 분류 | 항목 |
|---|---|
| 반드시 산출 | 입력·정상·오류 행 수, Area별 행 수, 13개 Area 코드 정합성, 시간 파싱 성공률, 숫자형 변환 성공률, 결측률 |
| 권장 | 중복률, 수집 지연, Forecast 대상시각 커버리지, 요청 Area 코드와 반환 코드 일치 여부, 데이터 기간, 최초·최종 관측시각 |

구체적인 통과 임계값(예: 결측률 상한, 최소 커버리지 비율)은 아직 확정하지
않는다.

**상태(임계값): `OPEN_DECISION`**

임계값은 실제 v3 source sheets 데이터를 확인한 뒤 PM이 승인한다. EG-8A의
정성적 통과 기준(읽기 전용 접근 확인, 재현 가능성 확인, 품질 리포트에 결측·
중복·오류를 숨기지 않음)은 `docs/testing/QUALITY_GATES.md` §12.1이 소유한다.

## 14. Area-Spot-Sensor 데이터 관계(목표 계약)

`docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md`의 Spot Identity·Spatial
Evidence 계약이 참조하는 데이터 관계를 정의한다. 다음 다섯 데이터셋을 서로
다른 책임으로 분리한다.

| 데이터셋 | 책임 | 현재 상태 |
|---|---|---|
| Area 관측 데이터 | §7~§9의 Current Population·Forecast 필드 | 이 문서 §7~§9가 소유 |
| Spot 정적 마스터 | `eg6_spot_master.csv`의 Candidate Anchor Point | `Confirmed`(EG-6A 완료, `docs/product/EG6_AREA_SPOT_PANEL.md`) |
| S-DoT/Sensor 시계열 | 센서별 동적 관측값 | `FUTURE_CONTRACT`/`NOT_IMPLEMENTED`(D-005) |
| Area–Spot 관계 | `eg6_area_panel.csv`의 Area·Spot 연결 | `Confirmed`(EG-6A 완료) |
| Spot–Sensor 관계 | `eg6_sdot_links.csv`의 정적 근접 등급(`DIRECT_COVERAGE`/`NEARBY_SUPPORT`/`NO_NEARBY_SDOT`) | `Confirmed`(정적 분류만, EG-6A 완료) |

후보 필드:

| 필드 | 의미 | 상태 |
|---|---|---|
| `area_code` | 공식 `AREA_CD` | `Confirmed` |
| `spot_id` | Spot 고유 식별자 | `Confirmed`(Spot Master 존재), 값 자체는 대리 식별자 |
| `spot_name` | Spot 표시명 | `Confirmed` |
| `spot_type` | Spot 유형 | `Documented` |
| `sensor_id` | S-DoT/Sensor 식별자 | `FUTURE_CONTRACT` |
| `sensor_source` | 센서 데이터 출처 | `FUTURE_CONTRACT` |
| `spatial_support_type` | Spot-Sensor 근거 수준(`DIRECT_SENSOR`/`NEARBY_SENSOR`/`AREA_INFERENCE`/`UNSUPPORTED`) | `PLANNED`(정의는 존재, 실제 산출 로직 `NOT_IMPLEMENTED`) |
| `support_distance_m` | 센서-Spot 거리(미터) | `FUTURE_CONTRACT` |
| `sensor_observed_at` | 센서 관측 시각 | `FUTURE_CONTRACT` |
| `field_verified` | 현장검증 여부 | `Confirmed`(전부 `false`) |
| `validation_status` | 검증 상태 | `Confirmed`(전부 `FIELD_VALIDATION_REQUIRED`) |

**현재 S-DoT 동적 수집은 구현되지 않았다.** `sensor_id`·`sensor_source`·
`support_distance_m`·`sensor_observed_at`는 목표 계약이며, S-DoT 동적 Collector가
별도 승인·구현되기 전까지 실제 값을 생성하지 않는다. `spatial_support_type`은
동적 수집 구현 전까지 `AREA_INFERENCE` 또는 `UNSUPPORTED`만 산출한다(상세 원칙은
`docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md` §5.1).

### 14.1 검증된 Spot Master와 미검증 Spot Proxy

이 문서의 "Spot 정적 마스터"는 **위치 식별 정보**(좌표·명칭·Area 연결)가
`Confirmed`라는 뜻이며, 그 Spot이 **추천 가능**하다는 뜻이 아니다. 현재 13개
Spot은 위치 식별 정보는 `Confirmed`이지만 전부 `field_verified=false`인
미검증 Proxy 상태다(§7~9 필드가 아니라 Spot 자체의 상태).

- **Spot Recommendation eligibility**(어떤 Spot을 추천 대상으로 제시할 수
  있는가)와 **Spot Forecast eligibility**(어떤 Spot의 혼잡 예측을 직접
  표시할 수 있는가)는 서로 다른 기준이며, 둘 다
  `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md` §9.1/§9.2가 소유한다. 이
  문서는 그 기준이 참조하는 원본 데이터 관계만 정의하고 기준 자체를
  중복 정의하지 않는다.
- 현재 13개 Proxy Spot이 Spot Recommendation 또는 Spot Forecast에 즉시 사용
  가능하다고 표현하지 않는다.

## 15. 완료 정의

이 문서는 다음 조건을 만족해야 Draft를 벗어나 다음 개정을 검토할 수 있다.

- 입력 Source와 용어 정의
- 읽기 전용·중복 보존 원칙 정의
- 시간 필드 구분과 누수 금지 원칙 정의
- Raw/Normalized/Feature 계층 정의
- 필드 후보 목록 정의(확정 아님)
- 품질 항목과 오류 분류 정의
- 출력 형식과 품질 임계값을 `OPEN_DECISION`으로 명시
- PM 승인

## 16. 변경 이력

| 버전 | 날짜 | 변경내용 | 작성자 | 승인상태 |
|---|---|---|---|---|
| v0.7.4 | 2026-07-31 | Loader·정규화·Manifest Writer의 main 구현, 저장소 밖 기존·신규 공식 Dataset Profile의 불변 공존, EG-8C 비교 완료·서울시 Forecast Baseline 유지와 Production ML 미구현 상태를 계약과 분리해 정렬. Schema·Feature·Label·Leakage 계약은 불변 | 신동현 | PM 변경 승인 |
| v0.7.3 | 2026-07-27 | 공식 지원 경계를 CLI와 `run_eg8c_dataset_build`로 명시하고 Final 공개 생명주기는 Builder가 소유하도록 정렬. 동일 프로세스 임의 코드 실행은 현 PoC 위협 범위 밖이며 내부 Writer·Rename은 비지원 구현 세부사항임을 명시. 실제 Snapshot 함수 기반 동일 바이트·파일 교체 시험과 공개 Builder의 안전한 구조화 경로 오류 계약을 §12.2에 추가. 공개 산출물 8개와 Schema는 불변 | 신동현 | PM 결정 |
| v0.7.2 | 2026-07-27 | 공식 공개 진입점을 `run_eg8c_dataset_build` 하나로 단일화하고 기존 공개 Writer·외부 승인 객체 전달을 제거. 같은 이진 Snapshot 바이트의 Hash·크기·JSON 해석 계약, 내부 Writer의 미공개 Staging 전용 책임, Final 직전 존재·파일형식·Symlink·Hash·크기·identity 재검증 후 즉시 배타적 Rename을 §12.2에 명시. 기존 공개 산출물 8개와 Schema는 불변 | 신동현 | PM 결정 |
| v0.7.1 | 2026-07-27 | 공식 Builder의 Acceptance Contract 필수화, 전 계층 JSON 중복 Key 거부, 불변 Contract 내용과 승인 판단 연결, 행 식별자 집합 검증, Publish 경계 최종 무결성 재검증, 단일 제한 CLI 오류 경계를 §12.2에 보강. 기존 공개 산출물 8개와 Schema는 불변 | 신동현 | PM 결정 |
| v0.7.0 | 2026-07-26 | EG-8C 공식 CLI의 외부 PM 승인 Acceptance Contract 필수화, Contract 엄격 검증·실행 전후 불변, Leakage·Dataset 회귀·평가 상태의 Final Publish 전 Gate, 실패 시 미공개 Staging 전용 정리와 기존 8개 공개 Schema 불변 계약을 §12.2에 추가. 실제 Contract·Dataset·Output은 미포함 | 신동현 | PM 결정 |
| v0.6.0 | 2026-07-26 | EG-8C 공식 Output Run의 명시적 CLI, 단일 구간 Run ID, Input Hash·크기·파일 identity 전후 불변, 숨김 Run Root 전체의 배타적 Rename 공개, 미공개 Staging 전용 Cleanup, 사용자 중단 종료코드 130 계약을 §12.2에 추가. 실제 운영 Dataset Run·모델·Dependency는 미포함 | 신동현 | PM 결정 |
| v0.5.0 | 2026-07-24 | Source Correlation Key를 `area_code_returned`에서 `area_code_requested`로 정정(§8.1) — `raw_log_v3`에 `area_code_returned` 컬럼이 없어 세 시트 전체를 연결할 수 없었던 오류를 실 데이터 3-way 키 비교로 확인·수정. Response Integrity Check와 canonical `area_code` 정규화 규칙·불일치 행 Error Rows 격리 규칙을 §7.1에 추가. `duplicate_flag`/`error_flag`를 `LOADER_DERIVED_FIELD`, `source_status`를 `JOINED_FROM_RAW_LOG`로 세분화. §5.1에 KST 소스 해석·ISO 8601 명시적 Offset 출력 계약·`strptime` 기반 파싱 원칙·수집 지연이 오류가 아님을 추가 | 신동현 | PM 결정 |
| v0.4.0 | 2026-07-24 | PM이 제공한 실제 v3 sheets CSV Export(122회차)로 §7/§8 필드 후보 상태를 `CONFIRMED_SOURCE_FIELD`/`DERIVED_FIELD`/`NOT_AVAILABLE`로 갱신. `area_code`를 `area_code_requested`/`area_code_returned` 이중 컬럼으로 정정(§7.1). Current-Forecast Join Key `collection_run_id`+`area_code_returned` 확정(§8.1). §6 데이터 계층을 Raw(`raw_log_v3`)/Normalized Source(`population_current_v3`·`population_forecast_v3`)로 재정의. 시간 표현·검증 규칙 추가(§5.1). 오류 분류에 "시간 순서 위반" 추가(§11). 장기 자동화 방식·최종 정본 형식·품질 임계값은 계속 `OPEN_DECISION` | 신동현 | PM 결정 |
| v0.3.0 | 2026-07-24 | EG-8A Loader V0 입력 방식(수동 CSV Export, §3.1)·V0 실행 방식(§4.1)·V0 출력 형식과 산출물 구성(§12/§12.1)·품질 항목 반드시산출/권장 분류(§13) PM 결정 반영. 장기 자동화 방식·최종 정본 형식·품질 임계값은 계속 `OPEN_DECISION` | 신동현 | PM 결정 |
| v0.2.1 | 2026-07-24 | 검증된 Spot Master(위치 식별)와 미검증 Spot Proxy(추천 가능 여부)를 구분(§14.1), Spot Recommendation/Forecast eligibility는 RECOMMENDATION_OUTPUT_CONTRACT.md §9.1/§9.2 소유임을 명시 | 신동현 | PM 결정 |
| v0.2.0 | 2026-07-24 | Area-Spot-Sensor 데이터 관계(§14) 추가 — Spot 정적 마스터·S-DoT 시계열·Area-Spot·Spot-Sensor 관계 분리, `spatial_support_type` 후보 필드와 S-DoT 동적 수집 미구현 상태 명시 | 신동현 | PM 결정 |
| v0.1.0 | 2026-07-24 | 최초 초안 작성(EG-8A/EG-8B ML-ready 데이터셋 목표 계약) | 신동현 | PM 결정 |
