# Area-first Web Pilot Contract

- 문서 상태: Approved
- 버전: v0.5.0
- 작성자: 신동현
- 최종 승인자: 신동현
- 최초 작성일: 2026-07-30
- 최종 수정일: 2026-08-01
- 적용 프로젝트: Freshmanager Data PoC
- 관련 문서:
  - [`FreshManager_PRD_v1.0.md`](FreshManager_PRD_v1.0.md)
  - [`RECOMMENDATION_OUTPUT_CONTRACT.md`](RECOMMENDATION_OUTPUT_CONTRACT.md)
  - [`DECISION_LOG.md`](../../ai-context/DECISION_LOG.md)의 D-020, D-021, D-022,
    D-023과 D-024(`ACCEPTED_BY_PM_FOR_ISSUE_154`)
  - [`PROJECT_STATUS.md`](../../PROJECT_STATUS.md)
  - [`REPOSITORY_READINESS_AUDIT.md`](../architecture/REPOSITORY_READINESS_AUDIT.md)
  - [`DESIGN.md`](../design/DESIGN.md)
- 관련 작업: Issue #150, PR #151, Issue #154
- 변경 시 PM 승인: 필요

---

## 1. 목적과 정본 책임

이 문서는 FreshManager 초기 웹 파일럿의 Area-first 제품 흐름, UI 상태와 데이터
표시 경계를 소유하는 단일 상세 정본이다. 프래시매니저가 본인의 담당 Area를 먼저
선택하고, 선택 Area의 현재·1시간 후·3시간 후 유동상황과 Area 안의 Spot 3개를 확인한 뒤
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

실제 프래시매니저 인터뷰를 통해 담당 Area 안에서 판촉 위치를 판단하는 과정이 경험과
개인 노하우에 의존하는 문제 맥락을 확인했다. 이번 파일럿은 이 문제를 바탕으로 Area
유동정보와 Spot 비교정보를 제공하는 화면구조와 선택과정을 검토하기 위한 프로토타입이다.

```text
actual_interview_execution_status=PM_CONFIRMED
repository_evidence_status=NOT_TRACKED
synthetic_matrix_status=NOT_ACTUAL_INTERVIEW_EVIDENCE
gate_c_status=SEPARATE_EVALUATION_REQUIRED
```

Git에는 개인정보 없는 실제 Interview Evidence Summary 또는 외부 Evidence
Reference가 아직 없다. [`GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md`](../analysis/GATE_C_SYNTHETIC_INTERVIEW_MATRIX.md)는 공개자료 기반
합성자료이며 실제 인터뷰·직접 인용·Gate C 통과 근거가 아니다. 후속 Evidence
Traceability는 개인정보·원본 녹취·참여자 식별정보를 제외한 별도 PM 승인 범위다.

### 3.3 서비스 목적과 금지 표현

담당 Area의 현재·미래 유동상황과 Area 안의 후보 Spot을 함께 확인해 판촉 위치와
시간을 유연하게 판단하도록 지원한다. 다음을 주장하지 않는다.

- 매출 상승 또는 판매 성공 보장
- 최적 위치 확정
- 공식 Spot 추천
- 운영 적합성·안전·정차 가능성 보장

## 4. 서비스 형태·고정 파일럿 범위와 사용자 흐름

서비스 형태는 다음으로 고정한다.

```text
Responsive Web
Desktop Web + Mobile Web
Tablet 전용 UI 없음
```

데스크톱과 모바일은 같은 데이터·Component·선택상태를 사용하고 Layout만 바꾼다.
좁은 화면은 모바일웹 Layout을 사용하며, 태블릿 전용 Component·정보구조는 만들지
않는다. 정확한 CSS Breakpoint는 후속 UI 구현계약에서 코드 상수로 확정한다.

데스크톱 기본화면은 지도 중심이다. Header, 담당 Area Dropdown, 데이터 기준시각,
도움말, 지도, 선택 Area의 Spot Marker 3개, `구역 정보`, `후보 위치 3곳`,
`내 위치 표시`, 지도 확대·축소와 범례를 표시한다. Area 정보와 Spot 목록·상세는
기본화면에 고정하지 않고 필요할 때 지도 위 우측 단일 Drawer로 표시한다. Area
Drawer와 Spot Drawer는 상호배타적이며 한 번에 하나만 연다.

모바일은 같은 데이터·Component·선택상태를 지도 위 단일 Bottom Sheet로 표시한다.
`Area 선택 → 지도·Spot Marker 3개 → 구역 정보 또는 후보 위치 3곳 열기 → Marker
또는 목록 Card 클릭 → 후보 위치 상세 Bottom Sheet → 판촉 후보 위치로 선택` 흐름을
사용한다. 추가 확인 팝업은 사용하지 않는다.

| 항목 | 고정값 |
|---|---|
| Area 선택 | 승인된 5개 중 사용자 직접 선택 |
| Spot 선택 | 선택 Area의 정확히 3개 중 사용자 직접 선택 |
| 시간 표시 | 현재·1시간 후·3시간 후를 함께 표시(내부 `horizon_minutes=60`·`180`) |
| Area 데이터 | 서울시 공식 Area 데이터 |
| Spot 인구정보 | PM 직접 입력 프로토타입 데이터 |
| 추천·ML | Area·Spot 자동추천 없음, ML 미사용, 공식 추천 불허 |

기본 흐름은 다음과 같다.

```text
서비스 접속
→ hy 본사를 중심으로 네이버 지도 표시
→ 담당 Area Dropdown 선택
→ 선택 Area로 지도 이동
→ 지도에 Area의 Spot Marker 3개와 정보 Trigger 표시
→ 필요할 때 구역 정보 또는 후보 위치 3곳 열기
→ Marker 또는 목록 Card 클릭
→ Desktop 단일 Drawer 또는 Mobile Bottom Sheet에 Spot 상세정보 표시
→ Spot 현재·1시간 후·3시간 후 프로토타입 정보 확인
→ 증감수·증감률·직선거리 확인
→ 판촉 후보 위치로 선택
→ 선택 완료
```

별도 시간 선택버튼과 선택 확인 팝업은 사용하지 않는다. 사용자 화면에서 `Horizon`,
`60분 호라이즌`, `180분 호라이즌`, `평균 예측`은 사용하지 않는다. 내부 기술·데이터
계약의 `horizon_minutes=60`·`180`은 현재로부터 예측 대상시각까지의 시간간격이며
평균이 아니다.

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

목표 지도 Provider는 네이버 지도 JavaScript API다. 현재 디자인의 지도는
Layout·Interaction 검토용 Placeholder이며 실제 Provider·좌표·Zoom·Marker 위치는
통합 단계에서 확정한다. Area 미선택 시 hy 본사를 기본 중심으로 사용하는 계약은
유지하지만 다음 값은 PM 확인 전까지 확정하지 않는다.

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

선택 Area의 구역 정보 Drawer 또는 Bottom Sheet에는 다음 정보를 표시한다.

- Area명
- 현재 유동인구 최소·최대, 현재 혼잡도, 데이터 기준시각
- 1시간 후 예상 유동인구 최소·최대, 예측 대상시각, 현재 대비 증감수·증감률
- 3시간 후 예상 유동인구 최소·최대, 예측 대상시각, 현재 대비 증감수·증감률

출처는 `서울시 공식 Area 현재 데이터`와 `서울시 공식 Area Forecast`로 표시한다.
기준시각과 예측 대상시각을 구분하고, Area 값을 특정 Spot의 직접 관측값·예측값처럼
표시하지 않는다. 1시간 후와 3시간
후는 각각 독립적으로 다음 EG-8D 중앙값 계산 의미를 재사용한다.

```text
current_population_midpoint
= (current_population_min + current_population_max) / 2

forecast_population_midpoint
= (forecast_population_min + forecast_population_max) / 2

expected_population_change
= forecast_population_midpoint - current_population_midpoint

expected_population_change_rate
= expected_population_change / current_population_midpoint

display_change_rate_percent
= expected_population_change_rate × 100
```

계산된 값은 Backend 또는 기존 Python Service가 제공하며 Frontend가 별도 계산공식을
만들지 않는다. 현재 중앙값이 0이면 증감률을 계산하거나 `0%`로 대체하지 않는다.
서울시 최소·최대 범위는 그대로 표시하고, 중앙값을 서울시 공식 단일 인구값처럼
표현하지 않는다. 도움말은 "증감수와 증감률은 서울시가 제공한 현재·예상 인구 범위의
중앙값을 기준으로 계산합니다."를 사용한다.

새 최신성 임계값을 만들지 않고 기존 EG-8D Freshness Gate의 `FRESH`, `DEGRADED`,
`STALE_BLOCKED`, `NO_COMPLETE_SNAPSHOT` 의미를 재사용한다. 각 미래 시점은 독립적으로
처리한다. `FRESH`는 정상 표시, `DEGRADED`는 경고와 함께 Area 참고정보 표시,
`STALE_BLOCKED`는 해당 미래값 미표시, `NO_COMPLETE_SNAPSHOT`은 표시 가능한 최신
Current가 있으면 현재정보만 표시한다. 다른 시간간격 값을 복사하거나 보간하지 않는다.

## 7. Spot 프로토타입 데이터 계약

각 Area에는 정확히 3개 Spot을 제공한다. 후보 위치 목록과 Layout별 상세영역
(Desktop 단일 Drawer·Mobile Bottom Sheet)에는 다음 UI 영역을 둔다.

- 데이터 기준시각
- 현재 예상 인구 범위
- 1시간 후 예상 인구 범위·증감수·증감률
- 3시간 후 예상 인구 범위·증감수·증감률
- Prototype 데이터 상태와 제한사항

Spot Identity 정적 Master와 Spot 인구 Prototype은 분리한다. Spot 인구값은 PM이 직접
입력한 값만 표시하며 서울시 Area 데이터를 Spot별로 계산·분배하거나 누락값을 추측해
생성하지 않는다.

Optional Runtime 입력의 허용 필드는 다음과 같다.

```text
pilot_area_code
spot_option_id
observed_at
current_population_min
current_population_max
forecast_60_population_min
forecast_60_population_max
forecast_180_population_min
forecast_180_population_max
data_status
input_method
source_note
updated_at
```

```text
data_status=PROTOTYPE
input_method=PM_MANUAL
spot_population_source=PM_MANUAL_PROTOTYPE
```

화면에는 `프로토타입 데이터`, `PM 직접 입력` 배지를 함께 표시한다. `서울시 공식
Spot 데이터` 또는 `예측모델 Spot 결과`라는 표현은 금지한다. PM 입력값이 없으면 정적
Spot 3개는 유지하고 인구·증감 필드는 `null`, 상태는
`SPOT_PROTOTYPE_DATA_UNAVAILABLE`로 반환한다.

## 8. Spot 증감 계산 계약

PM 수동 Prototype 인구 범위가 있는 시점만 다음 중앙값 계산을 적용한다.

```text
current_mid
= (current_population_min + current_population_max) / 2

future_mid
= (forecast_population_min + forecast_population_max) / 2

change_amount
= future_mid - current_mid

change_rate
= change_amount / current_mid
```

60분과 180분은 독립 계산한다. `current_mid=0`이면 증감률은 `null`이다. 일부 범위가
없으면 해당 시점은 unavailable이며 다른 시점이나 Area 값으로 채우지 않는다.

## 9. Spot 상세와 선택

Spot Marker 또는 목록 Card 클릭은 같은 Spot의 Layout별 상세영역(Desktop 단일
Drawer·Mobile Bottom Sheet)을 열 뿐 최종 선택을 뜻하지 않는다. Marker와 목록의
Opened 상태는 동기화한다. 해당 상세영역에는 다음을 표시한다.

- Spot명·주소·유형
- 프로토타입 데이터 배지와 제한사항
- 데이터 기준시각과 현재·1시간 후·3시간 후 인구정보
- 제공된 시점의 증감수·증감률
- 현재 위치에서의 직선거리

`판촉 후보 위치로 선택` 버튼을 눌러야 선택이 완료된다. 추가 확인 팝업은 계약에
포함하지 않는다. Marker는 Default·Opened·Selected 상태를 구분하고, 선택 후
Marker와 목록 Card를 함께 강조한다. 다른 Spot으로 다시 선택할 수 있다.
기본선택·자동선택은 없다.

## 10. 현재 위치와 직선거리

페이지 접속 직후 위치권한을 요청하지 않는다. 사용자가 `내 위치 표시` 버튼을 누를
때만 브라우저 위치권한을 요청한다.

현재 위치는 서버·Database·파일·Local Storage·Session Storage·Cookie에 저장하거나
전송하지 않으며 새로고침 시 폐기한다. 위치권한 거부 또는 위치 확인 불가가 Area·
Spot 조회와 선택을 막지 않는다.

거리는 현재 위치에서 선택 Area의 각 Spot까지의 직선거리만 표시한다. Spot 간
거리는 계산하거나 표시하지 않는다.

표현 예시는 `현재 위치에서 직선거리 약 510m`다. 도보거리·도보시간·실제 이동시간·
최적 경로로 표현하지 않는다. 계산은 Browser에서만 수행하고 좌표를 Backend로
전송하거나 영구 저장하지 않는다.

## 11. UI 상태 계약

다음 상태는 하나만 선택되는 전역 Enum이 아니라 Area·Spot·Map·Geolocation의 독립
상태군이다. 예를 들어 `MAP_UNAVAILABLE`과 `AREA_AVAILABLE`,
`GEOLOCATION_DENIED`와 `SPOT_DETAIL_OPEN`은 함께 성립할 수 있다.

| 상태 | 표시정보 | 숨김정보 | 사용자 안내문구 | 재시도 | 다음 행동 |
|---|---|---|---|---|---|
| `AREA_UNSELECTED` | Area Dropdown, 선택 안내, 가능하면 기본지도 | Area 수치, Spot 핀·목록·상세 | 담당 Area를 선택하세요 | 해당 없음 | Area 선택 |
| `AREA_LOADING` | 선택 Area명, Loading 안내 | 이전 Area 수치·Spot·선택 | Area 정보를 불러오는 중입니다 | 완료·실패 후 가능 | 대기 또는 Area 변경 |
| `AREA_AVAILABLE` | 데이터 기준시각, 구역 정보 Trigger, Spot Marker 3개 | Drawer를 열기 전 Area 공식 수치·Spot 상세 | 구역 정보나 후보 위치를 확인하세요 | 수동 새로고침 가능 | Trigger·Marker 또는 목록 선택 |
| `DATA_UNAVAILABLE` | Area명, 정적 Spot 이름·주소, 안전한 제한 안내 | 공식 Area 수치·증감 | Area 정보를 사용할 수 없어 값을 표시하지 않습니다 | 수동 가능 | 재시도·다른 Area·정적 Spot 확인 |
| `SPOT_UNSELECTED` | Spot Marker 3개와 후보 위치 목록 Trigger | Spot 상세·선택 강조 | 후보 위치를 눌러 정보를 확인하세요 | 해당 없음 | Marker 또는 목록 열기 |
| `SPOT_LIST_OPEN` | 후보 위치 3곳 목록과 Marker 연동상태 | Area Drawer·Spot 상세 | 후보 위치 3곳을 확인하세요 | 해당 없음 | 목록 Card 또는 Marker 선택 |
| `SPOT_DETAIL_OPEN` | Spot 정체성, 프로토타입 배지, 가능한 수동 인구정보·거리·제한 | 시스템 추천 표현 | 정보를 확인한 뒤 후보 위치를 선택하세요 | 해당 없음 | 명시 선택 |
| `SPOT_SELECTED` | 선택 핀·카드 강조, 선택 완료, 상세 | 자동·공식 추천 주장 | 판촉 후보 위치로 선택했습니다. 다른 후보 위치로 변경할 수 있습니다 | 해당 없음 | 유지 또는 재선택 |
| `SPOT_PROTOTYPE_DATA_UNAVAILABLE` | Spot명·주소·유형, 인구정보 표의 `—`, 데이터 없음과 제한 안내 | 누락된 수동값 | Spot별 프로토타입 인구 데이터가 아직 입력되지 않았습니다. | 수동 가능 | 정적 정보로 선택·다른 Spot 확인·데이터 갱신 |
| `MAP_PLACEHOLDER` | Layout·Interaction 검토용 지도 | 실제 좌표·Zoom 정확성 주장 | 지도와 위치는 후속 통합 단계에서 연결합니다 | 해당 없음 | UI 흐름 검토 |
| `MAP_LOADING` | 지도 Loading, Area·Spot 텍스트 정보 | 지도·Marker | 지도를 불러오는 중입니다 | 완료·실패 후 가능 | 대기 또는 목록 사용 |
| `MAP_AVAILABLE` | 지도·Marker·Control과 텍스트 정보 | 없음 | 후보 위치를 지도나 목록에서 확인하세요 | 수동 가능 | Marker·목록 사용 |
| `MAP_UNAVAILABLE` | Area Dropdown, Area 텍스트 정보, Spot 이름·주소 목록·상세·선택 | 지도와 핀 | 지도를 불러오지 못했지만 목록으로 이용할 수 있습니다 | 수동 가능 | 지도 재시도 또는 목록 사용 |
| `GEOLOCATION_IDLE` | `내 위치 표시` 버튼과 기존 화면 | 현재 위치·거리 | 필요한 경우 내 위치를 표시할 수 있습니다 | 해당 없음 | 명시 버튼 선택 |
| `GEOLOCATION_REQUESTING` | 기존 화면, 권한 요청 중 안내 | 현재 위치·거리 | 브라우저 위치권한 응답을 기다리는 중입니다 | 응답 후 가능 | 허용 또는 거부 선택 |
| `GEOLOCATION_AVAILABLE` | 현재 위치, 직선거리, 기존 Area·Spot 정보 | 도보거리·시간·경로 | 거리는 직선거리 근사값입니다 | 명시 버튼으로 가능 | Spot 비교·선택 |
| `GEOLOCATION_DENIED` | 기존 Area·Spot 화면, 거부 안내 | 현재 위치·거리 | 위치 없이도 이용할 수 있습니다 | 사용자 동작 후 가능 | 주소·목록으로 계속 |
| `GEOLOCATION_UNAVAILABLE` | 기존 화면, 기기·브라우저 제한 안내 | 현재 위치·거리 | 위치를 확인할 수 없지만 나머지 기능은 이용할 수 있습니다 | 자동 재시도 없음 | 지도·주소로 계속 |
| `FRESH` | 해당 미래정보 정상 표시 | 없음 | 저장된 최신 승인 데이터 기준입니다 | 해당 없음 | 정보 확인 |
| `DEGRADED` | 해당 미래정보와 경고 | 없음 | 참고가 필요한 데이터 상태입니다 | 수동 가능 | 경고와 함께 확인 |
| `STALE_BLOCKED` | 해당 미래값 이용불가 안내 | 오래된 미래값 | 오래된 미래값은 표시하지 않습니다 | 수동 가능 | Current 또는 다른 시점 확인 |
| `NO_COMPLETE_SNAPSHOT` | 표시 가능한 Current와 미래값 없음 안내 | 불완전한 미래값 | 완전한 미래정보를 사용할 수 없습니다 | 수동 가능 | Current 확인 |
| `INPUT_INVALID` | 안전한 입력오류, Area Dropdown | 잘못된 입력 기반 파생값·Spot 상세 | 승인된 Area를 다시 선택하세요 | 입력 수정 후 가능 | 입력 교정 |

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

## 14. 반응형·접근성 원칙

Desktop Web과 Mobile Web은 같은 기능·데이터·상태를 제공한다. Desktop은 단일
Drawer, 좁은 화면은 단일 Bottom Sheet Container를 사용하며 태블릿 전용 UI는
없다. 다음을 만족해야 한다.

- 가로 Overflow 없음
- 충분한 터치영역과 조작 가능한 Dropdown
- 최소 44×44px Touch Target
- Drawer·Bottom Sheet가 열릴 때 Focus 이동, 닫힐 때 실행요소로 Focus 복귀
- 지도 드래그와 모바일 Bottom Sheet 스크롤 충돌 최소화
- 긴 주소 줄바꿈
- 색상 외 텍스트·형태로 상태 표시
- 지도 없이도 핵심정보 이해·선택 가능

Brand Color, 정확한 크기·간격과 Component Library는 후속 UI 설계에서 결정한다.

## 15. 구현 및 승인 경계

Area-first 화면의 사용자 선택 Area 조회 Service·Read-only API·Vue UI·NAVER Map
Adapter와 Spot Population Prototype Runtime은 Issue #154에서 로컬 구현·검증했다.
현재 구현은 다음을 승인하거나 수행하지 않는다.

- 실제 Area 데이터 연결
- 실제 NAVER Map Credential 사용
- Spot 인구 Prototype 실데이터 입력
- Database와 배포
- 실제 API·Recommendation·ML·S-DoT 실행
- 로그인과 사용자 파일럿

Issue #154의 구현은 Draft PR 검토 전이며 공식 반영·배포 완료를 뜻하지 않는다.
`Responsive Web`과 `Desktop Web + Mobile Web` 제품계약, ADR-012의 Vue·FastAPI
경계와 Issue #152 Scaffold를 유지한다.

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
- 반응형 Desktop Web·Mobile Web, 태블릿 전용 UI 제외, 현재·1시간 후·3시간 후,
  증감 계산과 명시 선택이 정의됨
- Area·Spot·Map·Geolocation·Future Data 독립 상태군과 지도·위치 실패 Fallback이
  정의됨
- 개인정보 비저장과 모바일 기준이 정의됨
- D-020·D-021 구현 이력과 기존 Core·Service가 보존됨
- Area-first Service·Read-only API·Vue UI·NAVER Map Adapter·Spot Prototype Runtime은
  Issue #154에서 로컬 구현·검증됨
- 실제 Area 데이터·NAVER Map Credential·Spot Population 실데이터·배포는 미실행
- PM 문서 검토 완료

## 18. 변경 이력

| 버전 | 날짜 | 변경내용 | 승인상태 |
|---|---|---|---|
| v0.5.0 | 2026-08-01 | PM 수동 Spot 인구 Prototype·증감 계산·unavailable 계약으로 상세정보 범위를 정렬 | Issue #154 PM 변경 승인 |
| v0.4.0 | 2026-07-31 | Desktop 고정 3열을 지도 중심 기본화면과 상호배타 단일 Drawer로 교체하고 Mobile Bottom Sheet, Marker·목록 동기화와 디자인 정본 연결을 반영 | PM 변경 승인 |
| v0.3.0 | 2026-07-31 | 실제 인터뷰 PM 확인과 Git Evidence 미추적, 합성 Matrix 비증거, Gate C 별도 평가를 구분하고 Audit 목표구조와 현재 미구현 Runtime 경계를 명시 | PM 변경 승인 |
| v0.2.0 | 2026-07-30 | 최신 PM 결정에 따라 반응형 Desktop·Mobile Layout, 사용자 시간표현, 중앙값 기반 Area 증감, EG-8D 최신성 재사용, 실제 인터뷰 근거와 Audit 이후 ADR 경계를 반영 | PR #141 main 반영 |
| v0.1.0 | 2026-07-30 | D-022 Area-first 초기 웹 파일럿의 제품·UI·데이터 표시 계약 초안 | PM 검토 대기 |
