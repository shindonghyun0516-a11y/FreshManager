---
name: Parent 작업
about: 여러 Checklist 항목을 담는 FreshManager Workflow v2 Parent Issue를 정의합니다.
title: ""
labels: ""
assignees: ""
---

<!-- 실제 API 키, .env 내용, 인증 URL, 개인정보를 입력하지 마세요. -->

이 템플릿은 `docs/engineering/DEVELOPMENT_WORKFLOW.md`가 정의하는 Parent
Issue용이다. 단일·단독 작업은 이 템플릿 대신 `task.md`를 사용한다.

## 작업 목적

<!-- 이 작업으로 달성할 결과를 작성합니다. -->

## 배경 및 문제

<!-- 해결해야 할 문제를 작성합니다. -->

## 현재 상태

<!-- 확인된 사실과 아직 확인되지 않은 사항을 구분해 작성합니다. -->

## 수정 범위

### 생성 또는 수정 허용 파일

-

### 수정 금지 파일

-

## Checklist

<!-- 사용자·제품·데이터 관점에서 완결된 하위 결과 단위로 작성합니다.
     "세부 계산 하나"보다는 크고 "이 Parent Issue 전체"보다는 작아야
     합니다. -->

- [ ]

## Integration PR 배치 계획

<!-- docs/engineering/DEVELOPMENT_WORKFLOW.md §6 -->

- 예상 Integration PR 수:
- PR별 Checklist 범위:
- Checklist 항목 사이 선행관계(순차 필요 vs 병렬 가능):
- 병렬로 진행할 Worktree 수:
- 각 PR 생성 시점:
- PR 하나의 최대 변경 범위:

## Worktree 사용 여부

- [ ] 필요(병렬 구현)
- [ ] 불필요(순차 진행)

## 외부 실행이 필요한 항목

<!-- 없으면 "없음"으로 기록합니다. 실행 직전 별도 PM 승인이 항상
     필요하며, 이 표시가 그 승인을 대신하지 않습니다
     (DEVELOPMENT_WORKFLOW.md §13). -->

-

## 고위험 변경 항목

<!-- Dataset Schema·공통 데이터 계약·Feature·Label·시간순 분할·평가
     공식·Ranking 공식·Recommendation Contract·Project Guard 자체 변경
     중 해당하는 Checklist 항목을 표시합니다. 없으면 "없음". -->

-

## WARN·SKIP 예상 항목

<!-- 이 배치에서 미리 예상되는 Project Guard WARN·SKIP이 있다면 기록합니다.
     여기 기록되지 않은 새 WARN·SKIP은 DEVELOPMENT_WORKFLOW.md §11에 따라
     기본적으로 병합을 차단합니다. 없으면 "없음". -->

-

## 완료조건

- [ ]

## 제외범위

-

## 선행조건

- 기준 Branch와 커밋:
- Integration Branch:
- 현재 품질 게이트와 이전 게이트 상태:
- 필요한 선행 작업:

## 검증계획

- 적용 검사 ID 또는 해당 없음 사유:
- 실행할 검증 명령:
- Project Guard 검사 또는 문서 수동검증 방법:

## PM 결정사항

- 구현계획 승인 여부(Gate 1):
- 실제 API 호출 허용 여부:
- 패키지 설치 허용 여부:
- 추가 승인 필요사항:

PM의 Gate 1 승인 전에는 파일을 생성·수정·삭제하거나 구현을 시작하지 않는다.
작업 범위가 변경되면 변경 이유, 변경 범위와 PM 승인 이력을 이 Issue에 기록한다.

## PROJECT_STATUS 예상 영향

다음 중 하나만 선택한다.

- [ ] 있음
- [ ] 없음
- [ ] 작업 완료 후 판정 필요

영향 예상 항목:

- 현재 단계
- Engineering Gate 또는 Codex Engineering Harness 단계
- 공식 경로·명령·Workflow
- 다음 행동
- 위험·제약
- 외부 실행 승인 상태

## 관련 문서

-

## 남은 위험

-

## 종료 전 PROJECT_STATUS 최종 판정

다음 중 하나만 선택한다.

- [ ] 갱신 필요
- [ ] 갱신 불필요
- [ ] 별도 상태 갱신 Issue 필요

판정 근거:

처리 파일 또는 후속 Issue:

## Worker 완료 기록

<!-- Checklist 항목이 끝날 때마다 docs/engineering/DEVELOPMENT_WORKFLOW.md
     §8 형식으로 아래에 코멘트를 추가합니다(이 섹션 자체는 안내용이며
     실제 기록은 Issue 코멘트로 남깁니다). -->

## 작업 체크리스트

- [ ] 관련 기준 문서를 확인했다.
- [ ] 현재 Branch와 Git 상태를 확인했다.
- [ ] 읽기 전용 구현계획을 보고했다.
- [ ] PM의 Gate 1 승인을 Issue에 기록했다.
- [ ] 승인된 파일과 범위만 변경했다.
- [ ] 계획한 검증을 수행하고 결과를 기록했다.
- [ ] 실행하지 못한 검사는 사유를 기록했다.
- [ ] 실제 키, `.env` 내용, 인증 URL과 개인정보가 포함되지 않았음을 확인했다.
- [ ] 범위 변경이 있다면 PM 승인 이력을 기록했다.
