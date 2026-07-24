# ML-ready Dataset Spec

- 문서 상태: Draft
- 버전: v0.3.0
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-24
- 최종 수정일: 2026-07-24
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

- Python Loader: `NOT_IMPLEMENTED`
- ML-ready Dataset: `NOT_IMPLEMENTED`

이 문서는 구현 결과가 아니라 목표 계약이다. 실제 Spreadsheet 접근, Loader 코드,
정규화 코드는 이 문서만으로 승인되지 않으며 별도 Issue와 PM 승인이 필요하다.

## 3. 입력 Source와 용어

입력은 `PoC 상시 수집 Runtime`(Apps Script, `ACTIVE`)이 쓰는 다음 세 탭이다.

- `raw_log_v3`
- `population_current_v3`
- `population_forecast_v3`

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

## 6. 데이터 계층

| 계층 | 정의 |
|---|---|
| Raw | Apps Script가 v3 source sheets에 기록한 원본 응답과 상태를 그대로 반영한 계층 |
| Normalized | Area·관측시각·인구값·Forecast를 표준화한 계층(필드명 통일, 자료형 변환) |
| Feature | 시간·시계열·변화율·Baseline 비교용 Feature가 추가된 계층(EG-8B 산출물) |

Raw 계층은 v3 source sheets의 읽기 전용 반출본이며 원본 셀 값을 변형하지
않는다. Normalized와 Feature 계층만 분석·모델 입력으로 사용한다.

## 7. Current Population 필드 후보

| 필드 | 의미 |
|---|---|
| `collection_run_id` | Apps Script 실행 단위 식별자(D-014 근거) |
| `called_at` | API 호출시각 |
| `observed_at` | 관측 기준시각 |
| `area_code` | 공식 `AREA_CD`(POI 코드) |
| `area_name` | 공식 `AREA_NM` |
| `congestion_level` | 혼잡도 |
| `population_min` | 추정 인구 하한 |
| `population_max` | 추정 인구 상한 |
| `population_mid` | §9 정의의 파생 대표값 |
| `duplicate_flag` | 동일 관측의 중복 여부 |
| `error_flag` | 오류행 여부 |
| `source_status` | 원본 응답 상태(success/오류 분류) |

## 8. Forecast 필드 후보

| 필드 | 의미 |
|---|---|
| `collection_run_id` | Apps Script 실행 단위 식별자 |
| `called_at` | API 호출시각 |
| `observed_at` | 예측 스냅샷을 확보한 시점의 관측 기준시각 |
| `forecast_at` | 예측 대상시각 |
| `area_code` | 공식 `AREA_CD` |
| `area_name` | 공식 `AREA_NM` |
| `forecast_congestion_level` | 예측 혼잡도 |
| `forecast_population_min` | 예측 인구 하한 |
| `forecast_population_max` | 예측 인구 상한 |
| `forecast_population_mid` | 예측 대표값(§9와 동일 계산식) |
| `duplicate_flag` | 동일 대상시각 예측의 중복 여부 |
| `error_flag` | 오류행 여부 |
| `source_status` | 원본 응답 상태 |

이 두 필드 후보 목록은 목표 계약이며, 실제 v3 source sheets 컬럼과의 정확한
매핑은 EG-8A 구현 착수 시 실제 응답을 확인한 뒤 확정한다. 확인 전 필드명을
`Confirmed`로 표시하지 않는다(`docs/data/FIELD_DICTIONARY.md` §2의 검증 상태
관례를 따른다).

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
- 요청 Area 코드와 반환 코드 일치 여부
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
- Area 코드 불일치
- 필수값 결측
- 숫자 변환 실패
- 시간 변환 실패

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

저장 위치는 저장소 밖 외부 output-root(EG-6B/EG-7과 동일한 관례, env var
후보 `FRESHMANAGER_EG8A_OUTPUT_ROOT`)를 우선 권고하며, 대안으로 이미
`.gitignore`가 제외하는 `data/raw/`·`data/processed/`·`data/quality/`
경로도 후보다. 두 후보 모두 §3.1의 Source Snapshot과 이 절의 Loader
Output을 분리된 하위 경로로 유지해야 한다. 최종 경로는 실제 구현 Issue에서
PM이 승인한다.

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
| v0.3.0 | 2026-07-24 | EG-8A Loader V0 입력 방식(수동 CSV Export, §3.1)·V0 실행 방식(§4.1)·V0 출력 형식과 산출물 구성(§12/§12.1)·품질 항목 반드시산출/권장 분류(§13) PM 결정 반영. 장기 자동화 방식·최종 정본 형식·품질 임계값은 계속 `OPEN_DECISION` | 신동현 | PM 결정 |
| v0.2.1 | 2026-07-24 | 검증된 Spot Master(위치 식별)와 미검증 Spot Proxy(추천 가능 여부)를 구분(§14.1), Spot Recommendation/Forecast eligibility는 RECOMMENDATION_OUTPUT_CONTRACT.md §9.1/§9.2 소유임을 명시 | 신동현 | PM 결정 |
| v0.2.0 | 2026-07-24 | Area-Spot-Sensor 데이터 관계(§14) 추가 — Spot 정적 마스터·S-DoT 시계열·Area-Spot·Spot-Sensor 관계 분리, `spatial_support_type` 후보 필드와 S-DoT 동적 수집 미구현 상태 명시 | 신동현 | PM 결정 |
| v0.1.0 | 2026-07-24 | 최초 초안 작성(EG-8A/EG-8B ML-ready 데이터셋 목표 계약) | 신동현 | PM 결정 |
