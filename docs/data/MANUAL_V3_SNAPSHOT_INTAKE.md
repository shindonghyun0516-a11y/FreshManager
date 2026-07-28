# Manual V3 Snapshot Intake Contract

- 문서 상태: Draft
- 계약 버전: v1
- 적용 Issue: #113
- 변경 시 PM 승인: 필요
- 관련 문서:
  - [`ML_READY_DATASET_SPEC.md`](ML_READY_DATASET_SPEC.md)
  - [`DATA_COLLECTION_RULES.md`](../rules/DATA_COLLECTION_RULES.md)
  - [`PROJECT_STATUS.md`](../../PROJECT_STATUS.md)
  - [`DECISION_LOG.md`](../../ai-context/DECISION_LOG.md)의 D-016

## 1. 목적과 범위

이 계약은 사용자가 수동으로 내보낸 `raw_log_v3`, `population_current_v3`,
`population_forecast_v3` CSV와 `upload_manifest.csv`를 검증하고 저장소 밖 결과
위치에 불변 Snapshot으로 보존하는 경계를 정의한다.

이 경계는 Apps Script 수집동작을 변경하거나 운영 수집 목적을 추론하지 않는다.
Apps Script 자동 Export, Google Sheets API, 실제 Snapshot 반입, Dataset 생성,
머신러닝, 사용자 게시와 공식 Recommendation은 별도 승인 대상이다.

## 2. 공개 실행계약

공개 함수 `run_manual_snapshot_intake`는 다음 다섯 경로를 역할별로 명시적으로 받는다.

- `raw_path`
- `current_path`
- `forecast_path`
- `upload_manifest_path`
- `output_root`

파일명이나 디렉터리 순서로 역할을 추정하지 않는다. `output_root`는 저장소 밖에
이미 존재하는 일반 디렉터리여야 하며 Symlink, 파일시스템 최상위, 일반 파일,
존재하지 않는 경로와 저장소 내부 경로를 거부한다.

네 입력은 존재하는 비어 있지 않은 일반 파일이어야 한다. Symlink와 같은 실제경로,
같은 장치·inode를 공유하는 역할 중복을 거부한다.

## 3. Upload Manifest

`upload_manifest.csv`는 Header 1행과 Data 1행만 허용한다.

필수 필드:

- `snapshot_intake_purpose`
- `exported_at`
- `source_sheet_contract`
- `source_origin_confirmed_by_pm`

선택 필드는 `note` 하나뿐이며 알 수 없는 필드는 거부한다.

`snapshot_intake_purpose`는 다음 값만 허용한다.

- `DATA_QUALITY_VALIDATION`
- `HISTORICAL_ANALYSIS`
- `UI_PROTOTYPE`
- `MODEL_EVALUATION`
- `PM_APPROVED_LIMITED_SNAPSHOT_REVIEW`

`source_sheet_contract`는 `V3`, `source_origin_confirmed_by_pm`은 소문자
`true` 또는 `false`만 허용한다. `exported_at`은 정확한 `+09:00` Offset이 있는
ISO 8601 시각이어야 하며 빈 값·Timezone-naive·미래시각을 거부한다.

`source_origin_confirmed_by_pm=true`는 현재 운영 v3 시트에서 반출했다는 출처
확인만 의미한다. 데이터 품질, 운영 사용, 분석결과, 사용자 게시 또는 공식 추천
승인이 아니다. `false`이면 검증보고서를 반환할 수 있지만 Final Snapshot은
공개하지 않는다.

## 4. V3 Source 계약

Intake 경계는 현재 생산코드의 정확한 Header만 허용한다.

`raw_log_v3` 7개 컬럼:

```text
collection_run_id,called_at,area_code_requested,area_name,http_code,result_status,raw_json_or_error
```

`population_current_v3` 9개 컬럼:

```text
collection_run_id,called_at,observed_at,area_code_requested,area_code_returned,area_name,congestion_level,population_min,population_max
```

`population_forecast_v3` 10개 컬럼:

```text
collection_run_id,called_at,observed_at,forecast_at,area_code_requested,area_code_returned,area_name,forecast_congestion_level,forecast_population_min,forecast_population_max
```

v1·v2 Header와 확장 컬럼은 Intake 경계에서 거부한다. 이 엄격한 경계는 기존
`eg8a.py`의 확장 컬럼 허용 계약을 변경하지 않는다.

Source 시각 문자열은 현재 v3 계약대로 Offset이 없는 `Asia/Seoul` 시각이며,
검증 시 Timezone-aware KST 값으로 해석한다. Upload Manifest의 `exported_at`만
명시적인 `+09:00` Offset을 요구한다.

각 행은 canonical UUID `collection_run_id`, 승인된 Area 코드, 필수값, 시각,
Current·Forecast 인구 최소·최대와 `forecast_at > observed_at`을 검증한다.
Raw·Current는 `collection_run_id + area_code_requested`, Forecast는 여기에
`forecast_at`을 더한 Key를 사용하며 세 Source의 회차·Area 연결이 일치해야 한다.

## 5. 불변 복사와 지문

각 입력은 한 번의 읽기 Stream으로 Staging에 바이트 그대로 복사한다. 복사 중
SHA-256과 크기를 계산하고 이후 검증은 Staging 복사본만 사용한다. 원본은 정렬,
변환, 재저장, Header 변경, 행 삭제, 중복 제거, 인코딩 교정 또는 줄바꿈 변경을
하지 않는다.

`source_content_fingerprint`는 고정 순서 `RAW`, `CURRENT`, `FORECAST` 역할명과
각 SHA-256을 결합해 계산한다. 각 항목은 UTF-8 역할명, NUL 1바이트, ASCII
SHA-256, LF 1바이트 순서로 직렬화한다. Upload Manifest는 포함하지 않는다.

`intake_metadata_fingerprint`는 Source 지문과 정규화한 목적, 반출시각, V3 계약,
출처확인 Boolean, `note`로 계산한다. `note`는 앞뒤 공백을 제거하고 반출시각은
`datetime.isoformat()` 결과를 사용한다. 이 여섯 필드의 Key를 정렬한 UTF-8 JSON을
공백 없는 구분자로 직렬화해 SHA-256을 계산한다. Snapshot ID는 전체 Source 지문을
사용한 `snapshot-<source_content_fingerprint>`다.

## 6. 중복과 재반입

정확히 동일한 행은 원본에서 제거하지 않고 전체·고유·중복 행 수를 각각 기록한다.
같은 Key의 내용이 다르면 `CONFLICTING_DUPLICATE_KEY`로 Final 공개를 차단한다.

- 같은 Source + 같은 Metadata + 기존 Final: `DUPLICATE_SNAPSHOT_BLOCKED`
- 같은 Source + 다른 Metadata + 기존 Final: `SOURCE_RECLASSIFICATION_BLOCKED`
- 이전 실패가 Staging에만 있고 Final이 없음: 안전한 재시도 허용
- CSV 내용이 달라 Source 지문이 바뀜: 신규 Snapshot 허용

초기 구현은 Snapshot 간 증분병합과 신규 행 영구추출을 하지 않는다.

## 7. 결과와 공개조건

논리구조는 다음과 같다.

```text
manual-snapshots/
  snapshot-<source-content-fingerprint>/
    source/raw/<original-name>
    source/current/<original-name>
    source/forecast/<original-name>
    source/intake/<original-name>
    snapshot_manifest.json
    validation_report.json
```

Snapshot Manifest는 지문, 역할별 경로·SHA-256·크기·행 수, 회차·Area·시간범위,
검증상태와 생성시각을 기록한다. `source_files_modified`는 `false`이며 목적 추론,
운영 지표, Dynamic Spot, 사용자 게시와 공식 Recommendation 관련 Flag도 모두
`false`다. `source_files_modified=false`는 Intake가 읽은 바이트를 변환하지 않았다는
뜻이며 반입 전 파일 변경 이력을 증명하지 않는다.

Validation Report는 파일·Manifest·Header·연결 검사, 행·중복·충돌·회차·Area 수,
시간범위, 경고·오류, 공개 가능 여부와 차단 사유 코드를 Raw 값이나 절대경로 없이
기록한다.

네 파일, Upload Manifest, V3 Header, 데이터 연결, 충돌 0, 출처확인 `true`를 모두
통과하고 Final 공개 직전 Staging의 네 SHA-256과 크기가 최초 복사값과 일치해야
한다. 그 뒤 배타적 이름 변경으로 공개하며 기존 Final을 덮어쓰지 않는다.

## 8. EG-8A 연결과 제외범위

`normalize_final_snapshot_for_eg8a` Adapter는 Final Manifest와 네 입력의 경로,
SHA-256·크기, 보존된 Upload Manifest의 재해석값, Intake Metadata 지문, Source 지문,
Snapshot ID, 검증상태와 모든 운영 관련 `false` Flag를 재검증한다. 그 뒤 세 Source를
기존 `eg8a.normalize_v3_sources`에 역할별로 전달하고 네 입력의 SHA-256·크기를 다시
확인한다. 기존 EG-8A 생산코드와 잠긴 Dataset은 변경하지 않는다.

현재 구현은 실제 운영 CSV, API, Apps Script, Google Sheets, Backend, Database,
머신러닝, Dynamic Spot, 사용자 게시, 공식 Recommendation과 판매·매출 결론을
실행하거나 허용하지 않는다.
