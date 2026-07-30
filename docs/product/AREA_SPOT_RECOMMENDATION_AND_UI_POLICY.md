# Area·Spot 판매 추천과 지도 UI 정책

- 상태: `PM_APPROVED`
- 기준일: 2026-07-31
- 관련 Issue: #124, #126, #128, #129, #132, #140, #146
- 상위 Issue: #99
- 선행 결정: D-018, D-020, D-021, D-022

이 문서는 D-022 초기 Area-first 사용자 선택 흐름, D-021 다중 Area 비교의 내부
분석 이력과 D-020 장기 원격 SPOT 추천 정책을 함께 정의한다. 정책 문서일 뿐 UI,
추천 계산, 지도 API 또는 사용자 게시를 구현하거나 승인하지 않는다. 초기 화면의
상세 정본은 `AREA_FIRST_WEB_PILOT_CONTRACT.md`, 추천 결과의 필드·null·fallback
계약은 `RECOMMENDATION_OUTPUT_CONTRACT.md`가 소유한다.

## 1. 서비스 목적

초기 파일럿은 사용자가 승인된 5개 중 담당 Area를 직접 선택하고, 선택 Area의
서울시 공식 현재·1시간 후·3시간 후 정보와 대표 Spot 3개를 확인해 이동할 지점을
직접 고르게 돕는다. Area·Spot 자동추천은 없으며, Spot별 값은 명확히 배지된
`PM_MANUAL` 프로토타입으로만 Area 공식 데이터와 분리해 표시한다. D-021
Core·Service는 다중 Area 비교 내부 분석 기능으로 보존하며 Area-first 기본 UX나
Primary API가 아니다.

장기 목표는 Area 안의 복수 Spot을 유동인구·밀집도·반복패턴으로 비교해 특정
Spot과 판매시간을 추천하는 것이다. 원격 SPOT 추천은 현장 운영 적합성 보장과
다르며 실제 판매 허용·안전·카트 정차·시설 점유·판매 성공·매출 증가를 보장하지 않는다.

## 2. Area 정의

Area는 판매기회와 유효 판매시간을 탐색하는 넓은 구역이다. 초기 화면은 사용자가
선택한 Area의 현재·1시간 후·3시간 후 정보를 제공한다. D-021 내부 분석은
서울시 공식 Forecast 기반 다중 Area 기회 비교로 제한한다.
강남역, 여의도, 잠실역, 구로디지털단지역 등이 예다.

Area 값은 Area 전체의 관측·예측 근거다. 특정 출구나 Spot의 직접 유동인구 또는
밀집도로 바꾸어 표현하지 않는다.

## 3. Spot 정의

Spot은 Area 안의 유동인구·밀집도와 반복패턴을 비교해 프래시매니저가 실제
이동·판매하도록 추천받는 특정 지점이다. 출구, 오피스 출입구, 버스정류장 인근,
광장 출입구 등이 될 수 있다. 원격 근거 Eligibility를 충족하면 현장검증 없이도
최종 SPOT 추천 대상이 될 수 있다.

초기 파일럿에서는 역할이 다르다. 대표 Spot 3개는
`spot_role=USER_SELECTABLE_OPTION`이며, 시스템 추천·순위 대상이 아니다. 장기
D-020의 Spot은 Eligibility를 통과한 `SYSTEM_RECOMMENDATION_TARGET`이다.

현재 Spot Master의 13개 행은 모두 역 중심 대리좌표인 Candidate Anchor다. 공식 출구나
검증된 판매 위치가 아니며 `field_verified=false`다.

초기 파일럿의 사용자 선택지는 별도 정본
`data/reference/pilot_spot_options.csv`의 5개 Area·15개 행이다. 이 행은 PM이 공개
지도에서 확인한 대표 위치지만 현장검증·운영 적합성·Spot별 동적근거가 없으며,
시스템 추천이나 추천순위가 아닌 같은 수준의 사용자 선택지다.

13개 Area에는 각각 Candidate Anchor 1개만 연결돼 있다. 이는 실제 출구·흡연부스·
오피스 입구·광장·버스정류장 같은 판매 후보가 아니라 실제 후보 구성을 위한
기준점이다. 현재는 Area당 역 중심 Candidate Anchor 1개만 존재하므로 Area 내부
Spot 비교와 순위 산정이 불가능하며, 최종 Spot 추천도 계산할 수 없다. Anchor를
실제 출구나 판매지점으로 자동 변환·승격하지 않으며, 다음 필수단계는 Area별 복수의
실제 후보 Spot을 원격 근거로 구성하는 것이다.

## 4. 사용자 흐름

### 4.1 초기 Area-first 파일럿

1. 사용자가 승인된 5개 중 담당 Area를 직접 선택한다.
2. 선택 Area의 서울시 공식 현재·1시간 후·3시간 후 정보와 대표 Spot 3개를
   같은 수준의 선택지로 표시한다.
3. 사용자가 이동할 Spot을 직접 선택한다.
4. 현장검증·운영 적합성 미확인 상태와 한계를 함께 표시한다.

### 4.2 장기 D-020 흐름

1. 지도나 검색목록에서 Area를 고른다.
2. Area의 판매기회와 유효 판매시간을 확인한다.
3. Area 안의 복수 Spot과 각 후보의 원격 근거·제한을 비교한다.
4. 원격 근거 Eligibility를 충족한 밀집도 우위 Spot과 판매시간을 추천한다.
5. 추천근거·신뢰도·제한사항을 확인한다.
6. 사용자가 해당 Spot으로 이동해 판매한다.

## 5. Spot 결과 예시

초기 파일럿에서 허용하는 문구는 다음과 같다.

> 사용자가 선택한 강남역 Area의 현재·1시간 후·3시간 후 공식 정보가 표시됩니다.
> 판매 후보 Spot은 강남스퀘어, CGV강남 앞, 점프밀라노 앞입니다.
> 이동할 Spot을 선택해 주세요.

다음 문구는 Spot별 직접근거와 자동추천이 없는 초기 파일럿에서 금지한다.

> 강남스퀘어의 밀집도가 가장 높습니다. 강남스퀘어에서 판매할 것을 추천합니다.

다음은 장기 원격 SPOT Eligibility와 Recommendation Output Contract §9.2의 직접
Spot 근거(`DIRECT_SENSOR`)까지 충족한 미래 상태를 설명하는 조건부 예시다.
현재 강남역 Anchor나 실제 1번 출구 등록을 뜻하지 않는다.

> 강남역 Area에서 후보 Spot을 비교한 결과 1번 출구 Spot의 유동인구 밀집도가
> 가장 높아 12시 30분부터 13시 30분까지 해당 Spot에서 판매할 것을 추천합니다.
>
> 이 추천은 원격 데이터에 기반합니다. 실제 판매 허용 여부, 안전성 및 카트 정차
> 가능성은 확인되지 않았습니다.

현재 강남역 Anchor를 특정 출구로 해석하지 않는다. 원격 SPOT 추천에는
정확한 Spot 정체성, 공식 또는 검증 가능한 좌표 출처, S-DoT 또는 대체 동적 근거,
같은 Area의 복수 후보 비교, 반복성·최신성·불확실성 기록이 필요하다. 원격자료로
접근성·안전·카트 정차·판매 허용과 운영 적합성을 확정하지 않는다.

> 강남역 Area의 유동인구 증가가 예상됩니다. 역 중심 Candidate Anchor는 실제
> 출구나 판매지점이 아니며 Spot별 근거가 부족해 판매 후보로만 표시합니다.

## 6. Area와 Spot 근거 구분

- Area 기회는 Area Observation과 승인된 Area 분석·예측 결과로 판단한다.
- Area Observation은 모든 Area에 필요한 Core Observation이다.
- S-DoT Observation은 지원·접근·수집·품질조건을 만족할 때 Area 안 Spot별
  시간대 밀집도를 확인·비교하기 위한 Optional Supporting Observation 후보다.
  모든 Area의 필수자료가 아니며 미지원 Area도 Area 분석에서 제외하지 않는다.
- Spot 기회는 Spot 자체의 시간대별 동적 근거와 Area 안 다른 Spot과의 비교로
  판단한다.
- 현재 S-DoT 공간 연결은 역 중심 Candidate Anchor를 기준으로 수집·결합 대상을
  정하기 위한 사전 연결이다. `DIRECT_COVERAGE`도 특정 출구나 판매지점을 센서가
  직접 측정한다는 뜻이 아니다.
- 실제 후보 Spot이 정해지면 실제 좌표를 기준으로 센서 거리와 연결등급을 다시
  계산하고, 필요하면 센서군과 측정범위를 검토한다. 공간 근접성만으로 밀집도를
  확정하지 않는다.
- 실제 시간대별 관측값과 실제 Spot 좌표·시간·측정범위를 결합하고, 기준시각·
  측정시간 정렬, 최신성·결측과 다중 데이터 간 일치성을 확인한 뒤에만 Spot의
  동적 밀집근거로 사용할 수 있다.
- Area 인구를 Spot 인구로 복사하거나 중간값·가장 가까운 값을 대신 사용하지
  않는다.
- 초기 파일럿의 후보 3개에 Area 예측값을 복사하거나 Spot별 순위·기본선택을
  부여하지 않는다.
- Spot 직접값이나 선택적 동적 근거가 부족하면 Spot 숫자와 SPOT 추천을 만들지
  않고 AREA 안내 또는 판매 후보로 하향하며 근거 부족을 명시한다.

현재 완료된 범위는 Candidate Anchor 13개, Anchor 기준 S-DoT 공간 연결 13개,
직접 지원 후보 3개·인근 지원 후보 4개·가까운 센서 없음 6개, 2026-07-06부터
2026-07-12까지의 과거 주간자료에 근거한 최근 활성 확인 이력과 S-DoT 활용 개념
정의다. 신규 수집 없이 이를 현재 활성상태로 표현하지 않는다.

미완료 범위는 실제 출구·판매지점 좌표, 실제 Spot 좌표 기준 S-DoT 재연결,
독립적으로 재현 가능한 S-DoT 시간대 수집, Spot별 S-DoT Feature, Area·S-DoT
관측시간 정렬, Area 안 복수 Spot 비교, 반복성·Backtesting과 우선순위 규칙 구현이다.

## 7. Spot 추천 준비상태

사용자 화면에는 다음 쉬운 한국어 상태를 사용한다. 별도 영문 코드값은 현재
필요하지 않으므로 새로 만들지 않는다.

| 상태 | 적용 기준 | 사용자 안내 |
|---|---|---|
| 정보 없음 | 위치 또는 기본 근거가 부족함 | 결과를 만들지 않음 |
| 판매 후보 | 위치와 정적 장소근거는 있으나 비교·동적 근거가 부족함 | 후보로만 표시 |
| 원격 근거 확인 중 | 공식 위치·동적·반복 자료 중 일부만 확인됨 | 제한사항과 함께 표시 |
| 원격 데이터 기반 SPOT 추천 | §8의 원격 근거 Eligibility를 모두 충족함 | 특정 Spot·판매시간과 운영 미확인 제한을 함께 표시 |
| 추천 제외 | 공식 제한, 오래된 자료, 근거 충돌 또는 품질 결함 | 후보에서 제외 |

현재 집계는 원격 데이터 기반 SPOT 추천 0개, 기존 Candidate Anchor 13개,
초기 파일럿 사용자 선택 Spot 15개다. 사용자 선택 Spot은 모두
`field_verification_status=UNAVAILABLE`,
`operational_suitability_status=NOT_VERIFIED`이며 판매 후보일 뿐 공식 추천이 아니다.

기존 Candidate Anchor 13개에는 다음 상태가 적용된다.

- 좌표 유형: `STATION_CENTER_PROXY`
- Spot 유형: `SUBWAY_STATION_CENTER_PROXY`
- 측정범위 또는 Spot 반경: 확인되지 않음
- 시간대별 Spot 동적 유동인구·밀집시간: 확인되지 않음
- 현장검증 상태: `UNAVAILABLE`
- 접근 가능성·안전·판매 가능성·마지막 확인일: 확인되지 않음
- 운영 적합성: `NOT_VERIFIED`
- 현재 결과범위: 판매 후보; 공식 추천 아님

초기 파일럿 사용자 선택 Spot 15개에는 다음 상태가 적용된다.

- 좌표 상태: `PM_CONFIRMED`
- 좌표 출처 유형: `PM_PROVIDED_PUBLIC_MAP_LOOKUP`
- 역할·선택 방식: `USER_SELECTABLE_OPTION`·`USER_CHOICE`
- 표시순서: 추천순위나 기본선택이 아님
- 시간대별 Spot 동적 유동인구·혼잡도: 없음
- 현장검증·운영 적합성: `UNAVAILABLE`·`NOT_VERIFIED`
- 현재 결과범위: 사용자가 직접 고르는 판매 후보; 공식 추천 아님

| Spot ID | Spot / 소속 Area | 좌표 | 정적 장소근거와 S-DoT 거리 참고 | 현재 상태 | 추천을 막는 부족정보 |
|---|---|---|---|---|---|
| `SPOT-EG6-001` | 구로디지털단지역 역 중심 대용점 / `POI019` 구로디지털단지역 | 37.4852660, 126.9014010 | 오피스 통근권 후보 기준점; `NO_NEARBY_SDOT` 1,471.9m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-002` | 가산디지털단지역 역 중심 대용점 / `POI013` 가산디지털단지역 | 37.4809595, 126.8826185 | 오피스 통근권 후보 기준점; `NO_NEARBY_SDOT` 837.0m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-003` | 강남역 역 중심 대용점 / `POI014` 강남역 | 37.4974135, 127.0280080 | 출구별 후보 비교 기준점; `DIRECT_COVERAGE` 120.5m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-004` | 여의도역 역 중심 대용점 / `POI072` 여의도 | 37.5217535, 126.9241935 | 오피스 보행 후보 기준점; `NO_NEARBY_SDOT` 2,278.1m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-005` | 삼성역 강남 MICE·코엑스 방향 역 중심 대용점 / `POI001` 강남 MICE 관광특구 | 37.5088570, 127.0632000 | 복합권 원격 후보 기준점; `NO_NEARBY_SDOT` 1,033.5m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-006` | 선릉역 역 중심 대용점 / `POI034` 선릉역 | 37.5045710, 127.0485050 | 업무 통근권 후보 기준점; `NEARBY_SUPPORT` 204.1m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-007` | 역삼역 역 중심 대용점 / `POI042` 역삼역 | 37.5006220, 127.0364560 | 업무지구 보행 후보 기준점; `NO_NEARBY_SDOT` 892.1m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-008` | 뚝섬역 역 중심 대용점 / `POI025` 뚝섬역 | 37.5471840, 127.0473670 | 업무·창업·상업권 후보 기준점; `DIRECT_COVERAGE` 56.4m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-009` | 광화문역 광화문광장 방향 역 중심 대용점 / `POI088` 광화문광장 | 37.5715250, 126.9771700 | 광장 보행 후보 기준점; `NEARBY_SUPPORT` 264.8m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-010` | 을지로입구역 명동·다동 방향 역 중심 대용점 / `POI003` 명동 관광특구 | 37.5660140, 126.9826180 | 업무·상업 보행 후보 기준점; `NEARBY_SUPPORT` 173.2m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-011` | 잠실역 역 중심 대용점 / `POI119` 잠실역 | 37.5139770, 127.1022485 | 출구별 후보·센서 경계 기준점; `NEARBY_SUPPORT` 273.6m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-012` | 서울역 역 중심 대용점 / `POI033` 서울역 | 37.5547706, 126.9713248 | 출구별 후보 비교 기준점; `NO_NEARBY_SDOT` 605.0m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |
| `SPOT-EG6-013` | 마곡나루역 역 중심 대용점 / `POI032` 서울식물원·마곡나루역 | 37.5661605, 126.8273440 | 업무·공원 복합권 후보 기준점; `DIRECT_COVERAGE` 122.3m | 판매 후보 | 동적 근거·Area 내 비교·반복성·최신성·원격 운영제한 |

## 8. 장기 원격 데이터 기반 SPOT 추천 Eligibility

이 절은 D-020 장기 자동추천 조건이다. D-022 초기 Area 선택이나
`USER_SELECTABLE_OPTION` 3개 구성의 Hard Filter로 사용하지 않는다.

원격 SPOT 추천은 다음을 모두 요구한다.

1. 유효한 Area 판매기회 근거
2. 같은 Area 안의 비교 가능한 Spot 최소 2개(파일럿 목표 3~5개)
3. 후보의 공식 명칭과 공식 또는 검증 가능한 위치근거
4. 후보들을 실제로 구분할 수 있는 Spot별 동적 근거 또는 승인된 대리근거
5. 같은 기준시각·시간범위의 후보 비교
6. 반복성 또는 최소 순위 안정성
7. 자료 최신성과 결측·이상치 관리
8. 사용자 이동·준비 가능시간과 추천시간의 정합
9. 추천 신뢰도
10. 제한사항 표시

S-DoT 존재나 후보 수만으로 추천하지 않는다. 운영 적합성·판매 허용·안전·카트
정차·시설 제한과 현장검증은 Eligibility가 아니라 별도 상태로 관리한다.

## 9. 추천 판단 구조

### 초기 파일럿

1. 사용자가 승인된 5개 중 담당 Area를 직접 선택한다.
2. 선택 Area의 서울시 공식 현재·1시간 후·3시간 후 정보와 대표 Spot 3개를
   순위 없이 표시한다.
3. 사용자가 이동할 Spot을 직접 선택한다.

D-021 Recommendation Core·Service의 서울시 Forecast 기반 다중 Area 비교는
내부 분석 기능과 구현 이력으로만 유지한다.

### 장기 원격 SPOT 추천

### 1단계 — Area 기회

미래 유동인구 증가, 밀집 시작시각과 사용자의 이동 가능시간을 판단한다.

### 2단계 — 원격 Spot 비교

공식 위치·시설정보, 후보별 직접·대리 동적 근거, 반복성, 최신성과 공개된 운영
제한을 같은 Area 안에서 비교한다.

### 3단계 — SPOT 추천 또는 하향

원격 근거 Eligibility를 모두 충족하면 특정 Spot과 판매시간을 `SPOT`으로 추천한다.
Spot 근거가 부족하고 Area 근거만 충분하면 `AREA`와 `fallback_reason`으로
하향한다. Area 근거도 부족하면 추천하지 않는다. 어떤 결과도 판매 허용이나 운영
적합성을 확정하지 않는다.

## 10. 원격 평가 결과 항목

초기 파일럿 정책값은 다음과 같다.

```text
area_selection_mode=USER_CHOICE
area_auto_recommendation=false
spot_selection_mode=USER_CHOICE
spot_auto_recommendation=false
machine_learning_used_for_recommendation=false
official_recommendation_allowed=false
data_status=PROTOTYPE
input_method=PM_MANUAL
```

서울시 공식 값은 Area 정보로만 표시하고 `PM_MANUAL` Spot 프로토타입 값과
분리한다. 이 사용자 선택 흐름은 Recommendation Output이 아니다.

다음은 장기 D-020 원격 SPOT 평가값이다.

평가 결과에는 Area, Spot 정체성과 출처, 직접·대리 근거 구분, 비교기준, 자료
기준시각·최신성, 반복성, 순위 변동성, 확인되지 않은 항목과 사용제한을 기록한다.

```text
verification_mode=REMOTE_EVIDENCE_ONLY
recommendation_type=SPOT
recommendation_basis=REMOTE_EVIDENCE
field_verification_status=UNAVAILABLE
operational_suitability_status=NOT_VERIFIED
confidence_level=HIGH | MEDIUM | LOW
```

이는 정책 계약이며 이번 Issue에서 생산 스키마를 구현하지 않는다.

Spot 자체의 직접 예측값이 없으면 Spot Forecast 값은 `null`로 두고 Area 예측과
구분한다. 다만 후보를 실제로 구분하는 승인된 대리근거가 §8을 충족하면
`prediction_scope=AREA`인 SPOT 추천은 가능하다. 필드 형식은 기존 Recommendation
Output Contract를 따른다.

## 11. 지도 UI 구조

- 지도에 Area 범위와 Spot 핀을 서로 다른 형태로 표시한다.
- 초기 파일럿은 사용자가 선택한 Area의 공식 정보와 대표 Spot 3개를 같은 수준의
  사용자 선택지로 표시한다. 추천·1위·기본선택 표시는 하지 않는다.
- 사용자가 고른 Spot은 사용자 선택임을 표시하며 시스템 추천으로 바꾸지 않는다.
- 승인된 Area 선택과 Spot 선택의 상세 UI는
  `AREA_FIRST_WEB_PILOT_CONTRACT.md`를 따른다.

다음 지도 상태·상세·분석 이동 항목은 D-020 장기 후속 후보이며 D-022 초기
파일럿 계약이나 구현 완료상태가 아니다.

- Spot 핀은 원격 데이터 기반 SPOT 추천, 판매 후보, 정보 없음, 원격 근거 확인 중,
  추천 제외를 구분한다.
- Spot 클릭 시 팝업 또는 모바일 하단 상세창에서 Area 정보, Spot 정보, 추천 근거,
  정보 출처, 확인상태와 사용 제한을 분리해 보여준다.
- 분석 메뉴로 이동할 수 있어야 하며 지도 복귀 시 선택한 Area·Spot·시간을 유지한다.
- Area 숫자와 Spot 숫자는 제목·단위·근거를 분리해 같은 값으로 오인하지 않게 한다.

## 12. 시간 표시 정책

초기 Area 정보의 Forecast Source는 서울시 공식 예측자료다. 기존 머신러닝
비교실험은 보존하지만 `machine_learning_used_for_recommendation=false`를
적용한다. 사용자 화면은 현재·1시간 후·3시간 후를 표시하고 내부
`horizon_minutes=60`·`180`을 유지한다. 기준시각·대상시각·최신성과
미제공 처리의 상세 계약은 `AREA_FIRST_WEB_PILOT_CONTRACT.md`를 따른다.

## 13. 자료 부족 시 대체안

D-022 초기 사용자 Area·Spot 선택은 Recommendation Output이나 fallback이 아니다.
D-021 내부 다중 Area 비교의 `AREA` 결과도 SPOT 추천 실패에 따른 fallback이
아니다. 대표 Spot 3개는 사용자 선택지이며 SPOT Eligibility를 통과했다고 보지
않는다. 다음 하향규칙은 D-020 장기 추천에만 적용한다.

1. Spot 원격 근거 Eligibility를 충족하면 `SPOT`과 판매시간을 추천한다.
2. Spot 근거가 부족하고 신뢰 가능한 Area 근거만 있으면 `AREA` 안내와
   `fallback_reason`을 제공한다.
3. Area 근거도 부족·노후·충돌 상태면 Recommendation Output을 생성하지 않고 자료
   상태만 알린다.

대체 Spot은 그 Spot 자체가 §8 Eligibility를 통과한 경우에만 제시한다.

## 14. 안전·접근·판매제한

공개자료에서 시설 운영·통행·점유 제한을 확인할 수 있을 때만 기록한다. 원격자료로
확인되지 않은 보행·카트 접근, 안전한 정차공간, 판매 허용과 실제 판매 가능시간은
`NOT_VERIFIED`로 유지한다. 자료 부재를 허용으로 추정하지 않는다.

## 15. 원격 검증과 현장 경계

현재 PoC에서는 실제 현장검증을 수행할 수 없고 현장검증 완료 상태로 전환하지
않는다. 공식 위치·시설정보, 다중 데이터 일치성, 반복성·Backtesting과 민감도
분석으로 원격 준비도를 평가한다. §8을 충족하면
`field_verification_status=UNAVAILABLE`,
`operational_suitability_status=NOT_VERIFIED` 상태에서도 원격 SPOT 추천이
가능하다. 향후 실제 운영기관이 별도 현장검증을 수행할 때만 운영 적합성 확인단계를
추가할 수 있다. 역 중심 대리좌표를 출구 또는 판매 위치로 자동 승격하지 않는다.

## 16. 향후 판매량·상품·매출 확장

장기 목표는 검증된 Spot·시간에 적합한 상품을 안내하는 것이다. 실제 판매량,
상품별 수요, 매출과 구매전환 자료가 별도 계약으로 확보되고 PM이 승인한 뒤에만
상품·판매성과 추천을 검토한다. 현재 Area·Spot 자료로 이를 추정하지 않는다.

## 17. 현재 제외범위

- UI 코드·지도 API·Backend·Database 구현
- Spot 추천 실행·사용자 게시·공식 Recommendation 활성화
- 초기 파일럿의 Spot 동적근거·S-DoT 신규 수집·Spot별 혼잡 예측·자동추천
- Spot 반복성·Backtesting·순위 안정성과 추천 신뢰도 임계값
- Spot 밀집도·판매시간·대체 Spot 숫자의 임의 생성
- 머신러닝·EG-8D·서울시 API·Apps Script 실행 또는 변경
- 현장검증·운영 적합성 완료 처리
- 판매량·매출·구매전환·상품 추천
- 상용 앱·웹 배포

## 18. 다음 PM 승인사항

정적 Master와 D-021 Core·Service, D-022 계약은 `main`에 있다. 이 문서 정합화는
Area-first Service·API, Vue UI, FastAPI, NAVER Map, Spot Prototype Runtime,
추천 실행 또는 배포를 승인하지 않는다. 해당 구현에는 Architecture ADR과 별도
PM 승인이 필요하다.

## 관련 정본

- `docs/product/EG6_AREA_SPOT_PANEL.md`
- `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md`
- `data/reference/eg6_area_panel.csv`
- `data/reference/eg6_spot_master.csv`
- `data/reference/pilot_spot_options.csv`
- `data/reference/eg6_sdot_links.csv`
- `docs/product/FreshManager_PRD_v1.0.md`
- `docs/engineering/FreshManager_TRD_v1.0.md`
- `docs/data/ML_READY_DATASET_SPEC.md`
- `docs/product/AREA_SPOT_REMOTE_EVIDENCE_READINESS_ASSESSMENT.md`
