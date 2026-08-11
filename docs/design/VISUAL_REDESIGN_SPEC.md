# FreshManager Visual Redesign Specification

## 1. 문서 목적과 현재 판정

이 문서는 Issue #154 Area-first 웹 파일럿의 기능·데이터 계약을 바꾸지 않고,
사용자 제공 UI Reference, AI Premium Reference의 승인된 시각 특성과 공식 지도
서비스의 일반 UX 원칙을 적용할 시각 기준을 정의한다. 외부 화면·코드·아이콘·지도
Asset을 복사하지 않는다.

```text
ui_functional_status=IMPLEMENTED
local_visual_prototype_status=PM_APPROVED
ui_visual_quality_status=PM_APPROVED_FOR_INTEGRATION
visual_acceptance=APPROVED_FOR_INTEGRATION
reference_fidelity_status=PASS
actual_browser_zoom_200=PENDING_MANUAL_QA
user_test_readiness=NOT_READY
portfolio_readiness=NOT_READY
official_current_data=NOT_CONNECTED
historical_time_average=NOT_CONNECTED
recurring_peak_analysis=NOT_CONNECTED
official_forecast_60=NOT_CONNECTED
official_forecast_120=CONTRACT_NOT_APPROVED
fixture_forecast_120=FIXED_PRESENTATION_ONLY
fixture_reference_time=14:00_FIXED_PRESENTATION_ONLY
official_forecast_180=NOT_CONNECTED
spot_population=FIXED_PRESENTATION_ONLY
fixture_data_mode=IMPLEMENTED_PENDING_PM_VISUAL_REVIEW
field_verification=NOT_PERFORMED
area_information_architecture_status=PASS
spot_information_architecture_status=PASS
linear_regression_user_facing_status=EXCLUDED_DUE_TO_VALIDATION_ERROR
linear_regression_source_code_status=RETAINED
linear_regression_pm_analysis_status=FUTURE_SEPARATE_SCREEN
official_seoul_forecast_status=PRIMARY_USER_FACING_FORECAST
historical_descriptive_analysis_allowed_after_contract_approval=true
visual_polish_iteration=07_FINAL_PROTOTYPE_INTEGRATION
ready_for_commit=true
ready_for_merge=false
```

## 2. Reference 우선순위

1. 제품·데이터 의미: Product·Architecture 정본
2. 시각 Layout·Component: 사용자 원본 UI Reference 6개와 `REFERENCE_NOTES.md`
3. 시각 밀도·Typography·Surface: `AI-REF-01-premium-field-operations-map.png`
4. 지도·예측 UX Pattern: 승인된 공식 Web Reference
5. 현재 구현: 기능·State·API Binding·Accessibility 보존용
6. Codex 자율해석: 최소화

문서와 이미지가 충돌하면 정본 문서를 따른다. AI Reference에서는 Pretendard 방향,
Emerald·Neutral 색, 절제된 Border·Shadow, Button·Badge·Card·Drawer·Marker의 밀도만
참고한다. Reference의 지도, 좌표, 숫자, 주소, 점수, 순위, Sidebar, 8개 Spot,
Chart·Service 상태·Mobile Navigation과 외부 Brand Asset은 구현 근거로 사용하지 않는다.

## 3. 현재 구현 진단

Redesign 전 구현은 Area 직접 선택, 단일 Drawer·Bottom Sheet, Spot 3개, 명시 선택,
지도 실패 Fallback, Browser-only 위치정보와 접근성 흐름을 갖췄지만 큰 Header·Drawer,
일반 버튼, 문자기호 Icon과 빈 표의 반복이 지도보다 UI 틀을 앞세웠다. 현재 Preview는
아래 변경으로 이 문제를 보완했다.

Redesign은 다음만 바꾼다.

- 지도를 주 시각영역으로 되돌리는 비율과 밀도
- Header·Control·Drawer·Bottom Sheet의 크기와 위계
- 직접 작성한 Inline SVG Icon과 Marker 상태
- 빈 표를 대체하는 정상적인 Empty State
- Spot 목록·상세·선택의 단계적 정보 노출
- Area의 현재·오늘의 변화·반복 패턴·데이터 기준 정보구조
- Spot의 선택 구역 전망·후보별 인구·단일 현장 확인상태·제한 정보구조

API·Backend·데이터 가용성 계약, 추천 여부, 위치정보 수명과 지도
Loader·Retry·Cleanup은 변경하지 않는다. 120분 값과 내부 범위 기준점·증감 계산은 고정
Fixture 표시모드에만 존재하며 API Field나 실제 데이터로 취급하지 않는다. Area 값을
Spot 값으로 복사하지 않으며 선형회귀 결과를 사용자 화면에 표시하지 않는다.

## 4. 사용자 Reference 차이 Matrix

| Screen | Reference Pattern | Current Implementation | Gap | Required Change | Must Preserve | Must Not Copy |
|---|---|---|---|---|---|---|
| `UI-01-desktop-default-map.png` | 1줄 Compact Header, 전체 Map, 좌측 소형 Control, 하단 Legend | 78px Header, 150px 폭 Control, 문자기호 Icon, 지도 실패 안내가 중앙을 크게 점유 | Map 중심성이 약하고 관리화면 인상이 남음 | Header 66px, 44px Control, 접근 가능한 담당 구역 Select, 중립 Fallback Surface와 후보 목록 진입 | Area 직접 선택, 기준시각, 도움말, 지도 없이 이용 | 지도 이미지·지명·좌표·Zoom·Logo·Mock 수치 |
| `UI-02-desktop-spot-list-drawer.png` | Map 위 단일 우측 Drawer, 같은 높이의 Card 3개 | Drawer 최대 500px, Card 130px, 상태문구와 간격이 큼 | Map 가용폭과 비교 밀도가 낮음 | 공통 464px Drawer, Compact Intro, 정돈된 Identity·주소·거리·상태, Card 전체를 하나의 클릭 대상으로 구성 | 정확히 3개, 번호는 식별용, 선택 없음 가능 | 순위 의미, 판매 점수, 외부 Map·주소·거리 |
| `UI-03-desktop-spot-detail-drawer.png` | Identity 우선, 상태·시점·제한과 하단 CTA 영역의 단계적 배치 | 큰 표와 여러 `—`가 중심이고 Identity와 행동이 분산됨 | 데이터 없음이 핵심정보보다 크게 보임 | Compact 시점 Row, 이유·표시제한·이용 가능정보를 설명하는 Empty State, 52px Sticky CTA | Prototype 출처, 현장 한계, 명시 선택, 재선택 | 매출 점수·순위·운영 적합성·Mock 인구 |
| `UI-04-mobile-area-info-and-spot-list-bottom-sheet.png` | Area 현재·1시간·3시간 정보를 상단에 두고 후보목록은 별도 Bottom Sheet에 둔 단일열 배치, 큼직한 Touch Target | 126px Header와 2열 Control이 지도 세로공간을 많이 차지 | 첫 화면의 Map Context가 좁음 | Mobile Header 압축, Control을 지도 가장자리로 정리, Map Context를 남기는 Sheet 최대 76dvh | Desktop과 같은 데이터·상태, Focus 이동·복귀 | 이미지 숫자·주소·Provider·판매 문구 |
| `UI-05-mobile-spot-detail-bottom-sheet.png` | 상단 Handle·Identity, 읽기 쉬운 단일열 정보 | 좁은 화면에서도 최소 430px Table이 가로 Scroll을 요구 | 한 손 탐색과 핵심정보 독해가 어려움 | Table 대신 세로 Compact Row, 내부만 Scroll, 하단 CTA 고정 | 데이터 없음, 제한, 위치 선택 가능 | 점수·순위·비교기준 Mock·추정 거리 |
| `UI-06-mobile-spot-selected-state.png` | Check와 명확한 Selected 상태, 상세 맥락 유지 | 선택은 상태문구와 보라색 강조 중심 | 색상 외 Marker·Card 상태가 충분히 강하지 않음 | Marker Check, Card의 `선택됨`, Inline Status와 변경 가능 문구 | `role=status`, `aria-live=polite`, Global Toast 없음 | 서버 저장·확정·Lock 주장, 외부 Check Asset |
| `REFERENCE_NOTES.md` | 문서 우선, 이미지 시각 참고, 운영값·지도 Asset 복사 금지 | 기능 계약은 대체로 준수하나 문자기호와 Reference 밀도 차이가 큼 | 시각 우선순위가 코드에 충분히 반영되지 않음 | 정본 의미는 유지하고 Layout·Spacing·Typography만 Reference에 맞춤 | 후보 위치 용어, 누락값 비생성, NAVER Adapter | 판매 위치 문구, 점수·순위, 외부 이미지·CSS·SVG |

### 4.1 요소별 최종 방향

| 요소 | 최종 방향 |
|---|---|
| Header | Desktop 66px 한 줄, Mobile은 Brand·도움말과 Area Selector를 최소 높이로 배치 |
| Area Selector | 시각적 Label 없이 접근 가능한 이름과 Placeholder·현재 선택을 Control 안에 표시 |
| Map Surface | 화면 대부분을 차지하며 Fallback은 중립 Surface와 `후보 위치 3곳` 목록 진입을 제공 |
| Map Control | 44px Touch Target, Inline SVG, 짧은 문구, 최소 Shadow |
| Marker | Default·Opened·Selected를 색상과 모양·Check로 구분, 번호는 표시 순서 |
| Drawer | Desktop 공통 464px, 상·우·하 16px Inset의 단일 Floating Panel, Header·Scroll·Footer 분리 |
| Bottom Sheet | 상단 Radius 24px, 최대 76dvh, 내부 Scroll과 Sticky CTA |
| Spot Card | 이름 우선, 주소·거리·데이터상태 보조, 선택 시 Check와 `선택됨` 표시 |
| Data State | 값이 있으면 Compact Row, 없으면 이유·미표시 원칙·가능 행동을 안내 |
| CTA | 52px, 하나의 Primary Action, 선택 후에도 변경 가능성 유지 |

## 5. 공식 Web Reference 조사 Matrix

근거일은 모두 `2026-08-01`이다. Screenshot·Asset·코드는 복사하지 않았다.

| Service | URL | Observed Pattern | FreshManager Adaptation | Forbidden Carryover | Screenshot Copied |
|---|---|---|---|---|---|
| Uber Offline Delivery Heatmap | https://www.uber.com/us/en/blog/offline-delivery-heatmap/ | Driver 앱 홈에서 Map과 경계 Zone을 주 화면으로 두고 상태와 다음 행동을 가까이 제공 | Map 우선, 선택 Area·Marker·상태·단일 행동의 단계적 노출 | 수요색, Heatmap, 주문·수익·Surge, Best Zone·Hotspot, 경로유도·매출보장·자동추천 | NO |
| Google Maps Busy Area | https://support.google.com/maps/answer/11323117?hl=ko | Area 혼잡과 Area 내부 장소를 구분하고 충분한 데이터가 없으면 표시하지 않음 | Area와 Spot을 분리하고 데이터 부족을 정상 Empty State로 처리 | 상대 혼잡도를 총인구·판매기회로 전환·오용, Google Label·Graph | NO |
| Google Business Popular Times | https://support.google.com/business/answer/6263531?hl=ko | 과거 일반 패턴과 현재 상태를 구분하며 자료가 부족하면 숨김 | 현재·미래·비교근거를 구분하고 Spot 값 부재 시 생성하지 않음 | 인기시간·대기·체류시간 생성, 과거값을 현재·예측으로 표현 | NO |
| Placer.ai Trade Area Analysis | https://www.placer.ai/guides/trade-area-analysis | 제품 화면이 아닌 Trade Area 분석 설명형 Guide이며 실제 Marker·Panel 배치는 확인되지 않음 | Guide 주제만 참고하고 Map → Spot → 상세는 FreshManager 자체 계약으로 적용 | Trade Area 추정, 방문자·인구통계·경쟁·매출·점수 | NO |
| CARTO for Retail | https://carto.com/solutions/carto-for-retail/ | Interactive Map과 Point-and-click 분석을 설명 | Map과 선택대상 Panel 결합, 한 화면 한 행동으로 축소 | KPI Dashboard, Chart·Layer Toolbar, Site Selection·Clustering·White Space·외부 데이터 보강·Hotspot·Revenue Prediction | NO |
| ArcGIS Dashboards | https://www.esri.com/ko-kr/arcgis/products/arcgis-dashboards/overview | Map·List 등 연결 요소가 상호작용에 따라 갱신 | Marker·목록·Drawer 상태 동기화 | 다중 Widget·Gauge·KPI·관리자 구성화면 | NO |
| Foursquare Studio | https://docs.foursquare.com/analytics-products/docs/what-is-studio | Map이 Dataset·Layer·Interaction·Legend를 구분 | 후보 Marker Layer와 최소 Legend만 사용 | Upload·Join·Filter·Layer 편집·분석 Console | NO |
| TomTom Traffic Flow | https://developer.tomtom.com/traffic-api/documentation/tomtom-orbis-maps/v2/traffic-flow/traffic-flow-service | Current 상태와 Quality Indicator를 분리 | 값·품질·기준시각을 분리하고 없음 상태 유지 | Traffic Tile·색상·산식·실시간성을 인구 근거로 전용 | NO |
| Mapbox Traffic Data | https://www.mapbox.com/traffic-data | Live와 Typical의 데이터 성격·갱신주기를 구분 | 현재·일반패턴·미래예측을 구분하고 조용한 대체 금지 | Traffic UI·자동 Typical 대체·Telemetry·Mapbox Asset | NO |
| NAVER Maps API v3 | https://navermaps.github.io/maps.js.ncp/docs/ | Map·Control·Layer·Marker·InfoWindow·Overlay를 분리 | 기존 Adapter 경계를 유지하고 Surface·Marker·Panel 책임 분리 | 미확인 옵션·Mobile 동작 추측 | NO |
| NAVER Map Tutorial | https://navermaps.github.io/maps.js.ncp/docs/tutorial-Map.html | DOM에 Map을 만들고 `fitBounds`로 Bounds를 표시 | Spot 3개가 보이도록 기존 `fitBounds` 유지 | 예제 좌표·Map Type·미확인 Padding API | NO |
| NAVER Controls Tutorial | https://navermaps.github.io/maps.js.ncp/docs/tutorial-Controls.html | Control·Scale·Copyright·Logo 위치를 MapOptions로 관리 | Preview CSS에 하단 공식요소용 공간을 두며 실제 Credential Runtime의 안전영역은 후속 확인 | Control DOM 변경·Logo 숨김·Custom Control 중첩 | NO |
| NAVER Marker | https://navermaps.github.io/maps.js.ncp/docs/naver.maps.Marker.html | HTML Icon, Anchor, Title, Click, Z-index를 지원 | 직접 작성 Marker에 Size·Anchor·상태를 명시하고 목록 대체경로 유지 | 외부 Marker Asset, 번호 순위화, 미지원 충돌처리 가정 | NO |
| NAVER InfoWindow | https://navermaps.github.io/maps.js.ncp/docs/naver.maps.InfoWindow.html | Marker Anchor·Auto-pan·Padding을 지원 | 상세는 Drawer·Sheet로 유지하고 중복 InfoWindow를 만들지 않음 | 긴 상세 중복, 원본문자열 HTML 삽입, 과밀 Overlay | NO |

공식 페이지에서 직접 확인되지 않은 Map 실패 UX는 외부 서비스의 관찰 사실로
주장하지 않는다. Map/Data 실패 분리는 FreshManager 자체 제품·오류 계약이다.

## 6. Visual Concept

```text
visual_concept=FIELD_OPERATIONS_MAP_FIRST
```

- 현장 업무용이며 Map을 첫 판단 영역으로 사용한다.
- 한 번에 한 가지 행동만 강조하고 정보는 단계적으로 연다.
- 데이터가 없어도 고장난 화면이 아니라 정상적인 제품상태로 보인다.
- 분석 Dashboard가 아니라 사용자가 Area 안 후보를 직접 고르는 도구다.
- Overlay, 색, Shadow와 장식은 최소화한다.
- Modern하지만 장식적이지 않고, 포트폴리오 검토에 견딜 완성도를 목표로 한다.

## 7. Visual Token

외부 UI Library 없이 다음 CSS Custom Property를 사용한다.

```css
:root {
  --color-brand-700: #006b5e;
  --color-brand-600: #008577;
  --color-brand-500: #00a08d;
  --color-brand-100: #dff5f0;
  --color-brand-50: #f0faf7;
  --color-surface-canvas: #f3f6f5;
  --color-surface-base: #ffffff;
  --color-surface-raised: #ffffff;
  --color-surface-subtle: #f7f9f8;
  --color-surface-selected: #edf9f6;
  --color-text-primary: #172320;
  --color-text-secondary: #5e6b67;
  --color-text-tertiary: #84908c;
  --color-border-default: #dce4e1;
  --color-border-strong: #bcc9c5;
  --color-warning: #b96b16;
  --color-warning-subtle: #fff5e8;
  --color-unavailable: #737f7b;
  --color-unavailable-subtle: #f0f3f2;
  --radius-control: 12px;
  --radius-card: 16px;
  --radius-panel: 20px;
  --shadow-floating-control: 0 4px 14px rgba(21, 47, 41, 0.10);
  --shadow-panel: 0 20px 54px rgba(21, 47, 41, 0.16);
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --font-size-caption: 12px;
  --font-size-label: 13px;
  --font-size-control: 14px;
  --font-size-body: 15px;
  --font-size-section: 16px;
  --font-size-spot-title: 18px;
  --font-size-panel-title: 22px;
  --font-size-metric: 20px;
  --line-height-caption: 17px;
  --line-height-label: 18px;
  --line-height-control: 20px;
  --line-height-body: 23px;
  --line-height-section: 24px;
  --line-height-spot-title: 26px;
  --line-height-panel-title: 30px;
  --line-height-metric: 28px;
  --font-weight-regular: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
}
```

공식 Pretendard v1.3.9 Variable Dynamic Subset 스타일시트를 `index.html`에서 읽고,
첫 Font Family를 `"Pretendard Variable"`로 둔다. Binary·npm Package는 저장하지 않는다.
고정 치수는 Base spacing 4px, Desktop Header 66px, 우측에서 16px 떨어진 Floating
Drawer 464px, Mobile Sheet 최대 76dvh, Map Control 44px, Touch Target 최소 44×44px,
Primary CTA 52px, Control Radius 12px, Card Radius 16px, Mobile Panel 상단 Radius
24px, Icon 20px, Stroke 1.8px로 한다.

## 8. Component와 Icon 원칙

기존 `App.vue`의 상태·요청 흐름을 유지한다. 이 Preview에서 반복이 명확하지 않은
Wrapper Component는 만들지 않는다. Icon은 동일 `viewBox`, `stroke-linecap`과
`stroke-linejoin`을 쓰는 직접 작성 Inline SVG로만 표현한다.

| Component | 시각 책임 |
|---|---|
| Header | Brand, Area Selector, 기준시각, Compact Help |
| Map Action | 44px Control과 간결한 Icon·Label |
| Fallback Map | 중립 Surface, `후보 위치 3곳` 목록 진입, 이용 상태·재시도 |
| Spot Card | 표시순서, Identity, 주소·거리·상태, Selected Check |
| Drawer·Bottom Sheet | 단일 Panel Header, 내부 Scroll, Sticky CTA |
| Population State | Area와 Spot을 분리한 Compact Metric Cell과 데이터 없음 안내 |
| Selection Status | Check, 선택 완료, 변경 가능 안내 |

내부 상태코드는 API·Type·Logic에서 유지하되 사용자 화면에서는 다음 표현만 쓴다.

| 내부 상태 | 사용자 표현 |
|---|---|
| `DATA_UNAVAILABLE` | 구역 인구 데이터 준비 중 |
| `NO_COMPLETE_SNAPSHOT` | 사용할 수 있는 최신 데이터가 없습니다 |
| `SPOT_PROTOTYPE_DATA_UNAVAILABLE` | 후보 위치별 인구 데이터가 아직 준비되지 않았습니다 |
| `NOT_VERIFIED` | 현장 확인 전 |
| `PM_MANUAL_PROTOTYPE` | 프로토타입 데이터 |
| `PM_MANUAL` | 직접 입력 |
| `PROTOTYPE` | 프로토타입 |

### 8.1 Fixture Data Mode와 Population Graph

`오늘의 변화`는 현재·60분·120분·180분의 네 Slot을 항상 유지하는 Responsive
Inline SVG다. 실제 범위가 있으면 최소~최대 Range와 `(min + max) / 2` 내부 기준 Point를
표시하되 사용자 화면에는 `중앙값`을 노출하지 않는다. 증감수·증감률은 Point의
Hover·Keyboard Focus·Tap Tooltip에서만 제공한다. 인접한 두 Slot에 직접값이 모두
있을 때만 직선 Segment를 연결하며 곡선,
보간과 60분~180분 건너뛰기 연결은 하지 않는다. 실제 API의 120분 계약은 승인되지
않았으며, 120분 Fixture는 기능·정보구조 검토를 위한 표시값으로만 사용한다.

Fixture의 상단 `기준시각`은 모든 Area에서 고정값 `14:00`을 표시한다. 이는 화면
검토용 시각이며 실제 서울시 관측시각이나 현재시각 기반 동적값이 아니다. Official
모드는 API가 제공한 확인 가능한 시각만 표시하고, Unavailable 모드는 `—`로 유지한다.

표시모드는 다음 세 값만 허용한다.

```text
fixture    = 고정 시뮬레이션 집계값 표시
unavailable = 데이터 없음 상태 표시
official   = API가 제공한 값만 표시
```

명시값이 없으면 Local Development는 `fixture`, Production Build는 `unavailable`을
사용한다. Query Parameter로 모드를 바꾸지 않는다. Fixture는 정확히 5개 Area와 기존
API ID에 대응하는 15개 Spot의 현재·60·120·180분 집계값, Area별 6개 시간대와 반복
피크 2개만 보유한다. 14일 Raw 시계열, 이름·주소·좌표, API Response, Backend,
Storage와 실제 데이터는 Fixture에 넣지 않는다.

정적 Fixture는 Vite Config 평가 때 실제 값 모듈을 불러오기 전에 Source의 Type-only
Import와 동적 값 생성 금지를 검사하고, 통과한 값만 순수 검증함수로 확인해
Development와 Build를 Fail-fast 처리한다. API 응답 뒤에는 선택 Area의 Spot ID 3개와 Fixture ID를 정확히
비교하며, 불일치하면 Fixture 값을 표시하지 않고 `후보 위치 정보를 불러오지
못했습니다.`만 사용자에게 알린다.

데이터 성격은 표시모드별 도움말과 Area의 `데이터 기준`에서만 표시하며, Fixture는
`기준시각 14:00`도 함께 기록한다. 일반 Card·Chart와 Spot 상세에 Badge를 반복하지
않는다.

선형회귀 Source는 보존하지만 Validation Error 때문에 사용자 화면에서는 제외한다.
서울시 공식 Forecast만 현재 사용자용 1차 Forecast다. 잔차·MAE·RMSE·R²·검증기간과
Model Version은 향후 별도 `PM 분석 → 모델 실험결과` 화면에서만 검토한다.

## 9. 핵심 Preview 화면 계약

### 9.1 Screen A — Desktop Default Map

66px Header와 Compact Control을 사용하고 Map이 나머지 화면을 채운다. 실제 지도
자격정보가 없으면 중립 Surface, `지도 없이 목록 이용`, 재시도와 `후보 위치 3곳`
목록 진입을 제공한다. 지도 하단 고정 후보 Card Strip과 가짜 도로·지명·지도 이미지는
만들지 않는다.

### 9.2 Screen B — Desktop Area Information Drawer

Area 이름 다음에 현재 유동인구, `오늘의 변화` Graph, `반복 패턴`의 시간대별 평균·
자주 붐비는 시간, 데이터 기준을 순서대로 둔다. Fixture 모드에서는 현재·60·120·180분의
Range를 기본 표시하고 Point 상호작용 때만 증감을 제공하며, 06·09·12·15·18·21시
집계값을 표시한다. 데이터 기준은 `서울열린데이터광장`, `14일`, `84개`,
`기준시각 14:00`, `연결 완료`를 명시한다. `연결 완료`는 Fixture의 테스트 화면
문구이며 실제 Area API Production 연결 완료를 뜻하지 않는다.

### 9.3 Screen C — Desktop Spot List Drawer

464px Drawer에서 후보 3개를 같은 수준의 Card로 표시한다. 이름, 주소, 가능한
직선거리와 데이터상태만 제공한다. 번호는 표시순서이며 우열·추천·순위를 뜻하지
않는다. 선택된 Card는 Check와 `선택됨` 문구를 함께 사용한다.

### 9.4 Screen D — Desktop Spot Detail Drawer

Identity → 주소·유형·거리·단일 `현장 확인 전` 상태 → `선택 구역 전망` Compact Area
Graph → 후보 위치별 현재·60·120·180분 예상 인구 Graph → 제한 → Sticky CTA 순서로
표시한다. `현장 운영 확인` 2×3 Grid와 반복 Prototype Badge는 만들지 않는다. Area
정보는 구역 전체 맥락이라고 명시하고 후보 위치 값으로 복사하지 않는다. 제한사항은
실제 판매 가능 여부·접근성·안전성·카트 정차 가능성의 현장 확인 필요를 한 번만 알린다.

### 9.5 Screen E — Mobile Spot Detail Bottom Sheet

Sheet는 최대 76dvh이며 Map Context를 남긴다. 상단 Handle, 제목·닫기, 내부 Scroll과
52px Sticky CTA를 사용한다. 390×844와 360×800에서 가로 Overflow가 없어야 한다.

### 9.6 Screen F — Mobile Selected State

Marker Check, Card의 `선택됨`, `role=status`·`aria-live=polite` Inline Status로
표시한다. 상세과 CTA를 유지하며 다른 후보로 변경할 수 있음을 명시한다. Global
Toast와 서버 저장·확정 표현을 사용하지 않는다.

## 10. 금지 시각스타일

- 구형 관리자 Dashboard, Desktop 3열, 별도 관리자 Navigation
- 큰 일반 사각형 버튼 3개, 대형 KPI Card, Donut·Gauge·임의 Heatmap
- Emoji·Unicode 기호를 주요 Icon으로 사용
- 과도한 Shadow·Glassmorphism·Gradient·Border·카드 중첩
- 점수·순위·Best·Optimal·추천·판매성과 표현
- 기본·Production 화면의 실제값처럼 보이는 Mock 숫자
- 원인 설명 없이 `—`만 반복해 고장난 화면처럼 보이는 구성
- 외부 Screenshot·Icon·CSS·SVG·Logo·Map Asset 복사

## 11. Visual Acceptance

| 항목 | 기준 |
|---|---|
| 공통 | Reference 방향, Map 중심, Token 일관성, 정상 Empty State, 점수·추천 없음. 고정 Fixture는 승인된 5개 Area·15개 Spot 표시값만 허용 |
| Desktop | Header ≤68px, 세 Drawer 공통 464px, Compact Control, 명확한 CTA, 가로 Overflow 없음 |
| Mobile | Sheet ≤76dvh, Map Context, 내부 Scroll, Sticky CTA, 360px 가로 Overflow 없음 |
| 접근성 | Touch 44px, Chart Hover·Keyboard Focus·Tap Tooltip, Visible Focus, Keyboard·Escape·Focus Return, Status Announcement |
| Typography | 실제 `Pretendard Variable` Load, 400·500·600·700 Weight만 사용, 12px 미만 Text 없음 |
| Resolution | 1440×900·1200×800·390×844·360×800을 가능하면 `deviceScaleFactor=2`로 실측 |
| 데이터 | Area·Spot 분리, Fixture 기준시각은 고정 `14:00`, Fixture 120분은 표시전용, Production 기본 unavailable, Rank·추천·선형회귀 출력 0건, 누락값 생성·대체 없음 |
| 지도 | 기존 NAVER Adapter·Retry·Cleanup, 공식 Control DOM·Logo를 변경하지 않음. 실제 Credential Runtime 안전영역은 별도 확인 |

실제 NAVER Credential Runtime, 실제 Area Artifact, 실제 Spot 인구 입력과 사용자
사용성 검증은 이 시각 계약의 승인범위가 아니다. Exact-head CI 성공 뒤의 Vercel
Preview만 별도 PM 승인 범위이며 Production 배포는 승인되지 않았다. API·Type·Schema
변경과 Area 값을 Spot 값으로 사용하는 처리도 승인범위가 아니다.
