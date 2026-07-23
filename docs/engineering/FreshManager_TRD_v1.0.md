**TECHNICAL REQUIREMENTS DOCUMENT**

# FreshManager 기술 요구사항 정의서

> EG-6B 단일 수집·Backup과 EG-7 1시간 파일럿 Controller, EG-8 및 후속 Recommendation 목표 아키텍처

**문서 ID:** FM-TRD-001

**버전 / 상태:** v1.0 · 공식 기술 기준

**기준일:** 2026-07-23 (Asia/Seoul)

**기술 기준:** EG-6B Area Collector·독립 Backup Worker·EG-7 오프라인 Controller와 파생 인덱스 계약

**현재 상태 기준:** Branch·PR·Issue·실행·검증 상태는
[`PROJECT_STATUS.md`](../../PROJECT_STATUS.md)를 단일 기준으로 사용한다.

**적용 범위:** EG-6B 완료 + 승인된 EG-7 오프라인 구현·EG-8 Feature 분석 + `PLANNED`
Recommendation MVP Workstream(Gate number `NOT_ASSIGNED`) 목표 구조

**2026-07-22~23 완료·진행 이력:** Issue #60에서 Google Drive for Desktop Sync와 분리된
1회 실행형 Backup Worker·append-only Receipt·H-708을 구현했고 PR #61로 `main`에
병합했다. 첫 EG-6B 실제 Batch 13/13, 품질·백업 Closeout 후 Issue #69가 EG-7
1시간·12회차 Controller와 파생 인덱스 범위를 승인했고 Issue #70에서 구현한다.
5분은 `PM_APPROVED_FIXED` 장기 반복수집 기준이며 이 1시간은 주기 선택이 아니라
첫 구현·운영 안전성 검증이다.
Issue #58의 Area Core Observation·선택적 S-DoT Supporting Observation·Spot Candidate
Evaluation·Recommendation 결과 구조는 유지하되 동적 S-DoT는 EG-7에서 수집하지 않는다.
파일 버전은 PM의 별도 결정 전 `v1.0`을 유지한다.

> **설계 기준**  구현 계약과 목표 구조를 섞지 않는다. EG-6B는 13개 Area 회차의
> 원본·메타데이터·Batch Log·Manifest를 제공하고, 독립 Backup Worker는 완료 Batch의
> 검증·복사·Receipt를 담당한다. EG-7은 이 둘을 승인 슬롯마다 한 번씩 조립하고
> canonical 증거 기반 Slot·Area Index와 Summary를 파생한다. 일반 CSV Exporter,
> 날씨·상권과 분석 파이프라인의 현재 상태는 `PROJECT_STATUS.md`에서 확인한다.

## 문서 구성

이 문서는 아래 순서로 읽도록 구성했다. PM은 1~4장을 먼저 보고, 구현·검증 담당자는 요구사항과 추적성 장을 이어서 확인한다.

- 1~5장: 기술 범위, 현행 상태, 아키텍처와 실행 흐름
- 6~12장: 인터페이스, 데이터·저장·오류·보안·검증 계약
- 13~18장: 시간 의미, 목표 데이터 모델, EG-7 반복수집·용량·품질
- 19~24장: 분석, 관측성, 테스트, 배포·복구, 기술 의사결정
- 25~27장: 미결정사항, 추적성, 용어·운영 체크리스트

## 1. 목적과 기술 범위

이 TRD는 PRD의 제품 요구를 구현 계약으로 변환한다. 첫째, 현재 main에 병합된 EG-6B 단일 회차 수집기의 실제 동작·데이터·오류·보안·검증 계약을 정확히 기록한다. 둘째, EG-7 반복수집, EG-8 Feature 분석과 별도 Recommendation MVP Workstream으로 확장할 때 필요한 목표 구조와 승인 지점을 정의한다. Recommendation MVP는 공식 Gate가 아니라 별도 승인할 계획 Workstream이다.

본 문서는 코드보다 우선하지 않는다. EG-6B Collector와 Backup Worker의 기술 계약은
병합된 구현과 검증 결과를 기준으로 한다. 현재 Branch·PR·Issue·실행 상태는
`PROJECT_STATUS.md`를 따르고, 미래 항목은 ‘목표’ 또는 ‘결정 필요’로 표시한다.
이 문서 자체는 실제 API 호출을 승인하지 않는다.

## 2. 기술 원칙

- 표준 라이브러리 우선: Python 3.12 호환 표준 라이브러리로 수집·검증·저장을 구현한다.
- 오프라인 우선 검증: Project Guard와 Unit Tests는 DNS·socket·HTTP 접근 0회를 보장한다.
- 명시적 외부 실행: 네트워크 Transport는 승인된 Adapter 안에서만 생성되고 --execute-live가 필요하다.
- 불변 원본: 응답 bytes와 요청별 메타데이터는 배타적 생성으로 저장하고 덮어쓰지 않는다.
- 실패 격리: Area 오류는 기록 후 계속하고, 공통 무결성·설정·저장 오류는 안전 중단한다.
- 시간 의미 보존: 요청·수신·관측·예측 스냅샷·예측 대상·후속 관측 시각을 분리한다.
- 증거 기반 Gate: 코드·테스트·CI·실제 실행 증거와 PM 승인을 모두 거쳐 다음 단계로 간다.
- 경계 최소화: 1시간 Controller 외 영구 Scheduler·DB·Google Drive API/OAuth/SDK·ML
  의존성을 추가하지 않는다. Backup Worker는 Batch 완료 직후 한 번 호출하고 원격
  동기화는 Google Drive for Desktop Sync에 위임한다.

## 3. 기술 구성과 상태 기준

| **기능** | **기술 계약** | **근거/위치** |
| --- | --- | --- |
| 공식 121개 장소 검증 | 공식 CSV를 유일한 장소 기준으로 사용 | collector.py / Project Guard |
| POI072 단일 CLI | 한 Area 수집 계약 | live.py |
| 대표 3개 순차수집 | 고정 3개 Area·실패 격리 계약 | eg5.py |
| 13개 Area 참조 패널 | Area·Spot Proxy·S-DoT 정적 연결 계약 | eg6_*.csv |
| 13개 단일 회차 | 순차 수집·Batch Log·Manifest·SHA-256 계약 | eg6b.py |
| Google Drive Backup Worker | 완료 Batch 검증·복사·잠금·Receipt 계약 | freshmanager.backup |
| EG-7 1시간 Controller | 불변 계획·5분 경계·잠금·실패중단·사건로그 | freshmanager.eg7 |
| EG-7 파생 인덱스 | 12행 Slot·최대 156행 Area·중복·Summary | freshmanager.eg7 |
| Google Drive for Desktop Sync | 논리 Backup Root와 동기화 책임 분리 | `FreshManager-Data/`; 계정 이메일·절대경로 비기록 |
| Apps Script 13개 Area 반복수집 | 5분 벽시계 트리거·POI 코드 호출·Script Properties Key·v3 시트 저장 | PoC 상시 Runtime; 저장소 밖 Apps Script 프로젝트, 소스 버전관리는 `PLANNED` |
| Raw-to-CSV Exporter | 첫 실제 Batch 이후 확정할 파생자료 계약 | 별도 승인 대상 |
| S-DoT 관측 데이터 계층 | Area Collector와 독립적인 보조 Feature 계층 | EG-7 제외·후속 별도 승인 |
| Spot Candidate Evaluation | Area·선택적 S-DoT·공간 Context 결합 | EG-8; Score·가중치·임계값 OPEN_DECISION |
| Recommendation MVP | 별도 계획 Workstream | Gate number `NOT_ASSIGNED` |

> **상태 정렬**  위 표는 기술 책임을 정의하며 완료·미완료 상태표가 아니다. 현재
> Branch·PR·Issue·실행·검증 결과는 `PROJECT_STATUS.md`에서만 확인한다.

## 4. 현행 시스템 아키텍처

> **실행 흐름**  CLI·입력·출력 Root 검증 → Source·Sync·Receipt·Lock 읽기 전용 충돌 검사 → 참조파일 검증·해시 스냅샷 → Source Batch 원자적 예약 → 예약 디렉터리 동일성 검증과 예약 인식 Storage 조립 → API Key 로드 → Lazy HTTP Client → 13개 Area Collector → 예약 인식 불변 Raw·Metadata·Collection Log·Manifest 쓰기 → SHA-256 검증 → 요약·종료코드

| **컴포넌트** | **책임** | **경계** |
| --- | --- | --- |
| freshmanager.eg6b | EG-6B 조립·13개 순회·Batch 증거·CLI | main entry point |
| freshmanager.config | .env에서 SEOUL_OPEN_API_KEY 로드·마스킹 | secret boundary |
| freshmanager.http_adapter | 고정 서울시 요청·Redirect 거부·5 MiB 제한 | network boundary |
| freshmanager.collector | 장소 확인·응답 원본 저장·파싱·8필드 Metadata | collection core |
| freshmanager.storage | 배타적·비덮어쓰기 파일 저장·Batch JSON | persistence |
| data/reference/* | 121개 장소와 13개 Area·Spot·S-DoT 기준 | immutable inputs |
| scripts/project_guard_check.py | 문서·데이터·보안·수집 계약 검사 | offline guard |
| freshmanager.backup | 완료 Batch 검증·로컬 Sync 복사·Lock·Receipt | 네트워크 없음 |
| freshmanager.eg7 | 1시간 계획·벽시계 회차·전역 Lock·EG-6B/Backup 조립·파생 출력 | 영구 Scheduler 아님 |
| tests/* | Fake Transport·임시 파일 기반 단위·통합 계약 | offline tests |
| .github/workflows/ci.yml | PR·main Push에서 Guard와 전체 테스트 | CI |

### 4.1 공식 목표 서비스 데이터 아키텍처

```text
Core Observation: EG-6B Area Observation — 모든 승인 Area에서 필수
Optional Supporting Observation: S-DoT — 지원·접근·수집·품질조건 충족 시만 사용
Additional Context: Spatial Context + Field Validation + Operational Constraints

Area Feature + 선택적 S-DoT Feature + Additional Context
→ Spot Candidate Evaluation
→ 신뢰 가능한 Spot: SPOT / 없는 경우: AREA + fallback_reason
```

현행 EG-6B는 Core Area Observation만 수집한다. `eg6_spot_master.csv`와
`eg6_sdot_links.csv`는 승인된 정적 패널 연결을 검증하는 immutable input이지만
Spot 좌표나 센서 관측값을 API 요청에 사용하지 않는다. 동적 S-DoT 수집과 Spot
Candidate Evaluation은 후속 독립 책임이며, 그 실패는 Area 회차를 중단시키지
않는다. S-DoT 미지원 6개 Area도 Area 분석과 추천 후보에서 제외하지 않는다.

## 5. EG-6B 실행 시퀀스

1. CLI 인자를 파싱한다. --env-file, --output-root는 필수이고 timeout 기본값은 10초다.
2. --execute-live가 없으면 설정·Transport·Request·출력 저장 없이 preflight 실패 종료코드 2를 반환한다.
3. --execute-live에서는 PM이 승인한 --batch-id가 필수다. Collector와 Backup Worker가
   같은 strict canonical UUID validator를 사용하며 입력을 정규화하거나 재생성하지 않는다.
4. output-root를 절대경로로 정규화하고 파일시스템 루트·파일·저장소 내부 경로를 거부한다.
5. Source Batch, 설정된 Sync Backup, 기존 Receipt와 Lock에 같은 batch_id가 없는지
   읽기 전용으로 확인한다. 충돌 시 API Key 사용·Probe·Transport 생성 전에 중단한다.
6. 공식 121 CSV와 세 EG-6 참조 CSV의 구조·행·연결을 검증하고 SHA-256 스냅샷을 만든다.
7. Source Batch의 정확한 batch_id 디렉터리를 `exist_ok=False` 의미의 단일 `mkdir`로
   원자적으로 예약한다. 이 연산에 성공한 실행만 소유권을 얻고 다음 단계로 진행한다.
8. 예약 직후 심볼릭 링크를 따르지 않고 정확한 디렉터리를 열어 디렉터리 FD와
   `st_dev`·`st_ino`를 보존한다. 경로와 FD가 같은 실제 디렉터리를 가리키는지 확인한다.
9. raw·metadata에는 일반 숨김 Probe를, 예약 Batch 디렉터리에는 열린 FD를 사용하는
   기존-디렉터리 전용 Probe를 수행하고 예약 인식 FileStorage·BatchStorage를 조립한다.
10. 명시된 .env에서 API Key를 읽는다. 키는 출력하지 않는다.
11. 예약 승자만 Lazy HTTP Client·Collector를 조립한다.
12. panel_order 1~13 순서로 참조파일 불변성과 예약 디렉터리 동일성을 재검사한 뒤
    고유 request_id를 만들고 장소당 1회 요청한다.
13. Collector는 원본을 먼저 저장하고 HTTP·파싱·필드·장소·인구 범위를 검증한 뒤 8필드 Metadata를 저장한다.
14. Area 오류는 AreaOutcome으로 기록하고 다음 Area를 진행한다. 공통 오류나 참조 변경은 중단한다.
15. 누락된 나머지 Area를 not_attempted로 채우고 종료코드 0·1·2를 계산한다.
16. Collection Log payload와 Manifest를 만들고 Manifest를 먼저 저장한 뒤, 아직 저장 전인 Log payload를 포함해 전체 해시를 검증한다.
17. Manifest·Log를 포함한 모든 Batch 쓰기는 열린 예약 디렉터리 FD 기준의 배타적
    쓰기로 수행하며 쓰기 전후 동일성을 확인한다. 예약 루트는 다시 만들지 않는다.
18. 검증 성공 후 Collection Log를 배타적으로 저장하고 콘솔에 Area 결과와 회차 요약만 출력한다.

원자적 Source Batch 예약은 성공·부분실패·공통오류·예외·중단 뒤에도 자동 삭제하지
않는다. 불완전 예약은 같은 ID의 재사용을 막지만 Collection Log·Manifest 증거가
없으므로 Backup 대상이 아니다. abandoned 또는 stale 예약의 복구는 자동화하지 않고
별도 PM 검토와 명시적 절차가 필요하다. 예약 경로가 삭제·교체되거나 심볼릭 링크로
바뀌면 이름만 같은 새 경로를 유효한 예약으로 인정하지 않고 `reservation_integrity_error`로
중단한다. 런타임은 예약 루트를 재생성하거나 교체 대상을 따라가지 않는다.

## 6. CLI 계약

| **인자** | **형식/기본** | **계약** |
| --- | --- | --- |
| --env-file | Path · 필수 | 명시적 .env 경로; 자동 탐색하지 않음 |
| --output-root | Path · 필수 | 저장소 밖 안전한 디렉터리 |
| --batch-id | canonical UUID · Live 필수 | PM 승인값을 변경 없이 Source·Log·Manifest·Backup에 사용 |
| --timeout | float · 10초 | 0 < timeout ≤ 60, 유한값 |
| --execute-live | flag · 기본 false | 실행 의사 확인; PM 승인을 대체하지 않음 |

**승인 후 실행 형태:**

```bash
python3 -m freshmanager.eg6b --env-file .env --output-root "$FRESHMANAGER_EG6B_OUTPUT_ROOT" --batch-id "$FM_LIVE_BATCH_ID" --execute-live
```

> **중요**  위 명령은 계약 예시이며 현재 실제 실행 승인이 아니다. Batch ID, env-file과
> output-root는 PM이 승인한 값을 사용하고 실제 값이나 경로를 문서·로그에 기록하지 않는다.

canonical Batch ID는 Backup Worker와 공유하는 validator가 허용하는 소문자 UUID다.
공백·대문자·경로·상위경로 이동·형식 오류를 자동 보정하지 않고 거부한다. 요청별
Metadata는 기존 정확한 8필드 계약을 유지하므로 batch_id를 추가하지 않으며,
Collection Log와 Manifest가 request_id·상대경로를 통해 같은 회차에 연결한다.

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
- Batch approval boundary: --execute-live에서는 PM 승인 --batch-id를 필수로 받고,
  missing·invalid·conflict는 API Key 사용·영속 쓰기·네트워크 전에 종료한다. 읽기 전용
  충돌검사 뒤 Source Batch 디렉터리를 원자적으로 예약한 단 하나의 실행만 API Key와
  Transport에 접근한다. 예약의 장치·inode·열린 디렉터리 FD를 이후 설정과 모든 Batch
  쓰기의 동일성 기준으로 사용하며, 경로 삭제·교체·심볼릭 링크를 감지하면 중단한다.
  중단된 예약을 런타임이 자동 삭제·재생성·재사용하지 않는다.
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

첫 실제 EG-6B Batch 품질 감사 후 Raw와 Metadata만으로는 리드타임별 평가를
반복하기 어렵다는 사실을 실제 구조로 확인한 뒤 정규화 계약을 확정한다. CSV는 첫
Batch 전에 구현하지 않으며 다음 데이터셋은 목표 계약이다. 저장 형식은 별도 Issue와
PM 승인으로 결정한다.

| **데이터셋** | **고유키** | **핵심 내용** |
| --- | --- | --- |
| population_observations | area_code + population_reference_time + request_id | 현재 인구·혼잡·구성·요청시각 |
| population_forecasts | area_code + snapshot + target + request_id | 예측 min/max·혼잡·lead_time |
| collection_logs | request_id | 승인된 8필드 메타데이터 |
| batch_runs | batch_id | 회차 집계·버전·종료코드 |
| weather_forecasts | area + issue + target + request | 예보값과 사용가능 시각 |
| weather_observations | area + observation_time + request | 사후 실제 날씨 |
| commerce_observations | area + reference_time + request | 활동단계·지원상태·시간차 |
| sdot_observations | sensor_id + observation_time + source_snapshot | 센서 관측·시간대 변화; Area와 독립 저장 |
| spot_candidate_context | context_version + candidate_id | Area–S-DoT 근접성·공간 Context·현장검증 상태 |
| spot_candidate_evaluations | evaluation_version + candidate_id + decision_time | Area Feature·선택적 S-DoT Feature·Context 기반 후보 근거 평가 |
| recommendations | recommendation_id | target_level·target_id·fallback_reason·사용 Feature 버전 |

### 14.1 버전 계약

- collector_version: 수집 실행 의미가 바뀔 때 증가한다.
- data_version: 저장 스키마·필드 의미가 바뀔 때 증가한다.
- panel_version: Area 패널과 순서가 바뀔 때 증가한다.
- context_version: Spot Candidate·S-DoT 근접성·공간·현장검증 문맥이 바뀔 때 목표 구조로 추가한다.
- parser_version: 현재 최소 8필드 메타데이터에는 넣지 않으며 정규화 저장 설계에서 별도 승인한다.

### 14.2 S-DoT·Spot Candidate·Recommendation 목표 계약

Area Collector는 Spot 추천 여부와 무관하게 공식 Area 관측을 계속한다. S-DoT
관측과 Spot Candidate Evaluation 오류가 EG-6B Area 수집을 중단시켜서는 안 된다.
후속 구조는 필수 직렬 파이프라인이 아니라 다음 독립 입력을 결합한다.

```text
필수: Area Observation → Area Feature
선택: S-DoT Observation → 지원·접근·수집·품질조건을 통과한 S-DoT Feature
추가: Spatial Context + Field Validation + Operational Constraints
결합: Spot Candidate Evaluation
결과: target_level=SPOT 또는 target_level=AREA + fallback_reason
```

- S-DoT는 Area 데이터를 대체하지 않고 후보 생성과 공간 Feature 분석을 보조한다.
- 검증된 Spot Candidate가 있으면 반드시 `SPOT`을 선택한다.
- 후보가 없거나 운영 가능성이 미확인이면 `AREA`로 fallback하고 이유를 기록한다.
- 현재 Spot Master의 `STATION_CENTER_PROXY`, `field_verified=false` 행은 Candidate
  Anchor Point이며 추천 가능한 Spot이나 고정 판매 위치가 아니다.
- Area 값은 특정 출구·Spot의 직접 유동인구 측정값이 아니다.
- EG-6B의 정적 Spot/S-DoT CSV 사전검사는 패널 참조 무결성 계약이며 동적 계층
  실행이나 추천 성공을 의미하지 않는다.
- S-DoT 미지원 6개 Area도 Area Feature와 추천 후보를 계속 평가한다.
- 후보 Score·가중치·임계값은 `PLANNED` 또는 `OPEN_DECISION`이며 필수 데이터
  계약이 아니다.

## 15. EG-7 구현 아키텍처

> **구현 흐름**  불변 승인 계획 검증 → 계획 SHA-256 지문·Live Gate → 기존 계획·
> Batch ID 충돌 검사 → 파일럿 전역 Lock → 5분 벽시계 슬롯 → 기존 EG-6B Collector
> 최대 1회 → 적격성 평가 → 기존 Backup Worker 최대 1회 → append-only 사건 →
> canonical Batch 증거 기반 Slot·Area Index와 Summary

| **컴포넌트** | **책임** | **상태** |
| --- | --- | --- |
| Pilot Plan | v2; 고정 5분·`long_term_baseline_status=ACTIVE`·1개 `pilot_run_id`·12개 시각·UUIDv4 Batch ID·호출예산·승인상태 | 구현·합성 검증 |
| Plan Fingerprint | 승인된 Plan 시각을 `YYYY-MM-DDTHH:MM:SS+09:00`으로 의미 정규화한 정렬 canonical JSON의 결정적 SHA-256; 추적용 | 구현 |
| Live Gate | `CONFIRMED` 할당량·`PM_APPROVED`·지문·시간창·환경·충돌 | 구현; 운영 값 OPEN |
| Pilot Lock | 원자적 단일 실행, stale 자동삭제·정상 force-unlock 없음 | 구현 |
| Wall-clock Scheduler | `Asia/Seoul` 5분 경계 12개, 무보충·무드리프트 | 구현 |
| Batch Core | 현 EG-6B 로직 재사용; Area별 최대 1회·재시도 0 | 재사용 |
| Backup Trigger | 적격 Batch의 기존 Worker 1회, 로컬 복사 검증 필수 | 구현 조립 |
| Event Log | 상태 전환을 JSONL append-only로 보존 | 구현 |
| Slot Index | 계획 회차를 항상 12행 CSV·JSONL로 기록 | 구현 |
| Area Observation Index | 실제 시도 Area만 최대 156행, 관측·Forecast·해시·중복 | 구현 |
| Pilot Summary | 호출·실패·중복·시간·용량·Backup·무재수집 집계 | 구현 |
| S-DoT·Spot·ML | 동적 수집·평가·추천·학습 | EG-7 제외 |

### 15.1 계획과 시간 계약

- 시간대는 `Asia/Seoul`, 장기 주기는 벽시계 5분으로
  `PM_APPROVED_FIXED`·`LONG_TERM_OPERATING_BASELINE`이다.
- 계획 v2는 `cadence_minutes=5`, `cadence_decision_status=PM_APPROVED_FIXED`,
  `long_term_baseline_status=ACTIVE`,
  `cadence_scope=LONG_TERM_OPERATING_BASELINE`, `cadence_change_allowed=false`를
  모두 강제하고 비 5분 계획과 런타임 주기 옵션을 거부한다. 대안 주기는 지원하지
  않는다.
- 계획 지문은 검증된 `planned_start_at`, `planned_end_at`과 모든
  `slots[].scheduled_at`을 `YYYY-MM-DDTHH:MM:SS+09:00`으로 정규화한 뒤 계산한다.
  허용된 `T`·공백 구분자와 JSON 키 순서 차이는 같은 지문을 만들며, 다른 시각·
  Batch ID·승인 상태는 다른 지문을 만든다. `plan_fingerprint` 자체, 환경값,
  Secret과 절대경로는 입력에서 제외하고 이 SHA-256을 인증값으로 표현하지 않는다.
- 첫 통제 검증 길이는 1시간이고 계획 회차는 12다. 이 결과로 5분 유지 여부를
  평가하거나 10분·15분 대안을 비교하지 않는다.
- 회차당 13 Area, 전체 최대 156호출, Area별 회차당 최대 1회, 재시도는 0회다.
- 이미 늦은 회차는 `SKIPPED_MISSED`, 이전 Collector와 즉시 Backup이 다음 경계를
  넘으면 `SKIPPED_OVERLAP`이다. 둘 다 호출 0회이고 지연 보충수집을 하지 않는다.
- 건너뛴 Batch ID도 불변 계획에 남겨 다른 파일럿에서 재사용하지 않는다.
- 실제 날짜·시작시각·운영 ID·계획 지문은 구현에서 생성하지 않는다.

### 15.2 상태와 실패 계약

종결 상태는 `COMPLETED_SUCCESS`, `COMPLETED_PARTIAL`, `SKIPPED_MISSED`,
`SKIPPED_OVERLAP`, `STOPPED_FATAL`, `NOT_RUN_AFTER_FATAL_STOP`이다.
개별 Area 오류는 기존 Collector 계약에 따라 기록 후 계속한다. 확정된 공통 API,
자격증명, 스키마, 할당량, Backup 또는 저장 오류는 남은 회차를 중단한다.
Backup 실패는 Source를 보존하고 Collector·서울시 API·대체 Batch ID를 다시
실행하지 않는다. 모든 회차가 하나의 종결상태를 가진다.

### 15.3 파생 데이터와 중복 계약

Slot Index는 정확히 12행이고 알 수 없는 값을 0으로 추정하지 않는다. Area Index는
실제 시도한 Area만 최대 156행이며 `area_code`를 후속 Area–Spot/S-DoT 결합키로
유지하고 `spot_id`를 추가하지 않는다. 수집시각, API 관측시각, Raw SHA-256,
Forecast 대상시각의 의미 정규화된 canonical 정렬 집합을 Area별로 구분해 중복
플래그를 만든다. Forecast 비교 signature는 각 대상 instant를
`YYYY-MM-DDTHH:MM:SS+09:00`으로 정규화하고, 같은 instant를 집합 안에서 한 번만
남긴 뒤 오름차순 불변 tuple로 만든다. 원본 Forecast 배열 순서는 비교에 사용하지
않고 Raw에서 그대로 보존한다.
Raw·Metadata·Collection Log·Manifest는 수정·병합·삭제하지 않으며 파생 출력은
기존 Batch Manifest에 추가하지 않는다. 중복 건수·비율은 저장·EG-8 데이터셋 구성
근거이며 계획 API 호출 생략이나 주기 변경 조건이 아니다. 중복 제거·선별·가중치는
EG-8에서 다룬다.

### 15.4 승인 경계

할당량 기본은 `UNCONFIRMED`, Live 승인 기본은 `NOT_APPROVED`다. Dry-run·테스트·
계획 검증만 허용하며 실제 할당량, 파일럿 날짜·시작시각, 운영 `pilot_run_id`,
12개 운영 Batch ID, 승인 계획 지문과 PM Live 승인이 모두 확인되기 전 실제
실행을 거부한다. H-707 PASS는 이 차단과 합성 orchestration 계약을 검증할 뿐
실제 Live 승인을 뜻하지 않는다. 일일 운영시간대, 24시간 또는 선택 시간 운영,
첫 1시간 이후 확대 시점은 OPEN이며 이는 주기 미결정을 뜻하지 않는다. 24시간
Scheduler와 영구 백그라운드 서비스는 없다.

## 16. 백업과 복구

- 공식 제공자는 Google Drive다. iCloud와 수동 백업은 현행 운영방식으로 사용하지 않는다.
- Google Drive API·OAuth·SDK 대신 Google Drive for Desktop Sync의 로컬 동기화
  폴더를 사용한다. Backup Root는 `FreshManager-Data/` 논리 구조만 정의한다.
- 실제 계정 이메일과 동기화 절대경로는 저장소·Receipt·로그에 기록하지 않는다.
- Collector는 로컬 원본만 생성하고, Batch 완료 판정 직후 별도 1회 실행형 Backup
  Worker를 호출해 복사·검증한다. 시간 간격 기반 폴링은 사용하지 않는다.
- 백업 단위는 완결된 Raw·Metadata·Collection Log·Manifest 전체다. 종료코드 `1`의
  부분 실패 Batch도 증거와 Manifest가 완결되면 보존한다. 실행 중 Batch는 복사하지 않는다.
- 동기화 루트의 임시 디렉터리로 복사하고 파일 수·Manifest SHA-256을 확인한 뒤
  최종 `batch_id` 경로로 원자적으로 게시한다.
- 동일 `batch_id`의 파일 수·해시가 같으면 중복을 생략하고, 다르면 `CONFLICT`로
  중단한다. 기존 원본이나 복사본을 덮어쓰지 않는다.
- Collector가 받은 승인 `batch_id`를 Worker CLI에도 그대로 전달한다. Backup 실패는
  같은 ID의 Collector 또는 서울시 API를 재실행하는 사유가 아니다.
- `LOCAL_SYNC_COPY_VERIFIED`와 `REMOTE_SYNC_CONFIRMED`를 구분한다. 로컬 폴더
  복사만으로 실제 Google Drive 원격 업로드 완료를 주장하지 않는다.
- 백업 실패는 서울시 API 재호출 사유가 아니며 `.env`, Secret, 인증 URL과 임시
  파일을 백업하지 않는다.
- append-only Backup Receipt와 Fake Restore 계약은 Issue #60에서 구현됐다. 실제 Batch
  Restore, 원격 동기화 확인, 일일 무결성 감사와 보존기간의 현재 진행 상태는
  `PROJECT_STATUS.md`를 따르며 실행에는 별도 PM 승인이 필요하다.

상태·충돌·복원·CSV 상세 목표 계약은
`docs/data/CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md`를 따른다. 모두 목표 구조이며
현재 코드에 구현된 것으로 해석하지 않는다.

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

## 19. EG-8 Feature 분석 기술 구조

> **분석 흐름**  검증된 Batch → Point-in-time 정규화 → Area Feature + 승인·확보된 경우의 독립 S-DoT Feature + 공간·현장·운영 Context → Spot Candidate Evaluation → 기준선·예측 비교 → Gate A/B 리포트

분석은 단계별 증거 수준을 구분한다.

| 단계 | 데이터 | 기술적 산출물 |
|---|---|---|
| 첫 Batch 품질 감사 | 최초 실제 EG-6B Batch | 저장·Manifest·필드·결측·지연·오류 감사와 PASS/보완 근거 |
| Snapshot 비교 | 품질 감사 통과한 한 회차 | Area별 현재값·구성·Forecast 방향·상대순위 |
| 초기 EDA | EG-7 평일 5영업일 | 시간대 요약·증감·피크 후보·결측·초기 1시간 오차 |
| 공식 EG-8 | 4주 기준선+5주차 | Area Feature·선택적 S-DoT Feature·Spot Candidate Evaluation·1/3/6시간 오차·Feature 유효성 |

| **분석** | **방법** | **목적** |
| --- | --- | --- |
| B0 최근값 유지 | 직전 관측값을 미래 비교 기준으로 사용 | 단순 기준선 |
| B1 동일 요일·시간 | 동일 요일·시간의 과거 평균 | 반복성 |
| B2 최근 4주 평균 | 평가주 이전 4주 동일 요일·시간 | 전향 평가 기준 |
| 서울시 예측 | 스냅샷·대상·후속 관측 연결 | 리드타임별 비교 |
| 피크 | 기준선 대비 상승·지속·비관행 시간 | 후보 시간창 |
| 장소 | 절대값·상대순위·변동성 | 분별력 |
| S-DoT | 센서 시간대 변화·Area 근접 관계 | Area 내부 활성 위치 판단 보조 |
| Spot Candidate | Area·선택적 S-DoT·공간·현장검증 Feature 조합 | 후보별 Candidate Evidence Assessment |
| 소비·날씨 | 지원상태와 point-in-time join | 보조 설명 |

### 19.1 분석 산출물

- 데이터 품질 대시보드용 CSV/차트: 성공률, 결측, 지연, 스키마·파일 무결성
- 예측 평가표: MAE, RMSE, 상대오차, 구간 포함률, 혼잡도 일치율, 리드타임
- 시간패턴 차트: 요일·시간 기준선, 변화율, 변동성, 피크 지속시간
- 장소 비교표: Area 유형, 인구 기회, 혼잡 위험, S-DoT 지원 여부
- Spot Candidate 표: 후보 Anchor, Area·선택적 S-DoT·공간 Feature, 현장검증, 근거와 제한
- Gate A/B 판정 메모: 사실·해석·가설·한계·다음 행동

### 19.2 후속 Recommendation MVP Workstream 목표

이 Workstream은 EG-8에서 유효성이 확인된 Area Feature, 선택적으로 승인·확보된
S-DoT Feature와 Candidate Evidence Assessment를 입력으로 사용하는 별도 Recommendation
MVP다. 상태는 `PLANNED`, Gate number는 `NOT_ASSIGNED`이며 EG-8 분석 결과와 PM 승인
전에는 구현하지 않는다.

- 충분하고 신뢰 가능한 Spot Candidate가 있으면 `target_level=SPOT`을 출력한다.
- 후보 근거가 부족하면 `target_level=AREA`와 `fallback_reason`을 출력한다.
- 추천 근거에는 사용한 Feature·Evaluation·Context 버전을 남긴다.
- 추천 실패가 원본 Area Observation을 변경하거나 API 재호출을 유발하지 않는다.
- 실제 판매효과와 추천 적중은 Recommendation MVP 구현만으로 입증됐다고 표현하지 않는다.

## 20. 관측성·운영 보고

현행 콘솔은 민감하지 않은 고정 키-값 형식만 출력한다. EG-7에서는 실행 슬롯·회차·백업·품질 상태를 추가하되 API Key·완성 URL·Raw 전문·로컬 절대경로를 출력하지 않는다.

| **보고** | **필드** | **시점** |
| --- | --- | --- |
| Area 결과 | area_code, request_id, status, raw_saved, metadata_saved | 요청 직후 |
| Batch 요약 | target/attempt/success/failure, elapsed, files, hash, exit | 회차 종료 |
| 품질 요약 | forecast count, duplicate timestamp/hash/targets, duration, storage | EG-7 파생 Summary |
| 백업 요약 | batch_id, eligible, verify, status | EG-7 Slot·Area Index |
| 운영 상태 | missed·overlap·fatal·remaining not-run | EG-7 사건·Slot Index |

## 21. 검증 전략

| **계층** | **검증 대상** | **검증 방법** |
| --- | --- | --- |
| Unit | 파서·설정·저장·요청·상태 | 가짜 bytes·임시 경로 |
| Adapter | 정상·HTTP 오류·Timeout·Redirect·5 MiB | 주입 Transport |
| Collector | 6개 오류·원본·8필드 Metadata | Fake Client |
| EG-6B Target | 13개 순서·실패 격리·Manifest·경로 | 전용 오프라인 Target Tests |
| EG-7 Target | 계획·시간·잠금·실패·무재수집·인덱스·Dry-run | 합성 계획·Clock·Batch 증거 |
| Project Guard | 문서·데이터·보안·오프라인·H-707·H-708 | PROJECT_GUARD_SPEC의 상태·집계 계약 |
| Full | 저장소 전체 unittest | 전체 Unit Test 실행 |
| CI | 모든 PR·main Push | CI Validation Workflow |
| Live smoke | 실제 API·외부 output-root | 별도 PM 승인 실행 |

Project Guard 검사별 현재 PASS·SKIP, 전체 집계와 Live 실행 여부는
`PROJECT_STATUS.md`에서 확인한다.

## 22. 배포·Rollout 계약

현재 완료 지점은 `PROJECT_STATUS.md`를 단일 기준으로 확인한다. 아래는 상태표가
아니라 승인 순서와 의존관계다.

- T0 — EG-6B Collector와 독립 Backup Worker 구현·병합·오프라인 검증
- T1 — env/output 및 Google Drive for Desktop Sync 로컬 경로 Preflight
- T2 — Fake Batch Backup·Receipt·Restore 무결성 검증
- T3 — PM의 실제 원격 동기화 상태 확인
- T4 — Live Preflight 재통과와 최대 13회 실제 호출 별도 승인
- T5 — 첫 Batch 원본·Manifest·백업·품질 감사와 EG-6B PASS/보완
- T6 — 실제 구조 기반 CSV 계약·Exporter 별도 구현·누적·재생성 검증
- T7 — EG-7 5분·1시간 Controller·파생 인덱스 오프라인 구현·독립 검토
- T7-Live — 별도 PM 승인 운영 계획으로 동일 13개 Area 최대 156호출 파일럿
- T8 — EG-8 Area·선택적 S-DoT Feature와 Spot Candidate Evaluation
- T9 — Recommendation MVP Workstream(`PLANNED`, Gate number `NOT_ASSIGNED`)
- T10 — 현장·인터뷰 결과로 121개 확대 또는 서비스 실증 여부 결정

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
| ADR-08 | Google Sheets 수집 미채택 | 현행 로컬 Python·원본 보존·승인 Gate와 충돌 | `SUPERSEDED` — ADR-15로 대체 |
| ADR-09 | Spot Master는 Candidate Anchor Point | 고정 판매 위치가 아니라 Area·S-DoT·공간·현장검증 기반 후보 생성의 입력 | 유지 |
| ADR-10 | Google Drive for Desktop Sync 백업 | API·OAuth·SDK 없이 로컬 파일 계약과 원격 동기화 책임 분리 | 유지 |
| ADR-11 | Batch 완료 직후 1회 실행형 Worker | 수집기·백업 책임 분리와 장애 격리 | 채택 |
| ADR-12 | CSV는 첫 Batch 이후 | 실제 필드·결측·Forecast를 확인한 뒤 파생 계약 확정 | 목표 구조 |
| ADR-13 | S-DoT는 독립·선택적 보조 데이터 계층 | Area를 대체하거나 필수 직렬 단계가 아니며 Spot Candidate 근거만 보조 | 목표 구조 |
| ADR-14 | Recommendation MVP Workstream 분리 | EG-8 Feature 검증과 추천 제품 동작을 분리; Gate number NOT_ASSIGNED | 목표 구조 |
| ADR-15 | Apps Script를 PoC 반복수집 Runtime으로 재채택 | ADR-08 폐기 근거(현행 로컬 Python과 충돌)가 이제 반대로 적용됨 — 로컬 Python·Codex·Claude Code 세션 종료와 무관하게 5분 반복수집이 계속돼야 한다는 요구를 로컬 EG-7(동기 실행, 세션 종속)은 충족할 수 없음. PM이 외부에서 기존 Apps Script 자산을 직접 복원·검증(POI 코드 호출·Script Properties Key·13개 Area v3 시트 누적) | `ACCEPTED` |

## 25. 미결정 기술사항

- O-01 Google Drive for Desktop Sync 설치·로그인과 논리 루트 접근·용량 확인 방법
- O-02 일일 운영시간대·24시간 또는 선택 시간 운영·일 호출예산·공휴일 처리와
  첫 1시간 이후 확대 시점; 반복수집 간격 5분은 확정
- O-03 stale lock의 승인된 수동 복구 규칙; 자동 삭제 금지
- O-04 정규화 저장 형식: 분할 CSV vs SQLite 등 표준 라이브러리 기반 로컬 DB
- O-05 parser_version과 schema migration 기록 방식
- O-06 원격 완료 확인, Receipt, 보관·일일 감사·복구 시험
- O-07 디스크 여유 임계치와 수집 중단 정책
- O-08 날씨·상권 Endpoint·실응답 필드·지원상태 Enum
- O-09 context_version과 현장검증 갱신 방식
- O-10 EG-7 재시도 도입 여부와 호출량·시간 정렬 영향
- O-11 Live Preflight의 env-file·output-root·실행시각·최대 13회 호출 승인
- O-12 실제 원격 동기화 확인과 운영자 확인 증거의 최소 계약
- O-13 Apps Script Runtime의 24시간 이상 장기 지속성(`PENDING_VALIDATION`), 소스 Git
  버전관리 방식(`PLANNED`), v3 시트 데이터와 Python 정규화 파이프라인의 통합 스키마(`PLANNED`)

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
| FR-09 | docs/analysis/ANALYSIS_PLAN.md | EG-8·후속 Recommendation MVP Workstream 미구현 |
| FR-10 | EG5 report + 목표 reporting | 부분 |
| FR-11 | Collector statuses + eg6b exit 0/1/2 | H-704/H-705/H-706 |
| FR-13 | 즉시 Backup Worker·Google Drive for Desktop Sync | H-708 계약; 실환경 상태는 PROJECT_STATUS 참조 |
| FR-14 | 목표 S-DoT·Spot Candidate·Recommendation 계층 | 미구현; EG6 Panel·EG-8 Feature·현장검증 필요 |
| FR-12 | --execute-live + 승인 --batch-id + AGENTS/Git workflow | Project Guard/CI/PM |

## 근거 자료

문서의 사실·상태·계약은 아래 로컬 저장소 자료와 완료 기록을 대조해 작성했다. 경로는 FreshManager 저장소 루트 기준이다.

| **자료** | **사용 목적** |
| --- | --- |
| freshmanager/eg6b.py | EG-6B CLI·참조 검증·13개 순회·Batch Log·Manifest |
| freshmanager/collector.py | 요청·응답 파싱·원본·8필드 메타데이터 계약 |
| freshmanager/http_adapter.py | 서울시 요청·Redirect·Timeout·응답 상한 |
| freshmanager/storage.py | 배타적 비덮어쓰기 파일 저장 |
| freshmanager/backup.py | Issue #60 완료 Batch 검증·로컬 Sync 복사·Lock·Receipt |
| freshmanager/eg7.py | Issue #70 계획·벽시계 회차·Pilot Lock·Collector/Backup 조립·파생 출력 |
| tests/test_eg6b.py | EG-6B Target 계약 검증 |
| tests/test_eg7.py | EG-7 계획·Scheduling·Lock·실패·인덱스·Dry-run 합성 검증 |
| scripts/project_guard_check.py | 47개 Project Guard 등록·실행; H-707·H-708 활성 |
| docs/rules/DATA_COLLECTION_RULES.md | 단계별 저장·시간·원본·실패·배치 규칙 |
| docs/testing/PROJECT_GUARD_SPEC.md | 검사 ID·판정·종료코드 기준 |
| Issue #69·#70 | EG-7 승인 범위와 구현 작업 추적 |

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
| S-DoT Data Layer | 센서 위치·근접 관계·관측 변화의 독립 보조 계층; Area 데이터를 대체하지 않음 |
| Spot Candidate | Area·S-DoT·공간 Context·현장검증을 결합해 생성하는 판매 후보 위치 |
| Candidate Anchor Point | Spot 후보 생성의 기준점; 현재 역 중심 대리좌표이며 고정 판매 위치가 아님 |
| Recommendation 결과 | 후보 근거에 따라 SPOT 또는 AREA+fallback_reason을 결정하는 후속 Workstream 결과 |
