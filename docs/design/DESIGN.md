# FreshManager UI/UX Design Specification

- 문서 상태: `APPROVED · ACCEPTED`
- 버전: `v0.2.0`
- 적용 범위: Area-first 초기 웹 파일럿
- 관련 결정:
  - [`D-022`](../../ai-context/DECISION_LOG.md)
  - [`D-024`](../../ai-context/DECISION_LOG.md)
  - [`ADR-012`](../architecture/AREA_FIRST_WEB_API_ARCHITECTURE.md)
  - Related Issue: #150
  - Related Issue: #154
  - Related PR: #151
- 관련 제품계약:
  - [`AREA_FIRST_WEB_PILOT_CONTRACT.md`](../product/AREA_FIRST_WEB_PILOT_CONTRACT.md)
  - [`AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md`](../product/AREA_SPOT_RECOMMENDATION_AND_UI_POLICY.md)
- 변경 시 PM 승인: 필요

---

## 1. 문서 목적

이 문서는 FreshManager 지도 중심 UI의 사용자 흐름, 화면, Component, State와
사용자 문구를 정의한다. Stitch·Figma·Codex·Frontend 구현이 공통으로 따르는
디자인 기준선이다.

이 문서는 API, Python, Snapshot 선택 알고리즘, 데이터 수집과 배포를 소유하지
않는다. 제품 의미와 데이터 계산계약은 관련 제품·Architecture 정본을 따르며,
이 문서는 이를 복제하거나 변경하지 않는다.

## 2. 디자이너 역할과 판단순서

### 2.1 역할

- Primary Role: Senior Product Designer, UX Architect
- Specialization:
  - Map-based Field Operations SaaS
  - Responsive Web Application
  - Data-heavy Decision Support Interface
  - Accessible Interaction Design
  - Design System and Developer Handoff

### 2.2 의사결정 우선순위

1. 사용자 핵심 과업 완료
2. 데이터 의미와 근거의 정확성
3. 현재 상태와 다음 행동의 명확성
4. 지도 장애·권한 거부 시 기능 지속
5. 접근성
6. Desktop·Mobile 일관성
7. 구현 가능성과 Component 재사용성
8. 시각적 완성도

### 2.3 디자이너가 결정하지 않는 항목

- 서울시 API 수집방식
- Snapshot 선택 알고리즘
- Freshness 임계값
- Area·Spot 추천 Logic
- 실제 Spot 운영 적합성
- Backend Route
- Database·인증·배포구조
- 실제 지도 좌표·Zoom
- 실제 Spot Prototype 값

미확정사항은 `OPEN DECISION · PM 확인 필요`로 표시한다.

## 3. 고정 제품원칙

- Area는 사용자가 직접 선택한다.
- Spot은 사용자가 직접 선택한다.
- Area 자동추천과 Spot 자동추천은 없다.
- 승인된 Area는 5개다.
- 선택 Area마다 Spot은 정확히 3개다.
- 현재·1시간 후·3시간 후 정보를 표시한다.
- Area 정보는 서울시 공식 Area 데이터를 사용한다.
- Spot 수치는 PM 직접 입력 Prototype 데이터만 사용한다.
- Area 값을 Spot 값으로 복사·분배·추정하지 않는다.
- 위치권한은 선택사항이다.
- 지도 실패 시에도 목록으로 이용할 수 있다.
- 선택상태는 Browser Memory에서만 유지하며 영구 저장하지 않는다.
- Desktop과 Mobile은 같은 데이터·Component·State를 사용한다.
- Tablet 전용 UI는 만들지 않는다.

## 4. Desktop 지도 중심 Layout

기존 고정 3열 Dashboard를 사용하지 않는다. Desktop 기본화면은 지도를 중심으로
구성한다.

Area 선택이 완료된 기본 지도 상태에는 다음을 표시한다.

- FreshManager Header
- 담당 Area Dropdown
- 데이터 기준시각
- 도움말
- 지도 영역
- 선택 Area의 Spot Marker 3개
- `구역 정보` 버튼
- `후보 위치 3곳` 버튼
- `내 위치 표시` 버튼
- 지도 확대·축소
- 후보 위치·내 위치 범례

Area 미선택 상태에서는 Spot Marker와 Area·Spot 정보를 표시하지 않는다. 기본 지도
상태에서 다음을 항상 표시하지 않는다.

- Area 현재·1시간 후·3시간 후 Card
- Spot 목록
- Spot 상세
- 제한사항

## 5. 단일 Drawer 계약

Desktop은 지도 위에 겹쳐 표시하는 우측 Slide-over Drawer 하나만 사용한다. 동시에
둘 이상의 Drawer를 열지 않는다.

허용 상태는 다음과 같다.

1. 기본 지도
2. 지도 + 구역 정보 Drawer
3. 지도 + 후보 위치 목록 Drawer
4. 지도 + 후보 위치 상세 Drawer
5. 지도 + 후보 위치 선택 완료상태

다음 상태는 금지한다.

- 좌측 Area 정보 Panel + 우측 Spot 목록
- 좌측 Area 정보 Panel + 우측 Spot 상세
- 고정 3열 Dashboard

Drawer 동작은 다음과 같다.

- `구역 정보` 클릭 → 구역 정보 Drawer
- `후보 위치 3곳` 클릭 → 후보 위치 목록 Drawer
- Marker 클릭 → 해당 후보 위치 상세 Drawer
- 목록 Card 클릭 → 해당 후보 위치 상세 Drawer
- 상세 뒤로가기 → 후보 위치 목록 Drawer
- 닫기 → 기본 지도
- Area 변경 → Drawer·Opened Spot·Selected Spot 초기화
- Area Drawer와 Spot Drawer는 상호배타적

## 6. 구역 정보 Drawer

다음을 표시한다.

- Area명
- 현재 유동인구 최소·최대
- 현재 혼잡도
- 현재 관측 기준시각
- 1시간 후 예상 범위
- 1시간 후 혼잡도
- 1시간 후 증감수·증감률
- 1시간 후 예측 대상시각
- 3시간 후 예상 범위
- 3시간 후 혼잡도
- 3시간 후 증감수·증감률
- 3시간 후 예측 대상시각
- 데이터 출처
- 데이터 기준시각
- Freshness 또는 이용불가 상태

다음 표현은 사용하지 않는다.

- 실시간
- Live
- Monitoring
- 현재 접속시점 수집
- 자동 새로고침
- Telemetry

다음 표현을 사용한다.

- 데이터 기준시각
- 저장된 최신 승인 데이터 기준
- 서울시 공식 Area 데이터

Area 정보에는 `프로토타입 데이터` Badge를 표시하지 않는다.

## 7. 후보 위치 목록 Drawer

제목은 `후보 위치 3곳`이다. 각 목록 Card에는 다음을 표시한다.

- 번호
- 후보 위치명
- 주소 또는 위치설명
- 현재 위치 확인 후 직선거리
- Prototype 정보 이용 가능 여부
- 상세 진입 Chevron

목록 Card 전체를 클릭할 수 있어야 한다. 후보 위치 목록을 일반 HTML Select
Dropdown으로 축소하지 않는다.

근거가 확정되지 않은 다음 태그는 표시하지 않는다.

- 역세권
- 오피스 밀집
- 유동인구 많음
- 추천
- Best
- 최적

## 8. 후보 위치 상세 Drawer

사용자 화면 제목은 `후보 위치 상세`이다. 다음을 표시한다.

- 목록으로 돌아가기
- 닫기
- Spot 번호
- Spot명
- 주소 또는 위치설명
- 유형
- 직선거리
- `프로토타입 데이터` Badge
- `PM 직접 입력` Badge
- 데이터 기준시각
- 현재 예상 인구 범위
- 1시간 후 예상 인구 범위와 증감수·증감률
- 3시간 후 예상 인구 범위와 증감수·증감률
- 제한사항
- `판촉 후보 위치로 선택` Sticky CTA

Spot 인구정보는 `spot_population_source=PM_MANUAL_PROTOTYPE`인 PM 직접 입력값만
표시한다. 값이 없으면 표의 현재·1시간 후·3시간 후 값은 `—`로 유지하고
`Spot별 프로토타입 인구 데이터가 아직 입력되지 않았습니다.`를 표시한다. 서울시
공식 Area 값을 Spot 값으로 복사·분배·추정하지 않는다.

제한사항에는 다음을 포함한다.

- 실제 판매 허용 여부
- 접근성
- 안전성
- 카트 정차 가능성
- 시간대별 운영 가능성
- 현장 확인 필요

## 9. 선택 완료상태

`판촉 후보 위치로 선택`을 누르면 다음과 같이 표시한다.

- 선택 Marker에 체크 표시
- 선택 완료 Inline Status
- Drawer 상세는 유지 가능
- 다른 Spot으로 변경 가능

사용자 문구는 다음과 같다.

> 판촉 후보 위치로 선택했습니다.
>
> 다른 후보 위치로 변경할 수 있습니다.

다음 표현은 사용하지 않는다.

- 서버에 저장되었습니다
- Campaign에 등록됐습니다
- 위치가 확정됐습니다
- Lock 완료
- 변경할 수 없습니다

## 10. Mobile Bottom Sheet

Mobile은 Desktop과 같은 데이터·State·Component를 사용하고 Container만 Bottom
Sheet로 바꾼다.

- 구역 정보 → Bottom Sheet
- 후보 위치 목록 → Bottom Sheet
- 후보 위치 상세 → Bottom Sheet
- 선택 완료 → Bottom Sheet + Inline Status

추가 확인 Popup은 사용하지 않는다.

- 기본높이: `OPEN DECISION · PM 확인 필요`
- 최대높이: `OPEN DECISION · PM 확인 필요`
- 내용이 높이를 넘으면 Sheet 내부만 Scroll한다.
- 닫기 동작은 기본 지도로 돌아간다.
- 열릴 때 Sheet 제목 또는 첫 조작요소로 Focus를 이동하고, 닫을 때 실행한
  Trigger·Marker·Card로 Focus를 돌려준다.
- 상세의 `판촉 후보 위치로 선택`은 Sticky CTA로 유지한다.
- 지도 Drag는 지도에서, Bottom Sheet Scroll은 Sheet의 Scroll 영역에서 시작되도록
  제스처 영역을 분리한다.
- 모든 Touch Target은 최소 44×44px로 한다.

## 11. 지도·데이터 적용시점

### 11.1 Map

- UI 참고 이미지의 지도는 Layout·Interaction 검토용 Placeholder다.
- Issue #154는 NAVER Maps JavaScript API Adapter를 로컬 구현했지만 실제 Credential
  기반 Runtime은 아직 검증하지 않았다.
- 참고 이미지의 지명·좌표·Zoom·Marker 위치는 구현값으로 사용하지 않는다.

### 11.2 Data

- UI 참고 이미지의 수치는 정보구조·Component 검토용 Mock Data다.
- Issue #154 Runtime은 참고 이미지 수치를 사용하지 않으며 Area·Spot 인구값이 없으면
  `DATA_UNAVAILABLE`·`SPOT_PROTOTYPE_DATA_UNAVAILABLE`과 `null`을 표시한다.
- 실제 Area·Spot 데이터는 별도 승인 후 연결하며 Mock 값은 운영값 또는 사실로
  해석하지 않는다.

다음을 금지한다.

- Mock 값을 운영값으로 표현
- Area 값을 Spot 값으로 복사
- 누락값을 0·평균·추정값으로 대체
- Mock 수치로 운영결과·추천 주장

현재 승인범위는 다음과 같다.

- Layout
- Component
- Drawer·Bottom Sheet
- User Flow
- State
- UX Writing
- Responsive
- Accessibility

Issue #154에서 API Binding과 NAVER Map Adapter를 로컬 구현·검증했다. 다음은 후속
승인범위다.

- 실제 NAVER Map Credential 기반 Runtime 검증
- 실제 Area 데이터
- 실제 Spot Prototype 데이터
- 배포

## 12. 상태 Matrix

Area·Spot·Map·Geolocation·Future Data는 서로 독립된 상태군이다. 예를 들어
`MAP_UNAVAILABLE`과 `AREA_AVAILABLE`은 함께 성립할 수 있다.

| 상태군 | 상태 | 의미와 기본 표시 |
|---|---|---|
| Area | `AREA_UNSELECTED` | 담당 Area 선택 안내만 표시하고 Area 수치·Spot을 숨김 |
| Area | `AREA_LOADING` | 이전 Area 정보·Spot 선택을 지우고 Loading 표시 |
| Area | `AREA_AVAILABLE` | Area 공식정보와 Spot 3개를 이용할 수 있음 |
| Area | `DATA_UNAVAILABLE` | 공식 수치 없이 Area명·안전한 제한 안내와 가능한 정적 Spot 정보 표시 |
| Spot | `SPOT_UNSELECTED` | 상세·선택 강조 없음 |
| Spot | `SPOT_LIST_OPEN` | 후보 위치 3곳 목록 Drawer 또는 Bottom Sheet 표시 |
| Spot | `SPOT_DETAIL_OPEN` | 한 Spot의 상세 Drawer 또는 Bottom Sheet 표시 |
| Spot | `SPOT_SELECTED` | 선택 Marker·상태문구 표시, 다른 Spot으로 변경 가능 |
| Spot | `SPOT_PROTOTYPE_DATA_UNAVAILABLE` | 정적 Spot 정보와 데이터 없음·제한을 표시하고 값을 만들지 않음 |
| Map | `MAP_PLACEHOLDER` | Layout·Interaction 검토용 지도 Placeholder 표시 |
| Map | `MAP_LOADING` | 지도 Loading 표시, 텍스트 정보는 유지 |
| Map | `MAP_AVAILABLE` | 지도·Marker·Control을 이용할 수 있음 |
| Map | `MAP_UNAVAILABLE` | 지도 대신 목록 Fallback 제공 |
| Geolocation | `GEOLOCATION_IDLE` | 위치권한을 아직 요청하지 않음 |
| Geolocation | `GEOLOCATION_REQUESTING` | 사용자가 요청한 위치권한 응답을 기다림 |
| Geolocation | `GEOLOCATION_AVAILABLE` | 현재 위치와 직선거리를 표시 |
| Geolocation | `GEOLOCATION_DENIED` | 위치 없이 나머지 기능을 유지 |
| Geolocation | `GEOLOCATION_UNAVAILABLE` | 기기·브라우저에서 위치를 확인할 수 없음을 안내 |
| Future Data | `FRESH` | 해당 미래정보를 정상 표시 |
| Future Data | `DEGRADED` | 경고와 함께 해당 미래정보를 참고용으로 표시 |
| Future Data | `STALE_BLOCKED` | 해당 미래값을 표시하지 않음 |
| Future Data | `NO_COMPLETE_SNAPSHOT` | 표시 가능한 Current만 표시하고 미래값을 만들지 않음 |

## 13. Component 목록

| Component | 책임 |
|---|---|
| `AppHeader` | 제품명·공통 Header |
| `AreaSelector` | 승인 Area 직접 선택 |
| `MapCanvas` | 지도 Placeholder 또는 실제 지도 Container |
| `AreaInfoTrigger` | 구역 정보 열기 |
| `SpotListTrigger` | 후보 위치 3곳 목록 열기 |
| `CurrentLocationButton` | 사용자 동작으로 위치권한 요청 |
| `MapControl` | 지도 확대·축소와 범례 |
| `SpotMarker` | 기본 후보 위치 표시 |
| `OpenedSpotMarker` | 상세를 연 후보 위치 표시 |
| `SelectedSpotMarker` | 사용자가 선택한 후보 위치와 Check 표시 |
| `UserLocationMarker` | 승인된 현재 위치 표시 |
| `DesktopDrawer` | Desktop 단일 Slide-over Container |
| `MobileBottomSheet` | Mobile 공통 정보 Container |
| `AreaInfoContent` | Area 공식정보와 기준시각·출처·Freshness |
| `SpotList` | Spot 3개 목록 |
| `SpotListItem` | 클릭 가능한 후보 위치 Card |
| `SpotDetailContent` | Spot PM 수동 인구 Prototype 상세와 제한 |
| `PrototypeBadge` | Prototype·PM 직접 입력 출처 표시 |
| `LimitationNotice` | 확인되지 않은 운영·현장 한계 표시 |
| `SelectSpotButton` | 후보 위치 명시 선택 |
| `SelectionStatus` | 선택 완료와 변경 가능 안내 |
| `LoadingState` | Area·Map·위치 Loading 안내 |
| `EmptyState` | 선택 전 또는 제공값 없음 안내 |
| `ErrorState` | 안전한 오류와 다음 행동 안내 |
| `MapFallback` | 지도 실패 시 Area·Spot 목록 기반 이용 |

## 14. Stitch Prompt Recipe

각 Prompt는 독립 실행하되 §1~§13의 계약을 함께 제공한다. 생성 결과는 UI
검토자료이며 구현 완료나 실제 데이터 연결을 뜻하지 않는다.

### 14.1 프로젝트 기본 지도화면

- 역할: Senior Product Designer이자 UX Architect
- 맥락: 사용자가 승인된 Area를 직접 고른 뒤 Spot 3개를 비교하는 지도 중심
  Responsive Web
- 작업: Desktop의 Header, Area Dropdown, 데이터 기준시각, 도움말, 지도, Marker
  3개, `구역 정보`, `후보 위치 3곳`, `내 위치 표시`, Zoom과 범례를 설계
- 형식: Desktop 기본 지도 화면 1개와 Component 이름 주석
- 유지사항: 사용자 직접선택, 단일 Drawer 진입점, Area 공식정보와 Spot Prototype
  분리
- 금지사항: 고정 3열, 열린 Drawer, 자동추천, Best·최적, 실제 지도 정확성 주장
- 성공조건: 지도 위에서 Area와 세 후보 위치 및 다음 행동을 즉시 이해할 수 있음

### 14.2 구역 정보 Drawer

- 역할: Senior Product Designer이자 Data-heavy Decision Support UX Architect
- 맥락: 선택 Area의 서울시 공식 현재·1시간 후·3시간 후 정보를 필요할 때 확인
- 작업: 우측 단일 Drawer에 Area 수치, 혼잡도, 증감수·증감률, 관측·대상시각,
  출처·데이터 기준시각·Freshness를 설계
- 형식: Desktop 지도 + 구역 정보 Drawer 상태 1개
- 유지사항: Drawer Overlay, 서울시 공식 Area 데이터, 다른 Drawer 닫힘
- 금지사항: 프로토타입 Badge, 실시간·Live·Monitoring·자동 새로고침 표현
- 성공조건: Area 정보의 출처·기준시각과 각 시간범위를 혼동 없이 읽을 수 있음

### 14.3 후보 위치 목록 Drawer

- 역할: Senior Product Designer이자 Accessible Interaction Designer
- 맥락: 선택 Area의 동등한 사용자 선택지 3개를 비교
- 작업: 번호, 이름, 주소·위치설명, 가능한 직선거리, Prototype 이용 가능상태,
  Chevron을 가진 전체 클릭 Card 3개를 설계
- 형식: Desktop 지도 + 후보 위치 목록 Drawer 상태 1개
- 유지사항: 제목 `후보 위치 3곳`, 표시순서는 우열 의미가 없음, Marker와 목록 상태
  동기화
- 금지사항: HTML Select, 기본선택, 역세권·오피스 밀집·유동인구 많음·추천·Best·최적
- 성공조건: 사용자가 세 후보를 동등하게 훑고 Card 전체로 상세에 들어갈 수 있음

### 14.4 후보 위치 상세 Drawer

- 역할: Senior Product Designer이자 Field Operations SaaS UX Architect
- 맥락: 한 Spot의 PM 입력 Prototype 정보와 운영 한계를 확인한 뒤 명시적으로 선택
- 작업: 뒤로가기·닫기, 정체성, Badge, 데이터 기준시각, 현재·1시간 후·3시간 후
  예상 인구 범위, 증감수·증감률, 제한과 Sticky CTA를 설계
- 형식: Desktop 지도 + 후보 위치 상세 Drawer 상태 1개
- 유지사항: `프로토타입 데이터`, `PM 직접 입력`, 값 부재 시 `—`,
  `판촉 후보 위치로 선택`
- 금지사항: 공식 추천, 판매허용·안전·운영 적합성 확정
- 성공조건: Prototype 근거와 한계를 이해한 뒤 CTA로만 선택을 완료할 수 있음

### 14.5 선택 완료상태

- 역할: Senior Product Designer이자 UX Writer
- 맥락: 서버 저장 없이 Browser Memory에서 후보 위치 선택상태만 유지
- 작업: Selected Marker Check, Inline Status와 재선택 가능성을 설계
- 형식: Desktop 선택 완료 화면 1개
- 유지사항: 상세 Drawer 유지 가능, 정확한 선택 완료·변경 가능 문구
- 금지사항: 서버 저장·Campaign 등록·위치 확정·Lock·변경 불가 주장
- 성공조건: 현재 선택을 분명히 알면서 다른 후보로 바꿀 수 있음을 이해함

### 14.6 Mobile Bottom Sheet

- 역할: Senior Mobile Web Product Designer이자 Accessibility Specialist
- 맥락: Desktop과 같은 데이터·State·Component를 Mobile Container로 제공
- 작업: 지도 위 구역 정보·목록·상세·선택 상태의 단일 Bottom Sheet를 설계
- 형식: Mobile 화면 4개 상태와 Sheet 내부 Scroll·Sticky CTA 주석
- 유지사항: 추가 확인 Popup 없음, Focus 이동·복귀, 지도 Drag와 Sheet Scroll 분리,
  44×44px Touch Target
- 금지사항: Mobile 전용 데이터·기능, Tablet 전용 UI, Desktop과 다른 선택상태
- 성공조건: 한 손 조작, 키보드·보조기기와 지도 조작에서 핵심 흐름이 유지됨

### 14.7 부분 데이터

- 역할: Senior Product Designer이자 Data Quality UX Architect
- 맥락: 현재 또는 미래 Horizon 일부만 안전하게 표시할 수 있는 상태
- 작업: `FRESH`, `DEGRADED`, `STALE_BLOCKED`, `NO_COMPLETE_SNAPSHOT`별 표시·경고·
  숨김 상태를 설계
- 형식: Desktop Drawer와 Mobile Bottom Sheet의 부분 데이터 변형
- 유지사항: 각 미래 시점 독립 처리, 이용 가능한 Current 보존, 다음 행동 안내
- 금지사항: 다른 Horizon 복사·보간, 누락값 0·평균·추정 대체
- 성공조건: 사용자가 어떤 값이 있고 왜 없는지 이해하며 제공값만 신뢰할 수 있음

### 14.8 지도 실패

- 역할: Senior Product Designer이자 Resilient UX Architect
- 맥락: `MAP_UNAVAILABLE`이어도 Area·Spot 조회와 선택은 계속 가능
- 작업: 지도 대신 Area 정보, Spot 이름·주소 목록, 상세·선택과 지도 재시도를 설계
- 형식: Desktop과 Mobile `MapFallback` 상태
- 유지사항: 같은 Area·Spot 데이터와 선택상태, 안전한 오류문구
- 금지사항: 전체화면 차단, 추정 Marker·거리, 다른 Area 값 재사용
- 성공조건: 지도 없이도 후보 3개를 확인하고 한 곳을 선택할 수 있음

### 14.9 위치권한 거부

- 역할: Senior Product Designer이자 Privacy-aware Interaction Designer
- 맥락: 사용자가 위치권한을 거부해도 핵심기능은 정상 이용
- 작업: 거리만 숨기고 Area·Spot 정보, 지도·목록·상세·선택을 유지하는 상태를 설계
- 형식: Desktop과 Mobile `GEOLOCATION_DENIED` 상태
- 유지사항: `위치 없이도 이용할 수 있습니다`, 명시적 재요청만 허용
- 금지사항: 접속 즉시 권한요청, 반복 Prompt, 거부를 오류로 취급, 위치 저장 주장
- 성공조건: 사용자가 거부 결과와 계속 가능한 기능을 즉시 이해함

### 14.10 Prototype 데이터 없음

- 역할: Senior Product Designer이자 Trust-centered UX Architect
- 맥락: Spot 정체성은 있으나 PM 입력 Prototype 수치가 없음
- 작업: Spot명·주소·유형과 데이터 없음·한계를 유지하고 인구정보 표의 값을 `—`로
  표시하는 상세 상태를 설계
- 형식: `SPOT_PROTOTYPE_DATA_UNAVAILABLE` Drawer·Bottom Sheet
- 유지사항: 정적 Spot 선택 가능, 다른 Spot 확인과 데이터 갱신 안내
- 금지사항: Area 값 복사, 0·평균·추정값, 공식 데이터 Badge
- 성공조건: 값 부재를 오해하지 않고 정적 후보 선택을 계속할 수 있음

### 14.11 Theme

- 역할: Senior Product Designer이자 Design System Designer
- 맥락: 지도와 정보 Drawer를 장시간 읽는 현장업무용 Responsive Web
- 작업: 명확한 정보계층, 지도 위 가독성, Default·Opened·Selected Marker 구분과
  상태색·Typography·Spacing 방향을 제안
- 형식: Theme 방향 1개와 최소 Design Token 후보표
- 유지사항: 색상 외 형태·문구로 상태 구분, Component 재사용성, 높은 대비
- 금지사항: Brand Color 확정, 실제 Marker 형태 확정, 장식이 데이터 의미를 압도
- 성공조건: `OPEN DECISION · PM 확인 필요` 항목을 확정하지 않고 일관된 검토안 제공

### 14.12 Korean UX Writing

- 역할: 한국어 UX Writer이자 Field Operations Product Designer
- 맥락: 비개발자 사용자가 데이터 시점·출처·Prototype 한계를 쉽게 이해
- 작업: 버튼, 상태, 빈 화면, 오류, 제한사항과 선택 완료 문구를 쉬운 한국어로 검토
- 형식: 현행 문구·권장 수정·금지 표현 표
- 유지사항: 데이터 기준시각, 저장된 최신 승인 데이터 기준, 후보 위치, 변경 가능
- 금지사항: 실시간·Live·Monitoring·추천·최적·Best·판매 보장·확정 저장
- 성공조건: 운영사실·추천·저장 여부를 과장하지 않고 다음 행동이 명확함

### 14.13 Accessibility Review

- 역할: WCAG 관점의 Accessibility Specialist이자 UX Architect
- 맥락: 지도, Drawer, Bottom Sheet, Marker와 목록이 같은 과업을 제공
- 작업: 키보드 순서, Focus 이동·복귀, 이름·역할·상태, 대비, Touch Target,
  지도 없는 대체 흐름을 검토
- 형식: Component별 PASS·ISSUE·권장 최소 수정 Checklist
- 유지사항: Marker와 목록의 동등한 진입, 44×44px, 색상 외 상태표시, Error 안내
- 금지사항: 지도만으로 정보 전달, Focus 손실, 키보드 Trap, 색상만으로 선택 표시
- 성공조건: 지도·위치 기능 없이도 핵심 과업을 키보드와 보조기기로 완료할 수 있음
