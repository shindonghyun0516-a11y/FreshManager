# Field Dictionary

- 문서 상태: Draft
- 버전: v0.1.2
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-17
- 최종 수정일: 2026-07-22
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - `AGENTS.md`
  - `docs/product/FreshManager_PRD_v1.0.md`
  - `docs/engineering/FreshManager_TRD_v1.0.md`
  - `requirements-definition-freshmanager-poc-v0.4.md` (역사 문서)
  - `docs/rules/DATA_COLLECTION_RULES.md`
  - `docs/analysis/ANALYSIS_PLAN.md`
  - `docs/data/CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md`
  - `data/reference/seoul_121_places.csv`
  - `data/samples/population_yeouido_sample.json`
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 Freshmanager Data PoC에서 사용하는 원본 필드, 정규화 필드, 수집 메타데이터 및 파생필드의 의미와 처리방법을 정의한다.

이 문서는 단순한 번역표가 아니다.

각 필드에 대해 다음을 정의한다.

- 데이터셋
- 원본 필드명
- 분석용 필드명
- 한글명
- 정의
- 출처
- JSON 경로
- 데이터 형식
- 단위
- 결측 허용 여부
- 현재값·예측값 구분
- 원본·파생 구분
- 변환 규칙
- 검증 상태
- 주의사항

---

## 2. 검증 상태

| 상태 | 의미 |
|---|---|
| `Confirmed` | 실제 API 응답 또는 공식 기준파일에서 확인 |
| `Documented` | 공식 문서나 승인된 프로젝트 문서에 정의됐으나 실응답 또는 구현 확인 전 |
| `Implemented` | 코드와 합성 오프라인 검증이 존재하나 실제 운영 데이터 확인 전 |
| `Unverified` | 아직 공식 문서나 실응답에서 확정하지 못함 |
| `Derived` | 원본 필드로 계산한 파생필드 |
| `Deprecated` | 더 이상 사용하지 않음 |
| `PLANNED` | 승인된 계획에 포함됐으나 필드 계약·구현이 아직 완료되지 않음 |
| `FUTURE_CONTRACT` | 후속 구현이 따라야 할 목표 계약이며 현재 저장 데이터에는 존재하지 않음 |
| `NOT_IMPLEMENTED` | 코드·저장·검증이 현재 존재하지 않음 |

실제 응답 또는 공식 기준파일에서 확인하지 않은 필드를 `Confirmed`로 표시하지 않는다.

---

## 3. 데이터셋 목록

| 데이터셋 | 역할 | 현재 상태 |
|---|---|---|
| `places` | 공식 121장소 기준정보 | 공식 CSV 정비·main 반영 완료, 정확한 5개 컬럼·유효 장소 121개, EG-1 PASS |
| `population_observations` | 현재 인구값 | 여의도·EG-5와 첫 EG-6B 실제 13개 Area 응답 확인 |
| `population_forecasts` | 미래 인구예측 | 여의도·EG-5와 첫 EG-6B 실제 13개 Area 응답 확인 |
| `commerce_observations` | 카드소비 기반 상권현황 | 실응답 확인 필요 |
| `weather_observations` | 날씨 관측 | 실응답 확인 필요 |
| `weather_forecasts` | 날씨 예보 | 실응답 확인 필요 |
| `collection_logs` | 수집 성공·실패 기록 | EG-6B Batch Log·Manifest 구현·첫 실제 13개 Area 회차 확인 |
| `backup_receipts` | Batch별 로컬 Sync 복사·검증 상태 | 구현·Fake/실제 Batch 검증 완료; Worker는 원격 완료 상태를 생성하지 않음 |
| `eg7_pilot_plans` | 12회차 불변 계획과 Live Gate 상태 | 구현·합성 검증 완료; 운영 계획은 생성하지 않음 |
| `eg7_execution_events` | 파일럿 상태전이 append-only 로그 | 구현·합성 검증 완료; 실제 실행 기록 없음 |
| `eg7_slot_index` | 계획 12회차의 종결·호출·Backup 파생 인덱스 | CSV·JSONL 구현·합성 검증 완료 |
| `eg7_area_observation_index` | 실제 시도 Area의 관측·Forecast·무결성·중복 파생 인덱스 | 최대 156행 CSV·JSONL 구현·합성 검증 완료 |
| `eg7_pilot_summary` | 호출·중복·시간·용량·Backup 파생 요약 | JSON 구현·합성 검증 완료 |
| `batches_csv` | 조회용 Batch 파생 CSV | 첫 실제 Batch 품질 감사 후 PLANNED |
| `area_observations_csv` | 조회용 Area 현재 관측 파생 CSV | 첫 실제 Batch 품질 감사 후 PLANNED |
| `area_forecasts_csv` | 조회용 예측 스냅샷 파생 CSV | 첫 실제 Batch 품질 감사 후 PLANNED |
| `collection_errors_csv` | 조회용 요청·Area 오류 파생 CSV | 첫 실제 Batch 품질 감사 후 PLANNED |
| `sdot_observations` | 센서 관측·시간대 변화의 독립 보조 계층 | FUTURE_CONTRACT / NOT_IMPLEMENTED |
| `spot_candidate_context` | Area·S-DoT 근접성·공간 Context·현장검증 연결 | FUTURE_CONTRACT / NOT_IMPLEMENTED |
| `spot_candidate_evaluations` | Area Feature·선택적 S-DoT Feature·Context 기반 후보 근거 평가 | FUTURE_CONTRACT / NOT_IMPLEMENTED |
| `recommendations` | SPOT 또는 AREA fallback 추천 결과 | FUTURE_CONTRACT / NOT_IMPLEMENTED |
| `derived_features` | 분석용 파생필드 | 분석계획에 따라 생성 |

---

## 4. 공통 작성 규칙

### 원본 필드

서울시 API의 필드명을 그대로 유지한다.

예:

```text
AREA_PPLTN_MIN
FCST_PPLTN_MAX
```

### 분석용 필드

분석용 필드명은 영문 소문자 snake_case를 사용한다.

예:

```text
population_min
forecast_population_max
```

### 데이터 유형

허용 예:

- string
- integer
- float
- boolean
- datetime
- categorical
- array
- object

### 시간대

날짜시간은 원본값을 보존하고 분석 시 `Asia/Seoul` 기준으로 처리한다.

---

## 5. `places` 데이터셋

원본:

```text
data/reference/seoul_121_places.csv
```

| 원본 필드 | 분석용 필드 | 한글명 | 정의 | 원본 형식 | 분석 형식 | 결측 허용 | 키 | 검증 상태 |
|---|---|---|---|---|---|---|---|---|
| `CATEGORY` | `category` | 장소 분류 | 서울시 주요 장소의 분류 | string | categorical | 아니오 | 일반 | Confirmed |
| `NO` | `place_no` | 목록 순번 | 공식 목록의 순번 | string 또는 integer | integer | 아니오 | 일반 | Confirmed |
| `AREA_CD` | `area_code` | 장소코드 | 서울시 장소 식별코드 | string | string | 아니오 | PK 후보 | Confirmed |
| `AREA_NM` | `area_name` | 한글 장소명 | 서울시가 제공한 장소명 | string | string | 아니오 | 일반 | Confirmed |
| `ENG_NM` | `area_name_en` | 영문 장소명 | 서울시가 제공한 영문 장소명 | string | string | 확인 필요 | 일반 | Confirmed |

### 장소 분류 기대값

| 분류 | 기대 건수 |
|---|---:|
| 관광특구 | 7 |
| 고궁·문화유산 | 5 |
| 인구밀집지역 | 48 |
| 발달상권 | 28 |
| 공원 | 33 |
| 합계 | 121 |

### 주요 검증값

```text
AREA_NM=여의도
AREA_CD=POI072
```

---

## 6. `population_observations` 데이터셋

샘플 원본 경로:

```text
$["SeoulRtd.citydata_ppltn"][0]
```

### 원본 응답 필수·선택 상태

공식 샘플은 성공 응답 1건이므로, 이 절과 `population_forecasts` 절의
원본 응답 필드가 모든 응답에서 항상 필수인지 여부는 `확인 필요`다.
`Confirmed`는 샘플에서 필드명, JSON 경로와 원본 형식을 확인했다는 뜻이며,
항상 필수인 필드로 확정했다는 뜻이 아니다.

`RESULT.CODE`, `RESULT.MESSAGE`, 현재 인구·인구 구성 필드,
`FCST_PPLTN`과 예측 객체 필드의 필수·선택 여부는 추가 공식 응답 또는
공식 문서 확인 전까지 `확인 필요`로 유지한다. 기존 표의 `결측 허용`은
필드가 존재할 때의 값 처리 기준이며, 응답에서의 필드 존재 의무를 확정하지 않는다.

### 6.1 응답 외피와 배열 컨테이너

다음 항목은 분석용 수치 필드가 아니라 실제 샘플에서 확인한 응답 구조다.

| 원본 항목 | JSON 경로 | 역할 | 원본 형식 | 구분 | 검증 상태 |
|---|---|---|---|---|---|
| `RESULT.CODE` | `$["RESULT"]["RESULT.CODE"]` | API 처리 결과코드 | string | 응답 외피 | Confirmed |
| `RESULT.MESSAGE` | `$["RESULT"]["RESULT.MESSAGE"]` | API 처리 결과메시지 | string | 응답 외피 | Confirmed |
| `FCST_PPLTN` | `$["SeoulRtd.citydata_ppltn"][0]["FCST_PPLTN"]` | 미래 인구예측 항목 묶음 | array | 배열 컨테이너 | Confirmed |

### 6.2 핵심 확인 필드

| 원본 필드 | 분석용 필드 | 한글명 | 정의 | 원본 형식 | 분석 형식 | 단위 | 결측 허용 | 검증 상태 |
|---|---|---|---|---|---|---|---|---|
| `AREA_NM` | `area_name` | 장소명 | 인구 데이터 대상 장소명 | string | string | 없음 | 아니오 | Confirmed |
| `AREA_CD` | `area_code` | 장소코드 | 인구 데이터 대상 장소코드 | string | string | 없음 | 아니오 | Confirmed |
| `AREA_CONGEST_LVL` | `congestion_level` | 혼잡도 단계 | 서울시가 제공한 혼잡도 범주 | string | categorical | 없음 | 확인 필요 | Confirmed |
| `AREA_CONGEST_MSG` | `congestion_message` | 혼잡도 안내문 | 혼잡도에 대한 설명문 | string | string | 없음 | 예 | Confirmed |
| `AREA_PPLTN_MIN` | `population_min` | 추정 인구 하한 | 해당 시점 추정 인구의 최소값 | string | integer | 명 | 아니오 | Confirmed |
| `AREA_PPLTN_MAX` | `population_max` | 추정 인구 상한 | 해당 시점 추정 인구의 최대값 | string | integer | 명 | 아니오 | Confirmed |
| `PPLTN_TIME` | `population_reference_time` | 인구 기준시각 | 현재 인구값이 기준으로 하는 시각 | string | datetime | Asia/Seoul | 아니오 | Confirmed |
| `FCST_YN` | `forecast_available_yn` | 예측 제공 여부 | 미래 인구예측 제공 여부 | string | boolean 또는 categorical | 없음 | 아니오 | Confirmed |

### 6.3 인구 구성 필드

다음 필드는 실제 샘플에서 필드명, 경로와 원본 형식을 확인했다.
단위와 상세 의미가 확인되지 않은 항목은 단위의 `확인 필요` 표시를 유지한다.

| 원본 필드 | 분석용 필드 | 한글명 | 정의 | 원본 형식 | 분석 형식 | 단위 | 검증 상태 |
|---|---|---|---|---|---|---|---|
| `MALE_PPLTN_RATE` | `male_population_rate` | 남성 인구 비율 | 추정 인구 중 남성 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `FEMALE_PPLTN_RATE` | `female_population_rate` | 여성 인구 비율 | 추정 인구 중 여성 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `PPLTN_RATE_0` | `population_rate_age_0` | 0대 비율 | 0~9세 인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `PPLTN_RATE_10` | `population_rate_age_10` | 10대 비율 | 10~19세 인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `PPLTN_RATE_20` | `population_rate_age_20` | 20대 비율 | 20~29세 인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `PPLTN_RATE_30` | `population_rate_age_30` | 30대 비율 | 30~39세 인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `PPLTN_RATE_40` | `population_rate_age_40` | 40대 비율 | 40~49세 인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `PPLTN_RATE_50` | `population_rate_age_50` | 50대 비율 | 50~59세 인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `PPLTN_RATE_60` | `population_rate_age_60` | 60대 비율 | 60~69세 인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `PPLTN_RATE_70` | `population_rate_age_70` | 70대 이상 비율 | 70세 이상 인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `RESNT_PPLTN_RATE` | `resident_population_rate` | 상주인구 비율 | 해당 인구 중 상주인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `NON_RESNT_PPLTN_RATE` | `non_resident_population_rate` | 비상주인구 비율 | 해당 인구 중 비상주인구 비율 | string | float | % 또는 비율 확인 필요 | Confirmed |
| `REPLACE_YN` | `replacement_yn` | 대체값 여부 | 데이터 대체 여부를 나타내는 값 | string | categorical | 없음 | Confirmed |

### 필드명 주의

최종 기준 필드명:

```text
FEMALE_PPLTN_RATE
```

여성 인구 비율은 실제 응답 필드명인 `FEMALE_PPLTN_RATE`만 사용한다.
실제 샘플 JSON을 수정하지 않고 문서와 파서가 실응답 필드를 따른다.

---

## 7. `population_forecasts` 데이터셋

샘플 JSON 경로:

```text
$["SeoulRtd.citydata_ppltn"][0]["FCST_PPLTN"]
```

| 원본 필드 | 분석용 필드 | 한글명 | 정의 | 원본 형식 | 분석 형식 | 단위 | 결측 허용 | 검증 상태 |
|---|---|---|---|---|---|---|---|---|
| `FCST_TIME` | `forecast_target_time` | 예측 대상시각 | 예측값이 가리키는 미래 시각 | string | datetime | Asia/Seoul | 아니오 | Confirmed |
| `FCST_CONGEST_LVL` | `forecast_congestion_level` | 예측 혼잡도 | 미래 혼잡도 범주 | string | categorical | 없음 | 확인 필요 | Confirmed |
| `FCST_PPLTN_MIN` | `forecast_population_min` | 예측 인구 하한 | 미래 추정 인구 최소값 | string | integer | 명 | 아니오 | Confirmed |
| `FCST_PPLTN_MAX` | `forecast_population_max` | 예측 인구 상한 | 미래 추정 인구 최대값 | string | integer | 명 | 아니오 | Confirmed |

추가 메타데이터:

| 필드 | 한글명 | 정의 | 형식 | 구분 |
|---|---|---|---|---|
| `forecast_snapshot_time` | 예측 스냅샷 시각 | 해당 예측 묶음을 수집한 시각 | datetime | 수집 메타데이터 |
| `request_id` | 요청 고유번호 | 예측을 확보한 API 요청 ID | string | 수집 메타데이터 |
| `area_code` | 장소코드 | 예측 대상 장소 | string | 키 |
| `raw_file_path` | 원본 파일 경로 | 예측 원본 JSON 위치 | string | 추적성 |
| `parser_version` | 파서 버전 | 향후 정규화·분석 데이터 저장 구현 시 검토할 파서 추적 필드 | string | 향후 제안 |

---

## 8. `collection_logs` 데이터셋

| 필드 | 한글명 | 정의 | 형식 | 결측 허용 | 검증 상태 |
|---|---|---|---|---|---|
| `request_id` | 요청 고유번호 | API 호출별 고유 식별값 | string | 아니오 | Documented |
| `area_code` | 장소코드 | 공식 CSV에서 확인한 요청 대상 장소코드 | string | 아니오 | Documented |
| `endpoint_name` | Endpoint 이름 | 인증 URL이 아닌 논리적 API 이름 | string | 아니오 | Documented |
| `requested_at` | 요청시각 | API 호출 시작시각 | datetime | 아니오 | Documented |
| `received_at` | 응답 수신시각 | 응답 수신 또는 요청 실패를 확인한 시각 | datetime | 아니오 | Documented |
| `http_status` | HTTP 상태 | HTTP 응답 상태코드 | integer | 예 | Documented |
| `collection_status` | 수집 상태 | 수집 결과 상태값 | categorical | 아니오 | Documented |
| `raw_file_path` | 원본 파일 경로 | 저장된 원본 JSON 경로 | string | 실패 시 예 | Documented |

`raw_payload`는 수집 메타데이터가 아니라 원본 응답이며,
`raw_file_path`로 저장 위치를 추적한다.

`parser_version`은 현재 `collection_logs` 최소 계약에 포함하지 않는다. 향후
정규화·분석 데이터 저장 구현 시 파서 추적 필드로 별도 검토한다.

다음 필드는 v0.1 필수 메타데이터가 아닌 선택 제안이다.

| 필드 | 제안 목적 | 검증 상태 |
|---|---|---|
| `error_type` | 실패 원인의 구조화된 분류 | Unverified |
| `error_message` | 민감정보를 제거한 오류 설명 | Unverified |

### `collection_status` 허용값

```text
success
missing
not_supported
api_error
timeout
parse_error
validation_error
storage_error
config_error
security_error
```

### 8.1 `backup_receipts` 구현 계약

Backup Receipt는 Sync Root 밖 Ledger의 append-only 사건 파일로 구현됐다. 현재
EG-6B Collection Log·Manifest에 포함되는 필드로 해석하지 않는다.

| 필드 | 의미 | 형식 | 상태 |
|---|---|---|---|
| `backup_attempt_id` | Backup Worker 실행별 UUIDv4 | string | Implemented |
| `batch_id` | 백업 대상 canonical UUID | string | Implemented |
| `backup_status` | Worker가 기록할 수 있는 복사·검증 상태 | categorical | Implemented |
| `started_at` | 백업 시작시각 | ISO 8601 datetime | Implemented |
| `completed_at` | 사건 종료시각; 진행 중이면 null | ISO 8601 datetime / null | Implemented |
| `source_file_count` | Manifest 기준 대상 파일 수 | integer | Implemented |
| `copied_file_count` | 복사한 파일 수 | integer | Implemented |
| `verified_file_count` | 복사 후 검증 통과 파일 수 | integer | Implemented |
| `source_manifest_sha256` | Source Manifest SHA-256 | string / null | Implemented |
| `logical_destination` | 비민감 논리 Backup Root | string | Implemented |
| `failure_code` | 비민감 실패 코드 | string / null | Implemented |
| `conflict_detected` | 기존 복사본 충돌 여부 | boolean | Implemented |
| `restore_test_status` | Worker 실행에서 Restore 수행 여부 | categorical | Implemented |
| `capability_warnings` | 파일시스템 능력 경고 | list[string] | Implemented |

계획 상태값:

```text
PENDING
IN_PROGRESS
LOCAL_SYNC_COPY_VERIFIED
FAILED
CONFLICT
```

`LOCAL_SYNC_COPY_VERIFIED`는 Google Drive for Desktop 동기화 폴더에 생성된 로컬
복사본의 파일 수·크기·SHA-256 검증을 완료했다는 뜻이다. 원격 Google Drive 업로드
완료를 의미하지 않는다. Worker는 `REMOTE_SYNC_PENDING`이나
`REMOTE_SYNC_CONFIRMED`를 Receipt에 생성하지 않는다.
Backup Root는 `FreshManager-Data/` 논리 구조로만 표현한다. Receipt에는 실제 Google
계정 이메일, 사용자 식별정보와 동기화 절대경로를 저장하지 않는다.

### 8.2 CSV·S-DoT·Spot Candidate·추천 미래 계약

예정 CSV와 키는 첫 실제 Batch 품질 감사 후 별도 Issue에서 확정한다.

| CSV | 고유키 후보 | 상태 |
|---|---|---|
| `batches.csv` | `batch_id` | PLANNED / NOT_IMPLEMENTED |
| `area_observations.csv` | `area_code + population_reference_time + request_id` | PLANNED / NOT_IMPLEMENTED |
| `area_forecasts.csv` | `area_code + forecast_snapshot_time + forecast_target_time + request_id` | PLANNED / NOT_IMPLEMENTED |
| `collection_errors.csv` | `request_id + area_code` | PLANNED / NOT_IMPLEMENTED |

동적 S-DoT, Spot Candidate와 추천 필드는 현재 구현되지 않았다. 아래 필드는 목표
계약이며 실제 API 응답 필드나 현행 EG-6B Metadata로 해석하지 않는다.

| 필드 | 의미 | 상태 |
|---|---|---|
| `sensor_id` | S-DoT 센서 식별자 | FUTURE_CONTRACT |
| `sensor_observed_at` | S-DoT 관측 기준시각 | FUTURE_CONTRACT |
| `sdot_activity_value` | 공식 자료에서 확인된 센서 관측값 | FUTURE_CONTRACT; 실제 필드 확인 전 이름 확정 금지 |
| `candidate_id` | Spot Candidate 식별자 | FUTURE_CONTRACT |
| `anchor_spot_id` | 후보 생성에 사용한 Spot Master Anchor 식별자 | FUTURE_CONTRACT |
| `candidate_evidence` | Area·선택적 S-DoT·공간·현장·운영 Context의 후보 평가 근거 | FUTURE_CONTRACT |
| `evaluation_version` | 후보 근거 평가 계약 버전 | FUTURE_CONTRACT |
| `candidate_score` | 정량 점수를 채택할 경우의 후보 점수 | PLANNED / OPEN_DECISION; 필수 필드 아님 |
| `score_version` | 정량 점수를 채택할 경우의 계산 계약 버전 | PLANNED / OPEN_DECISION; 필수 필드 아님 |
| `spatial_context_version` | 공간 Context 버전 | FUTURE_CONTRACT |
| `target_level` | `SPOT` 또는 `AREA` 추천 단위 | FUTURE_CONTRACT |
| `fallback_reason` | AREA fallback의 필수 이유 | FUTURE_CONTRACT |
| `target_spot_id` | SPOT 추천으로 선택한 검증된 후보 식별자 | FUTURE_CONTRACT |
| `field_verified` | 현장 검증 여부 | 참조 CSV에 존재; 추천 계약 연결은 FUTURE_CONTRACT |

S-DoT 데이터는 지원·접근·수집·품질조건을 만족할 때 Area 내부 활성 위치 판단과
후보 Feature를 보조하지만 Area 데이터를 대체하지 않는다. Area·선택적 S-DoT·공간
Context·현장검증·운영 제약으로 신뢰 가능하고 운영 가능한 Spot Candidate가 생성되면
`target_level=SPOT`을 사용한다. 후보가 없거나 근거가
부족하면 `target_level=AREA`와 `fallback_reason`을 사용한다. 현재 Spot Master의
`STATION_CENTER_PROXY`는 Candidate Anchor Point이며 검증된 판매 Spot이 아니다.
S-DoT 미지원 Area도 Area 분석과 추천 후보에서 제외하지 않는다.

---

### 8.3 EG-7 파일럿 계획·사건·파생 인덱스 계약

`freshmanager.eg7`의 모든 스키마는 버전 문자열을 포함한다. 운영 계획은 아직
생성하지 않았고 아래 구현 상태는 합성 임시 증거의 오프라인 검증을 뜻한다.

공통 표현:

- 인코딩: UTF-8
- 시각: timezone offset을 포함한 ISO 8601; 운영 시간대는 `Asia/Seoul`
- JSON·JSONL null/boolean: JSON native `null`, `true`, `false`
- CSV null/boolean: 빈 문자열, 소문자 `true`, `false`
- Enum: 문서에 정의된 대문자 문자열
- 경로: Source 단계 기준 상대경로만 허용; 절대경로 금지

`eg7_pilot_plans` 필드:

```text
schema_version, pilot_run_id, timezone, cadence_minutes,
cadence_decision_status, long_term_baseline_status, cadence_scope,
cadence_change_allowed, planned_start_at, planned_end_at,
planned_slot_count, max_api_calls, retry_count, area_count,
area_order_contract, quota_confirmation_status, live_approval_status, slots
```

계획 schema는 `eg7-pilot-plan-v2`다. `cadence_minutes=5`,
`cadence_decision_status=PM_APPROVED_FIXED`,
`long_term_baseline_status=ACTIVE`,
`cadence_scope=LONG_TERM_OPERATING_BASELINE`,
`cadence_change_allowed=false`를 정확히 요구한다. 비 5분 계획은 거부하고 임의
주기 선택 필드는 두지 않는다.

H-707이 코드와 직접 비교하는 Plan v2 canonical 계약:

| contract_key | required_value |
|---|---|
| `PLAN_SCHEMA_VERSION` | `eg7-pilot-plan-v2` |
| `PLAN_FIELDS` | `schema_version,pilot_run_id,timezone,cadence_minutes,cadence_decision_status,long_term_baseline_status,cadence_scope,cadence_change_allowed,planned_start_at,planned_end_at,planned_slot_count,max_api_calls,retry_count,area_count,area_order_contract,quota_confirmation_status,live_approval_status,slots` |
| `CADENCE_MINUTES` | `5` |
| `CADENCE_DECISION_STATUS` | `PM_APPROVED_FIXED` |
| `LONG_TERM_BASELINE_STATUS` | `ACTIVE` |
| `CADENCE_SCOPE` | `LONG_TERM_OPERATING_BASELINE` |
| `CADENCE_CHANGE_ALLOWED` | `false` |
| `ALTERNATIVE_CADENCES_SUPPORTED` | `false` |
| `DUPLICATE_TRIGGERED_CADENCE_CHANGE` | `false` |
| `RUNTIME_CADENCE_OVERRIDE` | `UNSUPPORTED` |
| `FIRST_ONE_HOUR_SELECTS_CADENCE` | `false` |
| `FORECAST_DUPLICATE_SIGNATURE` | `CANONICAL_SORTED_SET_OF_NORMALIZED_TARGET_INSTANTS` |
| `LIVE_REQUIRES_SEPARATE_PM_APPROVAL` | `true` |
| `OPERATING_WINDOW_STATUS` | `OPEN_PM_DECISION` |

각 `slots` 항목은 `slot_index`, `scheduled_at`, `batch_id`,
`planned_status`를 가진다. `quota_confirmation_status`는 기본
`UNCONFIRMED`, `live_approval_status`는 기본 `NOT_APPROVED`로 운영 계획을
작성해야 하며 두 상태를 충족하지 않으면 Live를 거부한다. 계획 지문은 정렬된
canonical JSON의 SHA-256이고 추적용이지 인증값이 아니다. 지문 입력의
`planned_start_at`, `planned_end_at`, 모든 `slots[].scheduled_at`은 기존 검증을
통과한 뒤 `YYYY-MM-DDTHH:MM:SS+09:00`으로 의미 정규화한다. 입력 JSON의 키 순서와
허용된 `T`·공백 구분자 차이는 지문을 바꾸지 않으며, 유효하지 않은 시각은
정규화로 보정하지 않고 거부한다. `plan_fingerprint` 자체, 환경값, Secret과
절대경로는 지문 입력이 아니다.

`eg7_execution_events` 필드:

```text
schema_version, pilot_run_id, plan_fingerprint, slot_index, scheduled_at,
batch_id, state_before, state_after, event_at, reason,
collector_execution_count, actual_api_call_count, backup_execution_count,
backup_status
```

Slot 종결 Enum:

```text
COMPLETED_SUCCESS
COMPLETED_PARTIAL
SKIPPED_MISSED
SKIPPED_OVERLAP
STOPPED_FATAL
NOT_RUN_AFTER_FATAL_STOP
```

`eg7_slot_index` 필드:

```text
schema_version, pilot_run_id, slot_index, scheduled_at, batch_id,
slot_status, collection_started_at, collection_ended_at,
collection_duration_ms, attempted_area_count, successful_area_count,
failed_area_count, actual_api_calls, backup_eligible, backup_status,
failure_reason
```

항상 12행이며 실행하지 않은 회차의 알 수 없는 값은 `0`으로 추정하지 않고 null로
둔다. 건너뛴 회차의 확인된 API 호출 수만 `0`이다.

`eg7_area_observation_index` 필드:

```text
schema_version, pilot_run_id, slot_index, scheduled_at, slot_status,
batch_id, request_id, panel_order, area_code, area_status, failure_reason,
requested_at, received_at, collection_started_at, collection_ended_at,
collection_duration_ms, api_observation_at, population_min, population_max,
congestion_level, forecast_record_count, forecast_first_target_at,
forecast_last_target_at, raw_relative_path, metadata_relative_path,
raw_sha256, manifest_sha256, duplicate_collection_time,
duplicate_observation_time, duplicate_raw_hash, duplicate_forecast_targets,
backup_eligible, backup_status
```

실제 시도한 Area만 최대 156행으로 기록한다. 중복 비교는 `area_code` 범위에서
수집시각, API 관측시각, Raw SHA-256, Forecast 대상시각의 의미 정규화된 canonical
정렬 집합을 각각 구분한다. Forecast signature는 각 대상시각을
`YYYY-MM-DDTHH:MM:SS+09:00`으로 정규화하고, 같은 instant를 집합 안에서 한 번만
남긴 뒤 오름차순 불변 tuple로 비교한다. 원본 Forecast 배열 순서는 비교에 사용하지
않고 Raw에서 그대로 보존한다. `spot_id`는 포함하지 않고 `area_code`를 후속
결합키로 유지한다.
이 인덱스와 Summary는 canonical Raw·Metadata·Collection Log·Manifest를
대체하거나 수정하지 않는다. 중복 플래그는 계획 호출 생략이나 5분 주기 변경
신호가 아니며 EG-8 데이터셋 제거·선별·가중치 판단에 사용한다.

`eg7_pilot_summary`는 계획·실행·건너뜀·치명중단·Area 성공실패·실제 호출·중복
건수와 비율·Forecast 구조 일관성·Collector/Backup 소요시간·Source/Backup 용량
증가·Backup 적격/검증 수·무재수집 확인을 기록한다. schema는
`eg7-pilot-summary-v2`이고 `cadence_minutes`,
`cadence_decision_status`, `long_term_baseline_status`, `cadence_scope`,
`cadence_change_allowed`,
`alternative_cadences_supported`, `duplicate_triggered_cadence_change`를 함께
기록한다. 마지막 두 값은 모두 `false`다. ML 성능은 평가하지 않는다.

---

## 9. `commerce_observations` 데이터셋

현재는 실제 상권현황 샘플 응답을 확보한 후 상세 필드를 확정한다.

현재 정의 가능한 원칙:

- 카드소비 기반 소비활동 대리변수
- 실제 야쿠르트 매출이 아님
- 프레시매니저 판매실적이 아님
- 지원 장소와 미지원 장소를 구분
- `not_supported`와 `missing`을 구분
- 숫자 0으로 대체하지 않음

### 필드 등록 전 확인사항

- 실제 루트 키
- 배열 또는 객체 구조
- 장소코드
- 데이터 기준시각
- 활동단계
- 결제 관련 집계필드
- 단위
- 지원 장소 범위
- 결측 표현 방식

확인 전 필드명을 추측해 추가하지 않는다.

---

## 10. `weather_observations` 데이터셋

실제 응답을 확보한 후 다음을 확인한다.

- 관측 기준시각
- 기온
- 습도
- 강수
- 풍속
- 하늘상태
- 날씨 상태
- 단위
- 결측 표현

관측필드와 예보필드를 같은 의미로 사용하지 않는다.

확인 전 상세 필드를 `Confirmed`로 등록하지 않는다.

---

## 11. `weather_forecasts` 데이터셋

실제 응답을 확보한 후 다음을 확인한다.

- 예보 발행시각
- 예보 대상시각
- 기온 예보
- 습도 예보
- 강수 예보
- 풍속 예보
- 하늘상태 예보
- 단위
- 예보 리드타임

예측 평가에는 당시 이용 가능했던 예보값만 사용한다.

---

## 12. 파생필드

### 12.1 현재 인구 중심값

| 항목 | 내용 |
|---|---|
| 필드명 | `population_midpoint` |
| 정의 | 현재 인구 추정범위의 중심값 |
| 계산식 | `(population_min + population_max) / 2` |
| 입력필드 | `population_min`, `population_max` |
| 형식 | float |
| 단위 | 명 |
| 결측처리 | 입력 중 하나라도 결측이면 결측 |
| 상태 | Derived |

### 12.2 예측 인구 중심값

| 항목 | 내용 |
|---|---|
| 필드명 | `forecast_population_midpoint` |
| 정의 | 예측 인구범위의 중심값 |
| 계산식 | `(forecast_population_min + forecast_population_max) / 2` |
| 입력필드 | `forecast_population_min`, `forecast_population_max` |
| 형식 | float |
| 단위 | 명 |
| 결측처리 | 입력 중 하나라도 결측이면 결측 |
| 상태 | Derived |

### 12.3 예측 리드타임

| 항목 | 내용 |
|---|---|
| 필드명 | `lead_time_minutes` |
| 정의 | 예측 스냅샷 시각에서 예측 대상시각까지의 시간 |
| 계산식 | `forecast_target_time - forecast_snapshot_time` |
| 형식 | integer |
| 단위 | 분 |
| 결측처리 | 두 시간 중 하나라도 없으면 결측 |
| 상태 | Derived |

### 12.4 인구 범위폭

| 항목 | 내용 |
|---|---|
| 필드명 | `population_interval_width` |
| 정의 | 현재 인구 추정 상한과 하한의 차이 |
| 계산식 | `population_max - population_min` |
| 형식 | integer |
| 단위 | 명 |
| 상태 | Derived |

---

## 13. 시간필드 관계

```text
requested_at
→ API를 호출한 시각

population_reference_time
→ 현재 인구값의 기준시각

forecast_snapshot_time
→ 예측 묶음을 확보한 시각

forecast_target_time
→ 예측이 가리키는 미래시각
```

서로 다른 의미의 시간을 한 컬럼에 섞지 않는다.

---

## 14. 결측 규칙

다음 상태를 구분한다.

| 값 | 의미 |
|---|---|
| 빈 문자열 | 원본 빈 값 |
| JSON `null` | 원본 null |
| 필드 없음 | 스키마 또는 응답 구조 문제 가능 |
| `missing` | 지원하지만 해당 시점 데이터 없음 |
| `not_supported` | 지원대상이 아님 |
| 숫자 `0` | API가 실제로 제공한 숫자 0 |

결측을 숫자 0으로 변환하지 않는다.

---

## 15. 변환 규칙

분석용 변환 시 다음을 기록한다.

- 원본 형식
- 변환 형식
- 변환 실패 처리
- 결측 처리
- 반올림 규칙
- 시간대
- 파서 버전

변환 실패를 원본값 삭제로 처리하지 않는다.

---

## 16. 필드 등록 절차

새 필드를 등록할 때 다음 순서를 따른다.

1. 실제 샘플 또는 공식 문서 확보
2. 원본 필드명 확인
3. JSON 경로 확인
4. 원본 형식 확인
5. 단위 확인
6. 결측 표현 확인
7. 분석용 필드명 제안
8. 검증 상태 지정
9. 관련 파서·Project Guard 영향 확인
10. PM 승인

---

## 17. 필드 변경 절차

필드명을 변경할 때 다음을 확인한다.

- 기존 원본 데이터 영향
- 파서 영향
- 분석 코드 영향
- Project Guard 영향
- README 영향
- 요구사항 영향
- 마이그레이션 필요 여부

원본 API 필드명은 임의로 수정하지 않는다.

---

## 18. 완료 정의

Field Dictionary v0.1은 다음 조건을 만족해야 한다.

- 장소 필드 정의
- 현재 인구 핵심 필드 정의
- 미래 인구예측 필드 정의
- 수집 로그 필드 정의
- 파생필드 정의
- 시간필드 구분
- 결측 규칙 정의
- 실응답 확인 여부 표시
- 추측 필드를 확정값으로 표현하지 않음
- PM 승인

---

## 19. 변경 이력

| 버전 | 날짜 | 변경내용 | 작성자 | 승인상태 |
|---|---|---|---|---|
| v0.1.5 | 2026-07-23 | Plan 시각 의미 정규화·ACTIVE 장기 기준 필드·Forecast canonical 정렬 집합 계약과 H-707 비교표 반영 | 신동현 | PR #71 변경요청 보완 |
| v0.1.4 | 2026-07-23 | EG-7 plan·summary v2의 고정 5분 결정 필드와 중복 기반 주기 변경 금지 반영 | 신동현 | PM 최종 결정 |
| v0.1.3 | 2026-07-23 | EG-6B·Backup 현재 상태와 EG-7 계획·사건·Slot/Area Index·Summary 필드·표현·중복 계약 반영 | 신동현 | PM 구현 범위 승인 |
| v0.1.2 (Issue #58 보완) | 2026-07-22 | 백업·CSV와 Area·S-DoT·Spot Candidate·Recommendation 미래 데이터 계약 분리 | 신동현 | PM Diff 검토 전 |
| v0.1.1 | 2026-07-20 | collection_logs를 공식 8개 메타데이터 계약으로 정렬하고 parser_version을 향후 정규화·분석 추적 필드로 분리 | 신동현 | PM 검토 전 |
| v0.1.0 | 2026-07-17 | 장소·인구·예측·로그 필드 초안 | 신동현 | Draft |
