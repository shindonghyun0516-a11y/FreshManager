# FreshManager Project Memory

## 1. 문서 역할

이 문서는 새 AI 세션이 FreshManager의 장기 제품 맥락과 쉽게 바뀌지 않는 원칙을
복원하기 위한 보조 메모리다. 현재 Issue·Branch·HEAD·검증 결과와 다음 행동은
[`PROJECT_STATUS.md`](../PROJECT_STATUS.md), 제품 요구는
[`FreshManager_PRD_v1.0.md`](../docs/product/FreshManager_PRD_v1.0.md), 기술 계약은
[`FreshManager_TRD_v1.0.md`](../docs/engineering/FreshManager_TRD_v1.0.md)를 따른다.

이 문서는 세 정본을 대체하거나 현재 완료 상태를 선언하지 않는다.

## 2. 장기 프로젝트 정의

FreshManager는 프레시매니저 유동판매 위치·시간 추천 서비스가 성립할 데이터
전제조건을 검증하는 서울시 공개데이터 기반 PoC다. 현재 목표는 앱이나 추천 화면이
아니라, Area별 인구·혼잡·Forecast와 후속 보조 근거를 안정적으로 수집·보존·비교할
데이터 기반을 만드는 것이다.

- 제품 운영자와 최종 승인자는 PM 신동현이다.
- hy 내부 시스템 또는 실제 프레시매니저 판매실적과 연결된 프로젝트가 아니다.
- 실제 판매효과, 구매전환과 개인 최적화를 현재 공개데이터만으로 입증하지 않는다.
- 장기 공식 후보군은 서울시 주요 121개 Area이고, 현재 MVP 패널은 승인된 13개 Area다.

## 3. Area First 원칙

Area Observation은 모든 승인 Area에서 확보해야 하는 Core Observation이다.
서울시 실시간 도시데이터의 Area 값은 특정 출구·건물 앞·Spot의 직접 유동인구가
아니다. EG-6B Collector의 책임은 승인 Area의 원본·메타데이터·Forecast·Batch 증거를
보존하는 데까지다.

S-DoT Observation은 Optional Supporting Observation이다. 지원되고, 접근 가능하며,
실제로 수집할 수 있고, 품질조건을 만족할 때만 보조 Feature로 쓴다. S-DoT Collector는
Area Collector와 독립된 후속 책임이며 S-DoT 실패로 Area 수집을 중단하거나 API를
재호출하지 않는다. S-DoT 미지원 6개 Area도 Area 분석과 추천 후보에서 제외하지 않는다.

## 4. Spot Candidate와 추천 경계

현재 Spot Master의 `STATION_CENTER_PROXY`는 판매 위치 확정값이 아니라 Candidate
Anchor Point다. 후보 평가는 다음 독립 근거를 결합한다.

```text
Area Feature
+ 사용할 수 있는 경우의 S-DoT Feature
+ Spatial Context
+ Field Validation
+ Operational Constraints
→ Spot Candidate Evaluation
```

Score·가중치·임계값은 `PLANNED` 또는 `OPEN_DECISION`이며 필수 확정계약이 아니다.

- D-020의 원격 근거 Eligibility를 충족한 Spot이 있으면 `target_level=SPOT`을
  사용한다. 현장검증 불가와 운영 적합성 미확인은 추천 제한으로 표시하되 원격
  SPOT 추천 자체를 차단하지 않는다.
- Spot 근거가 부족하고 Area 근거만 충분하면 `target_level=AREA`로 fallback하고
  `fallback_reason`을 기록한다. Area 근거도 부족하면 추천하지 않는다.
- Recommendation MVP Workstream은 `PLANNED`, Gate number `NOT_ASSIGNED`다.
- EG-6C와 EG-9는 현재 공식 Engineering Gate가 아니다.

## 5. 데이터 보존과 백업 원칙

- 서울시 원본 Raw JSON은 변형·덮어쓰기·자동 삭제하지 않는다.
- Metadata·Collection Log·Manifest와 SHA-256 증거를 원본과 함께 보존한다.
- 분석용 CSV는 Raw에서 재생성할 수 있는 파생자료이며 Raw를 대체하지 않는다.
- CSV 실패는 서울시 API 재호출 사유가 아니다.
- 로컬 외부 output-root의 Batch가 공식 원본이다.
- Google Drive에는 Google Drive for Desktop Sync와 별도 Backup Worker를 사용해 Batch
  완료 직후 검증된 복사본만 저장하는 목표구조를 쓴다.
- `.env`, API Key, 인증 URL과 임시 파일은 백업하지 않는다.
- iCloud와 수동 복사는 현행 공식 백업 방식이 아니다.
- Backup Root는 `FreshManager-Data/` 논리 구조만 정의한다. 실제 계정 이메일과
  동기화 절대경로는 저장소·Receipt·로그에 기록하지 않는다.
- Worker 구현 완료 여부는 [`PROJECT_STATUS.md`](../PROJECT_STATUS.md)에서 확인한다.

## 6. 공식 Roadmap 경계

```text
EG-6A  Area Panel + Spot Candidate Anchor + S-DoT Link
EG-6B  13개 Area 최초 Live Collection
        + EG-6B Quality Review
EG-7   13개 Area 반복수집
        + 독립 S-DoT 접근성·스키마·품질 검증 Workstream
EG-8   데이터 분석·예측·추천 준비 상위 Gate
        EG-8A Python Loader·정규화·데이터 품질
        EG-8B EDA·서울시 Forecast 평가·Baseline·Feature Dataset
        EG-8C 미래 Area 인구·피크 예측 모델
        EG-8D Area Ranking·선택적 S-DoT·Spot Candidate Evaluation
              (기존 EG-8 정의 계승)
        EG-8E Recommendation Output Contract·UI/UX Readiness
              (Recommendation MVP 구현 Gate 아님)
후속   Recommendation MVP Workstream
        상태 PLANNED / Gate number NOT_ASSIGNED / 별도 PM 승인
```

121개 Area 확대는 13개 패널의 단일·반복 수집과 분석에서 필요성이 확인된 뒤 별도
PM 승인으로 검토한다. 동일 13개 Area 반복수집은 `Asia/Seoul` 벽시계 5분이
`PM_APPROVED_FIXED` 장기 기준이며 대안 주기와 중복 기반 변경은 허용하지 않는다.
첫 1시간은 이 고정 기준의 구현·운영 안전성 검증이다. 일일 운영시간대, 24시간 또는
선택 시간 운영, 할당량·용량, Live 실행과 확대 시점은 별도 OPEN이다. 로컬 EG-7의
자동 재시도, 영구 Scheduler와 확대 수집은 기본값이 아니다 — 이는 로컬 EG-7 Live
파일럿 확대에 관한 원칙이며, PoC의 실제 상시 반복수집 Runtime 존재 여부와는 별개다.

### 6.1 PoC 상시 수집 Runtime은 Apps Script다

새 세션이 반복해서 다시 확인해야 하는 핵심 사실:

- PoC의 13개 Area 5분 상시 반복수집은 Google Apps Script가 담당하며 5분 Trigger
  실행과 자동 반복수집 모두 `ACTIVE`다(PM이 Apps Script 화면에서 직접 확인).
  Codex·Claude Code 세션이나 사용자 로컬 컴퓨터의 종료 여부와 무관하게 동작한다.
- 로컬 EG-6B/EG-7(Python)은 상시 Scheduler가 아니라 기술검증·Pilot Runner다.
  새 세션이 "무인 상시수집이 필요하니 로컬 EG-7을 24시간으로 확대"하는 방향으로
  다시 판단하지 않는다.
- Apps Script는 Area 이름이 아니라 공식 POI 코드로 API를 호출하고, Key는 `.env`가
  아니라 Apps Script Script Properties의 `SEOUL_OPEN_API_KEY`에 별도 저장한다.
- 과거 "Apps Script 폐기"(TRD ADR-08, PRD R-09)는 근거 재검토 후 `SUPERSEDED`
  됐다 — 삭제가 아니라 대체 결정(TRD ADR-15, DECISION_LOG 신규 항목)으로 기록한다.
- 복원 경위: 기존 여의도 단일 Area Apps Script 자산 발견 → Script Properties 적용 →
  공식 POI 코드 기반 13개 Area로 확장 → 이전 `v2` 시트의 스키마 혼합 문제 발견 →
  신규 `v3` 시트로 정본 분리 → 수동 1회 실행 검증 → 5분 Trigger 활성화 → 반복
  실행과 데이터 누적을 직접 확인.
- **`ACTIVE`와 `NOT_COMPLETED`를 혼동하지 않는다.** 5분 자동수집 동작은 `ACTIVE`이지만,
  24시간 이상 장기 무중단 지속성 검증은 `NOT_COMPLETED`다. 새 세션은 이 둘을 같은
  의미로 표현하지 않는다. Python ML은 수집 Runtime과 독립적인 관심사이며, "ML이
  Python이므로 수집도 Python이어야 한다"는 추론을 다시 적용하지 않는다.

### 6.2 EG-8은 상위 Gate이며 하위 Gate로 세분화됐다

- 기존 "EG-8 = Area Feature + 선택적 S-DoT Feature + Spot Candidate Evaluation"
  정의는 삭제되지 않고 **EG-8D**로 흡수됐다. 내용은 그대로다.
- EG-8A~8E 순서: Python Loader·정규화·품질(8A) → EDA·Forecast 평가·Baseline·
  Feature Dataset(8B) → 예측 모델(8C) → Ranking·Spot Candidate Evaluation(8D)
  → Recommendation Contract·UI/UX Readiness(8E). 각 하위 Gate는 이전 하위 Gate
  통과 후 순차 진입한다.
- Apps Script는 수집 Runtime, Python은 이후 정규화·분석·ML Runtime이라는 역할
  분리는 §6.1의 결정과 일관된다.
- `v3 source sheets`(Apps Script가 쓰는 원본 Spreadsheet) 자체는 ML-ready
  Dataset이 아니다. EG-8A Python Loader를 거쳐야 정규화 데이터셋이 된다.
- UI/UX 상세 설계(EG-8E)는 Recommendation Output Contract 확정 이후에 진행한다.
  UI는 Model Output을 직접 소비하지 않는다(Model Output → Recommendation
  Output → UI Presentation 계층 분리).
- Recommendation MVP Workstream의 공식 Gate 번호는 여전히 `NOT_ASSIGNED`다.
  EG-8E는 그 준비 단계일 뿐 구현 Gate가 아니다. D-008과 ADR-14는 대체되지
  않았다.

## 7. 새 세션 복원 순서

1. [`AGENTS.md`](../AGENTS.md)
2. [`PROJECT_STATUS.md`](../PROJECT_STATUS.md)
3. 이 문서
4. [PRD](../docs/product/FreshManager_PRD_v1.0.md)
5. [TRD](../docs/engineering/FreshManager_TRD_v1.0.md)
6. 현재 GitHub Issue와 Git 상태
7. 작업 관련 Rule·Quality·Data·Analysis 문서
8. [`DECISION_LOG.md`](DECISION_LOG.md)의 관련 Decision
9. [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md)의 관련 ADR

충돌이 있으면 최신 PM 명시 지시와 `AGENTS.md`의 우선순위를 따르고 임의로 정본을
바꾸지 않는다.
