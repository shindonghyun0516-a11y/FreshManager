# FreshManager Documentation Index

이 문서는 FreshManager의 현행 문서와 역사 문서를 역할별로 구분하는 탐색용 색인이다.
현재 상태는 [`PROJECT_STATUS.md`](../PROJECT_STATUS.md), 작업·승인 규칙은
[`AGENTS.md`](../AGENTS.md), 저장소 소개는 [`README.md`](../README.md)를 따른다.
[`PROJECT_MEMORY.md`](../ai-context/PROJECT_MEMORY.md)는 장기 맥락 복원 자료이며
현재 상태나 아래 정본을 대체하지 않는다.

## Current Product

- [`FreshManager_PRD_v1.0.md`](product/FreshManager_PRD_v1.0.md) — 제품 문제,
  사용자, 범위, 요구사항과 수용 기준의 공식 제품 정본이다.
- [`AREA_FIRST_WEB_PILOT_CONTRACT.md`](product/AREA_FIRST_WEB_PILOT_CONTRACT.md) —
  초기 Area-first 웹 파일럿의 사용자 흐름, UI 상태와 데이터 표시 경계를 소유한다.
- [`AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md`](product/AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md) —
  Area·Spot의 책임 구분, 추천 표현 상한과 지도 UI 정책을 정의한다.
- [`RECOMMENDATION_OUTPUT_CONTRACT.md`](product/RECOMMENDATION_OUTPUT_CONTRACT.md) —
  추천 결과의 필드, `null`, fallback과 Eligibility 계약을 정의한다.
- [`EG6_AREA_SPOT_PANEL.md`](product/EG6_AREA_SPOT_PANEL.md) — 승인된 13개 Area,
  정적 Spot Anchor와 선택적 S-DoT 연결 및 해석 한계를 정의한다.
- [`DECISION_LOG.md`](../ai-context/DECISION_LOG.md) — 승인·대체·제안 상태를 구분한
  제품·운영 결정 이력을 보존한다.

## Design

- [`DESIGN.md`](design/DESIGN.md) — Stitch·Figma·Codex·Frontend가 공유할
  지도 중심 UI/UX 설계 기준을 정의한다.

## Architecture

- [`AREA_FIRST_WEB_API_ARCHITECTURE.md`](architecture/AREA_FIRST_WEB_API_ARCHITECTURE.md) —
  Area-first Web/API 경계, Dependency 방향과 읽기 전용 데이터 공급 계약을 정의한다.
- [`CODEX_HARNESS_ARCHITECTURE.md`](architecture/CODEX_HARNESS_ARCHITECTURE.md) —
  Harness 계층, 문서 소유권, 검증·승인과 피드백 구조를 정의한다.
- [`REPOSITORY_READINESS_AUDIT.md`](architecture/REPOSITORY_READINESS_AUDIT.md) —
  구현 전 Repository 자산 분류와 정리 판단의 승인된 Audit 근거를 보존한다.
- [`ARCHITECTURE_DECISIONS.md`](../ai-context/ARCHITECTURE_DECISIONS.md) —
  기술·데이터 Architecture 결정과 대안·영향 이력을 보존한다.

## Data

- [`CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md`](data/CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md) —
  Google Drive Backup·Restore와 CSV 후속 도입 계약을 정의한다.
- [`DATA_COLLECTION_EXECUTION_GUIDE.md`](data/DATA_COLLECTION_EXECUTION_GUIDE.md) —
  비개발자가 Apps Script와 로컬 Python 수집 경로를 구분해 실행하도록 안내한다.
- [`FIELD_DICTIONARY.md`](data/FIELD_DICTIONARY.md) — 원본·정규화·메타데이터와
  파생 필드의 의미를 정의한다.
- [`MANUAL_V3_SNAPSHOT_INTAKE.md`](data/MANUAL_V3_SNAPSHOT_INTAKE.md) — 수동 v3 CSV
  반입·검증과 불변 Snapshot 공개 계약을 정의한다.
- [`ML_READY_DATASET_SPEC.md`](data/ML_READY_DATASET_SPEC.md) — EG-8A~EG-8C의
  Feature·Label·Split·Manifest와 공개 Dataset 계약을 정의한다.

## Engineering

- [`FreshManager_TRD_v1.0.md`](engineering/FreshManager_TRD_v1.0.md) — PRD를 현재·
  목표 기술 구조, Interface, 데이터, 보안과 검증 계약으로 변환한 공식 기술 정본이다.
- [`DEVELOPMENT_WORKFLOW.md`](engineering/DEVELOPMENT_WORKFLOW.md) — Parent Issue,
  Worktree 병렬 작업과 통합 절차를 정의한다.

## Rules

- [`CODING_RULES.md`](rules/CODING_RULES.md) — 코드 구조, 오류 처리, 저장과 시험 작성 규칙이다.
- [`DATA_COLLECTION_RULES.md`](rules/DATA_COLLECTION_RULES.md) — 데이터 수집,
  원본 보존, 결측과 반복주기 규칙이다.
- [`GIT_WORKFLOW.md`](rules/GIT_WORKFLOW.md) — Issue·Branch·Commit·PR·Review·Merge 규칙이다.
- [`ML_EXPERIMENT_RULES.md`](rules/ML_EXPERIMENT_RULES.md) — Dataset Lock 이후
  Offline ML Experiment의 공통 불변 규칙이다.
- [`SECURITY_RULES.md`](rules/SECURITY_RULES.md) — Secret·경로·로그·GitHub와
  외부 공유 보안 규칙이다.

## Testing

- [`PROJECT_GUARD_SPEC.md`](testing/PROJECT_GUARD_SPEC.md) — Project Guard 검사 ID,
  판정과 종료코드의 유일한 정본이다.
- [`PROJECT_GUARD_REPORT_TEMPLATE.md`](testing/PROJECT_GUARD_REPORT_TEMPLATE.md) —
  Guard 결과와 PM 확인사항의 보고 형식이다.
- [`QUALITY_GATES.md`](testing/QUALITY_GATES.md) — EG 진입·통과와 다음 단계 승인 조건을 정의한다.

## Analysis

- [`ANALYSIS_PLAN.md`](analysis/ANALYSIS_PLAN.md) — 분석 질문, 방법론, Baseline,
  평가와 Gate 판정 계획을 정의한다.
- [`GATE_C_INTERVIEW_PLAN.md`](analysis/GATE_C_INTERVIEW_PLAN.md) — 실제 사용자 문제를
  검증하기 위한 인터뷰 설계이며, Git에 추적된 실제 인터뷰 Evidence 자체는 아니다.
- [`GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md`](analysis/GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md) —
  공개자료 기반 합성 응답·코딩체계 자료이며 실제 인터뷰, 직접 인용 또는 Gate C
  통과 근거가 아니다.

## History

아래 문서는 삭제하지 않고 의사결정·실험·분석 이력을 재현하기 위해 보존한다.
현재 제품·Architecture·상태 정본이나 현행 실행 지시로 사용하지 않는다.

- [`requirements-definition-freshmanager-poc-v0.4.md`](history/requirements/requirements-definition-freshmanager-poc-v0.4.md) —
  PRD 이전 요구사항 기준선이다.
- [`EG5_DATA_ANALYSIS_REPORT.md`](history/analysis/EG5_DATA_ANALYSIS_REPORT.md) —
  EG-5 대표 3개 Area 실제수집 단면 분석 증거다.
- [`AREA_SPOT_REMOTE_EVIDENCE_READINESS_ASSESSMENT.md`](history/research/AREA_SPOT_REMOTE_EVIDENCE_READINESS_ASSESSMENT.md) —
  Issue #126 당시 원격 Spot 근거 준비도 조사다.
- [`PILOT_AREA_SELECTION_ASSESSMENT.md`](history/research/PILOT_AREA_SELECTION_ASSESSMENT.md) —
  D-021 파일럿 5개 Area 선정 조사다.
- [`2026-07-27-eg8c-ml-modeling.md`](history/plans/2026-07-27-eg8c-ml-modeling.md) —
  후속 결정으로 대체된 EG-8C Modeling 실행계획이다.
