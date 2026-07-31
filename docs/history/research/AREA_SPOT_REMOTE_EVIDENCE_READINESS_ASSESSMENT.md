# Area·Spot 원격 근거 준비도 평가

> **Historical Document · 현행 정본 아님**
>
> Issue #126 당시 조사 결과를 보존한 문서다. 현행 제품·추천 계약의 정본으로
> 사용하지 않는다.

- 상태: `COMPLETED`
- 기준일: 2026-07-29
- 관련 Issue: #126
- 상위 Issue: #99
- 적용 결정: D-019, D-020

## 1. 목적

현장검증을 할 수 없는 FreshManager PoC에서 승인된 13개 Area가 복수 Spot 후보의
원격 비교를 시작할 준비가 어느 정도인지 1차로 평가한다. 이 점수는 원격 근거를
발견·확인한 준비도이며 판매 적합성, 추천 성능이나 최종 사업 우선순위가 아니다.
실제 Spot 등록, 좌표 생성, 데이터 수집과 추천 실행도 아니다.

D-020 이후 이 문서의 점수·Matrix·Shortlist는 Issue #126 당시 준비도 조사 결과로
보존한다. 여기의 `데이터 기반 우선 후보`는 현행 제품 출력 상한이 아니며, 이
평가만으로 D-020의 SPOT Eligibility를 충족하거나 추천을 승인하지 않는다. 이
문서는 정책 정합화가 main에 반영된 뒤 시작할 Issue #128 공정성 조사의 입력이다.

## 2. 현장검증 불가 전제

Issue #126 조사 당시 최대 분류는 **데이터 기반 우선 Spot 후보**였다. D-020은 이
분류를 현행 제품 출력 상한으로 둔 부분을 대체했으며, 아래 값은 당시 평가의
이력으로 보존한다.

```text
verification_mode=REMOTE_EVIDENCE_ONLY
field_verification_status=UNAVAILABLE
operational_suitability_status=NOT_VERIFIED
recommendation_scope=DATA_PRIORITY_ONLY
```

## 3. 정책 변경사항

현장관측 대신 공식 위치·시설정보, 선택적 S-DoT 또는 대체 동적 근거, 다중 자료의
일치성, 반복 시간패턴, Backtesting과 민감도 분석을 사용한다. 근거가 부족하면
`데이터 기반 우선 후보`로 올리지 않고 `판매 후보` 또는 `AREA` 안내로 하향한다.
`field_verified=true`는 현재 PoC의 달성조건으로 사용하지 않는다.

## 4. 원격 검증 정의

- 위치 정체성: 공식 명칭·주소·좌표·출입구 또는 시설 식별정보와 확인일
- 동적 직접근거: 후보 위치·측정범위가 정합한 센서의 시간대 관측값
- 동적 대리근거: 인근 S-DoT, 역별 승하차 등 승인된 대리자료와 거리·한계
- Area 맥락근거: Area Observation·Forecast·반복 피크·Area 순위
- 원격 운영근거: 공개된 시설 운영·통행·점유 제한

Area와 역 단위 자료를 특정 Spot의 직접값으로 바꾸지 않는다. 자료가 없거나 실제
행·좌표·측정범위를 확인하지 않은 항목은 `NOT_CONFIRMED`로 기록한다.

## 5. 평가기준

현재 확인된 **자료 준비도**를 100점 만점으로 보수적으로 기록한다.

| 항목 | 배점 | 이번 평가의 인정 범위 |
|---|---:|---|
| 실제 후보 구성·위치근거 | 25 | 공식 후보 행과 좌표가 없으므로, 공식 시설·출입구 자료의 존재만 일부 인정 |
| 동적 근거 확보 가능성 | 25 | S-DoT 정적 연결과 Area·역 단위 대리자료의 존재만 일부 인정 |
| Area 내부 비교·반복성 | 20 | 복수 Spot 자료가 없어 반복자료의 향후 이용 가능성만 일부 인정 |
| Backtesting·재현성 | 15 | Spot 후보·관측 시계열이 없어 0점 |
| 자료 최신성·품질 | 10 | 갱신주기가 공개된 출처의 존재만 일부 인정; 실제 행 최신성은 미확인 |
| 제한·불확실성 관리 | 5 | 직접값과 대리값, 미확인 운영 적합성을 명시한 경우 인정 |

점수는 객관적 성능값이나 판매 적합성 점수가 아니다. Area별 공식 자료 확인 깊이가
같지 않으므로 현재 점수만으로 최종 우선 Area를 고를 수 없다. 공식 자료의 특정
Area 행을 확인하지 않은 상태에서 후보 수·좌표·동적값을 추정하지 않았다.

## 6. 13개 Area 준비도 Matrix

공통사항: 현재 Anchor는 모두 `STATION_CENTER_PROXY`, 확인된 실제 후보 Spot은 0개,
동적 직접근거와 Spot Backtesting은 `NOT_CONFIRMED`, 운영 적합성은
`NOT_VERIFIED`다. S-DoT 등급은 기존 Anchor 기준 정적 연결이며 Spot 직접관측이 아니다.

`자료 확인수준`은 다음 세 값으로 구분한다. `AREA_SPECIFIC_CONFIRMED`는 Area별
공식 자료 내용을 확인한 상태, `COMMON_SOURCE_ROW_CONFIRMED`는 공통 공식자료의
해당 Area 행을 확인한 상태, `COMMON_SOURCE_ROW_NOT_CONFIRMED`는 공통 출처의 존재만
확인하고 해당 행은 이번 조사에서 확인하지 않은 상태다. 마지막 값은 자료나 행이
없다는 뜻이 아니다.

| Area ID·이름 | 현재 Anchor | 실제 후보 구성 가능성·공식 위치근거 | 자료 확인수준 | 비교 후보 수 | S-DoT | 직접·대리 동적근거 | 반복·Backtesting | 원격 운영근거 | 주요 공백 | 준비도 | 증거수준 | 판단 |
|---|---|---|---|---:|---|---|---|---|---|---:|---|---|
| `POI019` 구로디지털단지역 | `SPOT-EG6-001` 역 중심 | LOW; 공통 역세권 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 미지원 | 직접 `NOT_CONFIRMED`; 역·Area 대리 가능성만 있음 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 후보 좌표·복수비교·동적값 | 18/100 | LOW | 보류 |
| `POI013` 가산디지털단지역 | `SPOT-EG6-002` 역 중심 | LOW; 공통 역세권 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 미지원 | 직접 `NOT_CONFIRMED`; 역·Area 대리 가능성만 있음 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 후보 좌표·복수비교·동적값 | 18/100 | LOW | 보류 |
| `POI014` 강남역 | `SPOT-EG6-003` 역 중심 | LOW; 공통 출입구 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 직접 후보 | 직접 `NOT_CONFIRMED`; 정적 S-DoT·역·Area 대리 가능 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 실제 후보와 센서 측정범위 | 22/100 | LOW | 예비후보 |
| `POI072` 여의도 | `SPOT-EG6-004` 역 중심 | LOW; 공통 역세권 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 미지원 | 직접 `NOT_CONFIRMED`; 역·Area 대리 가능성만 있음 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 후보 좌표·복수비교·동적값 | 18/100 | LOW | 보류 |
| `POI001` 강남 MICE 관광특구 | `SPOT-EG6-005` 삼성역 중심 | MEDIUM; 코엑스 공식 진입로·시설구역 출처 있음, 후보 미등록 | `AREA_SPECIFIC_CONFIRMED` | 0 | 미지원 | 직접 `NOT_CONFIRMED`; 역·Area 대리 가능성만 있음 | Spot 반복·Backtesting `NOT_READY` | 공식 진입·시설정보 있음, 판매 허용 `NOT_CONFIRMED` | 후보 좌표·동적 비교·점유 제한 | 25/100 | MEDIUM | 동일기준 추가확인 대상 Shortlist |
| `POI034` 선릉역 | `SPOT-EG6-006` 역 중심 | LOW; 공통 출입구 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 인근 | 직접 `NOT_CONFIRMED`; 인근 S-DoT·역·Area 대리 가능 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 실제 후보와 센서 측정범위 | 20/100 | LOW | 보류 |
| `POI042` 역삼역 | `SPOT-EG6-007` 역 중심 | LOW; 공통 출입구 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 미지원 | 직접 `NOT_CONFIRMED`; 역·Area 대리 가능성만 있음 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 후보 좌표·복수비교·동적값 | 18/100 | LOW | 보류 |
| `POI025` 뚝섬역 | `SPOT-EG6-008` 역 중심 | LOW; 공통 출입구 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 직접 후보 | 직접 `NOT_CONFIRMED`; 정적 S-DoT·역·Area 대리 가능 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 실제 후보와 센서 측정범위 | 22/100 | LOW | 예비후보 |
| `POI088` 광화문광장 | `SPOT-EG6-009` 광화문역 중심 | MEDIUM; 공식 광장 구역·진입·이용정보 출처 있음, 후보 미등록 | `AREA_SPECIFIC_CONFIRMED` | 0 | 인근 | 직접 `NOT_CONFIRMED`; 인근 S-DoT·Area 대리 가능 | Spot 반복·Backtesting `NOT_READY` | 광장 이용절차 있음, 판매 허용 `NOT_CONFIRMED` | 후보 좌표·동적 비교·행사 영향 | 27/100 | MEDIUM | 동일기준 추가확인 대상 Shortlist |
| `POI003` 명동 관광특구 | `SPOT-EG6-010` 을지로입구역 중심 | LOW; 공통 출입구 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 인근 | 직접 `NOT_CONFIRMED`; 인근 S-DoT·역·Area 대리 가능 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 실제 후보와 센서 측정범위 | 20/100 | LOW | 보류 |
| `POI119` 잠실역 | `SPOT-EG6-011` 역 중심 | LOW; 공통 출입구 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 인근 | 직접 `NOT_CONFIRMED`; 인근 S-DoT·역·Area 대리 가능 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 실제 후보와 센서 측정범위 | 20/100 | LOW | 보류 |
| `POI033` 서울역 | `SPOT-EG6-012` 역 중심 | LOW; 공통 역세권 자료의 해당 행 미확인 | `COMMON_SOURCE_ROW_NOT_CONFIRMED` | 0 | 미지원 | 직접 `NOT_CONFIRMED`; 역·Area 대리 가능성만 있음 | Spot 반복·Backtesting `NOT_READY` | 출입구 자료 가능, 제한 `NOT_CONFIRMED` | 후보 좌표·복수비교·동적값 | 18/100 | LOW | 보류 |
| `POI032` 서울식물원·마곡나루역 | `SPOT-EG6-013` 역 중심 | MEDIUM; 공식 공원 안내도에 진입로·구역 있음, 후보 미등록 | `AREA_SPECIFIC_CONFIRMED` | 0 | 직접 후보 | 직접 `NOT_CONFIRMED`; 정적 S-DoT·역·Area 대리 가능 | Spot 반복·Backtesting `NOT_READY` | 공식 시설안내 있음, 판매 허용 `NOT_CONFIRMED` | 후보 좌표·동적 비교·운영 제한 | 29/100 | MEDIUM | 동일기준 추가확인 대상 Shortlist |

점수 구성은 일반 Area가 위치 5, 동적 4~8, 반복 2, Backtesting 0, 최신성 2,
한계관리 5점이다. 공식 시설·진입 자료가 별도로 확인된 세 Area만 위치근거를
12점으로 평가했다. S-DoT 직접 후보 8점, 인근 후보 6점, 미지원 4점은 **확보
가능성**만 반영하며 동적 직접관측으로 인정하지 않는다.

## 7. 동일기준 추가확인 대상 Shortlist

1. **서울식물원·마곡나루역(29점):** 공식 안내도와 진입구역, Anchor 기준
   `DIRECT_COVERAGE`가 있다. 실제 후보 좌표·센서 측정범위·판매 제한은 미확인이다.
2. **광화문광장(27점):** 공식 구역·이용절차 자료와 `NEARBY_SUPPORT`가 있다.
   행사·점유조건과 후보별 동적 비교는 미확인이다.
3. **강남 MICE 관광특구(25점):** 코엑스 공식 진입로·시설구역 자료로 후보 구성을
   시작할 수 있다. 현재 Anchor 기준 S-DoT는 미지원이다. 실제 후보 Spot 좌표를
   확보한 후 인접 센서 또는 센서군을 재탐색할 수 있는지는 미확인이다.

세 곳은 Area별 공식 출처가 먼저 확인돼 추가조사를 시작하기 쉬운 1차 Shortlist일
뿐이다. **최종 선정 Area**, 사업 적합성 우수 Area, 공식 추천 Area 또는 판매 적합
Area가 아니며, 다른 10개보다 실제 준비도가 높다고 결론내릴 수 없다. 13개 Area에
같은 최소 근거 확인을 적용한 뒤에만 최종 우선 Area를 제안할 수 있다. 추천 신뢰도는
자료 준비도 기준 `LOW~MEDIUM`이며 운영 적합성은 미검증이다.

## 8. 실제 Spot 후보 구성 가능성

세 Shortlist Area는 공식 명칭이 있는 진입로·광장 구역·공원 구역을 바탕으로 후보 목록을
만들 가능성이 있다. 이번 조사에서는 특정 출구나 구역을 Spot으로 등록하지 않았고
좌표도 수집·생성하지 않았다. 나머지 10개 Area도 공통 역세권·출입구 자료의 실제
행을 확인한 뒤 후보 구성 가능성을 다시 판정해야 한다.

## 9. S-DoT와 대체 동적 근거

기존 Anchor 기준 S-DoT 연결은 직접 후보 3개, 인근 4개, 미지원 6개다. 최근 활성
참조기간은 2026-07-06~12이며 신규 수집은 없었다. 대체 근거로 서울시 역별 시간대
승하차와 Area Observation을 검토할 수 있지만 둘 다 Spot 직접값이 아니다. 실제
후보 좌표·측정범위·시간 정렬을 확인하기 전에는 모든 직접근거를 `NOT_CONFIRMED`로
유지한다.

## 10. 반복성·Backtesting 계획

후속 승인 뒤 같은 기준의 후보별 시계열이 확보된 경우에만 다음을 수행한다.

1. 동일 요일·시간대와 여러 주간의 순위 유지율을 계산한다.
2. 단일 이상치 제거와 결측 처리 전후 순위 변화를 비교한다.
3. 과거 자료만으로 순위를 만들고 이후 관측과 비교한다.
4. 거리·시간범위·결측처리·S-DoT 사용 여부·Area 가중치를 바꿔 민감도를 본다.

현재는 후보별 시계열이 없어 Backtesting 결과를 만들 수 없다.

## 11. 원격 운영근거와 미확인 항목

공식 시설·진입·이용 정보가 있더라도 보행 안전, 카트 이동·정차, 판매·점유 허가,
혼잡 방해 가능성과 실제 판매시간은 원격자료만으로 확정할 수 없다. 확인되지 않은
모든 항목은 `NOT_VERIFIED`다. 공개된 제한이 나중에 확인되면 해당 후보를 제외할
수 있지만, 자료 부재를 허용으로 해석하지 않는다.

## 12. 불확실성·하향정책

- 직접근거가 없으면 Spot 인구·밀집도·추천시간을 만들지 않는다.
- 복수 후보·동일 비교기준·반복성이 없으면 D-020의 원격 SPOT 추천 Eligibility를
  충족하지 않는다.
- 근거 일부만 있으면 `원격 근거 확인 중`, 정적 근거만 있으면 `판매 후보`다.
- 명확한 제한·충돌·오래된 자료가 있으면 `추천 제외`, Area 근거만 있으면 AREA로
  하향한다.

사용 금지 표현: 판매 가능한 Spot, 안전한 Spot, 카트 정차 가능 Spot, 현장검증 완료,
실제 판매 적합, 판매 성공 가능성이 높음, 매출이 증가할 Spot.

## 13. 후속 작업구조

정책 정합화 PR이 main에 반영된 뒤 Issue #128에서 13개 Area의 선정 근거를 같은
최소 기준으로 조사한다. 그 결과와 PM 결정을 거친 뒤 다음을 각각 별도 승인한다.

1. 실제 Spot 후보 범위 승인
2. 공식 위치·근거 Dataset 구성
3. S-DoT 또는 대체 동적 근거 수집 Pilot
4. Spot Feature·반복성·Backtesting 구현
5. 데이터 우선순위 규칙 구현
6. Recommendation Output Contract 구현
7. 지도 UI 프로토타입
8. 화면 기반 사용성 검증

현장검증 Issue는 만들지 않는다. 화면 검증은 장소 적합성이 아니라 정보 이해도와
의사결정 유용성을 확인한다.

## 14. PM 결정사항

다음 한 단계는 D-020 정책 정합화 PR의 main 반영이다. 반영 전에는 Issue #128
조사를 시작하지 않는다. 이번 문서는 우선 Area 선정, 실제 Spot 등록, 데이터 수집
또는 추천 실행을 승인하지 않는다.

## 15. 근거 출처

이번 작업은 공개 페이지의 설명만 읽었고 파일 다운로드·API 호출·실데이터 수집은
하지 않았다.

- [서울시 지하철호선별 역별 승하차 인원 현황](https://data.seoul.go.kr/bsp/wgs/dataView/data300View/516.do): 역·시간 단위 대리자료 후보
- [서울시 교통카드이용정보](https://data.seoul.go.kr/dataList/7/literacyView.do): 시간대별 역 이용자료 후보
- [서울시 지하철 정보 묶음](https://data.seoul.go.kr/dataList/32/literacyView.do): 역·주변시설·접근정보 출처 안내
- [서울시 S-DoT 유동인구 측정기 설치정보](https://data.seoul.go.kr/dataList/OA-15964/S/1/datasetView.do?tab=A): 센서 위치 출처
- [서울교통공사 역별 역세권 현황](https://www.data.go.kr/data/15044230/fileData.do): 출구번호·인근 시설 후보 출처
- [서울교통공사 외부 출입구 캐노피 현황](https://www.data.go.kr/data/15082999/fileData.do): 출입구 식별·시설정보 후보
- [역 출입구 인근 주요시설 데이터 폐기 안내](https://www.data.go.kr/bbs/ntc/selectNotice.do?originId=NOTICE_0000000004350): 2025년 폐기된 자료와 대체자료 부재 한계
- [광화문광장 시설 안내](https://gwanghwamun.seoul.go.kr/ghm/facility/list.do?codeId=CODE_04&fcltSn=52&mid=1011&pitem=place13&seq=04&siteGrpKey=ghm&siteId=ghm): 공식 구역정보
- [광화문광장 사용신청 안내](https://gwanghwamun.seoul.go.kr/ghm/bbsPost/62/4890/detail.do?mid=1020): 공개 이용절차·제한 참고
- [서울식물원 안내도](https://botanicpark.seoul.go.kr/front/img/%EC%95%88%EB%82%B4%EB%8F%84.pdf): 마곡나루 연결·공원 구역정보
- [코엑스 오시는 길](https://www.coex.co.kr/guide/directions/): 삼성역 연결·진입로 정보
- [코엑스 시설안내](https://business.coex.co.kr/exhibition-hall/facilities-information-floor/): 공식 시설구역 정보
