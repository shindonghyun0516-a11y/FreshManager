<!-- 실제 API 키, .env 내용, 인증 URL, 개인정보를 입력하지 마세요. -->

## 연결 Issue

<!-- 필수: Closes #이슈번호(Parent Issue의 Checklist가 이 PR로 전부
     끝나는 경우) 또는 Part of #이슈번호(배치 중 일부만 담당하는 경우)
     형식으로 연결합니다. -->

Closes #

## Integration PR 여부

<!-- docs/engineering/DEVELOPMENT_WORKFLOW.md v2 Parent Issue/Integration
     PR 흐름이면 체크합니다. 단독 Issue/PR(v1)이면 체크하지 않습니다. -->

- [ ] Integration PR(Parent Issue의 Checklist 배치를 담당)
- [ ] 단독 PR

### 포함된 Parent Checklist

<!-- Integration PR인 경우에만 작성합니다. 각 항목은 Parent Issue의
     Worker 완료 코멘트(DEVELOPMENT_WORKFLOW.md §8)를 링크합니다.
     단독 PR이면 "해당 없음"으로 기록합니다. -->

-

## 작업 목적

<!-- 연결 Issue에서 승인된 작업 목적을 작성합니다. -->

## 변경 파일

| 파일 | 변경 내용 |
|---|---|
|  |  |

## 주요 변경사항

-

## 검증 결과

CI 결과를 공식 증거로 인용한다. 로컬 실행 결과는 CI가 다루지 않는
항목(실제 외부 실행, 실 Dataset Smoke 등)만 기록한다
(`docs/engineering/DEVELOPMENT_WORKFLOW.md` §9).

### GitHub Actions CI

- 상태(PASS/FAIL):
- 링크:
- FAIL인 경우 원인 요약:

### CI가 다루지 않는 검증

<!-- 실제 외부 실행, 실 Dataset Smoke 등. 없으면 "해당 없음". -->

| 검사 또는 명령 | 결과 |
|---|---|
|  |  |

### 실행하지 못한 검사

| 검사 | 사유 | 영향 |
|---|---|---|
|  |  |  |

- Project Guard 결과 또는 미실행 사유:
- Codex 리뷰 결과:

### WARN·SKIP 분류

<!-- docs/engineering/DEVELOPMENT_WORKFLOW.md §11·§12. 각 WARN·SKIP을
     "비차단"(현재 PR 범위와 무관 AND Gate 1에서 사전에 예상됨)과
     "차단"(그 외 전부, PM 확인 전 병합하지 않음)으로 분류합니다.
     없으면 "해당 없음". -->

| 검사 ID | 상태 | 분류(차단/비차단) | 근거 |
|---|---|---|---|
|  |  |  |  |

## 보안 확인

- [ ] 실제 API 키가 포함되지 않았다.
- [ ] `.env` 파일이나 그 내용이 포함되지 않았다.
- [ ] 인증정보가 포함된 URL이나 로그가 없다.
- [ ] 개인정보와 제한된 원본 데이터가 포함되지 않았다.
- [ ] 새 Secret 또는 외부 공유 항목이 있다면 PM 승인을 기록했다.

## 범위 외 작업

<!-- 없으면 "없음"으로 기록합니다. -->

-

## 남은 위험 및 WARN

<!-- 없으면 "없음"으로 기록합니다. -->

-

## 다음 게이트 진입 가능 여부

- 현재 게이트:
- 다음 게이트 진입 가능 여부와 근거:

## PM 확인사항

<!-- PM이 직접 확인·승인해야 할 내용만 구분해 짧게 기록합니다.
     없으면 "없음". -->

-

## PROJECT_STATUS 영향 판정

다음 중 하나만 선택한다.

- [ ] 영향 있음
- [ ] 영향 없음

판정 근거:

처리 방식:

다음 중 하나만 선택한다.

- [ ] 현재 PR에 반영
- [ ] Merge 후 별도 상태 갱신 Issue 필요
- [ ] 갱신 불필요

PM 최종 상태 판단:

- [ ] 완료
- [ ] 대기

## PM 최종 검토

- [ ] 연결 Issue와 변경 범위가 일치한다.
- [ ] 완료조건과 검증 결과를 확인했다.
- [ ] 범위 외 작업과 남은 위험을 확인했다.
- [ ] 보안 확인 항목을 검토했다.
- [ ] PROJECT_STATUS 영향 판정과 처리 방식을 검토했다.
- [ ] PM이 `main` Merge를 최종 승인했다.

## Merge 방식

기본 Merge 방식은 `Squash and merge`다.

- [ ] 연결 Issue가 존재하고 완료조건을 충족했다.
- [ ] 적용 대상 검증이 통과했거나 미실행 사유와 영향을 검토했다.
- [ ] 보안 위반과 승인되지 않은 범위 변경이 없다.
- [ ] PM 최종 Merge 승인을 받았다.
