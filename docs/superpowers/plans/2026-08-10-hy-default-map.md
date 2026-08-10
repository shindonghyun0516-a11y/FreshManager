# hy 본사 기본 지도 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Area를 선택하지 않은 첫 진입 화면에 hy빌딩 중심 NAVER 지도와 중립 Marker를 표시한다.

**Architecture:** 기존 `createNaverMap` Adapter가 Spot 지도와 기본 중심 지도를 모두 처리하도록 최소 확장한다. `App.vue`는 같은 Adapter를 첫 mount와 Area 선택 해제 때 호출하며, 기존 Area 선택·Spot 3개·`fitBounds` 흐름은 그대로 유지한다.

**Tech Stack:** Vue 3.5, TypeScript 6, Vite 8, NAVER Maps JavaScript API, Node built-in test runner, Python 3.12 Project Guard

## Global Constraints

- Issue `#156`과 승인 설계 `docs/superpowers/specs/2026-08-10-hy-default-map-design.md`만 구현한다.
- 기본 위치는 `서울특별시 서초구 강남대로 577 (잠원동, hy빌딩)`, 위도 `37.51325`, 경도 `127.01982`, Zoom `16`이다.
- 중립 Marker 이름은 `hy 기준 위치`이며 담당 Area·내 위치·판매 위치·추천을 뜻하지 않는다.
- Area Dropdown은 미선택 상태로 시작하고 로그인·위치권한·Browser 저장을 추가하지 않는다.
- Fixture Production의 Backend 요청은 `0`을 유지하고 새 API·Dependency·Dataset·Fixture 값은 추가하지 않는다.
- 실제 서울시 API·Collector·Backup·Recommendation·ML은 실행하지 않는다.
- `main` Merge와 Production 배포는 이 계획의 자동 실행 범위가 아니다.
- 이 계획 문서는 구현 시작 전에 별도 Commit으로 보존한다.

---

### Task 1: Spot 없는 기본 지도를 Map Adapter에 추가

**Files:**
- Modify: `apps/web/src/naver-map.ts:9-219`
- Test: `apps/web/src/prototype/prototype-fixtures.test.mjs:349-442`

**Interfaces:**
- Consumes: 기존 `MapPoint`, `MapSpot`, `createNaverMap(...)` 호출 계약
- Produces: `MapInitialLocation`, 확장된 `createNaverMap(..., initialLocation?)`, 정리 가능한 중립 Marker

- [ ] **Step 1: 기본 지도 실패 시험을 먼저 작성**

기존 NAVER Map 시험의 Fake 객체가 Map 옵션, `fitBounds`, Marker 옵션과 Marker 정리를 기록하게 한다.

```js
const mapOptions = [];
const markerOptions = [];
let fitBoundsCount = 0;
let markerDetachCount = 0;
let listenerCount = 0;

class FakeMap {
  constructor(element, options) {
    mapOptions.push(options);
    element.style.position = "relative";
    if (element.collapseOnCreate) element.height = 0;
  }
  fitBounds() { fitBoundsCount += 1; }
  destroy() { mapDestroyed += 1; }
}

class FakeMarker {
  constructor(options) {
    markerCount += 1;
    markerOptions.push(options);
  }
  setIcon() {}
  setMap(map) { if (map === null) markerDetachCount += 1; }
  setZIndex() {}
}
```

Fake NAVER Event도 Spot 클릭 Listener 수를 기록한다.

```js
Event: {
  addListener: () => {
    listenerCount += 1;
    return {};
  },
  removeListener() {},
},
```

기존 Area 지도 assertion 뒤에 기본 중심 계약을 추가한다.

```js
const fitBoundsBeforeDefault = fitBoundsCount;
const markerCountBeforeDefault = markerCount;
const detachCountBeforeDefault = markerDetachCount;
const zoneCountBeforeDefault = zoneOptions.length;
const listenerCountBeforeDefault = listenerCount;
const defaultController = await naverMap.createNaverMap(
  element(800, 600),
  "client",
  [],
  () => {},
  false,
  {
    latitude: 37.51325,
    longitude: 127.01982,
    zoom: 16,
    title: "hy 기준 위치",
  },
);

assert.equal(mapOptions.at(-1).center.latitude, 37.51325);
assert.equal(mapOptions.at(-1).center.longitude, 127.01982);
assert.equal(mapOptions.at(-1).zoom, 16);
assert.equal(markerCount, markerCountBeforeDefault + 1);
assert.equal(markerOptions.at(-1).title, "hy 기준 위치");
assert.equal(markerOptions.at(-1).position.latitude, 37.51325);
assert.equal(markerOptions.at(-1).position.longitude, 127.01982);
assert.match(markerOptions.at(-1).icon.content, /hy 기준 위치/);
assert.equal(markerOptions.at(-1).clickable, false);
assert.equal(fitBoundsCount, fitBoundsBeforeDefault);
assert.equal(zoneOptions.length, zoneCountBeforeDefault);
assert.equal(listenerCount, listenerCountBeforeDefault);
defaultController.destroy();
assert.equal(markerDetachCount, detachCountBeforeDefault + 1);

await assert.rejects(
  naverMap.createNaverMap(element(800, 600), "client", [], () => {}),
  /NAVER_MAP_UNAVAILABLE/,
);
```

- [ ] **Step 2: 시험이 현재 구현에서 실패하는지 확인**

Run:

```bash
cd apps/web
npm ci
npm test
```

Expected: `createNaverMap`이 Spot `0`개 입력을 거부하거나 새 인자를 지원하지 않아 NAVER Map 시험이 FAIL한다.

- [ ] **Step 3: Adapter를 최소 확장**

`apps/web/src/naver-map.ts`에 기본 중심 타입을 추가한다.

```ts
export type MapInitialLocation = MapPoint & {
  zoom: number;
  title: string;
};
```

기존 Marker와 구분되는 중립 Label을 같은 파일의 inline icon 패턴으로 만든다.

```ts
function initialLocationMarkerContent() {
  return {
    content:
      '<span aria-hidden="true" style="display:flex;align-items:center;gap:6px;padding:8px 10px;border:1px solid #008577;border-radius:999px;background:#fff;color:#006b5e;font:700 13px/1 system-ui,sans-serif;box-shadow:0 4px 14px rgba(21,47,41,.10)"><span style="display:block;width:8px;height:8px;border-radius:50%;background:#008577"></span>hy 기준 위치</span>',
  };
}
```

`createNaverMap` 마지막 인자를 추가하고 Spot이 없을 때만 기본 중심을 사용한다.

```ts
export async function createNaverMap(
  element: HTMLElement,
  clientId: string,
  spots: MapSpot[],
  onSpotClick: (spotId: string) => void,
  showPrototypeZones = false,
  initialLocation?: MapInitialLocation,
) {
  const defaultLocation = spots.length === 0 ? initialLocation : undefined;
  const centerPoint = spots[0] ?? defaultLocation;
  if (!clientId || !centerPoint) throw new Error("NAVER_MAP_UNAVAILABLE");

  assertMapContainerAvailable(element);
  const maps = await loadMaps(clientId);
  assertMapContainerAvailable(element);
  const center = new maps.LatLng(centerPoint.latitude, centerPoint.longitude);
  const map = new maps.Map(element, {
    center,
    zoom: defaultLocation?.zoom ?? 14,
    minZoom: 10,
    zoomControl: true,
  });
```

Spot loop 앞에서 기본 Marker를 만들고, Spot이 있을 때만 `fitBounds`를 호출한다.

```ts
const initialLocationMarker = defaultLocation
  ? new maps.Marker({
      map,
      position: center,
      title: defaultLocation.title,
      clickable: false,
      zIndex: 5,
      icon: {
        ...initialLocationMarkerContent(),
        anchor: new maps.Point(54, 18),
      },
    })
  : undefined;

for (const spot of spots) {
  const position = new maps.LatLng(spot.latitude, spot.longitude);
  bounds.extend(position);
  if (showPrototypeZones) {
    const color = PROTOTYPE_ZONE_COLORS[zones.length % PROTOTYPE_ZONE_COLORS.length];
    zones.push(new maps.Circle({
      map,
      center: position,
      radius: PROTOTYPE_ZONE_RADIUS_METERS,
      strokeColor: color,
      strokeOpacity: 0.9,
      strokeWeight: 2,
      fillColor: color,
      fillOpacity: 0.14,
      clickable: false,
      zIndex: 1,
    }));
  }
  const marker = new maps.Marker({
    map,
    position,
    title: spot.name,
    zIndex: 10,
    icon: {
      ...markerContent(spot.displayOrder, "default"),
      anchor: new maps.Point(22, 44),
    },
  });
  listeners.push(
    maps.Event.addListener(marker, "click", () => onSpotClick(spot.id)),
  );
  markers.set(spot.id, { marker, order: spot.displayOrder });
}

if (spots.length > 0) {
  map.fitBounds(bounds, { top: 80, right: 80, bottom: 100, left: 80 });
}
```

Controller 정리에 중립 Marker를 포함한다.

```ts
destroy() {
  listeners.forEach((listener) => maps.Event.removeListener(listener));
  initialLocationMarker?.setMap(null);
  userMarker?.setMap(null);
  markers.forEach(({ marker }) => marker.setMap(null));
  zones.forEach((zone) => zone.setMap(null));
  map.destroy();
}
```

- [ ] **Step 4: Adapter 시험 통과 확인**

Run:

```bash
cd apps/web
npm test
```

Expected: 기존 17개 Web 시험이 모두 PASS하고 Area Marker `3`, Zone `3`, 기본 Marker `1`, 기본 지도 `fitBounds` `0` 계약이 확인된다.

- [ ] **Step 5: Task 1 Commit**

```bash
git add apps/web/src/naver-map.ts apps/web/src/prototype/prototype-fixtures.test.mjs
git commit -m "feat: support hy default map origin (#156)"
```

---

### Task 2: 첫 mount와 Area 선택 해제를 기본 지도에 연결

**Files:**
- Modify: `apps/web/src/App.vue:48-80,261-368,443-446,537-554`
- Test: `apps/web/src/prototype/prototype-fixtures.test.mjs:264-273`

**Interfaces:**
- Consumes: Task 1의 `MapInitialLocation`과 확장된 `createNaverMap`
- Produces: 첫 진입·Area 해제 기본 지도, 동적 지도 접근성 Label, 비차단 Empty State

- [ ] **Step 1: App wiring 실패 시험을 먼저 작성**

기존 App Source 계약 시험 다음에 아래 시험을 추가한다.

```js
test("initial screen opens the approved hy default map without selecting an Area", () => {
  const app = readFileSync(resolve(process.cwd(), "src/App.vue"), "utf8");
  const emptyAreaBranch = app.match(
    /if \(!selectedAreaCode\.value\) \{([\s\S]*?)\n\s*\}/,
  )?.[1] ?? "";

  assert.match(app, /latitude:\s*37\.51325/);
  assert.match(app, /longitude:\s*127\.01982/);
  assert.match(app, /zoom:\s*16/);
  assert.match(app, /title:\s*"hy 기준 위치"/);
  assert.match(app, /onMounted\(\(\) => \{[\s\S]*void setupMap\(\)/);
  assert.match(emptyAreaBranch, /viewState\.value = "idle"/);
  assert.match(emptyAreaBranch, /await setupMap\(\)/);
  assert.match(app, /viewState === 'idle' && mapState !== 'available'/);
  assert.match(app, /hy 기준 위치 지도와 담당 구역 선택/);
});
```

- [ ] **Step 2: 시험이 현재 App에서 실패하는지 확인**

Run:

```bash
cd apps/web
npm test
```

Expected: 승인 좌표 상수와 첫 mount `setupMap()` 호출이 없어 새 시험 1개가 FAIL한다.

- [ ] **Step 3: App에 승인 상수와 기본 지도 흐름 추가**

`fixtureMode` 아래에 공개 회사 기준 위치만 코드 상수로 둔다.

```ts
const HY_DEFAULT_MAP_LOCATION = {
  latitude: 37.51325,
  longitude: 127.01982,
  zoom: 16,
  title: "hy 기준 위치",
} as const;
```

Area 선택 해제 경로가 기본 지도를 다시 만든다.

```ts
if (!selectedAreaCode.value) {
  viewState.value = "idle";
  await setupMap();
  return;
}
```

`setupMap`은 `pilotView`가 없어도 Map Canvas가 있으면 실행한다.

```ts
async function setupMap() {
  destroyMap();
  const view = pilotView.value;
  const element = mapCanvas.value;
  if (!element) return;

  const generation = mapGeneration;
  mapState.value = "loading";
  try {
    const controller = await createNaverMap(
      element,
      import.meta.env.VITE_NAVER_MAP_CLIENT_ID ?? "",
      view?.spot_options.map((spot) => ({
        id: spot.spot_option_id,
        name: spot.spot_name,
        latitude: spot.latitude,
        longitude: spot.longitude,
        displayOrder: spot.display_order,
      })) ?? [],
      (spotId) => openSpot(spotId),
      fixtureMode && Boolean(view),
      view ? undefined : HY_DEFAULT_MAP_LOCATION,
    );
```

첫 mount에서 Area 목록과 기본 지도를 각각 준비한다.

```ts
onMounted(() => {
  void loadAreas();
  void setupMap();
  document.addEventListener("keydown", handleDocumentKeydown);
});
```

Map section과 Empty State 조건을 승인 의미로 좁힌다.

```vue
<section
  class="map-shell"
  :data-map-state="mapState"
  :data-panel-open="panel !== 'none'"
  :aria-label="selectedAreaCode ? '판매 위치 지도와 정보' : 'hy 기준 위치 지도와 담당 구역 선택'"
>
  <div ref="mapCanvas" class="map-canvas" :aria-hidden="mapState !== 'available'"></div>

  <div
    v-if="viewState === 'idle' && mapState !== 'available'"
    class="map-fallback map-empty"
  >
```

- [ ] **Step 4: Web 시험·Type Check·Build 통과 확인**

Run:

```bash
cd apps/web
npm test
npm run typecheck
VITE_FRESHMANAGER_DATA_MODE=fixture npm run build
```

Expected: Web 시험 `18/18` PASS, TypeScript PASS, Vite Fixture Build PASS.

- [ ] **Step 5: Task 2 Commit**

```bash
git add apps/web/src/App.vue apps/web/src/prototype/prototype-fixtures.test.mjs
git commit -m "feat: show hy map on first entry (#156)"
```

---

### Task 3: 정본 계약과 현재 상태 동기화

**Files:**
- Modify: `docs/product/AREA_FIRST_WEB_PILOT_CONTRACT.md:1-18,151-184,402-456`
- Modify: `ai-context/DECISION_LOG.md:388-440`
- Modify: `PROJECT_STATUS.md:38-74,515-536`

**Interfaces:**
- Consumes: Issue #156 PM 확정값과 Task 1~2 실제 구현 상태
- Produces: 좌표 상태 `PM_CONFIRMED`, Decision `D-025`, Issue #156 현재 상태

- [ ] **Step 1: 제품 계약 Header·두 미확정 좌표 Block·변경 이력을 확정 상태로 교체**

문서 버전은 `v0.6.0`, 최종 수정일은 `2026-08-10`으로 올리고 관련 결정에 `D-025`,
관련 작업에 `Issue #156`을 추가한다. 변경 이력 맨 위에는 다음 행을 추가한다.

```markdown
| v0.6.0 | 2026-08-10 | 첫 진입 hy빌딩 중심 좌표·Zoom 16·중립 Marker와 Area 미선택 계약 확정 | Issue #156 PM 변경 승인 |
```

`docs/product/AREA_FIRST_WEB_PILOT_CONTRACT.md`의 Section 5와 Section 16에 중복된
`PM_CONFIRMATION_REQUIRED` Block을 모두 아래 동일한 확정값으로 교체한다.

```text
default_location_name=hy빌딩
default_address=서울특별시 서초구 강남대로 577 (잠원동, hy빌딩)
default_latitude=37.51325
default_longitude=127.01982
default_zoom=16
default_marker_label=hy 기준 위치
coordinate_status=PM_CONFIRMED
```

바로 다음 문단을 정확히 추가한다.

```markdown
`hy 기준 위치` Marker는 모든 방문자에게 동일한 지도 시작점을 알리는 중립 표기다.
담당 Area, 사용자 현재 위치, 판매 위치 또는 추천 결과로 사용하지 않는다. Area 미선택
상태에서는 Area 수치, Spot Marker·Zone·목록·상세를 숨기고, Area를 선택하면 기존
Spot 3개 `fitBounds` 지도로 전환한다.
```

Section 15의 기존 본문과 `실제 NAVER Map Credential 사용`, `Database와 배포`를
포함한 과거 Bullet 전체를 아래 현재 사실로 교체하고, 완료 정의의 과거 Release
문구도 같은 상태로 맞춘다.

```markdown
Issue #154·PR #155의 Area-first Web은 `main`에 병합됐고 Frontend-only Fixture
Production이 활성화됐다. 실제 Area API·운영 데이터 Production 연결은 완료되지 않았다.
Issue #156은 첫 진입 기본 지도 계약만 정렬하며 실제 데이터 연결 범위를 확대하지 않는다.

현재 구현은 다음을 승인하거나 수행하지 않는다.

- 실제 Area API·운영 데이터 연결
- Spot 인구 Prototype 실데이터 입력
- Database
- 실제 API·Recommendation·ML·S-DoT 실행
- 로그인과 사용자 파일럿
```

Section 16 제목은 `PM 확인 완료 및 후속 항목`으로 바꾸고, 위 확정값 뒤에는 기존
`Area별 접근권한과 제한배포 방식은 후속 결정` 문장만 유지한다.

- [ ] **Step 2: Decision Log에 D-025 추가**

`D-022`의 `PM_CONFIRMATION_REQUIRED` 문구는 `RESOLVED_BY_D-025`로 바꾸고 다음 결정을 `D-024` 뒤에 추가한다.

```markdown
### D-025 — hy 본사 기본 지도 좌표·Zoom·중립 Marker 확정

- Date: `2026-08-10`
- Status: `ACCEPTED`
- Relationship: D-022의 `서비스 접속 → hy 본사 중심 지도 → 담당 Area 직접 선택` 계약과 D-023의 지도 중심 기본화면을 구현값으로 확정한다.
- Default map: `hy빌딩`, `서울특별시 서초구 강남대로 577 (잠원동, hy빌딩)`, latitude `37.51325`, longitude `127.01982`, zoom `16`.
- Marker: `hy 기준 위치` 중립 Marker 하나만 표시하며 담당 Area·내 위치·판매 위치·추천으로 사용하지 않는다.
- Interaction: Area Dropdown은 미선택 상태를 유지하고 Area 선택 전 Area 수치·Spot Marker·Zone·목록·상세를 숨긴다. Area 선택 시 기존 Spot 3개 `fitBounds`로 전환하고 선택 해제 시 기본 지도로 복귀한다.
- Privacy: 로그인·위치권한 자동요청·Browser 저장·새 Backend 요청을 추가하지 않는다.
- Scope boundary: Backend·API·Dataset·Fixture 값·ML·Dependency·실제 서울시 API·Collector·Backup은 변경하거나 실행하지 않는다. `main` Merge와 Production 배포는 별도 PM 승인사항이다.
- Evidence: Issue #156, `docs/superpowers/specs/2026-08-10-hy-default-map-design.md`.
```

- [ ] **Step 3: PROJECT_STATUS를 현재 Git·Release 사실과 Issue #156 상태로 갱신**

`PROJECT_STATUS.md`의 마지막 동기화 시각을 `2026-08-10`으로 갱신한다. 다음 상태를
한 번만 기록하고 과거 PR #155 pre-merge 문구를 현재 상태로 사용하지 않는다.

```text
Issue #156: IMPLEMENTED_PENDING_PR_VALIDATION
Branch: feat/issue-156-default-hy-map
Base: main @ f71d397deb580003c05cd0ddb14a5995b42fc095
Default map: hy빌딩 / 37.51325 / 127.01982 / zoom 16 / hy 기준 위치
API·Collector·Backup·ML execution: 0
main Merge: NOT_APPROVED
Production deploy: NOT_APPROVED
```

다음 행동은 `Targeted Tests → Full Tests·Project Guard → Draft PR → Exact-head CI → PM Merge 결정`으로 기록한다.

- [ ] **Step 4: 문서·Guard 검증**

Run:

```bash
python3 scripts/project_guard_check.py
git diff --check HEAD
if rg -n "PM_CONFIRMATION_REQUIRED|default_zoom=NOT_PROVIDED" \
    docs/product/AREA_FIRST_WEB_PILOT_CONTRACT.md \
    ai-context/DECISION_LOG.md \
    PROJECT_STATUS.md; then
  exit 1
fi
```

Expected: Project Guard `PASS=43 FAIL=0 WARN=0 SKIP=4`, `git diff --check` PASS, 오래된 기본 좌표 미확정 표현 검색 결과 `0`.

- [ ] **Step 5: Task 3 Commit**

```bash
git add docs/product/AREA_FIRST_WEB_PILOT_CONTRACT.md ai-context/DECISION_LOG.md PROJECT_STATUS.md
git commit -m "docs: confirm hy default map contract (#156)"
```

---

### Task 4: 전체 검증·Push·Draft Pull Request

**Files:**
- Verify only: all Issue #156 changed files
- External record: GitHub Issue #156 and Draft Pull Request

**Interfaces:**
- Consumes: Task 1~3 Commit과 exact `origin/main`
- Produces: 검증된 Branch HEAD, Draft PR, CI 검토 대상

- [ ] **Step 1: 고정 Dependency로 검증 환경 준비**

신규 Dependency를 추가하지 않고 저장소 밖 임시 경로에 저장소의 기존 Pin만 설치한다.
아래 Step 1~2는 같은 Shell Session에서 실행한다.

```bash
FM_ISSUE156_VENV_DIR=$(mktemp -d "${TMPDIR:-/tmp}/freshmanager-issue156-venv.XXXXXX")
export FM_ISSUE156_VENV_DIR
trap 'case "$FM_ISSUE156_VENV_DIR" in "${TMPDIR:-/tmp}"/freshmanager-issue156-venv.*) rm -rf -- "$FM_ISSUE156_VENV_DIR" ;; esac' EXIT
python3.12 -m venv "${FM_ISSUE156_VENV_DIR}/venv"
"${FM_ISSUE156_VENV_DIR}/venv/bin/python" -m pip install \
  -r requirements.txt -r requirements-ml.txt
cd apps/web
npm ci
cd ../..
```

- [ ] **Step 2: 전체 로컬 검증**

```bash
cd apps/web
npm test
npm run typecheck
VITE_FRESHMANAGER_DATA_MODE=fixture npm run build
cd ../..
"${FM_ISSUE156_VENV_DIR}/venv/bin/python" -m unittest discover -s tests -q
"${FM_ISSUE156_VENV_DIR}/venv/bin/python" scripts/project_guard_check.py
git diff --check origin/main...HEAD
git status --short
```

Expected: Web `18/18`, TypeScript PASS, Vite Build PASS, Python `800/800`, Guard `43 PASS / 0 FAIL / 0 WARN / 4 SKIP`, diff-check PASS, Working Tree CLEAN.

- [ ] **Step 3: 범위·보안 감사**

```bash
git fetch origin main
test "$(git rev-parse origin/main)" = "f71d397deb580003c05cd0ddb14a5995b42fc095"
test "$(git merge-base HEAD origin/main)" = "f71d397deb580003c05cd0ddb14a5995b42fc095"
git diff --name-status origin/main...HEAD
git diff --stat origin/main...HEAD
git diff --check origin/main...HEAD
git log --oneline origin/main..HEAD
git status --short --branch
```

Expected: Issue #156 코드·시험·정본 문서·설계·계획 파일만 변경, Dependency·Backend·Dataset·Fixture 값·Workflow 변경 `0`, 사용자 원본 Worktree 영향 `0`.
`origin/main`이 예상 SHA와 달라졌으면 Push하지 않고 변경된 Base에 맞춰 범위와 검증을 다시 확인한다.

- [ ] **Step 4: Branch Push와 Draft PR 생성**

```bash
git push -u origin feat/issue-156-default-hy-map
head_sha=$(git rev-parse HEAD)
gh pr create \
  --draft \
  --base main \
  --head feat/issue-156-default-hy-map \
  --title "feat: 첫 진입 hy 본사 중심 지도 표시" \
  --body "## 요약

- 첫 진입 hy빌딩 중심 지도와 hy 기준 위치 중립 Marker
- 위도 37.51325, 경도 127.01982, Zoom 16
- Area 자동 선택·Geolocation·Browser 저장·새 Backend 요청 없음

## 검증

- Head: ${head_sha}
- Web Tests: 18/18 PASS
- TypeScript·Fixture Build: PASS
- Python Tests: 800/800 PASS
- Project Guard: 43 PASS / 0 FAIL / 0 WARN / 4 SKIP
- API·Collector·Backup·Recommendation·ML 실행: 0
- Preview: NOT_DEPLOYED
- main Merge: NOT_APPROVED
- Production 배포: NOT_APPROVED

Closes #156"
```

- [ ] **Step 5: Exact-head CI 확인**

```bash
head_sha=$(git rev-parse HEAD)
gh pr checks --watch
gh pr view --json headRefOid,mergeable,mergeStateStatus,isDraft,statusCheckRollup
test "$(gh pr view --json headRefOid --jq .headRefOid)" = "$head_sha"
```

Expected: PR HEAD 일치, CI 전부 SUCCESS, Draft 유지. Merge·Production 배포는 수행하지 않는다.

## Execution Boundary

실제 NAVER Tile과 중립 Marker의 Browser QA는 기존 Client ID가 적용된 Vercel Preview를 별도 승인받아 만든 뒤 수행한다. Preview에서는 첫 진입 중심 좌표·Zoom 16·중립 Marker 1개, Area 선택 전 Spot Marker·Zone 0개, Geolocation 권한 팝업 0회, FreshManager Browser Storage 쓰기 0회, Fixture Backend 요청 0회를 확인한다. Preview 승인 전에는 Adapter 시험·Type Check·Build·CI까지만 완료로 판정하고 실제 지도 Browser 결과는 `NOT_EVALUATED`로 기록한다.
