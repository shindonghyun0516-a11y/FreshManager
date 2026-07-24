# Recommendation Output Contract

- 문서 상태: Draft
- 버전: v0.2.0
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-24
- 최종 수정일: 2026-07-24
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - `AGENTS.md`
  - `docs/product/FreshManager_PRD_v1.0.md`(§5.2 PoC 범위, §14 부록A 용어)
  - `docs/engineering/FreshManager_TRD_v1.0.md`(§19.3 계층 분리 원칙)
  - `docs/testing/QUALITY_GATES.md`(EG-8E 진입·통과조건 정본)
  - `docs/product/EG6_AREA_SPOT_PANEL.md`(Spot Candidate Anchor·S-DoT 정적 연결 정의)
  - `docs/data/ML_READY_DATASET_SPEC.md`(Area-Spot-Sensor 데이터 관계)
  - `docs/analysis/ANALYSIS_PLAN.md`(Spot Forecast 분석 가능성 조건)
  - `ai-context/DECISION_LOG.md`의 D-003, D-004, D-005, D-006, D-008, D-009, D-015
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 EG-8E(Recommendation Output Contract·UI/UX Readiness)가 정의하는
Recommendation Output 스키마를 소유한다. Model Output(EG-8C 예측 모델의 원시
산출값)을 UI Presentation이 직접 소비하지 않도록, 그 사이에 위치하는 중간
계약을 정의한다.

```text
Model Output(EG-8C)
→ Recommendation Output(EG-8E, 이 문서가 정의)
→ UI Presentation(별도 PM 승인 후 상세 설계)
```

이 계층 분리는 모델이 바뀌어도 UI가 직접 깨지지 않게 하려는 목적이며,
`docs/engineering/FreshManager_TRD_v1.0.md` §19.3과 TRD ADR-16이 정의한 원칙과
동일하다.

이 문서는 Recommendation MVP의 구현을 승인하지 않는다. Recommendation MVP
Workstream의 공식 Engineering Gate 번호는 계속 `NOT_ASSIGNED`다(D-008,
ai-context/ARCHITECTURE_DECISIONS.md ADR-011).

**v0.2.0 범위 추가:** 이 문서는 처음에는 "어떤 Area 또는 Spot을 추천할지"만
계약했다. v0.2.0부터는 "특정 Spot 자체의 현재·미래 혼잡 상태를 얼마나 직접적인
근거로 표현할 수 있는지"를 별도 계약(§5~§7)으로 추가한다. **추천 대상이
SPOT이라는 사실과, 그 Spot의 혼잡 상태를 직접 예측할 수 있다는 사실은 같지
않다.** 이 구분이 이 문서의 핵심 확장이다.

## 2. Recommendation Type

허용값은 다음 둘뿐이다.

- `AREA`
- `SPOT`

이는 기존 D-006("추천은 SPOT 우선, AREA fallback")을 그대로 따르며, **"어떤
단위를 추천 결과로 제시할지"**를 결정하는 필드다.

## 3. Prediction Scope

`prediction_scope`는 Recommendation Type과 다른 개념이다.

허용값:

- `AREA`
- `SPOT`

의미:

- `recommendation_type`은 "추천 결과의 단위"를 결정한다.
- `prediction_scope`는 "그 추천에 첨부된 예측(현재·미래 혼잡 상태) 콘텐츠가
  어느 수준의 근거에서 나왔는지"를 결정한다.

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

| `recommendation_type` | `prediction_scope` | 의미 |
|---|---|---|
| `SPOT` | `SPOT` | 이 Spot을 추천하며, Spot 자체의 혼잡 예측도 직접 표시 가능 |
| `SPOT` | `AREA` | 이 Spot을 추천하지만, 예측 근거는 Area 수준(Spot 자체 예측 콘텐츠 미표시) |
| `AREA` | `AREA` | Area를 추천하며, 예측도 Area 수준(일반적인 조합) |
| `AREA` | `SPOT` | 허용하지 않는다(Area 추천에 Spot 단위 예측을 붙이지 않는다) |

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
| `coordinate_type` | 좌표 종류(§6 참조) |
| `field_verified` | 현장검증 여부 |
| `validation_status` | 검증 상태(§6 참조) |

**현재 13개 Spot이 실제 출구로 검증됐다고 기록하지 않는다.** 예시의
`GANGNAM_EXIT_5`/`강남역 5번 출구`는 계약 구조를 설명하기 위한 예시 식별자이며,
실제 Spot Master 데이터가 이 값을 확정했음을 의미하지 않는다. 실제 값은 §6의
기본 상태를 따른다.

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
| `confidence_level` | 신뢰도(§9 참조, `OPEN_DECISION`) |
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

`prediction_scope = AREA`인 레코드에는 이 절의 필드를 채우지 않는다(§3 규칙).

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
문구를 생성하지 않는다.**

| `spatial_support_type` | 허용 표현 예시 |
|---|---|
| `DIRECT_SENSOR` | "강남역 5번 출구는 1시간 뒤 혼잡할 전망입니다." |
| `NEARBY_SENSOR` | "강남역 5번 출구 인근은 1시간 뒤 혼잡할 가능성이 있습니다." |
| `AREA_INFERENCE` | "강남역 Area는 혼잡할 전망입니다. 5번 출구 상태는 확인되지 않았습니다." |
| `UNSUPPORTED` | "5번 출구의 개별 혼잡 상태를 확인할 수 없습니다." |

이 표는 표현 강도의 상한을 정의하며, 실제 UI 문구 템플릿은 후속 UI/UX 상세
설계에서 확정한다.

## 9. SPOT 추천 필드 요구사항

`recommendation_type = SPOT`인 레코드는 다음을 만족해야 한다.

- `spot_id` 필수
- `fallback_reason`은 존재하지 않는다 — 필드 자체를 생략하지 않고 명시적
  `null`로 기록한다(§12.1 null/생략 계약 참조)
- `field_verified` 필수
- `coordinate_type` 필수
- `validation_status` 필수

`prediction_scope = SPOT`이 추가로 성립하면 §6 Spot Forecast Content 필드도
채운다. `prediction_scope = AREA`면 §6 필드는 비운다.

## 10. AREA 추천 필드 요구사항

`recommendation_type = AREA`인 레코드는 다음을 만족해야 한다.

- `spot_id`는 명시적 `null`(§12.1 참조)
- `fallback_reason` 필수(값 존재)
- `prediction_scope`는 항상 `AREA`다(§3 조합표)

## 11. 공통 필드 후보

| 필드 | 의미 |
|---|---|
| `schema_version` | 이 계약의 스키마 버전 |
| `recommendation_id` | 추천 결과 고유 식별자 |
| `generated_at` | 추천 결과 생성 시각 |
| `data_observed_at` | 추천 근거로 사용한 관측 데이터의 기준시각 |
| `data_freshness` | 근거 데이터의 최신성(예: 지연 시간) |
| `recommendation_type` | `AREA` 또는 `SPOT`(§2) |
| `prediction_scope` | `AREA` 또는 `SPOT`(§3) |
| `area_code` | 공식 `AREA_CD` |
| `area_name` | 공식 `AREA_NM` |
| `spot_id` | SPOT 추천 시 필수, AREA 추천 시 명시적 `null` |
| `spot_name`/`spot_type`/`latitude`/`longitude` | Spot Identity(§4) |
| `predicted_peak_at` | Area 수준 예측의 피크 예상시각 |
| `predicted_population_min`/`predicted_population_max` | Area 수준 예측 인구 범위 |
| `trend` | Area 또는 Spot 수준 증가·감소 추세 |
| `spatial_support_type`/`support_source`/`support_sensor_id`/`support_distance_m`/`support_observed_at` | Spatial Evidence(§5) |
| `current_spot_congestion_level`/`predicted_spot_congestion_level`/`forecast_target_at`/`forecast_horizon_minutes`/`expected_peak_at`/`minutes_until_peak`/`forecast_summary` | Spot Forecast Content(§6, `prediction_scope=SPOT`일 때만) |
| `confidence_level` | 신뢰도(§9 `OPEN_DECISION`) |
| `reason_codes` | 추천 사유 코드 목록(§7, §13) |
| `action_message` | 행동 권고 메시지(§7) |
| `fallback_reason` | AREA 추천 시 필수, SPOT 추천 시 명시적 `null` |
| `field_verified` | 현장검증 여부 |
| `coordinate_type` | 좌표 종류(§12) |
| `validation_status` | 검증 상태(§12) |

이 필드 목록은 목표 계약이며 실제 구현 시 확정 스키마는 별도 Issue와 PM
승인으로 정한다.

## 12. Spot 기본 상태

현재 Spot Master(`docs/product/EG6_AREA_SPOT_PANEL.md`)의 모든 행은 다음
기본 상태다.

- `coordinate_type = STATION_CENTER_PROXY`
- `field_verified = false`
- `validation_status = FIELD_VALIDATION_REQUIRED`

이 상태를 실제 검증된 판매 위치로 표현하지 않는다. `STATION_CENTER_PROXY`는
역 중심 대리좌표이며 고정 판매지점이 아니다(D-004).

### 12.1 null과 필드 생략 계약

이 문서 전체에서 "필드가 없다"는 항상 **필드를 생략하는 것이 아니라 명시적
JSON `null`을 기록하는 것**을 의미한다(`docs/data/FIELD_DICTIONARY.md` §8.3의
JSON null 표현 관례와 동일). 예: AREA 추천의 `spot_id`, SPOT 추천의
`fallback_reason`은 모두 키 자체를 생략하지 않고 값을 `null`로 채운다.

## 13. Fallback과 추천 사유

SPOT 추천이 불가능한 경우 AREA 추천으로 전환한다. AREA 추천에는
`fallback_reason`이 반드시 존재해야 한다(§12.1에 따라 값으로 존재, 생략 아님).

Fallback reason 후보는 계약상 Enum 후보로만 기록하며, 확정되지 않은 값은
`OPEN_DECISION`으로 표시한다.

`reason_codes`는 UI 문구와 분리한다(§7). UI 표시 문구는 이 계약이 아니라 후속
UI/UX 상세 설계에서 정한다. 코드 후보 예시:

- `EXPECTED_POPULATION_INCREASE`
- `PEAK_APPROACHING`
- `AREA_RANK_HIGH`
- `DATA_FRESH`
- `NO_FIELD_VERIFIED_SPOT`

실제 최종 Enum은 PM 승인 전까지 확정하지 않는다.

**상태: `OPEN_DECISION`**

## 14. 신뢰도

`confidence_level` 필드는 계약에 둘 수 있으나 산출 규칙과 등급 기준(임계값)은
아직 확정하지 않는다.

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
- (근거 수준이 충족되는 경우) 특정 Spot의 현재·미래 혼잡 또는 여유 상태(§6)

이 경계는 `docs/product/FreshManager_PRD_v1.0.md` §5.4 현재 명시적 비목표와
`docs/rules/DATA_COLLECTION_RULES.md` §16 상권현황 데이터 규칙이 이미 정의한
"카드소비 기반 소비활동 대리변수 ≠ 실제 매출" 원칙과 동일한 절제 원칙을
추천 결과에도 적용한 것이다.

## 16. 완료 정의

이 문서는 다음 조건을 만족해야 Draft를 벗어나 다음 개정을 검토할 수 있다.

- SPOT/AREA 스키마와 상호 배타 필드 규칙 정의
- Prediction Scope와 Recommendation Type의 독립성 정의
- Spot Identity·Spatial Evidence·Spot Forecast Content 계약 정의
- Forecast Summary·Recommendation Reason·Action Message 분리 정의
- 근거 수준별 UI 표현 상한 정의
- Model Output·Recommendation Output·UI Presentation 계층 분리 명시
- Spot 기본 상태(`field_verified=false` 등) 명시
- null과 필드 생략 계약 명시
- Fallback과 reason code 후보를 `OPEN_DECISION`으로 명시
- 판매성과 표현 금지 경계 명시
- PM 승인

## 17. 변경 이력

| 버전 | 날짜 | 변경내용 | 작성자 | 승인상태 |
|---|---|---|---|---|
| v0.2.0 | 2026-07-24 | Spot Identity·Prediction Scope·Spatial Evidence·Spot Forecast Content 계약 추가. Forecast Summary/Reason Codes/Action Message 3계층 분리와 근거 수준별 UI 표현 규칙 추가. 기존 S-DoT 정적 연결과 `spatial_support_type`의 관계 명시. null/필드 생략 계약 명시 | 신동현 | PM 결정 |
| v0.1.0 | 2026-07-24 | 최초 초안 작성(EG-8E Recommendation Output 목표 계약) | 신동현 | PM 결정 |
