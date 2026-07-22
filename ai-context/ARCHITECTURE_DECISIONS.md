# FreshManager Architecture Decisions

## 1. 문서 역할

이 문서는 FreshManager의 기술 구조 결정, 검토한 대안과 영향을 ADR(Architecture
Decision Record, 기술 구조 결정 기록) 형식으로 보존한다. 현행 구현은
[`FreshManager_TRD_v1.0.md`](../docs/engineering/FreshManager_TRD_v1.0.md)와 `main`
코드가 기준이며, 현재 상태는 [`PROJECT_STATUS.md`](../PROJECT_STATUS.md)를 따른다.

## ADR-001 — Area Collector를 Core Observation 수집기로 유지

- Status: `ACCEPTED`
- Context: 서울시 실시간 도시데이터는 공식 Area 단위로 요청하며 Spot·S-DoT 근거와 무관하게 Area 관측을 제공한다.
- Decision: EG-6B Collector는 승인된 13개 Area의 Raw·Metadata·Forecast·Batch 증거만 수집한다.
- Alternatives: Spot 좌표를 요청값으로 사용, S-DoT 성공을 Area 요청의 선행조건으로 사용.
- Consequences: 한 Area당 최대 1회, 순차 처리, 실패 격리와 원본 보존 계약을 유지한다.
- Validation: `freshmanager/eg6b.py`, `tests/test_eg6b.py`, H-706.
- Related decision: D-001, D-003.

## ADR-002 — S-DoT Collector를 Area Collector와 분리

- Status: `PLANNED`
- Context: S-DoT는 지원 범위·접근 방식·스키마·갱신주기·품질이 Area API와 다르다.
- Decision: S-DoT 접근성·스키마·품질 검증과 향후 Collector는 독립 Issue·실행·저장·테스트 경계로 관리한다.
- Alternatives: EG-6B Area Collector에 S-DoT 요청을 결합.
- Consequences: S-DoT 실패는 Area Batch를 실패시키거나 서울시 Area API 재호출을 유발하지 않는다.
- Validation: EG-7에서 접근성·스키마·품질 계약을 먼저 검증한다.
- Related decision: D-005.

## ADR-003 — Area와 S-DoT를 병렬·독립 입력으로 결합

- Status: `ACCEPTED`
- Context: S-DoT는 13개 Area 모두에서 사용할 수 있는 필수 데이터가 아니다.
- Decision: Area Feature는 필수 입력, 품질조건을 통과한 S-DoT Feature는 선택 입력으로 Spot Candidate Evaluation에 결합한다.
- Alternatives: S-DoT를 모든 Area의 필수 다음 단계로 두는 직렬 파이프라인.
- Consequences: S-DoT 미지원 6개 Area도 Area 분석과 추천 후보에 남으며, 결측을 0이나 실패로 바꾸지 않는다.
- Validation: 분석 시 S-DoT 사용 여부·출처·품질 근거를 별도로 기록한다.
- Related decision: D-003, D-005.

## ADR-004 — Spot Candidate Evaluation을 근거 평가로 정의

- Status: `ACCEPTED`
- Context: 현장 검증 전 Spot Master는 역 중심 대리 Anchor이며 정량 점수의 타당성도 아직 확인되지 않았다.
- Decision: Area Feature, 선택적 S-DoT Feature, Spatial Context, Field Validation과 Operational Constraints를 Candidate Evidence Assessment로 결합한다.
- Alternatives: 고정 Spot 목록, 필수 단일 Candidate Score.
- Consequences: Score·가중치·임계값은 `PLANNED` 또는 `OPEN_DECISION`; 현재 필수 저장계약이 아니다.
- Validation: EG-8에서 근거 재현성·한계·버전을 검토한다.
- Related decision: D-004, D-009.

## ADR-005 — Recommendation Level은 SPOT 우선·AREA fallback

- Status: `PLANNED`
- Context: 후보 근거가 충분한 Area와 그렇지 않은 Area를 같은 해상도로 추천하면 과도한 정밀도 주장이 된다.
- Decision: 신뢰 가능하고 운영 가능한 Spot은 `target_level=SPOT`, 없으면 `target_level=AREA`와 `fallback_reason`을 반환한다.
- Alternatives: 모든 추천을 AREA 또는 모든 추천을 SPOT으로 고정.
- Consequences: 추천 근거와 fallback 사유를 추적하고 Area 값을 Spot 직접 유동인구로 표현하지 않는다.
- Validation: Recommendation MVP Workstream은 Gate number `NOT_ASSIGNED`이며 별도 PM 승인 후 검증한다.
- Related decision: D-006, D-008.

## ADR-006 — Backup Worker를 Collector와 분리

- Status: `ACCEPTED`
- Context: 백업 장애가 수집 호출량과 원본 보존에 영향을 주면 API 재호출·중복 위험이 생긴다.
- Decision: 완료 Batch만 처리하는 1회 실행형 Worker를 Batch 완료 직후 호출하고,
  Google Drive for Desktop Sync의 `FreshManager-Data/` 논리 루트에 검증 복사본을 게시한다.
- Alternatives: Collector 내부 복사, Google Drive API/OAuth/SDK 직접 연동, 수동 복사.
- Consequences: 백업 실패로 API를 재호출하지 않고, `.env`·Secret·임시파일을 제외하며,
  Manifest SHA-256과 충돌을 검증한다. 실제 계정 이메일과 동기화 절대경로는 기록하지
  않는다. Worker는 `LOCAL_SYNC_COPY_VERIFIED`까지만 생성하고 원격 완료 상태는 생성하지 않는다.
- Validation: Issue #60 Branch의 Fake 성공·부분 실패·중복·충돌·잠금·Fake Restore와
  H-708로 검증했다. `main` 병합·실제 Sync Root·실제 Batch·원격 완료 확인은 남아 있다.
- Related decision: D-007, D-010.

## ADR-007 — Raw 원본과 CSV 파생자료를 분리

- Status: `PLANNED`
- Context: Raw는 재현·감사 근거이고 CSV는 조회·정렬·분석 편의를 위한 다른 책임이다.
- Decision: Raw JSON·Metadata·Collection Log·Manifest를 공식 원본으로 보존하고 CSV는 첫 실제 Batch 품질 감사 후 별도 Exporter로 생성한다.
- Alternatives: API 응답을 즉시 CSV로 변환해 Raw 대신 보존, CSV 실패 시 재수집.
- Consequences: CSV는 Raw에서 재생성하며 실패해도 API를 재호출하지 않는다. Area 관측과 Spot Context를 같은 측정값으로 합치지 않는다.
- Validation: 파일 수·키·시간 의미·결측·재생성 일치성을 별도 테스트한다.
- Related decision: D-011.

## 2. ADR 갱신 규칙

결정이 바뀌면 기존 ADR을 삭제하지 않고 상태를 `SUPERSEDED`로 바꾸며 대체 ADR을
연결한다. 계획 구조를 구현 완료로 표현하지 않고, PM 승인·코드·테스트·실제 실행
증거를 각각 구분한다.
