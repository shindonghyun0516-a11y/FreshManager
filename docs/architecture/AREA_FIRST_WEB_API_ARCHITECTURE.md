# Area-first Web/API Architecture

- Status: `APPROVED · ACCEPTED`
- Decision record: `ADR-012`
- Related Issue: `#148`
- Baseline: `main` at `3740daead8a02964316ed0ba36284ed7f157a6e8`

## 1. 목적과 책임 경계

이 문서는 D-022 Area-first 웹 파일럿의 Vue Frontend, FastAPI Backend와 읽기 전용
데이터 공급 경계를 정한다. 사용자가 승인된 Area를 직접 선택해 현재·60분 후·180분
후 Area 정보와 PM 수기 Spot 선택지 3개를 조회하는 흐름이다. 시스템 Area 추천,
Spot 자동추천 또는 공식 Recommendation Output이 아니다.

상위 Engineering Harness의 Issue·Branch·PR·CI·Merge 규칙과 데이터·분석 정본은
각 기존 문서가 계속 소유한다. 이 ADR은 이를 대체하지 않는다.

- 제품 계약: [`AREA_FIRST_WEB_PILOT_CONTRACT.md`](../product/AREA_FIRST_WEB_PILOT_CONTRACT.md)
- 추천 경계: [`RECOMMENDATION_OUTPUT_CONTRACT.md`](../product/RECOMMENDATION_OUTPUT_CONTRACT.md)
- 기술 정본: [`FreshManager_TRD_v1.0.md`](../engineering/FreshManager_TRD_v1.0.md)
- Repository 기준선: [`REPOSITORY_READINESS_AUDIT.md`](REPOSITORY_READINESS_AUDIT.md)
- 현재 상태: [`PROJECT_STATUS.md`](../../PROJECT_STATUS.md)

이번 결정은 Architecture만 확정한다. 코드, Directory Scaffold, Dependency, 데이터,
Workflow, 배포와 Live 실행을 승인하거나 구현하지 않는다.

## 2. 고정 기술 Stack

| 영역 | 결정 |
|---|---|
| Frontend | Vue 3, TypeScript strict mode, Vite, Composition API, `<script setup>` |
| Backend | FastAPI, Pydantic, Uvicorn |
| Map | NAVER Maps JavaScript API |
| 화면 | 같은 상태·Component를 쓰는 Responsive Desktop Web + Mobile Web |
| Tablet | 전용 UI를 만들지 않음 |
| 초기 저장 | Database, 사용자 계정, Session, 선택이력 저장 없음 |

Framework 대안은 이 ADR에서 다시 비교하지 않는다. Nuxt, Next.js, NestJS, Django,
Pinia, Vue Router, Axios와 대형 UI Component Library는 초기 파일럿에 추가하지 않는다.

## 3. Dependency 방향

```text
apps/web
  -> HTTP API only

apps/api
  -> freshmanager SelectedAreaPilotService

freshmanager
  -X-> apps/api, apps/web

data/prototype
  -> PilotSpotOptionRepository only (read-only)
```

- Vue는 Python 파일, CSV, Dataset 또는 Manifest를 직접 읽지 않는다.
- `freshmanager`는 FastAPI·Vue를 Import하지 않는다.
- Route는 Area 계산식·최신성 판정·Spot 계약을 다시 구현하지 않는다.
- 웹 요청은 Collector, Backup, Loader, Dataset Builder, ML 또는 Recommendation
  Engine을 실행하지 않는다.
- Frontend는 Area 증감수·증감률을 다시 계산하지 않고 API 값을 표시한다.

## 4. 목표 Directory 책임

아래는 목표구조이며 이 ADR 작업에서는 Directory를 생성하거나 파일을 이동하지 않는다.

| Directory | 소유 책임 | 허용 자산 | 금지 자산 | Dependency | 생성 시점 |
|---|---|---|---|---|---|
| `apps/web` | Area-first Vue 화면 | Component, Composable, style, frontend test·build config | Secret, Raw·Manifest, Python 분석코드 | HTTP로 `apps/api`만 호출 | 별도 Web Scaffold Issue 승인 후 |
| `apps/api` | FastAPI HTTP 경계 | Route, Pydantic schema, 오류 변환, API test, 정적 build 연결 | Collector, 계산식 복제, DB, 추천·ML 실행 | `freshmanager` Application Service만 호출 | 별도 API Scaffold Issue 승인 후 |
| `freshmanager` | 수집·분석 Domain과 Application Service | 기존 생산코드, 새 선택 Area Service·Provider 계약 | FastAPI·Vue Import | `apps/*`에 의존하지 않음 | 기존 유지; 새 코드는 구현 Issue에서만 |
| `data/reference` | 공식·승인 기준자료 | Area·Spot·S-DoT 정본 | 화면 전용 임시값 | 기존 Python 계약이 읽음 | 기존 유지 |
| `data/samples` | 오프라인 공식 Sample | 저장된 비운영 Sample | Live 결과·사용자 위치 | Offline 검증만 | 기존 유지 |
| `data/prototype` | 화면용 비운영 Prototype | PM 승인 Pilot Spot 선택지 | Raw·Forecast·공식 Manifest | Prototype Adapter만 읽음 | 별도 데이터 이동 Issue 승인 후 |
| `docs/architecture` | Architecture·Audit | 이 ADR와 구조 감사문서 | 실행로그·운영 데이터 | 정본 문서에 링크 | 이 ADR부터 사용 |
| `scripts` | 수동 검증·운영 보조 | 승인된 단일목적 Script | Web 요청 처리코드 | 소유 모듈 계약만 호출 | 필요성이 승인된 구현 Issue에서 |
| `tests` | Python·통합 안전계약 | Backend·Domain·Guard test | 운영 데이터·Secret | 생산경로를 검증 | 구현과 함께 |
| `ai-context` | 압축된 결정·복원정보 | ADR 요약과 장기 결정 | 상세 구현 복제 | 상세 정본에 링크 | 기존 유지 |

현재 `data/reference/pilot_spot_options.csv`는 별도 이동 승인이 있을 때까지 원위치를
유지한다. 목표 `data/prototype` 경로를 먼저 만들거나 파일을 이 ADR에서 이동하지 않는다.

## 5. Backend 계층

### 5.1 HTTP Layer — `apps/api`

책임은 Route, 요청 검증, Pydantic Response, 안전한 HTTP 오류 변환, OpenAPI와 공개
Same-origin 경계다. 서울시 API 수집, Spreadsheet 접근, Area 계산, Recommendation,
ML, Backup, Dataset 생성과 파일 쓰기는 금지한다.

개발 중에는 Vite Dev Server가 `/api`를 FastAPI Development Server로 Proxy한다.
ADR-012 승인 당시 초기 기본안은 FastAPI가 Vue Build를 같은 Origin에서 제공하는
방식이었다. Vercel 플랫폼 확정 후 ADR-013은 Web·API 두 Project와 Production
Rewrite를 Working Topology로 제안한다. ADR-013이 승인되기 전에는 어느 방식도 실제
배포계약이 아니며, 승인 뒤에도 Same-origin과 공개 API 계약은 바뀌지 않는다.

### 5.2 Application Layer — `SelectedAreaPilotService`

Area-first Primary Service는 새 `SelectedAreaPilotService`다.

```text
input: selected_area_code
output:
  Area identity
  current Area state
  60-minute forecast and freshness
  180-minute forecast and freshness
  exactly three Spot options
  prototype and source metadata
  warnings and limitations
```

Service는 승인된 5개 Area의 사용자 선택을 검증하고 Provider 두 개의 결과를 조립한다.
순위를 계산하거나 Area·Spot을 추천하지 않으며 선택을 저장하지 않는다.
`area_selection_mode=USER_CHOICE`, `area_auto_recommendation=false`,
`spot_selection_mode=USER_CHOICE`, `spot_auto_recommendation=false`,
`machine_learning_used_for_recommendation=false`,
`official_recommendation_allowed=false`를 유지한다.

기존 `pilot_recommendation_service.py` 판정은 `NO_REUSE`다. 이 모듈의 JSON-safe 변환은
D-021 다중 Area 추천 결과, 단일 Horizon과 추천 상태에 결합돼 있고 재사용 후보는
private helper다. D-022 주 서비스나 Helper로 끌어오면 추천 의미와 부분 Horizon 계약을
함께 가져오므로 보존만 한다.

### 5.3 Domain·Analysis Layer — `freshmanager`

수집, 원본·Manifest, Backup, 정규화, Area Ranking, 내부 다중 Area 비교, ML 비교,
사용자 선택 Spot Master 검증 책임은 현재 위치에 남는다. Web Runtime을 이유로 기존
분석코드를 이동하거나 공개 API로 넓히지 않는다.

## 6. 읽기 전용 데이터 공급

고정 흐름은 다음과 같다.

```text
Existing Collection / Normalization
-> Latest Complete Approved Snapshot
   -> or latest approved Current-only fallback when no complete Snapshot exists
-> read-only AreaDataProvider
-> SelectedAreaPilotService
-> FastAPI
-> Vue
```

배포 설정은 저장소 밖의 승인된 불변 Snapshot 또는 Export를 명시한다. Provider는
그 입력과 Manifest에서 Current·60분·180분이 모두 유효한 최신 승인 Source run을
결정적으로 선택한다. 완전한 Snapshot이 없으면 별도 Current 계약을 통과한 최신 승인
Current-only Snapshot만 사용하고 두 미래값은 모두 `NO_COMPLETE_SNAPSHOT`으로
반환한다. 서로 다른 run을 섞거나 불완전 Snapshot의 한 Horizon만 가져오지 않는다.
완전한 Snapshot이 선택된 뒤에는 60분·180분 Freshness를 독립 판정해 한 Horizon의
`DEGRADED`·`STALE_BLOCKED`가 다른 Horizon을 바꾸지 않게 한다. 요청이 데이터를 찾지
못하거나 오래된 경우에도 Collector·Apps Script·Spreadsheet API·서울시 API를
실행하거나 파일을 보정하지 않는다.

### 6.1 `AreaDataProvider`

- 선택 Area의 Current와 `observed_at`을 반환한다.
- 60분·180분 Forecast와 각각의 `forecast_at`을 반환한다.
- Source metadata와 Horizon별 Freshness를 반환한다.
- Current·60분·180분 완전성을 같은 Source run에서 검증한 뒤 60분·180분 Freshness를
  독립 판정한다.
- 다른 Horizon 값 복사, 보간, 결측의 0 변환을 하지 않는다.
- 원본, Snapshot, Export, Dataset 또는 Manifest를 쓰거나 변경하지 않는다.

### 6.2 `PilotSpotOptionRepository`

- Spot identity는 기존 `pilot_spot_options.load_pilot_spot_options()`의 검증을 좁게
  재사용하고, PM 수기 값은 별도 승인 뒤 명시적으로 설정된 `data/prototype` 자산에서만
  읽는다. 두 입력 중 없는 값을 서로 만들어 채우지 않는다.
- 선택 Area에 연결된 Spot을 정확히 3개 반환한다.
- Spot identity·주소·좌표와, 존재하는 경우 PM 수기 Current·60분·180분 값,
  혼잡도, 비교값, 점수·Area 내 순위를 함께 반환한다.
- 비교기준은 `PREVIOUS_DAY`, `PREVIOUS_WEEK`, `RECENT_4WEEK_AVERAGE`만 허용하고
  기본값은 `RECENT_4WEEK_AVERAGE`다.
- 수기 값에는 `data_status=PROTOTYPE`, `input_method=PM_MANUAL`,
  `score_source=PM_MANUAL`, `rank_source=PM_MANUAL`을 보존한다.
- Area 값을 Spot 값으로 복사·분배·추정하지 않는다.
- Spot 점수·순위를 계산하지 않고 PM 입력값만 전달한다. 기본선택·자동추천을 만들거나
  입력을 쓰지 않는다.
- 선택지 3개의 identity 계약 위반만 500 오류다. 선택지 계약은 유효하지만 일부
  PM 수기 값 또는 출처 metadata가 없거나 유효하지 않으면 정적 Spot은 반환하고
  `SPOT_PROTOTYPE_DATA_UNAVAILABLE`로 표시하며 해당 값을 숨기고 새로 만들지 않는다.

초기 Runtime은 Spreadsheet 직접 접근, Google OAuth와 Browser의 서울시 API Key
보유를 지원하지 않는다.

## 7. HTTP API 계약

| Method·Path | 역할 | 부작용 |
|---|---|---|
| `GET /api/v1/health` | Process와 읽기 전용 Provider 준비상태 확인 | 없음 |
| `GET /api/v1/areas` | 사용자 선택 가능한 승인 Area Identity 목록 | 없음 |
| `GET /api/v1/areas/{area_code}/pilot-view` | 선택 Area의 Current·60분·180분·Spot 3개 통합 조회 | 없음 |

POST Endpoint와 Recommendation 실행 Endpoint는 만들지 않는다. 공개 Route, Service,
Operation과 Response 명칭은 사용자 선택을 시스템 추천으로 오해하게 하는
Recommendation, Recommended, Best, Optimal, Ranking, Ranked 또는 이에 해당하는
한국어 추천·최적·최고·순위 용어를 사용하지 않는다.
중립 개념명은 `AreaPilotView`, `SelectedAreaView`, `SpotOption`이다.

`pilot-view`는 Area identity, Current, 60분·180분 값과 각 Freshness, Spot Option
3개, 사용 가능한 PM 수기 Prototype 값·Source metadata, warning과 limitation을 한
Response로 반환한다.
Pydantic Schema가 API 계약의 정본이고 TypeScript Type은 FastAPI OpenAPI에서
파생한다. Type Generator Package는 Scaffold Issue에서 승인·선정하며 Frontend와
Backend Schema를 손으로 이중 관리하지 않는다.

### 7.1 오류 계약

오류 Body는 다음 한 형태만 사용하고 내부 경로·원본 데이터·예외문을 포함하지 않는다.

```json
{
  "error": {
    "code": "AREA_NOT_SUPPORTED",
    "message": "지원하지 않는 Area입니다."
  }
}
```

| HTTP | Error Code | 의미 |
|---:|---|---|
| 404 | `AREA_NOT_SUPPORTED` | 승인 목록에 없는 Area |
| 422 | `REQUEST_VALIDATION_FAILED` | 형식이 잘못된 Path·Request |
| 503 | `AREA_DATA_PROVIDER_UNAVAILABLE` | 공급원 장애로 안전한 Response 자체를 구성할 수 없음 |
| 500 | `SPOT_PROTOTYPE_CONTRACT_INVALID` | Spot 정확히 3개의 identity 구조 계약 위반 |

특정 Horizon의 정상적인 데이터 부족은 HTTP 오류가 아니다. 성공 Response 안에서
해당 Horizon을 명시적 unavailable로 반환한다. 선택 Area의 동적 값이 없더라도
정적 Spot 3개를 검증할 수 있으면 `AREA_DATA_UNAVAILABLE` 성공 Response로 반환한다.

## 8. Freshness와 부분 Response

60분과 180분은 독립 판정하고 기존 의미를 바꾸지 않는다.

| 상태 | 반환 계약 |
|---|---|
| `FRESH` | 값과 Source 시각을 정상 반환 |
| `DEGRADED` | 값, Source 시각과 Warning을 함께 반환 |
| `STALE_BLOCKED` | 해당 Horizon 값은 `null`, 상태와 차단 이유를 반환 |
| `NO_COMPLETE_SNAPSHOT` | 두 미래값은 unavailable; 별도 계약을 통과한 Current만 반환 |

한 Horizon의 실패가 다른 Horizon이나 Current를 숨기지 않는다. Map 또는
Geolocation 실패도 이용 가능한 Area·Spot 텍스트를 차단하지 않는다. Spot Prototype
계약 자체가 깨지면 정확히 3개 선택지를 보장할 수 없으므로 500 계약 오류로 차단한다.

## 9. Frontend 경계

Frontend는 Composition API의 `ref`·`reactive`·`computed`, Composable, Native
`fetch`, Scoped CSS 또는 CSS Modules와 CSS Custom Properties를 사용한다.

초기 상태는 `selectedAreaCode`, `areaPilotView`, `openedSpotId`, `selectedSpotId`,
`mapStatus`, `geolocationStatus`, `userLocation`, `comparisonType`으로 제한한다.
Desktop과 Mobile은 같은 상태·Component를 쓰고 Layout만 바꾼다. Area가 바뀌면 이전
Spot 열림·선택 상태를 초기화한다.

## 10. 지도·위치·개인정보

- 현재 위치는 사용자가 버튼을 누른 뒤 Browser Geolocation으로만 요청한다.
- 위치는 Browser memory에만 두고 FastAPI, 로그, Telemetry, Database, 파일,
  Session, Cookie, `localStorage`, `sessionStorage`로 보내거나 보존하지 않는다.
- 새로고침하면 폐기한다.
- Spot까지 직선거리는 Frontend에서만 계산한다.
- 권한 거부는 Area·Spot 텍스트 조회를 차단하지 않는다.
- Area 코드는 현재 조회를 위해 Path parameter로만 보내고 서버가 선택이력으로
  저장하거나 사용자와 연결하지 않는다. 초기 Uvicorn access log는 비활성화한다.
  Reverse Proxy를 쓰면 원본 요청 URI를 저장하지 않거나 동적 Area 값을 마스킹한다.
  Application log에는 Route template과 HTTP 상태만 남기고 Area 코드를 기록하지 않는다.
- Spot 선택은 현재 Browser 상태에만 두고 API, 로그, Telemetry, Analytics, Database,
  파일 또는 Browser 영구저장소로 전송·기록하지 않는다.

NAVER Maps Client ID는 Frontend 환경변수로 주입하고 허용 Domain을 제한한다. 서울시
API Key와 분리하며 실제 값은 코드·문서·Git에 기록하지 않는다. Client ID는 Browser에
전달되는 식별자이므로 Backend Secret처럼 은닉된다고 표현하지 않는다.

## 11. 개발·배포 경계

- 개발: Vite Dev Server + FastAPI Development Server + `/api` Proxy.
- 파일럿: 사용자 URL 하나와 Same-origin 우선.
- 배포 플랫폼: `VERCEL`, 상태는 `PLANNED_NOT_DEPLOYED`.
- Working Topology: `apps/web` Root의 Vue Project와 Repository Root의 FastAPI
  Project를 분리한다. 이 구성은 `PROPOSED_PENDING_PM_REVIEW`다.
- FastAPI는 `apps.api.main:app` 표준 ASGI App이며 Local Uvicorn과 Vercel Python
  Runtime에서 같은 Entry Point를 사용한다. Vercel은 배포 Adapter일 뿐 Business
  Logic에 포함되지 않는다.
- ADR-012의 Same-origin 원칙은 유지한다. 실제 API Project 주소가 만들어진 뒤
  별도 배포 작업에서 Production Rewrite와 Domain을 결정한다.
- Python Runtime은 API용 Dependency만 설치하고 `requirements-ml.txt`를 설치하지
  않는다.
- Runtime 파일쓰기는 금지한다. 후속 Snapshot 공급은 저장소 밖 승인 불변자료를
  읽기 전용으로 사용하는 Provider가 담당한다.
- 실제 Vercel Project·Domain·Rewrite·Secret·배포와 운영 로그 정책은 후속 배포
  작업이 소유한다.

Microservice, API Gateway, BFF, Kubernetes, Redis, Celery, PostgreSQL, 사용자 인증,
관리자 페이지, Model Serving과 실시간 Collector 연결은 초기 범위가 아니다.

## 12. 시험·CI 경계

기존 Python 전체시험과 Project Guard를 유지한다. 새 Web/API CI가 이를 대체하거나
약화하지 않는다. 이 Architecture PR에서는 Workflow를 추가하지 않았고, 후속
Scaffold는 API Import·시험과 Vue Type Check·Build만 담당하는 별도 Workflow를 둔다.

후속 Backend 시험은 Pydantic Schema, Route, Provider 실패, 부분 Horizon, 허용
Area, Spot 정확히 3개, no-write, no-network와 Area 선택값 비기록을 검증한다. 후속
Frontend 시험은 Type Check, Unit·Component, Responsive 상태, Map fallback,
Geolocation 거부와 Area 변경 시 Spot 상태 초기화를 검증한다. E2E는 실제 화면 구현
후에만 추가한다.

## 13. 기존 Module 재사용 Matrix

판정은 현재 Import, 소유 Test와 Project Guard에 근거한다. 직접 Guard 대상이 없는
Module은 표에 적은 호출 Import와 전용 Test를 근거로 삼는다. Module 전체를 Web 요청에
노출한다는 뜻이 아니며 `APPLICATION_HELPER_REUSE`는 명시한 좁은 함수만 뜻한다.

| Module | 판정 | Import·Test·Guard 근거와 Web 경계 |
|---|---|---|
| `pilot_recommendation_service.py` | `INTERNAL_ANALYSIS_ONLY` | Pilot Core만 Import하고 전용 Service test가 D-021 JSON ViewModel을 보호한다. D-022 Primary·Helper 판정은 `NO_REUSE`. |
| `pilot_area_recommendation.py` | `INTERNAL_ANALYSIS_ONLY` | EG-8D private 평가와 Spot loader를 조립하고 전용 Core test가 다중 Area 추천을 검증한다. Web 선택 Area 조회에서 실행하지 않는다. |
| `pilot_spot_options.py` | `APPLICATION_HELPER_REUSE` | Core가 Import하고 Service 경로가 간접 사용하며 전용 test와 Guard `H-703`이 5×3 정적 계약을 보호한다. 새 Repository 내부 검증 Helper로만 재사용한다. |
| `eg8d_area_priority.py` | `APPLICATION_HELPER_REUSE` | Pilot Core와 EG-8D test가 사용한다. 공개 `evaluate_horizon_freshness`만 Provider 내부에서 재사용 가능하며 Ranking·CLI·Writer는 실행하지 않는다. |
| `eg8c_features.py` | `INTERNAL_ANALYSIS_ONLY` | Modeling·EG-8D와 전용 test가 Dataset·배타 공개를 보호한다. Web Runtime에서 Builder·Writer를 실행하지 않는다. |
| `eg8b.py` | `INTERNAL_ANALYSIS_ONLY` | B2a·B2b가 직접 Import하고 EG-8C Modeling은 B2a를 통해 간접 의존한다. 전용 test가 분석 산출물을 검증하며 Request path에서 분석·Writer를 실행하지 않는다. |
| `eg8b_b2a.py` | `INTERNAL_ANALYSIS_ONLY` | 단일일자 잠정 Backtest와 전용 test 책임이다. Web Runtime 입력이 아니다. |
| `eg8b_b2b.py` | `INTERNAL_ANALYSIS_ONLY` | 단기 다일자 Backtest와 전용 test 책임이다. Web Runtime 입력이 아니다. |
| `eg6b.py` | `COLLECTION_ONLY` | EG-7이 호출하고 EG-6B test·Guard `H-706`이 Batch·Manifest를 보호한다. Web 요청 호출 금지. |
| `eg7.py` | `INTERNAL_ANALYSIS_ONLY` | EG-6B·Backup을 조립하는 Pilot Controller와 수집 증거용 파생 Index이며 EG-7 test·Guard `H-707`이 실행을 보호한다. Web 요청 호출 금지. |
| `live.py` | `COLLECTION_ONLY` | Collector·HTTP Adapter를 호출하고 Live test가 승인 경계를 보호한다. Web 요청 호출 금지. |
| `eg5.py` | `COLLECTION_ONLY` | Collector·Storage를 호출하고 EG-5 test·Guard `H-702`가 3 Area 수집을 보호한다. Web 요청 호출 금지. |
| `http_adapter.py` | `COLLECTION_ONLY` | Live 수집기가 사용하고 Adapter·Security test와 Guard가 외부 HTTP·비밀정보 경계를 보호한다. Web 요청에서 직접 사용·호출하지 않으며 전이적 Module load는 네트워크 실행을 뜻하지 않는다. |
| `offline.py` | `INTERNAL_ANALYSIS_ONLY` | 공식 Sample 전용 CLI이며 EG-4 Collector test와 Guard `H-506` 대상이다. Web Provider가 아니다. |
| `freshmanager/__init__.py` | `COLLECTION_ONLY` | Collector·Config·Storage public surface만 export한다. Python package 초기화로 로드되지만 API는 현재 export를 Web facade로 재사용하지 않고 새 Service module을 명시적으로 Import한다. |

현재 `WEB_REQUEST_PATH_REUSE`로 판정한 기존 Module은 0개다. Audit의 7개 Interface
seam 검토 후보는 모두 `KEEP · DEFERRED`이며, 이번 ADR에서 선행 정리 대상으로 확정한
`TARGETED_CLEANUP_CANDIDATE`는 0개다. 새 Service와 Provider가 후속 구현에서 최초
Web request path를 만든다.

## 14. Code Cleanup Decision

최종 결정은 다음과 같다.

```text
NO_CODE_CLEANUP_REQUIRED_BEFORE_SCAFFOLD
```

Repository Readiness Audit은 즉시 삭제·정리 가능한 코드가 0개임을 확인했다. 이번
분석도 기존 Module의 Import·Test·Guard 책임이 유효함을 확인했다. 기존 Python Module과
새 Application 계층 사이에 추가할 경계는 `SelectedAreaPilotService`와 Provider 두
개다. Route·Schema·오류 변환은 HTTP Layer 책임이다. 기존 Recommendation Service
일반화나 private Helper 추출은 선택 Area 경로의 선행조건이 아니며 현재 범위를 넓힌다.

- 정리 대상 파일·함수: 없음
- 정리 실행시점: `NOT_APPLICABLE`
- 별도 Cleanup Issue: 만들지 않음
- 데이터·Manifest 영향: 없음

API 구현 중 실제 중복이나 막힌 Interface가 증거로 확인될 때만 같은 구현 Issue에서
최소 변경을 다시 검토한다. 미래 가능성만으로 선행 정리 작업을 만들지 않는다.

## 15. 결정 결과와 제외범위

Issue #152 작업공간에는 이 경계를 따르는 `apps/web`·`apps/api` 최소 Scaffold와
Dependency 초안만 있다. `main` 반영과 실제 기능 구현 완료를 뜻하지 않는다. 다음은
여전히 `NOT_IMPLEMENTED`이며 별도 PM 승인이 필요하다.

- `data/prototype` 생성
- Health 외 Area-first API와 실제 Area 데이터가 연결된 Vue 기능
- NAVER Map 구현
- AreaDataProvider, PilotSpotOptionRepository, SelectedAreaPilotService 구현
- Pilot CSV 이동, 코드 이동·삭제·Refactor
- Cloud 배포, Database, 인증, 사용자 위치·선택 저장
- 실제 API·Recommendation·ML 실행
- Dataset·Manifest 변경 또는 사용자 파일럿 실행
