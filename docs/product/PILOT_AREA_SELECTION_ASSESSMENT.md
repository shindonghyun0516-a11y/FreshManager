# 파일럿 Area 최소 공통근거 스크리닝

- 상태: `PM_REVIEW_PROPOSAL`
- 기준일: 2026-07-29
- 관련 Issue: #128
- 상위 Issue: #99
- 선행 결정: D-018, D-020

## 1. 목적

승인된 13개 Area에 같은 최소 기준을 적용해 실제 Spot 근거를 만들 첫 파일럿
Area 1개와 Backup Area 1개를 PM에게 제안한다. 이 문서는 Area를 공식 선정하거나
Spot을 등록하지 않는다. 실제 데이터 수집, 추천 계산, UI·Backend 구현과 배포도
수행하지 않는다.

## 2. FreshManager 통합 파일럿 PoC

이번 제안은 다음 하나의 수직형 PoC에서 Gate A만 다룬다.

```text
Area·Spot 데이터 타당성
→ 파일럿 Area 선정
→ 실제 Spot Dataset
→ 동적 근거
→ 반복성·Backtesting
→ SPOT 추천 로직
→ 지도 UI·Backend
→ 제한 배포
→ 사용자 파일럿
→ Go/No-Go
```

Primary Area 1개, Backup Area 1개만 제안한다. Primary의 실제 Spot 3~5개 구성은
후속 Gate B의 일이며 이번 문서의 후보명은 조사대상일 뿐 실제 Spot이 아니다.

## 3. 최소 스크리닝 범위

각 Area에 다음 12개 항목을 같은 순서로 확인했다.

1. 공식 위치·시설정보 출처
2. 공통 공식자료의 해당 Area 행 존재
3. 실제 Spot 후보명 3~5개 확보 가능성
4. 공식 좌표 제공 여부
5. 동일 Area 후보 구분 가능성
6. Spot을 구분할 동적 근거 경로
7. 동일 기준시각·시간범위 비교 가능성
8. 반복 시계열 확보 가능성
9. 공개 운영·판매·점유 제한 자료
10. 오피스·유동판매 시나리오 적합성
11. 자료 최신성
12. 파일럿 구현 난이도

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

## 7. 13개 Area 비교표

`후보 구성 가능성`은 공식 명칭을 이용한 Gate B 조사후보이며 등록·좌표 확정·판매
허용을 뜻하지 않는다. `공통행 미확인`은 공통 공식자료의 개별 행을 내려받아
검증하지 않았다는 뜻이지 행이 없다는 뜻이 아니다.

| Area | 공식 위치·공통행 | 후보 구성 가능성 | 후보별 좌표·구분 | 동적 근거·동일시각·반복 | 운영 제한 | Evidence Readiness | Business Fit | 최신성·난이도 | Hard Filter |
|---|---|---|---|---|---|---|---|---|---|
| `POI019` 구로디지털단지역 | 구로구 공식 출구·깔깔거리 자료; 공통행 미확인 | 1·2·3·6번 출구 4곳 | 좌표 `NOT_CONFIRMED`; 명칭만 구분 | `AREA_OR_STATION_ONLY`; 후보별 근거·반복 `NOT_READY` | 출구 6 통행·정비 이슈; 판매 허용 `NOT_VERIFIED` | LOW | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | FAIL |
| `POI013` 가산디지털단지역 | 금천구 공식 출구·시설 자료; 공통행 미확인 | 2·4·5·7·11번 출구 5곳 | 좌표 `NOT_CONFIRMED`; 명칭만 구분 | `AREA_OR_STATION_ONLY`; 후보별 근거·반복 `NOT_READY` | 환승·출구 변경 이력; 판매 허용 `NOT_VERIFIED` | LOW | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | FAIL |
| `POI014` 강남역 | 강남구 공식 위치자료; 공통행 미확인 | 4번 출구 횡단보도·강남스퀘어·CGV강남 앞·점프밀라노 앞·국기원입구 5곳 | 주소 일부만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 120.5m Anchor S-DoT도 후보 구분 `NOT_READY` | 도로점용 절차 있음; 판매 허용 `NOT_VERIFIED` | MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM-HIGH | FAIL |
| `POI072` 여의도 | 서울시 공원 구역자료; 공통행 미확인 | 문화의마당·잔디마당·자연생태숲·전통의숲 4곳 | 구역명만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 후보별 근거·반복 `NOT_READY` | 장소사용 승인·행사 충돌 가능 | MEDIUM 정적·LOW 동적 | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM-HIGH | FAIL |
| `POI001` 강남 MICE 관광특구 | 코엑스 공식 접근·시설자료; 공통행 미확인 | 삼성역 5·6번, 봉은사역 7번, 코엑스 동문, 무역센터 정류장 5곳 | 위치명만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 가까운 S-DoT 없음 | 사유시설·공사·점용 조건 `NOT_VERIFIED` | MEDIUM | MEDIUM-HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | FAIL |
| `POI034` 선릉역 | 강남구 공식 위치자료; 공통행 미확인 | 출구 후보 3~5개 확보 가능성 `NOT_CONFIRMED` | 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 204.1m Anchor S-DoT도 후보 구분 불가 | 도로점용·판매 허용 `NOT_VERIFIED` | LOW-MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM | FAIL |
| `POI042` 역삼역 | 강남구 공식 위치자료; 공통행 미확인 | 출구 후보 3~5개 확보 가능성 `NOT_CONFIRMED` | 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 가까운 S-DoT 없음 | 도로점용·판매 허용 `NOT_VERIFIED` | LOW-MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM | FAIL |
| `POI025` 뚝섬역 | 성동구 공식 출구·시설자료; 공통행 미확인 | 4·5·6·8번 출구 4곳 | 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 56.4m Anchor S-DoT도 후보 구분 불가 | 판매 허용 `NOT_VERIFIED` | MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM | FAIL |
| `POI088` 광화문광장 | 서울시 공식 광장 구역·이용자료; 공통행 미확인 | 육조마당·놀이마당·해치마당·열린마당·광장숲 5곳 | 공식 지도상 구분; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 264.8m Anchor S-DoT와 역자료는 구역 구분 불가 | 사용허가·행사 영향; 판매 허용 `NOT_VERIFIED` | MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; MEDIUM-HIGH | BACKUP CONDITIONAL PASS |
| `POI003` 명동 관광특구 | 중구 공식 출구·관광특구 자료; 공통행 미확인 | 을지로입구역 1·4·5번 출구 3곳 | 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 173.2m Anchor S-DoT도 후보 구분 불가 | 보도·사유지 경계와 판매 허용 `NOT_VERIFIED` | LOW-MEDIUM | HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | FAIL |
| `POI119` 잠실역 | 서울시 공식 출구군·시설자료; 공통행 미확인 | 1·2, 3·4, 10·11번 출구군 3곳 | 출구군만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 273.6m Anchor S-DoT도 후보 구분 불가 | 대형 사유시설·공공영역 경계 `NOT_VERIFIED` | LOW-MEDIUM | MEDIUM-HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; HIGH | FAIL |
| `POI033` 서울역 | 서울시 공식 광장·보행로 자료; 공통행 미확인 | 서울역광장·만리동광장·퇴계로 교통섬·서울로7017 4곳 | 장소명만 확인; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 후보별 근거·반복 `NOT_READY` | 다기관·다층 공간과 점용 제약 | MEDIUM 정적·LOW 동적 | MEDIUM-HIGH | 확인일 2026-07-29; 콘텐츠 갱신일 `NOT_CONFIRMED`; VERY HIGH | FAIL |
| `POI032` 서울식물원·마곡나루역 | 서울식물원 공식 안내도·2026-07 운영페이지; 공통행 미확인 | 열린숲 1번 입구·주제원 7번 입구·식물문화센터·호수원·방문자센터 5곳 | 공식 지도상 구분; 후보별 좌표 `NOT_CONFIRMED` | `AREA_OR_STATION_ONLY`; 122.3m Anchor S-DoT는 후보 구분 전 재검증 필요 | 공원 운영·행사·판매 허용 `NOT_VERIFIED` | MEDIUM | MEDIUM-HIGH | 2026-07 운영·S-DoT 갱신 확인, 안내도 발행일 `NOT_CONFIRMED`; MEDIUM-HIGH | PRIMARY CONDITIONAL PASS |

합산점수는 만들지 않았다. 13개 모두 현재 원격 SPOT 추천 Eligibility는 미충족이며
실제 Spot과 후보별 동적자료는 0건이다. 두 조건부 통과는 **Gate A 조사 우선순위**일
뿐 SPOT 추천, 운영 적합성 또는 판매 허용 판정이 아니다.

## 8. Primary Pilot Area 제안

**`POI032` 서울식물원·마곡나루역**을 Primary로 제안한다.

- 공식 안내도에서 서로 구분되는 구역·입구 5곳을 조사후보로 구성할 수 있다.
- 2026-07 공식 운영페이지에서 시설 운영·접근을, S-DoT 페이지에서 2026-07-27
  자료 갱신을 확인했다. 안내도 자체 발행일은 `NOT_CONFIRMED`이며 Gate B에서 다시
  확인한다.
- 공원·역·업무권을 한 Area로 묶어 지도와 사용자 설명이 비교적 명확하다.
- 기존 역 중심 Anchor에는 `DIRECT_COVERAGE` S-DoT가 있고, 공식 지도에는 서로
  다른 정류소·입구가 표시돼 Gate C의 센서 설치위치·정류소 시간대 자료 대조를
  실패 가능하게 검증할 수 있다.
- 기존 Area Observation과 EG-8D 결과로 Area 판매기회·추천시간 후보 계산은 가능하다.
- 후보별 좌표, 독립 관측범위, 반복성, 판매·점유 허용은 아직 확인되지 않았다.

Hard Filter의 `검증 가능한 Pilot 경로` 조항으로만 조건부 통과한다. Gate B에서
공식 위치근거가 있는 후보 3개를 확보하지 못하거나 Gate C에서 최소 3개 후보를
같은 시각에 서로 구분할 승인 근거를 확보하지 못하면 Primary 제안은 즉시 실패한다.

## 9. Backup Pilot Area 제안

**`POI088` 광화문광장**을 Backup으로 제안한다.

- 육조마당·놀이마당·해치마당 등 공식 구역명이 있어 후보 설명이 명확하다.
- 공식 이용절차와 행사정보가 있어 운영 위험을 숨기지 않고 기록할 수 있다.
- Anchor 인근 S-DoT, 역·정류소 단위 반복자료와 공식 구역지도를 대조하는 Gate C
  Pilot 경로를 검증할 수 있다.
- 다만 행사 영향과 사용허가 변동이 크고, 현재 자료는 구역별 유동을 구분하지 못한다.

Backup도 조건부다. Primary 실패 시 자동 승격하지 않고 같은 Gate B·C를 통과해야
한다. 후보 3개별 동적 근거 또는 승인 대리근거를 만들 수 없으면 Backup도 폐기한다.

## 10. 각 후보의 실제 Spot 구성 가능성

| 제안 | Gate B 조사후보 | 현재 상태 |
|---|---|---|
| Primary | 열린숲 1번 입구, 주제원 7번 입구, 식물문화센터, 호수원, 방문자센터 중 3~5개 | 공식 지도 명칭만 확인; 실제 Spot 등록·좌표·판매 허용 0건 |
| Backup | 육조마당, 놀이마당, 해치마당, 열린마당, 광장숲 중 3~5개 | 공식 구역 명칭만 확인; 실제 Spot 등록·좌표·판매 허용 0건 |

Gate B는 후보별 공식 명칭, 검증 가능한 위치근거와 출처 확인일을 기록한다. 역 중심
대리좌표를 후보 좌표로 복사하지 않는다.

## 11. 동적 근거 Pilot 경로

1. Gate B 후보 위치를 공식 지도·공공 위치자료로 확정한다.
2. 후보 위치 기준으로 S-DoT 설치위치와 측정범위를 다시 대조한다.
3. 후보를 구분할 수 없다면 공식 정류소별 시간대 승하차 등 대체 경로의 실제 행과
   공간 대응을 확인한다. 대리근거 승인기준은 이때 PM이 결정한다.
4. 최소 3개 후보를 같은 기준시각·시간범위로 비교할 수 없으면 실패한다.
5. 반복 시계열을 확보한 뒤에만 순위 안정성과 Backtesting으로 이동한다.

현재 분류는 끝까지 `AREA_OR_STATION_ONLY`다. 위 경로는 동적근거를 확보했다는
주장이 아니라, Gate C에서 성공·실패를 판정할 수 있는 최소 검증계획이다.

## 12. 주요 데이터 공백

- 공통 역세권·출입구 자료의 13개 개별 행
- 후보별 공식 또는 검증 가능한 좌표와 측정범위
- 후보별 동일시각 동적 관측과 반복 시계열
- S-DoT 방문자수와 실제 후보의 공간 대응
- 정류소 자료를 Spot 대리근거로 인정할 조건
- 자료 결측·최신성·이상치와 순위 안정성 기준
- 이동판매, 점유, 안전, 카트 정차와 시설별 운영 허용

## 13. 구현·배포 위험

- Area·역 자료를 Spot 값으로 잘못 표시할 위험
- 단일 Anchor S-DoT를 여러 후보의 직접근거로 과대해석할 위험
- 행사·계절·날씨를 지속적인 판매기회로 오인할 위험
- 공원·광장의 이용허가를 판매 허용으로 오인할 위험
- 대리근거 승인 전에 후보 순위를 계산할 위험
- 현장검증 불가 상태를 운영 적합성 확인으로 잘못 표시할 위험

이 문서는 생산 Schema, 추천 로직, UI, Backend, Scheduler, 배포 또는 사용자 게시를
승인하지 않는다.

## 14. 후속 수직형 PoC Gate

| Gate | 내용 | 현재 상태 |
|---|---|---|
| A | Primary Pilot Area PM 선정 | 이번 문서의 PM 제안만 완료 |
| B | 실제 Spot 3~5개 위치근거 Dataset | 미실행 |
| C | S-DoT 또는 대체 동적 근거 Pilot | 미실행 |
| D | 반복성·Backtesting·순위 안정성 | 미실행 |
| E | 신뢰도·최신성·fallback 임계값 결정 | 미실행 |
| F | Recommendation Schema·추천 로직 구현 | 미실행 |
| G | 지도 UI·Backend 구현 | 미실행 |
| H | Scheduler·로그·모니터링·배포 준비 | 미실행 |
| I | 파일럿 설계·제한 배포 | 미실행 |
| J | 사용자 파일럿·Go/No-Go | 미실행 |

Gate A 이후는 별도 PM 승인 전 실행하지 않는다.

## 15. PM 결정사항

PM은 다음 한 가지만 결정한다.

> `POI032` 서울식물원·마곡나루역을 Gate A Primary로, `POI088` 광화문광장을
> Backup으로 승인하고 Gate B 계획 작성을 시작할지 결정한다.

다음 값은 아직 열려 있으며 Issue #128에서 정하지 않는다.

- `confidence_level` 산출기준과 임계값
- 최소 `rank_stability`
- 허용 결측률
- 데이터 freshness 상한
- 승인 대리근거 기준
- `fallback_reason` 최종 Enum
- 생산 Schema 대표 필드명 `recommendation_type` 또는 `target_level`
- SPOT+AREA Prediction의 UI 문구 규칙
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
