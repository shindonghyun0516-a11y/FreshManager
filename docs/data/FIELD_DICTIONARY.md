# Field Dictionary

- 문서 상태: Draft
- 버전: v0.1.0
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-17
- 최종 수정일: 2026-07-17
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - `AGENTS.md`
  - `requirements-definition-freshmanager-poc-v0.4.md`
  - `docs/rules/DATA_COLLECTION_RULES.md`
  - `docs/analysis/ANALYSIS_PLAN.md`
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
| `Unverified` | 아직 공식 문서나 실응답에서 확정하지 못함 |
| `Derived` | 원본 필드로 계산한 파생필드 |
| `Deprecated` | 더 이상 사용하지 않음 |

실제 응답 또는 공식 기준파일에서 확인하지 않은 필드를 `Confirmed`로 표시하지 않는다.

---

## 3. 데이터셋 목록

| 데이터셋 | 역할 | 현재 상태 |
|---|---|---|
| `places` | 공식 121장소 기준정보 | 공식 CSV 정비·main 반영 완료, 정확한 5개 컬럼·유효 장소 121개, EG-1 PASS |
| `population_observations` | 현재 인구값 | 여의도 샘플 확인 |
| `population_forecasts` | 미래 인구예측 | 여의도 샘플 확인 |
| `commerce_observations` | 카드소비 기반 상권현황 | 실응답 확인 필요 |
| `weather_observations` | 날씨 관측 | 실응답 확인 필요 |
| `weather_forecasts` | 날씨 예보 | 실응답 확인 필요 |
| `collection_logs` | 수집 성공·실패 기록 | 구조 정의 |
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
| `parser_version` | 파서 버전 | 예측 파싱에 사용한 코드 버전 | string | 추적성 |

---

## 8. `collection_logs` 데이터셋

| 필드 | 한글명 | 정의 | 형식 | 결측 허용 | 검증 상태 |
|---|---|---|---|---|---|
| `request_id` | 요청 고유번호 | API 호출별 고유 식별값 | string | 아니오 | Documented |
| `endpoint_name` | Endpoint 이름 | 인증 URL이 아닌 논리적 API 이름 | string | 아니오 | Documented |
| `requested_at` | 요청시각 | API 호출 시작시각 | datetime | 아니오 | Documented |
| `http_status` | HTTP 상태 | HTTP 응답 상태코드 | integer | 예 | Documented |
| `area_code` | 장소코드 | 요청 대상 장소코드 | string | 예 | Documented |
| `collection_status` | 수집 상태 | 수집 결과 상태값 | categorical | 아니오 | Documented |
| `raw_file_path` | 원본 파일 경로 | 저장된 원본 JSON 경로 | string | 실패 시 예 | Documented |
| `parser_version` | 파서 버전 | 사용한 파서 버전 | string | 예 | Documented |

`raw_payload`는 수집 메타데이터가 아니라 원본 응답이며,
`raw_file_path`로 저장 위치를 추적한다.

다음 필드는 v0.1 필수 메타데이터가 아닌 선택 제안이다.

| 필드 | 제안 목적 | 검증 상태 |
|---|---|---|
| `received_at` | API 응답 수신 완료시각 기록 | Unverified |
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
| v0.1.0 | 2026-07-17 | 장소·인구·예측·로그 필드 초안 | 신동현 | Draft |
