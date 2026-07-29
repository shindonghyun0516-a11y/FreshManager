# FreshManager Project Status

## 1. 문서 역할

이 문서는 현재 Branch·Pull Request·Issue·외부 실행·검증·다음 행동을 복원하는
단일 운영 기준이다. 제품 목적은 PRD, 기술 계약은 TRD, 검사 ID와 판정은
`docs/testing/PROJECT_GUARD_SPEC.md`를 따른다.

마지막 동기화 시각: `2026-07-29` (Asia/Seoul)

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
- 장기 Spot 원격 추천 계약: `AVAILABLE_ON_MAIN`(D-020, PR #130)
- 초기 파일럿 A안: `FIVE_AREA_SPOT_SELECTION_SUPPORT_AVAILABLE_ON_MAIN`(D-021, PR #131)
- 파일럿 사용자 선택 Spot 정적 Master: `AVAILABLE_ON_MAIN`(Issue #132, PR #133)
- 초기 파일럿 Area 추천 Core: `IMPLEMENTED_ON_ISSUE_134_BRANCH_PENDING_DRAFT_PR_REVIEW`
- Spot 자동 추천: `DEFERRED_AFTER_INITIAL_PILOT`
- 24시간 Scheduler(로컬 EG-7 Live 파일럿 확대 기준): `NOT_IMPLEMENTED`
- ML 학습: `COMPARISON_COMPLETED_NOT_ADOPTED`; 추천 사용 `false`
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
- EG-8C(미래 Area 인구·피크 예측 모델): `IN_PROGRESS`
- EG-8D(Area Ranking·선택적 S-DoT·Spot Candidate Evaluation): `IN_PROGRESS` — 서울시
  Forecast 기반 60분·180분 Area 예상 유동인구 변화 순서는 PR #110으로 main 반영.
  Horizon별 데이터 최신성 잠정 Gate는 PR #112로 main 반영되고 Issue #111은 종료됐으며,
  선택적 S-DoT·Spot Candidate Evaluation은 미착수
- EG-8E(Recommendation Output Contract·UI/UX Readiness): `PLANNED` — Recommendation
  MVP 구현 Gate가 아니며, Recommendation MVP Workstream의 공식 Gate 번호는 계속
  `NOT_ASSIGNED`다

구현 상태:

- Python Loader: `IN_PROGRESS`
  - Source Reader·Schema Validation·Normalization: `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #84)
  - Duplicate Detector·Quality Report·Dataset Manifest·최종 Output Writer: `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #86, Issue #85)
  - 실제 오류 응답 기반 검증: `NOT_COMPLETED`(합성 Fixture 오류 경로만 테스트 통과, 실 v3 CSV Smoke는 정상 경로만 확인)
- Manual V3 Snapshot Intake: `LOCAL_IMPLEMENTATION_COMPLETE_PENDING_PM_DIFF_REVIEW`
  (Issue #113) — 합성 CSV로만 구현·검증했으며 실제 운영 CSV 반입, Commit·Push·PR,
  Apps Script·Dataset·ML 실행은 하지 않음
- EG-8B Dataset Profile·시간 커버리지·Forecast-Current Exact Join(B1): `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #88, Issue #87)
- EG-8B Phase 1 Read-only 준비도 분석(ML-ready Dataset·EDA·Forecast 평가·Baseline 가능성): `COMPLETED`
- ML-ready Dataset: `LOCKED_OFFICIAL_RUN_2` — Run ID `eg8c-20260727T153257-kst`,
  Manifest SHA-256 `388a5e6649e6e23d05a442ae9b4f8d0857f8ea382011c2ff07c0af64aae42771`
- 신규 공식 데이터 묶음: Run ID `d5e888ef-7514-4f3a-83f5-7820dec58088` —
  Issue #119 재평가에 사용했으며 기존 공식 데이터 묶음을 변경하거나 삭제하지 않음
- EDA: `NOT_STARTED`
- EG-8B B2a(B0 Persistence Baseline·서울시 Forecast 단일 일자 잠정 Backtest): `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #92, Issue #89) — 단일 일자 잠정 결과이며 공식 성공 임계값·EG-8B Gate PASS/FAIL 판정이 아님
- EG-8B B2b — 2026-07-24 01:00~2026-07-25 07:00 단기 다일자 Baseline·Forecast 검증: `IMPLEMENTATION_AVAILABLE_ON_MAIN`(Parent Issue #93, PR #94) — 단기 다일자 잠정 검증 결과이며 evaluation_status=PROVISIONAL, coverage_status=SHORT_WINDOW_MULTI_DAY_PARTIAL_COVERAGE, gate_judgment=null. 공식 성공 임계값·EG-8B Gate PASS/FAIL 판정이 아님. 장기 다일자·5영업일·4주·공식 Gate 평가는 데이터 추가 축적 후 별도 검토한다.
- EG-8C 1차(Feature·Label·Provisional Train/Validation Split): `IMPLEMENTATION_AVAILABLE_ON_MAIN`(Parent Issue #95, PR #96) — evaluation_status=PROVISIONAL, data_sufficiency_status=PROVISIONAL_SPLIT_ONLY, test_split_created=false, official_model_gate_judgment=null, Leakage 12종 위반 0, 지원 Horizon 60·180분만. 모델 학습·공식 Test 평가·Peak 예측·EG-8D·EG-8E·UI·E2E는 이번 범위에 포함하지 않음. 장기 다일자·5영업일·4주·공식 Gate 평가는 데이터 추가 축적 후 별도 검토한다.
- EG-8C 이전 잠정 Modeling Run: `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #108) — Run ID
  `eg8c-ml-20260727T202447-kst`, Modeling Manifest SHA-256
  `7a1748102fc2b079084ace8bcdb539f99535eab7ffc696e8a04b2b2c2d42df13`,
  Training Matrix 2,158행(TRAIN 1,742 /
  VALIDATION 416), Current·서울시 Forecast Baseline과 Linear·Ridge를 동일 Validation
  행에서 비교. 서울시 Forecast가 가장 강한 Baseline이며 두 모델 모두 승인된
  MAE/RMSE 통과조건을 충족하지 못해 `BASELINE_RETAINED`. 평가상태는
  `PROVISIONAL`, Test Split 미생성, 공식 Model Gate 판단 `null`, 피크 예측 미구현.
- EG-8C 신규 공식 데이터 재평가: `COMPLETED`(Issue #119, Issue #120, PR #121) —
  모델 실행 Run ID `eg8c-ml-20260729T075003-kst`, 결과 명세 SHA-256
  `e1447b534091a8dfdb5003a707abfb6f53caf68b549ffa952b760f83ed7f0a0d`.
  Ridge는 PM 결정에 따라 `alpha=100.0`으로 고정하고 자동 탐색하지 않았다. 서울시
  미래 예상값 기준 예측이 전체·60분·180분과 13개 Area 모두에서 가장 정확해
  `BASELINE_RETAINED`로 확정했다. Linear·Ridge는 채택하지 않고 현재 PoC의 추가
  모델 조정을 종료했다. 별도 최종 시험구간은 없고 평가는 `PROVISIONAL`, 공식
  Model Gate 판단은 `null`이며 운영 사용·사용자 게시·공식 추천은 허용하지 않는다.
- ML Model: `BASELINE_RETAINED_PROVISIONAL`
- Issue #118: `CLOSED·COMPLETED` — 30분 직접 예상값 부재와 무대체 정책,
  현재·30·60·90·120·150·180분 표시구조를 확정했으며 UI는 구현하지 않음
- Area·Spot 원격 근거 정책·준비도: `LONG_TERM_CONTRACT_AVAILABLE_ON_MAIN`
  (Issue #126·#129 완료, PR #127·#130 병합) — D-020은 장기 제품가치를 Area 안의
  특정 Spot과 판매시간 추천으로 유지한다. 원격 근거 Eligibility를 충족하면
  `field_verification_status=UNAVAILABLE`,
  `operational_suitability_status=NOT_VERIFIED` 상태에서도 SPOT 추천이 가능하다.
  이는 판매 허용·안전·카트 정차·운영 적합성·판매 성공을 보장하지 않는다.
  현재 원격 SPOT 추천 가능 Spot 0개, 추천 실행 0건이며
  S-DoT 동적 수집·결합과 실제 Spot 좌표 기준 재연결은 미완료다.
- 초기 파일럿 A안: `AVAILABLE_ON_MAIN`(D-021, Issue #128, PR #131) — 서울시
  공식 Forecast로 5개 Area와 판매시간을 `AREA` 단위로 추천하고, Area당 대표
  Spot 3개를 `USER_SELECTABLE_OPTION`으로 제공해 사용자가 직접 선택한다. Spot별
  동적근거·자동추천·Backtesting은 `DEFERRED_AFTER_INITIAL_PILOT`이며 머신러닝은
  비교기록만 보존하고 추천에 사용하지 않는다. 생산 Schema·Backend·UI·배포와
  공식 추천 실행은 0건이다.
- 파일럿 사용자 선택 Spot 정적 Master: `AVAILABLE_ON_MAIN`(Issue #132, PR #133) —
  5개 Area·각 3개·총 15개의 주소와 PM 확인 좌표를 기존 Candidate Anchor와 분리해
  저장한다. 모두 사용자 직접 선택용이며 현장검증·운영 적합성·Spot별 동적근거·
  자동추천·추천순위·기본선택은 없다.
- 초기 파일럿 Area 추천 Core:
  `IMPLEMENTED_ON_ISSUE_134_BRANCH_PENDING_DRAFT_PR_REVIEW` — 정확한 5개 Area의
  60분·180분을 독립 판정한다. 완전한 `RUNTIME`·`FRESH` Horizon의 양수 후보만
  `pilot_recommendation_allowed=true`로 반환하고,
  `official_recommendation_allowed=false`는 유지한다. 양수 후보가 없으면
  `recommendation=null`이다. 선택 Area의 Spot은 순위 없는 정확히 3개 사용자
  선택지이며 ML은 사용하지 않는다. Backend·UI·배포·파일 산출물 게시는 없고
  추천 실행은 0건이다.
- Area Ranking: `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #110, Issue #109) — 서울시
  Forecast 기반 60분·180분 예상 유동인구 변화·미래 인구 규모 순위를 각각 계산.
  `LATEST_COMPLETE_LOCKED_SNAPSHOT` 정책으로 잠긴 Dataset의 전체 1,027회 중 승인된
  13개 Area Current와 정확한 60분·180분 Forecast가 완전한 86회를 판별하고,
  Prediction Origin 정본 필드 `observed_at`이 가장 최신인 회차를 순위 계산 전에 자동
  선택한다. 동률이면 실패하며 호출자가 회차를 지정하지 않는다. 결정적 선택 보완
  Result Run `eg8d-area-priority-20260728T074335-kst`는 기존과 같은 회차
  `6ebf1dab-8494-44e0-b598-80248f7f6ff0`을 선택했고, 각 시간간격 13개 Area,
  제외 0개. 60분은 양의 증가 1개·중간값 변화 0인 Area 8개·감소 4개이고 1위는
  잠실역(+2,000명)이다. 180분은 양의 증가 0개·중간값 변화 0인 Area 3개·감소
  10개로 증가 후보가 없다. 180분 1위는 전체 표시 순서일 뿐 판매 추천이 아니다.
  변화 0은 범위 중간값 차이 0만 뜻하고 예측 불확실성을 제거하지 않는다. 한 수집
  회차 Snapshot의 `PROVISIONAL` 내부 Area 분석이며 공식 Recommendation Output·
  실제 방문·판매 성공 보장이 아니다. 가중치·Spot·S-DoT·판매량·매출·구매전환은
  포함하지 않음. 기존 Result Run `eg8d-area-priority-20260728T003701-kst`는 보존됨.
- Area Ranking Freshness Gate:
  `IMPLEMENTATION_AVAILABLE_ON_MAIN`(Issue #111, PR #112) — 공개 Runtime은
  평가시각·모드·게시 표식을 받지 않는 Runtime 전용 경로만 사용하고, 해당 경로가
  실행 시작의 서울 시스템 현재시각과 운영 실행 맥락을 한 번만 확정한다. 공통 실행부는
  이처럼 이미 확정된 내부 실행 맥락만 소비하며 원시 평가시각·모드·게시 표식을 받거나
  시스템 시각을 읽어 Runtime을 시작할 수 없다. 평가시각 주입 내부 경로는
  `HISTORICAL_AUDIT`·`SYNTHETIC_VALIDATION`만 허용하며 표식이 일관돼도 `RUNTIME`은
  계약 오류로 차단한다. `evaluation_time`과 `Asia/Seoul` 시간 계약으로 Snapshot 경과시간·완전성 지연·
  60분·180분 잔여시간을 계산하고 Horizon별 `FRESH`·`DEGRADED`·
  `STALE_BLOCKED`를 독립 판정한다. `DEGRADED`는 경고가 있는 Area 참고정보만
  허용하고 Spot 내부평가는 차단하며, 공식 Recommendation은 항상 차단한다. 완전
  Snapshot 부재 시 생산 Builder가 최신 Current 회차의 13개 Area 완전성·중복·인구
  범위·시각을 검증하고, `RUNTIME`의 15분 이내 Current만 전용 4파일 계약으로
  표시한다. Forecast·변화·순위·Spot·추천 필드는 생성하지 않는다. 15분 초과와
  `HISTORICAL_AUDIT`는 전용 계약에 차단 사유만 기록하며, Current 결함·미래 시각은
  공개 전에 실패한다. 임계값은 PoC
  잠정값이며 수집 스키마·기존 선택·순위 계산은 변경하지 않음. 잠긴 Dataset 사례
  A/B/C는 별도 외부 Result Root의 새 Run 세 개로 검증했고 각각
  `FRESH/FRESH`, `STALE_BLOCKED/DEGRADED`,
  `STALE_BLOCKED/STALE_BLOCKED`였으며 기존 EG-8D Result Run은 변경하지 않음.
  보완 전 합성 D(10분)·E(16분)는 그대로 보존했다. 합성 식별 보완 후 새 D2
  `eg8d-area-priority-20260728T134259-kst`와 E2
  `eg8d-area-priority-20260728T134301-kst`를 저장소 밖에서 각 1회 생성했으며 정책 결과는
  각각 `CURRENT_ONLY_ALLOWED`·`CURRENT_ONLY_BLOCKED`다. 두 결과 모두 사용자 표시·
  운영 게시·운영 통계 사용을 차단하고, Manifest SHA-256은 각각
  `f743bc49955e7443e44ad7a331c7dbafae403093216d77d5fb8dc6db3970fa2b`,
  `11d1ff201926a2a77a56559cb27ae06c6340144b2640815590b1077b8de946e9`다.
  공개 `RUNTIME` Builder 통합시험과 주입시각의 `RUNTIME` 위조 차단시험에 더해,
  공통 실행부가 과거시각 또는 `None`과 원시 `RUNTIME` 조합을 받을 수 없고 내부 시계를
  읽지 않는 회귀시험을 추가해 마지막 내부 실행계약 문제를 해소했다. D2·E2 계약과
  결과는 그대로 유효하다. 실제 고정 `+09:00` 입력 생성 경로는
  확인되지 않아 입력 경계 정규화를 후속 과제로 남김. 승인 격리환경 Python 3.12.13·
  scikit-learn 1.6.1에서 공통 실행부 직접차단 3개·Runtime 신뢰경계 13개·
  Publication 18개·EG-8D 70개·EG-8C 머신러닝 24개·전체 707개
  시험과 Project Guard `PASS=43, FAIL=0, WARN=0, SKIP=4` 통과.
- Spot Ranking: `DEFERRED_AFTER_INITIAL_PILOT`
- Recommendation Contract: `DRAFT_UPDATED_IN_PR_131`; 생산 Schema `NOT_IMPLEMENTED`
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
| EG-8C | `IN_PROGRESS` | 신규 공식 데이터 재평가 `COMPLETED`(Issue #119, Issue #120, PR #121), 서울시 미래 예상값 기준 예측 `BASELINE_RETAINED`; Linear·Ridge 미채택·PoC 추가 조정 종료, 공식 Model Gate 미완료, 피크 예측 미구현 |
| EG-8D | `IN_PROGRESS` | Area 예상 유동인구 변화 순서 `IMPLEMENTATION_AVAILABLE_ON_MAIN`(PR #110); Horizon별 최신성 잠정 Gate `IMPLEMENTATION_AVAILABLE_ON_MAIN`(Issue #111, PR #112); 선택적 S-DoT·Spot Candidate Evaluation 미착수 |
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
- Spot 자동 추천: `DEFERRED_AFTER_INITIAL_PILOT`
- ML 학습·성능평가: `COMPARISON_COMPLETED_NOT_ADOPTED` — 공식 모델 채택·Test
  Gate 미실행, 추천 사용 `false`
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
- PR #130: `MERGED`
- PR #131: `MERGED`
- PR #133: `MERGED`
- Issue #70: `CLOSED`
- Issue #69: `OPEN`
- Issue #129: `CLOSED`
- Issue #128: `CLOSED`
- Issue #132: `CLOSED`
- Issue #134: `OPEN`
- Issue #134 Source Branch: `feat/issue-134-pilot-area-recommendation`
- Issue #134 Draft PR: `PENDING_PM_REVIEW`
- 병합된 feature Branch: local·remote `DELETED`
- post-merge 검증 시 작업 트리: `CLEAN`
- post-merge 검증 시 미추적 파일: `0`

## 10. 다음 행동

현재 최우선 한 단계는 Issue #134의 메모리 내 초기 파일럿 Area 추천 Core 변경을
Draft PR에서 PM이 검토하는 것이다. 추천 실행·Ready 전환·병합은 별도 승인 전
수행하지 않는다. 아래 EG-7 Live 결정은 독립 backlog로 유지한다.

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

1. Issue #134 초기 파일럿 Area 추천 Core Draft PR을 PM이 검토한다.
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
동적 수집·Spot 실행은 시작하지 않았고, ML은 비교 완료 후 미채택 상태다. D-021은
초기 파일럿을 서울시 공식 Forecast 기반 Area 5개·판매시간 추천과 사용자 선택
Spot 3개로 제한했다. Issue #132·PR #133의 정적 Master는 `main`에 있고, 현재
다음 작업은 Issue #134 메모리 내 추천 Core Draft PR의 PM 검토다. 추천 실행은
0건이다. EG-7 Live
preflight는 독립 backlog이며 EG-7 구현 Branch를 다시 만들지 않는다.
