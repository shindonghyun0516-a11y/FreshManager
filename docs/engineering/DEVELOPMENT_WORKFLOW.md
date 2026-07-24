# Development Workflow v2 — Heavy Engineering·Lean Git Operations

- 문서 상태: 정본(Canonical)
- 적용 프로젝트: FreshManager Data PoC
- 관련 문서: `AGENTS.md`, `docs/engineering/CODEX_HARNESS_ARCHITECTURE.md`,
  `docs/rules/GIT_WORKFLOW.md`, `docs/testing/QUALITY_GATES.md`,
  `docs/testing/PROJECT_GUARD_SPEC.md`, `.github/ISSUE_TEMPLATE/task.md`,
  `.github/ISSUE_TEMPLATE/parent_task.md`, `.github/pull_request_template.md`
- 변경 시 PM 승인: 필요

---

## 1. 목적과 적용 범위

이 문서는 FreshManager의 Issue·Branch·Worktree·Pull Request·검증 실행·
Merge·보고를 다루는 실무 절차의 v2("Heavy Engineering·Lean Git
Operations")를 정의한다. 목적은 다음 다섯 가지다.

1. 작은 작업마다 Issue·PR을 반복하는 행정비용 축소
2. 동일 검증의 불필요한 반복 제거
3. Worktree 병렬 구현과 Integration PR 도입
4. GitHub Actions CI를 공식 전체 검증 Gate로 사용
5. PM 승인 Gate를 명확한 두 단계(범위 승인·Merge 승인)로 단순화

이 문서가 바꾸지 않는 것: 기능 범위(실제 데이터 수집~UI/UX), 품질
기준(단위·통합·회귀·실데이터 검증), Project Guard·Unit Tests·CI가
요구하는 통과 기준, PM의 최종 승인권. `docs/testing/QUALITY_GATES.md`가
소유하는 EG-0~EG-8 각 단계의 진입·통과조건(기능 완료조건)도 바꾸지
않는다 — 이 문서가 바꾸는 것은 그 조건을 확인하는 절차의 단위(Issue/PR
포장)와 반복 빈도뿐이다.

적용 범위: EG-8B B2b 및 그 이후 착수하는 모든 Parent Issue(EG-8C·
EG-8D·EG-8E·UI 등, §18 참조). 이미 진행 중인 EG-8B B2a(Issue #89)에는
소급 적용하지 않는다(§17). 단순 문서 1~2개 수정이나 작은 단독 수정은
이 문서의 Parent Issue 구조를 강제하지 않고 기존 `docs/rules/
GIT_WORKFLOW.md`의 단독 Issue/PR 절차를 그대로 사용해도 된다.

---

## 2. 절대 불변 원칙

이 Workflow 개편은 다음을 약화하지 않는다.

1. **모든 `main` Merge는 PM의 명시적 승인이 매번 필요하다.** Integration
   PR이든 단독 PR이든 예외가 없다. 여러 체크리스트 항목을 하나의
   Integration PR로 묶는 것은 승인 "횟수"를 줄이는 것이지 승인 "요건"을
   없애는 것이 아니다.
2. **실제 외부 실행(서울시 API 호출 등)은 실행 직전 PM의 명시적 승인이
   매번 필요하다.** Gate 1에서 외부 실행이 필요한 항목이 있다고 미리
   알리는 것과, 그 항목을 실제로 실행해도 좋다는 승인은 서로 다른 별개의
   확인이며 하나가 다른 하나를 대신하지 않는다.
3. **`AGENTS.md` §6의 승인 대상 목록**(실제 API 호출·패키지 설치·기준파일
   변경·데이터 저장구조 변경·호출주기 결정·자동실행 구성·`main` 병합
   등)은 그대로 유지한다.
4. **Project Guard `FAIL=0`·전체 테스트 통과·필요한 실 Dataset 검증
   수준은 축소하지 않는다.** 축소 대상은 "몇 번 반복해서 보여주는가"이지
   "검증 자체를 하는가"가 아니다.
5. **Repository Safety**: `git add .`/`-A`, `git push --force*`, `git
   reset --hard`, `git branch -D` 등 `docs/rules/GIT_WORKFLOW.md` §17·
   `.claude/settings.json`의 금지 명령 목록은 그대로 유지한다.
6. **보호 경로**(`.gitignore`·`.claude/`·`CLAUDE.md`·구 작업일지 경로 등)
   규칙은 그대로 유지한다.
7. **기능·테스트·품질 Gate는 축소하지 않는다.** 이 문서는 포장을 줄일
   뿐 검증 내용을 줄이지 않는다.

---

## 3. 용어

| 용어 | 정의 |
|---|---|
| Parent Issue | 사용자·제품·데이터 관점에서 하나의 완결된 결과를 만드는 작업 단위. 여러 Checklist Item을 체크박스로 담는다(예: EG-8C). |
| Checklist Item | Parent Issue 안의 하위 결과 단위. "세부 계산 하나"보다 크고 "EG 전체"보다 작은, 그 자체로 검증 가능한 산출물 단위. |
| Integration Branch | Parent Issue 전체를 대표하는 작업 Branch. Worker Branch들이 최종적으로 합류하는 지점이며, `main`을 겨냥한 Integration PR의 Compare Branch가 된다. |
| Worker Branch | Checklist Item 하나를 구현하는 개별 Branch. Integration Branch에서 분기하고, 완료되면 Integration Branch로 로컬 merge된다. 그 자체로 `main`을 겨냥한 PR을 만들지 않는다. |
| Worktree | Worker Branch를 별도 실제 폴더에 펼쳐 물리적으로 격리하는 선택적 방식(`docs/rules/GIT_WORKFLOW.md` §7의 기존 정의 그대로). |
| Integration PR | Integration Branch → `main`을 향한 Pull Request. CI와 PM Merge 승인이 발생하는 유일한 지점. |
| Fast-check | Worker 개발 중 실행하는 변경 모듈 테스트 + 관련 정적·형식 검사. |
| Targeted Check | Worker Branch를 Integration Branch로 합류시키기 전 실행하는, 그 변경과 직접 연관된 모듈·Integration Test. |
| Integration·Regression Check | Checklist Item 배치가 Integration Branch에 모인 후 실행하는, 그 배치가 건드린 영역 중심의 통합·회귀 테스트. |
| Full-check | Project Guard 전체(`scripts/project_guard_check.py`) + 전체 테스트 전체(`unittest discover`) + Repository Safety(보호 경로·git status 위생) + 필요한 실 Dataset Smoke 1회. |

---

## 4. Gate 1 — 범위 승인

Parent Issue 시작 전 PM이 1회 승인한다. 다음을 모두 담아 승인받는다.

- 목적·완료조건·허용 파일·제외범위(`.github/ISSUE_TEMPLATE/
  parent_task.md` 필수 항목 그대로)
- Checklist 전체(§5)
- 외부 실행이 필요한 항목이 있는지 여부(있다면 그 항목을 명시 — 단,
  실제 실행 승인은 §13대로 실행 직전 별도로 받는다)
- **예상 Integration PR 수와 PR별 Checklist 배치**(§6)

Gate 1 승인 후에는 Worker Branch → Integration Branch 합류 사이에 별도
PM 승인 라운드를 두지 않는다. 계획에 없던 범위 이탈이 발견되면
`docs/rules/GIT_WORKFLOW.md` §5.3 형식(새로 발견한 문제·기존 범위에
미치는 영향·선택 가능한 처리방법·권장안·Child Issue 분리 필요 여부·PM
승인 필요사항)으로 즉시 보고한다.

---

## 5. Parent Issue·Checklist 작성 규칙

Parent Issue는 `.github/ISSUE_TEMPLATE/parent_task.md`를 사용하며 기존
`task.md`의 필수 계약(목적·배경·현재상태·범위·제외범위·허용파일·금지파일·
완료조건·검사ID·검증명령·API호출여부·패키지설치여부·PM승인사항·남은위험)을
전부 포함한 위에 Checklist와 §6의 PR 배치 계획을 더한다.

Checklist Item은 원칙적으로 **별도 GitHub Issue를 만들지 않는다** —
Parent Issue 본문의 `- [ ]` 항목과 §8의 Worker 완료 코멘트로 추적한다.
Child Issue는 다음에만 예외적으로 분리한다(자동 생성 아님, 필요성이
확인되면 그때 보고 후 PM 승인).

- 독립적으로 장기간 추적할 필요가 있음
- 별도 중단·재개가 필요함
- Parent 범위에서 분리해야 할 만큼 위험·증거가 큼
- PM이 명시적으로 독립 추적을 요청함

**외부 실행이 필요하다는 사실만으로는 Child Issue를 자동 생성하지
않는다** — §13대로 실행 직전 별도 승인만 받고, 추적은 기본적으로 Parent
Issue Checklist 안에서 계속한다.

---

## 6. Integration PR 배치 계획 규칙

Gate 1에서 다음을 함께 확정한다.

- 예상 Integration PR 수
- PR별 Checklist 범위
- Checklist Item 사이의 선행관계(순차 필요 vs 병렬 가능)
- 병렬로 진행할 Worktree 수
- 각 PR을 생성하는 시점(예: 특정 Checklist 배치가 끝났을 때)
- PR 하나의 최대 변경 범위(리뷰 가능한 크기를 넘지 않도록)

**Parent Issue 하나가 반드시 Integration PR 하나를 의미하지 않는다.**
실제 진행 중 배치 구성이 바뀌면(항목 재배치, 통합·분할) 그 사실과 이유를
Parent Issue에 기록하고 계속 진행한다 — 범위 자체가 아니라 배치 방식만
바뀌는 경우 새 Gate 1 승인 왕복을 요구하지 않는다.

---

## 7. Worker Branch·Worktree 사용 기준

```text
Parent Issue 범위 승인(Gate 1, PR 배치 계획 포함)
→ Integration Branch 생성
→ Checklist Item별 Worker Branch(Integration Branch에서 분기, 필요하면 Worktree로 격리)
→ Worker 구현 + Fast-check
→ Integration Branch 합류 직전 Targeted Check
→ Worker Branch를 Integration Branch로 로컬 merge(개별 PR 아님)
→ Parent Issue 체크박스 갱신 + Worker 완료 코멘트(§8)
```

- Worktree 이름(제안): `../freshmanager-worktrees/{parent-issue-slug}-{item-slug}`,
  Branch 이름: `{integration-branch-name}/{item-slug}`.
- Checklist Item이 1~2개뿐이거나 순차 진행이 자연스러우면 Worktree 없이
  Integration Branch에서 바로 순차 구현해도 된다(`docs/rules/
  GIT_WORKFLOW.md` §7 "모든 Issue에 Worktree를 요구하지 않는다" 원칙
  그대로).
- Worktree 안에서도 `AGENTS.md`와 관련 규칙을 그대로 적용한다.

---

## 8. Worker 완료 추적 형식

Checklist Item(Worker) 하나가 끝나면 Parent Issue에 다음을 짧게 기록한다.

```markdown
- [x] {Checklist Item명}
  - Worker Branch: `{branch-name}`
  - Base SHA: `{Integration Branch가 분기된 시점 SHA}`
  - Worker Commit SHA: `{Worker Branch 최종 commit}`
  - 변경 파일: {경로 목록}
  - Fast·Targeted Check: `{실행한 검증 명령}` — 결과
  - Integration Branch 반영 Commit: `{Integration Branch로 merge된 commit}`
```

Worker별로 `main`을 겨냥한 PR은 기본적으로 만들지 않는다.

---

## 9. 검증 정책

| 시점 | 검사 |
|---|---|
| Worker 개발 중 | Fast-check |
| Integration 합류 전 | Targeted Check |
| Checklist 배치 완료 후 | Integration·Regression Check |
| Integration PR 생성 직전 | Full-check 1회 |
| Integration PR | GitHub Actions CI — 공식 전체 검증 증거 |

**Checklist Item마다 Project Guard 전체와 전체 테스트 전체를 반복하지
않는다.** 대신 다음 고위험 변경은 Checklist Item 완료 시점에도 즉시
Full-check를 추가로 허용한다(요구하되 매번 강제하지는 않음 — 변경
성격상 필요하다고 판단되면 PR 직전까지 미루지 않는다는 뜻).

- Dataset Schema 변경
- 공통 데이터 계약(EG-8A/B1 Output 스키마 등) 변경
- Feature·Label 정의 변경
- 시간순 분할(Data Leakage 방지) 로직 변경
- 평가 공식(MAE/RMSE/상대오차/구간포함률/혼잡도일치율 등) 변경
- Ranking 공식 변경
- Recommendation Contract 변경
- Project Guard 자체 변경

Integration PR 본문과 최종 보고에는 CI 링크·상태(PASS/FAIL)를 공식
증거로 인용하고, CI가 다루지 못하는 검증(실제 외부 실행, 실 Dataset
Smoke 등)만 별도로 요약한다. CI가 실패하면 실패한 Step과 로그를 상세히
인용한다(`docs/rules/GIT_WORKFLOW.md` §18.5 그대로).

---

## 10. Integration PR 규칙

- 방향: `base: main`, `compare: Integration Branch`(`docs/rules/
  GIT_WORKFLOW.md` §13.1과 동일).
- 제목 형식: `[Parent Issue 유형] Integration: <이번 배치 요약>`.
- `.github/pull_request_template.md`의 기존 12개 필수 항목(연결 Issue·
  작업 목적·변경 파일·파일별 변경사항·검증 명령·Project Guard 결과·
  Unit Tests 결과·Codex 리뷰 결과·범위 외 변경·PM 확인사항·남은 위험·
  다음 게이트 진입 가능 여부)에 다음을 더한다.
  - 포함된 Parent Checklist 항목 목록(§8 Worker 완료 코멘트 링크)
  - CI 링크·상태(공식 증거로 인용)
  - WARN·SKIP 분류(§11·§12)
- `Closes #{Parent Issue 번호}`로 연결한다 — 단, Parent Issue의 Checklist
  가 아직 남아 있다면(이 PR이 배치 중 일부만 담당) `Closes` 대신
  `Part of #{Parent Issue 번호}`를 쓰고 마지막 배치 PR에서만 `Closes`를
  사용한다.
- CI는 기존 `.github/workflows/ci.yml`의 `pull_request` Trigger를 그대로
  사용한다(신규 Trigger 불필요 — 모든 PR에 이미 적용됨).

---

## 11. WARN·SKIP 판단 규칙

Project Guard는 이미 PASS·FAIL·WARN·SKIP 4개 상태를 갖는다(`docs/
testing/PROJECT_GUARD_SPEC.md`). WARN·SKIP은 **자동 비차단이 아니다.**

다음 두 조건을 **모두** 만족할 때만 비차단으로 처리할 수 있다.

1. 현재 PR의 완료조건과 무관하다.
2. Gate 1에서 사전에 예상되었거나 이미 이해된 경우다(예: 아직 구현 전
   단계라 영구적으로 `SKIP`으로 유지되는 검사, 이미 문서화된 기존
   WARN).

다음은 **차단한다**(PM 확인 전 병합하지 않는다).

- 현재 Scope와 관련된 WARN
- 예상하지 못한 새 WARN·SKIP
- 구현 완료로 보고한 기능에 필요한 검사의 SKIP
- 완료조건과 관련된 검사의 미실행

기본값은 차단이고, "사전에 알려지고 무관함이 확인된 경우"만 예외로
비차단이다. Codex나 CI가 이 분류를 자동으로 최종 결정하지 않는다 — PM이
Merge 승인 시 함께 확인한다.

---

## 12. 병합 차단·비차단 조건

- **차단(Merge 진행 불가, 절대 원칙)**: Project Guard `FAIL>0`, 전체
  테스트 실패, Integration PR CI 실패, 보안 위반 발견, 승인 범위 밖 변경
  존재, PM Merge 승인 미획득, §11의 차단 대상 WARN·SKIP
- **비차단(기록 후 Merge 진행 가능)**: §11의 두 조건을 모두 만족하는
  WARN·SKIP, 문서 표현 개선 여지, 이번 배치 범위 밖으로 분리하기로 합의된
  개선 후보
- 비차단 항목이 있어도 Gate 2(PM Merge 승인)는 그대로 필요하다 —
  "비차단"은 "PM 확인 없이 자동 병합"이 아니라 "이 문제 때문에 병합
  자체를 재작업할 필요는 없다"는 뜻이다.

---

## 13. 외부 실행 승인 규칙

실제 서울시 API 호출 등 외부 실행은 **실행 직전** PM의 명시적 승인을
매번 받는다(절대 불변 원칙 2). Gate 1에서 "이 배치에 외부 실행이 필요한
항목이 있다"고 미리 알리는 것은 이 실행 직전 승인을 대신하지 않는다.

외부 실행이 필요하다는 이유만으로 자동으로 Child Issue를 만들지 않는다
(§5). Child Issue는 §5에 열거한 조건(독립 장기 추적, 별도 중단·재개,
분리해야 할 만큼 큰 위험·증거, PM의 명시적 요청)에서만 만든다.

---

## 14. Gate 2 — Merge 승인

Integration PR을 `main`에 반영하기 전 PM이 **매번** 개별적·명시적으로
승인한다. 승인 시 확인 대상은 기존과 동일하다(`docs/rules/
GIT_WORKFLOW.md` §15): 연결 Issue 존재, 완료조건 충족, 변경 파일 검토
완료, Project Guard `FAIL=0`, 전체 테스트 통과, CI 통과, 보안 위반 없음,
범위 밖 변경 없음, 남은 위험 보고 — 여기에 §11·§12의 WARN·SKIP 분류
확인이 더해진다.

축소되는 것은 승인 "횟수"(Integration PR 하나가 여러 Checklist Item을
대표)이지 승인 "요건"이 아니다(절대 불변 원칙 1).

---

## 15. Post-Merge 검증

기본값(대부분의 Integration PR Merge에 적용):

- PR 상태 `MERGED` 확인
- 연결 Issue 상태 확인(Checklist 전체 완료 시 Close, 배치 중이면 Open 유지)
- `origin/main` SHA 확인
- local `main` fast-forward
- local `main`과 `origin/main` SHA 일치 확인
- `main` Push에서 트리거된 CI 결과 확인

**이것으로 충분하다.** 전체 로컬 Project Guard·전체 테스트 재실행은
다음 경우에만 수행한다.

- Merge 중 수동 충돌 해결이 있었던 경우
- Squash 과정에서 병합 결과 코드가 변형된 것으로 의심되는 경우
- `main`을 기준으로 새 산출물(Dataset, Manifest, 버전 태그 등)을 생성하는
  main 전용 단계가 이 Merge에 포함된 경우
- `main` CI가 실패했거나 트리거되지 않은 경우
- Release·배포 Gate(예: EG 전체 통과 판정, Parent Issue 완전 종료) 시점인 경우
- PM이 별도로 지시한 경우

`docs/rules/GIT_WORKFLOW.md` §16은 "Merge 후 항상 로컬 Project Guard+
전체 테스트 재검증"을 규정한다 — 이는 **단독 PR·v1 흐름의 기본값**이다.
Parent Issue/Integration PR 흐름(v2)의 Post-Merge 기본 검증은 위 목록을
따른다. 두 문서는 이렇게 적용 범위로 정렬되며 서로 충돌하지 않는다.

---

## 16. Claude Code 축소형 보고(기본값)

```markdown
## [Parent Issue 제목] — [배치 요약]

- Parent Issue / Integration PR: 링크
- 이번 배치 포함 Checklist: 항목 목록
- 변경 파일: 경로 목록(표 아님)
- CI: PASS/FAIL, 링크(FAIL이면 원인 요약 추가)
- 실 Dataset·외부 실행 검증(있는 경우만): 핵심 수치만
- PM 확인 필요사항(있는 경우만)
- 남은 위험(있는 경우만)
- 다음 행동
```

PM이 상세 보고를 요청하면 언제든 기존(더 긴, `docs/rules/
GIT_WORKFLOW.md` §13.3·AGENTS.md §22 기준) 형식으로 복귀한다.

---

## 17. v1에서 v2로의 전환 정책

- 이미 진행 중인 EG-8B B2a(Issue #89, Branch `feat/issue-89-eg8b-b0-baseline-forecast-backtest`)는
  이 문서를 소급 적용하지 않고 기존(v1) Workflow(`docs/rules/
  GIT_WORKFLOW.md`의 단독 Issue/Branch/PR 절차)로 계속 진행하고
  완료한다.
- 이 Workflow v2 문서 자체를 만드는 작업(Issue #90)은 별도 단독 작업으로
  처리하며 이 문서가 정의하는 Parent Issue 구조를 스스로에게 적용하지
  않는다.
- Workflow v2의 실제 적용은 **EG-8B B2b 또는 EG-8C부터** 시작한다.
- 이미 진행 중인 Branch·Issue·Commit을 새 구조로 소급 이동하지 않는다.

---

## 18. EG-8B B2b~UI Workflow 매핑

| Parent Issue | Worktree 병렬화 후보 | 예상 Integration PR 배치(안, Gate 1에서 각 Parent Issue별 확정) |
|---|---|---|
| EG-8B B2(Baseline·Backtest·다일자 Gate) | B1(요일·시간)·B2(4주평균)는 서로 독립 계산이라 병렬 후보(최소 5영업일 데이터 축적 후 착수, B2b `WAITING_FOR_MORE_DATA` 유지) | 데이터 축적 후 1~2개 |
| EG-8C(ML Forecast·Peak Prediction) | Feature/Label은 순차(서로 의존), Linear·Tree 모델은 병렬 후보 | Feature·Label 1개 / Baseline·모델 비교 1개 / Peak·Manifest 1개(안) |
| EG-8D(Area Ranking) | Score 산식·가중치는 `OPEN_DECISION`이라 EG-8C 이후 착수 | 1개 내외 |
| EG-8E(Recommendation Output) | Output Contract는 대체로 순차 | 1개 내외 |
| UI(Decision Experience) | 정보구조·와이어프레임은 병렬 후보 | 배치 진행에 따라 PM 재량 |

착수 시점·착수 승인은 이 문서가 아니라 각 Parent Issue 자체에서 PM이
별도로 결정한다(이 표는 계획 참고용이며 자동 착수 승인이 아니다).
**EG-8B B2a(Issue #89)는 이 표에 포함하지 않는다** — v1으로 계속 진행한다
(§17).

---

## 19. 관련 문서 링크

- [`AGENTS.md`](../../AGENTS.md) — Codex/Claude Code 행동 규칙과 문서 진입점
- [`docs/engineering/CODEX_HARNESS_ARCHITECTURE.md`](CODEX_HARNESS_ARCHITECTURE.md) — 전체 Harness 구조와 PM Approval 3종 정의
- [`docs/rules/GIT_WORKFLOW.md`](../rules/GIT_WORKFLOW.md) — Branch 이름 규칙·Commit 규칙·단독 Issue/PR 절차(v1)
- [`docs/testing/QUALITY_GATES.md`](../testing/QUALITY_GATES.md) — EG-0~EG-8 진입·통과조건
- [`docs/testing/PROJECT_GUARD_SPEC.md`](../testing/PROJECT_GUARD_SPEC.md) — 검사 ID·상태·종료코드
- [`.github/ISSUE_TEMPLATE/task.md`](../../.github/ISSUE_TEMPLATE/task.md) — Child/단독 작업 Issue 템플릿
- [`.github/ISSUE_TEMPLATE/parent_task.md`](../../.github/ISSUE_TEMPLATE/parent_task.md) — Parent Issue 템플릿
- [`.github/pull_request_template.md`](../../.github/pull_request_template.md) — PR 템플릿(Integration PR 포함)
