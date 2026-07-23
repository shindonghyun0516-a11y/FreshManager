# Recommendation Output Contract

- 문서 상태: Draft
- 버전: v0.1.0
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
  - `docs/product/EG6_AREA_SPOT_PANEL.md`(Spot Candidate Anchor 정의)
  - `ai-context/DECISION_LOG.md`의 D-006, D-008, D-009, D-015
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

## 2. Recommendation Type

허용값은 다음 둘뿐이다.

- `AREA`
- `SPOT`

이는 기존 D-006("추천은 SPOT 우선, AREA fallback")을 그대로 따른다.

## 3. SPOT 추천 필드 요구사항

`recommendation_type = SPOT`인 레코드는 다음을 만족해야 한다.

- `spot_id` 필수
- `fallback_reason` 없음(값이 존재하면 계약 위반)
- `field_verified` 필수
- `coordinate_type` 필수
- `validation_status` 필수

## 4. AREA 추천 필드 요구사항

`recommendation_type = AREA`인 레코드는 다음을 만족해야 한다.

- `spot_id = null`
- `fallback_reason` 필수

## 5. 공통 필드 후보

| 필드 | 의미 |
|---|---|
| `schema_version` | 이 계약의 스키마 버전 |
| `recommendation_id` | 추천 결과 고유 식별자 |
| `generated_at` | 추천 결과 생성 시각 |
| `data_observed_at` | 추천 근거로 사용한 관측 데이터의 기준시각 |
| `data_freshness` | 근거 데이터의 최신성(예: 지연 시간) |
| `recommendation_type` | `AREA` 또는 `SPOT` |
| `area_code` | 공식 `AREA_CD` |
| `area_name` | 공식 `AREA_NM` |
| `spot_id` | SPOT 추천 시 필수, AREA 추천 시 `null` |
| `predicted_peak_at` | EG-8C 예측의 피크 예상시각 |
| `predicted_population_min` | 예측 인구 하한 |
| `predicted_population_max` | 예측 인구 상한 |
| `trend` | 인구 증가·감소 추세 |
| `confidence_level` | 신뢰도(§8 참조, `OPEN_DECISION`) |
| `reason_codes` | 추천 사유 코드 목록(§7 참조) |
| `fallback_reason` | AREA 추천 시 필수, SPOT 추천 시 없음 |
| `field_verified` | 현장검증 여부 |
| `coordinate_type` | 좌표 종류(§6 참조) |
| `validation_status` | 검증 상태(§6 참조) |

이 필드 목록은 목표 계약이며 실제 구현 시 확정 스키마는 별도 Issue와 PM
승인으로 정한다.

## 6. Spot 기본 상태

현재 Spot Master(`docs/product/EG6_AREA_SPOT_PANEL.md`)의 모든 행은 다음
기본 상태다.

- `coordinate_type = STATION_CENTER_PROXY`
- `field_verified = false`
- `validation_status = FIELD_VALIDATION_REQUIRED`

이 상태를 실제 검증된 판매 위치로 표현하지 않는다. `STATION_CENTER_PROXY`는
역 중심 대리좌표이며 고정 판매지점이 아니다(D-004).

## 7. Fallback과 추천 사유

SPOT 추천이 불가능한 경우 AREA 추천으로 전환한다. AREA 추천에는
`fallback_reason`이 반드시 존재해야 한다.

Fallback reason 후보는 계약상 Enum 후보로만 기록하며, 확정되지 않은 값은
`OPEN_DECISION`으로 표시한다.

`reason_codes`는 UI 문구와 분리한다. UI 표시 문구는 이 계약이 아니라 후속
UI/UX 상세 설계에서 정한다. 코드 후보 예시:

- `EXPECTED_POPULATION_INCREASE`
- `PEAK_APPROACHING`
- `AREA_RANK_HIGH`
- `DATA_FRESH`
- `NO_FIELD_VERIFIED_SPOT`

실제 최종 Enum은 PM 승인 전까지 확정하지 않는다.

**상태: `OPEN_DECISION`**

## 8. 신뢰도

`confidence_level` 필드는 계약에 둘 수 있으나 산출 규칙과 등급 기준(임계값)은
아직 확정하지 않는다.

**상태: `OPEN_DECISION`**

## 9. 판매성과 표현 금지

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

이 경계는 `docs/product/FreshManager_PRD_v1.0.md` §5.4 현재 명시적 비목표와
`docs/rules/DATA_COLLECTION_RULES.md` §16 상권현황 데이터 규칙이 이미 정의한
"카드소비 기반 소비활동 대리변수 ≠ 실제 매출" 원칙과 동일한 절제 원칙을
추천 결과에도 적용한 것이다.

## 10. 완료 정의

이 문서는 다음 조건을 만족해야 Draft를 벗어나 다음 개정을 검토할 수 있다.

- SPOT/AREA 스키마와 상호 배타 필드 규칙 정의
- Model Output·Recommendation Output·UI Presentation 계층 분리 명시
- Spot 기본 상태(`field_verified=false` 등) 명시
- Fallback과 reason code 후보를 `OPEN_DECISION`으로 명시
- 판매성과 표현 금지 경계 명시
- PM 승인

## 11. 변경 이력

| 버전 | 날짜 | 변경내용 | 작성자 | 승인상태 |
|---|---|---|---|---|
| v0.1.0 | 2026-07-24 | 최초 초안 작성(EG-8E Recommendation Output 목표 계약) | 신동현 | PM 결정 |
