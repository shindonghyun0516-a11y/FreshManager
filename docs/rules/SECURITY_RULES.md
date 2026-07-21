# Security Rules

- 문서 상태: Draft
- 버전: v0.1.3
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-17
- 최종 수정일: 2026-07-21
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - `AGENTS.md`
  - `.gitignore`
  - `.env.example`
  - `docs/rules/GIT_WORKFLOW.md`
  - `docs/rules/CODING_RULES.md`
  - `docs/testing/PROJECT_GUARD_SPEC.md`
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 Freshmanager Data PoC에서 사용하는 인증정보, 로그, 데이터, Git 저장소, 화면 캡처 및 외부 공유자료를 안전하게 관리하는 규칙을 정의한다.

목적은 다음과 같다.

1. API 인증키가 코드·문서·로그·GitHub에 노출되는 것을 방지한다.
2. 개인정보와 민감정보를 불필요하게 수집하지 않는다.
3. 실제 수집데이터의 공개 범위를 통제한다.
4. GitHub Actions와 외부 패키지의 보안위험을 통제한다.
5. 보안사고가 발생했을 때 대응절차를 명확히 한다.

---

## 2. 정보 분류

| 등급 | 정의 | 예시 | GitHub 저장 |
|---|---|---|---|
| Secret | 외부에 공개되면 즉시 위험한 정보 | 실제 API 키, 토큰 | 금지 |
| Sensitive | 개인이나 내부 운영을 식별할 수 있는 정보 | 연락처, 인터뷰 원문 | 원칙적 금지 |
| Internal | 외부 공개 전 검토가 필요한 정보 | 미공개 분석, 운영기록 | Private에서만 검토 |
| Public | 공개 출처이며 공개 가능한 정보 | 공개 API 샘플, 공개 문서 | 검토 후 허용 |

정보 등급이 불분명하면 더 높은 보안등급으로 취급한다.

---

## 3. API 인증키 관리

서울시 API 인증키는 `Secret`으로 분류한다.

### 3.1 저장 위치

실제 키는 프로젝트 루트의 다음 파일에만 저장한다.

```text
.env
```

실제 `.env` 생성과 실제 인증키 저장은 EG-3 오프라인 Project Guard 통과 후
PM이 EG-4 진입과 실제 API 호출을 승인한 뒤에만 진행한다.

환경변수 이름:

```text
SEOUL_OPEN_API_KEY
```

예:

```env
SEOUL_OPEN_API_KEY=********
```

실제 값을 문서 예시에 작성하지 않는다.

### 3.2 예시 파일

공유 가능한 파일:

```text
.env.example
```

내용:

```env
SEOUL_OPEN_API_KEY=your_api_key_here
```

`.env.example`에는 실제 키와 유사한 값도 넣지 않는다.
`.env.example`은 EG-3 Project Guard 구현 단계에서 생성·검증하며,
그 전에는 존재를 완료조건으로 요구하지 않는다.

---

## 4. API 키 금지 위치

실제 API 키를 다음 위치에 작성하지 않는다.

- Python 코드
- JSON 설정파일
- Markdown 문서
- CSV 파일
- 테스트 코드
- 샘플 JSON
- 로그 파일
- Git Commit 메시지
- GitHub Issue
- Pull Request
- GitHub 댓글
- 화면 캡처
- 채팅 메시지
- Codex 프롬프트
- 터미널 명령 인자

---

## 5. `.gitignore` 규칙

최소 규칙:

```gitignore
.env
.env.*
!.env.example

.DS_Store
**/.DS_Store

__pycache__/
*.py[cod]
.pytest_cache/

.vscode/

data/raw/**
data/processed/**
data/quality/**
logs/**
/work log/
```

필요한 빈 디렉터리를 유지하려면 `.gitkeep`을 예외로 허용할 수 있다.

예:

```gitignore
data/raw/**
!data/raw/.gitkeep
```

---

## 6. Git 추적 확인

`.env`가 Git에서 제외되는지 확인한다.

```bash
git check-ignore -v .env
```

Git이 `.env`를 추적하고 있지 않은지 확인한다.

```bash
git ls-files --cached -- .env
```

정상 결과는 출력 없음이다.

무시된 파일의 전체 목록은 출력하지 않는다. `.env`처럼 검증이 승인된 일반 경로는
정확한 개별 pathspec으로만 확인하고, 보호 경로의 ignored·tracked·untracked·Stage·
Working Tree 상태는 H-206이 Git stdout·stderr를 캡처한 뒤 Boolean과 개수로만
보고한다. 비밀정보 스캔과 보호 경로 Git 상태 검사는 서로 분리한다.

---

## 7. API URL 관리

서울시 API URL에는 인증키가 경로에 포함될 수 있다.

전체 URL을 로그나 오류 메시지에 출력하지 않는다.

허용 예:

```text
.../********/...
```

금지 예:

```text
.../{API_KEY}/...
```

코드는 URL 출력 전에 인증키를 마스킹해야 한다.

HTTP Adapter는 자동 Redirect를 거부하고 인증키가 Redirect 대상에 전달되지 않게
한다. Request 객체, 원래 인증 URL과 Redirect 대상 URL을 출력하거나 예외에 포함하지
않으며, 실제 Transport는 명시적으로 주입된 경우에만 사용할 수 있다.

---

## 8. 로그 보안

저장소 최상위 `work log/`는 Issue #47에서 폐기한다. 이 경로에는 로그나 개인
작업일지를 새로 만들지 않고, 신규 개인 작업일지는 저장소 밖에서 관리한다.
기존 추적 항목을 허용하는 Legacy 예외는 없으며 정상 상태의 추적·미추적·Stage·
Working Tree 항목 수는 모두 0이다. 내부 파일명·상대경로·내용·크기·해시는
출력하지 않고, H-206은 경로 존재 여부와 캡처된 Git 상태·개수만 검사한다.
Issue #47의 승인된 삭제-only Diff 외 보호 경로 Commit·PR 변경은 금지하며,
과거 Git 이력은 재작성하지 않는다.

- `.gitignore`에는 정확한 최상위 `/work log/` 규칙 하나만 허용하고 유사·중첩·
  일반 로그 또는 다른 정상 프로젝트 경로까지 제외하는 광범위 규칙을 금지한다.
- H-206은 EG-3 이후 `SKIP`할 수 없는 활성 검사이며 Project Guard는 `TOTAL=46`이다.
- 보호 상태 검사의 Git stdout·stderr는 캡처 후 폐기하고 원문을 출력하지 않는다.
- H-206 실패 메시지는 내부 이름·probe 경로·Git 오류 원문이 없는 고정 문구만 사용한다.
- 보호 안전성 확인을 이유로 보호 경로를 열거나 순회하지 않는다.
- 현재 Issue #47 삭제 전환과 병합 후 항목 0의 정상 상태를 구분한다.
- PR #48은 Issue #47 해결·전체 검증·PM 승인 전까지 Merge 보류다.
- Issue #47 구현·검증에서는 실제 API 호출과 EG-5 대표 3장소 수집을 수행하지 않는다.
- 보호 정보가 출력되면 보안 절차 위반으로 처리하고 작업을 즉시 중단한다.

### 기록 가능한 정보

- `request_id`
- `endpoint_name`
- `requested_at`
- `area_code`
- HTTP 상태
- 수집 상태
- 오류 유형
- 원본 파일 경로
- 마스킹된 URL

### 기록 금지 정보

- 실제 API 키
- 전체 `.env`
- 인증키가 포함된 전체 URL
- 불필요한 원본 전체 응답
- 개인정보
- 사용자 계정 비밀번호
- GitHub 토큰
- 외부 서비스 Secret

---

## 9. 오류 메시지 보안

예외 메시지에 API 키가 포함되지 않도록 한다.
`HTTPError`와 `URLError`의 원문 문자열이나 traceback을 그대로 외부에 노출하지 않고,
인증정보가 없는 고정 오류 메시지로 변환한다.

피해야 할 예:

```python
raise RuntimeError(f"Request failed: {full_url}")
```

권장 예:

```text
API 요청 실패
endpoint_name=citydata_ppltn
area_code=POI072
status=timeout
```

오류 원인을 이해하는 데 필요하지 않은 민감정보는 출력하지 않는다.

---

## 10. 화면 캡처 규칙

화면 캡처 전 다음을 확인한다.

- `.env` 탭 닫기
- 브라우저 주소창 확인
- API URL에 키가 없는지 확인
- 터미널에 키가 출력되지 않았는지 확인
- GitHub Secret 화면이 아닌지 확인
- 개인정보가 포함되지 않았는지 확인
- 인터뷰 원문이 노출되지 않았는지 확인

인증키가 포함된 URL을 호출한 브라우저 화면은 주소창을 제외하고 캡처한다.

---

## 11. 샘플 JSON 보안

공식 샘플:

```text
data/samples/population_yeouido_sample.json
```

샘플 파일에는 다음이 없어야 한다.

- API 인증키
- API 요청 URL
- 사용자 이름
- 이메일
- 전화번호
- 설명문
- Markdown 코드 블록
- 브라우저 HTML

샘플 JSON은 실제 응답 본문만 저장한다.

---

## 12. 개인정보 및 인터뷰 자료

다음 정보는 코드 저장소에 저장하지 않는다.

- 전화번호
- 이메일
- 주소
- 주민등록번호
- 계좌정보
- 개인 식별이 가능한 인터뷰 원문
- 동의 없이 확보한 위치정보
- 개별 판매원의 실제 실적

인터뷰 자료는 필요한 최소 범위만 수집한다.

공개자료 기반 분석, 실제 인터뷰, 합성 시뮬레이션을 구분한다.

합성 답변을 실제 인터뷰 결과처럼 표현하지 않는다.

---

## 13. 저장소 공개 범위

PoC 개발 중 GitHub 저장소는 기본적으로 Private으로 관리한다.

Public 전환 전 다음을 검토한다.

- API 키 없음
- 개인정보 없음
- 내부자료 없음
- 외부 저작권 자료 없음
- 공개 가능한 데이터만 존재
- README의 표현 적절성
- 인터뷰 자료 비식별화
- 원본 대량데이터 제외

Public 전환은 PM 승인사항이다.

---

## 14. 실제 수집데이터 Git 관리

다음 데이터는 원칙적으로 GitHub에 올리지 않는다.

```text
data/raw/
data/processed/
data/quality/
logs/
```

GitHub에 포함할 수 있는 자료:

```text
data/reference/seoul_121_places.csv
data/samples/population_yeouido_sample.json
tests/fixtures/
```

단, 포함 전 민감정보 검사를 통과해야 한다.

---

## 15. GitHub Issue와 PR 보안

Issue, PR, 댓글에 다음 내용을 작성하지 않는다.

- 실제 API 키
- 인증 URL
- `.env` 내용
- 개인정보
- 내부 토큰
- 제한된 데이터 원문

오류를 설명할 때는 민감값을 마스킹한다.

```text
SEOUL_OPEN_API_KEY=********
```

---

## 16. GitHub Actions 보안

PR Project Guard는 실제 서울시 API를 호출하지 않는다.

일반 GitHub Actions에는 실제 API 키가 필요하지 않다.

향후 Secret이 필요한 경우 다음 원칙을 따른다.

- GitHub Repository Secret 사용
- 최소 권한
- Secret 출력 금지
- 외부 PR에서 Secret 사용 금지
- 승인된 Workflow에서만 사용
- 실제 API 자동호출은 별도 PM 승인

GitHub Actions에서 `.env` 파일을 생성해 Commit하지 않는다.

---

## 17. 외부 패키지 보안

새 패키지를 설치하기 전 다음을 확인한다.

1. 패키지 이름
2. 공식 배포처
3. 필요한 이유
4. 표준 라이브러리 대체 가능성
5. 유지보수 상태
6. 라이선스
7. 보안위험
8. 의존성 증가
9. PM 승인

다음 명령을 PM 승인 없이 실행하지 않는다.

```bash
pip install ...
pip3 install ...
brew install ...
npm install ...
```

---

## 18. Codex 사용 보안

Codex 프롬프트에 실제 인증키를 입력하지 않는다.

Codex에게 다음 작업을 시키지 않는다.

- `.env` 내용 출력
- 실제 키 복사
- 실제 키를 코드에 삽입
- 전체 인증 URL 보고
- 개인 연락처 수집
- 민감정보가 포함된 파일을 임의 공유

Codex는 환경변수 존재 여부만 확인하고 실제 값을 출력하지 않아야 한다.

---

## 19. Project Guard 보안검사

아래 검사는 `PROJECT_GUARD_SPEC.md`에서 현재 게이트에 적용되는 시점부터 수행한다.
Project Guard 미구현 단계의 문서 전용 작업은 읽기 전용 수동 보안검사로 대신한다.

Project Guard는 최소 다음을 검사한다.

- `.env` Git 제외
- `.env.example` 존재
- `.env.example`에 예시값만 존재
- 코드·문서에 실제 키 없음
- 로그 URL 마스킹
- 샘플 JSON에 URL 없음
- 실제 네트워크 호출 없음
- 금지된 Secret 패턴 없음
- Git 추적 대상에 `.env` 없음

정상 문자열을 실제 키로 오탐하지 않도록 검사기준을 문서화한다.

---

## 20. 보안사고 정의

다음 상황을 보안사고 후보로 본다.

- API 키가 화면 캡처에 노출
- 실제 키가 Commit에 포함
- 인증 URL이 로그에 출력
- `.env`가 GitHub에 Push
- 개인정보가 저장소에 포함
- GitHub Actions 로그에 Secret 출력
- 외부 공유자료에 민감정보 포함

---

## 21. 보안사고 대응

보안사고가 의심되면 다음 절차를 따른다.

```text
1. 추가 공유와 Push 중단
2. 노출 위치 확인
3. 노출 범위 확인
4. 키 폐기·재발급 필요 여부 판단
5. Git 추적 여부 확인
6. GitHub Commit·PR·Actions 로그 확인
7. 민감정보 제거
8. 필요 시 Git 이력 정리
9. 원인 기록
10. Project Guard 또는 규칙 보완
11. PM 최종 확인
```

최신 파일에서 문자열만 삭제해도 과거 Commit에 남아 있을 수 있다.

Git 이력 정리는 위험한 작업이므로 PM 승인 후 수행한다.

---

## 22. Commit 전 보안 체크리스트

- [ ] 현재 Branch가 `main`이 아닌가
- [ ] `.env`가 Commit 대상이 아닌가
- [ ] 실제 API 키가 없는가
- [ ] 전체 인증 URL이 없는가
- [ ] 개인정보가 없는가
- [ ] 원본 수집데이터가 포함되지 않았는가
- [ ] 로그 파일이 포함되지 않았는가
- [ ] 폐기한 저장소 작업일지 경로가 재생성되거나 Commit에 포함되지 않았는가
- [ ] 샘플 JSON이 안전한가
- [ ] Commit 메시지에 민감정보가 없는가

확인은 다음 안전 절차로 수행한다.

1. 승인된 일반 파일을 정확한 개별 pathspec으로만 검토한다.
2. 보호 경로는 H-206을 통해 존재 여부, 항목 수, 변경 여부와 deletion-only 여부만
   확인한다.
3. Git stdout·stderr는 메모리에서 캡처하고 원문을 출력하지 않는다.
4. ignored·untracked·tracked·Stage 상세 목록과 광범위한 Staged Diff를 출력하지 않는다.
5. 보호 내부 이름이나 내용이 노출되면 Commit 검토를 즉시 중단하고 보안사고
   대응 절차를 적용한다.

---

## 23. PR 전 보안 체크리스트

- [ ] 변경 파일이 Issue 범위와 일치하는가
- [ ] Commit·PR 변경 대상에 `.env`가 없는가
- [ ] 실제 키가 없는가
- [ ] 로그에 인증정보가 없는가
- [ ] 적용 대상 Project Guard 보안검사 또는 Project Guard 미구현 단계의 문서 수동검사 통과
- [ ] GitHub Actions에서 Secret을 사용하지 않는가
- [ ] 화면 캡처가 안전한가
- [ ] 남은 보안위험을 보고했는가

---

## 24. 완료 정의

보안 검토는 다음 조건을 만족해야 완료다.

- Secret 저장 위치 준수
- Git 추적 제외 확인
- 코드·문서·로그에 실제 키 없음
- 샘플 데이터 안전
- 개인정보 미포함
- 적용 대상 Project Guard 보안검사 또는 Project Guard 미구현 단계의 문서 수동검사 통과
- 남은 위험 보고
- PM 확인 완료

---

## 25. 변경 이력

| 버전 | 날짜 | 변경내용 | 작성자 | 승인상태 |
|---|---|---|---|---|
| v0.1.3 | 2026-07-21 | ignored·Stage 원시 출력 제거와 H-206 고정 메시지·Boolean·개수 검증 정책 보강 | 신동현 | PM 승인 구현 중 |
| v0.1.2 | 2026-07-21 | 저장소 작업일지 경로 폐기, 외부 관리와 H-206 비노출 검증 정책 반영 | 신동현 | PM 승인 구현 중 |
| v0.1.1 | 2026-07-20 | HTTP Adapter의 Transport 주입, Redirect 거부, 인증 URL·네트워크 예외 비노출 규칙 반영 | 신동현 | PM 검토 전 |
| v0.1.0 | 2026-07-17 | 최초 초안 작성 | 신동현 | Draft |
