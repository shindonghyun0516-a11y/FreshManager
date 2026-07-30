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
- Validation: 동적 S-DoT는 첫 EG-7 1시간 파일럿에서 제외하고 후속 별도 승인 작업에서 접근성·스키마·품질 계약을 검증한다.
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
- Decision: D-020의 원격 근거 Eligibility를 충족한 Spot은
  `target_level=SPOT`, Spot 근거가 부족하고 Area 근거만 충분하면
  `target_level=AREA`와 `fallback_reason`을 반환한다. Area 근거도 부족하면
  Recommendation Output을 생성하지 않는다.
- Alternatives: 모든 추천을 AREA 또는 모든 추천을 SPOT으로 고정.
- Consequences: 추천 근거와 fallback 사유를 추적하고 Area 값을 Spot 직접 유동인구로
  표현하지 않는다. 원격 SPOT 추천과 운영 적합성 보장을 분리하고, 운영 적합성이
  미확인이면 그 상태와 제한을 표시한다.
- Validation: Recommendation MVP Workstream은 Gate number `NOT_ASSIGNED`이며 별도 PM 승인 후 검증한다.
- Related decision: D-006, D-008, D-020.
- History: 이전 문구는 "신뢰 가능하고 운영 가능한 Spot"만 SPOT으로 허용했으나,
  D-020이 운영 적합성 확인을 원격 추천의 필수조건에서 분리했다. 이전 결정 이력은
  D-006·D-018·D-019에 보존한다.

## ADR-006 — Backup Worker를 Collector와 분리

- Status: `ACCEPTED`
- Context: 백업 장애가 수집 호출량과 원본 보존에 영향을 주면 API 재호출·중복 위험이 생긴다.
- Decision: 완료 Batch만 처리하는 1회 실행형 Worker를 Batch 완료 직후 호출하고,
  Google Drive for Desktop Sync의 `FreshManager-Data/` 논리 루트에 검증 복사본을 게시한다.
- Alternatives: Collector 내부 복사, Google Drive API/OAuth/SDK 직접 연동, 수동 복사.
- Consequences: 백업 실패로 API를 재호출하지 않고, `.env`·Secret·임시파일을 제외하며,
  Manifest SHA-256과 충돌을 검증한다. 실제 계정 이메일과 동기화 절대경로는 기록하지
  않는다. Worker는 `LOCAL_SYNC_COPY_VERIFIED`까지만 생성하고 원격 완료 상태는 생성하지 않는다.
- Completed validation history: Issue #60에서 Fake 성공·부분 실패·중복·충돌·잠금·
  Fake Restore와 H-708을 검증하고 PR #61로 `main`에 병합했다.
- Operational status boundary: 실제 Sync Root·실제 Batch·원격 완료 확인의 현재 상태는
  [`PROJECT_STATUS.md`](../PROJECT_STATUS.md)를 따른다.
- Related decision: D-007, D-010.

## ADR-007 — Raw 원본과 CSV 파생자료를 분리

- Status: `PLANNED`
- Context: Raw는 재현·감사 근거이고 CSV는 조회·정렬·분석 편의를 위한 다른 책임이다.
- Decision: Raw JSON·Metadata·Collection Log·Manifest를 공식 원본으로 보존하고 CSV는 첫 실제 Batch 품질 감사 후 별도 Exporter로 생성한다.
- Alternatives: API 응답을 즉시 CSV로 변환해 Raw 대신 보존, CSV 실패 시 재수집.
- Consequences: CSV는 Raw에서 재생성하며 실패해도 API를 재호출하지 않는다. Area 관측과 Spot Context를 같은 측정값으로 합치지 않는다.
- Validation: 파일 수·키·시간 의미·결측·재생성 일치성을 별도 테스트한다.
- Related decision: D-011.

## ADR-008 — EG-7은 승인 계획 기반 1시간 Controller와 재생성 가능한 인덱스를 사용

- Status: `ACCEPTED`
- Context: 첫 반복수집은 정확한 5분 정렬 실행 가능성, 중첩 방지, 호출 상한, Backup
  무재수집과 PM 승인 추적을 함께 만족해야 하지만 영구 Scheduler나 ML 플랫폼은 필요 없다.
- Decision: 하나의 불변 계획에 `pilot_run_id`, 12개 벽시계 시각과 UUIDv4 Batch ID,
  Area 순서, 최대 156호출, 할당량·Live 승인 상태를 넣는다. 파일럿 전역 Lock 아래
  기존 EG-6B Collector와 Backup Worker를 회차별 최대 한 번 조립하고 append-only
  사건 로그를 남긴다. canonical Batch 증거에서 12행 Slot Index, 최대 156행 Area
  Observation Index와 Summary를 CSV·JSONL·JSON으로 파생한다.
- Alternatives: 이전 실행 종료 후 5분 대기, runtime Batch ID 생성, cron·launchd,
  Collector 내부 Backup, 별도 Controller/Index PR, 수집 중 중복 제거.
- Consequences: 늦거나 중첩된 회차는 호출 0회로 건너뛰고 보충하지 않는다. 건너뛴
  ID도 재사용하지 않는다. Backup 실패는 Source를 보존하고 남은 회차를 중단하며
  Collector를 다시 호출하지 않는다. 파생 중복 플래그는 Raw를 수정하지 않는다.
- Safety boundary: `UNCONFIRMED`·`NOT_APPROVED`가 기본이며 실제 날짜·할당량·운영
  ID·계획 지문·PM Live 승인 전 실행을 거부한다. Dry-run은 자격증명·Transport·
  Collector·Backup·운영 디렉터리·Google Drive에 접근하지 않는다.
- Scope boundary: 동적 S-DoT, Spot 평가, Recommendation, ML 학습, 24시간·영구
  Scheduler는 제외한다.
- Validation: `freshmanager/eg7.py`, `tests/test_eg7.py`, H-707.
- Related decision: D-003, D-005, D-010, D-012, D-013.

## ADR-009 — 5분 장기 주기는 버전 계획의 불변 계약

- Status: `ACCEPTED`
- Context: PM은 5분을 파일럿 비교 후보가 아닌 장기 반복수집 기준으로 확정했다.
  운영시간·24시간 확대·할당량이 OPEN인 사실과 주기 결정을 분리해야 한다.
- Decision: 계획 schema v2는 `cadence_minutes=5`,
  `cadence_decision_status=PM_APPROVED_FIXED`,
  `long_term_baseline_status=ACTIVE`,
  `cadence_scope=LONG_TERM_OPERATING_BASELINE`, `cadence_change_allowed=false`를
  정확히 요구한다. CLI에 임의 주기 옵션을 두지 않고 비 5분 계획을 거부한다.
- Alternatives: 10분·15분 비교, runtime cadence 선택, 중복률 기반 자동 변경.
  PM 결정으로 모두 제외한다.
- Consequences: 중복 응답도 불변 Raw와 파생 플래그로 보존하며 다음 계획 호출을
  중복만으로 생략하지 않는다. 제거·선별·가중치는 EG-8 데이터셋 책임이다. 향후
  주기 변경에는 새 PM 결정, schema 버전 변경과 별도 코드 검토가 필요하다.
- Open boundary: 파일럿 날짜·시작시각, 일일 운영시간대, 24시간 또는 선택 시간 운영,
  API 할당량·용량, 운영 ID·지문, Live 승인과 확대 시점은 별도 OPEN 결정이다.
- Validation: plan v2 검증, `--cadence` 거부 테스트, 중복 보존 테스트, H-707.
- Related decision: D-013.

## ADR-010 — Apps Script를 PoC 상시 반복수집 Runtime으로 재채택

- Status: `ACCEPTED`
- Context: 로컬 EG-7 Controller는 `time.sleep` 기반 동기 실행이라 Codex·Claude
  Code 세션과 사용자 컴퓨터가 켜져 있어야 5분 반복수집이 계속된다. PM은 "Mac과
  Codex·Claude Code가 꺼져도 5분마다 수집이 계속돼야 한다"는 요구사항을 확정했다.
  기존 ADR-08(TRD 내부 목록)의 Apps Script 폐기 근거는 재조사 결과 "현행 로컬
  Python과 충돌"이라는 순환 서술이었고 별도 기술 실패 증거는 없었다.
- Decision: 승인된 13개 Area의 5분 상시 반복수집 Runtime을 Google Apps Script로
  채택한다. Apps Script는 POI 코드로 서울시 API를 호출하고 Script Properties의
  `SEOUL_OPEN_API_KEY`로 Key를 관리하며, 로컬 EG-6B/EG-7은 상시 Scheduler가 아닌
  기술검증·Pilot Runner로 유지한다.
- Alternatives: 로컬 EG-7을 24시간 Scheduler로 확장, 독립 클라우드 Runtime(Cloud
  Scheduler/Cloud Run) 신규 구축. 둘 다 검토했으나 PM이 이미 검증된 Apps Script
  자산이 존재해 우선 채택했다.
- Consequences: Apps Script의 24시간 이상 장기 지속성은 `PENDING_VALIDATION`이다.
  Apps Script 소스의 Git 버전관리와 Python 정규화·ML 파이프라인과의 데이터 통합은
  `PLANNED`이며 이번 결정에 포함하지 않는다. Python은 수집이 아니라 정제·분석·
  머신러닝을 담당하는 독립적 관심사로 남는다.
- Validation: PM이 Google 계정 화면에서 직접 확인(Spreadsheet·Apps Script 프로젝트
  존재, POI 코드 호출, Script Properties Key, `raw_log_v3`/`population_current_v3`/
  `population_forecast_v3` 데이터 누적). 추가로 5분 시간 기반 Trigger가 실제로
  반복 실행되며(`collection_run_id`별 Raw 13·Current 13·Forecast 156건) 데이터가
  계속 쌓이는 것을 확인 — 5분 자동수집은 `ACTIVE`, 24시간 이상 무중단 지속성은
  `NOT_COMPLETED`로 구분한다. 이 저장소만으로는 재현·재검증할 수 없다.
- Related decision: D-014, TRD ADR-15(ADR-08을 `SUPERSEDED`로 대체).

## ADR-011 — EG-8 상위 Gate와 EG-8A~8E 세분화, Model Output/Recommendation Output/UI 계층 분리

- Status: `ACCEPTED`
- Context: 데이터 분석·ML·추천·UI 전환 단계에서 수집 Runtime(Apps Script)과
  분석·ML Runtime(Python)의 역할이 이미 분리돼 있다(ADR-010, `PROJECT_MEMORY.md`
  §6.1). 이 분리를 데이터 처리 계층에도 명시적으로 적용해 UI가 Model Output을
  직접 소비하는 구조를 방지해야 한다. 기존 EG-8 정의를 다른 의미로 재사용하면
  9개+ 문서·67회 참조와 D-008의 "EG-9 미확정" 결정 모두와 충돌한다.
- Decision: 기존 EG-8 정의(Area Feature + 선택적 S-DoT Feature + Spot Candidate
  Evaluation)를 EG-8D로 흡수하고, EG-8을 상위 Gate로 삼아 EG-8A(Python Loader·
  정규화·품질)~EG-8E(Recommendation Output Contract·UI/UX Readiness)로
  세분화한다. 데이터 계층을 Raw(v3 source sheets) → Normalized Dataset →
  Feature Dataset → Model Output → Recommendation Output → UI Presentation
  순으로 분리한다. UI Presentation은 Model Output을 직접 참조하지 않고
  Recommendation Output만 소비한다.
- Alternatives: (a) EG-8을 새 의미로 재사용 — 기존 참조·완료 이력과 직접
  충돌해 기각. (b) EG-9 이후 번호를 새로 배정 — D-008이 이미 "EG-9 미확정"을
  결정해 재검토가 필요하므로, 상위/하위 세분화로 D-008과 충돌 없이 처리하는
  이번 방식을 선택. (c) UI가 Model Output을 직접 소비 — 모델 변경이 UI를
  직접 깨뜨리는 결합도 위험으로 기각.
- Consequences: 기존 EG-8 참조는 EG-8D를 가리키는 것으로 재해석한다. ML-ready
  데이터셋·Recommendation 출력 계약의 상세 정본은 각각
  `docs/data/ML_READY_DATASET_SPEC.md`, `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md`
  (둘 다 `PLANNED`, PR2에서 생성 예정)가 담당한다. D-008과 이 문서의 ADR-14는
  대체되지 않는다 — Recommendation MVP의 공식 Gate 번호는 계속 `NOT_ASSIGNED`며,
  EG-8E는 그 구현 Gate가 아니라 계약·설계 준비 Gate다.
- Validation: 문서 정합성(Project Guard H-003)과 EG-7 정본 무변경(H-707)을 PR1
  에서 확인한다. 실제 Loader·모델·Ranking 구현 검증은 후속 Issue의 범위다.
- Related decision: D-015, TRD ADR-14(대체 아님 — EG-8E는 Recommendation MVP의
  구현 Gate가 아니라 계약·설계 준비 Gate), TRD ADR-16.

## ADR-012 — Area-first Web/API 경계와 읽기 전용 데이터 공급

- Status: `ACCEPTED`
- Context: D-022 Area-first 웹 파일럿은 사용자가 담당 Area를 직접 선택하는 조회
  흐름이며 D-021 다중 Area Recommendation Service와 책임이 다르다. UI 구현 전에
  Web/API, 기존 Python Package와 저장소 밖 불변 데이터의 의존방향을 고정해야 한다.
- Decision: Vue 3·TypeScript·Vite Frontend는 HTTP API만 호출하고, FastAPI·Pydantic·
  Uvicorn Backend는 새 `SelectedAreaPilotService`를 통해 읽기 전용
  `AreaDataProvider`와 `PilotSpotOptionRepository`를 사용한다. 웹 요청은 수집·Backup·
  Dataset·ML·Recommendation을 실행하거나 데이터를 쓰지 않는다. 초기에는 DB·인증·
  Session·선택이력·위치정보 저장이 없고 Same-origin 배포를 우선한다.
- Alternatives: 기존 D-021 Recommendation Service를 Primary API로 사용, Vue의 파일
  직접 읽기, 요청 시 수집, Spreadsheet 직접 접근, 초기 DB·인증·Microservice 도입.
- Consequences: API는 `GET /api/v1/health`, `GET /api/v1/areas`,
  `GET /api/v1/areas/{area_code}/pilot-view`만 제공하는 방향이며 Current·60분·180분의
  부분 가용성과 Freshness를 독립 표현한다. 기존 Code Cleanup은 Scaffold 선행조건이
  아니며 결정은 `NO_CODE_CLEANUP_REQUIRED_BEFORE_SCAFFOLD`다.
- Validation: 상세 Stack, Dependency, 오류, 개인정보, Module 재사용 Matrix와 Code
  Cleanup Gate는
  [`AREA_FIRST_WEB_API_ARCHITECTURE.md`](../docs/architecture/AREA_FIRST_WEB_API_ARCHITECTURE.md)를
  따른다. 이 ADR PR은 문서·전체시험·Project Guard만 검증하고 구현은 후속 Issue로
  분리한다.
- Related decision: D-020, D-021, D-022, ADR-011.
- Related work: Issue #148, PR #149.

## 2. ADR 갱신 규칙

결정이 바뀌면 기존 ADR을 삭제하지 않고 상태를 `SUPERSEDED`로 바꾸며 대체 ADR을
연결한다. 계획 구조를 구현 완료로 표현하지 않고, PM 승인·코드·테스트·실제 실행
증거를 각각 구분한다.
