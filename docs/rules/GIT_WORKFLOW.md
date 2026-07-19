# Git Workflow

- 문서 상태: Draft
- 버전: v0.1.1
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-17
- 최종 수정일: 2026-07-20
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - `AGENTS.md`
  - `README.md`
  - `docs/rules/CODING_RULES.md`
  - `docs/rules/SECURITY_RULES.md`
  - `docs/testing/PROJECT_GUARD_SPEC.md`
  - `docs/testing/QUALITY_GATES.md`
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 Freshmanager Data PoC에서 발생하는 모든 문서, 코드, 설정, 테스트 및 기준데이터 변경을 Git과 GitHub에서 안전하게 관리하는 절차를 정의한다.

이 문서의 목적은 다음과 같다.

1. 승인되지 않은 변경이 `main`에 반영되는 것을 방지한다.
2. 작업 목적과 범위를 Issue 단위로 명확히 한다.
3. 모든 변경을 Branch 또는 Worktree에서 분리한다.
4. 변경 결과와 검증 근거를 Pull Request에 기록한다.
5. 적용 대상 Project Guard와 Unit Tests를 통과하고, 구성된 경우 GitHub Actions도 통과한 변경만 병합한다.
6. PM이 최종 승인권을 유지한다.
7. 문제가 발생했을 때 변경 이유와 이력을 추적할 수 있게 한다.

---

## 2. 적용 범위

다음 변경에 이 문서를 적용한다.

- Markdown 문서
- Python 코드
- 테스트 코드
- 설정파일
- GitHub Actions
- Issue 및 Pull Request 템플릿
- 공식 기준 CSV
- 샘플 JSON
- 데이터 구조
- Project Guard 검사 규칙
- 분석계획
- Codex Skill
- 운영 스크립트

단순히 로컬에서 내용을 확인하는 읽기 전용 작업에는 Branch를 만들지 않을 수 있다.

파일을 생성·수정·삭제하거나 Git 이력에 반영하는 작업에는 이 절차를 적용한다.

---

## 3. 핵심 용어

| 용어 | 의미 |
|---|---|
| Repository | 프로젝트 파일과 변경 이력을 관리하는 저장소 |
| `main` | PM 승인과 검증을 통과한 공식 기준 브랜치 |
| Branch | 특정 작업을 `main`과 분리해 진행하는 변경 이력 |
| Worktree | 특정 Branch를 별도의 실제 폴더에 펼쳐놓은 작업공간 |
| Commit | 의미 있는 변경사항을 저장한 하나의 기록 |
| Push | 로컬 Commit을 GitHub에 업로드하는 작업 |
| Issue | 한 번의 작업 목적·범위·완료조건을 정의한 작업요청서 |
| Pull Request | 작업 Branch를 `main`에 반영하기 위한 검토·승인 요청 |
| Merge | 승인된 작업 Branch의 변경을 `main`에 반영하는 작업 |
| Project Guard | 파일·데이터·문서·보안·정책 등 저장소 규칙을 자동검사하는 하위 시스템 |
| Unit Tests | 코드 또는 Project Guard 검사 로직의 개별 동작을 검증하는 별도 검증 요소 |
| GitHub Actions/CI | GitHub 서버에서 Project Guard와 Unit Tests를 자동 실행하는 체계 |
| PM 승인 | 신동현이 작업 범위 또는 다음 단계 진행을 명시적으로 승인한 상태 |

---

## 4. 브랜치 운영 원칙

### 4.1 `main` 브랜치

`main`은 다음 조건을 만족한 상태만 포함한다.

- 작업 목적이 명확함
- Issue 범위를 준수함
- 관련 문서가 업데이트됨
- 적용 대상 Project Guard 검사 통과 또는 Project Guard 미구현 단계의 문서 수동검증 완료
- 적용 대상 Unit Tests 통과
- GitHub Actions가 구성돼 현재 작업에 적용되는 경우 통과
- 보안 위반 없음
- PM 최종 승인 완료

`main`에서 다음 행위를 금지한다.

- 직접 파일 수정
- 직접 Commit
- 검증 없이 Push
- Pull Request 없이 변경 반영
- PM 승인 없는 Merge
- 강제 Push

최초 Git 저장소 기준선 생성과 같은 예외 작업은 PM이 명시적으로 승인한 경우에만 허용한다.

---

### 4.2 작업 Branch

모든 변경 작업은 작업 Branch에서 수행한다.

작업 Branch는 하나의 Issue 또는 하나의 명확한 작업 목적만 다룬다.

다음 작업을 하나의 Branch에 섞지 않는다.

- 문서 구조 정비
- 데이터 검증
- 수집기 구현
- 분석 코드 구현
- 보안 설정
- unrelated 리팩터링

---

## 5. Issue 작성 규칙

모든 구현 또는 문서 변경은 원칙적으로 GitHub Issue에서 시작한다.

### 5.1 Issue 제목

권장 형식:

```text
[게이트 또는 유형] 작업명
```

예:

```text
[EG-1] 서울시 121장소 CSV 무결성 검증
[EG-2] 여의도 샘플 JSON 경로 동기화
[EG-3] 오프라인 Project Guard 1차 구현
[Docs] Git 운영 규칙 작성
[Security] API 키 로그 마스킹
```

### 5.2 Issue 필수 항목

Issue에는 다음 내용을 포함한다.

1. 작업 목적
2. 배경
3. 현재 상태
4. 작업 범위
5. 제외 범위
6. 생성 또는 수정 가능한 파일
7. 수정 금지 파일
8. 완료 조건
9. 적용할 검사 ID
10. 실행할 검증 명령
11. 실제 API 호출 허용 여부
12. 패키지 설치 허용 여부
13. PM 승인 필요사항
14. 남은 위험

### 5.3 Issue 범위 변경

작업 중 Issue 범위를 변경해야 할 경우 임의로 확장하지 않는다.

다음 형식으로 PM에게 보고한다.

1. 새로 발견한 문제
2. 기존 Issue 범위에 미치는 영향
3. 선택 가능한 처리방법
4. 권장안
5. 추가 Issue 분리 필요 여부
6. PM 승인 필요사항

---

## 6. Branch 이름 규칙

Branch 이름은 영문 소문자와 하이픈을 사용한다.

권장 형식:

```text
작업유형/issue-번호-작업명
```

예:

```text
docs/issue-12-git-workflow
data/issue-13-csv-validation
feature/issue-18-eg3-project-guard
fix/issue-21-forecast-parser
security/issue-25-key-masking
test/issue-27-parser-fixtures
chore/issue-30-config-template
```

### 작업유형

| 접두어 | 사용 목적 |
|---|---|
| `docs/` | 문서 작성·수정 |
| `data/` | 기준데이터·데이터 구조 |
| `feature/` | 새로운 기능 |
| `fix/` | 오류 수정 |
| `test/` | 테스트·Project Guard |
| `security/` | 보안 관련 변경 |
| `chore/` | 환경·설정·정리 |
| `analysis/` | 분석계획·분석 코드 |

피해야 할 Branch 이름:

```text
test
new
work
final
aaa
donghyun
수정
```

---

## 7. Branch와 Worktree 사용 기준

### Branch만 사용하는 경우

- Markdown 문서 1~2개 수정
- 단순 설정파일 수정
- 작은 오류 수정
- 한 번에 하나의 작업만 수행

### Worktree를 권장하는 경우

- 여러 코드 파일을 동시에 수정
- Codex가 장시간 구현 작업 수행
- 두 개 이상의 Issue를 병렬 진행
- `main` 상태를 별도 폴더에서 유지해야 함
- 실 API 테스트와 오프라인 개발을 분리해야 함

### Worktree 원칙

- Issue별로 하나의 Worktree를 사용한다.
- Worktree는 해당 Issue Branch에 연결한다.
- Worktree 안에서도 `AGENTS.md`와 관련 규칙을 적용한다.
- Worktree 종료 전 Commit·Push 여부를 확인한다.
- 사용이 끝난 Worktree는 PM 확인 후 정리한다.
- 실제 `.env` 복사 여부는 `SECURITY_RULES.md`를 따른다.

---

## 8. 작업 시작 절차

### 8.1 `main` 최신화

작업 시작 전 다음 순서로 확인한다.

1. `git status --short --untracked-files=all`
2. `git branch --show-current`
3. Stage·추적 파일 변경·미추적 파일 상태 확인
4. `git switch main`
5. `git pull --ff-only origin main`
6. `git status --short --untracked-files=all`

작업 시작 전 다음 조건을 모두 확인한다.

- Stage된 변경이 없어야 한다.
- 추적 파일의 수정·삭제·추가가 없어야 한다.
- 예상하지 못한 미추적 파일이 없어야 한다.
- PM이 인지한 보호 대상 미추적 파일은 유지할 수 있다.
- 보호 대상 미추적 파일은 자동 Stage하지 않는다.

다음 중 하나라도 해당하면 Branch 전환과 Pull을 중단한다.

- Stage된 변경이 있음
- 추적 파일 변경이 있음
- 예상하지 못한 미추적 파일이 있음
- 미추적 파일의 보호 대상 여부가 확인되지 않음

PM이 인지한 보호 대상 미추적 파일만 존재하는 경우에는
Branch 전환과 `main` 최신화를 차단하지 않는다.

```bash
git status --short --untracked-files=all
git branch --show-current
git switch main
git pull --ff-only origin main
git status --short --untracked-files=all
```

의미:

| 명령 | 의미 |
|---|---|
| `git status --short --untracked-files=all` | Stage·추적 파일 변경과 전체 미추적 파일 확인 |
| `git branch --show-current` | 현재 Branch 확인 |
| `git switch main` | 기준 브랜치로 이동 |
| `git pull --ff-only origin main` | 새 Merge Commit 없이 GitHub의 최신 `main`을 로컬에 반영 |

### 8.2 작업 Branch 생성

```bash
git switch -c 작업브랜치명
```

예:

```bash
git switch -c docs/issue-12-git-workflow
```

현재 Branch 확인:

```bash
git branch --show-current
```

### 8.3 작업 전 확인

Codex 또는 작업자는 다음을 먼저 확인한다.

- Issue 번호
- 현재 품질 게이트
- 작업 목적
- 수정 가능 파일
- 수정 금지 파일
- 실제 API 호출 허용 여부
- 패키지 설치 허용 여부
- 적용 검사 ID
- PM 승인 여부

---

## 9. Codex 작업 절차

Codex는 다음 순서를 따른다.

```text
AGENTS.md 읽기
→ Issue 읽기
→ 관련 요구사항 읽기
→ 관련 규칙 문서 읽기
→ 현재 파일 상태 읽기 전용 확인
→ 구현 계획 보고
→ PM 승인 대기
→ 승인된 범위만 수정
→ Project Guard 실행
→ Unit Tests 실행
→ 자체 리뷰
→ 결과 보고
```

PM 승인 전에는 다음을 수행하지 않는다.

- 파일 생성
- 파일 수정
- 파일 삭제
- 패키지 설치
- 실제 API 호출
- Commit
- Push
- Pull Request 생성
- Merge

---

## 10. Commit 규칙

### 10.1 Commit의 역할

Commit은 하나의 의미 있는 변경 단위를 기록한다.

하나의 Commit에 여러 목적을 섞지 않는다.

좋은 예:

```text
docs: define Git workflow
data: validate Seoul place reference
feat: implement offline project guard
fix: preserve forecast snapshots
security: mask API key in logs
test: add invalid JSON fixture
```

피해야 할 예:

```text
수정
업데이트
최종
진짜최종
여러가지 수정
work
```

### 10.2 Commit 접두어

| 접두어 | 의미 |
|---|---|
| `docs:` | 문서 변경 |
| `data:` | 데이터 기준·구조 |
| `feat:` | 기능 추가 |
| `fix:` | 오류 수정 |
| `test:` | 테스트 추가·수정 |
| `security:` | 보안 변경 |
| `analysis:` | 분석 관련 변경 |
| `chore:` | 설정·환경·정리 |

### 10.3 Commit 전 확인

```bash
git status
git diff
```

변경 파일을 선택한다.

```bash
git add 파일경로
```

여러 파일 예:

```bash
git add docs/rules/GIT_WORKFLOW.md AGENTS.md README.md
```

Commit 대상 확인:

```bash
git diff --cached --name-only
git diff --cached
```

Commit:

```bash
git commit -m "docs: define Git workflow"
```

### 10.4 `git add .` 사용 금지

`git add .`는 사용하지 않는다.

승인된 파일 경로를 직접 지정해서 Stage한다.

```bash
git add docs/rules/GIT_WORKFLOW.md
```

---

## 11. 로컬 검증

Commit 또는 Push 전에 다음을 수행한다.

1. `git status`
2. 변경 파일 확인
3. 범위 밖 변경 여부 확인
4. Project Guard 실행
5. Unit Tests 실행
6. 민감정보 확인
7. Codex 자체 리뷰
8. 문서와 코드 정합성 확인

Project Guard가 구현된 이후 공식 명령은 다음과 같다.

```bash
python3 scripts/project_guard_check.py
```

Unit Tests 공식 명령은 다음과 같다.

```bash
python3 -B -m unittest discover -s tests -p "test_*.py" -v
```

Project Guard가 아직 구현되지 않은 단계에서는 관련 문서에 정의된 읽기 전용 수동검증을 수행한다.

검증 실패 상태에서 완료로 보고하지 않는다.

---

## 12. Push 규칙

최초 Push:

```bash
git push -u origin 작업브랜치명
```

예:

```bash
git push -u origin docs/issue-12-git-workflow
```

`-u`는 로컬 Branch와 GitHub Branch의 연결을 기억하게 한다.

연결 이후에는 다음 명령을 사용할 수 있다.

```bash
git push
```

Push 전 확인:

- Commit 존재
- 현재 Branch가 `main`이 아님
- 실제 API 키 없음
- 범위 밖 파일 없음
- Project Guard 결과 확인
- Unit Tests 결과 확인

---

## 13. Pull Request 규칙

### 13.1 방향

```text
base: main
compare: 작업 Branch
```

의미:

```text
작업 Branch의 변경을
main에 반영하기 위한 검토 요청
```

### 13.2 PR 제목

권장 형식:

```text
[게이트 또는 유형] 작업명
```

예:

```text
[Docs] Git 운영 규칙 기준선 수립
[EG-3] 오프라인 Project Guard 1차 구현
```

### 13.3 PR 본문 필수항목

1. 연결 Issue
2. 작업 목적
3. 변경 파일
4. 파일별 변경사항
5. 검증 명령
6. Project Guard 결과
7. Unit Tests 결과
8. Codex 리뷰 결과
9. 범위 외 변경
10. PM 확인사항
11. 남은 위험
12. 다음 게이트 진입 가능 여부

### 13.4 Issue 연결

PR 본문에 다음 형식을 사용한다.

```text
Closes #이슈번호
```

PR 병합 시 연결된 Issue가 종료되도록 한다.

---

## 14. 리뷰 순서

표준 리뷰 순서는 다음과 같다.

```text
로컬 Project Guard와 Unit Tests 또는 문서 전용 작업의 수동검증
→ Codex Review
→ Commit
→ Push
→ Pull Request
→ 구성된 경우 GitHub Actions/CI에서 Project Guard와 Unit Tests
→ 필요 시 Codex GitHub Review
→ PM Review
→ Merge
```

### 14.1 Project Guard

정해진 규칙을 기계적으로 검사한다.

예:

- 파일 존재
- CSV 121행
- 필수필드
- Python 문법
- API 키 노출
- 종료 코드

### 14.2 Unit Tests

코드 또는 Project Guard 검사 로직의 개별 동작이 예상대로 수행되는지 검증한다.

예:

- 정상·실패 입력별 판정
- 검사 ID와 순서
- 종료 코드
- 네트워크 차단
- 공식 데이터 불변성

### 14.3 Codex Review

의미와 위험을 검토한다.

예:

- 요구사항 해석 오류
- 데이터 손실 가능성
- 범위 밖 수정
- 잘못된 예외처리
- 문서와 코드 불일치
- 테스트 누락

### 14.4 PM Review

다음을 최종 판단한다.

- 작업 목적 달성
- 사업 범위 준수
- 품질 게이트 통과
- 위험 수용 가능 여부
- `main` 병합 승인

---

## 15. Merge 규칙

다음 조건을 모두 충족한 후 Merge한다.

- 연결 Issue 존재
- 완료조건 충족
- 변경 파일 검토 완료
- 적용 대상 Project Guard `FAIL=0` 또는 Project Guard 미구현 단계의 문서 수동검증 완료
- 적용 대상 Unit Tests 통과
- GitHub Actions/CI가 구성돼 현재 작업에 적용되는 경우 Project Guard와 Unit Tests 통과
- 보안 위반 없음
- 범위 밖 변경 없음
- 남은 위험 보고
- PM 최종 승인

### 권장 Merge 방식

1인 프로젝트에서는 `Squash and merge`를 권장한다.

```text
Issue 1개
→ PR 1개
→ main Commit 1개
```

다른 Merge 방식을 사용하는 경우 저장소 전체에서 한 가지 방식을 일관되게 사용한다.

---

## 16. Merge 후 정리

GitHub에서 Merge 후 다음 절차를 수행한다.

```bash
git switch main
git pull --ff-only origin main
git status --short --untracked-files=all
```

`main` 반영 후 다음 명령으로 재검증한다.

```bash
python3 scripts/project_guard_check.py
python3 -B -m unittest discover -s tests -p "test_*.py" -v
```

`main` 재검증에 실패하면 완료 처리와 Branch 정리를 중단하고,
실패한 단계와 결과를 PM에게 보고한다.

PROJECT_STATUS 영향 판정은 Merge 전과 Merge 후 두 단계로 구분한다.

Merge 전:

```text
Pull Request에서 Codex가 PROJECT_STATUS 영향 분석
→ PM이 갱신 필요 또는 불필요 최종 판단
→ 필요하면 같은 Pull Request에 상태 문서 반영
```

Merge 후:

```text
Merge
→ main 최신화
→ main CI 확인
→ Project Guard와 Unit Tests 재검증
→ Merge 후 새롭게 확정된 중요 사실 확인
→ 필요한 경우에만 별도 상태 갱신 Issue 생성
→ 갱신 불필요하면 Issue 또는 Pull Request에 근거 기록
→ Issue 종료 상태 확인과 Branch 정리
```

- PM은 공식 프로젝트 상태와 Issue 완료 여부를 최종 판단한다.
- Codex는 상태 영향 분석, 승인된 내용 반영과 문서 정합성 검증을 담당한다.
- GitHub CI는 Project Guard와 Unit Tests의 성공·실패 증거만 제공하며,
  프로젝트 완료 또는 공식 상태를 판단하지 않는다.
- 상태 영향이 Merge 전에 확정되면 원칙적으로 같은 Pull Request에 반영한다.
- Merge 후에만 확정되는 중요한 정보가 있을 때만 별도 상태 갱신 Issue를 만든다.
- 모든 Issue에 별도 상태 갱신 Issue를 자동 생성하지 않는다.

로컬 작업 Branch 삭제:

```bash
git branch -d 작업브랜치명
```

GitHub에서 삭제된 Branch 정보 정리:

```bash
git fetch --prune
```

최종 확인:

```bash
git branch --show-current
git status --short --untracked-files=all
git log --oneline -5
```

정상 상태:

```text
현재 Branch: main
로컬 main과 origin/main 동기화
추적 파일 변경 없음
승인되지 않은 Stage 없음
PM이 인지한 보호 대상 미추적 파일은 존재할 수 있음
```

---

## 17. 금지 또는 주의 명령

다음 명령은 PM 확인 없이 실행하지 않는다.

```bash
git reset --hard
git clean -fd
git push --force
git push --force-with-lease
git branch -D
git rebase
git filter-repo
```

이 명령들은 파일, Commit 또는 Git 이력을 삭제하거나 변경할 수 있다.

---

## 18. 자주 발생하는 문제와 대응

### 18.1 잘못된 파일을 `git add`한 경우

```bash
git restore --staged 파일경로
```

파일 수정내용은 유지하고 Commit 대상에서만 제거한다.

### 18.2 잘못된 Branch에서 Commit한 경우

추가 작업을 중단하고 다음을 보고한다.

1. 현재 Branch
2. Commit ID
3. 변경 파일
4. 원격 Push 여부
5. 권장 복구안

임의로 `reset --hard`하지 않는다.

### 18.3 PR Merge 전 Branch를 삭제한 경우

- GitHub PR 상태 확인
- 원격 Branch 존재 여부 확인
- Commit ID 확인
- 필요 시 해당 Commit에서 Branch 복원

### 18.4 민감정보가 Commit된 경우

`SECURITY_RULES.md`의 사고 대응 절차를 적용한다.

단순히 최신 파일에서 문자열만 삭제하고 끝내지 않는다.

### 18.5 GitHub Actions 실패

- 실패한 Step 확인
- Project Guard와 Unit Tests 출력 확인
- 로컬에서 동일 명령 재현
- 원인 수정
- 다시 Commit·Push
- Actions 재실행 확인

---

## 19. 완료 정의

Git 작업은 다음 조건을 모두 만족해야 완료다.

- Issue 목적 달성
- 승인된 Branch에서 작업
- 범위 밖 변경 없음
- Commit 메시지 명확
- 적용 대상 Project Guard 통과 또는 Project Guard 미구현 단계의 문서 수동검증 완료
- 적용 대상 Unit Tests 통과
- PR 생성
- GitHub Actions/CI가 구성돼 현재 작업에 적용되는 경우 Project Guard와 Unit Tests 통과
- PM 승인
- `main` Merge
- `main`에서 Project Guard와 Unit Tests 재검증 통과
- PROJECT_STATUS 영향 판정 완료
- 갱신 필요 시 같은 Pull Request 반영 또는 Merge 후 새롭게 확정된 중요 사실에 대한 후속 상태 갱신 Issue 생성
- 갱신 불필요 시 Issue 또는 Pull Request에 사유 기록
- PM의 최종 상태 영향과 완료 판단 완료
- 로컬 `main` 최신화
- 작업 Branch 정리
- Issue 종료 상태 확인
- 남은 위험 기록

---

## 20. 변경 이력

| 버전 | 날짜 | 변경내용 | 작성자 | 승인상태 |
|---|---|---|---|---|
| v0.1.1 | 2026-07-20 | PROJECT_STATUS 영향 판정의 Merge 전·후 절차와 책임·완료조건 보완 | 신동현 | Draft |
| v0.1.0 | 2026-07-17 | 최초 초안 작성 | 신동현 | Draft |
