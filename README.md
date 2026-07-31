# Freshmanager Data PoC

## 1. 프로젝트 소개

이 프로젝트는 프레시매니저 유동판매 위치·시간 추천 서비스의 선행 단계인
서울시 공개데이터 기반 데이터 타당성 PoC다.

현재 단계에서는 프레시매니저가 사용하는 모바일 앱이나 추천 화면을 개발하지 않는다.

서울시 주요 121장소를 장기 공식 후보군으로 유지하되, 현재는 EG-6A에서 확정한
13개 Area 패널의 수집·분석 가능성을 먼저 검증한다. EG-6B 첫 실제 단일 회차와
백업 검증은 완료됐다. 5분은 PM이 확정한 장기 반복수집 기준이며, EG-7의 1시간·
12회차는 이 고정 주기의 첫 통제 검증이다. EG-7 Controller와 파생 인덱스는
Issue #70·PR #71로 `main`에 반영됐으며, 실제 반복수집은 별도 PM Live 승인 전까지
금지한다.

### 공식 문서 안내

새 세션은 다음 문서를 순서대로 확인한다.

1. [`AGENTS.md`](AGENTS.md) — Codex 작업 절차와 금지사항
2. [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — 현재 단계와 다음 행동의 공식 운영 상태
3. [`PROJECT_MEMORY.md`](ai-context/PROJECT_MEMORY.md) — 장기 제품 맥락과 안정적 원칙
4. [`FreshManager_PRD_v1.0.md`](docs/product/FreshManager_PRD_v1.0.md) — 공식 제품 기준
5. [`FreshManager_TRD_v1.0.md`](docs/engineering/FreshManager_TRD_v1.0.md) — 공식 기술 기준
6. 현재 GitHub Issue와 Branch·Git 상태
7. 관련 Rule·Quality·Data·Analysis 문서
8. [`DECISION_LOG.md`](ai-context/DECISION_LOG.md)의 관련 Decision
9. [`ARCHITECTURE_DECISIONS.md`](ai-context/ARCHITECTURE_DECISIONS.md)의 관련 ADR

`ai-context/`는 상태·제품·기술 정본을 대체하지 않는 복원 보조 문서다. 전체 Harness
구조는 [`CODEX_HARNESS_ARCHITECTURE.md`](docs/architecture/CODEX_HARNESS_ARCHITECTURE.md),
백업·CSV 목표계약은
[`CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md`](docs/data/CLOUD_BACKUP_AND_CSV_MANAGEMENT_PLAN.md)를 따른다.

---

## 2. 현재 검증 목표

1. 현재 13개 Area 패널을 안정적으로 수집하고 후속 필요 시 121개로 확장할 수 있는가
2. 장소별 현재 인구값과 미래 인구예측값을 모두 저장할 수 있는가
3. 같은 미래시점의 예측값을 수집시점별로 보존할 수 있는가
4. 서울시 예측값과 후속 관측값을 비교할 수 있는가
5. 장소 유형과 요일·시간대에 따른 반복 패턴이 존재하는가
6. 인구 증가와 카드소비 기반 소비활동 변화가 함께 나타나는가
7. 수집된 데이터가 향후 프레시매니저 서비스 가설 검증에 활용 가능한가

---

## 3. 수집 범위와 분석 범위

### 장기 공식 후보군

서울시 주요 121장소. 장소코드 검증과 후속 확대의 유일한 기준은 공식 CSV다.

### 현재 MVP 구현·수집 범위

- 여의도 1개 Area: 실제 수집·검증 완료
- 대표 3개 Area: 실제 수집·분석 완료
- EG-6A 13개 Area·Spot·S-DoT 패널: 확정·`main` 반영 완료
- EG-6B 동일 13개 Area 단일 회차 파이프라인: 구현·오프라인 검증·`main` 병합 완료
- 실제 EG-6B 13개 Area 단일 회차: 13/13 성공·품질 PASS·백업 무결성 PASS
- Issue #57: EG-6B 최종 Closeout 완료 후 CLOSED
- Google Drive 자동 백업: 독립 Backup Worker 구현·검증 완료, PM 원격 동기화 확인 완료
- EG-7: 5분 장기 기준 PM 확정, Controller와 ML-ready 파생 인덱스
  `IMPLEMENTATION_AVAILABLE_ON_MAIN`; 첫 1시간 Live `NOT_STARTED`
- Area-first 제품·UI·데이터 계약은 D-022·PR #141로 승인·`main` 반영됐고,
  Recommendation Core·Service도 PR #135·#137로 `main`에 있다. Area-first
  Service·API, Vue UI, FastAPI, NAVER Map, Spot Prototype Runtime과 배포는
  `NOT_IMPLEMENTED`다. 세부 변동상태는 `PROJECT_STATUS.md`를 따른다.

### 현재 분석 범위

- 여의도와 EG-5 대표 3개 Area
- EG-6A에서 확정한 13개 Area·Spot·S-DoT 패널
- Area Observation과 S-DoT 보조 Feature
- Area Feature와 선택적으로 사용할 수 있는 S-DoT Feature, 공간·현장 Context 기반
  Spot Candidate Evaluation과 스팟 이동 기회

### 공식 서비스 데이터 구조

```text
필수 Core Observation: Area Observation
선택적 Supporting Observation: 사용 가능한 경우의 S-DoT Observation
추가 Context: Spatial Context + Field Validation Status + Operational Constraints Status

Area Feature + 선택적 S-DoT Feature + 추가 Context
→ Spot Candidate Evaluation
→ 원격 Eligibility 충족: SPOT
→ Spot 근거 부족·Area 근거 충분: AREA + fallback_reason
→ Area 근거 부족: 추천 없음
```

현재 Spot Master는 확정 판매 위치가 아니라 `STATION_CENTER_PROXY` 기반 Candidate
Anchor Point다. S-DoT는 Area 데이터를 대체하거나 모든 Area에 필수인 단계가 아니며,
동적 센서 수집과 후보 근거 평가는 EG-6B Collector와 분리된 후속 책임이다. S-DoT
미지원 6개 Area도 분석·추천 후보에서 제외하지 않는다.
정적 연결의 `DIRECT_COVERAGE`, `NEARBY_SUPPORT`, `NO_NEARBY_SDOT`는 각각
DIRECT·NEARBY·UNSUPPORTED 의미의 Context로만 유지하며 EG-7 관측값으로 만들지 않는다.

### 후속 범위

EG-7 실제 반복수집, EG-8(상위, EG-8A~8E) 결과 및 후속 Recommendation
MVP Workstream의 데이터 필요성을 확인한 뒤 별도 PM 승인으로 121개 Area 확대를 검토한다.

```text
장기 후보군: 서울시 주요 121장소
현재 MVP: 1개 Area → 대표 3개 Area → 13개 Area 패널
현재 Gate: EG-6B 완료 / EG-7 구현 완료(main)·Live 독립 backlog 유지
후속 검토: EG-7·EG-8과 별도 승인된 Recommendation MVP Workstream 결과 후 필요 시 121개 확대
```

### 현재 PoC 범위에 포함하는 항목 (EG-8A~EG-8E)

- 미래 Area 인구 예측, 피크 발생 여부와 예상 피크시각
- Area Ranking, Spot Candidate Ranking, 선택적 S-DoT 보조정보
- Recommendation Output Contract
- UI/UX 정보구조·와이어프레임·프로토타입(비상용 설계 산출물)

상세 Gate 계약은 `docs/testing/QUALITY_GATES.md`를 따른다.

### 현재 제외 범위

- 판매량 예측, 매출 예측, 판매 성공확률, 제품별 수요예측, 재고 최적화
- 판매성과 인과효과 검증
- 상용 모바일 앱·웹 서비스 구현 및 출시
- 상용 지도 서비스 개발·배포
- 실시간 모델 서빙, 완성형 MLOps
- 프레시매니저 위치 추적
- 실제 판매량 수집
- 고객 개인정보 수집
- 개별 건물 또는 지하철 출구 추천
- 이동경로 최적화
- 유료 데이터
- hy 내부 데이터 연동
- 대중교통·문화행사 데이터의 필수 연동
- 프로덕션 수준의 대규모 인프라
- 호출한도 확인 전 121장소 고빈도 자동수집
- 별도 PM Live 승인 없는 실제 5분 반복수집

---

## 4. 공식 장소 목록

수집기와 Project Guard가 공통으로 사용하는 유일한 공식 장소 기준파일은 다음 CSV다.

```text
data/reference/seoul_121_places.csv
```

| 상태 | 현재 값 |
|---|---|
| 공식 CSV 배치·정비 및 `main` 반영 | 완료 |
| CSV 무결성 검증 | 읽기 전용 재검증 완료 |
| EG-1 통과 | PASS |

- XLSX 파일과 XLSX 보존 경로는 사용하지 않는다.
- CSV는 Python 표준 라이브러리 `csv` 모듈로만 읽는다.
- `encoding="utf-8-sig"`를 사용해 UTF-8과 UTF-8 BOM을 모두 처리하며,
  BOM 존재 자체를 필수조건으로 요구하지 않는다.
- 공식 CSV 처리를 위해 `openpyxl`을 사용하거나 설치하지 않는다.
- 수집기와 Project Guard는 CSV를 자동 수정·보정·정렬·덮어쓰기·재인코딩하거나
  다른 형식으로 변환하지 않는다.

공식 CSV는 `CATEGORY`, `NO`, `AREA_CD`, `AREA_NM`, `ENG_NM`의 정확한
5개 컬럼과 순서, 유효 장소 121개를 기준으로 재검증해 EG-1을 통과했다.

기준 컬럼:

| 컬럼 | 의미 |
|---|---|
| `CATEGORY` | 장소 분류 |
| `NO` | 목록 순번 |
| `AREA_CD` | 서울시 장소코드 |
| `AREA_NM` | 한글 장소명 |
| `ENG_NM` | 영문 장소명 |

공식 CSV 사용 전에는 파일 존재, UTF-8 또는 UTF-8 BOM 읽기 가능 여부,
필수 컬럼, 데이터 121행, `AREA_CD` 결측·중복, `AREA_NM` 결측,
여의도 코드와 분류별 합계 121을 읽기 전용으로 확인한다.

검증 과정에서 장소코드를 생성·보정하거나 CSV 내용을 변경하지 않는다.
기준파일 변경은 PM 승인 없이 진행하지 않는다.

---

## 5. 장소코드 사용 원칙

API 호출에는 확정 경로에 배치되고 검증을 통과한 공식 CSV의
`AREA_CD`만 사용한다.

여의도 공식 장소코드:

```text
POI072
```

`POI`는 영문 대문자 `P`, `O`, `I`다.

다음 방식은 사용하지 않는다.

```text
POI001부터 POI121까지 자동 생성
```

장소코드는 중간 번호가 비어 있을 수 있으므로
공식 파일에 실제로 존재하는 코드만 사용한다.

비슷한 이름의 장소도 별도 장소로 유지한다.

예:

```text
여의도: POI072
여의도한강공원: 별도 장소코드
여의서로: 별도 장소코드
```

---

## 6. 현재 프로젝트 상태

### 완료

- 서울 열린데이터광장 일반 인증키 발급
- 공식 장소 기준 CSV 배치
- 공식 장소 기준 CSV 정비·`main` 반영 및 EG-1 통과
- EG-0 문서 기준선 PM 승인
- 공식 여의도 실응답 샘플 `data/samples/population_yeouido_sample.json` 배치
- 공식 샘플 읽기 전용 사전검증과 `H-301`~`H-304` 통과
- EG-3 Python 기반 Project Guard `scripts/project_guard_check.py` 구현 및 로컬 검증 완료
- Issue #32 EG-4 POI072 오프라인 수집기와 Fake 기반 검증 완료
- Issue #34 EG-4 HTTP Adapter와 명시적 Transport 주입의 Fake 기반 검증 완료
- Issue #39 Closed 및 PR #40 Squash Merge 완료: POI072 단일 실행 CLI와 Fake Transport 기반 오프라인 검증 `main` 반영 완료
- Issue #43에서 POI072 실제 정상 JSON과 원본·메타데이터 저장 확인, EG-4 PASS
- Issue #46·PR #48에서 대표 3개 Area 수집기 구현·병합 및 실제 3/3 수집 완료, EG-5 PASS
- Issue #51·PR #52에서 서로 다른 공식 Area 13개와 Spot·S-DoT 참조 패널 `main` 반영
- Issue #53·PR #54에서 13개 Area 단일 순차수집·Batch Log·Manifest·SHA-256 파이프라인 구현·오프라인 검증·`main` 병합
- PR #54와 병합 후 `main` CI 성공
- Issue #60·PR #61에서 독립 Backup Worker와 H-708 구현·병합
- 첫 EG-6B 실제 Batch 13/13 성공, 품질 PASS, 로컬 복사 무결성과 PM 원격 동기화 확인 완료
- Issue #67·PR #68에서 `.DS_Store` 검증 경계 보정·병합 후 EG-6B 최종 Closeout 완료
- Issue #69에서 EG-7 5분·1시간·12회차 범위 승인
- Issue #70·PR #71에서 EG-7 Controller·파생 인덱스·H-707 구현·검증 후
  `main` 반영, Issue #70 종료
- Repository Readiness Audit을 Issue #144·PR #145로 승인·`main` 반영
- `AGENTS.md` 생성
- Codex의 `AGENTS.md` 인식 확인

`tests/fixtures/`는 결측 필드, 잘못된 JSON, 빈 예측 배열 등 오류 테스트
입력에만 사용하며 공식 실응답 샘플을 이동·복사하지 않는다.

### 진행 예정

- Repository 문서 정합화 뒤 Area-first Web/API 경계와 데이터 공급 Architecture ADR
- 실제 날짜·시각·할당량·운영 ID·계획 지문에 대한 별도 PM 결정
- PM Live 승인 후에만 동일 13개 Area의 5분·1시간 파일럿 실행 검토
- 첫 Batch 품질 감사 결과를 기준으로 Raw-to-CSV Exporter 별도 검토
- EG-8D에서 Area Feature·승인·확보된 경우의 S-DoT Feature·Spot Candidate Evaluation 검증(EG-8A~8E 상세는 `docs/testing/QUALITY_GATES.md` 참조)
- 별도 PM 승인 후 Recommendation MVP Workstream 검토(`PLANNED`, Gate number `NOT_ASSIGNED`)

### 미진행

- EG-7 실제 5분·1시간 반복수집
- 실제 운영 계획과 12개 운영 Batch ID 생성·승인
- 동적 S-DoT 수집
- Spot 자동추천·공식 Recommendation 실행
- 공식 모델 채택
- 24시간 Scheduler·영구 백그라운드 서비스·자동 재시도
- CSV Exporter
- EG-8D 선택적 S-DoT Feature와 Spot Candidate Evaluation
- Recommendation MVP의 사용자용 Runtime·공식 출력 활성화
- 121장소 자동수집
- 장기 데이터 누적
- 장기 다일자·별도 Test 기반 장소별 예측 성능 평가
- 카드소비 상권현황 분석
- Gate A·B·C 데이터 PoC 판정
- 모바일 서비스 개발

---

## 7. 데이터 대상

### 공식 Area 공통 필수 데이터

- 장소 분류
- 장소코드
- 장소명
- 실시간 추정 인구
- 현재 혼잡도
- 미래 인구예측
- API 요청시각
- 인구 데이터 기준시각
- 수집 성공·실패 상태

### 지원 장소에 한해 수집하는 데이터

- 카드소비 기반 실시간 상권현황

상권현황이 지원되지 않는 장소는 다음처럼 기록한다.

```text
not_supported
```

지원 장소이지만 해당 시점 데이터가 없으면 다음처럼 기록한다.

```text
missing
```

둘 다 `한산` 또는 `0`으로 바꾸지 않는다.

### 날씨 데이터

- 날씨 관측값
- 날씨 예보값

날씨 관측값과 예보값은 실제 제공 여부를 각각 기록하고,
한쪽이 없다고 다른 값으로 대체하지 않는다.

### 최소 수집 메타데이터

- `request_id`
- `area_code`
- `endpoint_name`
- `requested_at`
- `received_at`
- `http_status`
- `collection_status`
- `raw_file_path`

Issue #32 PM 결정에 따라 이전 최소 계약의 `parser_version` 대신
`received_at`을 사용한다.

`endpoint_name`에는 실제 URL이 아니라 `citydata_ppltn`과 같은 논리적 이름을 저장한다.
`raw_file_path`에는 원본 JSON 내용이 아니라 저장된 원본 파일 경로를 기록한다.

### 선택 데이터

- 대중교통 승하차
- 문화행사
- S-DoT 유동인구

선택 데이터는 PM 승인 없이 필수 범위로 추가하지 않는다.

---

## 8. API 호출 방식

서울시 API는 한 번 호출할 때 한 장소를 조회한다.

현재 EG-6B 단일 회차는 승인된 13개 Area를 다음 순서로 처리한다.

```text
검증된 공식 CSV 읽기
→ 장소 하나 호출
→ 원본 JSON 저장
→ 요청별 metadata 저장
→ 성공·실패 기록
→ 다음 장소 호출
→ 승인된 13개 Area까지 반복
→ Collection Log·Manifest·SHA-256 생성·검증
```

한 장소의 오류 때문에 전체 회차를 중단하지 않는다.

회차 종료 후 다음을 확인한다.

- 전체 대상 장소 수
- 성공 장소 수
- 실패 장소 수
- 실패 장소 목록
- 전체 소요시간

---

## 9. 단계적 구현 순서

| 엔지니어링 게이트 | 내용 | 현재 상태 |
|---|---|---|
| EG-0 | 문서 기준선 | 통과: PM 승인 완료 |
| EG-1 | 장소 기준데이터 사전검증 | 통과: 공식 CSV 정비·`main` 반영 및 읽기 전용 재검증 완료 |
| EG-2 | 샘플 JSON 사전검증 | 통과: 공식 샘플 배치 및 `H-301`~`H-304` PASS |
| EG-3 | Project Guard 구현 및 자동 재검증 | 구현·로컬 검증 완료: PASS 28, SKIP 17 |
| EG-4 | 여의도 1장소 | 통과: Issue #43 실제 POI072 정상 JSON과 원본·메타데이터 저장 확인 |
| EG-5 | 유형별 대표 3장소 | 통과: POI019·POI013·POI014 실제 수집 3/3, 재시도 0회와 구조 분석 완료 |
| EG-6A | 13개 Area·Spot·S-DoT 패널 | 통과: Issue #51·PR #52로 13개 고유 공식 Area 패널 `main` 반영 |
| EG-6B | 동일 13개 Area 단일 수집 | 통과: 첫 실제 Batch 13/13·품질·백업 무결성·원격 동기화 확인과 Closeout 완료 |
| EG-7 | 동일 13개 Area 반복수집 파일럿 | 구현 완료(`main`): Issue #70·PR #71; 첫 Live `NOT_STARTED` |
| EG-8(상위) | 데이터 분석·예측·추천 준비 상위 Gate(EG-8A~8E); 기존 EG-8 정의는 EG-8D가 계승 | `NOT_STARTED`; 하위 구현·실행 상태는 `PROJECT_STATUS.md` 참조 |
| Recommendation MVP Workstream | SPOT 우선·AREA fallback 추천 | `PLANNED`; Gate number `NOT_ASSIGNED`, 별도 PM 승인 필요 |

EG-1과 EG-2는 Project Guard 구현 전의 읽기 전용 사전검증이다.
공식 여의도 실응답 샘플 경로는
`data/samples/population_yeouido_sample.json`이다.
EG-3에서 문서, 공식 CSV, 샘플 JSON을 네트워크 없이 자동 재검증한다.
일반 Project Guard와 Unit Tests는 실제 `.env`·인증키·네트워크를 사용하지 않는다.
실제 실행은 각 Gate에서 env-file·output-root·호출 수를 PM이 별도로 승인한 경우에만
일반 테스트와 분리해 진행한다.
각 게이트 통과 후 다음 구현 단계로 전환하려면 PM 승인을 받는다.

EG-0~EG-8은 구현 준비도와 엔지니어링 품질을 판정한다. Recommendation MVP
Workstream은 아직 공식 Engineering Gate가 아니다.
Gate A·Gate B·Gate C는 별도의 데이터 PoC 판정 게이트이며,
어떤 EG의 통과도 Gate A·B·C 통과를 의미하지 않는다.

처음부터 121장소 자동수집과 장기실행을 동시에 구현하지 않는다.

---

## 10. 수집주기 원칙

반복수집은 `cadence_minutes=5`, `cadence_decision_status=PM_APPROVED_FIXED`,
`cadence_scope=LONG_TERM_OPERATING_BASELINE`, `cadence_change_allowed=false`인
PM 확정 장기 기준이다. 10분·15분 대안과 런타임 주기 옵션을 지원하지 않으며,
향후 변경에는 새 PM 명시 결정과 버전 계약·코드 변경 검토가 필요하다.

EG-7 첫 1시간 파일럿은 주기를 선택하는 시험이 아니라 이 고정 계약의 구현·운영
안전성을 검증한다. `Asia/Seoul` 벽시계 기준 정확히 12회차, 회차당 13 Area,
전체 최대 156호출, 재시도 0회다. 늦은 회차는
`SKIPPED_MISSED`, 이전 Collector와 즉시 Backup이 끝나지 않은 회차는
`SKIPPED_OVERLAP`으로 기록하고 지연 보충수집을 하지 않는다.

실제 날짜·시작시각·일일 운영시간대·24시간 또는 선택 시간 운영 여부·API 할당량·
용량 확인·운영
`pilot_run_id`·12개 운영 Batch ID·계획 지문과 PM Live 승인은 아직 열려 있다.
`quota_confirmation_status=UNCONFIRMED` 또는
`live_approval_status=NOT_APPROVED`이면 실제 실행을 거부한다. 첫 1시간 이후 확대
시점도 별도 결정이다. 운영시간 미결정을 주기 미결정으로 해석하지 않는다. 24시간 Scheduler,
영구 백그라운드 서비스, S-DoT 수집, Spot 평가, Recommendation과 ML 학습은 포함하지 않는다.

---

## 11. 데이터 해석 원칙

### 인구 데이터

서울시 인구값은 현장에서 직접 센 실제 인원이 아니라 추정 인구다.

사용 가능한 표현:

- 장소별 추정 인구
- 후속 시점 관측값
- 예측값과 후속 관측값의 일치도

사용하지 않는 표현:

- 정확한 실제 인구
- 현장 실측 인원
- 특정 출구의 정확한 보행량

### 상권현황

카드소비 기반 상권현황은 소비활동 대리변수다.

사용 가능한 표현:

- 카드소비 기반 소비활동 대리변수
- 상권 활동단계
- 일반 소비활동 변화

사용하지 않는 표현:

- 실제 야쿠르트 매출
- 프레시매니저 판매실적
- 실제 전체 소비금액
- 구매전환율

---

## 12. 공간 단위 해석 원칙

121장소는 서울시가 정의한 POI 영역이다.

장소별 인구값은 다음을 의미하지 않는다.

- 특정 지하철 출구의 인구
- 특정 빌딩 앞 인구
- 개별 판매지점의 보행량
- 특정 프레시매니저 담당구역 인구
- 실제 야쿠르트 구매고객 수

이름이 비슷한 장소도 임의로 합치지 않는다.

Spot은 Area 데이터와 선택적 S-DoT 또는 승인된 대리근거·공간 Context를 결합해
비교하는 구체적인 이동·판매 추천 지점이다. 후속 추천에서 D-020의 원격 근거
Eligibility를 충족한 Spot Candidate가 확인되면 `target_level=SPOT`으로 추천한다.
현장검증 불가와 운영 적합성 미확인은 제한 상태로 표시하되 원격 추천 자체를
차단하지 않는다. Spot 근거가 부족하고 Area 근거만 충분하면
`target_level=AREA`로 fallback하고 이유를 기록하며, Area 근거도 부족하면
추천하지 않는다. 현재 역 중심 대리좌표는
`field_verified=false`인 Candidate Anchor Point이며 검증된 판매 Spot이 아니다.
동적 S-DoT 관측과 Spot Candidate Evaluation 실패는 EG-6B Area 수집을 중단시키지
않는다. EG-6B가 확인하는 정적 Spot/S-DoT CSV는 승인된 13개 Area 패널의 참조
무결성 입력일 뿐 API 요청값이나 Spot 추천 결과가 아니다.

---

## 13. 원본 데이터 보존 원칙

서울시 API에서 받은 원본 JSON은 수정하지 않는다.

- 장소별 호출마다 새 파일로 저장한다.
- 기존 파일을 덮어쓰지 않는다.
- 파일명에 장소코드와 요청시각을 포함한다.
- 원본 필드명을 변경하지 않는다.
- 문자열 형태의 숫자도 원본에서는 변환하지 않는다.
- 값이 이상해 보여도 원본에서 삭제하지 않는다.
- 결측값을 임의로 `0`으로 바꾸지 않는다.
- 데이터 오류 여부는 별도 로그에 기록한다.
- 분석용 CSV에서만 형식을 변환한다.

원본 파일명 예:

```text
POI072_20260716_200000.json
```

권장 저장구조:

```text
data/raw/population/2026/07/16/POI072_20260716_200000.json
```

---

## 14. 예측 데이터 보존 원칙

미래 예측값은 최신값 하나만 남기지 않는다.

구분해야 하는 시각:

- API 요청시각
- 현재 인구 기준시각
- 예측 스냅샷 시각
- 예측 대상시각
- 후속 관측시각

같은 미래 대상시각의 예측이 여러 번 수집돼도
기존 예측값을 덮어쓰지 않는다.

공식 예측 발행시각 필드가 확인되지 않으면 임의로 만들지 않는다.

---

## 15. 날씨 데이터 원칙

날씨 관측값과 날씨 예보값은 분리 저장한다.

- 실제 관측값과 미래 예보값을 같은 CSV에 섞지 않는다.
- 예보에는 예보 발행시각과 예보 대상시각을 저장한다.
- 예측 평가에는 당시 이용 가능했던 예보값만 사용한다.
- 이후 관측된 실제 날씨를 과거 예측 입력값으로 사용하지 않는다.
- 실제 날씨는 사후 원인 분석과 예보 오차 확인에만 사용한다.
- 예보가 없다고 실제 관측값으로 대체하지 않는다.

---

## 16. API 키 관리

서울시 API 키는 비밀정보다.

실제 키는 프로젝트 루트의 `.env` 파일에만 저장하고,
`.env`는 `.gitignore`에 포함한다.

로컬 `.env`는 존재하지만 Git에서 제외돼 있다. 별도 PM 외부 실행 승인 전에는
내용을 읽거나 실제 키 존재 여부를 확인하지 않으며 실제 키를 사용하지 않는다.

실제 키를 다음 위치에 작성하지 않는다.

- Python 코드
- README
- Markdown 문서
- Git 커밋
- GitHub
- 콘솔 출력
- 오류 로그
- 인증키가 포함된 전체 URL
- 화면 캡처
- 테스트 파일

API 요청 주소를 기록할 때 인증키 부분을 마스킹한다.

```text
http://openapi.seoul.go.kr:8088/********/json/...
```

공유용 파일은 `.env.example`만 사용하고 실제 키를 넣지 않는다.

```env
SEOUL_OPEN_API_KEY=your_api_key_here
```

---

## 17. 저장 경계

- 공식 CSV·샘플·코드·문서는 Git 저장소에 둔다.
- 실제 Raw·Metadata·Collection Log·Manifest는 PM이 승인한 저장소 밖
  `output-root`에 둔다.
- EG-4·EG-5·EG-6B 결과는 단계별 하위 경로로 분리한다.
- 기존 실제 원본과 메타데이터는 자동 삭제하거나 덮어쓰지 않는다.
- `.env`는 Git 추적에서 제외하며 실제 값은 출력하지 않는다.
- 로컬 Raw·Metadata·Collection Log·Manifest가 공식 원본이다. Google Drive에는
  Google Drive for Desktop Sync 로컬 동기화 폴더를 통해 검증된 복사본을 자동 백업한다.
- Backup Root는 `FreshManager-Data/` 논리 구조만 정의한다. 실제 계정 이메일과
  동기화 절대경로는 저장소·Receipt·로그에 기록하지 않는다.
- 백업은 Collector와 분리된 1회 실행형 Worker가 Batch 완료 직후 담당한다. Worker는
  `main`에 구현돼 있으며 Google Drive API·OAuth·SDK는 제외 범위다.

---

## 18. 현재 실행방법

Python 기반 Project Guard가 `scripts/project_guard_check.py`에 구현돼 있다.
EG-7 구현에서는 `H-707`이 PM 확정 5분 장기 기준, 비 5분 계획 거부, 대안 미지원,
중복 기반 주기 변경 금지와 1시간 안전계약의 오프라인 검사로 활성화된다. 이 PASS는
실제 할당량 확인이나 Live 승인을 뜻하지 않는다.

표준 Project Guard 실행 명령:

```bash
python3 scripts/project_guard_check.py
```

단위 테스트 실행 명령:

```bash
python3 -B -m unittest discover -s tests -p "test_*.py" -v
```

일반 Project Guard와 일반 테스트는 저장된 샘플 또는 가짜 응답만 사용하며
네트워크와 실제 서울시 API를 호출하지 않는다. `freshmanager/http_adapter.py`에
실제 통신은 HTTP Adapter 안에 분리돼 있고 일반 테스트에서는 Fake Transport만
사용한다. 현재 `main`의 EG-6B CLI는 승인 패널 13개를 `panel_order` 순서로 각각
최대 한 번 처리하며 자동 재시도와 반복 실행은 없다.

EG-7 합성 계획의 엄격한 Dry-run은 다음처럼 실행한다. 이 명령은 계획과 12개
벽시계 회차를 검증할 뿐 자격증명, Collector, Backup Worker, 운영 디렉터리와
Google Drive에 접근하지 않는다.

```bash
python3 -m freshmanager.eg7 \
  --plan "$EG7_SYNTHETIC_PLAN" \
  --dry-run
```

`EG7_SYNTHETIC_PLAN`은 검토자가 준비한 합성 계획 파일만 가리켜야 하며 저장소는
운영 계획을 제공하거나 자동 생성하지 않는다. 실제 Live 실행에는 별도 PM이 승인한
날짜·시각·할당량·운영 ID·계획 지문이
모두 필요하다. 이 저장소 문서는 운영 값을 제공하거나 생성하지 않는다.

EG-6B 단일 회차 실행 명령 형식은 다음과 같다. PM이 승인한 canonical UUID 형식의
`FM_LIVE_BATCH_ID`를 먼저 준비하고, 같은 값을 Collector와 Backup Worker에 전달한다.
아래 명령은 PM이 env-file, 저장소 밖 output-root, Batch ID와 최대 13회 호출을 별도로
승인한 뒤에만 실행한다. `--execute-live` 자체는 PM 승인을 의미하지 않는다.

```bash
python3 -m freshmanager.eg6b \
  --env-file .env \
  --output-root "$FRESHMANAGER_EG6B_OUTPUT_ROOT" \
  --batch-id "$FM_LIVE_BATCH_ID" \
  --timeout 10 \
  --execute-live

python3 -m freshmanager.backup --batch-id "$FM_LIVE_BATCH_ID"
```

`--execute-live`에는 `--batch-id`가 필수다. ID는 소문자 canonical UUID를 그대로
사용하며 공백 제거·대소문자 변경·재생성을 하지 않는다. 누락·형식 오류 또는 기존
Source Batch·Sync Backup·Receipt·Lock 충돌은 API Key 사용, 네트워크와 영속 파일
쓰기 전에 종료코드 `2`로 중단한다. Backup 실패는 Collector 재실행 사유가 아니다.

읽기 전용 충돌검사와 참조검증이 끝나면 Collector는 정확한 Source Batch ID 디렉터리를
원자적으로 예약한다. 동시에 같은 ID를 사용한 실행 중 예약 승자 하나만 API Key와
Transport에 접근한다. 예약 직후 디렉터리의 장치·inode와 열린 디렉터리 FD를 보존하고,
설정과 모든 Batch 쓰기 전후에 같은 디렉터리인지 확인한다. 예약 경로가 삭제·교체되거나
심볼릭 링크가 되면 디렉터리를 다시 만들거나 새 대상을 따라가지 않고 즉시 중단한다.
불완전하거나 중단된 예약은 자동 삭제·재사용하지 않으며, Collection Log와 Manifest가
없으므로 Backup 대상이 아니다. stale 예약 복구는 별도 PM 검토 절차가 필요하다.

EG-6B 실제 단일 회차와 품질·백업 Closeout은 완료됐다. 이 명령은 완료 이력을
재실행하라는 뜻이 아니며 새로운 실제 호출에는 다시 별도 PM 승인이 필요하다.

---

## 19. 작업 원칙

Codex는 작업 전 반드시 `AGENTS.md`를 읽는다.

관련 운영 문서:

- `docs/product/FreshManager_PRD_v1.0.md`: 공식 제품 목적·범위·수용 기준
- `docs/engineering/FreshManager_TRD_v1.0.md`: 공식 기술 구조·계약
- `PROJECT_STATUS.md`: 현재 단계와 다음 행동
- `docs/architecture/CODEX_HARNESS_ARCHITECTURE.md`: 문서·검증·승인 책임 구조
- `docs/rules/GIT_WORKFLOW.md`: Git 작업 운영 규칙
- `docs/rules/SECURITY_RULES.md`: 보안 운영 규칙
- `docs/rules/DATA_COLLECTION_RULES.md`: 데이터 수집·원본 보존·결측 처리 규칙
- `docs/data/FIELD_DICTIONARY.md`: 원본·정규화·메타데이터·파생필드 정의
- `docs/analysis/ANALYSIS_PLAN.md`: 분석 질문·기준선·평가기간·Gate 판정 계획
- `.github/ISSUE_TEMPLATE/task.md`: 범용 작업 Issue 템플릿
- `.github/pull_request_template.md`: Pull Request 검토 템플릿

```text
요구사항 확인
→ 현재 EG와 선행 게이트 확인
→ 읽기 전용 사전검증 또는 적용 Project Guard 검사
→ 게이트 판정
→ PM의 다음 구현 단계 전환 승인
→ 승인된 최소 단위 구현
→ 결과 보고
```

위 흐름은 구현 작업에 적용한다.
문서 전용 작업은 Python 기반 Project Guard를 새로 만들지 않는다. 기존 H-001~H-004
입력 문서를 바꾸거나 PM이 요구한 경우에는 구현된 Project Guard와 승인된 테스트를
실행하고, 모든 문서에서 코드 블록·Markdown 제목·링크·규칙·상태 일관성을 확인한다.

검사 실행과 읽기 전용 판정 자체에는 PM 승인이 필요하지 않다.
다음 작업은 PM 명시 승인 후 진행한다.

- 품질 게이트 통과 후 다음 구현 단계로의 전환
- 실제 서울시 API 호출
- 새로운 패키지 또는 라이브러리 설치
- 기준파일 생성·배치·교체·변경
- 데이터 저장구조 변경
- API 호출주기 결정 또는 변경
- 자동실행 구성 또는 변경
- GitHub main 브랜치 병합

EG-1과 EG-2는 Project Guard 없이 읽기 전용으로 판정하고,
EG-3부터 적용 대상 Project Guard 검사를 사용한다. 121개 Area 확대는 현재 13개
패널의 단일·반복 수집과 Feature 분석에서 필요성이 확인된 경우에만 별도 승인한다.

---

## 20. 완료 기준

구현 작업은 현재 EG에 적용되는 다음 조건을 모두 만족해야 완료로 판단한다.
후속 EG에서만 적용되는 조건을 현재 단계의 선행 완료조건으로 요구하지 않는다.
단계별 세부조건은 `docs/testing/QUALITY_GATES.md`를 따른다.

- 무결성 검증을 통과한 공식 CSV 121행을 읽음
- 공식 CSV의 실제 장소코드만 사용함
- 모든 장소의 성공·실패 상태를 기록함
- 한 장소 실패로 전체 수집이 중단되지 않음
- 장소별 원본 JSON을 저장함
- 기존 원본 파일을 덮어쓰지 않음
- 예측 스냅샷을 덮어쓰지 않음
- 상권 미지원과 결측을 구분함
- API 키가 노출되지 않음
- Project Guard 검사를 실행하고 통과함
- 현재 품질 게이트 통과와 다음 단계 전환 승인을 구분함
- 실행방법을 한국어로 설명함
- PM 확인사항과 남은 위험을 보고함

문서 전용 작업은 다음을 모두 만족해야 완료로 판단한다.

- 요청받은 문서만 수정함
- 코드 블록 정상 종료와 Markdown 제목 구조를 확인함
- 프로젝트 목표, 수집 범위, 분석 범위가 일치함
- 공식 CSV 경로와 배치·검증·EG-1 상태가 일치함
- 단계적 구현 순서와 호출주기 원칙이 일치함
- Gate A·B·C와 EG-* 명칭이 구분됨
- 검사 ID 중복·누락과 품질 게이트 순환 여부를 확인함
- 상권 상태와 API 키 보안 규칙이 일치함
- 원본·예측·날씨 규칙이 일치함
- 완료·미완료 상태와 여섯 문서 사이의 충돌 여부를 확인함
- PM 확인사항과 남은 위험을 보고함

PM 최종 승인 전에는 작업을 최종 완료로 확정하지 않는다.
