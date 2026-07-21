# PROJECT_STATUS.md

> FreshManager 프로젝트의 **상태 복원·AI 인수인계 문서**
> 새 대화, 새 AI 세션, 새 작업을 시작할 때 이 파일을 가장 먼저 읽는다.

---

## 0. 30초 요약

- 프로젝트: **프레시매니저 유동판매 추천 서비스 — 데이터 타당성 PoC**
- 현재 목표: EG-6A에서 확정한 13개 Area의 EG-6B 단일 순차수집을 오프라인으로 구현·검증
- `main` 반영 완료: EG-0~EG-6A, CI 보강, 보호 경로 Hardening, 대표 3장소 실제 수집과 13개 참조 패널
- 공식 진행 Issue: #53
- 공식 기준 Branch: `main`
- 공식 작업 Branch: `feature/issue-53-eg6b-single-collection`
- 기준 Commit: `289bd18a5b870bc6dfde1ca18febbc48a948b8dc`
- 현재 작업: 승인 13개 Area 단일 회차 CLI·Batch Log·Manifest·SHA-256 오프라인 구현
- 현재 Engineering Gate: EG-6B 구현 진행 — 실제 API 호출 전 오프라인 검증 단계
- 현재 Codex Engineering Harness 개편 상태: P1~P7 완료
- 다음 공식 단계: **Issue #53 구현 Diff와 오프라인 검증 결과에 대한 PM 검토**
- 실제 서울시 API 호출: EG-4 POI072와 EG-5 대표 3장소 수집 완료; EG-6A·EG-6B 구현 중 0회
- Issue #43: 완료, PM이 EG-4 PASS 확정
- 절대 주의:
  - API Key Commit 금지
  - 공식 CSV·JSON 임의 수정 금지
  - `git add .` 사용 금지
  - 저장소 최상위 `work log/` 재생성·열거·Stage 금지

실제 작업 중 Issue와 Branch는 GitHub의 현재 Issue와
`git branch --show-current` 결과를 우선한다.

Issue #43의 POI072와 후속 EG-5 대표 3장소 수집을 완료했다. PR #52에서 EG-6A
13개 Area·Spot·S-DoT 참조데이터를 `main`에 반영했다. Issue #53은 같은 13개 Area의
단일 수집 기능을 Fake Transport로 구현·검증하며 실제 호출은 별도 PM 승인 전 수행하지 않는다.

---

## 1. 프로젝트 기본 정보

### 1.1 프로젝트 정의

- 프로젝트명: FreshManager
- 프로젝트 성격: 프레시매니저 유동판매 추천 서비스 — 데이터 타당성 PoC
- 추진 방식: hy 비제휴, 공개 데이터 기반 선행 검증
- 1차 검증 지역: 여의도 오피스 상권
- 핵심 사용자:
  - 정기배송 완료 후 담당구역에서 유동판매를 수행하는 프레시매니저

### 1.2 해결하려는 문제

- 유동판매 위치와 시간 선택이 개인 경험에 크게 의존한다.
- 정기배송 이후 추가 판매 기회를 체계적으로 찾기 어렵다.
- 출근·점심시간처럼 익숙한 시간대에만 판매가 집중될 가능성이 있다.
- 공개 데이터가 실제 현장 의사결정에 활용될 수 있는지 아직 확인되지 않았다.

### 1.3 PoC 목표

- 공개 데이터로 시간대별 유동 변화가 구분되는지 확인한다.
- 서울시 예측값과 실제 관측값을 비교할 수 있는지 확인한다.
- 반복적으로 발생하는 피크 시간대를 탐지할 수 있는지 확인한다.
- 예측 결과가 프레시매니저의 이동 가능한 시간 안에 제공될 수 있는지 검토한다.
- 향후 hy에 현장 실증을 제안할 근거를 만든다.

### 1.4 현재 단계에서 확정할 수 없는 것

- 실제 매출 증가
- 실제 구매 전환율
- 최적 알림 시점
- 실제 판매지점의 최종 적합성
- 프레시매니저 전체의 수용성
- 완성형 추천 서비스의 사업성

---

## 2. 프로젝트 책임자와 AI 협업 원칙

프로젝트 책임자는 **비개발자 PM/PO**다.

AI와 Codex는 다음 순서로 설명한다.

1. 지금 무엇을 하는 작업인지
2. 왜 이 작업이 필요한지
3. 사용자가 지금 해야 하는 행동
4. 복사해서 실행할 명령어
5. 실행 후 예상되는 정상 결과
6. 문제가 발생했을 때 멈춰야 하는 기준

### 2.1 설명 규칙

- 개발 용어만 나열하지 않는다.
- 전문 용어는 처음 등장할 때 쉬운 말로 풀이한다.
- 코드 내부 구조보다 업무 흐름을 먼저 설명한다.
- 한 번에 너무 많은 결정을 요구하지 않는다.
- PM이 결정할 사항과 개발자가 판단할 사항을 분리한다.
- 구현 전에는 읽기 전용 계획을 먼저 보고한다.
- 사용자가 승인하지 않은 범위를 임의로 확장하지 않는다.
- 불확실한 내용은 사실처럼 단정하지 않는다.
- 명령어는 한 단계씩 실행할 수 있도록 구분한다.

### 2.2 사용자가 이미 이해한 작업 흐름

```text
Issue 생성
→ Branch 생성
→ 필요 시 Worktree 생성
→ 구현
→ 검토
→ Commit
→ Push
→ Pull Request
→ Merge
→ Issue 종료 상태 확인
→ Branch·Worktree 정리
```

앞으로 기술 설명은 이 흐름에 연결해서 설명한다.

---

## 3. 프로젝트 운영 흐름

```text
요구사항 확인
→ GitHub Issue 생성
→ 작업 Branch 생성
→ 필요 시 Worktree 생성
→ Codex 읽기 전용 계획
→ PM 범위 승인
→ 구현
→ 로컬 Project Guard와 Unit Tests
→ 변경 파일 검토
→ 승인된 파일만 Stage
→ Commit
→ Push
→ Pull Request
→ Codex가 PROJECT_STATUS 영향 사전 분석
→ PM이 갱신 필요 또는 불필요 최종 판정
→ 영향이 Merge 전에 확정되면 같은 PR에 반영
→ GitHub Actions 확인
→ PM 최종 승인
→ main Merge
→ main CI와 로컬 재검증
→ Merge 후 새롭게 확정된 중요 사실 확인
→ 필요한 경우에만 별도 상태 갱신 Issue 생성
→ Issue 종료 상태 확인
→ Branch·Worktree 정리
```

### 3.1 Git 운영 원칙

- PM이 최종 승인자다.
- Commit, Push, PR, Merge는 서로 다른 단계로 본다.
- `git add .`은 사용하지 않는다.
- 승인된 파일만 경로를 지정해 Stage한다.
- 미추적 파일은 자동으로 Stage하지 않는다.
- 예상하지 못한 미추적 파일은 작업을 중단하고 정체와 범위를 확인한다.
- 폐기한 저장소 작업일지 경로는 H-206으로 존재 여부와 개수만 확인한다.
- PR의 `Files changed`에 승인되지 않은 파일이 있으면 Merge하지 않는다.

---

## 4. 문서와 정보의 우선순위

내용이 서로 충돌할 때 다음 순서로 판단한다.

```text
1. 현재 main 코드와 실제 테스트 결과
2. 현재 GitHub Issue의 PM 확정 댓글
3. 병합된 Pull Request
4. PROJECT_STATUS.md
5. AGENTS.md
6. docs/testing/QUALITY_GATES.md
7. docs/testing/PROJECT_GUARD_SPEC.md
8. README.md
9. 작업일지
10. 과거 AI 대화
```

`PROJECT_STATUS.md`는 빠른 복원을 위한 문서다.
실제 코드, 테스트 결과, PM이 승인한 Issue 기록보다 우선하지 않는다.

---

## 5. Engineering Gate 진행 상태

| 구분 | 상태 | 설명 |
|---|---|---|
| EG-0 | 완료 | 프로젝트 초기 기준 수립 |
| EG-1 | 완료 | 데이터·검증 계약 수립 |
| EG-2 | 완료 | 공식 기준 CSV와 샘플 JSON 반영 |
| EG-3 | 완료 | Project Guard와 Unit Tests 구현·병합 |
| CI 보강 | 완료 | Issue #16, PR #20, PR 및 main Push 자동검사 검증 완료 |
| EG-4 | 완료 | Issue #43에서 POI072 실제 정상 JSON과 원본·메타데이터 저장 확인, PM PASS |
| EG-5 | 완료 | POI019·POI013·POI014 실제 수집 3건 성공, 재시도 0회, 데이터 구조·Feature 분석 완료 |
| Issue #47 Hardening | 완료 | 보호 경로 제거와 H-206·Stacked PR CI 보강을 main에 반영 |
| EG-6A | 완료 | Issue #51·PR #52에서 서로 다른 공식 Area 13개와 Spot·S-DoT 참조 패널을 main에 반영 |
| EG-6B | 진행 | Issue #53에서 동일 13개 Area 단일 순차수집·Batch Log·Manifest·SHA-256을 오프라인 구현; 실제 호출 미승인 |
| EG-7 | 미진행 | 주기와 백업 Gate 승인 후 동일 13개 반복수집 파일럿 |
| EG-8 | 미진행 | 반복 관측 데이터의 Feature 유효성 분석 |

> EG-0~EG-2의 상세 완료조건은 저장소 문서와 병합된 Issue·PR을 확인한다.

---

## 6. 완료된 핵심 작업

### 6.1 EG-3 Python Harness

- Issue: #14
- 상태: main 병합 완료
- 구현 목적:
  - 사람이 매번 확인하던 데이터와 문서 상태를 자동 검사
  - 오류가 있으면 다음 작업으로 넘어가지 않도록 방지

`Python Harness`는 Issue #14 당시 작업명이다. 현재 자동검사 하위 시스템의
공식 명칭은 Project Guard다.

### 6.2 검사 범위

- 공식 CSV 구조와 내용
- 공식 JSON 구조와 내용
- 필수 파일 존재 여부
- 문서의 현재 상태 표현
- 민감정보와 금지 패턴
- 종료코드
- 단위 테스트

### 6.3 공식 실행 명령

Project Guard:

```bash
python3 scripts/project_guard_check.py
```

단위 테스트:

```bash
python3 -B -m unittest discover -s tests -p "test_*.py" -v
```

현재 공식 구성:

- 명세: `docs/testing/PROJECT_GUARD_SPEC.md`
- 결과 보고 템플릿: `docs/testing/PROJECT_GUARD_REPORT_TEMPLATE.md`
- CI Workflow: `.github/workflows/ci.yml`
- Unit Tests: `tests/test_project_guard_check.py`

### 6.4 EG-3 병합 당시 정상 기준

```text
PASS=28
FAIL=0
WARN=0
SKIP=17
TOTAL=45
EXIT_CODE=0

Ran 45 tests
OK
```

### 6.5 공식 기준 데이터

- `data/reference/seoul_121_places.csv`
- `data/samples/population_yeouido_sample.json`

이 두 파일은 별도 Issue와 PM 승인 없이 수정하지 않는다.

### 6.6 Codex Engineering Harness Architecture — Issue #24 / PR #25

- Issue #24 완료 및 Close
- PR #25 Merge 완료
- Commit: `docs: define Codex engineering harness architecture (#25)`
- 반영 문서: `docs/engineering/CODEX_HARNESS_ARCHITECTURE.md`
- 주요 결과:
  - Codex Engineering Harness와 Project Guard 계층 구분
  - Project Guard, Unit Tests, CI, Review와 Quality Gates 책임 구분
  - PM 범위 승인·외부 실행 승인·Merge 승인 구분
  - 문서별 공식 책임과 중복 방지 원칙 정의
  - Current State와 Target State 구분
- Codex Engineering Harness 구조·용어 개편: P1 완료, P2 완료
- 검증: PR #25 CI, `main` Push CI, 로컬 Project Guard와 Unit Tests 성공

### 6.7 Project Guard 명칭·경로 전환 — Issue #28 / PR #29

- Issue #28 완료
- PR #29 Squash and merge 완료
- Squash Commit: `0201eee`
- PR CI 성공
- `main` Push CI 성공
- 로컬 `main`과 `origin/main` 동기화 완료
- Issue #28 작업 Branch 삭제 완료
- Project Guard 공식 명칭·파일명·경로 전환 완료
- Codex Engineering Harness 구조·용어 개편: P3~P7 완료
- 검사 ID 45개 유지
- Unit Tests 45개 유지
- 공식 경로:
  - `scripts/project_guard_check.py`
  - `tests/test_project_guard_check.py`
  - `docs/testing/PROJECT_GUARD_SPEC.md`
  - `docs/testing/PROJECT_GUARD_REPORT_TEMPLATE.md`
  - `.github/workflows/ci.yml`

### 6.8 POI072 오프라인 수집기 — Issue #32

- 루트 `freshmanager/` 패키지에 교체 가능한 Client 계약과 Fake 기반 수집 흐름 구현
- 공식 CSV의 `POI072` 한 장소만 읽기 전용으로 처리
- 원본 bytes 비덮어쓰기와 요청별 8개 메타데이터 JSON 구현
- 실제 HTTP Adapter, 실제 `.env` 사용과 실제 API 호출은 제외
- Issue #32 완료 당시 Project Guard: 45개 ID 유지, 활성 35개 PASS,
  후속 10개 SKIP
- Issue #32 완료 당시 Unit Tests: 83개 통과

### 6.9 HTTP Adapter 오프라인 구현 — Issue #34 / PR #36

- Issue #34 Closed
- PR #36 Squash and merge 완료
- Squash Commit: `b99c9c9`
- PR #36 CI 성공
- Merge 후 `main` Push CI 성공
- HTTP Adapter `main` 반영 완료
- 명시적으로 주입한 Transport를 통해서만 HTTP 처리를 수행하는 Adapter 구현
- Fake Transport로 정상·오류·Timeout·Redirect 거부와 5 MiB 응답 상한 검증 완료
- 실제 실행 CLI는 구현하지 않음
- 실제 `.env`와 실제 API Key를 사용하지 않음
- 실제 DNS·socket·HTTP 요청 0회
- 실제 `POI072` 응답은 수집하지 않음
- Project Guard: PASS 35, FAIL 0, WARN 0, SKIP 10, TOTAL 45, EXIT_CODE 0
- Unit Tests: Ran 107 tests, OK
- Issue #34 완료 당시에는 EG-4 전체 통과 전 상태였음

### 6.10 POI072 단일 실행 CLI 오프라인 구현 — Issue #39 / PR #40

- Issue #39 Closed
- PR #40 Squash Merge 완료
- Squash Commit: `3040242e5bf23b2eee5ef15b118ce4fd46e41597`
- PR #40 CI 성공
- Merge 후 `main` Push CI 성공
- `freshmanager/live.py`에 `python3 -m freshmanager.live` 실행 경로 구현
- 장소코드는 `POI072`로 고정하고 요청은 최대 한 번만 수행
- 필수 옵션은 `--env-file`, `--output-root`, `--execute-live`이며 Timeout 기본값은 10초
- `--execute-live` 누락 시 설정·Transport·Request·출력과 네트워크 접근 0회
- 설정 오류는 `config_error`, `raw_file_path=null`인 공식 8개 메타데이터로 기록
- Fake Transport와 임시 Dummy `.env`를 사용한 오프라인 검증 완료
- Project Guard: PASS 35, FAIL 0, WARN 0, SKIP 10, TOTAL 45, EXIT_CODE 0
- Unit Tests: Ran 120 tests, OK
- Issue #39 로컬·원격 작업 Branch 삭제 완료
- 단일 실행 CLI `main` 반영 완료
- 실제 프로젝트 `.env`를 열람·사용하지 않았고 실제 API Key 사용과 DNS·socket·HTTP 요청 0회
- 실제 `POI072` 응답은 수집하지 않음
- 공식 CSV·JSON 해시 변경 없음
- Issue #39 완료 당시에는 실제 호출 전이어서 EG-4 전체 통과 전 상태였음

### 6.11 POI072 실제 수집과 EG-4 PASS — Issue #43 / Issue #44 / PR #45

- Issue #43의 PM 승인 범위에서 로컬 Python으로 POI072 실제 단일 수집 수행
- 최초 인증 오류 응답을 원본으로 보존하고 민감정보 없이 실패 기록
- Issue #44와 PR #45에서 XML 서비스 오류를 `api_error`로 분류하도록 보완
- Squash Commit: `b596d85bbe4b4b1898b4846378b978c5ea31e120`
- 보완 후 POI072 정상 JSON과 원본·메타데이터 저장 확인
- PM이 EG-4 PASS 확정, Issue #43 완료

---

## 7. 완료 이력 — Issue #16 CI 보강

### 7.1 기본 정보

- Issue: #16 종료
- Pull Request: #20 Squash and merge 완료
- 작업명: GitHub Actions에서 Python Harness 자동 실행
- Workflow: `.github/workflows/harness.yml` 구현 완료(당시 경로, 현재 공식 경로는 `.github/workflows/ci.yml`)
- 검증 결과:
  - `pull_request` Trigger 실행 성공
  - `main` Push Trigger 실행 성공
  - Harness 실행 성공
  - 단위 테스트 실행 성공
- 정리 결과:
  - GitHub 원격 작업 Branch 삭제 완료
  - 로컬 Issue #16 Branch 삭제 완료
  - 로컬 `main` 최신화 완료
- Branch 보호 규칙: 아직 미적용
- Issue #16 완료 당시 후속 진행 Issue: 없음

### 7.2 이 작업을 쉬운 말로 설명하면

Issue #16 전에는 사용자가 직접 명령어를 실행해야 검사가 시작됐다.

이제 다음 상황에서 GitHub가 검사를 자동 실행한다.

```text
Pull Request 생성 또는 갱신
→ GitHub가 Harness와 단위 테스트 자동 실행
→ 성공 또는 실패 표시
→ 성공한 경우에만 PM이 Merge 검토
```

### 7.3 Issue #16 당시 자동 실행 명령

```bash
python3 scripts/harness_check.py
python3 -B -m unittest discover -s tests -p "test_*.py" -v
```

### 7.4 구현 파일

- `.github/workflows/harness.yml`(당시 경로)
- `docs/testing/QUALITY_GATES.md`

### 7.5 적용 결과

| 항목 | 적용 내용 | 이유 |
|---|---|---|
| CI Python 버전 | `3.12` | 지원되는 Python 버전으로 자동검사 실행 |
| GitHub Action 참조 | `actions/checkout@v6`, `actions/setup-python@v6` | 공식 주 버전 사용 |
| 권한 | `contents: read` | 저장소 읽기 최소 권한만 허용 |
| Secret·`.env` | 사용하지 않음 | 오프라인 Project Guard와 단위 테스트만 실행 |
| Branch 보호 규칙 | 미적용 | 별도 승인과 설정이 필요한 후속 운영 범위 |

### 7.6 Issue #16에서 변경하지 않은 범위

- Harness 검사 로직 추가·변경
- 단위 테스트 변경
- 실제 서울시 API 호출
- API Key 또는 GitHub Secret 등록
- `.env` 생성·열람
- 외부 Python 패키지 설치
- Matrix
- Cache
- Artifact 업로드
- Branch 보호 규칙 변경
- EG-4 기능 구현

---

## 8. 저장소 작업일지 폐기 상태

저장소 최상위 `work log/`는 Issue #47의 PM 승인에 따라 작업 Branch에서
전체 제거했다. 내부 파일명과 내용은 문서나 검사 결과에 기록하지 않는다.

처리 원칙:

- 신규 개인 작업일지는 저장소 밖에서 관리한다.
- `.gitignore`의 정확한 `/work log/` 규칙 하나로 경로 재생성을 방지하며,
  유사·중첩·일반 로그 또는 다른 정상 프로젝트 경로를 포함하는 광범위 규칙은 금지한다.
- 기존 추적 항목을 허용하는 Legacy 예외는 없다.
- 현재 삭제 전환에서는 부모 Commit의 기존 추적 항목 전부가 이름 비노출 삭제
  Diff로 남으며, 승인된 후속 Stage와 Commit 뒤 정상 추적 항목 수는 0이 된다.
- 병합 후에는 디렉터리·추적·미추적·Stage·Working Tree 항목이 모두 0이어야 한다.
- 보호 내부 파일명·상대경로·내용·크기·해시를 열거하거나 출력하지 않는다.
- Git stdout·stderr는 캡처 후 원문을 출력하지 않고, 보호 상태는 Boolean과 숫자로만
  보고한다.
- H-206은 EG-3 이후 활성 상태로 유지하며 현재 Project Guard는 `TOTAL=46`이다.
- Git 이력 재작성은 하지 않는다.
- PR #48은 Issue #47 해결과 전체 회귀검증 전까지 Merge 보류다.
- Issue #47 구현·검증에서는 실제 API 호출과 EG-5 대표 3장소 수집을 수행하지 않는다.

---

## 9. 기술 원칙을 비개발자 관점으로 설명

### 9.1 Python을 사용하는 이유

Python이 유일한 언어라서가 아니다.

현재 작업이 다음과 같기 때문에 선택했다.

- CSV 읽기
- JSON 읽기
- 파일 확인
- 값 비교
- 자동 테스트
- 이후 데이터 수집과 분석

Python은 이 작업을 외부 패키지 없이 비교적 단순하게 수행할 수 있다.

최종 웹서비스까지 Python으로 개발하기로 결정한 것은 아니다.

### 9.2 현재 의존성 원칙

- Python 표준 라이브러리만 사용
- `pip install` 불필요
- pandas 사용 안 함
- openpyxl 사용 안 함
- 별도 테스트 프레임워크 사용 안 함

### 9.3 데이터와 보안 원칙

- 공개 데이터만 사용한다.
- API Key는 Git에 Commit하지 않는다.
- `.env` 내용은 문서, 로그, PR에 노출하지 않는다.
- CI에서는 실제 서울시 API를 호출하지 않는다.
- 원본 데이터와 가공 데이터를 구분한다.
- 공식 기준 CSV·JSON을 임의로 바꾸지 않는다.

---

## 10. PoC 핵심 전제

### 10.1 서울 실시간 도시데이터

- 공식 자료마다 장소 수 표기가 다를 수 있다.
- 장소 수를 임의로 하나의 숫자로 단정하지 않는다.
- 실제 API 응답과 공식 장소 목록을 기준으로 확인한다.
- 실시간 인구와 서울시 제공 예측값을 함께 검토한다.
- 유동인구가 많다고 판매가 반드시 증가하는 것은 아니다.

### 10.2 S-DoT

- 모든 지점이 동일한 센서 방식이 아니다.
- 정확한 유동인구 값이라고 단정하지 않는다.
- 실제 센서 위치와 커버리지 확인에 한계가 있다.

### 10.3 생활인구

- 서울 전역 비교에는 유용하다.
- 실시간 데이터가 아니다.
- 지점 단위 추천에는 시간·공간 해상도 한계가 있다.

### 10.4 현재 검증 가능한 가설

- 데이터 수집 가능성
- 누락 없이 반복 수집 가능한지
- 시간대별 변화가 구분되는지
- 예측값과 실제 관측값을 비교할 수 있는지
- 반복 피크가 존재하는지
- 이동 가능한 시간 전에 예측값을 제공할 수 있는지

---

## 11. 현재 공식 단계 — EG-6B 구현

EG-5에서 POI019·POI013·POI014를 각각 한 번 수집했고 모두 성공했다. 저장된 결과의
데이터 구조·Feature 후보 분석과 최신 정적 자료 기반 S-DoT 커버리지 조사도 완료했다.
Issue #51과 PR #52는 그 결과를 13개 Area·Spot·S-DoT 공식 참조데이터로 정리해
`main`에 반영했다. Issue #53은 확정한 Area 패널의 단일 회차 수집을 구현한다.

### 11.1 EG-6B를 쉬운 말로 설명하면

승인된 13개 Area를 `panel_order` 순서로 한 번씩만 요청하고, 각 응답 원본과 요청
metadata를 분리해 저장한다. 한 장소의 API·Timeout·Parsing·Validation 실패는 기록한 뒤
다음 장소를 계속 처리한다. 회차가 끝나면 Collection Log와 Manifest를 만들고 SHA-256으로
입력 참조파일과 생성 산출물이 바뀌지 않았는지 확인한다.

### 11.2 확정 패널과 구현 계약

- 제안 지역: 13개
- 공식 Area 안전 매핑 승인: 13개
- PM 결정 대기: 0개
- 정확 일치: 8개
- 관련 Area 연결: 여의도역→여의도, 마곡나루역→서울식물원·마곡나루역,
  삼성역→강남 MICE 관광특구, 광화문역→광화문광장,
  을지로입구역→명동 관광특구 5개
- 판교역 대체: 뚝섬역(`POI025`)
- 대표 Spot: 지역별 1개, 총 13개
- Spot 좌표: 공식 출구 좌표가 아니라 역 중심 대리좌표 13개이며 모두 현장 검증 필요
- S-DoT 분류: 직접 3개, 인근 4개, 미지원 6개
- 수집 순서: 패널 1번부터 13번까지 고정
- 장소별 최대 호출: 1회
- 전체 최대 호출: 13회
- 자동 재시도: 0회
- 출력: raw JSON, 요청별 metadata, Collection Log, Manifest
- 무결성: SHA-256 기록과 저장 후 재검증
- 종료코드: 모두 성공 `0`, 장소별 실패 존재 `1`, 공통 오류 `2`

### 11.3 Issue #53 구현에서 하지 않는 것

- 실제 API 호출 또는 실데이터 13개 지역 수집
- 반복수집·Scheduler·자동 재시도
- Google Spreadsheet 자동백업
- S-DoT 실시간 API 연동
- 추천 점수·머신러닝·판매량 예측
- UI와 프레시매니저 위치 추적
- Feature 분석과 실제 판매효과 분석

Issue #53 구현과 오프라인 검증이 통과해도 실제 호출을 자동 승인하지 않는다. PM이 Diff,
테스트, Project Guard 결과를 검토한 뒤 실제 output root·env-file과 최대 13회 호출을 별도로
승인해야 한다. 반복수집 전에는 외장 저장장치 주기적 복사 또는 PM 승인 클라우드 폴더
주기적 백업 중 하나를 별도 Gate로 준비하며 수집 실행은 로컬 Python에 유지한다.

---

## 12. 새 AI 세션 복원 절차

### 12.1 AI가 먼저 확인할 자료

1. `PROJECT_STATUS.md`
2. `AGENTS.md`
3. `docs/engineering/CODEX_HARNESS_ARCHITECTURE.md`
4. `README.md`
5. `docs/testing/QUALITY_GATES.md`
6. `docs/testing/PROJECT_GUARD_SPEC.md`
7. 현재 GitHub Issue
8. 현재 Branch
9. `git status --short`
10. 최근 병합된 PR과 Commit

### 12.2 AI가 작업 전 보고할 내용

```text
1. 프로젝트 목적
2. 완료된 Gate
3. 현재 Issue와 Branch
4. 현재 작업 단계
5. 변경된 파일
6. 범위 밖 파일
7. 허용 범위
8. 금지사항
9. PM 결정사항
10. 사용자가 지금 해야 할 다음 행동
```

### 12.3 새 대화 시작 프롬프트

```text
저장소의 PROJECT_STATUS.md부터 읽고 프로젝트 상태를 복원해줘.

그다음 AGENTS.md, docs/engineering/CODEX_HARNESS_ARCHITECTURE.md,
README.md, QUALITY_GATES.md, PROJECT_GUARD_SPEC.md, 현재 GitHub Issue,
Branch, 최근 PR과 Git 상태를 확인해줘.

나는 비개발자 PM이다. 반드시 다음 순서로 설명해줘.

1. 지금 무엇을 하는지
2. 왜 필요한지
3. 내가 지금 해야 하는 행동
4. 복사해서 사용할 명령어
5. 실행 후 정상 결과
6. 문제가 생겼을 때 멈춰야 하는 기준

파일을 수정하거나 Git 작업을 하기 전에
읽기 전용으로 현재 상태와 다음 계획만 보고해줘.
```

---

## 13. PROJECT_STATUS.md 갱신 규칙

모든 Issue를 종료할 때 `PROJECT_STATUS.md` 영향 여부를 반드시 판정한다.
실제 문서 수정은 공식 프로젝트 상태에 영향이 있을 때만 수행하며,
갱신이 불필요하면 그 사유를 Issue 또는 Pull Request에 기록한다.

### 13.1 갱신 필요 조건

다음 중 하나 이상이 변경되면 갱신한다.

- 공식 작업 단계 또는 주요 작업축
- Engineering Gate 또는 Codex Engineering Harness 단계
- 공식 파일 경로, 실행 명령 또는 Workflow
- 완료된 주요 Issue, Pull Request 또는 Commit
- 다음 공식 행동이나 우선순위
- PM이 확정한 운영정책
- 위험, 제약 또는 외부 실행 승인 상태
- 새 AI 세션의 상태 복원에 필요한 핵심 사실

단순한 Issue 시작·종료 또는 작업 Branch 변경만으로는 자동 갱신하지 않는다.

### 13.2 갱신 불필요 조건

다음 변경만 있고 공식 상태, 다음 행동과 위험이 그대로라면 갱신하지 않는다.

- 내부 구현 세부사항 또는 결과에 영향 없는 리팩터링
- 테스트 내부 정리
- 문체, 오타 또는 서식 수정
- 상태 변화 없는 CI 재실행
- 공식 경로와 계약을 바꾸지 않는 유지보수

### 13.3 갱신 책임

- PM은 공식 상태 영향과 완료 여부를 최종 판단한다.
- Codex는 영향 분석, PM이 승인한 내용의 반영과 문서 정합성 검증을 담당한다.
- GitHub CI는 Project Guard와 Unit Tests의 성공·실패 증거만 제공하며,
  프로젝트 완료 또는 공식 상태를 판단하지 않는다.
- 확인되지 않은 작업을 완료로 표시하지 않는다.

### 13.4 반영 시점

- 상태 영향이 Merge 전에 확정되면 원칙적으로 같은 Pull Request에 반영한다.
- Merge 후에만 확정되는 중요한 정보는 별도 상태 갱신 Issue에서 반영한다.
- 모든 Issue마다 별도 상태 갱신 Issue를 자동 생성하지 않는다.
- Merge 후에는 `main` 기준으로 상태 영향과 문서 내용을 다시 확인한다.

---

## 14. 현재 다음 행동

### 14.1 공식 진행 중인 작업

- 공식 진행 Issue: #53
- 공식 작업 Branch: `feature/issue-53-eg6b-single-collection`
- 기준 `main`: `289bd18a5b870bc6dfde1ca18febbc48a948b8dc`
- 현재 작업: 승인 13개 Area 단일 회차와 Batch 무결성 증거 오프라인 구현
- 실제 API 호출: Issue #53 구현 중 0회

### 14.2 다음 행동 — Issue #53 검토

1. 승인된 7개 파일만 변경됐는지 Diff를 읽기 전용으로 검토
2. EG-6B Target Tests, 전체 Unit Tests와 Project Guard 결과 확인
3. H-706의 13개 순서·1회 호출·소요시간·성공·실패·Manifest 검증 확인
4. 비밀정보·실데이터·외부 네트워크 사용이 없는지 확인
5. 별도 승인 후 Stage·Commit·Push·PR 진행
6. `main` 반영 후 다시 검증하고 별도 PM 승인으로 실제 최대 13회 호출

### 14.3 다음 제품 Engineering Gate

- EG-6B: 구현·오프라인 검증 후 별도 승인으로 확정된 13개 Area 단일 수집
- EG-7: 동일 패널 반복수집 파일럿; 실행 전 주기와 백업 방식 PM 승인 필요
- EG-8: 반복 관측 결과를 이용한 Feature 유효성 분석
- 121장소 확대는 위 MVP 검증 이후 후속 범위로 검토

---

## 15. 마지막 갱신 정보

- 문서 버전: 1.16
- 마지막 갱신일: 2026-07-21
- 공식 진행 Issue: #53
- 공식 기준 Branch: `main`
- 기준 Commit: `289bd18a5b870bc6dfde1ca18febbc48a948b8dc`
- 공식 작업 Branch: `feature/issue-53-eg6b-single-collection`
- 현재 Engineering Gate: EG-6B 구현 진행 — 실제 호출 전 오프라인 검증
- 현재 단계: 13개 단일 회차·Batch Log·Manifest·SHA-256 구현과 검증
- 완료된 최근 작업:
  - Issue #28 완료 및 PR #29 Squash and merge 완료
  - Squash Commit `0201eee`
  - PR CI와 `main` Push CI 성공
  - Project Guard 공식 명칭·파일명·경로 전환 완료
  - Codex Engineering Harness P3~P7 완료
  - Issue #32 EG-4 오프라인 수집기와 Project Guard 7개 runner 구현
  - Issue #34 Closed 및 PR #36 Squash and merge 완료(`b99c9c9`)
  - PR #36 CI와 Merge 후 `main` Push CI 성공
  - HTTP Adapter `main` 반영 및 Project Guard 35개 PASS·Unit Tests 107개 OK
  - Issue #39 Closed 및 PR #40 Squash Merge 완료(`3040242e5bf23b2eee5ef15b118ce4fd46e41597`)
  - PR #40 CI와 Merge 후 `main` Push CI 성공
  - POI072 단일 실행 CLI와 Fake Transport 기반 오프라인 검증 `main` 반영 완료
  - Project Guard 35개 PASS·Unit Tests 120개 OK
  - Issue #39 로컬·원격 작업 Branch 삭제 완료
  - Issue #43 PM 승인 실제 POI072 정상 JSON 수집 및 EG-4 PASS
  - Issue #44·PR #45 XML 서비스 오류를 `api_error`로 안전하게 분류, Commit `b596d85`
  - Issue #46·#47과 PR #48·#49 main 반영, 기준 Commit `92e4512e`
  - EG-5 대표 3장소 실제 수집 3건 성공·재시도 0회
  - EG-5 데이터 구조·Feature 분석과 S-DoT 커버리지 조사 완료
  - Issue #51·PR #52로 EG-6A 13개 Area·Spot·S-DoT 참조 패널 main 반영
- 다음 행동: Issue #53 구현 Diff와 오프라인 검증 결과 검토
- 다음 공식 단계: Stage·Commit·PR 승인 후 별도 실제 13개 호출 승인
- 실제 서울시 API 호출: Issue #53 구현 중 0회
