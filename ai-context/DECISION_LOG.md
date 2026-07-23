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
- Status: `ACCEPTED`
- Decision: 신뢰 가능하고 운영 가능한 Spot이 있으면 `target_level=SPOT`, 없으면 `target_level=AREA`와 `fallback_reason`을 사용한다.
- Consequence: Area fallback은 실패가 아니라 Spot 근거 부족을 명시하는 정상 결과다.

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
- Related: [[D-015]] — EG-8 상위 Gate·EG-8A~8E 세분화(D-015는 이 결정을 대체하지
  않으며, EG-8E는 Recommendation MVP의 구현 Gate가 아니다).

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

## 4. 갱신 규칙

새 PM 결정이 기존 결정을 대체하면 이전 항목을 삭제하지 않고 `SUPERSEDED`로 바꾸고
대체 Decision ID를 기록한다. Issue·PR이 존재한다는 사실만으로 승인 상태를 추정하지
않는다.
