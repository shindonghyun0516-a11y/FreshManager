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

## 4. 갱신 규칙

새 PM 결정이 기존 결정을 대체하면 이전 항목을 삭제하지 않고 `SUPERSEDED`로 바꾸고
대체 Decision ID를 기록한다. Issue·PR이 존재한다는 사실만으로 승인 상태를 추정하지
않는다.
