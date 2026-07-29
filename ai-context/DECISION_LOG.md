# FreshManager Decision Log

## 1. 문서 역할

PM이 승인했거나 명시적으로 보류한 제품·운영 결정을 새 AI 세션이 다시 추측하지
않도록 기록한다. 현재 상태는 [`PROJECT_STATUS.md`](../PROJECT_STATUS.md), 제품·기술
상세는 PRD와 TRD가 소유한다. 날짜가 확인되지 않은 과거 결정은 추정하지 않고
`NOT_RECORDED`로 표시한다.

## 2. 상태값

- `ACCEPTED`: 현재 적용하는 승인 결정
- `PLANNED`: 방향만 승인됐고 구현·외부 실행 승인은 남은 결정
- `OPEN_DECISION`: PM이 아직 확정하지 않은 선택
- `HISTORICAL`: 과거 이력이며 현재 실행 기준이 아닌 결정
- `SUPERSEDED`: 후속 결정으로 대체된 결정

## 3. 결정 목록

### D-001 — 현재 MVP는 13개 Area 패널

- Date: `NOT_RECORDED`
- Status: `ACCEPTED`
- Decision: EG-6A에서 승인한 서로 다른 공식 Area 13개를 현재 MVP 수집·분석 패널로 사용한다.
- Reason: 대표 Area 다양성과 단일·반복 수집 운영 가능성을 121개 확대 전에 검증한다.
- Evidence: Issue #51, PR #52, `data/reference/eg6_area_panel.csv`
- Consequence: Collector 대상은 Spot 좌표가 아니라 공식 `area_code`와 `panel_order`다.

### D-002 — 121개 Area 즉시 확대 보류

- Date: `NOT_RECORDED`
- Status: `ACCEPTED`
- Decision: 13개 패널의 단일·반복 수집과 Feature 분석에서 필요성이 확인되기 전에는 121개 Area로 확대하지 않는다.
- Reason: 호출량·실패율·갱신주기·저장량과 분석 가치를 먼저 측정해야 한다.
- Consequence: 과거 `10개 → 121개 1회` 계획은 역사 이력이며 현재 실행 순서가 아니다.

### D-003 — Area First

- Date: `2026-07-22`
- Status: `ACCEPTED`
- Decision: Area Observation을 모든 승인 Area의 Core Observation으로 사용한다.
- Reason: 서울시 API의 공식 수집 단위가 Area이며 S-DoT·Spot 근거 유무와 독립적으로 확보할 수 있다.
- Consequence: S-DoT 또는 Spot 오류로 Area 수집을 중단하거나 재호출하지 않는다.

### D-004 — Spot Proxy 해석 제한

- Date: `NOT_RECORDED`
- Status: `ACCEPTED`
- Decision: Spot Master의 `STATION_CENTER_PROXY`는 Candidate Anchor Point이며 실제 출구·고정 판매 위치가 아니다.
- Evidence: Issue #51, PR #52
- Consequence: `field_verified=false`인 Anchor를 직접 관측 Spot 또는 추천 성공으로 표현하지 않는다.

### D-005 — S-DoT는 독립·선택적 보조 근거

- Date: `2026-07-22`
- Status: `ACCEPTED`
- Decision: S-DoT는 지원·접근·수집·품질조건을 만족할 때만 Spot Candidate Evaluation을 보조한다.
- Reason: S-DoT는 Area 데이터의 대체값이나 모든 Area의 필수 다음 단계가 아니다.
- Consequence: S-DoT Collector와 Area Collector를 분리하고, 미지원 6개 Area도 분석·추천 후보로 유지한다.

### D-006 — 추천은 SPOT 우선, AREA fallback

- Date: `2026-07-22`
- Status: `ACCEPTED · SUPERSEDED_IN_PART_BY_D-020`
- Decision: 신뢰 가능하고 운영 가능한 Spot이 있으면 `target_level=SPOT`, 없으면 `target_level=AREA`와 `fallback_reason`을 사용한다.
- Consequence: Area fallback은 실패가 아니라 Spot 근거 부족을 명시하는 정상 결과다.
- Supersession: D-020은 원격 SPOT 추천에 운영 적합성 확인을 요구하던 부분만
  대체한다. SPOT 우선·AREA fallback과 Area 값을 Spot 직접값으로 쓰지 않는 원칙은
  유지한다.

### D-007 — EG-6C 미신설

- Date: `2026-07-22`
- Status: `ACCEPTED`
- Decision: Backup Worker와 CSV Exporter를 EG-6C라는 공식 Engineering Gate로 만들지 않는다.
- Consequence: EG-6B Live 준비 및 첫 Batch 이후의 독립 작업으로 Issue·승인·검증을 관리한다.

### D-008 — EG-9 미확정

- Date: `2026-07-22`
- Status: `ACCEPTED`
- Decision: Recommendation MVP를 EG-9로 확정하지 않는다.
- Current expression: `PLANNED Recommendation MVP Workstream`, Gate number `NOT_ASSIGNED`.
- Consequence: EG-8 증거와 별도 PM 승인 전 공식 Gate 또는 구현 완료 상태로 표현하지 않는다.

### D-009 — Spot 정량 점수는 미확정

- Date: `2026-07-22`
- Status: `OPEN_DECISION`
- Decision: 현 단계의 필수 계약은 `Spot Candidate Evaluation` 또는 `Candidate Evidence Assessment`다.
- Open items: Score 사용 여부, 가중치, 임계값, 버전·검증 기준.

### D-010 — Google Drive 자동 백업 목표

- Date: `2026-07-22`
- Status: `ACCEPTED`
- Decision: 검증된 로컬 Batch를 별도 1회 실행형 Backup Worker가 Batch 완료 직후 Google Drive for Desktop Sync 동기화 폴더로 복사한다.
- Constraints: Collector와 분리, 백업 실패 시 API 재호출 금지, Secret 제외, Manifest SHA-256 재검증.
- Backup root: `FreshManager-Data/` 논리 구조만 정의한다.
- Privacy: 실제 계정 이메일과 동기화 절대경로는 저장소·Receipt·로그에 기록하지 않는다.
- Completed implementation history: Issue #60에서 `--batch-id` 1회 실행형 Worker,
  비동기화 Lock·append-only Receipt와 H-708을 구현하고 PR #61로 `main`에 병합했다.
- State boundary: Worker는 `LOCAL_SYNC_COPY_VERIFIED`까지만 기록하며 원격 업로드 완료를 주장하지 않는다.
- Operational boundary: 실제 Sync Root, Fake·실제 Batch, Restore와 원격 동기화의
  현재 확인 상태는 `PROJECT_STATUS.md`를 따른다. 외부 실행에는 별도 PM 승인이 필요하다.

### D-011 — CSV는 Raw 파생자료

- Date: `2026-07-22`
- Status: `PLANNED`
- Decision: CSV는 조회·정렬·분석용 파생자료이며 Raw JSON이 공식 원본이다.
- Consequence: CSV는 첫 실제 Batch 품질 감사 후 별도 구현하고, 생성 실패 시 Raw에서 재생성하며 API를 재호출하지 않는다.

### D-012 — EG-7 첫 파일럿은 5분·1시간 승인 계획

- Date: `2026-07-23`
- Status: `ACCEPTED`
- Decision: 첫 EG-7 구현은 `Asia/Seoul` 벽시계 5분 경계, 1시간, 12회차,
  고정 13 Area, 전체 최대 156호출, Area별 회차당 최대 1회, 재시도 0회로 제한한다.
- Identity: 하나의 `pilot_run_id`와 회차별 시각·사전 생성 UUIDv4 Batch ID를 가진
  불변 계획 Option C를 사용한다. 건너뛴 ID도 계획 이력에 남겨 재사용하지 않는다.
- Scheduling: 늦은 회차는 `SKIPPED_MISSED`, 이전 Collector와 즉시 Backup이
  끝나지 않은 회차는 `SKIPPED_OVERLAP`이며 지연 보충수집은 하지 않는다.
- Failure: 개별 Area 실패는 기록 후 계속할 수 있지만 확정 공통·자격증명·스키마·
  할당량·저장·Backup 실패는 남은 회차를 중단한다. Backup 실패로 재수집하지 않는다.
- Data: Raw를 모두 보존하고 Area별 중복 관측시각·Raw SHA-256·Forecast 대상시각
  집합을 canonical 증거 기반 Slot·Area 파생 인덱스와 Summary에 기록한다.
- Excluded: 동적 S-DoT, Spot 평가, Recommendation, ML 학습, 24시간·영구 Scheduler.
- Open Live decisions: 실제 날짜·시작시각·할당량 확인·운영 `pilot_run_id`·12개
  Batch ID·계획 지문·PM Live 승인.
- Evidence: Issue #69 승인 범위, Issue #70 구현.

### D-013 — 5분은 고정 장기 반복수집 기준

- Date: `2026-07-23`
- Status: `ACCEPTED · PM_APPROVED_FIXED`
- Supersedes: 5분을 파일럿 전용·비교 후보·OPEN 결정으로 표현한 모든 과거 문구.
- Closed decision: `cadence_minutes=5`,
  `cadence_decision_status=PM_APPROVED_FIXED`,
  `long_term_baseline_status=ACTIVE`,
  `cadence_scope=LONG_TERM_OPERATING_BASELINE`, `cadence_change_allowed=false`.
- Scheduling: `Asia/Seoul` 벽시계 5분 정렬을 사용한다. 10분·15분 대안은 지원·평가하지
  않으며 새 PM 명시 결정과 버전 계약·코드 검토 없이는 변경할 수 없다.
- Duplicate policy: 모든 Raw를 보존하고 중복 플래그·건수·비율을 기록한다. 중복만으로
  계획 호출을 생략하거나 주기를 바꾸지 않으며 제거·표본선택·가중치는 EG-8
  데이터셋 구성에서 다룬다.
- Pilot purpose: 첫 1시간은 12개 정렬 슬롯, Collector·Backup 완료, 무중첩·무보충,
  최대 156호출, 시간·저장·중복·추적·실패처리와 장기 확대 전 구현·용량 문제를
  검증한다. 주기 선택 실험이 아니다.
- Open decisions: 실제 날짜·시작시각, 일일 운영시간대, 24시간 또는 선택 시간 운영,
  API 할당량·용량 Gate, 운영 `pilot_run_id`·12개 Batch ID·계획 지문, PM Live 승인,
  첫 1시간 이후 확대 시점.
- Evidence: PM Decision Override, Issue #70·Draft PR #71.

### D-014 — Apps Script를 PoC 상시 반복수집 Runtime으로 재채택

- Date: `2026-07-24`
- Status: `ACCEPTED`
- Supersedes: TRD ADR-08("Google Sheets 수집 미채택")과 PRD R-09(과거 대응:
  "현행 로컬 Python을 단일 운영 계약으로 지정")의 결정을 대체한다. 두 항목은
  삭제하지 않고 각 문서에서 `SUPERSEDED`로 표시한다.
- Decision: 승인된 13개 Area의 5분 상시 반복수집 Runtime은 Google Apps Script다.
  로컬 EG-6B/EG-7(Python)은 상시 Scheduler가 아니라 기술검증·Pilot Runner로
  유지한다. Python은 이후 정규화·분석·머신러닝을 담당한다.
- Reason: 저장소를 읽기 전용으로 조사한 결과, 기존 ADR-08의 폐기 근거는
  "현행 로컬 Python·원본 보존·승인 Gate와 충돌"이라는 순환적 서술이었고, 별도
  기술 실패·API 한도·보안 사고 증거는 확인되지 않았다. 반면 로컬 EG-7은
  `time.sleep` 기반 동기 실행 구조라 Codex·Claude Code 세션과 사용자 컴퓨터가
  종료되면 반복수집이 중단된다는 것이 코드로 확인됐다. PM은 "Mac·Codex·Claude
  Code가 꺼져도 5분마다 수집이 계속돼야 한다"는 요구사항을 우선해 기존에 보유한
  Apps Script 자산을 외부에서 직접 복원·검증했다.
- Evidence: PM이 Google 계정 화면에서 직접 확인 — 기존 Spreadsheet·Apps Script
  프로젝트 존재, 공식 POI 코드 기반 13개 Area 호출로 개선, Script Properties에
  `SEOUL_OPEN_API_KEY` 저장, `raw_log_v3`/`population_current_v3`/
  `population_forecast_v3` 시트에 데이터 누적 확인. 이후 5분 시간 기반 Trigger가
  `collectData`를 반복 실행하며 실행마다 서로 다른 `collection_run_id`로 Raw
  13건·Current 13건·Forecast 156건이 계속 쌓이는 것을 추가로 확인 — 5분 자동수집
  동작은 `ACTIVE`다.
- Consequence: TRD·PRD·`etc/데이터수집 실행 가이드.md`·`docs/rules/DATA_COLLECTION_RULES.md`·
  `PROJECT_STATUS.md`·`PROJECT_MEMORY.md`의 관련 표현을 정렬한다. 5분 자동수집
  동작은 `ACTIVE`로 기록하되, Apps Script의 24시간 이상 장기 지속성, 소스 Git
  버전관리, Python 파이프라인과의 데이터 통합은 각각 `NOT_COMPLETED`·`PLANNED`·
  `PLANNED`로 별도 관리하며 이번 결정으로 완료 처리하지 않는다. `ACTIVE`(5분
  자동수집)와 `NOT_COMPLETED`(24시간 이상 지속성)를 같은 의미로 표현하지 않는다.

### D-015 — EG-8을 상위 Gate로 세분화하고 데이터 분석·ML·추천·UI 설계를 PoC 범위에 포함

- Date: `2026-07-24`
- Status: `ACCEPTED`
- Decision: 기존 EG-8("Area Feature + 선택적 S-DoT Feature + Spot Candidate
  Evaluation")을 삭제하지 않고 EG-8D로 흡수한다. EG-8을 데이터 분석·예측·추천
  준비의 상위 Gate로 재정의하고 EG-8A(Python Loader·정규화·데이터 품질),
  EG-8B(EDA·서울시 Forecast 평가·Baseline·Feature Dataset), EG-8C(미래 Area
  인구·피크 예측 모델), EG-8D(Area Ranking·선택적 S-DoT·Spot Candidate
  Evaluation), EG-8E(Recommendation Output Contract·UI/UX Readiness)로
  세분화한다. PoC 범위에 미래 Area 인구·피크 예측, Area/Spot Ranking,
  Recommendation Output Contract, UI/UX 정보구조·와이어프레임·프로토타입을
  포함한다. 매출·판매량·판매 성공확률·수요·재고 예측, 판매성과 인과효과
  검증, 상용 앱·웹 서비스 구현·출시, 실시간 모델 서빙, 완성형 MLOps는 계속
  제외한다.
- Reason: 수집기 구축 단계에서 데이터 분석·ML·추천·UI 준비 단계로 전환이
  필요하나, 수집 데이터가 존재한다는 사실만으로 ML이나 추천 UI를 구현해서는
  안 된다. Baseline 비교 선행과 시계열 누수 방지 원칙을 EG-8 세분화로 명시적
  단계에 귀속시킨다.
- Evidence: PM 결정(EG-8 하위 Gate 구조 확정 및 문서 정합성 PR 1 진행 지시),
  `docs/testing/QUALITY_GATES.md` §12.1~12.5, Issue #77.
- Consequence: 기존 EG-8 참조는 EG-8D를 가리키는 것으로 재해석한다. 이 결정은
  D-008을 대체하지 않는다 — D-008이 결정한 "Recommendation MVP Gate 번호
  `NOT_ASSIGNED`"를 그대로 유지하며, EG-8E는 Recommendation MVP의 구현 Gate가
  아니라 계약·설계 준비(Contract·UI/UX Readiness) Gate다.
- Related: [[D-008]](양립, 미대체), TRD ADR-16, `ARCHITECTURE_DECISIONS.md`
  ADR-011.

### D-016 — Manual V3 Snapshot Intake Metadata 계약

- Date: `2026-07-28`
- Status: `ACCEPTED`
- Decision: Apps Script와 기존 v3 수집동작은 변경하지 않고, 사용자가 수동 Export한
  Raw·Current·Forecast v3 CSV와 `upload_manifest.csv`를 저장소 밖 불변 Snapshot으로
  검증·보존한다. 실제 Snapshot 반입은 구현 병합 후 별도 승인한다.
- Intake purpose: `DATA_QUALITY_VALIDATION`, `HISTORICAL_ANALYSIS`, `UI_PROTOTYPE`,
  `MODEL_EVALUATION`, `PM_APPROVED_LIMITED_SNAPSHOT_REVIEW`만 허용한다. 어떤 값도
  사용자 게시·Spot 추천·공식 Recommendation을 자동 허용하지 않는다.
- Origin: `source_origin_confirmed_by_pm`은 현재 운영 v3 시트에서 반출한 출처 확인만
  뜻한다. `false`는 검증보고서까지만 허용하고 Final 공개를 차단한다.
- Identity: 역할명이 포함된 Raw·Current·Forecast SHA-256 조합을
  `source_content_fingerprint`로, Source 지문과 정규화한 Upload Manifest를
  `intake_metadata_fingerprint`로 사용한다. Snapshot ID는 Source 지문으로 결정한다.
- Duplicate policy: 같은 Source·Metadata의 기존 Final은 중복으로 차단하고, 같은
  Source의 Metadata 변경은 재분류로 차단한다. Final이 없는 실패 Staging은 재시도를
  막지 않으며 내용이 달라 Source 지문이 바뀐 CSV만 신규 Snapshot으로 허용한다.
- Data boundary: 누적 CSV 전체를 독립 보존하며 원본을 수정하지 않는다. 증분병합,
  신규 행 영구추출, 실제 운영 CSV 반입, Apps Script 자동화, Dataset·ML·API·Backend·
  Database 연결은 이번 결정의 구현 범위가 아니다.
- Spot boundary: 좌표·서울 범위·Area 연결·출처·Proxy 상태·DESK 검증만 현재 허용하며
  Dynamic Spot 근거, 자동승격, 사용자 게시와 공식 Recommendation은 제외한다.
- Evidence: Issue #113 PM 승인 댓글, `docs/data/MANUAL_V3_SNAPSHOT_INTAKE.md`.

### D-017 — EG-8C 신규 공식 데이터 재평가는 서울시 미래 예상값 기준 예측 유지

- Date: `2026-07-29`
- Status: `ACCEPTED`
- Decision: 신규 공식 데이터 Run `d5e888ef-7514-4f3a-83f5-7820dec58088`의 재평가
  결과를 `BASELINE_RETAINED`로 확정한다. 현재 가장 신뢰할 수 있는 기준 예측은
  `seoul_forecast_baseline`이며 Linear Regression과 Ridge Regression은 채택하지
  않는다. 현재 PoC의 두 모델 추가 조정도 종료한다.
- Ridge contract: Issue #120·PR #121의 최신 PM 결정에 따라 `alpha=100.0`을 고정하고
  자동 탐색하지 않았다.
- Reason: 모델 실행 Run `eg8c-ml-20260729T075003-kst`에서 서울시 미래 예상값 기준
  예측이 전체·60분·180분과 승인된 13개 Area 모두에서 가장 정확했다. 결과 명세
  SHA-256은 `e1447b534091a8dfdb5003a707abfb6f53caf68b549ffa952b760f83ed7f0a0d`다.
- Gate boundary: 별도 최종 시험구간은 만들지 않았고 `evaluation_status=PROVISIONAL`,
  `data_sufficiency_status=PROVISIONAL_SPLIT_ONLY`, `test_split_created=false`,
  `official_model_gate_judgment=null`을 유지한다. 공식 모델 승격·운영 사용·사용자
  게시·공식 추천을 승인하지 않는다.
- Revisit conditions: 여러 주 또는 여러 달의 데이터, 별도 최종 시험구간, 날씨·행사
  등 새 입력자료, 실제 방문·판매·매출 자료, 서울시 미래 예상값 오차보정 문제의 별도
  정의가 생기고 PM이 새로 승인한 경우에만 자체 모델을 다시 검토한다.
- Consequence: Issue #119의 재평가를 완료한다. 다음 주요 작업은 OPEN 상태인 Issue
  #118의 UI 정책 검토와 별도 승인된 Spot 검증이며, 이번 결정으로 EG-8D를 다시
  실행하거나 UI·Spot을 구현하지 않는다.
- Evidence: Issue #119, Issue #120, PR #121.

### D-018 — Area 탐색과 Spot 판매 추천의 제품 책임 분리

- Date: `2026-07-29`
- Status: `ACCEPTED · SUPERSEDED_IN_PART_BY_D-019_AND_D-020`
- Decision: Area는 판매기회를 탐색·분석하는 넓은 구역이고, Spot은 Area 안에서
  실제 이동·판매를 안내할 최종 추천 대상이다. 공식 Spot 추천은 Area 기회뿐 아니라
  Spot별 동적 밀집근거, 같은 Area 안의 Spot 비교, 접근성·안전·판매 가능성,
  정보 최신성, 사용자 이동 가능시간과 현장확인을 모두 요구한다.
- Evidence boundary: Area 유동인구를 특정 Spot의 직접 유동인구나 밀집도로 표현하지
  않는다. Spot 근거가 부족하면 Area 안내 또는 판매 후보로 하향한다. 현재 등록된
  13개 역 중심 대리좌표는 모두 `field_verified=false`이므로 판매 후보이며 공식
  추천 가능 Spot은 0개다.
- Supersession: Area와 Spot의 책임 분리, Area 값과 Spot 값의 구분은 유지한다.
  현장확인·운영 적합성을 원격 SPOT 추천의 필수조건으로 둔 부분만 D-019와 D-020이
  대체한다.
- S-DoT boundary: S-DoT는 지원조건을 만족할 때 사용하는 선택적 동적 근거 후보다.
  실제 Spot 좌표와 시간대 관측자료를 결합하기 전에는 Spot 밀집도를 확정하지 않으며,
  근거가 부족하면 Area 안내 또는 판매 후보로 하향한다.
- Time policy: 현재·30·60·90·120·150·180분 표시구조를 유지하고 60·120·180분을
  강조한다. 30분 직접값이 없으면 "현재 제공하지 않음"으로 표시하며 90·150분은
  정확한 값이 있을 때만 표시한다. 현재 머신러닝은 60·180분이고 120분 확대는
  별도 승인사항이다.
- Product direction: 장기 목표는 검증된 Spot·시간·상품 추천이지만 판매량·상품·
  매출·구매전환 자료와 별도 승인 전에는 상품 또는 판매성과를 추정하지 않는다.
- Scope boundary: 이번 결정은 정책 정의다. UI·지도 API·Spot 추천·머신러닝·
  EG-8D·서울시 API·Apps Script 실행 또는 사용자 게시를 시작하지 않는다.
- Evidence: Issue #118 최종 PM 결정, Issue #124,
  `docs/product/AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md`.

### D-019 — 현장검증 불가 환경의 원격 근거 기반 Spot 후보 정책

- Date: `2026-07-29`
- Status: `ACCEPTED · SUPERSEDED_IN_PART_BY_D-020`
- Decision: FreshManager PoC에서는 실제 현장방문과 현장검증을 수행할 수 없다.
  D-018의 현장검증 필수조건은 현재 PoC 범위에서 이 결정으로 부분 대체한다.
  `field_verified=true`를 현재 PoC의 달성조건으로 사용하지 않는다.
- Maximum output: 현재 PoC의 최대 Spot 결과는 `데이터 기반 우선 후보`다. 이는
  현장 적합성 확인 Spot 또는 실제 판매 가능성이 보장된 Spot과 다르다.
- Policy contract: `verification_mode=REMOTE_EVIDENCE_ONLY`,
  `field_verification_status=UNAVAILABLE`,
  `operational_suitability_status=NOT_VERIFIED`,
  `recommendation_scope=DATA_PRIORITY_ONLY`를 적용한다. 이 결정은 생산 스키마 구현을
  승인하지 않는다.
- Evidence method: 공식 위치·시설정보, 선택적 S-DoT 또는 승인된 대체 동적 근거,
  Area 맥락, 다중 자료 일치성, 반복성·Backtesting·민감도와 최신성을 비교한다.
  Area 값을 Spot 직접값으로 사용하지 않는다.
- Safety boundary: 원격자료만으로 실제 안전, 카트 이동·정차, 판매·점유 허용,
  운영 적합성이나 판매 성공 가능성을 확정하지 않는다. 근거가 부족하면 판매 후보
  또는 AREA 안내로 하향한다.
- Future boundary: 향후 실제 운영기관이 별도 현장검증을 수행하는 경우에만 운영
  적합성 확인단계를 추가할 수 있다. 현재 Issue에서 현장검증 Issue는 만들지 않는다.
- Evidence: Issue #126,
  `docs/product/AREA_SPOT_REMOTE_EVIDENCE_READINESS_ASSESSMENT.md`,
  `docs/product/AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md`.
- Supersession: 현장검증 불가, 운영 적합성 미확인과 판매·안전·정차·성과 비보장
  원칙은 유지한다. `데이터 기반 우선 후보`를 현재 PoC의 최대 출력으로 제한하고
  `recommendation_scope=DATA_PRIORITY_ONLY`를 최종 상한으로 둔 부분만 D-020이
  대체한다.

### D-020 — 원격 데이터 기반 SPOT 판매 추천과 운영 적합성 분리

- Date: `2026-07-29`
- Status: `ACCEPTED`
- Product responsibility: Area는 판매기회와 유효 시간대를 탐색·비교하는 구역이고,
  Spot은 Area 안에서 프래시매니저가 실제로 이동해 판매하도록 추천받는 특정
  지점이다. 핵심 출력은 추천 Area·Spot·판매시간과 선택근거다.
- Remote recommendation: 유효한 Area 기회, 같은 Area 안의 비교 가능한 Spot 최소
  2개(파일럿 목표 3~5개), 공식 명칭·위치근거, 후보를 구분할 수 있는 Spot별 동적
  근거 또는 승인된 대리근거, 동일 기준시각·시간범위, 반복성 또는 순위 안정성,
  최신성·결측관리, 사용자 이동·준비 가능시간, 신뢰도와 제한사항을 모두 충족하면
  현장검증 없이도 원격 데이터 기반 `SPOT` 추천이 가능하다.
- Operational boundary: `field_verification_status=UNAVAILABLE`과
  `operational_suitability_status=NOT_VERIFIED`를 유지한다. 원격 추천은 실제 판매
  허용·안전·카트 이동·정차·시설 점유·판매 성공·매출 증가를 보장하지 않는다.
  운영 적합성은 파일럿 사용자 또는 실제 운영기관이 별도로 판단한다.
- Fallback: Spot 근거가 충분하면 `SPOT`, Area 근거만 충분하면 `AREA`와
  `fallback_reason`, Area 근거도 부족하면 Recommendation Output을 생성하지 않는다.
- Existing decisions: D-006의 운영 가능성 필수조건, D-018의 현장·운영 확인
  필수조건과 D-019의 후보 한정 상한을 부분 대체한다. D-006의 SPOT 우선·AREA
  fallback, D-018의 Area·Spot 책임 분리, D-019의 현장검증 불가와 운영 적합성
  미확인 원칙은 유지한다.
- Scope boundary: 이번 결정은 정책·목표 계약 정합화다. 생산 Schema·코드·시험,
  실제 Spot 등록·데이터 수집·추천 실행·UI·Backend·배포를 승인하지 않는다.
- Evidence: Issue #129, Follow-up to PR #127, Blocks #128.

### D-021 — 초기 파일럿 Area 추천과 Spot 선택 지원 범위

- Date: `2026-07-29`
- Status: `ACCEPTED`
- Relationship: D-020의 원격 데이터 기반 SPOT 자동추천은 장기 제품 목표로
  유지한다. D-021은 장기 목표를 취소하지 않고 초기 파일럿 범위만 축소한다.
- Pilot Area: 초기 대상은 PM 검토용 Area 5개이며, Area별 대표 Spot을 정확히
  3개씩 `spot_role=USER_SELECTABLE_OPTION`으로 제공한다.
- Recommendation: 서비스는 서울시 공식 현재·예측 유동인구를 기준으로 Area와
  판매시간만 추천한다.

```text
recommendation_type=AREA
recommendation_basis=SEOUL_OFFICIAL_FORECAST
spot_selection_mode=USER_CHOICE
spot_auto_recommendation=false
```

- Spot boundary: Spot은 시스템 추천대상이 아니다. 사용자가 세 선택지 중 이동할
  지점을 직접 고르며, Spot별 유동인구·밀집도·순위와 자동추천을 제공하지 않는다.
- ML boundary: 기존 비교실험은
  `machine_learning_status=COMPARISON_COMPLETED_NOT_ADOPTED`로 보존하고,
  `machine_learning_used_for_recommendation=false`를 적용한다. 추천 Forecast Source는
  서울시 공식 예측자료다.
- Deferred: Spot 동적근거와 S-DoT 신규 수집·연결, Spot별 예측·자동추천,
  반복성·Backtesting·순위 안정성·추천 신뢰도 임계값은
  `DEFERRED_AFTER_INITIAL_PILOT`이다.
- Operational boundary: 현장검증은 `UNAVAILABLE`, 운영 적합성은
  `NOT_VERIFIED`로 유지한다. Area 예측값을 Spot 직접값으로 표현하지 않는다.
- Scope boundary: 이 결정은 정책·문서 정합화다. 생산 Schema·코드·시험, 실제
  Spot 등록·추천 실행·UI·Backend·배포와 파일럿 실행을 승인하지 않는다.
- Evidence: Issue #128, PR #131.

## 4. 갱신 규칙

새 PM 결정이 기존 결정을 대체하면 이전 항목을 삭제하지 않고 `SUPERSEDED`로 바꾸고
대체 Decision ID를 기록한다. Issue·PR이 존재한다는 사실만으로 승인 상태를 추정하지
않는다.
