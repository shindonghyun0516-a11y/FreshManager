# Recommendation Output Contract

- 문서 상태: Draft
- 버전: v0.7.0
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-24
- 최종 수정일: 2026-07-29
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - `AGENTS.md`
  - `docs/product/FreshManager_PRD_v1.0.md`(§5.2 PoC 범위, §14 부록A 용어)
  - `docs/engineering/FreshManager_TRD_v1.0.md`(§19.3 계층 분리 원칙)
  - `docs/testing/QUALITY_GATES.md`(EG-8E 진입·통과조건 정본)
  - `docs/product/EG6_AREA_SPOT_PANEL.md`(Spot Candidate Anchor·S-DoT 정적 연결 정의)
  - `docs/data/ML_READY_DATASET_SPEC.md`(Area-Spot-Sensor 데이터 관계)
  - `docs/analysis/ANALYSIS_PLAN.md`(Spot Forecast 분석 가능성 조건)
  - `docs/product/AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md`(원격 근거 정책)
  - `ai-context/DECISION_LOG.md`의 D-003, D-004, D-005, D-006, D-008, D-009, D-015, D-019, D-020, D-021
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 EG-8E(Recommendation Output Contract·UI/UX Readiness)가 정의하는
Recommendation Output 스키마를 소유한다. Model Output(EG-8C 예측 모델의 원시
산출값)을 UI Presentation이 직접 소비하지 않도록, 그 사이에 위치하는 중간
계약을 정의한다.

```text
서울시 공식 Forecast(D-021 초기 파일럿)
또는 Model Output(장기, 별도 채택 시)
→ Recommendation Output(EG-8E, 이 문서가 정의)
→ UI Presentation(별도 PM 승인 후 상세 설계)
```

초기 파일럿은 EG-8C Model Output을 거치지 않는다. 이 계층 분리는 입력 예측원이
바뀌어도 UI가 직접 깨지지 않게 하려는 목적이며,
`docs/engineering/FreshManager_TRD_v1.0.md` §19.3과 TRD ADR-16이 정의한 원칙과
동일하다.

이 문서는 Recommendation MVP의 구현을 승인하지 않는다. Recommendation MVP
Workstream의 공식 Engineering Gate 번호는 계속 `NOT_ASSIGNED`다(D-008,
ai-context/ARCHITECTURE_DECISIONS.md ADR-011).

### 1.1 장기 원격 SPOT 추천과 운영 적합성의 경계

D-019의 `데이터 기반 우선 후보`는 Issue #126 당시의 원격 준비도 평가결과다.
D-020은 이를 현재 PoC의 최대 출력으로 제한한 부분을 대체한다. §9.1의 원격 근거
Eligibility를 충족하면 현장검증 없이도 `recommendation_type=SPOT`을 사용할 수
있다. 다음은 목표 계약 필드이며 이번 문서 개정만으로 생산 Schema·코드·Database에
구현됐다고 보지 않는다.

```text
verification_mode=REMOTE_EVIDENCE_ONLY
recommendation_basis=REMOTE_EVIDENCE
field_verification_status=UNAVAILABLE
operational_suitability_status=NOT_VERIFIED
```

원격 SPOT 추천과 현장 운영 적합성 보장은 별개다. 원격 추천은 실제 판매 허용·
안전·카트 이동·정차·시설 점유·판매 성공·매출 증가를 보장하지 않는다. 현재
등록된 실제 Spot과 §9.1을 통과한 후보는 0개이므로 현재 추천 결과도 0개다.

### 1.2 초기 파일럿 A안

D-021의 초기 파일럿은 D-020 장기 SPOT 추천을 구현하지 않는다. 시스템은 서울시
공식 Forecast로 Area와 판매시간만 추천하고, 대표 Spot 3개는 순위 없는 사용자
선택지로 별도 제공한다.

초기 대상은 다음 5개 Area로 고정한다.

- `POI032` 서울식물원·마곡나루역
- `POI088` 광화문광장
- `POI014` 강남역
- `POI025` 뚝섬역
- `POI072` 여의도

```text
recommendation_type=AREA
prediction_scope=AREA
recommendation_basis=SEOUL_OFFICIAL_FORECAST
recommendation_forecast_source=SEOUL_OFFICIAL_FORECAST
spot_selection_mode=USER_CHOICE
spot_auto_recommendation=false
machine_learning_used_for_recommendation=false
```

Issue #134의 초기 파일럿 Core(`freshmanager/pilot_area_recommendation.py`)는 다음
계약만 메모리에서 구현한다.

- 60분과 180분을 서로 독립적으로 판정한다.
- EG-8D의 최신 완전 13개 Area Snapshot 선택·검증과 기존 순위 규칙을 재사용한다.
- 해당 Horizon이 `RUNTIME`·`FRESH`이고 완전 Snapshot·Area 표시·Spot 평가 조건을
  모두 통과하며, 위 5개 Area 중 예상 인구 변화가 양수인 후보가 있을 때만
  `pilot_recommendation_allowed=true`와 `recommendation_status=AVAILABLE`을 반환한다.
- 양수 후보가 없으면 `recommendation=null`,
  `pilot_recommendation_allowed=false`, `reason_code=NO_POSITIVE_AREA_OPPORTUNITY`다.
- `official_recommendation_allowed`는 결과와 무관하게 항상 `false`다.
- 선택 Area에는 정확히 3개의 `spot_options`를 순위·기본선택 없이 제공하고,
  `spot_selection_mode=USER_CHOICE`, `spot_auto_recommendation=false`,
  `user_selected_spot_id=null`, `machine_learning_used_for_recommendation=false`를 사용한다.

`spot_options`의 후보는 추천대상 `spot_id`가 아니다. 후보별 직접 유동인구·혼잡·
순위·예측값을 갖지 않으며, 사용자가 직접 선택한다. 이 Core는 파일을 생성하거나
EG-8D 산출물을 갱신·게시하지 않는다. Backend·UI·배포·생산 Database·공식 추천
게시와 실제 파일럿 실행은 구현하거나 승인하지 않는다.

**v0.2.0 범위 추가:** 이 문서는 처음에는 "어떤 Area 또는 Spot을 추천할지"만
계약했다. v0.2.0부터는 "특정 Spot 자체의 현재·미래 혼잡 상태를 얼마나 직접적인
근거로 표현할 수 있는지"를 별도 계약(§5~§7)으로 추가한다. **추천 대상이
SPOT이라는 사실과, 그 Spot의 혼잡 상태를 직접 예측할 수 있다는 사실은 같지
않다.** 이 구분이 이 문서의 핵심 확장이다.

## 2. Recommendation Type

Recommendation Output 레코드의 허용값은 다음 둘뿐이다.

- `AREA`
- `SPOT`

이는 기존 D-006("추천은 SPOT 우선, AREA fallback")을 그대로 따르며, **"어떤
단위를 추천 결과로 제시할지"**를 결정하는 필드다.

D-021 초기 파일럿에서는 `AREA`만 사용한다. 사용자 선택용 Spot 3개가 함께
표시돼도 `recommendation_type=SPOT`으로 바뀌지 않는다.

Area 근거도 부족한 경우에는 새 Enum을 만들지 않고 Recommendation Output
레코드를 생성하지 않는다. 추천하지 않은 이유는 향후 실행·검증 증거에 기록한다.

## 3. Prediction Scope

`prediction_scope`는 Recommendation Type과 다른 개념이다.

허용값:

- `AREA`
- `SPOT`

의미:

- `recommendation_type`은 "추천 결과의 단위"를 결정한다.
- `prediction_scope`는 "그 추천에 첨부된 예측(현재·미래 혼잡 상태) 콘텐츠가
  어느 수준의 근거에서 나왔는지"를 결정한다.

이 문서의 계약 용어 `recommendation_type`은 TRD·Field Dictionary의 향후 저장
필드 `target_level`과 같은 추천 단위를 뜻하며, 서로 다른 판단값으로 취급하지 않는다.
생산 Schema는 아직 구현되지 않았다.

규칙:

- `prediction_scope = AREA`인 결과를 특정 Spot의 직접 예측처럼 표시하지 않는다.
- `prediction_scope = SPOT`은 Spot 단위 근거(§5 Spatial Evidence)와 검증조건을
  충족한 경우에만 허용한다.
- Spot-level 근거가 부족하면 `prediction_scope = AREA`로 fallback한다. 이때도
  `recommendation_type = SPOT`(추천 대상은 Spot)을 유지할 수 있다 — 즉
  **"이 Spot을 추천하지만, 예측 근거는 Area 수준"**이라는 조합이 허용된다.
- Spot의 현재·미래 혼잡을 §6 Spot Forecast Content 필드로 직접 표시하려면
  반드시 `prediction_scope = SPOT`이어야 한다. `prediction_scope = AREA`인
  레코드에는 §6 필드를 채우지 않는다.

다음 조합표로 요약한다.

| 조합 | `recommendation_type` | `prediction_scope` | 상태 |
|---|---|---|---|
| A | `SPOT` | `SPOT` | 허용(조건부, §9.1) |
| B | `SPOT` | `AREA` | 허용(조건부, §9.1) |
| C | `AREA` | `AREA` | 허용(기본 조합, §10) |
| D | `AREA` | `SPOT` | **금지** — 별도 제품 정책 승인 전까지 허용하지 않는다 |

네 조합의 상세 조건과 예시 문구는 §9.1(SPOT Recommendation Eligibility)이
소유한다. 이 절은 개념 구분만 정의하고 조건 상세를 중복 정의하지 않는다.

### 3.1 조합 A — SPOT Recommendation + SPOT Prediction

이 Spot을 추천하고, Spot 자체의 혼잡 예측도 직접 표시한다. §9.1의 Spot
Recommendation Eligibility와 Spot Forecast Eligibility를 모두 충족해야 한다.

### 3.2 조합 B — SPOT Recommendation + AREA Prediction

이 Spot을 추천하지만, 혼잡 예측 콘텐츠는 Area 수준 근거만 사용한다. Spot
자체는 §9.1의 원격 Spot Recommendation Eligibility를
충족해야 하며, Spot Forecast Eligibility(Spot-level 예측 근거)는 충족하지
않아도 된다. 이 조합에서 §6 Spot Forecast Content 필드는 모두 명시적 `null`
이다(§12.1). 추천 판매시간은 Area 기회시간과 사용자 이동·준비 가능시간에서
정하며, 이를 Spot 자체의 예측시간으로 표현하지 않는다.

### 3.3 조합 C — AREA Recommendation + AREA Prediction

Area를 추천하고 예측도 Area 수준이다. 시스템 추천대상 `spot_id`는 명시적
`null`이다. D-021 초기 파일럿은 의도된 AREA 기본 추천이므로
`fallback_reason=null`이며 사용자 선택용 `spot_options` 3개를 별도로 표시할 수
있다. D-020 장기 하향 결과는 `fallback_reason`이 필수다(§10). **현재 실제 Spot
등록과 원격 Eligibility 통과 후보가 0개이므로 이 조합이 현재 가능한 추천의
기본값이다.**

### 3.4 조합 D — AREA Recommendation + SPOT Prediction(금지)

Area를 추천하면서 Spot 단위 예측 콘텐츠를 붙이는 조합은 금지한다. 추천
대상이 Area인데 특정 Spot의 혼잡 상태를 함께 제시하면, 그 Spot이 왜
언급됐는지 근거가 없는 상태로 정밀도를 과장하게 된다. 이 조합이 필요하다고
판단되면 이 문서 개정이 아니라 별도 제품 정책 승인을 먼저 받는다.

## 4. Spot Identity Contract

특정 Spot을 식별하는 계약이다. `docs/product/EG6_AREA_SPOT_PANEL.md`의 Spot
Master를 참조 정본으로 사용하며, 이 문서는 그 식별자를 Recommendation Output에
전달하는 필드만 정의한다.

| 필드 | 의미 |
|---|---|
| `spot_id` | Spot 고유 식별자(예: `GANGNAM_EXIT_5`) |
| `spot_name` | Spot 표시명(예: `강남역 5번 출구`) |
| `spot_type` | Spot 유형(예: `SUBWAY_EXIT`) |
| `latitude` | Spot Master가 보유한 대표좌표 위도 |
| `longitude` | Spot Master가 보유한 대표좌표 경도 |
| `area_code` | 연결된 공식 `AREA_CD` |
| `area_name` | 연결된 공식 `AREA_NM` |
| `coordinate_type` | 좌표 종류(§12 참조) |
| `field_verified` | 현장검증 여부(§12; 원격 추천 Eligibility와 별도 상태) |
| `validation_status` | 검증 상태(§12; 원격 추천 Eligibility와 별도 상태) |

**현재 Spot Master의 13개 Candidate Anchor 행이 실제 출구로 검증됐다고 기록하지 않는다.** 예시의
`GANGNAM_EXIT_5`/`강남역 5번 출구`는 계약 구조를 설명하기 위한 예시 식별자이며,
실제 Spot Master 데이터가 이 값을 확정했음을 의미하지 않는다. 이 표의 각
필드가 `Confirmed`처럼 보이는 것은 "레코드가 존재하고 식별 정보를 담고
있다"는 뜻일 뿐, 실제 출구 등록·SPOT Recommendation 가능·Spot Forecast 가능을
의미하지 않는다. 실제 값은 §12의 기본 상태를 따른다.

## 5. Spatial Evidence Contract

S-DoT 또는 다른 공간 근거가 해당 Spot을 얼마나 직접적으로 대표하는지 구분한다.

| 필드 | 의미 |
|---|---|
| `spatial_support_type` | 근거 수준(아래 4개 값) |
| `support_source` | 근거 출처(예: 센서 유형, Area 추론 등) |
| `support_sensor_id` | 근거로 사용한 센서 식별자(있는 경우) |
| `support_distance_m` | 센서와 Spot 간 거리(미터, 있는 경우) |
| `support_observed_at` | 근거 관측 시각 |

`spatial_support_type` 허용값:

| 값 | 의미 |
|---|---|
| `DIRECT_SENSOR` | 해당 Spot을 직접 대표한다고 검증된 센서 또는 관측 근거 |
| `NEARBY_SENSOR` | Spot 인근에 있으나 해당 Spot 자체를 직접 대표한다고 확정할 수 없는 센서 |
| `AREA_INFERENCE` | Spot 직접 관측 없이 Area 예측만 사용하는 상태 |
| `UNSUPPORTED` | Spot 상태를 판단할 공간 근거가 없는 상태 |

### 5.1 기존 S-DoT 정적 연결과의 관계

`docs/product/EG6_AREA_SPOT_PANEL.md` §6은 이미 Spot별 S-DoT 근접 등급을
`DIRECT_COVERAGE`(3개)·`NEARBY_SUPPORT`(4개)·`NO_NEARBY_SDOT`(6개)로 **정적으로**
분류해 뒀다. 이 정적 분류와 `spatial_support_type`은 같은 개념이 아니다.

- 정적 분류(`DIRECT_COVERAGE` 등)는 "이 Spot 근처에 어떤 센서가 설치돼 있는가"를
  1회 확인한 참조 데이터다.
- `spatial_support_type`은 "이 특정 추천을 생성할 때 실제로 어떤 근거를
  사용했는가"를 매 추천마다 기록하는 값이다.

정적 분류는 `spatial_support_type`이 가질 수 있는 **상한**만 정의한다. 예를
들어 정적 분류가 `NO_NEARBY_SDOT`인 Spot은 `spatial_support_type`이 `DIRECT_SENSOR`
또는 `NEARBY_SENSOR`가 될 수 없다.

**S-DoT 동적 수집은 현재 `NOT_IMPLEMENTED`다(D-005, PRD §5.2).** 동적 수집이
구현되기 전까지는 정적 분류가 `DIRECT_COVERAGE`인 Spot이라도
`spatial_support_type`을 `DIRECT_SENSOR`로 자동 부여하지 않는다. **S-DoT가
존재한다는 사실만으로 `DIRECT_SENSOR`를 부여하지 않으며**, 동적 수집 구현
전까지 `spatial_support_type`은 `AREA_INFERENCE` 또는 `UNSUPPORTED`만
사용한다. 이 원칙은 기존 S-DoT 정적 연결 계약을 대체하거나 그 상태를 임의로
격상하지 않는다.

## 6. Spot Forecast Content Contract

`prediction_scope = SPOT`인 레코드에서만 사용하는, 특정 Spot의 현재·미래 혼잡
또는 여유 상태를 전달하는 필드다.

| 필드 | 의미 |
|---|---|
| `current_spot_congestion_level` | Spot의 현재 혼잡도 |
| `predicted_spot_congestion_level` | Spot의 예측 혼잡도 |
| `forecast_target_at` | 예측이 가리키는 대상시각 |
| `forecast_horizon_minutes` | 예측 리드타임(분) |
| `trend` | 증가·감소·유지 추세 |
| `expected_peak_at` | 예상 피크시각 |
| `minutes_until_peak` | 피크까지 남은 시간(분) |
| `confidence_level` | 신뢰도(§14 참조, `OPEN_DECISION`) |
| `forecast_summary` | 예측 내용을 요약한 문장(§7 참조) |

표현 가능한 콘텐츠:

- 현재 혼잡 또는 여유
- N분·N시간 뒤 혼잡도 상승 예상
- N분·N시간 뒤 혼잡도 하락 예상
- 현재 상태 유지 예상
- 예상 피크시각
- 피크까지 남은 시간
- 현재 대비 인구 증가·감소 전망

예시(충분한 Spot-level 근거가 있는 경우에만 허용):

```text
강남역 5번 출구는 현재 여유 상태지만, 1시간 뒤 혼잡도가 높아질 전망입니다.
```

`prediction_scope = AREA`인 레코드(조합 B, §3.2)에는 이 절의 9개 필드를
**명시적 `null`**로 기록한다 — 필드를 생략하지 않는다(§12.1). 이는 §9.1의
원격 Spot Recommendation Eligibility는 통과했지만 §9.2의 Spot Forecast
Eligibility(Spot-level 예측 근거)는 통과하지 못한 상태를 정확히 표현하기
위함이다.

## 7. Forecast Summary·Recommendation Reason·Action Message 분리

다음 세 계층을 같은 의미로 사용하지 않는다.

| 계층 | 필드 | 설명 | 예시 |
|---|---|---|---|
| Forecast Content | `forecast_summary` | 앞으로 어떤 상태가 될지 설명 | "1시간 뒤 혼잡도가 높아질 전망입니다." |
| Recommendation Reason | `reason_codes` | 왜 이 Area 또는 Spot을 추천하는지 설명 | "점심 피크가 접근 중이고 후보 Area 중 예상 증가폭이 높아 추천합니다." |
| Action Message | `action_message` | 사용자가 어떤 행동을 취해야 하는지 설명 | "오전 11시 40분 이전 이동을 권장합니다." |

`reason_codes`는 §11의 코드 목록을 사용하고 UI 문구와 분리한다.
`forecast_summary`와 `action_message`의 실제 문구 생성 규칙은 이 계약이 아니라
후속 UI/UX 상세 설계에서 정한다. 이 문서는 세 필드가 서로 다른 책임을 가진
별도 필드라는 것만 계약한다.

## 8. 근거 수준별 UI 표현 규칙

`spatial_support_type`별로 허용되는 표현 강도를 제한한다. **근거보다 강한
문구를 생성하지 않는다.** 아래 예시는 모두 §9.1 Eligibility를 통과한
Spot(조합 A 또는 B)을 전제로 한다. §3.3 조합 C에서 Spot을 시스템 추천대상처럼
언급하지 않는다. 다만 D-021 초기 파일럿은 `판매 후보 Spot`이라는 명칭으로
사용자 선택지 3개를 표시할 수 있으며, 후보별 혼잡·순위·추천을 주장하지 않는다.

| 조합·`spatial_support_type` | 허용 표현 예시 |
|---|---|
| 조합 A·`DIRECT_SENSOR` | "강남역 5번 출구는 1시간 뒤 혼잡할 전망입니다." |
| 조합 A·`NEARBY_SENSOR` | "강남역 5번 출구 인근은 1시간 뒤 혼잡할 가능성이 있습니다." |
| 조합 B(`AREA_INFERENCE`/`UNSUPPORTED`와 무관, §3.2 정의상 §6 필드 자체가 없음) | "강남역 Area는 1시간 뒤 혼잡할 전망입니다. 추천 위치는 강남역 5번 출구입니다. 5번 출구 자체의 혼잡 상태는 확인되지 않았습니다." |
| 조합 C·`AREA_INFERENCE` | "강남역 Area는 혼잡할 전망입니다. 출구 단위 혼잡도는 확인되지 않았습니다." |
| `UNSUPPORTED`(Spot 언급이 필요한 예외적 맥락) | "5번 출구의 개별 혼잡 상태를 확인할 수 없습니다." |

**허용 예시(D-021 조합 C)**: "강남역 Area는 1시간 뒤 혼잡할 전망입니다. 판매
후보 Spot 3개 중 이동할 곳을 선택해 주세요. 후보별 혼잡도는 확인되지 않았습니다."

**금지 예시**: 조합 B 또는 C 상태에서 "강남역 5번 출구는 1시간 뒤 혼잡할
전망입니다."처럼 Spot 이름과 Spot 자체의 혼잡 예측을 직접 연결하거나 "5번
출구를 추천합니다"라고 표현하지 않는다. 직접 혼잡 예측 문장은 조합
A·`DIRECT_SENSOR`에서만 허용된다.

이 표는 표현 강도의 상한을 정의하며, 실제 UI 문구 템플릿은 후속 UI/UX 상세
설계에서 확정한다.

## 9. SPOT 추천 필드 요구사항

`recommendation_type = SPOT`인 레코드는 다음을 만족해야 한다.

- `area_code`·`area_name`과 `spot_id`·`spot_name`·`spot_type`·`latitude`·
  `longitude` 필수
- `recommended_sales_start_at`·`recommended_sales_end_at`·
  `recommendation_target_at` 필수
- `recommendation_basis = REMOTE_EVIDENCE` 필수
- `area_opportunity_evidence`·`spot_comparison_evidence` 필수
- `spot_rank`·`compared_spot_count`·`rank_stability` 필수
- `data_observed_at`·`data_freshness` 필수
- `confidence_level`·`limitations` 필수
- `field_verification_status`와 `operational_suitability_status` 필수
- `alternate_spot_id`는 대체 Spot이 없으면 명시적 `null`
- `fallback_reason`은 존재하지 않는다 — 필드 자체를 생략하지 않고 명시적
  `null`로 기록한다(§12.1 null/생략 계약 참조)
- `field_verified` 필수(값은 §12의 현재 상태를 그대로 기록)
- `coordinate_type` 필수
- `validation_status` 필수(값은 §12의 현재 상태를 그대로 기록)

필드가 "존재"하는 것과 그 값이 추천을 허용할 만큼 "충분"한 것은 다르다.
`field_verified=false`와 `validation_status=FIELD_VALIDATION_REQUIRED`는 현장·
운영 상태를 나타낼 뿐 원격 SPOT 추천을 자동 차단하지 않는다.

### 9.1 SPOT Recommendation Eligibility

`recommendation_type = SPOT`을 사용하려면(조합 A·B 공통, §3.1/§3.2)
다음을 **모두** 만족해야 한다.

- Area 판매기회 근거가 유효함
- `spot_id`가 승인된 Spot Master의 실제 후보로 존재하고 Area 연결이 검증됨
- 같은 Area 안에 비교 가능한 Spot이 최소 2개 있음(파일럿 목표 3~5개)
- 각 후보의 공식 명칭과 공식 또는 검증 가능한 위치근거가 있음
- 후보들을 실제로 구분할 수 있는 Spot별 동적 근거 또는 승인된 대리근거가 있음
- 후보를 같은 기준시각과 시간범위에서 비교함
- 반복성 또는 최소 순위 안정성이 확인됨
- 자료 최신성과 결측·이상치 상태를 확인함
- 사용자 이동·준비 가능시간과 추천 판매시간이 정합함
- `confidence_level`을 표시함
- 원격 추천의 제한사항을 표시함

이 조건은 조합 A와 B에 **동일하게** 적용된다. 즉 Spot 자체를 추천 대상으로
제시하려면 예측 콘텐츠 수준(§3.1 vs §3.2)과 무관하게 이 조건을 먼저
통과해야 한다.

현장검증·판매 허용·안전·카트 정차·시설 제한과 운영 적합성은 이 Eligibility가
아니라 별도 상태다. `field_verification_status=UNAVAILABLE`,
`operational_suitability_status=NOT_VERIFIED`인 경우에도 위 조건을 모두 충족하면
원격 SPOT 추천이 가능하지만 해당 제한을 반드시 표시한다.

**현재 13개 행은 실제 Spot이 아닌 Candidate Anchor이고 Area당 하나뿐이며, Spot별
동적 비교·반복성·순위 안정성도 없다. 따라서 현재 §9.1을 충족한 Spot과
`recommendation_type = SPOT` 결과는 0개다**(§3.3 조합 C가 현재 가능한 추천의
기본 조합이다).

### 9.2 Spot Forecast Eligibility

조합 A(§3.1)에서 §6 Spot Forecast Content 필드를 채우려면, §9.1의 조건에
**추가로** 다음을 만족해야 한다.

- `spatial_support_type`이 `DIRECT_SENSOR` 또는 `NEARBY_SENSOR`(§5) —
  `AREA_INFERENCE`·`UNSUPPORTED`면 §6 필드를 채우지 않는다
- Spot-level 관측 근거가 존재(§5의 `support_sensor_id`/`support_observed_at`)
- Spot Forecast 최소 데이터조건을 충족(구체 기준은
  `docs/analysis/ANALYSIS_PLAN.md` §6.6이 소유하며 `OPEN_DECISION`)

조합 B(§3.2)는 §9.1만 충족하면 되고 이 절의 조건은 필요하지 않다 — 조합
B에서는 §6 필드를 애초에 채우지 않기 때문이다.

`prediction_scope = SPOT`이 성립하려면(§9.1과 함께) 이 절의 조건도 충족해야
한다. `prediction_scope = AREA`면 §6 필드는 채우지 않고 명시적 `null`로
둔다(§3.2, §12.1).

## 10. AREA 추천 필드 요구사항

`recommendation_type = AREA`인 레코드는 다음을 만족해야 한다(조합 C, §3.3).

- `spot_id`는 명시적 `null`(§12.1 참조)
- `prediction_scope`는 항상 `AREA`다(§3 조합표, 조합 D는 금지)
- D-021 초기 기본 AREA 추천은 `spot_selection_mode=USER_CHOICE`이고
  `fallback_reason=null`이다.
- D-020 장기 SPOT 추천의 하향 AREA 결과는 `fallback_reason`이 필수다.

**현재 Spot Master의 13개 Candidate Anchor 행이 전부 §9.1의 Eligibility를 충족하지 못하므로, 지금
시점에서는 이 조합이 기본값이다.** 이때 `fallback_reason`의 전형적인 값은
다음과 같다.

```text
fallback_reason = NO_ELIGIBLE_SPOT
```

위 값은 D-020 장기 하향 결과의 예시다. D-021 초기 파일럿에는 사용하지 않는다.

## 11. 공통 필드 후보

| 필드 | 의미 |
|---|---|
| `schema_version` | 이 계약의 스키마 버전 |
| `recommendation_id` | 추천 결과 고유 식별자 |
| `generated_at` | 추천 결과 생성 시각 |
| `data_observed_at` | 추천 근거로 사용한 관측 데이터의 기준시각 |
| `data_freshness` | 근거 데이터의 최신성(예: 지연 시간) |
| `horizon_minutes` | 초기 파일럿은 서로 독립적으로 판정하는 `60` 또는 `180` |
| `recommendation_status` | 메모리 내 Horizon 결과의 `AVAILABLE` 또는 `UNAVAILABLE` |
| `official_recommendation_allowed` | 초기 파일럿 Core에서도 항상 `false` |
| `pilot_recommendation_allowed` | 완전한 `RUNTIME`·`FRESH` Horizon에 양수 후보가 있을 때만 `true` |
| `recommendation_type` | `AREA` 또는 `SPOT`(§2) |
| `verification_mode` | 원격 경로는 `REMOTE_EVIDENCE_ONLY` |
| `recommendation_basis` | 추천 근거 유형; 초기 파일럿은 `SEOUL_OFFICIAL_FORECAST`, 장기 원격 SPOT은 `REMOTE_EVIDENCE` |
| `recommendation_forecast_source` | 초기 파일럿 추천 Forecast Source; `SEOUL_OFFICIAL_FORECAST` |
| `machine_learning_used_for_recommendation` | 초기 파일럿은 `false`; 기존 비교실험과 추천 사용 여부를 분리 |
| `prediction_scope` | `AREA` 또는 `SPOT`(§3) |
| `area_code` | 공식 `AREA_CD` |
| `area_name` | 공식 `AREA_NM` |
| `area_opportunity_evidence` | Area 판매기회와 유효시간 근거 |
| `spot_id` | SPOT 추천 시 필수, AREA 추천 시 명시적 `null` |
| `spot_name`/`spot_type`/`latitude`/`longitude` | Spot Identity(§4) |
| `spot_selection_mode` | 초기 파일럿은 `USER_CHOICE` |
| `spot_auto_recommendation` | 초기 파일럿은 `false` |
| `spot_role` | 초기 파일럿 선택지는 `USER_SELECTABLE_OPTION` |
| `spot_options` | 초기 파일럿의 순위 없는 사용자 선택 후보 정확히 3개; 추천 `spot_id`와 별개 |
| `user_selected_spot_id` | 사용자가 선택한 후보 식별자; 선택 전 `null`, 생산 필드명은 구현 Issue에서 확정 |
| `recommended_sales_start_at`/`recommended_sales_end_at` | 추천 판매 시작·종료시각 |
| `recommendation_target_at` | 추천 판단이 대상으로 삼은 예측시각 |
| `spot_comparison_evidence` | 후보별 유동인구·밀집도 또는 승인 대리근거 요약 |
| `spot_rank`/`compared_spot_count` | Area 내부 순위와 비교 후보 수 |
| `rank_stability` | 반복성 또는 순위 안정성 근거 |
| `alternate_spot_id` | Eligibility를 충족한 대체 Spot; 없으면 명시적 `null` |
| `predicted_peak_at` | Area 수준 예측의 피크 예상시각 |
| `predicted_population_min`/`predicted_population_max` | Area 수준 예측 인구 범위 |
| `trend` | Area 또는 Spot 수준 증가·감소 추세 |
| `spatial_support_type`/`support_source`/`support_sensor_id`/`support_distance_m`/`support_observed_at` | Spatial Evidence(§5) |
| `current_spot_congestion_level`/`predicted_spot_congestion_level`/`forecast_target_at`/`forecast_horizon_minutes`/`expected_peak_at`/`minutes_until_peak`/`forecast_summary` | Spot Forecast Content(§6, `prediction_scope=SPOT`일 때만) |
| `confidence_level` | `HIGH`, `MEDIUM`, `LOW` 중 하나(산출기준은 §14 `OPEN_DECISION`) |
| `reason_codes` | 추천 사유 코드 목록(§7, §13) |
| `action_message` | 행동 권고 메시지(§7) |
| `limitations` | 원격 추천의 미확인 항목과 사용 제한 |
| `fallback_reason` | D-021 초기 AREA 기본 추천은 `null`; D-020 장기 하향 AREA는 필수; SPOT 추천은 `null` |
| `field_verified` | 현장검증 여부 |
| `field_verification_status` | 현장검증 상태; 현재 원격 경로는 `UNAVAILABLE` |
| `operational_suitability_status` | 운영 적합성 상태; 미확인은 `NOT_VERIFIED` |
| `coordinate_type` | 좌표 종류(§12) |
| `validation_status` | 검증 상태(§12) |

이 필드 목록은 목표 계약이며 이번 개정으로 생산 Schema가 변경된 것은 아니다.
실제 구현 시 확정 스키마는 별도 Issue와 PM 승인으로 정한다.

D-021 초기 파일럿에서 `spot_comparison_evidence`, `spot_rank`, `rank_stability`,
`alternate_spot_id`와 Spot Forecast Content는 모두 `null`이다. `spot_options`는
후보명·위치 설명과 미확인 상태만 담고 Spot별 Area 예측값을 복사하지 않는다.

## 12. Spot 기본 상태

현재 Spot Master(`docs/product/EG6_AREA_SPOT_PANEL.md`)의 모든 행은 다음
기본 상태다.

- `coordinate_type = STATION_CENTER_PROXY`
- `field_verified = false`
- `validation_status = FIELD_VALIDATION_REQUIRED`

이 상태를 실제 검증된 판매 위치로 표현하지 않는다. `STATION_CENTER_PROXY`는
역 중심 대리좌표이며 고정 판매지점이 아니다(D-004).

`validation_status`의 값 공간은 최소 다음 둘을 포함한다.

| 값 | 의미 |
|---|---|
| `FIELD_VALIDATION_REQUIRED` | 기존 Spot Master의 현재 기본값. D-019 원격 평가상태와 별개 |
| `VERIFIED` | 현장검증·운영 적합성 확인 완료 |

`VERIFIED`로의 전환 절차와 판정 기준은 이 문서가 정의하지 않으며 별도 Issue와
PM 승인이 필요하다. 이 값은 운영 적합성 상태이며 §9.1 원격 추천 Eligibility와
분리한다.

### 12.1 null과 필드 생략 계약

이 문서 전체에서 "필드가 없다"는 항상 **필드를 생략하는 것이 아니라 명시적
JSON `null`을 기록하는 것**을 의미한다(`docs/data/FIELD_DICTIONARY.md` §8.3의
JSON null 표현 관례와 동일). 예: AREA 추천의 `spot_id`, SPOT 추천의
`fallback_reason`은 모두 키 자체를 생략하지 않고 값을 `null`로 채운다.

## 13. Fallback과 추천 사유

D-021 초기 파일럿은 처음부터 AREA를 추천하므로 fallback이 아니다.
`spot_selection_mode=USER_CHOICE`와 `fallback_reason=null`을 사용한다.

D-020 장기 계약에서 Spot 근거가 부족하고 Area 근거만 충분하면 AREA 추천으로
전환하고 `fallback_reason`을 반드시 기록한다(§12.1에 따라 생략하지 않음). Area
근거도 부족·노후·충돌 상태면 Recommendation Output 레코드를 생성하지 않는다.

Fallback reason 후보는 계약상 Enum 후보로만 기록하며, 확정되지 않은 값은
`OPEN_DECISION`으로 표시한다.

`reason_codes`는 UI 문구와 분리한다(§7). UI 표시 문구는 이 계약이 아니라 후속
UI/UX 상세 설계에서 정한다. 코드 후보 예시:

- `EXPECTED_POPULATION_INCREASE`
- `PEAK_APPROACHING`
- `AREA_RANK_HIGH`
- `DATA_FRESH`
- `NO_ELIGIBLE_SPOT`

실제 최종 Enum은 PM 승인 전까지 확정하지 않는다.

**상태: `OPEN_DECISION`**

## 14. 신뢰도

`confidence_level`의 허용값은 `HIGH`, `MEDIUM`, `LOW`다. 산출 규칙과 등급
기준(임계값)은 아직 확정하지 않는다.

**상태: `OPEN_DECISION`**

## 15. 판매성과 표현 금지

추천 결과는 다음을 의미하지 않는다.

- 매출 증가 보장
- 판매량 보장
- 판매 성공확률
- 구매전환 가능성
- 제품 수요예측

다음처럼만 표현한다.

- 미래 Area 인구
- 인구 증가 추세
- 피크 임박도
- Area 상대 순위
- 공간 보조정보 기반 Spot 후보
- §9.1을 충족한 특정 Spot과 추천 판매시간
- (근거 수준이 충족되는 경우) 특정 Spot의 현재·미래 혼잡 또는 여유 상태(§6)

특정 Spot과 판매시간을 추천해도 실제 판매 허용·안전·카트 정차·시설 점유·운영
적합성·판매 성공을 보장하지 않는다.

이 경계는 `docs/product/FreshManager_PRD_v1.0.md` §5.4 현재 명시적 비목표와
`docs/rules/DATA_COLLECTION_RULES.md` §16 상권현황 데이터 규칙이 이미 정의한
"카드소비 기반 소비활동 대리변수 ≠ 실제 매출" 원칙과 동일한 절제 원칙을
추천 결과에도 적용한 것이다.

## 16. 완료 정의

이 문서는 다음 조건을 만족해야 Draft를 벗어나 다음 개정을 검토할 수 있다.

- SPOT/AREA 스키마와 상호 배타 필드 규칙 정의
- Prediction Scope와 Recommendation Type의 독립성 정의
- SPOT+SPOT/SPOT+AREA/AREA+AREA/AREA+SPOT 4개 조합의 허용·금지와 조건 정의
- Spot Recommendation Eligibility와 Spot Forecast Eligibility를 분리 정의
- 원격 SPOT 추천 Eligibility와 현장·운영 적합성 상태를 분리 정의
- Spot Identity·Spatial Evidence·Spot Forecast Content 계약 정의
- Forecast Summary·Recommendation Reason·Action Message 분리 정의
- 근거 수준별·조합별 UI 표현 상한 정의
- Model Output·Recommendation Output·UI Presentation 계층 분리 명시
- Spot 기본 상태와 `validation_status` 값 공간(`FIELD_VALIDATION_REQUIRED`/`VERIFIED`) 명시
- null과 필드 생략 계약 명시
- Fallback과 reason code 후보를 `OPEN_DECISION`으로 명시
- SPOT·AREA·추천 없음 하향계약 명시
- D-021 초기 AREA 추천과 사용자 선택 Spot 3개를 시스템 SPOT 추천과 분리
- 초기 AREA 기본 추천과 장기 AREA fallback의 `fallback_reason` 차이 명시
- Issue #134 메모리 내 Core의 Horizon별 허용·추천 없음·비게시 계약 명시
- 판매성과 표현 금지 경계 명시
- PM 승인

## 17. 변경 이력

| 버전 | 날짜 | 변경내용 | 작성자 | 승인상태 |
|---|---|---|---|---|
| v0.7.0 | 2026-07-29 | Issue #134 초기 파일럿 메모리 내 Core 계약 반영. 5개 Area, 60·180분 독립 판정, RUNTIME·FRESH·완전 Snapshot·양수 후보 조건, 추천 없음 null, 별도 파일럿 허용값, 사용자 선택 Spot 3개와 비게시 경계를 명시 | 신동현 | Draft PR 검토 대기 |
| v0.6.0 | 2026-07-29 | D-021 초기 파일럿 A안 반영. AREA·판매시간 추천과 사용자 선택 Spot 3개를 시스템 SPOT 추천과 분리하고 서울시 공식 Forecast·ML 미사용·초기 AREA 비-fallback 계약을 추가. 생산 Schema는 미구현 상태 유지 | 신동현 | PM 결정 |
| v0.5.0 | 2026-07-29 | D-020에 따라 원격 SPOT 추천 Eligibility와 현장·운영 적합성을 분리. 판매시간·비교순위·원격근거·제한 필드 후보, SPOT·AREA·추천 없음 하향계약과 신뢰도 값 공간을 추가. 생산 Schema는 미구현 상태 유지 | 신동현 | PM 결정 |
| v0.4.0 | 2026-07-29 | D-019의 데이터 기반 우선 후보를 공식 Recommendation Output 전 단계로 분리. 원격 검증 정책값과 운영 적합성 미검증 경계를 추가하고 현재 PoC가 공식 SPOT Recommendation을 생성하지 않음을 명시 | 신동현 | PM 결정 |
| v0.3.0 | 2026-07-24 | SPOT+SPOT/SPOT+AREA/AREA+AREA/AREA+SPOT 4개 조합을 명시적으로 계약화(§3.1~3.4). Spot Recommendation Eligibility(§9.1)와 Spot Forecast Eligibility(§9.2)를 분리해 `field_verified`/`validation_status`의 값 기준(단순 존재가 아니라 `true`/`VERIFIED`)을 명확히 함. `validation_status` 값 공간에 `VERIFIED` 추가(§12). AREA-scope일 때 Spot Forecast 필드가 명시적 null임을 명시(§6). 근거 수준·조합별 UI 표현표에 조합 B 예시와 금지 예시 추가(§8) | 신동현 | PM 결정 |
| v0.2.0 | 2026-07-24 | Spot Identity·Prediction Scope·Spatial Evidence·Spot Forecast Content 계약 추가. Forecast Summary/Reason Codes/Action Message 3계층 분리와 근거 수준별 UI 표현 규칙 추가. 기존 S-DoT 정적 연결과 `spatial_support_type`의 관계 명시. null/필드 생략 계약 명시 | 신동현 | PM 결정 |
| v0.1.0 | 2026-07-24 | 최초 초안 작성(EG-8E Recommendation Output 목표 계약) | 신동현 | PM 결정 |
