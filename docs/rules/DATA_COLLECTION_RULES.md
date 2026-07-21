# Data Collection Rules

- 문서 상태: 공식 수집 기준
- 버전: v0.1.6
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-17
- 최종 수정일: 2026-07-21
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - `AGENTS.md`
  - `docs/product/FreshManager_PRD_v1.0.md`
  - `docs/engineering/FreshManager_TRD_v1.0.md`
  - `requirements-definition-freshmanager-poc-v0.4.md` (역사 문서)
  - `docs/rules/CODING_RULES.md`
  - `docs/rules/SECURITY_RULES.md`
  - `docs/data/FIELD_DICTIONARY.md`
  - `docs/testing/PROJECT_GUARD_SPEC.md`
  - `docs/testing/QUALITY_GATES.md`
  - `docs/analysis/ANALYSIS_PLAN.md`
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 서울시 공개데이터를 일관되고 재현 가능한 방식으로 요청·저장·변환·검증·누적하기 위한 규칙을 정의한다.

목적은 다음과 같다.

1. 원본 API 응답을 훼손하지 않는다.
2. 수집시각과 데이터 기준시각을 구분한다.
3. 현재값과 미래 예측값을 분리한다.
4. 같은 미래시점의 여러 예측 스냅샷을 모두 보존한다.
5. 결측, 미지원, API 오류와 숫자 0을 구분한다.
6. 일부 장소 실패가 전체 수집 실패로 이어지지 않게 한다.
7. 분석에 필요한 데이터 추적성을 유지한다.
8. 실제 API 호출을 PM 승인 범위 안에서 수행한다.

---

## 2. 수집 대상

### 2.1 공식 장소 범위

서울시 주요 121장소는 장기 공식 후보군이다. 현재 MVP 수집 대상은 EG-6A에서
확정한 13개 Area이며, 121개 Area 확대는 EG-7·EG-8 결과와 별도 PM 승인 후 검토한다.

유일한 공식 장소 기준파일:

```text
data/reference/seoul_121_places.csv
```

유효 장소 레코드는 정확히 121개여야 하며 전 필드 공백 레코드는 허용하지 않는다.
공백 레코드가 하나라도 존재하면 EG-1을 통과하지 못한다.
EG-1 통과 전에는 실제 수집기의 입력으로 사용하지 않는다.

장소코드는 공식 CSV의 `AREA_CD`를 그대로 사용한다.

다음 행위를 금지한다.

- `POI001`부터 `POI121`까지 자동생성
- `NO`를 장소코드로 사용
- 유사 장소명 자동 병합
- 누락 장소코드 추측
- CSV 자동수정
- 검증 실패 상태에서 수집 진행

여의도 공식 장소코드:

```text
POI072
```

---

### 2.2 수집 데이터

현재 필수 검토 대상:

1. 실시간 인구 현재값
2. 미래 인구예측
3. 카드소비 기반 상권현황
4. 날씨 관측값
5. 날씨 예보값
6. 수집 성공·실패 로그

선택 검토 대상:

- 교통
- 문화행사
- 생활인구
- S-DoT
- 기타 공개데이터

선택 데이터는 PM 승인 없이 필수 범위에 추가하지 않는다.

---

## 3. 단계별 수집 확대

수집은 다음 순서로 확대한다.

```text
EG-4 여의도 1장소
→ EG-5 대표 3장소
→ EG-6A 13개 Area·Spot·S-DoT 패널 확정
→ EG-6B 13개 Area 단일 수집·Batch Log·Manifest·SHA-256 검증
→ EG-7 동일 13개 Area 반복수집 파일럿
→ EG-8 시간·장소·Forecast·S-DoT Feature 분석
→ 후속 검토에서 필요 시 121개 Area 확대
```

처음부터 121장소 장기 자동수집을 구현하지 않는다.

각 단계는 이전 단계 검증과 PM 승인을 완료한 후 진행한다.

EG-4는 Issue #43의 PM 승인 실제 POI072 단일 수집에서 정상 JSON과 원본·
메타데이터 저장을 확인해 통과했다. EG-5는 다음 세 장소의 오피스·상업 역세권
집중 검증으로 제한한다.

```text
POI019 구로디지털단지역
POI013 가산디지털단지역
POI014 강남역
```

EG-5는 세 코드를 위 순서로 각각 최대 1회 처리하고 자동 재시도를 하지 않았으며,
별도 PM 승인 아래 실제 수집과 구조 분석을 완료했다.

EG-6A는 실제 수집 없이 13개 Area·Spot·S-DoT 참조 패널을 확정해 PR #52로
`main`에 반영했다. EG-6B는 같은 13개 Area의 단일 수집, Batch Log, Manifest와
SHA-256 무결성 파이프라인을 PR #54로 `main`에 반영했다. 실제 단일 회차와 결과
검토는 아직 수행하지 않았으며 PM PASS 전에는 EG-6B를 통과로 표시하지 않는다.
PM 확인용 CSV와 로컬·Google Spreadsheet 자동백업은 Issue #53 구현 범위에 포함하지
않으며 필요하면 별도 PM 승인을 받는다. EG-7은 같은 13개 Area 반복수집 파일럿으로 제한하며,
EG-8은 시간·장소·Forecast·S-DoT Feature를 분석한다. 현재 MVP 분석 범위는
유동인구·혼잡·Forecast·S-DoT Feature와 스팟 이동 기회이며 실제 판매효과 분석은
포함하지 않는다.

과거의 `시험용 10장소 → 121장소 1회 수집`은 이전 계획으로 보존하되 현재 승인된
실행 순서로 사용하지 않는다. 121개 Area 확대는 13개 패널 검증에서 필요성이 확인된
경우 후속 PM 승인 대상으로 검토한다.

### 3.1 단계별 저장 경로 분리

각 수집 단계의 결과는 공통 output root 아래 서로 다른 단계 경로에 저장하고,
다른 단계의 원본·메타데이터와 같은 폴더에 섞지 않는다.

EG-5 고정 단계 경로:

```text
<output-root>/stages/eg5_representative_3/data/raw/population/
<output-root>/stages/eg5_representative_3/data/processed/collection_logs/
```

사용자가 단계명, raw 경로 또는 metadata 경로를 직접 바꾸는 EG-5 CLI 옵션은
제공하지 않는다. 기존 EG-4 실제 원본과 메타데이터는 읽기·이동·복사·수정·삭제하지
않는다.

### 3.2 EG-5 실행 전 저장·기준파일 사전검사

EG-5는 Transport를 만들거나 호출하기 전에 raw와 metadata 저장 root를 준비하고,
각 root 안에서 숨김 probe 파일의 소량 쓰기·flush·삭제를 확인한다. probe 파일은
JSON이나 metadata 확장자를 사용하지 않으며 정상 종료와 검사 실패 모두에서 남기지
않는다. 이 사전검사에 실패하면 공통 오류 종료코드 `2`로 중단하고 Transport 호출은
0회여야 한다.

공식 CSV는 최초 승인 장소를 확인할 때 SHA-256을 기록하고 각 장소 처리 전과 처리
직후 같은 파일 상태인지 읽기 전용으로 확인한다. 파일 유실·변경·손상이 확인되면
일반 응답 `validation_error`와 구분해 공통 오류 종료코드 `2`로 중단한다. 이미 저장된
이전 장소 결과는 삭제하거나 되돌리지 않는다.

저장 probe는 실행 직전의 최소 쓰기 가능성만 확인한다. 실행 중 발생할 수 있는
디스크 고장·용량 소진이나 모든 파일시스템 경쟁조건을 방지한다고 해석하지 않는다.

### 3.3 EG-6B 단일 회차 저장·무결성 계약

EG-6B는 승인된 `eg6_area_panel.csv`의 `panel_order`에 따라 고정된 13개 Area를
각각 최대 1회 순차 처리한다. 사용자가 장소코드, 단계명, raw 경로 또는 metadata
경로를 직접 지정하는 옵션은 제공하지 않는다. 자동 재시도와 반복수집은 포함하지 않는다.

고정 단계 경로:

```text
<output-root>/stages/eg6b_single_13/data/raw/population/YYYY/MM/DD/
<output-root>/stages/eg6b_single_13/data/processed/collection_logs/YYYY/MM/DD/
<output-root>/stages/eg6b_single_13/data/processed/batches/<batch_id>/collection_log.json
<output-root>/stages/eg6b_single_13/data/processed/batches/<batch_id>/manifest.json
```

요청별 metadata는 승인된 8개 필드를 유지한다. Batch Collection Log는 최소한 다음을
별도로 기록한다.

- `collector_version`: EG-6B 실행 코드 계약 버전
- `data_version`: Batch 산출물 스키마 버전
- `batch_id`, `panel_version`, `collection_purpose`
- 대상·시도·성공·실패 수와 실패 장소코드
- 시작·종료시각과 총 소요시간
- `retry_count=0`
- 생성된 raw·metadata 수
- 장소별 상태와 단계 root 기준 상대경로
- 종료코드 `0`, `1`, `2`

Manifest는 공식 장소 CSV, EG-6A 참조 CSV 3개와 생성된 raw·metadata·Collection Log의
파일 크기와 SHA-256을 기록한다. Manifest 자신은 순환 해시를 피하기 위해 자기 항목에
포함하지 않는다. 참조파일과 이미 저장된 raw·metadata는 다시 읽어 크기와 SHA-256을
검증하고, Collection Log는 최종 직렬화 bytes의 크기·SHA-256을 Manifest와 대조한 뒤
같은 bytes를 마지막에 원자적으로 공개한다. 불일치나 최종 공개 실패 시 종료코드 `2`로
보고하고 기존 정상 산출물을 삭제·이동·덮어쓰지 않는다.

종료코드 계약:

- `0`: 승인 13개 모두 성공하고 Batch 무결성 검증 통과
- `1`: 단일 회차 완료, 장소별 실패가 하나 이상 있으며 Batch 무결성 검증 통과
- `2`: 공통 사전검사·설정·저장·보안·참조 또는 Batch 무결성·내부 오류

`api_error`, `timeout`, `parse_error`, `validation_error`는 장소별 실패로 기록하고 다음
Area를 처리한다. 공통 오류에서는 추가 호출을 중단하되 이미 저장된 결과를 되돌리지 않는다.
`--execute-live`는 실제 호출 PM 승인을 대체하지 않는다. Issue #53 구현과 일반 검증은
Fake Transport와 임시 output root만 사용했고, 실제 최대 13회 단일 회차는 별도 승인 전이다.

---

## 4. 실제 API 호출 원칙

신규 실제 API 호출은 다음 조건을 모두 만족한 뒤에만 수행한다.

- EG-3 오프라인 Project Guard 통과
- EG-4 진입 PM 승인
- 실제 호출 PM 승인

위 조건을 충족한 뒤에도 PM이 승인한 다음 범위에서만 수행한다.

- 여의도 1장소 스모크 테스트
- 승인된 대표 3장소 시험
- 승인된 13개 Area 단일 수집
- 승인된 동일 13개 Area 반복수집 파일럿
- 필요성이 확인되고 별도 PM 승인을 받은 121개 Area 확대 수집

일반 Project Guard와 단위 테스트에서는 실제 API를 호출하지 않는다.

테스트에는 다음 자료를 사용한다.

```text
data/samples/population_yeouido_sample.json
tests/fixtures/
```

---

## 5. 수집 기본 흐름

```text
공식 장소 CSV 읽기
→ 장소코드 검증
→ 요청 설정 확인
→ API URL 생성
→ API 호출
→ 응답 상태 확인
→ 원본 응답 저장
→ JSON 파싱
→ 분석용 구조 변환
→ 분석용 데이터 저장
→ 수집 로그 기록
→ 회차 결과 요약
```

API 호출과 파싱, 저장, 로그 기록은 테스트 가능한 별도 역할로 분리한다.

---

## 6. 요청 설정

API 요청 설정은 코드 여러 곳에 중복 작성하지 않는다.

설정 대상 예:

- 공식 장소 CSV 경로
- 원본 저장 경로
- 분석용 저장 경로
- 로그 저장 경로
- 요청 제한시간
- 호출 간 대기시간
- 재시도 횟수
- 대상 endpoint
- 대상 장소
- 배치 실행 허용 여부
- 시간대

실제 API 키는 설정 JSON이 아니라 `.env`의 `SEOUL_OPEN_API_KEY`에서 읽는다.

---

## 7. Endpoint 관리

로그와 메타데이터에는 전체 API URL 대신 논리적 endpoint 이름을 사용한다.

예:

```text
citydata_ppltn
citydata_commerce
citydata_weather
```

실제 서비스명이 확인되지 않은 endpoint는 추측해 확정하지 않는다.

전체 URL에 API 키가 포함되므로 원문 URL을 로그에 저장하지 않는다.

---

## 8. 요청 고유번호

각 API 요청에는 고유한 `request_id`를 생성한다.

원칙:

- 요청마다 새로운 값 생성
- 재시도 시 새로운 값 생성
- 원본 파일과 로그를 연결할 수 있어야 함
- 분석 테이블에서 수집 이력을 추적할 수 있어야 함

권장 형식:

```text
UUID
```

`request_id`를 실제 장소코드나 시각의 대체값으로 사용하지 않는다.

---

## 9. 시간 처리 규칙

운영 시간대:

```text
Asia/Seoul
```

다음 시간의 의미를 구분한다.

| 시간필드 | 의미 |
|---|---|
| `requested_at` | 수집기가 API 요청을 시작한 시각 |
| `received_at` | API 응답 수신 또는 요청 실패를 확인한 필수 수집 메타데이터 시각 |
| `population_reference_time` | 현재 인구값이 기준으로 하는 시각 |
| `forecast_snapshot_time` | 예측 묶음을 수집해 보존한 시각 |
| `forecast_target_time` | 예측값이 가리키는 미래 대상시각 |
| `weather_forecast_issued_at` | 날씨 예보 발행시각 |
| `weather_forecast_target_time` | 날씨 예보 대상시각 |
| `weather_observed_at` | 날씨 관측 기준시각 |

`forecast_snapshot_time`은 우리 시스템이 예측 묶음을 확보한 시각이다.

공식 예측 발행시각 필드가 확인되면 별도 `forecast_issued_at` 필드로 저장한다.

공식 발행시각을 확인하지 못한 상태에서 임의값을 만들지 않는다.

---

## 10. 원본 JSON 보존

서울시에서 받은 원본 JSON은 수정하지 않는다.

### 원칙

- 원본 필드명 변경 금지
- 문자열 숫자 변환 금지
- 정렬·보정 금지
- 결측값 보완 금지
- 이상값 삭제 금지
- 기존 파일 덮어쓰기 금지
- 호출마다 새 파일 생성
- 원본 응답 전체 보존
- 오류 여부는 별도 로그에 기록
- 최종 원본과 최종 메타데이터 자동 삭제 금지

### 권장 저장경로

```text
data/raw/population/YYYY/MM/DD/
data/raw/commerce/YYYY/MM/DD/
data/raw/weather/YYYY/MM/DD/
```

### 파일명

```text
{AREA_CD}_{REQUESTED_AT}.json
```

예:

```text
POI072_20260717_091500.json
```

동일 초에 여러 요청이 가능한 구조라면 `request_id`를 추가한다.

```text
POI072_20260717_091500_{request_id}.json
```

---

## 11. 분석용 데이터 저장

분석용 데이터에서만 형식을 변환한다.

예:

| 원본값 | 분석용값 |
|---|---|
| `"44000"` | 정수 `44000` |
| `"52.9"` | 소수 `52.9` |
| `"2026-07-17 23:10"` | 날짜시간 |
| `""` | 결측 |
| 필드 없음 | 결측 또는 스키마 오류 |

원본 필드와 파생필드를 구분한다.

예:

```text
AREA_PPLTN_MIN
AREA_PPLTN_MAX
population_midpoint
```

`population_midpoint`는 원본이 아니라 파생필드다.

---

## 12. 데이터셋 분리

다음 데이터셋을 논리적으로 분리한다.

```text
places
population_observations
population_forecasts
commerce_observations
weather_observations
weather_forecasts
collection_logs
```

현재값과 미래 예측값을 같은 행에 억지로 합치지 않는다.

날씨 관측과 날씨 예보도 분리한다.

---

## 13. 현재 인구 저장 규칙

현재 인구 데이터는 실제 응답의 필드를 저장한다.

최소 핵심 필드:

- `AREA_NM`
- `AREA_CD`
- `AREA_CONGEST_LVL`
- `AREA_CONGEST_MSG`
- `AREA_PPLTN_MIN`
- `AREA_PPLTN_MAX`
- `PPLTN_TIME`
- `FCST_YN`

현재 인구 데이터에는 다음 메타데이터를 연결한다.

- `request_id`
- `area_code`
- `endpoint_name`
- `requested_at`
- `received_at`
- `http_status`
- `collection_status`
- `raw_file_path`

권장 식별 조합:

```text
area_code
+ population_reference_time
+ request_id
```

---

## 14. 미래 인구예측 저장 규칙

예측 최소 필드:

- `AREA_CD`
- `FCST_TIME`
- `FCST_CONGEST_LVL`
- `FCST_PPLTN_MIN`
- `FCST_PPLTN_MAX`
- `forecast_snapshot_time`
- `forecast_target_time`
- `request_id`

같은 미래 대상시각의 예측이 여러 번 들어와도 기존 예측을 덮어쓰지 않는다.

예:

```text
09:00에 확보한 15:00 예측
12:00에 확보한 15:00 예측
14:00에 확보한 15:00 예측
```

세 예측을 모두 보존한다.

권장 식별 조합:

```text
area_code
+ forecast_snapshot_time
+ forecast_target_time
+ request_id
```

---

## 15. 날씨 데이터 규칙

날씨 예보와 관측은 분리한다.

### 예측·분석 입력

예측 성능 평가에는 예측 당시 이용 가능했던 날씨 예보만 사용한다.

### 사후 분석

실제 날씨 관측은 다음 목적으로만 사용한다.

- 사후 원인 분석
- 날씨 예보 오차 확인
- 조건별 성능 비교

다음 행위를 금지한다.

- 사후 관측값을 과거 예측 입력으로 소급 사용
- 예보 결측을 실제 관측값으로 대체
- 관측과 예보를 같은 의미의 컬럼에 저장

---

## 16. 상권현황 데이터 규칙

상권현황은 카드소비 기반 소비활동 대리변수로 해석한다.

허용 표현:

- 카드소비 기반 소비활동 대리변수
- 상권 활동단계
- 일반 소비활동 변화 신호

금지 표현:

- 실제 야쿠르트 매출
- 프레시매니저 판매실적
- 실제 전체 소비금액
- 구매전환율
- 추천으로 발생한 매출

상권현황은 모든 장소에서 지원되지 않을 수 있다.

---

## 17. 수집 상태값

| 상태 | 의미 |
|---|---|
| `success` | 정상 요청·저장·파싱 완료 |
| `missing` | 지원 대상이나 해당 시점 값이 없음 |
| `not_supported` | 해당 장소 또는 데이터가 지원 대상이 아님 |
| `api_error` | API가 오류 응답을 반환 |
| `timeout` | 요청 제한시간 초과 |
| `parse_error` | JSON 구조를 해석하지 못함 |
| `validation_error` | 필수값 또는 형식 검증 실패 |
| `storage_error` | 파일 또는 데이터 저장 실패 |
| `config_error` | 설정 또는 인증키 문제 |
| `security_error` | 키 노출 등 보안규칙 위반 |

다음 변환을 금지한다.

```text
missing → 0
not_supported → 0
api_error → 0
parse_error → 0
```

숫자 `0`은 API가 실제 숫자 0을 제공한 경우에만 사용한다.

---

## 18. 최소 수집 메타데이터

| 필드 | 의미 |
|---|---|
| `request_id` | 요청 고유번호 |
| `area_code` | 공식 CSV의 장소코드 |
| `endpoint_name` | 논리적 API 이름 |
| `requested_at` | 요청시각 |
| `received_at` | 응답 수신 또는 요청 실패 확인시각 |
| `http_status` | HTTP 상태 |
| `collection_status` | 수집 결과 상태 |
| `raw_file_path` | 원본 JSON 경로 |

`raw_payload`는 수집 메타데이터가 아니라 원본 응답이며,
메타데이터의 `raw_file_path`로 저장 위치를 추적한다.

`parser_version`은 최소 수집 메타데이터에 포함하지 않는다. 정규화·분석 데이터
파일 저장이 구현되는 시점에 파서 추적 필드로 별도 검토한다.

`error_type`, `error_message`는 필수 메타데이터에 포함하지 않는다. 필요성이
확인되면 선택 필드로 별도 제안하고 PM 승인을 받는다.

필요성이 확인되지 않은 메타데이터를 임의로 추가하지 않는다.

추가가 필요하면 다음을 보고한다.

1. 추가 필드
2. 필요한 이유
3. 활용 목적
4. 저장량 영향
5. PM 승인 필요사항

---

## 19. API 응답 검증

응답 수신 후 다음을 확인한다.

- HTTP 상태
- JSON 문법
- API 결과 코드
- 대상 장소코드
- 대상 장소명
- 필수 루트 키
- 필수 현재 인구 필드
- 예측 배열 구조
- 오류 메시지
- API 키 포함 여부

API가 JSON 형태의 오류를 반환해도 정상 데이터로 처리하지 않는다.

---

## 20. 제한시간과 재시도

초기 스모크 테스트 권장값:

```text
retry_count = 0
```

EG-5 대표 3장소와 EG-6B 승인 13개 Area 단일 회차는 `retry_count=0`으로 고정한다.
장소별 실패는 다음 장소 처리를 막지 않지만 같은 회차에서 실패 장소를 재호출하지 않는다.

재시도는 시험 결과를 본 뒤 PM 승인으로 적용한다.

재시도 규칙이 승인된 경우:

- 무한 재시도 금지
- 재시도 횟수 설정값 관리
- 재시도 사유 기록
- 요청마다 새로운 `request_id`
- 재시도에 따른 호출량 집계
- `config_error`는 재시도하지 않음
- `not_supported`는 재시도하지 않음

---

## 21. 배치 실패 격리

여러 장소를 수집할 때 한 장소의 실패로 전체 회차를 즉시 중단하지 않는다.

반드시 기록할 항목:

- 전체 대상 장소 수
- 성공 장소 수
- 실패 장소 수
- 실패 장소코드
- 실패 상태
- 실패 원인
- 시작시각
- 종료시각
- 총 소요시간
- 재시도 수
- 생성된 원본 파일 수

전체 중단이 가능한 오류:

- API 키 없음
- 설정파일 손상
- 공식 장소 CSV 없음
- 저장경로 접근 불가
- 디스크 저장 불가
- 보안규칙 위반

---

## 22. 호출주기 결정

반복수집 주기를 미리 확정하지 않는다.

반복수집에 들어가기 전 다음 백업 Gate 중 최소 하나를 PM이 승인해야 한다.

- 외장 저장장치에 주기적으로 복사
- PM이 승인한 클라우드 폴더에 주기적으로 백업

이 Gate는 수집 실행을 클라우드로 옮기는 것이 아니다. 수집은 로컬 Python에서
유지하고 백업 작업만 별도로 수행한다. EG-5와 EG-6B는 백업 기능과 반복수집을
구현하지 않았으며 `H-707`은 EG-7 전까지 `SKIP`한다.

Issue #53·PR #54의 EG-6B 단일 수집 구현은 로컬·Google Spreadsheet 자동백업을 포함하지 않는다.
향후 로컬 스프레드시트 산출물을 추가하더라도 위 외장 저장장치·승인 클라우드 백업
Gate를 대체하지 않는다. 반복수집 파일럿에 들어가기 전에는 위 백업 Gate와 다음 결과를
확인한 뒤 EG-7 진입을 PM이 승인한다.

- API 호출한도
- 13개 Area 1회 처리시간
- 실제 데이터 갱신주기
- 성공률과 실패율
- 재시도 호출량
- 저장공간 증가량
- 운영 컴퓨터 안정성
- 분석에 필요한 시간해상도

다음 주기는 후보일 뿐 기본값이 아니다.

```text
5분
10분
15분
30분
특정 운영시간
```

---

## 23. 데이터 품질 검사

수집 중 다음 지표를 측정한다.

- 예정 요청 수
- 실제 요청 수
- 성공률
- 실패율
- 결측률
- 연속 실패 횟수
- 필수필드 누락
- 중복 응답
- 기준시각 역전
- 요청시각과 기준시각 간 지연
- 원본 파일 수와 로그 수 차이
- 파싱된 행 수
- 스키마 변경 의심
- 장소별 지원 여부

결측을 단순 정상 상태로 간주하지 않는다.

결측률을 측정하고 Gate 판정에 반영한다.

---

## 24. 스키마 변경 대응

다음 상황을 스키마 변경 후보로 본다.

- 필수 루트 키 변경
- 필수 필드 누락
- 배열이 객체로 변경
- 데이터 유형 변경
- 새 오류 응답 구조
- 기존 필드명 변경
- 예측 배열 구조 변경

스키마 변경 후보가 발견되면:

1. 원본 보존
2. 자동 보정 금지
3. `validation_error` 또는 `parse_error` 기록
4. 영향받는 장소·시점 보고
5. 문서·파서 수정안 제시
6. PM 승인 후 변경

---

## 25. 원본과 분석용 데이터 보관

최소 보관기간:

```text
수집 시작
→ 최종 분석
→ 최종 보고서 작성 완료
```

이 기간 동안 원본 데이터를 삭제하지 않는다.

삭제는 PM 승인 후 수행한다.

원본과 파생데이터를 구분한다.

| 구분 | 재생성 가능성 |
|---|---|
| 원본 JSON | 다시 수집하지 않으면 재생성 불가 |
| 분석용 CSV | 원본과 파서가 있으면 재생성 가능 |
| 리포트 | 분석 결과로 재생성 가능 |
| 로그 | 수집 당시 상태이므로 중요 |

---

## 26. 데이터 수정·삭제

다음 작업은 PM 승인 없이 하지 않는다.

- 원본 JSON 수정
- 공식 CSV 수정
- 분석용 데이터 일괄 수정
- 데이터 삭제
- 기존 파일 덮어쓰기
- 저장구조 변경
- 컬럼명 변경
- 데이터 유형 변경

오류 정정이 필요한 경우 원본을 수정하지 않고 별도의 정정 결과를 생성한다.

---

## 27. 수집 단계 완료 보고

수집 작업 완료 보고에는 다음을 포함한다.

1. 대상 범위
2. 실행시각
3. 전체 요청 수
4. 성공 수
5. 실패 수
6. 실패 장소 목록
7. 결측 유형
8. 총 소요시간
9. 생성된 원본 파일 수
10. 생성된 분석용 행 수
11. Project Guard 결과
12. API 키 미노출 확인
13. 범위 준수
14. PM 확인사항
15. 남은 위험
16. 다음 단계 진입 가능 여부

---

## 28. 완료 정의

수집 단계는 다음 조건을 만족해야 완료다.

- 승인된 장소만 호출
- 공식 CSV의 `AREA_CD` 사용
- API 키 미노출
- 원본 JSON 보존
- 기존 원본 미덮어쓰기
- 수집 로그 기록
- 현재값·예측값 분리
- 예측 스냅샷 보존
- 결측·미지원·오류 구분
- 배치 실패 격리
- 성공·실패 결과 보고
- Project Guard 통과
- PM 승인

---

## 29. 변경 이력

| 버전 | 날짜 | 변경내용 | 작성자 | 승인상태 |
|---|---|---|---|---|
| v0.1.6 | 2026-07-22 | PRD·TRD 공식 기준 연결, PR #54 병합 완료와 EG-6B 실제 단일 회차 대기 상태 정렬 | 신동현 | PM 승인 |
| v0.1.5 | 2026-07-21 | Issue #53 EG-6B 13개 단일 회차의 단계 경로·Batch Log·Manifest·SHA-256·재시도 0회 계약 반영 | 신동현 | PM 구현 승인 |
| v0.1.4 | 2026-07-21 | EG-6A 13개 패널 전략과 EG-6B·EG-7·EG-8 현행 순서 및 121개 Area 후속 검토 범위 반영 | 신동현 | PM 승인 |
| v0.1.3 | 2026-07-21 | EG-5 저장 root probe와 공식 CSV 실행 전·후 무결성 검사 및 한계 반영 | 신동현 | PM 승인 |
| v0.1.2 | 2026-07-21 | EG-4 PASS, EG-5 고정 3장소·단계 경로·재시도 0회·원본 무삭제와 반복수집 전 백업 Gate 반영 | 신동현 | PM 승인 |
| v0.1.1 | 2026-07-20 | received_at 포함 공식 8개 수집 메타데이터 계약 및 HTTP Adapter 오프라인 실행 경계 반영 | 신동현 | PM 검토 전 |
| v0.1.0 | 2026-07-17 | 최초 초안 작성 | 신동현 | Draft |
