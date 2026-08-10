# hy 본사 기본 지도 설계

- 상태: `PM_APPROVED_DESIGN`
- Issue: `#156`
- 확정일: `2026-08-10`

## 1. 목적

서비스 첫 진입 시 전체 화면을 덮는 빈 안내 화면 대신 hy빌딩을 중심으로 NAVER 지도를
즉시 표시한다. 로그인·담당 구역 추론·사용자 위치 요청 없이 서비스의 지도 중심 성격을
먼저 보여주되, 담당 Area와 판매 위치는 사용자가 직접 선택하는 기존 계약을 유지한다.

## 2. 현재 문제

제품 계약은 `서비스 접속 → hy 본사 중심 지도 → 담당 Area 직접 선택` 순서를 정의한다.
현재 구현은 Area를 선택하기 전에는 지도를 생성하지 않고 불투명한 빈 상태 화면을
표시한다. 그 결과 첫 화면 대부분이 비어 보여 서비스가 준비되지 않았거나 로딩 중인
것처럼 보인다.

## 3. PM 확정값

| 항목 | 확정값 |
|---|---|
| 기본 위치명 | `hy빌딩` |
| 기본 주소 | `서울특별시 서초구 강남대로 577 (잠원동, hy빌딩)` |
| 위도 | `37.51325` |
| 경도 | `127.01982` |
| 기본 Zoom | `16` |
| 지도 표기 | `hy 기준 위치` 중립 Marker |
| 좌표 상태 | `PM_CONFIRMED` |

이 좌표는 모든 방문자에게 동일하게 적용하는 지도 시작점이다. 담당 Area, 사용자 현재
위치, 판매 위치 또는 추천 결과를 뜻하지 않는다.

## 4. 첫 진입 화면

1. 화면이 열리면 Area 목록과 NAVER 지도를 각각 준비한다.
2. 지도는 PM 확정 좌표와 Zoom `16`으로 열린다.
3. `hy 기준 위치` Marker 하나만 표시한다.
4. Area Dropdown은 `담당 구역을 선택해 주세요` 상태를 유지한다.
5. Area 수치, Spot Marker·Zone·목록·상세는 표시하지 않고 Header의 데이터 기준시각
   값은 `—`로 유지한다.
6. 기존 중앙 빈 상태 안내는 지도가 정상 표시된 동안 화면을 덮지 않는다.

중립 Marker는 번호, 판매 위치 색상 Zone, 선택 Check 또는 `내 위치` 색상을 사용하지
않는다. SDK `title`은 `hy 기준 위치`로 고정하고 클릭 동작과 선택 상태는 제공하지
않는다. Area 미선택 상태의 지도 영역은 `hy 기준 위치 지도와 담당 구역 선택`이라는
접근 가능한 이름을 사용하며, 중립 Marker를 판매 위치 범례에 포함하지 않는다.

## 5. Area 선택과 해제

- 사용자가 Area를 선택하면 기본 지도를 정리하고 기존 Pilot View를 불러온다.
- 기존과 같이 해당 Area의 Spot 3개가 모두 보이도록 `fitBounds`를 적용한다.
- 사용자가 Area 선택을 해제하면 Spot·Panel·사용자 위치 상태를 초기화하고 hy 기본
  중심 지도와 중립 Marker로 돌아간다.
- Area와 Spot의 기존 식별자·Fixture·직접 선택 계약은 변경하지 않는다.

## 6. 구현 경계

기존 `createNaverMap` 흐름을 재사용한다. 이 함수는 다음 두 입력만 허용한다.

- Spot이 있는 Area 지도: 기존 Spot Marker·선택·Zone·`fitBounds` 동작
- Spot이 없는 기본 지도: 명시된 중심 좌표·Zoom·중립 Marker만 사용

Spot도 없고 기본 중심도 없으면 기존처럼 Fail-closed 처리한다. 별도 지도 라이브러리,
상태 저장소, Router 또는 신규 Dependency는 추가하지 않는다.

## 7. 실패와 대체 화면

NAVER Client ID가 없거나 Script·지도 Container 초기화가 실패하면 지도 상태를
`unavailable`로 둔다. 이 경우 기존 중립 안내 화면을 표시하되 Area Dropdown과 Area
선택 흐름은 계속 사용할 수 있어야 한다. 자동 재시도, 위치권한 요청과 임의의 가짜
지도 이미지는 추가하지 않는다.

Area 선택 뒤 지도만 실패하면 기존 `지도 없이 목록 이용`과 수동 재시도 동작을
그대로 유지한다.

## 8. 외부 요청·개인정보

- 첫 진입 시 NAVER 지도 Script와 지도 Tile 요청 시점이 Area 선택 전으로 앞당겨진다.
- 현재 Fixture Production은 기존처럼 Backend 요청 `0`을 유지한다. Official 모드의
  기존 Area 목록 요청은 변경하지 않으며 새 Backend Endpoint·요청을 추가하지 않는다.
- 서울시 API, Collector, Backup, Recommendation과 ML은 실행하지 않는다.
- Browser Geolocation을 자동 요청하지 않는다.
- FreshManager 애플리케이션은 Cookie, Session, `localStorage`, `sessionStorage`, 파일과
  Database에 위치나 선택을 저장하지 않는다. NAVER Provider 측 요청 처리는 이 저장소의
  제어·검증 범위가 아니다.
- 기존 NAVER Client ID 환경변수와 허용 Domain 설정만 재사용하며 실제 값은 코드와
  문서에 기록하지 않는다.

## 9. 변경 예상 파일

| 파일 | 책임 |
|---|---|
| `apps/web/src/App.vue` | 첫 진입·Area 해제 시 기본 지도 초기화와 빈 화면 조건 조정 |
| `apps/web/src/naver-map.ts` | 명시 중심·Zoom·중립 Marker가 있는 Spot 없는 지도 지원 |
| `apps/web/src/prototype/prototype-fixtures.test.mjs` | 기본 지도와 기존 Area 지도 회귀시험 |
| `docs/product/AREA_FIRST_WEB_PILOT_CONTRACT.md` | PM 확정 위치·좌표·Zoom·Marker 기록 |
| `ai-context/DECISION_LOG.md` | 기본 지도 PM 결정 기록 |
| `PROJECT_STATUS.md` | Issue·PR·검증·배포 상태 동기화 |

CSS 변경은 기존 조건부 화면 구성만으로 목표를 달성할 수 없을 때만
`apps/web/src/styles.css` 한 파일에 제한한다.

## 10. 검증

자동검증은 다음을 확인한다.

- Spot `0`개와 PM 확정 중심·Zoom으로 지도가 생성된다.
- Map 생성 입력은 위도 `37.51325`, 경도 `127.01982`, Zoom `16`이다.
- 기본 지도에는 중립 Marker `1`개, Spot Marker·Zone·`fitBounds`는 `0`개다.
- 중심이 없는 빈 Spot 입력은 실패한다.
- 기본 지도 Controller를 정리하면 중립 Marker도 `setMap(null)`로 제거된다.
- Area 지도는 기존 Spot Marker `3`개와 `fitBounds` 동작을 유지한다.
- Area 미선택 상태에서 서울시 API·Geolocation·Storage 요청은 `0`이다.
- 지도 실패가 Area 선택을 차단하지 않는다.
- Web Target Tests, Type Check, Fixture Build, 전체 Unit Tests, Project Guard,
  `git diff --check`와 Exact-head CI를 통과한다.

기존 Node 시험은 Map Adapter의 중심·Zoom·Marker·정리와 Area 지도 회귀를 검증한다.
신규 Test Framework는 추가하지 않는다. App 최초 초기화, Area 선택 해제 후 복귀와
빈 안내의 비차단 동작은 Desktop·Mobile 브라우저 검증으로 확인한다. 브라우저 검증은
Area 선택 전 Spot 부재, Area 선택 후 Spot 3개, 가로 Overflow와 Console Error도 함께
확인한다.

## 11. 제외 범위

- 로그인·사용자 계정·담당 Area 추론
- 마지막 선택 Area 저장 또는 자동 복원
- hy빌딩을 담당 Area·판매 위치·추천으로 처리
- 사용자 현재 위치 자동 요청
- Backend·API·Dataset·Fixture 값·ML·Dependency 변경
- 실제 서울시 API·Collector·Backup 실행
- 별도 PM 승인 없는 `main` Merge와 Production 배포

## 12. 완료와 Release 순서

구현 Branch는 Issue #156 범위만 포함한다. 검증이 끝나면 Draft Pull Request와 Exact-head
CI 근거를 제공한다. PM의 별도 Merge 승인 후에만 `main`에 반영하고, Production 배포도
별도 승인과 exact `main` 검증 뒤 수행한다.
