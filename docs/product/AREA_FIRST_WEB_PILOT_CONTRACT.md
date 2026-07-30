# Area-first Web Pilot Contract

- 문서 상태: Draft
- 버전: v0.1.0
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-30
- 최종 수정일: 2026-07-30
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - [`FreshManager_PRD_v1.0.md`](FreshManager_PRD_v1.0.md)
  - [`RECOMMENDATION_OUTPUT_CONTRACT.md`](RECOMMENDATION_OUTPUT_CONTRACT.md)
  - [`DECISION_LOG.md`](../../ai-context/DECISION_LOG.md)의 D-020, D-021, D-022
  - [`PROJECT_STATUS.md`](../../PROJECT_STATUS.md)
- 변경 시 PM 승인: 필요

---

## 1. 목적과 정본 책임

이 문서는 FreshManager 초기 웹 파일럿의 Area-first 제품 흐름, UI 상태와 데이터
표시 경계를 소유하는 단일 상세 정본이다. 프래시매니저가 본인의 담당 Area를 먼저
선택하고, 선택 Area의 현재·60분·180분 유동상황과 Area 안의 Spot 3개를 확인한 뒤
판촉 후보 위치를 직접 선택하는 경험을 정의한다.

이 문서는 HTTP·저장 Schema, Application Service 구현, 지도 SDK 초기화, 화면
Component와 배포 절차를 소유하지 않는다. 다른 정본에는 현재 상태와 이 문서의
참조만 기록하고 아래 상세계약을 복제하지 않는다.

## 2. 기존 결정과의 관계

- D-020의 장기 원격 데이터 기반 SPOT 추천 목표는 유지한다.
- D-021의 5개 Area, Area당 Spot 3개, 사용자 Spot 선택, 서울시 Forecast 사용과
  머신러닝 미사용 계약은 유지한다.
- D-021 Recommendation Core와 Application Service는 여러 Area의 기회를 비교하는
  내부 분석 기능과 구현 이력으로 보존한다.
- D-022는 초기 웹 파일럿의 기본 진입 흐름을 시스템 Area 추천에서 사용자의 담당
  Area 직접 선택으로 바꾸고, 명확히 배지된 PM 직접 입력 Spot 프로토타입 표시를
  허용한다. 공식·계산·자동산출 Spot 값은 계속 금지한다.
- 기존 Recommendation Service는 Area-first 화면의 Primary API가 아니다. 선택
  Area 조회 Application Service는 별도 Issue에서 정의·구현한다.

고정 계약은 다음과 같다.

```text
area_selection_mode=USER_CHOICE
area_auto_recommendation=false
spot_selection_mode=USER_CHOICE
spot_auto_recommendation=false
machine_learning_used_for_recommendation=false
official_recommendation_allowed=false
```

사용자가 선택한 Area 또는 Spot을 시스템 추천 결과로 표현하지 않는다.

## 3. 사용자·문제·표현 상한

### 3.1 대상 사용자

- 기존 담당구역을 배정받은 프래시매니저
- 특히 지역 판매 노하우가 충분하지 않은 초보 프래시매니저

### 3.2 해결할 문제

출근·점심·퇴근시간과 개인의 감에만 의존해 한 장소에서 판촉시간을 소비하지만
실제 유동인구가 적어 판매기회를 놓칠 수 있는 문제를 다룬다. 이 문제 가설은 현재
판매실적이나 사용자 연구로 검증 완료된 사실이 아니다.

### 3.3 서비스 목적과 금지 표현

담당 Area의 현재·미래 유동상황과 Area 안의 후보 Spot을 함께 확인해 판촉 위치와
시간을 유연하게 판단하도록 지원한다. 다음을 주장하지 않는다.

- 매출 상승 또는 판매 성공 보장
- 최적 위치 확정
- 공식 Spot 추천
- 운영 적합성·안전·정차 가능성 보장

## 4. 고정 파일럿 범위와 사용자 흐름

| 항목 | 고정값 |
|---|---|
| Area 선택 | 승인된 5개 중 사용자 직접 선택 |
| Spot 선택 | 선택 Area의 정확히 3개 중 사용자 직접 선택 |
| 시간 표시 | 현재·60분·180분을 함께 표시 |
| Area 데이터 | 서울시 공식 Area 데이터 |
| Spot 수치 | PM 직접 입력 프로토타입 데이터 |
| 추천·ML | Area·Spot 자동추천 없음, ML 미사용, 공식 추천 불허 |

기본 흐름은 다음과 같다.

```text
서비스 접속
→ hy 본사를 중심으로 네이버 지도 표시
→ 담당 Area Dropdown 선택
→ 선택 Area로 지도 이동
→ Area 현재 유동인구·혼잡도 표시
→ Area의 Spot 3개 표시
→ Spot 핀 또는 목록 클릭
→ Bottom Sheet 상세정보 표시
→ Spot 현재·60분·180분 프로토타입 정보 확인
→ 과거 비교기준 선택
→ 점수·순위·직선거리 확인
→ 판촉 후보 위치로 선택
→ 선택 완료
```

별도 시간 선택버튼과 선택 확인 팝업은 사용하지 않는다. 60분·180분 정보는 Spot
Bottom Sheet에서 동시에 표시한다.

## 5. Area 선택과 초기 지도

Area Dropdown의 초기 문구는 `담당 Area를 선택하세요`다. 허용 Area는 정확히
다음 5개다.

| Area 코드 | 표시명 |
|---|---|
| `POI032` | 서울식물원·마곡나루역 |
| `POI088` | 광화문광장 |
| `POI014` | 강남역 |
| `POI025` | 뚝섬역 |
| `POI072` | 여의도 |

Area 미선택 상태에서는 Area 유동정보, Spot 핀·목록과 Spot 상세를 숨긴다. Area를
선택하면 해당 Area로 이동하고 Spot 3개가 모두 보이도록 지도 범위를 조정한다.
Area를 변경하면 이전 Area 수치, Spot 상세와 선택 상태를 즉시 해제한다.

지도 Provider는 네이버 지도 JavaScript API다. Area 미선택 시 hy 본사를 기본
중심으로 사용하지만 다음 값은 PM 확인 전까지 확정하지 않는다.

```text
default_location_name
default_address
default_latitude
default_longitude
default_zoom
coordinate_status=PM_CONFIRMATION_REQUIRED
```

주소·검색결과만으로 좌표와 zoom을 추측하지 않는다. Client ID 실제값은 문서와
Git에 기록하지 않는다. 후속 환경변수 이름 후보는 `NAVER_MAP_CLIENT_ID`이며 이번
문서가 실제 환경변수 생성이나 키 발급을 승인하지 않는다.

## 6. Area 공식 데이터 표시 계약

선택 Area에는 다음 정보를 표시한다.

- Area명
- 현재 유동인구 최소·최대, 현재 혼잡도, 데이터 기준시각
- 60분 후 예상 유동인구 최소·최대, 예측 대상시각, 현재 대비 증감수·증감률
- 180분 후 예상 유동인구 최소·최대, 예측 대상시각, 현재 대비 증감수·증감률

출처는 `서울시 공식 Area 데이터`로 표시한다. 기준시각과 예측 대상시각을 구분하고,
Area 값을 특정 Spot의 직접 관측값·예측값처럼 표시하지 않는다.

## 7. Spot 프로토타입 데이터 계약

각 Area에는 정확히 3개 Spot을 제공한다. Spot 카드와 Bottom Sheet에는 다음 UI
영역을 둔다.

- 현재 유동인구·현재 혼잡도
- 60분 후 예상 유동인구·예상 혼잡도
- 180분 후 예상 유동인구·예상 혼잡도
- 과거 비교 증감수·증감률
- 판촉 기회점수·Area 내 순위

초기 프로토타입에서 위 값은 PM이 직접 입력한 값만 표시한다. 서울시 Area 데이터를
Spot별로 계산·분배하거나 누락값을 추측해 생성하지 않는다.

```text
data_status=PROTOTYPE
input_method=PM_MANUAL
score_source=PM_MANUAL
rank_source=PM_MANUAL
```

화면에는 `프로토타입 데이터`, `PM 직접 입력` 배지를 함께 표시한다. `서울시 공식
Spot 데이터`, `AI 추천점수`, `공식 순위`, `예측모델 Spot 결과`라는 표현은 금지한다.

## 8. 과거 비교 계약

Spot 상세의 `비교기준` Dropdown은 다음 세 값만 허용한다.

| 코드 | 화면 표시 |
|---|---|
| `PREVIOUS_DAY` | 전일 같은 시간 |
| `PREVIOUS_WEEK` | 지난주 같은 요일·시간 |
| `RECENT_4WEEK_AVERAGE` | 최근 4주 같은 요일·시간 평균 |

기본값은 `RECENT_4WEEK_AVERAGE`다. 화면 용어는 `유동인구 증감수`와
`유동인구 증감률`을 사용하며 `인구 이동률`은 사용하지 않는다. 비교값 역시 PM 직접
입력 프로토타입 값이며 이번 계약에서 계산식을 정의하지 않는다.

## 9. Spot 상세와 선택

Spot 핀 또는 목록 클릭은 Bottom Sheet를 열 뿐 최종 선택을 뜻하지 않는다. Bottom
Sheet에는 다음을 표시한다.

- Spot명·주소·유형
- 프로토타입 데이터 배지와 제한사항
- 현재·60분·180분 정보
- 과거 비교 Dropdown과 증감수·증감률
- 점수·순위
- 현재 위치에서의 직선거리와 다른 Spot까지의 직선거리

`판촉 후보 위치로 선택` 버튼을 눌러야 선택이 완료된다. 추가 확인 팝업은 계약에
포함하지 않는다. 선택 후 핀과 카드를 함께 강조하고 다른 Spot으로 다시 선택할 수
있다. 기본선택·자동선택·시스템 산출 추천순위는 없다.

## 10. 현재 위치와 직선거리

페이지 접속 직후 위치권한을 요청하지 않는다. 사용자가 `내 위치 표시` 버튼을 누를
때만 브라우저 위치권한을 요청한다.

현재 위치는 서버·Database·파일·Local Storage·Session Storage·Cookie에 저장하거나
전송하지 않으며 새로고침 시 폐기한다. 위치권한 거부 또는 위치 확인 불가가 Area·
Spot 조회와 선택을 막지 않는다.

거리는 다음 두 관계의 직선거리만 표시한다.

- 현재 위치에서 선택 Area의 각 Spot까지
- 선택한 Spot에서 나머지 두 Spot까지

표현 예시는 `현재 위치에서 직선거리 약 510m`다. 도보거리·도보시간·실제 이동시간·
최적 경로로 표현하지 않는다. 거리 계산방식과 코드는 후속 구현 범위다.

## 11. UI 상태 계약

다음 상태는 하나만 선택되는 전역 Enum이 아니라 Area·Spot·Map·Geolocation의 독립
상태군이다. 예를 들어 `MAP_UNAVAILABLE`과 `AREA_AVAILABLE`,
`GEOLOCATION_DENIED`와 `SPOT_DETAIL_OPEN`은 함께 성립할 수 있다.

| 상태 | 표시정보 | 숨김정보 | 사용자 안내문구 | 재시도 | 다음 행동 |
|---|---|---|---|---|---|
| `AREA_UNSELECTED` | Area Dropdown, 선택 안내, 가능하면 기본지도 | Area 수치, Spot 핀·목록·상세 | 담당 Area를 선택하세요 | 해당 없음 | Area 선택 |
| `AREA_LOADING` | 선택 Area명, Loading 안내 | 이전 Area 수치·Spot·선택 | Area 정보를 불러오는 중입니다 | 완료·실패 후 가능 | 대기 또는 Area 변경 |
| `AREA_AVAILABLE` | Area 현재·60분·180분 공식정보, 출처·기준시각, Spot 3개 | 클릭 전 Spot 상세 | Spot을 눌러 비교하세요 | 수동 새로고침 가능 | 핀 또는 목록 선택 |
| `AREA_DATA_UNAVAILABLE` | Area명, 정적 Spot 이름·주소, 안전한 제한 안내 | 공식 Area 수치·증감 | Area 정보를 사용할 수 없어 값을 표시하지 않습니다 | 수동 가능 | 재시도·다른 Area·정적 Spot 확인 |
| `SPOT_DETAIL_OPEN` | Spot 정체성, 프로토타입 배지, 가능한 수동정보·거리·제한 | 시스템 추천 표현 | 정보를 확인한 뒤 후보 위치를 선택하세요 | 해당 없음 | 비교기준 변경 또는 명시 선택 |
| `SPOT_SELECTED` | 선택 핀·카드 강조, 선택 완료, 상세 | 자동·공식 추천 주장 | 판촉 후보 위치로 선택했습니다. 다른 Spot으로 변경할 수 있습니다 | 해당 없음 | 유지 또는 재선택 |
| `SPOT_PROTOTYPE_DATA_UNAVAILABLE` | Spot명·주소·유형, 데이터 없음과 제한 안내 | 누락된 수동값·점수·순위 | 프로토타입 값을 만들거나 대체하지 않았습니다 | 수동 가능 | 정적 정보로 선택·다른 Spot 확인·데이터 갱신 |
| `MAP_UNAVAILABLE` | Area Dropdown, Area 텍스트 정보, Spot 이름·주소 목록·상세·선택 | 지도와 핀 | 지도를 불러오지 못했지만 목록으로 이용할 수 있습니다 | 수동 가능 | 지도 재시도 또는 목록 사용 |
| `GEOLOCATION_REQUESTING` | 기존 화면, 권한 요청 중 안내 | 현재 위치·거리 | 브라우저 위치권한 응답을 기다리는 중입니다 | 응답 후 가능 | 허용 또는 거부 선택 |
| `GEOLOCATION_AVAILABLE` | 현재 위치, 직선거리, 기존 Area·Spot 정보 | 도보거리·시간·경로 | 거리는 직선거리 근사값입니다 | 명시 버튼으로 가능 | Spot 비교·선택 |
| `GEOLOCATION_DENIED` | 기존 Area·Spot 화면, 거부 안내 | 현재 위치·거리 | 위치 없이도 이용할 수 있습니다 | 사용자 동작 후 가능 | 주소·목록으로 계속 |
| `GEOLOCATION_UNAVAILABLE` | 기존 화면, 기기·브라우저 제한 안내 | 현재 위치·거리 | 위치를 확인할 수 없지만 나머지 기능은 이용할 수 있습니다 | 자동 재시도 없음 | 지도·주소로 계속 |
| `INPUT_INVALID` | 안전한 입력오류, Area Dropdown | 잘못된 입력 기반 파생값·Spot 상세 | 승인된 Area 또는 비교기준을 다시 선택하세요 | 입력 수정 후 가능 | 입력 교정 |

잘못된 입력과 Area 변경 시 이전 Area·Spot 데이터를 그대로 남기지 않는다. 지도·위치
실패는 텍스트 기반 Area·Spot 조회와 사용자 선택을 차단하지 않는다. Spot 수동
프로토타입 값이 없더라도 정적 Spot 정보와 사용자 선택은 유지하되 데이터 없음과
한계를 명확히 표시한다.

## 12. 지도·위치 장애 Fallback

네이버 지도가 로딩되지 않아도 Area Dropdown, Area 현재·미래 정보, Spot 이름·주소
목록, Spot 상세와 사용자 선택을 제공한다. 위치권한이 거부되거나 위치를 확인할 수
없어도 Spot 위치·주소·프로토타입 정보와 선택을 제공한다.

지도와 위치기능은 서비스 전체의 필수 성공조건이 아니다. 장애 시 확인되지 않은
값을 이전 Area 값이나 추정 거리로 대체하지 않는다.

## 13. 개인정보·저장 경계

초기 프로토타입에서는 다음을 사용하거나 저장하지 않는다.

- 로그인·사용자 계정·사번·이름·전화번호
- 현재 위치와 Spot 선택이력
- 판매량·재고·결제
- Analytics·광고 SDK

Area별 접근권한과 공통 접근코드는 후속 제한배포 단계의 별도 결정으로 보류한다.

## 14. 모바일·접근성 원칙

기준 화면폭은 360px, 390px, 430px다. 다음을 만족해야 한다.

- 가로 Overflow 없음
- 충분한 터치영역과 조작 가능한 Dropdown
- 지도 드래그와 Bottom Sheet 스크롤 충돌 최소화
- 긴 주소 줄바꿈
- 색상 외 텍스트·형태로 상태 표시
- 지도 없이도 핵심정보 이해·선택 가능

Brand Color, 정확한 크기·간격과 Component Library는 후속 UI 설계에서 결정한다.

## 15. 후속 구현 경계

Area-first 화면은 사용자 선택 Area를 조회하는 별도 Application Service가 필요하다.
그 Service의 인터페이스·오류·Runtime과 UI 구현은 별도 Issue에서 다룬다. 이번
계약은 다음을 구현하거나 승인하지 않는다.

- Python Service, HTTP Endpoint, Web Framework
- Spot 프로토타입 CSV·JSON과 PM 수치 입력
- 네이버 지도 Application, Client ID와 지도·위치·거리 코드
- HTML·CSS·JavaScript, Database, 배포
- 실제 API·Recommendation·ML·S-DoT 실행
- 로그인과 사용자 파일럿

## 16. PM 확인 대기 항목

다음 지도 기본값은 `PM_CONFIRMATION_REQUIRED`다.

```text
default_location_name=NOT_PROVIDED
default_address=NOT_PROVIDED
default_latitude=NOT_PROVIDED
default_longitude=NOT_PROVIDED
default_zoom=NOT_PROVIDED
```

Area별 접근권한과 제한배포 방식도 후속 결정이다. 미결정값은 구현 기본값으로
추측하지 않는다.

## 17. 완료 정의

- 사용자 담당 Area 선택이 기본 진입 흐름으로 명시됨
- 정확한 5개 Area와 Area당 Spot 3개 계약이 명시됨
- Area 공식 데이터와 Spot PM 수동 프로토타입 데이터가 분리됨
- 현재·60분·180분, 과거 비교, Bottom Sheet와 명시 선택이 정의됨
- 13개 UI 상태와 지도·위치 실패 Fallback이 정의됨
- 개인정보 비저장과 모바일 기준이 정의됨
- D-020·D-021 구현 이력과 기존 Core·Service가 보존됨
- 코드·데이터·UI·지도·API·배포가 구현되지 않음
- PM 문서 검토 완료

## 18. 변경 이력

| 버전 | 날짜 | 변경내용 | 승인상태 |
|---|---|---|---|
| v0.1.0 | 2026-07-30 | D-022 Area-first 초기 웹 파일럿의 제품·UI·데이터 표시 계약 초안 | PM 검토 대기 |
