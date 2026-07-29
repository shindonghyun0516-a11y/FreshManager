# 초기 파일럿 Area 5개 선정안과 Spot 선택 지원

- 상태: `PM_REVIEW_PROPOSAL`
- 기준일: 2026-07-29
- 관련 Issue: #128
- 상위 Issue: #99
- 선행 결정: D-018, D-020, D-021

## 1. 목적

승인된 13개 Area의 기존 조사결과와 Area 데이터를 이용해 초기 서비스에 사용할
Area 5개를 제안하고, 각 Area에 사용자가 직접 고를 대표 Spot 3개를 구성할 수
있는지 확인한다. 이 문서는 5개 Area를 공식 확정하거나 Spot을 등록하지 않는다.
실제 추천 계산, UI·Backend 구현, 배포와 파일럿 실행도 수행하지 않는다.

## 2. 초기 파일럿 A안 범위

초기 파일럿은 서울시 공식 현재·예측 유동인구로 Area와 판매시간을 추천하고,
해당 Area의 대표 Spot 3개를 같은 수준의 선택지로 보여준다.

```text
서울시 공식 현재·예측 유동인구
→ 파일럿 Area 5개와 판매시간을 AREA 단위로 추천
→ Area별 대표 Spot 3개 표시
→ 사용자가 이동할 Spot 직접 선택
```

Spot은 시스템 추천대상이 아니다. Spot별 유동인구·밀집도 비교, 자동 Spot 추천,
동적 근거 Pilot과 반복성·Backtesting은 초기 파일럿 이후로 보류한다. D-020의
원격 SPOT 자동추천은 장기 제품 목표로 그대로 유지한다.

## 3. 초기 파일럿 Area 선정기준

기존 13개 Area 조사결과에 다음 10개 기준을 같은 순서로 적용했다.

1. 기존 서울시 Area 데이터 존재
2. 현재·예측 유동인구 데이터 완전성
3. 판매시간을 설명할 수 있는 예측값
4. 오피스·점심·출퇴근 유동판매 시나리오 적합성
5. 대표 Spot 명칭 3개 이상 구성 가능성
6. 지도에서 Spot을 구분해 표시할 가능성
7. 사용자에게 Area와 Spot을 설명하기 쉬운 정도
8. 구현 난이도
9. 공개 운영 제한정보
10. 자료 최신성

`SPOT_DISCRIMINATING` 동적 근거, 후보별 동일시각 유동인구, 반복 시계열, Spot
순위 안정성, Backtesting과 자동 SPOT Recommendation Eligibility는 초기 Area
선정의 Hard Filter가 아니다. 확보되지 않았다는 사실과 위험은 그대로 기록한다.

13개 Area는 모두 기준 1~3의 Area 데이터·완전 회차·60분·180분 Forecast 조건을
충족해 동률이다. 5개 제안은 기준 4~10의 시나리오 적합성, 후보 구성·설명 가능성,
구현 난이도, 운영 제한정보와 최신성으로 구분했다.

공통 역세권·출입구 자료는 데이터셋의 존재와 필드만 확인했다. 파일을 내려받지
않아 13개 Area의 개별 행은 `NOT_CONFIRMED`다. Area별 공식 페이지에서 확인한
명칭만 후보 구성 가능성에 사용했다.

## 4. Evidence Readiness 기준

Evidence Readiness는 공식 후보정보, 위치근거, Spot 구분 동적자료, 동일시각 비교,
반복 시계열, 최신성과 재현 가능성을 본다. `LOW`, `LOW-MEDIUM`, `MEDIUM`은 이번
최소 조사에서 확인된 상대적 준비상태이며 성능점수나 추천 신뢰도가 아니다.

## 5. Business Scenario Fit 기준

Business Scenario Fit은 오피스·유동판매 대표성, 점심·출퇴근 시간 적합성, 후보
다양성, 이동 가능성, 한 Area로의 범위 통제, 사용자 설명 용이성과 운영 위험을
본다. Evidence Readiness와 합산하지 않는다.

## 6. 동적 근거 분류

| 분류 | 의미 |
|---|---|
| `SPOT_DISCRIMINATING` | 같은 Area의 후보 Spot을 서로 구분할 수 있음 |
| `AREA_OR_STATION_ONLY` | Area 또는 역 수준만 구분 가능 |
| `NOT_CONFIRMED` | 확보경로가 확인되지 않음 |
| `UNAVAILABLE` | 사용할 수 있는 경로가 없음 |

현재 13개 Area는 모두 `AREA_OR_STATION_ONLY`다. Area Observation, 역별 승하차와
역 중심 Anchor 인근 S-DoT는 반복자료 후보이지만 실제 Spot 3~5개를 서로 구분하지
못한다. S-DoT가 가깝다는 이유만으로 `SPOT_DISCRIMINATING`으로 올리지 않는다.
이 한계는 초기 Area 선정 실패사유는 아니지만 Spot별 수치·순위·추천 표현을
금지하는 경계다.

## 7. 13개 Area 비교표

`후보 구성 가능성`은 공식 명칭을 이용한 사용자 선택지 후보이며 등록·좌표 확정·판매
허용을 뜻하지 않는다. `공통행 미확인`은 공통 공식자료의 개별 행을 내려받아
검증하지 않았다는 뜻이지 행이 없다는 뜻이 아니다.

| Area | 공식 위치·공통행 | 후보 구성 가능성 | 후보별 좌표·구분 | 동적 근거·동일시각·반복 | 운영 제한 | Evidence Readiness | Business Fit | 최신성·난이도 | 초기 파일럿 제안 |
|---|---|---|---|---|---|---|---|---|---|
| `POI019` 구로디지털단지역 | 구로구 공식 출구·깔깔거리 자료; 공통행 미확인 | 1·2·3·6번 출구 4곳 | 좌표 `NOT_CONFIRMED`; 명칭만 구분 | `AREA_OR_STATION_ONLY`; 후보별 근거·반복 `NOT_READY` | 출구 6 통행·정비 이슈; 판매 허용 `NOT_VERIFIED` | LOW | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | 미선정 |
| `POI013` 가산디지털단지역 | 금천구 공식 출구·시설 자료; 공통행 미확인 | 2·4·5·7·11번 출구 5곳 | 좌표 `NOT_CONFIRMED`; 명칭만 구분 | `AREA_OR_STATION_ONLY`; 후보별 근거·반복 `NOT_READY` | 환승·출구 변경 이력; 판매 허용 `NOT_VERIFIED` | LOW | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | 미선정 |
| `POI014` 강남역 | 강남구 공식 위치자료; 공통행 미확인 | 4번 출구 횡단보도·강남스퀘어·CGV강남 앞·점프밀라노 앞·국기원입구 5곳 | 주소 일부만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 120.5m Anchor S-DoT도 후보 구분 `NOT_READY` | 도로점용 절차 있음; 판매 허용 `NOT_VERIFIED` | MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM-HIGH | **선정 제안** |
| `POI072` 여의도 | 서울시 공원 구역자료; 공통행 미확인 | 문화의마당·잔디마당·자연생태숲·전통의숲 4곳 | 구역명만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 후보별 근거·반복 `NOT_READY` | 장소사용 승인·행사 충돌 가능 | MEDIUM 정적·LOW 동적 | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM-HIGH | **선정 제안** |
| `POI001` 강남 MICE 관광특구 | 코엑스 공식 접근·시설자료; 공통행 미확인 | 삼성역 5·6번, 봉은사역 7번, 코엑스 동문, 무역센터 정류장 5곳 | 위치명만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 가까운 S-DoT 없음 | 사유시설·공사·점용 조건 `NOT_VERIFIED` | MEDIUM | MEDIUM-HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | 미선정 |
| `POI034` 선릉역 | 강남구 공식 위치자료; 공통행 미확인 | 출구 후보 3~5개 확보 가능성 `NOT_CONFIRMED` | 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 204.1m Anchor S-DoT도 후보 구분 불가 | 도로점용·판매 허용 `NOT_VERIFIED` | LOW-MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM | 미선정 |
| `POI042` 역삼역 | 강남구 공식 위치자료; 공통행 미확인 | 출구 후보 3~5개 확보 가능성 `NOT_CONFIRMED` | 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 가까운 S-DoT 없음 | 도로점용·판매 허용 `NOT_VERIFIED` | LOW-MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM | 미선정 |
| `POI025` 뚝섬역 | 성동구 공식 출구·시설자료; 공통행 미확인 | 4·5·6·8번 출구 4곳 | 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 56.4m Anchor S-DoT도 후보 구분 불가 | 판매 허용 `NOT_VERIFIED` | MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM | **선정 제안** |
| `POI088` 광화문광장 | 서울시 공식 광장 구역·이용자료; 공통행 미확인 | 육조마당·놀이마당·해치마당·열린마당·광장숲 5곳 | 공식 지도상 구분; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 264.8m Anchor S-DoT와 역자료는 구역 구분 불가 | 사용허가·행사 영향; 판매 허용 `NOT_VERIFIED` | MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM-HIGH | **선정 제안** |
| `POI003` 명동 관광특구 | 중구 공식 출구·관광특구 자료; 공통행 미확인 | 을지로입구역 1·4·5번 출구 3곳 | 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 173.2m Anchor S-DoT도 후보 구분 불가 | 보도·사유지 경계와 판매 허용 `NOT_VERIFIED` | LOW-MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | 미선정 |
| `POI119` 잠실역 | 서울시 공식 출구군·시설자료; 공통행 미확인 | 1·2, 3·4, 10·11번 출구군 3곳 | 출구군만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 273.6m Anchor S-DoT도 후보 구분 불가 | 대형 사유시설·공공영역 경계 `NOT_VERIFIED` | LOW-MEDIUM | MEDIUM-HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | 미선정 |
| `POI033` 서울역 | 서울시 공식 광장·보행로 자료; 공통행 미확인 | 서울역광장·만리동광장·퇴계로 교통섬·서울로7017 4곳 | 장소명만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 후보별 근거·반복 `NOT_READY` | 다기관·다층 공간과 점용 제약 | MEDIUM 정적·LOW 동적 | MEDIUM-HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; VERY HIGH | 미선정 |
| `POI032` 서울식물원·마곡나루역 | 서울식물원 공식 안내도·2026-07 운영페이지; 공통행 미확인 | 열린숲 1번 입구·주제원 7번 입구·식물문화센터·호수원·방문자센터 5곳 | 공식 지도상 구분; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 122.3m Anchor S-DoT는 후보 구분 전 재검증 필요 | 공원 운영·행사·판매 허용 `NOT_VERIFIED` | MEDIUM | MEDIUM-HIGH | 2026-07 운영·S-DoT 갱신 확인, 안내도 발행일 `NOT_CONFIRMED`; MEDIUM-HIGH | **선정 제안** |

합산점수는 만들지 않았다. 13개 모두 현재 원격 SPOT 추천 Eligibility는 미충족이며
실제 Spot과 후보별 동적자료는 0건이다. 선정 제안 5개도 `AREA` 추천과 사용자
Spot 선택 지원을 위한 PM 검토안일 뿐, SPOT 추천·운영 적합성·판매 허용 판정이 아니다.

## 8. 초기 파일럿 Area 5개와 Spot 후보 15개

| Area | 선정 이유 | Area 판매 시나리오 | 대표 Spot 후보 3개 |
|---|---|---|---|
| `POI032` 서울식물원·마곡나루역 | 공식 구역명이 명확하고 업무·공원 복합 Area를 설명하기 쉬움 | 평일 점심·퇴근과 공원 방문시간의 Area 기회 확인 | 열린숲 1번 입구, 식물문화센터, 호수원 |
| `POI088` 광화문광장 | 공식 광장 구역과 이용절차가 명확함 | 도심 업무 점심·퇴근과 행사 영향이 있는 Area 기회 확인 | 육조마당, 해치마당, 광장숲 |
| `POI014` 강남역 | 오피스·상업·출퇴근 대표성이 높고 공식 후보명이 충분함 | 점심·퇴근·저녁 시간의 대규모 Area 기회 확인 | 강남스퀘어, CGV강남 앞, 점프밀라노 앞 |
| `POI025` 뚝섬역 | 업무·창업·상업 혼합권이며 출구 구분이 쉬움 | 점심·퇴근과 상업시간의 혼합 Area 기회 확인 | 뚝섬역 4번 출구, 6번 출구, 8번 출구 |
| `POI072` 여의도 | Area 데이터 이력과 오피스·점심 시나리오가 강하며 공원 구역명이 명확함 | 금융·오피스 점심·퇴근과 공원 유동의 Area 기회 확인 | 문화의마당, 잔디마당, 자연생태숲 |

Pilot Area는 정확히 5개, 후보는 Area당 정확히 3개로 총 15개다. 후보명은 화면
설명용 조사후보이며 실제 Spot 등록, 검증좌표, 판매 허용 또는 추천순위를 뜻하지 않는다.

## 9. 5개 Area 상세 판정

다섯 Area 모두 잠긴 13개 Area 데이터의 완전 회차와 서울시 공식 60분·180분
Forecast를 사용할 수 있다. 실제 서비스에서는 실행시점의 최신성 Gate를 별도로
통과해야 하며, 이번 문서가 추천 결과를 생성하지는 않는다.

### `POI032` 서울식물원·마곡나루역

- 좌표: 세 후보 모두 `NOT_CONFIRMED`; 역 중심 Anchor 좌표를 복사하지 않는다.
- 운영 제한: 공원 운영·행사·판매·점유 허용은 `NOT_VERIFIED`다.
- 구현 난이도: `MEDIUM-HIGH`; 공식 지도 구역은 분명하지만 후보 좌표 확인이 남았다.
- 사용자 설명: 업무권·역·공원과 세 후보 위치를 지도에서 구분해 설명하기 쉽다.
- 한계: Spot별 직접 유동인구·밀집도·순위 근거는 없다.

### `POI088` 광화문광장

- 좌표: 공식 지도에서 구역은 구분되나 세 후보 좌표는 `NOT_CONFIRMED`다.
- 운영 제한: 사용허가·행사 영향과 판매 허용은 `NOT_VERIFIED`다.
- 구현 난이도: `MEDIUM-HIGH`; 공식 구역은 분명하지만 행사 변동을 함께 표시해야 한다.
- 사용자 설명: 광장 구역 3개를 같은 수준의 선택지로 설명하기 쉽다.
- 한계: Area·역·Anchor 자료는 광장 구역별 유동을 구분하지 못한다.

### `POI014` 강남역

- 좌표: 일부 주소만 확인됐고 세 후보 좌표는 `NOT_CONFIRMED`다.
- 운영 제한: 도로점용 절차가 있으며 실제 판매 허용은 `NOT_VERIFIED`다.
- 구현 난이도: `MEDIUM-HIGH`; 후보별 위치와 도로 경계를 다시 확인해야 한다.
- 사용자 설명: 알려진 시설명으로 세 선택지를 구분하기 쉽다.
- 한계: 120.5m Anchor S-DoT도 세 후보를 구분하지 못한다.

### `POI025` 뚝섬역

- 좌표: 세 출구의 검증좌표는 `NOT_CONFIRMED`다.
- 운영 제한: 출구별 판매·점유 허용은 `NOT_VERIFIED`다.
- 구현 난이도: `MEDIUM`; 출구 명칭은 단순하지만 운영정보 확인이 남았다.
- 사용자 설명: 번호가 다른 출구 3개를 지도에서 구분하기 쉽다.
- 한계: 56.4m Anchor S-DoT도 출구별 직접값이나 순위를 제공하지 않는다.

### `POI072` 여의도

- 좌표: 공식 공원 구역명만 확인했고 세 후보 좌표는 `NOT_CONFIRMED`다.
- 운영 제한: 장소사용 승인·행사 충돌과 판매 허용은 `NOT_VERIFIED`다.
- 구현 난이도: `MEDIUM-HIGH`; 넓은 공원 구역과 운영조건을 함께 표시해야 한다.
- 사용자 설명: 오피스 Area와 공원 구역의 관계를 설명하기 쉽다.
- 한계: Area Forecast를 세 공원 구역의 직접 유동인구로 표현할 수 없다.

## 10. Spot 역할과 화면 표현

```text
spot_role=USER_SELECTABLE_OPTION
spot_count_per_area=3
spot_auto_recommendation=false
```

허용 문구:

> 강남역 Area는 12시 30분부터 13시 30분 사이 유동인구가 높아질 것으로
> 예상됩니다. 판매 후보 Spot은 강남스퀘어, CGV강남 앞, 점프밀라노 앞입니다.
> 이동할 Spot을 선택해 주세요.

금지 문구:

> 강남스퀘어의 밀집도가 가장 높습니다. 강남스퀘어에서 판매할 것을 추천합니다.

Area 예측값을 후보 Spot의 직접값으로 표현하거나 세 후보에 순위·기본선택을
부여하지 않는다.

## 11. Recommendation Output 범위

```text
recommendation_type=AREA
recommendation_basis=SEOUL_OFFICIAL_FORECAST
spot_selection_mode=USER_CHOICE
spot_auto_recommendation=false
machine_learning_used_for_recommendation=false
```

시스템은 Area·판매시간만 추천한다. Spot 후보 3개는 추천된 `spot_id`가 아니라
사용자 선택지다. 사용자가 고른 값은 향후 `user_selected_spot_id` 또는 기존
명명규칙에 맞는 동등 필드 후보로 기록할 수 있으나, 이번 Issue에서 생산 Schema를
구현하지 않는다.

## 12. 머신러닝과 보류 작업

```text
machine_learning_status=COMPARISON_COMPLETED_NOT_ADOPTED
machine_learning_used_for_recommendation=false
recommendation_forecast_source=SEOUL_OFFICIAL_FORECAST
```

기존 머신러닝 산출물과 비교실험 기록은 보존한다. 추천에는 사용하지 않는다.
다음은 `DEFERRED_AFTER_INITIAL_PILOT`이다.

- Spot 동적 유동인구 수집과 S-DoT 신규 수집·연결
- Spot별 혼잡 예측과 자동 Spot 추천
- Spot 반복성·Backtesting과 순위 안정성
- 추천 신뢰도 임계값

## 13. 주요 데이터 공백과 위험

- 공통 역세권·출입구 자료의 13개 개별 행
- 후보별 공식 또는 검증 가능한 좌표와 측정범위
- 후보별 동일시각 동적 관측과 반복 시계열
- S-DoT 방문자수와 실제 후보의 공간 대응
- 정류소 자료를 Spot 대리근거로 인정할 조건
- 자료 결측·최신성·이상치 기준
- 이동판매, 점유, 안전, 카트 정차와 시설별 운영 허용
- Area·역 자료를 Spot 값으로 잘못 표시할 위험
- 단일 Anchor S-DoT를 여러 후보의 직접근거로 과대해석할 위험
- 행사·계절·날씨를 지속적인 판매기회로 오인할 위험
- 공원·광장의 이용허가를 판매 허용으로 오인할 위험
- 후보별 근거 없이 기본 Spot이나 순위를 계산할 위험
- 현장검증 불가 상태를 운영 적합성 확인으로 잘못 표시할 위험

이 문서는 생산 Schema, 추천 로직, UI, Backend, Scheduler, 배포 또는 사용자 게시를
승인하지 않는다.

## 14. 장기 목표와 초기 파일럿 경계

D-020의 원격 SPOT 자동추천은 장기 제품 목표로 유지한다. 초기 파일럿은 이를
완료조건으로 사용하지 않는다. Spot 동적근거, 반복성·Backtesting, 자동추천과
신뢰도 기준은 파일럿 결과와 별도 PM 승인 뒤 다시 검토한다.

## 15. PM 결정사항

PM은 다음 한 가지만 결정한다.

> 제안한 5개 Area와 Area당 대표 Spot 후보 3개를 초기 파일럿 범위로 확정할지
> 결정한다.

다음 값은 아직 열려 있으며 Issue #128에서 정하지 않는다.

- `confidence_level` 산출기준과 임계값
- 허용 결측률
- 데이터 freshness 상한
- 승인 대리근거 기준
- `fallback_reason` 최종 Enum
- 운영 적합성 미확인 경고와 사용자 확인방식

## 16. 근거 출처

이번 조사에서는 공개 페이지와 저장소 정적 참조만 읽었다. 실제 API 호출, S-DoT
수집, 파일럿 데이터 생성과 Spot 등록은 하지 않았다.

### 공통 공식자료

- [서울교통공사 역별 역세권 현황](https://www.data.go.kr/data/15044230/fileData.do)
- [서울교통공사 외부 출입구 캐노피 현황](https://www.data.go.kr/data/15082999/fileData.do)
- [서울교통공사 역 주소·좌표 정보](https://data.seoul.go.kr/dataList/OA-21232/S/1/datasetView.do)
- [서울시 역별 시간대별 승하차 정보](https://data.seoul.go.kr/dataList/OA-12921/S/1/datasetView.do)
- [서울시 교통카드이용정보](https://data.seoul.go.kr/dataList/7/literacyView.do)
- [서울시 버스정류소 위치정보](https://data.seoul.go.kr/dataList/OA-15067/S/1/datasetView.do?tab=A)
- [서울시 버스 정류장별 시간대별 승하차 정보](https://data.seoul.go.kr/dataList/OA-12913/A/1/datasetView.do)
- [서울시 S-DoT 유동인구 측정정보](https://data.seoul.go.kr/dataList/OA-15964/S/1/datasetView.do?tab=A)

### Area별 공식자료

- [구로디지털단지·깔깔거리](https://www.guro.go.kr/www/contents.do?key=2992)
- [구로디지털단지역 6번 출구 주변 정비 제안](https://www.guro.go.kr/www/partcptnBudgetStep02.do?bsnsCtgry=&bsnsDong=&bsnsNo=1165&bsnsSe=&key=3437&pageIndex=53&pageUnit=6&rep=1&searchCnd=all&searchCommpleteType=&searchKrwd=&sort=)
- [가산디지털단지역 자전거 편의시설](https://www.geumcheon.go.kr/portal/contents.do?key=860)
- [가산디지털단지역 인근 공식 시설 접근정보](https://www.geumcheon.go.kr/portal/contents.do?key=645)
- [강남구 그늘막 위치정보](https://www.gangnam.go.kr/contents/Shade/1/view.do?mid=ID06_041617)
- [강남구 도로점용 허가 안내](https://www.gangnam.go.kr/contents/permit_road/1/view.do?mid=ID03_010906)
- [서울시 여의도공원 안내](https://parks.seoul.go.kr/template/sub/yeouido.do)
- [강남 MICE·코엑스 접근정보](https://visitgangnam.net/about/mice)
- [코엑스 공식 오시는 길](https://www.coex.co.kr/guide/directions/)
- [강남구 테헤란로 업무지구](https://www.gangnam.go.kr/board/B_000031/1074999/view.do?mid=ID01_0313)
- [성동구 뚝섬역·서울숲 접근정보](https://sd.go.kr/main/contents.do?key=1463)
- [성동구 뚝섬역 출구·주요시설 안내](https://www.sd.go.kr/seongsu1ga1/contents.do?key=2780)
- [광화문광장 공간 안내](https://gwanghwamun.seoul.go.kr/ghm/cardNews/ghm/space.do?mid=1039)
- [광화문광장 사용신청 안내](https://gwanghwamun.seoul.go.kr/ghm/bbsPost/62/4890/detail.do?mid=1020)
- [광화문광장 행사·운영 안내](https://gwanghwamun.seoul.go.kr/ghm/main.do)
- [중구 명동 관광특구 안내](https://www.junggu.seoul.kr/tour/content.do?cmsid=14910)
- [중구 을지로입구역 출구 접근정보](https://www.junggu.seoul.kr/minwon/content.do?cmsid=13984)
- [서울시 잠실역 시설 접근정보](https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id=S230516103739372326)
- [서울시 잠실역 출구군 안내](https://english.visitseoul.net/attractions/LuggageStorage25/ENPpwo7rk)
- [서울시 서울로7017 안내](https://parks.seoul.go.kr/parks/detailView.do?pIdx=1382&tr_code=sweb)
- [서울시 만리동광장 안내](https://mediahub.seoul.go.kr/archives/1063221)
- [서울역광장·만리동광장·퇴계로 연결지점](https://news.seoul.go.kr/citybuild/archives/234051)
- [서울식물원 2026-07 운영·접근 안내](https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id=S260623135805041300)
- [서울식물원 현행 시설 구역 안내](https://botanicpark.seoul.go.kr/front/plants/plantDataList.do?sCategory=G)
- [서울식물원 종합안내도](https://botanicpark.seoul.go.kr/front/img/%EC%84%9C%EC%9A%B8%EC%8B%9D%EB%AC%BC%EC%9B%90%20%EC%A2%85%ED%95%A9%EC%95%88%EB%82%B4%EB%8F%84.pdf)

### 저장소 정본

- `data/reference/seoul_121_places.csv`
- `data/reference/eg6_area_panel.csv`
- `data/reference/eg6_spot_master.csv`
- `data/reference/eg6_sdot_links.csv`
- `docs/product/AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md`
- `docs/product/RECOMMENDATION_OUTPUT_CONTRACT.md`
