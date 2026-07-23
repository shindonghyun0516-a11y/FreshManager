# Quality Gates

## 1. 문서 목적

이 문서는 Freshmanager 데이터 타당성 PoC의 엔지니어링 품질 게이트
EG-0부터 EG-8까지의 순서, 진입조건과 통과조건을 정의한다.

검사 ID, PASS·FAIL·WARN·SKIP 판정과 종료 코드는
`PROJECT_GUARD_SPEC.md`를 유일한 기준으로 사용한다.

제품 목적·범위·수용 기준은 `docs/product/FreshManager_PRD_v1.0.md`, 현재 구현과
목표 기술 계약은 `docs/engineering/FreshManager_TRD_v1.0.md`를 따른다. 이 문서는
두 기준을 재정의하지 않고 다음 단계 진입·통과 조건만 소유한다.
현재 Branch·PR·Issue·실행·검증 상태는 [`PROJECT_STATUS.md`](../../PROJECT_STATUS.md)를
단일 기준으로 사용한다.

---

## 2. 게이트 명칭과 PM 승인

EG-0~EG-8은 구현 준비도와 엔지니어링 품질을 판정하는 게이트다.
Recommendation MVP Workstream은 `PLANNED`, Gate number `NOT_ASSIGNED`이며 PM이
별도로 승인하기 전에는 공식 Engineering Gate가 아니다.
Gate A·Gate B·Gate C는 데이터 PoC 판정을 위한 별도 게이트다.

- 어떤 EG의 통과도 Gate A·B·C 통과를 뜻하지 않는다.
- Gate A·B·C를 EG 명칭으로 바꾸거나 서로 대체하지 않는다.
- Gate A·B·C의 구체 판정기준은 해당 제품·검증 문서를 따른다.

검사 실행, 읽기 전용 확인과 판정 자체에는 PM 승인이 필요하지 않다.
다음 작업은 PM 명시 승인 후 진행한다.

- 품질 게이트 통과 후 다음 구현 단계로의 전환
- 실제 서울시 API 호출
- 새로운 패키지 또는 라이브러리 설치
- 기준파일 생성·배치·교체·변경
- 데이터 저장구조 변경
- API 호출주기 결정 또는 변경
- 자동실행 구성 또는 변경
- GitHub main 브랜치 병합

EG-1과 EG-2의 읽기 전용 사전검증에는 Project Guard가 필요하지 않다.
파일 생성·배치, 샘플 취득을 위한 실제 호출과 이후 구현 전환은 별도 승인 대상이다.

---

## 3. 전체 순서와 현재 상태

### 현재 게이트 상태 기준

```text
EG-0 문서 기준선
→ EG-1 장소 기준데이터 사전검증
→ EG-2 샘플 JSON 사전검증
→ EG-3 Project Guard 구현 및 자동 재검증
→ EG-4 여의도 1장소
→ EG-5 대표 3장소
→ EG-6A 13개 Area·Spot 패널
→ EG-6B 동일 13개 Area 단일 수집
→ EG-7 동일 13개 반복수집 파일럿
→ EG-8 Area Feature + 승인·확보된 경우 S-DoT Feature + Spot Candidate Evaluation
→ 후속 Recommendation MVP Workstream(PLANNED, Gate number NOT_ASSIGNED)
→ 121장소 확대 후속 검토
```

현재 게이트와 완료·대기 상태는 `PROJECT_STATUS.md`에서만 관리한다. 완료 이력으로
`EG-1 | 통과:` 공식 CSV 정비·검증, EG-4는 Issue #43, EG-6A는 PR #52,
EG-6B 구현은 PR #54, 독립 Backup Worker는 Issue #60·PR #61, 첫 실제 Batch와
최종 Closeout은 Issue #57·PR #68에서 각각 정리됐다. EG-7 구현 범위는 Issue #69에서
승인됐고 Issue #70의 동일 PR에서 Controller와 파생 인덱스를 함께 구현한다.

GitHub Actions Workflow는
구현되어 Base Branch와 관계없이 모든 Pull Request와 `main` Push에서 Project Guard와
단위 테스트를 자동 실행한다. Stacked·Draft Pull Request도 같은 CI Gate를 통과해야
하며, Branch 필터 때문에 Workflow run이 생성되지 않은 상태는 `IN_PROGRESS`가 아니라
`NOT_TRIGGERED_BY_BRANCH_FILTER`로 분류하고 CI 없이 Merge하지 않는다. 첫 Pull Request에서
`pull_request` Trigger를 검증하고, Merge 후 `main` Push Trigger를 검증한다.
EG-6A의 13개 제안 지역 Area·Spot·센서 참조에서 삼성역은 강남 MICE 관광특구,
광화문역은 광화문광장, 을지로입구역은
명동 관광특구와 공식 공간 관계를 조건으로 연결해 서로 다른 공식 Area 13개를 승인했다.
모든 좌표와 S-DoT 등급은 실제 출구가 아니라 역 중심 대리좌표 기준이다.

EG-6A에서 기존 `H-703`을 13지역 참조데이터 무결성 검사로 활성화했고, EG-6B
구현과 함께 `H-706`을, Backup Worker 계약에서 `H-708`을 로컬 복사 무결성
검사로 정의했다. EG-7 오프라인 구현에서는 기존 `H-707`을 5분·1시간·12회차,
13 Area·최대 156호출·재시도 0회와 할당량 미확인 Live 차단을 확인하는 검사로
활성화한다. 검사별 현재 PASS·SKIP과 집계는 `PROJECT_STATUS.md`를 따른다.

---

## 4. EG-0 문서 기준선

### 목표

여섯 기준 문서의 역할, 구조, 규칙과 현재 상태를 확정한다.

### 판정 방법

Python 기반 Project Guard를 만들거나 실행하지 않고 문서만 검사한다.

### 통과조건

- 여섯 문서가 존재하고 비어 있지 않다.
- 모든 코드 블록이 닫히고 Markdown 제목 구조가 정상이다.
- 프로젝트 목표, 수집 범위와 분석 범위가 일치한다.
- 유일한 공식 CSV의 경로·역할과 배치·검증·EG-1 상태가 일치한다.
- 메타데이터, 환경변수, 보안, 원본·예측·날씨·상권 규칙이 일치한다.
- EG 순서와 PM 승인 범위가 일치하고 품질 게이트 순환이 없다.
- `PROJECT_GUARD_SPEC.md`만 검사 ID를 정의한다.
- 일반 테스트와 실제 API 호출이 분리돼 있다.
- 완료·미완료 표현이 실제 파일 상태와 일치한다.
- 여섯 문서 사이에 남은 규칙 충돌이 없다.

### 관련 검사 기준

`H-001`부터 `H-004`까지를 읽기 전용 문서 검사 기준으로 사용한다.

### 다음 단계

PM이 EG-0 판정을 확인한 뒤 EG-1 읽기 전용 사전검증으로 진행한다.

---

## 5. EG-1 장소 기준데이터 사전검증

### 목표

유일한 공식 장소 기준파일인 CSV를 수집기와 Project Guard의 입력으로
사용할 수 있는지 확인한다.

### 판정 방법

Project Guard 구현 전에 파일을 수정하지 않고 읽기 전용으로 확인한다.
관련 Project Guard PASS를 요구하지 않는다.

### 입력

```text
data/reference/seoul_121_places.csv
```

### 통과조건

- 지정 경로에 공식 CSV가 존재한다.
- BOM 유무와 관계없이 `encoding="utf-8-sig"`, `newline=""`와 표준
  라이브러리 `csv`로 UTF-8 파일을 읽을 수 있다.
- CSV 헤더가 `CATEGORY`, `NO`, `AREA_CD`, `AREA_NM`, `ENG_NM`의 정확한
  5개 컬럼과 순서이며 데이터 행이 정확히 121개다.
- `AREA_CD` 결측이 없고 중복이 없으며 `AREA_NM` 결측이 없다.
- `AREA_NM`이 여의도인 행의 `AREA_CD`가 `POI072`다.
- `CATEGORY` 결측이 없고 모든 값이 관광특구, 고궁·문화유산,
  인구밀집지역, 발달상권, 공원 중 하나다.
- 분류별 건수는 관광특구 7, 고궁·문화유산 5, 인구밀집지역 48,
  발달상권 28, 공원 33이며 합계가 121이다.
- 검증 직전·직후 공식 CSV의 SHA-256이 같고 파일을 다른 형식으로 변환하지 않는다.

### 관련 검사 기준

`H-101`부터 `H-108`, `H-111`, `H-112`까지를 EG-1의 필수 읽기 전용
데이터 사전검증 기준으로 사용한다. 수집기와 Project Guard 코드가 없는 EG-1에서는
`H-109`와 `H-110`을 사유를 기록해 `SKIP`한다. 두 검사는 EG-3부터
PASS·FAIL 필수검사이며 `WARN`이나 `SKIP`으로 처리할 수 없다.

### 실패 시

자동 보정, 장소코드 생성과 수집 진행을 금지하고 PM에게 차이를 보고한다.

### 다음 단계

EG-1 판정 확인 후 EG-2 샘플 JSON 읽기 전용 사전검증으로 진행한다.

---

## 6. EG-2 샘플 JSON 사전검증

### 목표

네트워크 없이 실제 응답 구조를 반복 확인할 여의도 샘플을 확보한다.

### 판정 방법

Project Guard 구현 전에 샘플을 수정하지 않고 표준 `json`으로 읽기 전용 확인한다.
관련 Project Guard PASS를 요구하지 않는다.

### 입력

```text
data/samples/population_yeouido_sample.json
```

위 파일만 공식 여의도 실응답 샘플로 사용한다. `tests/fixtures/`는 결측 필드,
잘못된 JSON, 빈 예측 배열 등 오류 테스트 입력에만 사용하며 공식 샘플을
이동하거나 복사하지 않는다.

### 통과조건

- 기준 경로에 샘플 JSON이 존재하고 문법이 정상이다.
- `AREA_NM`, `AREA_CD=POI072`와 확인된 인구 필드가 있다.
- `FCST_YN=Y`이면 미래예측 배열과 확인된 필수 예측 필드가 있다.
- 실제 API 키와 인증키가 포함된 URL이 없다.
- 샘플은 원본 응답 구조를 임의 변경하지 않았다.
- 검증 중 네트워크와 실제 서울시 API를 호출하지 않는다.

### 관련 검사 기준

`H-301`부터 `H-304`까지를 읽기 전용 사전검증 기준으로 사용한다.
공식 경로를 실제 파일과 통일한 뒤 재검증한 결과 네 검사가 모두 PASS해
EG-2를 통과했다.

EG-3 통과 전에는 샘플 신규 취득을 위한 실제 API 호출도 하지 않는다.
현재 공식 샘플은 기존 실제 응답을 구조 변경 없이 오프라인으로 배치한 파일이며,
배치와 검증 과정에서 실제 API를 새로 호출하지 않았다.

### 다음 단계

EG-1과 EG-2가 통과되고 PM이 다음 구현 단계 전환을 승인한 뒤 EG-3로 진행한다.

---

## 7. EG-3 Project Guard 구현 및 자동 재검증

### 목표

EG-0부터 EG-2까지의 기준을 반복 가능한 자동검사로 다시 검증한다.

### 진입조건

- EG-0, EG-1, EG-2 통과
- PM의 EG-3 구현 단계 전환 승인

### 통과조건

- `scripts/project_guard_check.py`가 구현돼 있다.
- `PROJECT_GUARD_SPEC.md`의 EG-3 적용 대상 필수검사를 모두 실행한다.
- 문서, 공식 CSV와 샘플 JSON을 자동 재검증한다.
- 공식 CSV는 `utf-8-sig`와 표준 `csv`로 읽고 `openpyxl`을 사용하지 않는다.
- `H-109`와 `H-110`을 PASS·FAIL 필수검사로 실행하며 `WARN`이나 `SKIP`으로 처리하지 않는다.
- 공식 CSV는 읽기 전용이며 `H-111`에서 검증 직전·직후 SHA-256이 같은지 자동 확인한다.
- `H-112`에서 `CATEGORY` 허용값과 관광특구 7, 고궁·문화유산 5,
  인구밀집지역 48, 발달상권 28, 공원 33, 합계 121을 자동 확인한다.
- EG-3에 적용되는 `H-101`부터 `H-112`까지의 장소 기준데이터 필수검사가
  모두 PASS해야 한다.
- 실제 `.env`를 생성하거나 실제 인증키를 저장하지 않고 임시 fixture와 가짜 키만 사용한다.
- 일반 Project Guard와 테스트의 네트워크·실제 API 호출이 0회다.
- 적용 대상 필수검사가 모두 PASS이고 종료 코드가 `0`이다.
- `H-206`은 보호 경로를 순회하거나 이름을 출력하지 않고 폐기 상태와 Git 비교를
  검사하며 EG-3 이후 `SKIP`할 수 없다.
- 아직 적용되지 않은 기능 검사는 사유를 기록해 SKIP할 수 있지만,
  EG-3 필수검사는 SKIP할 수 없다.
- 결과를 `PROJECT_GUARD_REPORT_TEMPLATE.md` 형식으로 기록한다.

### 다음 단계

EG-3 오프라인 Project Guard 통과 후 PM의 EG-4 단계 전환과 여의도 1장소
실제 호출 승인을 각각 받은 뒤 EG-4로 진행한다.

---

## 8. EG-4 여의도 1장소

### 진입조건

- EG-3 통과
- PM의 EG-4 구현 단계 전환 승인

### 통과조건

- 공식 CSV에서 읽은 `POI072` 한 장소만 처리한다.
- 샘플 또는 가짜 응답 기반 일반 테스트와 적용 Project Guard 검사를 통과한다.
- EG-3 오프라인 Project Guard 통과와 별도 PM 외부 실행 승인 후에만 실제 `.env`와 인증키를 사용한다.
- `.env` 로더, 키 마스킹, 원본 새 파일, 최소 메타데이터와
  예측 스냅샷 보존을 검증한다.
- PM이 별도 승인한 단일 실제 호출은 일반 테스트와 구분해 실행·보고한다.
- 실제 호출 결과의 성공·실패와 남은 위험을 보고한다.

Issue #32에서는 `freshmanager/`의 POI072 오프라인 수집기와 Fake Client 기반
검증까지만 구현한다. 실제 HTTP Adapter, 실제 `.env` 사용과 단일 실제 호출은
Issue #32가 `main`에 병합된 뒤 별도 Issue와 PM 외부 실행 승인으로 진행한다.
따라서 Issue #32 완료는 EG-4 오프라인 구현 완료를 뜻하며 EG-4 전체 통과나
EG-5 진입 승인을 뜻하지 않는다.

Issue #34에서는 HTTP Adapter, 명시적 Transport 주입, Redirect 거부와 5 MiB 응답
상한을 구현하고 Fake Transport로만 검증한다. 실제 실행 CLI, 실제 `.env`·API Key
사용과 실제 호출은 포함하지 않으며, Issue #34 완료도 EG-4 전체 통과를 뜻하지 않는다.

Issue #39와 PR #40을 통해 `python3 -m freshmanager.live` 실행 CLI가 `main`에 반영됐다.
CLI는 기존 수집기·저장소와 명시적으로 주입한 HTTP Adapter를 조립하며, 장소를
`POI072`로 고정하고 `--execute-live`가 없으면 설정·Transport·Request·출력을 사용하지
않는다. Fake Transport와 임시 Dummy `.env`로 오프라인 검증을 완료했으며, 실제 프로젝트
`.env`는 열람·사용하지 않았고 실제 API Key와 서울시 API도 사용하지 않았다.
`--execute-live`는 PM 외부 실행 승인을 대체하지 않으며, 실제 1회 호출은 별도 Issue와
PM 승인 범위다. Issue #39 완료는
EG-4 전체 통과나 EG-5 진입을 뜻하지 않는다.

Issue #43에서는 별도 PM 승인 범위로 POI072 실제 단일 수집을 수행했다. 인증 오류
응답을 안전하게 분류하도록 Issue #44와 PR #45에서 보완한 뒤 정상 JSON과 원본·
메타데이터 저장을 확인했다. 비밀정보 노출 없이 PM이 EG-4 PASS를 확정했고,
Issue #43은 완료 처리됐다.

### 다음 단계

EG-4 통과 후 PM이 다음 구현 단계 전환을 승인하면 EG-5로 진행한다.

---

## 9. EG-5 대표 3장소

### 진입조건

- EG-4 통과
- PM의 EG-5 구현 단계 전환 승인

### 통과조건

- PM이 승인한 `POI019` 구로디지털단지역, `POI013` 가산디지털단지역,
  `POI014` 강남역을 이 순서로 각각 최대 1회 처리한다.
- 세 장소의 코드와 장소명은 공식 CSV와 일치해야 한다.
- 공통 output root 아래 `stages/eg5_representative_3`를 자동 적용하고,
  기존 EG-4 원본·메타데이터와 단계 결과를 섞지 않는다.
- Transport 호출 전에 raw·metadata 저장 root의 숨김 probe 쓰기·flush·삭제를
  확인하고 실패 시 호출 0회와 종료코드 `2`를 보장한다.
- 최초 공식 CSV SHA-256을 기록하고 장소 처리 전·후 무결성을 확인해 실행 중
  유실·변경·손상을 응답 `validation_error`와 구분한다.
- 일반 테스트와 적용 Project Guard 검사를 통과한다.
- 한 장소가 실패해도 다음 장소를 처리한다.
- 대상·성공·실패 건수와 실패 장소 목록을 보고한다.
- 자동 재시도는 0회이며 `H-702`, `H-704`, `H-705`를 활성화한다.
- 종료코드는 전체 성공 `0`, 장소별 일부·전체 실패 `1`, 공통 사전검사·설정·
  저장환경·안전 문제 `2`만 사용한다.
- 최종 원본과 메타데이터를 자동 삭제하지 않는다.
- 실제 API 호출은 별도 PM 승인 범위에서만 수행한다.

### 다음 단계

대표 3장소 실제 수집·분석과 PM 단계 전환 승인으로 EG-6A에 진입했다.

---

## 10. EG-6 13개 Area 패널과 단일 수집

### EG-6A 진입조건

- EG-5 통과
- PM의 EG-6A 참조데이터 구현 승인

### EG-6A 통과조건

- 13개 제안 지역을 공식 CSV와 대조하고 안전한 Area 매핑만 `approved=true`로 기록한다.
- 각 서비스 지역에 Spot Candidate Anchor Point 1개와 좌표 출처·현장검증 상태를 기록한다.
- 역 중심 대용점을 공식 출입구나 특정 출구 앞 인구로 표현하지 않는다.
- 최신 공개 측정 자료에 나타난 S-DoT 센서만 보조 연결로 인정한다.
- `H-703`과 참조 데이터 Unit Tests를 포함한 전체 오프라인 검증을 통과한다.
- 불확실한 Area는 승인 상태로 위장하지 않고 PM 결정사항으로 보고한다.
- Batch 필드 계약만 정의하며 실행 코드·반복수집·Scheduler는 구현하지 않는다.

### EG-6B 진입·구현 계약·통과조건

- 진입조건: 13개 Area가 모두 안전하게 확정되고 PM이 EG-6B 구현을 승인한다.
- 구현 완료: 확정한 13개 코드를 중복·누락 없이 각각 최대 1회 순차 처리하고,
  장소별 실패 격리·회차 집계·원본·메타데이터·Collection Log·Manifest·SHA-256을
  Fake Transport로 검증해 PR #54로 `main`에 반영했다.
- 통과조건: PM이 실제 최대 13회 단일 회차를 별도로 승인하고, 실행 결과의
  대상·성공·실패·실패 목록·원본·메타데이터·Collection Log·Manifest·SHA-256을
  검토해 PASS를 판정한다.
- 자동 재시도와 반복수집은 포함하지 않는다.
- EG-6B는 Area Observation 확보 단계이며 Spot 좌표와 S-DoT 관측값을 API 요청에
  사용하거나 Spot Candidate Evaluation을 수행하지 않는다.
- 정적 Spot/S-DoT CSV는 승인 Area 패널의 연결 무결성 입력이다. 동적 S-DoT 수집·
  후보 생성 실패는 후속 계층 책임이며 Area 호출 재시도 사유가 아니다.

실제 EG-6B Live 재진입조건:

- Issue #57의 env-file·output-root Probe PASS를 기준으로 하되 Live 직전 다시 확인한다.
- `--execute-live`에는 PM 승인 canonical `--batch-id`를 필수로 사용하고 Collector·Source
  Batch·Collection Log·Manifest·Backup Worker 입력의 ID가 일치하는지 확인한다.
- missing·invalid·기존 Source·Sync·Receipt·Lock과 충돌하는 Batch ID는 API Key 사용,
  영속 쓰기와 네트워크 전에 종료한다.
- 읽기 전용 충돌검사와 참조검증 뒤 정확한 Source Batch ID 디렉터리를 원자적으로
  예약하며, 승자 하나만 API Key와 Transport에 접근한다. 예약 직후 장치·inode·열린
  디렉터리 FD를 보존하고 설정과 모든 Batch 쓰기 전후 동일성을 검증한다. 경로 삭제·
  교체·심볼릭 링크 시 재생성하거나 새 대상을 따라가지 않고 중단한다. 불완전·중단
  예약은 자동 삭제·재사용하지 않고 Collection Log·Manifest가 없으면 Backup 비적격으로 유지한다.
- abandoned 또는 stale 예약 복구는 자동화하지 않으며 별도 PM 검토 절차가 필요하다.
- Google Drive for Desktop Sync 설치·로그인과 `FreshManager-Data/` 논리 루트 접근을 확인한다.
- 실제 계정 이메일과 동기화 절대경로는 저장소·Receipt·로그에 기록하지 않는다.
- 별도 1회 실행형 Backup Worker가 완료·부분 실패 Fake Batch를 Google Drive 로컬
  동기화 폴더에 복사하고 파일 수·Manifest SHA-256·중복·충돌·Secret 제외를 검증한다.
- Worker는 `LOCAL_SYNC_COPY_VERIFIED`까지만 기록하며 원격 업로드 완료 상태를
  생성하지 않는다. Lock·Receipt는 Sync Root 밖의 비동기화 Ledger에 둔다.
- Batch 완료 판정 직후 1회 실행형 Worker를 호출하고 중복 실행을 방지한다.
- Worker·테스트·설정이 별도 PR·CI·PM 승인으로 `main`에 병합된다.
- Backup Worker는 백업 실패를 API 재호출로 전환하지 않는다.
- Google Drive API·OAuth·SDK를 구현하지 않고 Desktop Sync에 원격 동기화를 위임한다.
- 위 조건과 Live Preflight가 통과한 뒤 PM이 최대 13회 실제 호출을 별도로 승인한다.

Backup Readiness는 EG-6B와 EG-7 사이의 선행 작업 묶음이지 EG-6C라는 새 Engineering
Gate가 아니다. 독립 Worker·H-708·실제 Sync Root·원격 동기화 확인의 현재 상태는
`PROJECT_STATUS.md`에서 확인한다. CSV Exporter는 첫 실제 Batch 품질 감사 후 별도
Issue에서 구현한다.

EG-6B 단일 수집·백업·Closeout 결과와 별도 PM 범위 승인을 받아 EG-7 오프라인
구현에 진입했다. 이는 실제 반복수집 Live 승인이 아니다.

---

## 11. EG-7 동일 13개 반복수집 파일럿

### 진입조건

- EG-6B 통과와 첫 실제 Batch 품질·Backup Closeout 완료
- PM의 5분·1시간·12회차·13 Area·최대 156호출·재시도 0회 구현 범위 승인
- Google Drive 자동 백업 Worker의 로컬 복사·무결성·원격 동기화 확인 계약 검증
- 실제 날짜·시각·API 할당량·운영 ID·계획 지문·PM Live 승인은 구현과 분리해 OPEN 유지

### 구현 계약

- 버전이 있는 불변 계획은 `pilot_run_id`, 12개 벽시계 시각과 사전 생성 UUIDv4
  Batch ID, Area 순서, 호출예산, 할당량·Live 승인 상태를 보존한다.
- `Asia/Seoul` 5분 경계 12개를 누적 오차 없이 계산한다. 늦은 회차와 이전
  Collector·즉시 Backup이 끝나지 않은 회차는 각각 `SKIPPED_MISSED`,
  `SKIPPED_OVERLAP`으로 종결하고 지연 보충수집을 하지 않는다.
- 파일럿 전역 Lock은 원자적으로 한 실행만 허용하고 stale Lock을 자동 삭제하지 않는다.
- 실행 회차는 기존 EG-6B Collector를 승인 Batch ID로 최대 한 번 호출하고,
  증거가 완결된 Batch의 Backup Worker를 최대 한 번 호출한다.
- 개별 Area 실패는 재시도 없이 기록하고 기존 Collector가 허용하는 범위에서 계속한다.
  확정된 공통 API·자격증명·스키마·할당량·저장·Backup 실패는 남은 회차를 중단한다.
- Backup 실패는 Source를 보존하고 Collector 재실행·대체 ID·재수집을 만들지 않는다.
- 모든 계획 회차는 append-only 사건 로그와 고정 12행 Slot Index에 종결상태를 남긴다.
- 실제 시도 Area만 최대 156행 Area Observation Index에 기록한다. 중복 관측시각,
  Raw SHA-256과 정렬된 Forecast 대상시각 집합은 Area별 파생 플래그로 남기며 Raw를
  삭제·병합·수정하지 않는다.
- 파생 CSV·JSONL은 canonical Batch 증거로 재생성할 수 있고 기존 Manifest에 추가하지 않는다.
- H-707은 합성 입력으로 위 계약과 `UNCONFIRMED` Live 차단을 검증한다. H-707 PASS는
  실제 할당량 확인·운영 계획 생성·PM Live 승인을 뜻하지 않는다.
- S-DoT 동적 수집, Spot 평가, Recommendation, ML 학습, 24시간 Scheduler와 영구
  백그라운드 서비스는 제외한다.

### 실제 파일럿 통과조건

- PM이 실제 날짜·시작시각·API 할당량·운영 `pilot_run_id`·12개 Batch ID·계획
  지문과 Live 실행을 별도로 승인한다.
- 동일 13개 Area만 실행하고 최대 156호출·재시도 0회·무보충·중복 보존 계약을 지킨다.
- 실제 호출량·성공률·실패율·중복률·갱신주기·Collector/Backup 소요시간·
  저장공간 증가량을 보고한다.
- 모든 적격 Batch가 `LOCAL_SYNC_COPY_VERIFIED`를 기록하고 PM이 원격 동기화를 확인한다.

### 다음 단계

충분한 반복 관측 결과와 PM 분석 단계 승인을 받은 뒤 EG-8로 진행한다.

---

## 12. EG-8 Area Feature·선택적 S-DoT Feature와 Spot Candidate Evaluation

### 목표

동일 13개 지역의 반복 관측으로 Area Feature의 재현성을 검증한다. S-DoT는 지원·
접근·수집·품질조건을 만족하는 경우에만 독립 보조 Feature로 사용한다. Area Feature,
선택적 S-DoT Feature, 공간 Context, 현장검증과 운영 제약을 결합한 Spot Candidate
Evaluation의 분석 타당성을 평가한다.

### 통과조건

- 시간대 기준선·변화율·변동성·피크 지속시간과 예측오차를 평가한다.
- S-DoT 지원·미지원 지역의 차이를 Area 대체값이 아닌 보조 근거로만 비교한다.
- 현재 Spot Master를 Candidate Anchor Point로 사용하고 고정 판매 위치로 표현하지 않는다.
- 후보 평가에 사용한 Area·선택적 S-DoT·공간·현장검증 Feature와 버전을 추적한다.
- S-DoT 미지원 6개 Area도 Area 분석과 추천 후보에서 제외하지 않는다.
- Score·가중치·임계값은 `PLANNED` 또는 `OPEN_DECISION`이며 현 단계 필수 계약이 아니다.
- 카드소비 기반 소비활동을 실제 판매량으로 표현하지 않는다.
- 판매결과나 현장 피드백이 없으면 추천 성능·판매효과를 확정하지 않는다.
- Gate A·B·C 판정과 Engineering Gate를 구분한다.

### 다음 단계

Feature와 Spot Candidate Evaluation의 유효성 및 제한을 PM이 확인한다. 후속
Recommendation MVP Workstream은 Gate number `NOT_ASSIGNED`이며 별도 PM 승인이
있을 때만 시작한다.

---

## 13. 후속 Recommendation MVP Workstream — 공식 Gate 아님

### 목표

EG-8에서 검증된 Area Feature와, 승인·확보된 경우의 S-DoT Feature 및 Candidate
Evidence Assessment를 사용해 추천 단위와 근거를 제시하는 최소 Workstream을
검토한다. 상태는 `PLANNED`, Gate number는 `NOT_ASSIGNED`다.

### 진입조건

- EG-8 통과와 Feature·후보 평가 증거 계약 확인
- SPOT 판단 근거와 AREA fallback 사유 Enum에 대한 PM 승인
- 실제 판매효과와 추천 산출물을 구분하는 표시 계약 승인

### 통과조건

- 충분하고 신뢰 가능한 Spot Candidate가 있으면 `target_level=SPOT`을 반환한다.
- 후보 근거가 부족하면 `target_level=AREA`와 `fallback_reason`을 반환한다.
- 추천 결과가 사용한 Area·선택적 S-DoT·공간 Context·현장검증 근거를 추적한다.
- 추천 실패로 원본 Area 데이터가 변경되거나 서울시 API가 재호출되지 않는다.
- 실제 판매량·판매효과·개인 최적화를 구현 또는 입증했다고 표현하지 않는다.

121장소 전체 확대는 13개 패널의 단일·반복 수집과 Feature 분석 결과를 확인한 뒤
Recommendation MVP Workstream의 데이터 필요성과 별도 PM 승인을 거쳐 후속 범위에서 검토한다.

---

## 14. Gate A·B·C 데이터 PoC 판정 게이트

Gate A·Gate B·Gate C는 EG와 독립된 데이터 PoC 판정 게이트다.
현재 세 게이트 모두 이 문서에서 통과로 판정하지 않는다.

이 문서는 Gate A·B·C의 기준을 새로 정의하지 않으며,
해당 제품·검증 문서의 기준과 PM 판정을 따른다.
