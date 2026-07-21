**TECHNICAL REQUIREMENTS DOCUMENT**

# FreshManager 기술 요구사항 정의서

> EG-6B 현행 단일 수집 파이프라인과 EG-7·EG-8 목표 아키텍처

**문서 ID:** FM-TRD-001

**버전 / 상태:** v1.0 · 공식 기술 기준

**기준일:** 2026-07-22 (Asia/Seoul)

**기술 기준:** main · 6253cc502c9a3c4bc248cf6972f077a99e13f09d

**검증 증거:** Target 19/19 · Full 243/243 · Project Guard PASS=41, SKIP=5, TOTAL=46

**적용 범위:** 현재 EG-6B + 승인 후 EG-7 반복수집·EG-8 분석 목표 구조

> **설계 기준**  현행 구현과 목표 구조를 섞지 않는다. 현재 main은 13개 Area 단일 회차의 원본·메타데이터·Batch Log·Manifest를 제공한다. 반복주기, 잠금, 백업 자동화, 정규화 영속화, 날씨·상권, 분석 파이프라인은 아직 승인·구현되지 않았다.

## 문서 구성

이 문서는 아래 순서로 읽도록 구성했다. PM은 1~4장을 먼저 보고, 구현·검증 담당자는 요구사항과 추적성 장을 이어서 확인한다.

- 1~5장: 기술 범위, 현행 상태, 아키텍처와 실행 흐름
- 6~12장: 인터페이스, 데이터·저장·오류·보안·검증 계약
- 13~18장: 시간 의미, 목표 데이터 모델, EG-7 반복수집·용량·품질
- 19~24장: 분석, 관측성, 테스트, 배포·복구, 기술 의사결정
- 25~27장: 미결정사항, 추적성, 용어·운영 체크리스트

## 1. 목적과 기술 범위

이 TRD는 PRD의 제품 요구를 구현 계약으로 변환한다. 첫째, 현재 main에 병합된 EG-6B 단일 회차 수집기의 실제 동작·데이터·오류·보안·검증 계약을 정확히 기록한다. 둘째, EG-7 반복수집과 EG-8 분석으로 확장할 때 필요한 목표 구조와 승인 지점을 정의한다.

본 문서는 코드보다 우선하지 않는다. 현재 동작은 main commit 6253cc5의 코드와 테스트 결과를 기준으로 하며, 미래 항목은 ‘목표’ 또는 ‘결정 필요’로 표시한다. 실제 API 호출이나 저장구조 변경을 승인하는 문서가 아니다.

## 2. 기술 원칙

- 표준 라이브러리 우선: Python 3.12 호환 표준 라이브러리로 수집·검증·저장을 구현한다.
- 오프라인 우선 검증: Project Guard와 Unit Tests는 DNS·socket·HTTP 접근 0회를 보장한다.
- 명시적 외부 실행: 네트워크 Transport는 승인된 Adapter 안에서만 생성되고 --execute-live가 필요하다.
- 불변 원본: 응답 bytes와 요청별 메타데이터는 배타적 생성으로 저장하고 덮어쓰지 않는다.
- 실패 격리: Area 오류는 기록 후 계속하고, 공통 무결성·설정·저장 오류는 안전 중단한다.
- 시간 의미 보존: 요청·수신·관측·예측 스냅샷·예측 대상·후속 관측 시각을 분리한다.
- 증거 기반 Gate: 코드·테스트·CI·실제 실행 증거와 PM 승인을 모두 거쳐 다음 단계로 간다.
- 경계 최소화: 현재 필요하지 않은 Scheduler·DB·클라우드·ML 의존성을 추가하지 않는다.

## 3. 현행 구현 상태

| **기능** | **상태** | **근거/위치** |
| --- | --- | --- |
| 공식 121개 장소 검증 | 구현 | collector.py / Project Guard |
| POI072 단일 CLI | 구현·실호출 검증 | live.py |
| 대표 3개 순차수집 | 구현·실호출 3/3 | eg5.py |
| 13개 Area 참조 패널 | 구현·승인 | eg6_*.csv |
| 13개 단일 회차 | 구현·병합·오프라인 검증 | eg6b.py |
| 실제 13개 단일 회차 | 미실행 | PM 승인 필요 |
| 반복수집·Scheduler | 미구현 | EG-7 |
| 백업 자동화·잠금 | 미구현 | EG-7 선행 |
| 예측·관측 정규화 영속화 | 부분 | Parser 반환만 구현 |
| 날씨·상권 영속화 | 미구현 | Guard H-505/H-601/H-602 SKIP |
| Feature 분석 파이프라인 | 미구현 | EG-8 |

> **문서 정렬**  PROJECT_STATUS.md, Quality Gates와 비개발자 실행 가이드는 PR #54 병합 이후 상태와 이 TRD의 로컬 Python·주기 미정 원칙을 따른다. 현재 동작 판단은 main 코드·merge commit·검증 기록이 우선이다.

## 4. 현행 시스템 아키텍처

> **실행 흐름**  CLI → 입력·출력 경로 검증 → 참조파일 검증·해시 스냅샷 → API Key 로드 → 저장소 쓰기 Probe → Lazy HTTP Client → 13개 Area Collector → 불변 Raw·Metadata → Collection Log·Manifest → SHA-256 검증 → 요약·종료코드

| **컴포넌트** | **책임** | **경계** |
| --- | --- | --- |
| freshmanager.eg6b | EG-6B 조립·13개 순회·Batch 증거·CLI | main entry point |
| freshmanager.config | .env에서 SEOUL_OPEN_API_KEY 로드·마스킹 | secret boundary |
| freshmanager.http_adapter | 고정 서울시 요청·Redirect 거부·5 MiB 제한 | network boundary |
| freshmanager.collector | 장소 확인·응답 원본 저장·파싱·8필드 Metadata | collection core |
| freshmanager.storage | 배타적·비덮어쓰기 파일 저장·Batch JSON | persistence |
| data/reference/* | 121개 장소와 13개 Area·Spot·S-DoT 기준 | immutable inputs |
| scripts/project_guard_check.py | 문서·데이터·보안·수집 계약 검사 | offline guard |
| tests/* | Fake Transport·임시 파일 기반 단위·통합 계약 | offline tests |
| .github/workflows/ci.yml | PR·main Push에서 Guard와 전체 테스트 | CI |

## 5. EG-6B 실행 시퀀스

1. CLI 인자를 파싱한다. --env-file, --output-root는 필수이고 timeout 기본값은 10초다.
2. --execute-live가 없으면 설정·Transport·Request·출력 저장 없이 preflight 실패 종료코드 2를 반환한다.
3. output-root를 절대경로로 정규화하고 파일시스템 루트·파일·저장소 내부 경로를 거부한다.
4. 공식 121 CSV와 세 EG-6 참조 CSV의 구조·행·연결을 검증하고 SHA-256 스냅샷을 만든다.
5. 명시된 .env에서 API Key를 읽는다. 키는 출력하지 않는다.
6. raw·metadata·batch root에 숨김 Probe 파일을 생성·flush·삭제해 쓰기 가능성을 확인한다.
7. batch_id를 생성하고 FileStorage·BatchStorage·Lazy HTTP Client·Collector를 조립한다.
8. panel_order 1~13 순서로 참조파일 불변성을 재검사한 뒤 고유 request_id를 만들고 장소당 1회 요청한다.
9. Collector는 원본을 먼저 저장하고 HTTP·파싱·필드·장소·인구 범위를 검증한 뒤 8필드 Metadata를 저장한다.
10. Area 오류는 AreaOutcome으로 기록하고 다음 Area를 진행한다. 공통 오류나 참조 변경은 중단한다.
11. 누락된 나머지 Area를 not_attempted로 채우고 종료코드 0·1·2를 계산한다.
12. Collection Log payload와 Manifest를 만들고 Manifest를 먼저 저장한 뒤, 아직 저장 전인 Log payload를 포함해 전체 해시를 검증한다.
13. 검증 성공 후 Collection Log를 배타적으로 저장하고 콘솔에 Area 결과와 회차 요약만 출력한다.

## 6. CLI 계약

| **인자** | **형식/기본** | **계약** |
| --- | --- | --- |
| --env-file | Path · 필수 | 명시적 .env 경로; 자동 탐색하지 않음 |
| --output-root | Path · 필수 | 저장소 밖 안전한 디렉터리 |
| --timeout | float · 10초 | 0 < timeout ≤ 60, 유한값 |
| --execute-live | flag · 기본 false | 실행 의사 확인; PM 승인을 대체하지 않음 |

**승인 후 실행 형태:**

```bash
python3 -m freshmanager.eg6b --env-file /approved/path/.env --output-root /approved/external/root --execute-live
```

> **중요**  위 명령은 계약 예시이며 현재 실제 실행 승인이 아니다. env-file과 output-root는 PM이 정확한 경로를 승인한 뒤 사용한다.

## 7. 외부 API 계약

| **항목** | **현행 값** | **설계 의도** |
| --- | --- | --- |
| Base URL | http://openapi.seoul.go.kr:8088 | 서울시 제공 Endpoint; HTTPS로 임의 변경 금지 |
| Service | citydata_ppltn | 인구 전용 논리 Endpoint |
| Format | json | 응답은 bytes로 원본 보존 후 UTF-8-sig JSON 파싱 |
| Range | 1/5 | 현 Adapter 고정 |
| Area | 공식 AREA_CD | EG-6B 고정 13개 |
| Method | GET | Redirect 거부 |
| Response cap | 5 MiB | 64 KiB chunk로 초과 차단 |
| Timeout | 기본 10초, 최대 60초 | 장소별 1회 |

API Key는 URL path에 들어가지만 완성 URL을 로그·예외·Manifest에 저장하지 않는다. Redirect를 거부해 인증정보가 다른 위치로 전달되는 것을 차단한다.

## 8. 참조 데이터 계약

| **파일** | **인코딩** | **필수 검증** |
| --- | --- | --- |
| seoul_121_places.csv | utf-8-sig | 121행·5열·고유 AREA_CD·POI072=여의도 |
| eg6_area_panel.csv | utf-8 | 13행·panel_order 1~13·approved/active=true |
| eg6_spot_master.csv | utf-8 | 13 Spot·공식 Area 연결·STATION_CENTER_PROXY |
| eg6_sdot_links.csv | utf-8 | 13 Link·고유 Spot·최근 활성 센서 |

EG-6B는 네 파일의 SHA-256을 preflight에서 저장하고, 각 Area 전후와 Manifest 검증에서 변경 여부를 확인한다. 참조 변경은 수집 중 응답 오류가 아니라 공통 무결성 오류로 취급한다.

## 9. 도메인 객체와 데이터 계약

### 9.1 요청·결과 객체

| **객체** | **필드 요약** | **역할** |
| --- | --- | --- |
| Place | category, number, area_code, area_name, english_name | 공식 CSV 행 |
| CollectionRequest | request_id, requested_at, area_code, endpoint_name | 한 Area 요청 문맥 |
| HttpResponse | status_code, body | 원본 bytes 유지 |
| CollectionResult | metadata, metadata_path, population | 상태와 선택적 정규화 결과 |
| AreaOutcome | order, code, request_id, attempted, status, raw, metadata | 회차 Area 결과 |
| Eg6bSummary | batch 집계·파일·해시·종료코드 | 콘솔 요약 |

### 9.2 요청별 최소 메타데이터

| **필드** | **형식** | **의미** | **Null 규칙** |
| --- | --- | --- | --- |
| request_id | string UUID | 요청 고유 ID | 항상 |
| area_code | string | 공식 AREA_CD | 항상 |
| endpoint_name | string | citydata_ppltn 논리명 | 항상 |
| requested_at | ISO 8601 KST | 요청 생성 시각 | 항상 |
| received_at | ISO 8601 KST | 응답 또는 실패 확인 시각 | 항상 |
| http_status | int\|null | HTTP 상태 | 요청 전 실패는 null |
| collection_status | enum | 수집 처리 결과 | 항상 |
| raw_file_path | path\|null | 저장된 원본 경로 | 원본 미저장 시 null |

### 9.3 현재 인구 정규화 반환

| **필드** | **형식/의미** | **검증** |
| --- | --- | --- |
| area_code / area_name | 응답 식별 | 공식 CSV와 정확히 일치 |
| population_reference_time | 관측 기준시각 | PPLTN_TIME 원문 |
| congestion_level | 공식 혼잡도 | 임의 점수화 없음 |
| population_min / max | 정수 | min ≤ max |
| forecast_available | boolean | FCST_YN=Y |
| forecasts | list | target_time, congestion, min, max |

> **현재 한계**  이 정규화 결과는 Collector 반환값으로만 존재하며 EG-6B는 별도 분석용 observation·forecast 파일로 영속화하지 않는다. 반복수집 전 이 공백을 별도 승인된 저장계약으로 해결해야 한다.

### 9.4 Batch Collection Log

- 버전·식별: collector_version, data_version, batch_id, panel_version, collection_purpose
- 시간: scheduled_at(null), started_at, finished_at, elapsed_seconds
- 집계: expected_area_count, attempted_count, success_count, failure_count, failed_area_codes, retry_count
- 파일: raw_file_count, metadata_file_count
- 판정: exit_code
- 상세: panel_order, area_code, request_id, attempted, collection_status, raw_file, metadata_file

### 9.5 Manifest

| **영역** | **계약** |
| --- | --- |
| header | data_version, batch_id, created_at, hash_algorithm=sha256 |
| reference_files[] | reference_type, path, byte_size, sha256 |
| artifacts[] | artifact_type, relative_path, byte_size, sha256, area_code, request_id |
| artifact types | raw_json, metadata, collection_log |

## 10. 저장 구조와 불변 쓰기

output-root 아래 단계별 경로를 자동 적용한다. 참조파일과 소스 저장소 내부에는 실제 수집 산출물을 쓰지 않는다.

| **산출물** | **상대 경로** |
| --- | --- |
| Stage root | stages/eg6b_single_13 |
| Raw | stages/eg6b_single_13/data/raw/population/YYYY/MM/DD/{AREA}_{TIME}_{REQUEST}.json |
| Metadata | stages/eg6b_single_13/data/processed/collection_logs/YYYY/MM/DD/{AREA}_{TIME}_{REQUEST}.metadata.json |
| Batch | stages/eg6b_single_13/data/processed/batches/{batch_id}/collection_log.json |
| Manifest | stages/eg6b_single_13/data/processed/batches/{batch_id}/manifest.json |

### 10.1 배타적 저장 알고리즘

1. 대상 디렉터리를 생성한다.
2. 같은 디렉터리에 숨김 .partial 임시파일을 생성한다.
3. payload를 쓰고 flush·fsync한다.
4. os.link로 최종 경로를 배타적으로 생성한다.
5. 최종 경로가 이미 있으면 StorageError로 처리하며 덮어쓰지 않는다.
6. 성공·실패와 무관하게 임시파일을 제거한다.

이 방식은 기존 최종 파일 보호와 부분 파일 노출 방지에 초점을 둔다. 파일시스템이 hard link와 fsync 의미를 지원하는지 실제 운영 볼륨에서 사전 확인해야 한다.

## 11. 오류 분류와 종료코드

| **상태** | **범위** | **의미** | **회차 동작** |
| --- | --- | --- | --- |
| success | Area | 정상 응답·저장·검증 | 계속 |
| api_error | Area | HTTP 비2xx, XML/JSON 서비스 오류, 연결 실패 | 계속 |
| timeout | Area | 요청 제한시간 초과 | 계속 |
| parse_error | Area | JSON decode 실패 | 계속·원본 유지 |
| validation_error | Area/Preflight | 장소·필드·범위·참조 불일치 | 문맥에 따라 계속/중단 |
| config_error | 공통 | .env 또는 Key 오류 | 중단 |
| storage_error | 공통 | Raw/Metadata/Batch 저장 실패 | 중단 |
| internal_error | 공통 | 예상 밖 예외 | 중단 |
| not_attempted | 회차 | 공통 중단 후 남은 Area | 증거에 기록 |

| **종료** | **조건** | **운영 의미** |
| --- | --- | --- |
| 0 | 13개 모두 success | 단일 회차 기술 성공; Gate PASS는 PM 별도 |
| 1 | 공통 오류 없이 하나 이상 Area 실패 | 부분 실패 증거 보존·재호출은 별도 승인 |
| 2 | 입력·참조·설정·저장·보안·내부·무결성 공통 오류 | 안전 중단 |

## 12. 보안과 안전 통제

- Secret 저장: 실제 Key는 Git 제외 .env에만 두고 .env.example에는 자리표시자만 둔다.
- Secret 사용: env-file 경로를 명시적으로 주입하고 코드가 저장소 .env를 자동 선택하지 않는다.
- Secret 노출: 완성 URL, Key, 실제 .env 내용은 콘솔·예외·문서·Manifest에 기록하지 않는다.
- Network boundary: urllib 사용은 http_adapter.py의 승인 Transport에만 존재한다.
- Redirect: 인증정보 전달 위험을 줄이기 위해 모든 Redirect를 거부한다.
- Resource limit: 응답은 5 MiB로 제한하고 timeout을 60초 이하로 제한한다.
- Output boundary: EG-6B output-root는 저장소 내부·파일시스템 루트·파일을 거부한다.
- Reference immutability: 네 참조파일을 읽기 전용으로 검증하고 실행 전후 해시를 비교한다.
- Approval boundary: --execute-live는 PM 승인의 기술적 대체물이 아니다.
- Privacy: 현재 개인 위치·고객정보·실제 판매데이터를 수집하지 않는다.

## 13. 시간 의미와 Point-in-time 계약

| **시각** | **의미** | **현재/목표 위치** | **규칙** |
| --- | --- | --- | --- |
| requested_at | 요청 생성 | 파일명·메타데이터 | KST aware datetime |
| received_at | 응답/실패 확인 | 메타데이터 | KST aware datetime |
| population_reference_time | 서울시 관측 기준 | PPLTN_TIME | 응답 원문 |
| forecast_snapshot_time | 예측을 확보한 스냅샷 | 목표 저장모델 | 공식 발행시각이 없으면 요청시각과 관계를 명시 |
| forecast_target_time | 예측 대상 | FCST_TIME | 미래 시점 |
| followup_observation_time | 대상시점 후 관측 | 목표 분석모델 | 예측 평가 기준 |
| weather_forecast_issued_at | 날씨 예보 발행 | 목표 날씨모델 | 미래정보 누수 방지 |

> **미래정보 누수 금지**  분석 시점에 알 수 없었던 후속 날씨·관측·수정 데이터를 과거 예측 입력으로 사용하지 않는다. Join은 각 레코드의 available_at 또는 snapshot time이 의사결정 시각 이하인지 확인해야 한다.

## 14. 목표 정규화 데이터 모델

EG-7 전에 Raw와 Metadata만으로는 리드타임별 평가를 반복하기 어렵다. 다음 데이터셋은 목표 계약이며 저장 형식(CSV 분할 또는 경량 로컬 DB)은 PM 승인 후 결정한다.

| **데이터셋** | **고유키** | **핵심 내용** |
| --- | --- | --- |
| population_observations | area_code + population_reference_time + request_id | 현재 인구·혼잡·구성·요청시각 |
| population_forecasts | area_code + snapshot + target + request_id | 예측 min/max·혼잡·lead_time |
| collection_logs | request_id | 승인된 8필드 메타데이터 |
| batch_runs | batch_id | 회차 집계·버전·종료코드 |
| weather_forecasts | area + issue + target + request | 예보값과 사용가능 시각 |
| weather_observations | area + observation_time + request | 사후 실제 날씨 |
| commerce_observations | area + reference_time + request | 활동단계·지원상태·시간차 |
| spot_context | context_version + spot_id | Area–Spot–S-DoT·현장검증 상태 |

### 14.1 버전 계약

- collector_version: 수집 실행 의미가 바뀔 때 증가한다.
- data_version: 저장 스키마·필드 의미가 바뀔 때 증가한다.
- panel_version: Area 패널과 순서가 바뀔 때 증가한다.
- context_version: Spot·S-DoT·현장검증 문맥이 바뀔 때 목표 구조로 추가한다.
- parser_version: 현재 최소 8필드 메타데이터에는 넣지 않으며 정규화 저장 설계에서 별도 승인한다.

## 15. EG-7 목표 아키텍처

> **목표 흐름**  승인 Scheduler/수동 Runner → 단일 실행 Lock → EG-6B Batch Core → 불변 Raw·Metadata·Batch → 정규화 Observation·Forecast → 품질 집계 → 검증된 백업 → 상태 보고

| **컴포넌트** | **책임** | **상태** |
| --- | --- | --- |
| Run Policy | 승인된 주기·운영시간·호출예산·대상 패널 | PM 승인 필요 |
| Single-instance Lock | 동일 output-root·패널의 중복 실행 차단 | 필수 |
| Batch Core | 현 EG-6B 로직 재사용; 장소별 1회·실패 격리 | 재사용 |
| Normalizer | 관측·예측 스냅샷 영속화 | 신규 |
| Quality Aggregator | 지연·결측·스키마·성공률·용량 | 신규 |
| Backup Worker | 외장 또는 승인 클라우드 복사·SHA-256·실패 기록 | 신규 |
| Run Registry | 예정 슬롯·실행·누락·중복·종료 상태 | 결정 필요 |
| Context Registry | 패널·Spot·S-DoT 버전 연결 | 결정 필요 |

### 15.1 반복 실행 상태기계

- SCHEDULED: 승인된 슬롯이 생성됐으나 아직 실행되지 않음
- RUNNING: Lock 획득 후 Batch 시작
- COMPLETED: 종료코드 0, 증거·백업 정책 충족
- COMPLETED_WITH_AREA_FAILURES: 종료코드 1, 부분실패 증거 보존
- FAILED_COMMON: 종료코드 2, 공통 오류로 중단
- MISSED: 승인 슬롯에 실행 기록이 없음
- BLOCKED_DUPLICATE: Lock 충돌로 중복 실행 차단
- BACKUP_PENDING / BACKUP_FAILED: 수집 성공과 백업 상태를 분리

### 15.2 재시도 정책

현 EG-6B는 retry_count=0이며 이를 유지한다. EG-7에서 자동 재시도가 필요하다면 다음을 별도 승인해야 한다: 재시도 대상 상태, 최대 횟수, backoff, 호출예산, 동일 request_id 재사용 여부, 원본·메타데이터 연결, 재시도로 인한 패널 내 시간차와 분석 영향. 승인 전에는 실패 Area를 자동 재호출하지 않는다.

## 16. 백업과 복구

- EG-7 진입 전 외장 저장장치 주기 복사 또는 PM 승인 클라우드 폴더 백업 중 하나를 선택한다.
- 수집 실행은 로컬 Python에 유지하며 백업 목적지 장애가 수집 원본을 삭제·덮어쓰게 해서는 안 된다.
- 백업 단위는 완결된 batch directory와 해당 날짜의 Raw·Metadata다.
- 원본 Manifest 또는 별도 backup manifest로 byte_size·SHA-256을 재검증한다.
- 백업 성공·실패·완료시각·대상 batch_id를 별도 상태로 기록한다.
- 정기적으로 샘플 회차를 복구해 해시·경로·JSON 파싱을 확인한다.
- 보관·삭제 정책은 5주 PoC와 최종 리포트 완료 전 삭제 금지를 기본으로 별도 승인한다.

## 17. 데이터 품질 계약

| **검사** | **규칙** | **주기** |
| --- | --- | --- |
| 참조 무결성 | 헤더·행·고유성·연결·SHA-256 | 회차 전·중·Manifest |
| 응답 구조 | RESULT, 정확히 1 Area, 필수 필드 | 요청별 |
| 인구 범위 | min ≤ max, 숫자 변환 가능 | 요청별 |
| 예측 구조 | FCST_YN=Y이면 비어 있지 않은 배열·필수 4필드 | 요청별 |
| 장소 정합성 | 응답 code/name = 공식 CSV | 요청별 |
| 회차 완전성 | expected=13, 대상=성공+실패, 중복·누락 없음 | 회차별 |
| 지연 | requested_at - PPLTN_TIME 분포 | 회차·장기 |
| 예측 간격 | 개수·대상시간·간격 변화 | 회차·장기 |
| 파일 무결성 | 경로·크기·SHA-256 | 회차·백업 |
| 지원 상태 | not_supported ≠ missing ≠ 0 | 날씨·상권 |

## 18. 성능·호출량·저장용량

수집주기를 정하지 않은 상태에서 시스템 규모는 식으로 관리한다. 아래 수치는 상한 계획값이며 실제 API 응답 크기·소요시간을 대체하지 않는다.

- 한 회차 최대 요청 수 = 13 Area × 장소당 1회 = 13회
- 순차 timeout 최악 상한 = 13 × timeout(최대 60초) = 약 13분 + 처리 오버헤드
- Raw 이론 상한 = 13 × 5 MiB = 65 MiB/회차; 실제 측정값으로 재산정 필요
- 일 호출량 = 13 × 일 회차 수; 재시도 승인 시 별도 예산을 더한다.
- PoC Raw 용량 = 회차 수 × Area당 평균 Raw bytes + Metadata·Batch 증거
- 백업 용량 = 원본 보관 용량 × 복제본 수 + Manifest/운영 여유
- 병렬 호출은 현재 금지한다. 향후 검토 시 API 제한·시각 정렬·실패 격리 영향을 다시 설계한다.

## 19. EG-8 분석 기술 구조

> **분석 흐름**  검증된 Batch → Point-in-time 정규화 → 포함·제외 규칙 → 기준선 B0/B1/B2 → 공식 예측 비교 → 피크·장소·소비·날씨 분석 → Gate A/B 리포트

| **분석** | **방법** | **목적** |
| --- | --- | --- |
| B0 최근값 유지 | 직전 관측값을 미래 비교 기준으로 사용 | 단순 기준선 |
| B1 동일 요일·시간 | 동일 요일·시간의 과거 평균 | 반복성 |
| B2 최근 4주 평균 | 평가주 이전 4주 동일 요일·시간 | 전향 평가 기준 |
| 서울시 예측 | 스냅샷·대상·후속 관측 연결 | 리드타임별 비교 |
| 피크 | 기준선 대비 상승·지속·비관행 시간 | 후보 시간창 |
| 장소 | 절대값·상대순위·변동성 | 분별력 |
| 소비·날씨 | 지원상태와 point-in-time join | 보조 설명 |

### 19.1 분석 산출물

- 데이터 품질 대시보드용 CSV/차트: 성공률, 결측, 지연, 스키마·파일 무결성
- 예측 평가표: MAE, RMSE, 상대오차, 구간 포함률, 혼잡도 일치율, 리드타임
- 시간패턴 차트: 요일·시간 기준선, 변화율, 변동성, 피크 지속시간
- 장소 비교표: Area 유형, 인구 기회, 혼잡 위험, S-DoT 지원 여부
- Gate A/B 판정 메모: 사실·해석·가설·한계·다음 행동

## 20. 관측성·운영 보고

현행 콘솔은 민감하지 않은 고정 키-값 형식만 출력한다. EG-7에서는 실행 슬롯·회차·백업·품질 상태를 추가하되 API Key·완성 URL·Raw 전문·로컬 절대경로를 출력하지 않는다.

| **보고** | **필드** | **시점** |
| --- | --- | --- |
| Area 결과 | area_code, request_id, status, raw_saved, metadata_saved | 요청 직후 |
| Batch 요약 | target/attempt/success/failure, elapsed, files, hash, exit | 회차 종료 |
| 품질 요약 | staleness, schema, forecast count, duplicate, missing | 목표 EG-7 |
| 백업 요약 | batch_id, destination class, verify, status | 목표 EG-7 |
| 운영 경보 | 연속 실패·저장 부족·Manifest 실패·missed slot | 목표 EG-7 |

## 21. 검증 전략

| **계층** | **검증 대상** | **현재 증거** |
| --- | --- | --- |
| Unit | 파서·설정·저장·요청·상태 | 가짜 bytes·임시 경로 |
| Adapter | 정상·HTTP 오류·Timeout·Redirect·5 MiB | 주입 Transport |
| Collector | 6개 오류·원본·8필드 Metadata | Fake Client |
| EG-6B Target | 13개 순서·실패 격리·Manifest·경로 | 19/19 PASS |
| Project Guard | 문서·데이터·보안·오프라인·H-706 | PASS 41 / SKIP 5 / TOTAL 46 |
| Full | 저장소 전체 unittest | 243/243 PASS |
| CI | 모든 PR·main Push | PR #54와 main CI SUCCESS |
| Live smoke | 실제 API·외부 output-root | PM 승인 후 별도; 현재 미실행 |

Project Guard의 H-706은 EG-6B 완전성을 검증해 PASS했다. H-707은 반복주기와 백업 Gate가 승인되지 않아 SKIP이며 현재 단계에서는 올바른 상태다. H-504·H-505·H-601·H-602는 예측 영속화·날씨·상권 구현 전이므로 남은 SKIP 범위에 포함된다.

## 22. 배포·Rollout 계획

- T0 완료 — PR #54 병합, main/PR CI, 19 Target·243 Full·Guard 41 PASS
- T1 승인 필요 — 실제 env/output Preflight, 참조 해시, 저장공간·Probe, 최대 13회 호출
- T2 판정 — Raw·Metadata·Collection Log·Manifest·hash와 실패 목록 검토 후 EG-6B PASS 결정
- T3 설계 승인 — 주기·호출예산·Lock·백업·정규화·버전 계약
- T4 EG-7 Pilot — 제한된 기간 동일 13개 반복, 품질·용량·운영 안정성 측정
- T5 EG-8 — 4주 기준선+5주차 평가, Gate A/B 분석
- T6 후속 — 현장·인터뷰 결과로 121개 확대 또는 서비스 실증 여부 결정

## 23. 중단·복구·변경관리

- 참조파일·Manifest 해시 불일치 시 해당 회차를 정상으로 승격하지 않고 원본을 보존한다.
- 부분 실패 회차도 삭제하지 않으며 실패 Area 자동 재호출은 별도 승인한다.
- 공통 오류 후 not_attempted Area를 숨기지 않고 회차 Log에 남긴다.
- 정규화 파서 수정은 Raw 재수집보다 Raw 재처리를 우선하며 data/parser version을 기록한다.
- 스키마 변경 시 기존 파일을 in-place 변환하지 않고 새 버전 산출물을 생성한다.
- 백업 복구는 새 위치에 복원하고 Manifest 검증 후 분석 입력으로 승격한다.
- 실제 수집 산출물은 자동 삭제·덮어쓰기하지 않는다. 삭제·보관 만료는 별도 PM 승인이다.
- Git 변경은 Issue→Branch→검증→승인된 Stage→PR→CI→PM Merge 순서를 따른다.

## 24. 기술 의사결정 기록

| **ID** | **결정** | **근거** | **상태** |
| --- | --- | --- | --- |
| ADR-01 | 로컬 Python·표준 라이브러리 | 1인 운영·오프라인 검증·의존성 최소화 | 유지 |
| ADR-02 | 한 호출=한 Area·순차 처리 | API 계약·실패 격리·시간 추적 | 유지 |
| ADR-03 | 원본 bytes 불변 저장 | 재현·감사·파서 변경 대응 | 유지 |
| ADR-04 | Metadata 8필드 최소 계약 | PoC 복잡도 제한 | 유지 |
| ADR-05 | 자동 재시도 0회 | 호출량·증거 명확성 | EG-7 전 재검토 가능 |
| ADR-06 | Manifest·SHA-256 | 참조·산출물 무결성 | 유지 |
| ADR-07 | output-root 저장소 밖 | 소스·기준데이터와 실데이터 분리 | 유지 |
| ADR-08 | Google Sheets 수집 미채택 | 현행 로컬 Python·원본 보존·승인 Gate와 충돌 | 폐기 지침 |
| ADR-09 | Spot은 Recommendation Context | Area 수집기와 현장 후보 문맥 분리 | 후속 설계 |

## 25. 미결정 기술사항

- O-01 실제 EG-6B env-file·output-root·실행시각과 수집 승인
- O-02 반복수집 간격·운영시간·일 호출예산·공휴일 처리
- O-03 단일 실행 Lock 방식과 stale lock 복구 규칙
- O-04 정규화 저장 형식: 분할 CSV vs SQLite 등 표준 라이브러리 기반 로컬 DB
- O-05 parser_version과 schema migration 기록 방식
- O-06 백업 목적지·주기·암호화·보관·복구 시험
- O-07 디스크 여유 임계치와 수집 중단 정책
- O-08 날씨·상권 Endpoint·실응답 필드·지원상태 Enum
- O-09 context_version과 현장검증 갱신 방식
- O-10 EG-7 재시도 도입 여부와 호출량·시간 정렬 영향
- O-11 Quality Gate·Project Status의 post-merge 상태 정렬

## 26. PRD–구현 추적성

| **PRD** | **구현/목표** | **검증·상태** |
| --- | --- | --- |
| FR-01 | eg6b._validate_references | H-703/H-706, test_eg6b |
| FR-02 | eg6b.build_parser/_validated_output_paths | CLI·preflight tests |
| FR-03 | collector.Collector + storage.FileStorage | H-501~503/H-506 |
| FR-04 | eg6b._collection_log/_manifest/_verify_manifest | H-706, 19 Target |
| FR-05 | collector.parse_population_response | 부분: 영속화 미구현, H-504 SKIP |
| FR-06 | Project Guard + Batch evidence | 부분: 장기 품질 집계 미구현 |
| FR-07 | 목표 weather datasets | H-505 SKIP |
| FR-08 | 목표 commerce_observations | H-601/H-602 SKIP |
| FR-09 | docs/analysis/ANALYSIS_PLAN.md | EG-8 미구현 |
| FR-10 | EG5 report + 목표 reporting | 부분 |
| FR-11 | Collector statuses + eg6b exit 0/1/2 | H-704/H-705/H-706 |
| FR-12 | --execute-live + AGENTS/Git workflow | Project Guard/CI/PM |

## 근거 자료

문서의 사실·상태·계약은 아래 로컬 저장소 자료와 완료 기록을 대조해 작성했다. 경로는 FreshManager 저장소 루트 기준이다.

| **자료** | **사용 목적** |
| --- | --- |
| freshmanager/eg6b.py | EG-6B CLI·참조 검증·13개 순회·Batch Log·Manifest |
| freshmanager/collector.py | 요청·응답 파싱·원본·8필드 메타데이터 계약 |
| freshmanager/http_adapter.py | 서울시 요청·Redirect·Timeout·응답 상한 |
| freshmanager/storage.py | 배타적 비덮어쓰기 파일 저장 |
| tests/test_eg6b.py | EG-6B Target 계약 검증 |
| scripts/project_guard_check.py | 46개 Project Guard 등록·실행 |
| docs/rules/DATA_COLLECTION_RULES.md | 단계별 저장·시간·원본·실패·배치 규칙 |
| docs/testing/PROJECT_GUARD_SPEC.md | 검사 ID·판정·종료코드 기준 |
| PR #54 완료 기록 | 19/19 Target, 243/243 Full, PASS=41/SKIP=5/TOTAL=46, CI 성공 |

## 부록 A. 운영 Preflight 체크리스트

- 현재 main HEAD와 작업 트리가 승인 상태인가?
- PRD/TRD 기준보다 코드·Issue·PM 최신 지시가 변경되지 않았는가?
- 실제 최대 13회 호출에 대한 PM 승인이 있는가?
- env-file과 output-root의 정확한 경로가 승인됐는가?
- output-root가 저장소 밖이며 충분한 저장공간과 hard link를 지원하는가?
- 네 참조파일과 13개 패널이 불변이며 Project Guard가 통과했는가?
- 일반 테스트와 실제 실행이 분리됐는가?
- 실행 후 Raw·Metadata·Log·Manifest·해시·종료코드를 검토할 준비가 됐는가?
- 실패 Area를 자동 재호출하지 않는다는 원칙을 확인했는가?
- 실행 결과가 EG-6B PASS를 자동 의미하지 않으며 PM 판정이 남아 있는가?

## 부록 B. 용어

| **용어** | **정의** |
| --- | --- |
| Batch | 승인된 Area 목록을 한 번 순차 처리한 회차 |
| Preflight | 네트워크 호출 전에 입력·참조·설정·저장 가능성을 확인하는 단계 |
| Manifest | 참조파일과 산출물의 경로·크기·SHA-256 목록 |
| Lazy Client | 첫 실제 fetch 시점까지 네트워크 Transport 생성을 지연하는 객체 |
| Point-in-time join | 의사결정 시점에 실제로 이용 가능했던 데이터만 연결하는 방식 |
| Common failure | 회차 전체의 안전성을 해치는 설정·저장·무결성·내부 오류 |
| Area failure | 해당 Area만 실패하고 다음 Area 진행이 가능한 API·Timeout·파싱·검증 오류 |
| Recommendation Context | Area 신호와 Spot·S-DoT·현장 상태를 연결하는 후속 문맥 계층 |
