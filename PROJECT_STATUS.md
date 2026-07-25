# FreshManager Project Status

## 1. 문서 역할

이 문서는 현재 Branch·Pull Request·Issue·외부 실행·검증·다음 행동을 복원하는
단일 운영 기준이다. 제품 목적은 PRD, 기술 계약은 TRD, 검사 ID와 판정은
`docs/testing/PROJECT_GUARD_SPEC.md`를 따른다.

마지막 동기화 시각: `2026-07-24` (Asia/Seoul)

## 2. 현재 요약

- 저장소: `shindonghyun0516-a11y/FreshManager`
- 정본 Branch: `main`
- 현재 `main` SHA: `VERIFY_AT_SESSION_START`
- local·`origin/main` 일치: `MUST_BE_VERIFIED_AT_SESSION_START`
- 마지막으로 검증된 EG-7 기능 구현 기준선: PR #71 Squash Merge SHA
  `562f984d7f84203196b34f8d1d827310405d3cc3`
- Planning Issue #69: `OPEN`
- Implementation Issue #70: `CLOSED`
- PR #71: `MERGED`
- EG-7 구현: `AVAILABLE_ON_MAIN`
- 영구 주기: `5분`
- 주기 결정 상태: `PM_APPROVED_FIXED`
- 장기 기준 상태: `ACTIVE`
- 주기 범위: `LONG_TERM_OPERATING_BASELINE`
- 첫 1시간 Live 수집: `NOT_STARTED`
- PM Live 승인: `NOT_APPROVED`
- API 할당량: `UNCONFIRMED`
- 일일 운영시간대: `OPEN_PM_DECISION`
- 운영 Plan·`pilot_run_id`·Batch ID·Plan fingerprint: `NOT_GENERATED`
- S-DoT 동적 수집: `NOT_STARTED`
- Spot 자동 추천: `NOT_STARTED`
- 24시간 Scheduler(로컬 EG-7 Live 파일럿 확대 기준): `NOT_IMPLEMENTED`
- ML 학습: `NOT_STARTED`
- PoC 상시 13개 Area 반복수집 Runtime: **Apps Script** `ACTIVE`(§2.1 참조)

PM이 장기 기준으로 확정한 5분 주기의 EG-7 1시간 파일럿 Controller와 파생
인덱스는 `main`에 구현됐다. 첫 Area-only 1시간 Live 수집은 시작하지 않았고,
실제 날짜·시각·운영시간대·할당량·운영 Plan·운영 ID·계획 지문은 생성하거나
확정하지 않았다. 이 §2~§10의 EG-7 Live 파일럿 상태는 로컬 Python 기술검증
경로에 대한 것이며, PoC의 실제 상시 반복수집 Runtime과는 별개다.

## 2.1 PoC 상시 수집 Runtime — Apps Script

- Runtime: Google Apps Script (5분 벽시계 트리거)
- 상태: `ACTIVE`
- 대상: 승인된 13개 Area, POI 코드 기준 호출(Area 이름 아님)
- Key 관리: Apps Script Script Properties의 `SEOUL_OPEN_API_KEY`(`.env`와 별도, 자동 연결 안 됨)
- 5분 Trigger 실행: `ACTIVE`(PM이 Apps Script 화면에서 직접 확인 — 시간 기반 Trigger가
  `collectData`를 반복 실행 중)
- 13개 Area 자동 반복수집: `ACTIVE`
- 저장 위치: Google Spreadsheet `raw_log_v3` / `population_current_v3` / `population_forecast_v3`(`ACTIVE`, 현재 정본)
- 이전 `v1`·`v2` 시트: 과거 또는 혼합 테스트 자산, 현재 정본 아님(스키마 혼합)
- 실행 단위 식별자: 실행마다 서로 다른 `collection_run_id` 사용
- 정상 실행 1회 기준 산출: Raw 13건 / Current 13건 / Forecast 156건
- 중복 실행 방지: LockService 적용
- 로컬 EG-6B/EG-7(Python): 상시 Scheduler 아님 — 기술검증·Pilot Runner로 유지(`VALIDATION_AND_PILOT_ONLY`)
- 독립 장기 관찰(Codex·Claude Code·Mac 종료 상태 지속 여부): `IN_PROGRESS`
- 24시간 이상 무중단 지속성 검증: `NOT_COMPLETED` — 5분 자동수집이 `ACTIVE`라는 사실과
  혼동하지 않는다
- Apps Script 소스 Git 버전관리: `PLANNED`
- Apps Script 데이터 ↔ Python 정규화·ML 파이프라인 통합: `PLANNED`
- 과거 "Apps Script 폐기" 결정(TRD ADR-08, PRD R-09): `SUPERSEDED` — 상세는
  `ai-context/DECISION_LOG.md`와 TRD ADR-15 참조

## 2.2 EG-8A~EG-8E 데이터 분석·ML·추천·UI 준비 상태

- EG-8(상위): `NOT_STARTED` — 데이터 분석·예측·추천 준비 상위 Gate, EG-8A~8E로 세분화
- EG-8A(Python Loader·정규화·데이터 품질): `IN_PROGRESS`
- EG-8B(EDA·서울시 Forecast 평가·Baseline·Feature Dataset): `IN_PROGRESS`
- EG-8C(미래 Area 인구·피크 예측 모델): `PLANNED`
- EG-8D(Area Ranking·선택적 S-DoT·Spot Candidate Evaluation): `PLANNED` — 기존
  EG-8 정의(Area Feature+선택적 S-DoT Feature+Spot Candidate Evaluation)를 그대로 계승
- EG-8E(Recommendation Output Contract·UI/UX Readiness): `PLANNED` — Recommendation
  MVP 구현 Gate가 아니며, Recommendation MVP Workstream의 공식 Gate 번호는 계속
  `NOT_ASSIGNED`다

구현 상태:

- Python Loader: `IN_PROGRESS`
  - Source Reader·Schema Validation·Normalization: `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #84)
  - Duplicate Detector·Quality Report·Dataset Manifest·최종 Output Writer: `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #86, Issue #85)
  - 실제 오류 응답 기반 검증: `NOT_COMPLETED`(합성 Fixture 오류 경로만 테스트 통과, 실 v3 CSV Smoke는 정상 경로만 확인)
- EG-8B Dataset Profile·시간 커버리지·Forecast-Current Exact Join(B1): `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #88, Issue #87)
- EG-8B Phase 1 Read-only 준비도 분석(ML-ready Dataset·EDA·Forecast 평가·Baseline 가능성): `COMPLETED`
- ML-ready Dataset: `NOT_IMPLEMENTED`
- EDA: `NOT_STARTED`
- EG-8B B2a(B0 Persistence Baseline·서울시 Forecast 단일 일자 잠정 Backtest): `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #92, Issue #89) — 단일 일자 잠정 결과이며 공식 성공 임계값·EG-8B Gate PASS/FAIL 판정이 아님
- EG-8B B2b — 2026-07-24 01:00~2026-07-25 07:00 단기 다일자 Baseline·Forecast 검증: `IMPLEMENTATION_AVAILABLE_ON_MAIN`(Parent Issue #93, PR #94) — 단기 다일자 잠정 검증 결과이며 evaluation_status=PROVISIONAL, coverage_status=SHORT_WINDOW_MULTI_DAY_PARTIAL_COVERAGE, gate_judgment=null. 공식 성공 임계값·EG-8B Gate PASS/FAIL 판정이 아님. 장기 다일자·5영업일·4주·공식 Gate 평가는 데이터 추가 축적 후 별도 검토한다.
- ML Model: `NOT_STARTED`
- Area Ranking: `NOT_STARTED`
- Spot Ranking: `NOT_STARTED`
- Recommendation Contract: `NOT_STARTED`
- UI/UX Detailed Design: `NOT_STARTED`

이 절은 §2.1의 Apps Script 상시 수집 Runtime과 독립적이다. 5분 자동수집 `ACTIVE`
상태는 이 절과 무관하게 유지된다. v3 source sheets 자체는 ML-ready Dataset이
아니며, EG-8A Python Loader를 거쳐야 정규화 데이터셋이 된다.

## 3. Engineering Gate 상태

| Gate | 상태 | 근거 |
|---|---|---|
| EG-0 | PASS | 문서 기준선 승인 |
| EG-1 | PASS | 공식 121장소 CSV 읽기 전용 검증 |
| EG-2 | PASS | 공식 여의도 샘플 H-301~H-304 |
| EG-3 | PASS | Python Project Guard·CI |
| EG-4 | PASS | POI072 실제 단일 수집 |
| EG-5 | PASS | 대표 3 Area 실제 3/3 수집 |
| EG-6A | PASS | PR #52, 13개 Area·Spot·S-DoT 정적 패널 |
| EG-6B | PASS | 첫 실제 13 Area 13/13, 품질·백업·원격 동기화 확인과 Closeout |
| EG-7 | IMPLEMENTATION_AVAILABLE_ON_MAIN | PR #71 병합, Issue #70 종료; 첫 Live 미시작 |
| EG-8(상위) | NOT_STARTED | 데이터 분석·예측·추천 준비 상위 Gate; EG-8A~8E로 세분화(§2.2) |
| EG-8A | `IN_PROGRESS` | Source Reader·Schema Validation·Normalization `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #84); Duplicate Detector·Quality Report·Manifest·Output Writer `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #86); 실제 오류 응답 기반 검증 `NOT_COMPLETED` |
| EG-8B | `IN_PROGRESS` | Dataset Profile·시간 커버리지·Forecast Exact Join(B1) `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #88); B0 Baseline·서울시 Forecast 오차 지표(B2a) `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #92); B2b 단기 다일자 검증 `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #94) |
| EG-8C | `PLANNED` | 미래 Area 인구·피크 예측 모델 |
| EG-8D | `PLANNED` | Area Ranking·선택적 S-DoT·Spot Candidate Evaluation(기존 EG-8 정의 계승) |
| EG-8E | `PLANNED` | Recommendation Output Contract·UI/UX Readiness(Recommendation MVP 구현 Gate 아님) |
| Recommendation MVP | PLANNED | Gate number `NOT_ASSIGNED` |

EG-7 post-merge 상태:

- PR #71: `MERGED`
- PR #71 Squash Merge SHA 이력:
  `562f984d7f84203196b34f8d1d827310405d3cc3`
- Issue #70: `CLOSED`
- Issue #69: `OPEN`
- EG-7 구현: `AVAILABLE_ON_MAIN`
- 첫 Live 파일럿: `NOT_STARTED`
- 다음 Gate: `FIRST_LIVE_PILOT_PREFLIGHT_AND_BOUNDED_PM_APPROVAL`

EG-6B Closeout 이력:

- Issue #57: `CLOSED`
- Issue #67: `CLOSED`
- PR #68: `MERGED`
- 첫 실제 Batch: 승인된 13개 Area `13/13 SUCCESS`
- 첫 Batch 품질: `PASS`
- canonical Source/Backup 무결성: `PASS`
- PM 원격 동기화 확인: `COMPLETE`

이 완료 이력은 EG-7 Live 승인을 뜻하지 않는다.

## 4. EG-7 승인 구현 계약

### 4.1 영구 주기 결정

| Permanent Cadence Decision | 상태 |
|---|---|
| Five-minute Cadence Fixed | `YES` |
| PM Approval Status | `PM_APPROVED_FIXED` |
| Long-term Baseline Status | `ACTIVE` |
| Alternative Cadences Supported | `NO` |
| Duplicate-triggered Cadence Change | `NO` |
| Plan Validation for Non-five-minute Cadence | `REJECTED` |
| Documentation Updated | `YES` |
| Operating Window Status | `OPEN_PM_DECISION` |

첫 1시간은 5분 주기 채택 여부를 결정하는 시험이 아니다. 이미 확정된 주기에서
12개 회차의 Collector·Backup 완료, 중첩·보충 금지, 156호출 상한, 실행시간·
저장 증가·중복률·추적성·실패처리와 장시간 확대 전 용량 문제를 검증한다.

### 4.2 시간·호출

- 시간대: `Asia/Seoul`
- Scheduling: 벽시계 5분 경계
- 길이: 1시간
- 계획 회차: 12
- 회차당 Area: 13
- 회차당 최대 호출: 13
- 전체 최대 호출: 156
- Area별 회차당 최대 호출: 1
- 재시도: 0
- 자동 재시도: 금지
- 지연 보충수집: 금지
- 중첩: 해당 회차 `SKIPPED_OVERLAP`, API 호출 0회

### 4.3 계획·식별자

- 한 파일럿에 하나의 `pilot_run_id`
- 정확히 12개의 계획 시각
- 회차별 사전 생성 canonical 소문자 UUIDv4 Batch ID
- 계획 canonical JSON의 결정적 SHA-256 지문
- Live 시작 뒤 계획 불변
- 건너뛴 ID는 `UNUSED`로 계획 이력에 남기고 다른 파일럿에서 재사용 금지

이 작업에서는 합성 테스트 ID만 임시 디렉터리에서 사용한다. 운영 ID·운영 계획은
생성하거나 예약하지 않는다.

### 4.4 실패·백업

- 개별 Area 실패: 재시도 없이 기록하고 기존 Collector 계약이 허용하면 다음 Area 진행
- 확정 공통 API·자격증명·스키마·할당량 오류: 현재 Batch 안전 중단, 남은 회차 중단
- 저장 오류: 기존 증거 보존, 남은 회차 중단
- Backup 오류: Source 보존, Collector·서울시 API 재호출 금지, 남은 회차 중단
- 적격 Batch는 Backup Worker를 최대 한 번 실행
- `LOCAL_SYNC_COPY_VERIFIED` 전에는 회차 성공으로 종결하지 않음

### 4.5 산출물

- 불변 JSON Pilot Plan
- append-only JSONL Execution Events
- 정확히 12행 Slot Index: CSV·JSONL
- 실제 시도 Area만 최대 156행 Area Observation Index: CSV·JSONL
- JSON Pilot Summary
- 중복 수집시각·API 관측시각·Raw SHA-256·Forecast 대상시각 집합을 별도 파생 플래그로 기록

Raw·Metadata·Collection Log·Manifest는 canonical 원본이다. EG-7 파생 산출물은
이를 대체·수정·삭제하지 않고 기존 Batch Manifest에도 추가하지 않는다.
중복이 있어도 해당 계획 호출을 건너뛰거나 5분 주기를 변경하지 않는다. 제거·
선별·가중치는 EG-8 데이터셋 구성에서 검토한다.

## 5. Live 차단 상태

다음 결정은 모두 OPEN이다.

- 실제 파일럿 날짜
- 실제 시작시각
- 일일 운영시간대
- 장기 운영을 24시간 또는 선택 시간대로 할지
- 확인된 API 할당량
- 장시간 운영 용량 Gate
- 운영 `pilot_run_id`
- 운영 12개 Batch ID
- 운영 계획 지문
- 명시적 PM Live 승인
- 첫 1시간 이후 확대 시점

5분 주기·벽시계 Scheduling·대안 주기 제외·중복 기반 주기 변경 금지·장기 5분
기준은 `CLOSED · PM_APPROVED`이며 위 OPEN 목록에 포함되지 않는다.

기본값:

```text
quota_confirmation_status=UNCONFIRMED
live_approval_status=NOT_APPROVED
```

둘 중 하나라도 기본 차단 상태이거나 승인 지문·현재 시간창·Area 계약·호출상한·
환경·Lock·ID 충돌 검사가 맞지 않으면 Live를 거부한다.

## 6. 현재 post-merge 상태와 첫 Live 범위 경계

- EG-7 Live 서울시 API 호출: `0`
- 운영 Collector 실행: `0`
- 운영 Backup Worker 실행: `0`
- Google Drive 접근: `0`
- S-DoT 동적 수집: `NOT_STARTED`
- Spot 자동 추천: `NOT_STARTED`
- ML 학습·성능평가: `NOT_STARTED`
- production Scheduler(로컬 EG-7 기준): `NOT_IMPLEMENTED` — PoC 상시 Runtime은 Apps Script(§2.1)
- 로컬 EG-7 Live 파일럿의 자동 24시간 확대: `NOT_APPROVED`
- 자동 재시도: 금지
- 일반 Raw-to-CSV Exporter: 첫 실제 파일럿 후 별도 검토
- 121개 Area 확대: EG-8 결과와 별도 PM 승인 후 검토

첫 Area-only 1시간 Live는 아직 시작하지 않았다. 별도 PM 승인 뒤 서울시 API,
기존 Collector와 Backup Worker를 승인 Plan 범위에서 사용한다. 기존 정적 S-DoT
mapping은 변경하지 않았고 Spot 후보는 계속 `field_verified=false`다. S-DoT
동적 수집, ML, Spot Candidate·Recommendation은 계획된 별도 MVP Workstream이지만
첫 Area-only 1시간 Live 실행에는 포함하지 않는다.

## 7. 구현 파일 범위

| 파일 | 역할 |
|---|---|
| `freshmanager/eg7.py` | 계획·지문·Live Gate·벽시계 회차·Lock·Collector/Backup 조립·사건로그·파생 출력 |
| `tests/test_eg7.py` | 계획·Scheduling·Lock·실패·인덱스·Dry-run 합성 테스트 |
| `scripts/project_guard_check.py` | H-707 오프라인 반복주기 계약 활성화 |
| `tests/test_project_guard_check.py` | H-707 PASS·회귀·47개 집계 검증 |
| `README.md` | 운영자용 EG-7 범위·Dry-run·Live 차단 안내 |
| `docs/testing/PROJECT_GUARD_SPEC.md` | H-707 입력·PASS·FAIL·활성 상태 |
| `docs/testing/QUALITY_GATES.md` | EG-7 구현·실제 파일럿 통과조건 분리 |
| `docs/engineering/FreshManager_TRD_v1.0.md` | Controller와 파생 인덱스 기술 구조 |
| `docs/rules/DATA_COLLECTION_RULES.md` | 5분·무보충·실패·중복 보존 규칙 |
| `docs/data/FIELD_DICTIONARY.md` | 계획·사건·Slot/Area Index·Summary 필드 |
| `ai-context/DECISION_LOG.md` | 1시간 구현 D-012·장기 5분 결정 D-013 |
| `ai-context/ARCHITECTURE_DECISIONS.md` | Controller ADR-008·고정 주기 ADR-009 |
| `AGENTS.md` | 고정 주기와 별도 OPEN 운영시간·Live 승인 경계 |
| `docs/product/FreshManager_PRD_v1.0.md` | 장기 5분 제품·운영 결정 |
| `docs/analysis/ANALYSIS_PLAN.md` | 분석 집계구간과 수집주기 대안 구분 |
| `ai-context/PROJECT_MEMORY.md` | 장기 주기 복원 기준 |
| `PROJECT_STATUS.md` | 현재 Issue·Branch·PR·검증·다음 행동 |

## 8. 검증 상태

PR #71 병합 직후 당시 exact-main
`562f984d7f84203196b34f8d1d827310405d3cc3`에서 확인한 결과:

- EG-7 Target Tests: `33/33 PASS`
- Project Guard Tests: `136/136 PASS`
- Full Unit Tests: `367/367 PASS`
- Project Guard: `PASS 43 / FAIL 0 / WARN 0 / SKIP 4 / TOTAL 47`
- H-706: `PASS`
- H-707: `PASS`
- H-708: `PASS`
- Markdown 구조·코드 블록: `13/13 PASS`
- `git diff --check`: `PASS`
- exact-main GitHub CI: `SUCCESS`
- 서울시 API 호출: `0`
- S-DoT API 호출: `0`
- 운영 Collector 실행: `0`
- 운영 Backup 실행: `0`
- 운영 Batch 접근: `0`
- Google Drive 접근: `0`
- 운영 Batch ID 생성·예약: `0`
- 기존 운영 증거 변경: `0`
- 기존 Fake 증거 변경: `0`

H-707은 구현과 함께 `PASS`로 활성화됐지만 이는 합성 계약 검사다. 위 결과는 실제
할당량 확인·운영 계획 생성·PM Live 승인 또는 첫 Live 수집 완료를 의미하지 않는다.

## 9. GitHub 상태

- 정본 Branch: `main`
- 현재 `main` SHA: `VERIFY_AT_SESSION_START`
- local·`origin/main` 일치: `MUST_BE_VERIFIED_AT_SESSION_START`
- 확인 방법: 세션 시작 시 `local main`과 `origin/main`을 조회·비교
- 주의: 문서에 기록된 과거 SHA를 현재 HEAD로 가정하지 않음
- PR #71: `MERGED`
- Issue #70: `CLOSED`
- Issue #69: `OPEN`
- 병합된 feature Branch: local·remote `DELETED`
- post-merge 검증 시 작업 트리: `CLEAN`
- post-merge 검증 시 미추적 파일: `0`

## 10. 다음 행동

현재 OPEN 또는 미생성 결정:

- First Live Date: `OPEN`
- First Live Start Time: `OPEN`
- Daily Operating Window: `OPEN`
- 24-hour or Selected-hour Operation: `OPEN`
- API Quota Confirmation: `UNCONFIRMED`
- Operational `pilot_run_id`: `NOT_GENERATED`
- Operational Batch IDs: `NOT_GENERATED`
- Approved Plan Fingerprint: `NOT_GENERATED`
- PM Live Approval: `NOT_APPROVED`
- Expansion Timing: `OPEN`

5분 장기 주기는 `CLOSED · PM_APPROVED_FIXED`이며 OPEN 결정이 아니다.

다음 행동 순서:

1. 이 `PROJECT_STATUS.md` 동기화 PR을 PM 승인으로 `main`에 병합한다.
2. 공식 API 할당량과 rate-limit 호환성을 확인한다.
3. 로컬 Source와 Drive sync-copy preflight를 확인한다.
4. 범위가 고정된 운영 Plan v2 하나를 생성한다.
5. `pilot_run_id` 하나와 Batch ID 정확히 12개를 생성한다.
6. 결정적 Plan fingerprint를 생성·검증한다.
7. 그 정확한 Plan에 대한 한정된 PM Live 승인을 기록한다.
8. 첫 Area-only 1시간 Live 수집을 실행한다.
9. 즉시 기술·데이터 품질 분석을 수행한다.
10. 자동 확대 없이 중단한다.
11. 다음 Area 수집 시간창을 결정한다.
12. 별도 승인된 S-DoT·ML·Spot Workstream을 계속한다.

2번 이후의 운영 단계는 각 단계에 필요한 확인과 별도 PM 승인을 전제로 하며,
24시간 수집으로 자동 확대하지 않는다.

## 11. 새 세션 복원 메모

새 세션은 `AGENTS.md` → 이 문서 → `ai-context/PROJECT_MEMORY.md` → PRD → TRD →
Issue #69와 현재 Diff → 관련 Rule·Quality·Data 문서 → Decision Log·ADR 순서로
읽는다.

정본 Branch는 `main`이다. 새 세션 시작 시 `origin`을 fetch하고 `local main`과
`origin/main`을 조회·비교해 현재 HEAD를 확인한다. 문서에 저장된 SHA를 현재 HEAD로
가정하지 않는다. PR #71은 병합됐고 Issue #70은 종료됐으며 Issue #69는 열려 있다.
마지막으로 검증된 EG-7 고정주기 기능 구현 기준선은 PR #71 Squash Merge SHA
`562f984d7f84203196b34f8d1d827310405d3cc3`다. EG-7 구현과 고정 5분 장기 주기는
`main`에 있지만 Live 수집은 시작하지 않았다. API 할당량은 `UNCONFIRMED`, 운영
Plan·`pilot_run_id`·Batch ID·Plan fingerprint는 아직 존재하지 않는다. S-DoT
동적 수집·ML 학습·Spot 실행도 시작하지 않았다. 다음 작업은 첫 Live 파일럿
preflight와 정확한 Plan에 대한 한정된 PM 승인이다. EG-7 구현 Branch를 다시
만들지 않는다.
