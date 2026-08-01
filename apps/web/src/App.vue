<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  createNaverMap,
  type MapPoint,
  type NaverMapController,
} from "./naver-map";
import type {
  AreaListItem,
  AreaPilotData,
  AreaPilotResponse,
  AreasResponse,
  PopulationRange,
  SpotOption,
} from "./generated/api-types";

type Panel = "none" | "area" | "spots" | "spot";
type RequestState = "idle" | "loading" | "ready" | "error";
type MapState = "idle" | "loading" | "available" | "unavailable";
type GeolocationState =
  | "idle"
  | "requesting"
  | "available"
  | "denied"
  | "unavailable";

const numberFormatter = new Intl.NumberFormat("ko-KR", {
  maximumFractionDigits: 1,
});

const areas = ref<AreaListItem[]>([]);
const areasState = ref<RequestState>("loading");
const selectedAreaCode = ref("");
const pilotView = ref<AreaPilotResponse | null>(null);
const viewState = ref<RequestState>("idle");
const panel = ref<Panel>("none");
const openedSpotId = ref<string | null>(null);
const selectedSpotId = ref<string | null>(null);
const helpOpen = ref(false);
const toastMessage = ref("");
const mapState = ref<MapState>("idle");
const geolocationState = ref<GeolocationState>("idle");
const userLocation = ref<MapPoint | null>(null);
const mapCanvas = ref<HTMLElement | null>(null);
const panelHeading = ref<HTMLElement | null>(null);

let viewAbortController: AbortController | undefined;
let mapController: NaverMapController | undefined;
let mapGeneration = 0;
let returnFocusElement: HTMLElement | null = null;
let toastTimer: number | undefined;

const openedSpot = computed(
  () =>
    pilotView.value?.spot_options.find(
      (spot) => spot.spot_option_id === openedSpotId.value,
    ) ?? null,
);

const selectedSpot = computed(
  () =>
    pilotView.value?.spot_options.find(
      (spot) => spot.spot_option_id === selectedSpotId.value,
    ) ?? null,
);

const spotPrototypeContractInvalid = computed(
  () => pilotView.value?.warnings.includes("SPOT_PROTOTYPE_CONTRACT_INVALID") ?? false,
);

const panelTitle = computed(() => {
  if (panel.value === "area") return "구역 정보";
  if (panel.value === "spots") return "후보 위치 3곳";
  if (panel.value === "spot") return "후보 위치 상세";
  return "";
});

const visibleTimestamp = computed(() => pilotView.value?.area.observed_at ?? null);

function formatRange(value: PopulationRange | null) {
  if (!value) return "—";
  return `${numberFormatter.format(value.min)} ~ ${numberFormatter.format(value.max)}명`;
}

function formatDateTime(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatChange(value: number | null) {
  if (value === null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${numberFormatter.format(value)}명`;
}

function formatRate(value: number | null) {
  if (value === null) return "—";
  const percent = value * 100;
  const sign = percent > 0 ? "+" : "";
  return `${sign}${numberFormatter.format(percent)}%`;
}

function changeClass(value: number | null) {
  if (value === null || value === 0) return "change-neutral";
  return value > 0 ? "change-up" : "change-down";
}

function limitationItems(spot: SpotOption) {
  const limitations = spot.limitations.filter(Boolean);
  return limitations.length
    ? limitations
    : ["실제 판매 허용 여부, 접근성, 안전성과 카트 정차 가능성은 현장 확인이 필요합니다."];
}

function isSpotDataUnavailable(spot: SpotOption) {
  return (
    spot.prototype_data_status === "SPOT_PROTOTYPE_DATA_UNAVAILABLE" ||
    (!spot.current_population && !spot.forecast_60 && !spot.forecast_180)
  );
}

function straightLineDistanceKm(
  from: { latitude: number; longitude: number },
  to: { latitude: number; longitude: number },
) {
  const toRadians = (degrees: number) => (degrees * Math.PI) / 180;
  const earthRadiusKm = 6371;
  const latitudeDelta = toRadians(to.latitude - from.latitude);
  const longitudeDelta = toRadians(to.longitude - from.longitude);
  const a =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(toRadians(from.latitude)) *
      Math.cos(toRadians(to.latitude)) *
      Math.sin(longitudeDelta / 2) ** 2;
  const bounded = Math.min(1, Math.max(0, a));
  return earthRadiusKm * 2 * Math.atan2(Math.sqrt(bounded), Math.sqrt(1 - bounded));
}

function straightDistanceKm(spot: SpotOption) {
  const point = userLocation.value;
  return point ? straightLineDistanceKm(point, spot) : null;
}

function formatDistance(spot: SpotOption) {
  const distance = straightDistanceKm(spot);
  return distance === null ? null : `${numberFormatter.format(distance)}km 직선거리`;
}

async function loadAreas() {
  areasState.value = "loading";
  try {
    const response = await fetch("/api/v1/areas", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error("AREA_LIST_UNAVAILABLE");
    const payload = (await response.json()) as AreasResponse;
    areas.value = payload.areas;
    areasState.value = "ready";
  } catch {
    areas.value = [];
    areasState.value = "error";
  }
}

async function selectArea() {
  viewAbortController?.abort();
  destroyMap();
  pilotView.value = null;
  panel.value = "none";
  openedSpotId.value = null;
  selectedSpotId.value = null;
  geolocationState.value = "idle";
  userLocation.value = null;

  if (!selectedAreaCode.value) {
    viewState.value = "idle";
    mapState.value = "idle";
    return;
  }

  viewState.value = "loading";
  viewAbortController = new AbortController();
  try {
    const response = await fetch(
      `/api/v1/areas/${encodeURIComponent(selectedAreaCode.value)}/pilot-view`,
      {
        headers: { Accept: "application/json" },
        signal: viewAbortController.signal,
      },
    );
    if (!response.ok) throw new Error("AREA_VIEW_UNAVAILABLE");
    pilotView.value = (await response.json()) as AreaPilotResponse;
    viewState.value = "ready";
    await nextTick();
    await setupMap();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    pilotView.value = null;
    viewState.value = "error";
    mapState.value = "unavailable";
  }
}

function destroyMap() {
  mapGeneration += 1;
  mapController?.destroy();
  mapController = undefined;
}

async function setupMap() {
  destroyMap();
  const view = pilotView.value;
  const element = mapCanvas.value;
  if (!view || !element) return;

  const generation = mapGeneration;
  mapState.value = "loading";
  try {
    const controller = await createNaverMap(
      element,
      import.meta.env.VITE_NAVER_MAP_CLIENT_ID ?? "",
      view.spot_options.map((spot) => ({
        id: spot.spot_option_id,
        name: spot.spot_name,
        latitude: spot.latitude,
        longitude: spot.longitude,
        displayOrder: spot.display_order,
      })),
      (spotId) => openSpot(spotId),
    );
    if (generation !== mapGeneration) {
      controller.destroy();
      return;
    }
    mapController = controller;
    controller.setMarkerState(openedSpotId.value, selectedSpotId.value);
    if (userLocation.value) controller.setUserLocation(userLocation.value);
    mapState.value = "available";
  } catch {
    if (generation === mapGeneration) mapState.value = "unavailable";
  }
}

async function openPanel(nextPanel: Exclude<Panel, "none">, trigger?: Event) {
  if (trigger?.currentTarget instanceof HTMLElement) {
    returnFocusElement = trigger.currentTarget;
  }
  panel.value = nextPanel;
  await nextTick();
  panelHeading.value?.focus();
}

function openSpot(spotId: string, trigger?: Event) {
  openedSpotId.value = spotId;
  const focusTrigger = panel.value === "none" ? trigger : undefined;
  void openPanel("spot", focusTrigger);
}

function closePanel() {
  panel.value = "none";
  openedSpotId.value = null;
  const target = returnFocusElement;
  returnFocusElement = null;
  void nextTick(() => target?.focus());
}

function backToSpotList() {
  openedSpotId.value = null;
  void openPanel("spots");
}

function selectSpot() {
  if (!openedSpot.value) return;
  selectedSpotId.value = openedSpot.value.spot_option_id;
  toastMessage.value = "판촉 후보 위치로 선택했습니다. 다른 후보 위치로 변경할 수 있습니다.";
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toastMessage.value = "";
  }, 4200);
}

function requestLocation() {
  userLocation.value = null;
  mapController?.setUserLocation(null);
  if (!navigator.geolocation) {
    geolocationState.value = "unavailable";
    return;
  }
  geolocationState.value = "requesting";
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      userLocation.value = {
        latitude: coords.latitude,
        longitude: coords.longitude,
      };
      geolocationState.value = "available";
      mapController?.setUserLocation(userLocation.value);
    },
    (error) => {
      geolocationState.value = error.code === error.PERMISSION_DENIED ? "denied" : "unavailable";
    },
    { enableHighAccuracy: false, maximumAge: 60_000, timeout: 10_000 },
  );
}

function handleEscape() {
  if (helpOpen.value) {
    helpOpen.value = false;
  } else if (panel.value !== "none") {
    closePanel();
  }
}

function handleDocumentKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") handleEscape();
}

watch([openedSpotId, selectedSpotId], ([openedId, selectedId]) => {
  mapController?.setMarkerState(openedId, selectedId);
});

onMounted(() => {
  void loadAreas();
  document.addEventListener("keydown", handleDocumentKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleDocumentKeydown);
  viewAbortController?.abort();
  destroyMap();
  window.clearTimeout(toastTimer);
});
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <a class="brand" href="#main-content" aria-label="FreshManager 메인으로 이동">
        <span class="brand-mark" aria-hidden="true">F</span>
        <span>FreshManager</span>
      </a>

      <div class="header-area-field">
        <label for="area-select">담당 Area</label>
        <select
          id="area-select"
          v-model="selectedAreaCode"
          :disabled="areasState === 'loading'"
          @change="selectArea"
        >
          <option value="">
            {{ areasState === "loading" ? "Area를 불러오는 중입니다" : "담당 Area를 선택하세요" }}
          </option>
          <option
            v-for="area in areas"
            :key="area.area_code"
            :value="area.area_code"
          >
            {{ area.area_name }}
          </option>
        </select>
      </div>

      <p class="data-time" aria-live="polite">
        <span>데이터 기준시각</span>
        <strong>{{ formatDateTime(visibleTimestamp) }}</strong>
      </p>

      <div class="help-wrap">
        <button
          class="help-button"
          type="button"
          :aria-expanded="helpOpen"
          aria-controls="help-panel"
          @click="helpOpen = !helpOpen"
        >
          <span aria-hidden="true">?</span> 도움말
        </button>
        <div v-if="helpOpen" id="help-panel" class="help-panel" role="status">
          담당 Area를 직접 고른 뒤 지도나 목록에서 후보 위치 3곳을 확인하세요.
          후보 위치는 현장검증 전의 선택지입니다.
        </div>
      </div>
    </header>

    <main id="main-content" class="app-main">
      <div v-if="areasState === 'error'" class="top-alert" role="alert">
        <span>Area 목록을 불러오지 못했습니다.</span>
        <button type="button" @click="loadAreas">다시 시도</button>
      </div>

      <section class="map-shell" :data-map-state="mapState" aria-label="후보 위치 지도와 정보">
        <div ref="mapCanvas" class="map-canvas" :aria-hidden="mapState !== 'available'"></div>

        <div v-if="viewState === 'idle'" class="map-fallback map-empty">
          <span class="map-fallback-icon" aria-hidden="true">⌖</span>
          <h1>담당 Area를 선택하세요</h1>
          <p>승인된 5개 Area 중 담당 구역을 고르면 후보 위치 3곳을 확인할 수 있습니다.</p>
        </div>

        <div v-else-if="viewState === 'loading'" class="map-fallback" role="status">
          <span class="loading-dot" aria-hidden="true"></span>
          <h1>Area 정보를 불러오는 중입니다</h1>
          <p>이전 Area 정보와 후보 선택은 초기화되었습니다.</p>
        </div>

        <div v-else-if="viewState === 'error'" class="map-fallback" role="alert">
          <h1>Area 정보를 불러오지 못했습니다</h1>
          <p>확인되지 않은 값은 표시하지 않았습니다.</p>
          <button class="secondary-button" type="button" @click="selectArea">다시 시도</button>
        </div>

        <div
          v-else-if="pilotView && mapState !== 'available'"
          class="map-fallback map-list-fallback"
        >
          <span class="status-pill">지도 없이 목록 이용</span>
          <h1>{{ pilotView.area.area_name }}</h1>
          <p v-if="mapState === 'loading'">지도를 불러오는 동안 목록을 이용할 수 있습니다.</p>
          <p v-else>지도를 불러오지 못했지만 후보 위치 정보와 선택 기능은 이용할 수 있습니다.</p>
          <div class="fallback-spot-list" aria-label="후보 위치 바로가기">
            <button
              v-for="spot in pilotView.spot_options"
              :key="spot.spot_option_id"
              type="button"
              @click="openSpot(spot.spot_option_id, $event)"
            >
              <span>{{ spot.display_order }}</span>
              {{ spot.spot_name }}
            </button>
          </div>
        </div>

        <template v-if="pilotView && viewState === 'ready'">
          <nav class="map-actions" aria-label="지도 정보 열기">
            <button type="button" @click="openPanel('area', $event)">
              <span aria-hidden="true">ⓘ</span> 구역 정보
            </button>
            <button type="button" @click="openPanel('spots', $event)">
              <span aria-hidden="true">⌖</span> 후보 위치 3곳
            </button>
            <button
              type="button"
              :disabled="geolocationState === 'requesting'"
              @click="requestLocation"
            >
              <span aria-hidden="true">◎</span>
              {{ geolocationState === "requesting" ? "위치 확인 중" : "내 위치 표시" }}
            </button>
          </nav>

          <div class="map-legend" aria-label="지도 표시 설명">
            <span><i class="legend-dot spot-dot"></i>후보 위치</span>
            <span><i class="legend-dot user-dot"></i>내 위치</span>
          </div>

          <p
            v-if="geolocationState === 'denied' || geolocationState === 'unavailable'"
            class="map-notice"
            role="status"
          >
            {{
              geolocationState === "denied"
                ? "위치 없이도 이용할 수 있습니다."
                : "위치를 확인할 수 없지만 나머지 기능은 이용할 수 있습니다."
            }}
          </p>
        </template>

        <aside
            v-if="panel !== 'none' && pilotView"
            class="info-panel"
            role="dialog"
            aria-modal="false"
            :aria-labelledby="panel === 'spot' ? 'spot-panel-title' : 'panel-title'"
          >
            <header class="panel-header">
              <button
                v-if="panel === 'spot'"
                class="panel-icon-button"
                type="button"
                aria-label="후보 위치 목록으로 돌아가기"
                @click="backToSpotList"
              >
                ←
              </button>
              <h2
                v-if="panel !== 'spot'"
                id="panel-title"
                ref="panelHeading"
                tabindex="-1"
              >
                {{ panelTitle }}
              </h2>
              <h2 v-else id="spot-panel-title" ref="panelHeading" tabindex="-1">
                후보 위치 상세
              </h2>
              <button
                class="panel-icon-button panel-close"
                type="button"
                aria-label="정보 닫기"
                @click="closePanel"
              >
                ×
              </button>
            </header>

            <div v-if="panel === 'area'" class="panel-scroll area-content">
              <p class="context-label">서울시 공식 Area 데이터</p>
              <h3>{{ pilotView.area.area_name }}</h3>
              <p v-if="pilotView.area.availability === 'DATA_UNAVAILABLE'" class="empty-notice">
                사용할 수 있는 승인 Area 인구 데이터가 없습니다. 값은 추정하지 않았습니다.
              </p>
              <div class="table-scroll">
                <table class="population-table area-population-table">
                  <caption>선택 Area의 현재와 미래 유동인구</caption>
                  <thead>
                    <tr><th>시점</th><th>예상 범위</th><th>혼잡도</th><th>증감수</th><th>증감률</th></tr>
                  </thead>
                  <tbody>
                    <tr>
                      <th>현재</th>
                      <td>{{ formatRange(pilotView.area.current_population) }}</td>
                      <td>{{ pilotView.area.congestion_level ?? "—" }}</td>
                      <td>—</td><td>—</td>
                    </tr>
                    <tr>
                      <th>
                        1시간 후
                        <small v-if="pilotView.area.forecast_60_target_at">
                          {{ formatDateTime(pilotView.area.forecast_60_target_at) }}
                        </small>
                      </th>
                      <td>{{ formatRange(pilotView.area.forecast_60) }}</td>
                      <td>{{ pilotView.area.forecast_60_congestion_level ?? "—" }}</td>
                      <td :class="changeClass(pilotView.area.change_amount_60)">{{ formatChange(pilotView.area.change_amount_60) }}</td>
                      <td :class="changeClass(pilotView.area.change_rate_60)">{{ formatRate(pilotView.area.change_rate_60) }}</td>
                    </tr>
                    <tr>
                      <th>
                        3시간 후
                        <small v-if="pilotView.area.forecast_180_target_at">
                          {{ formatDateTime(pilotView.area.forecast_180_target_at) }}
                        </small>
                      </th>
                      <td>{{ formatRange(pilotView.area.forecast_180) }}</td>
                      <td>{{ pilotView.area.forecast_180_congestion_level ?? "—" }}</td>
                      <td :class="changeClass(pilotView.area.change_amount_180)">{{ formatChange(pilotView.area.change_amount_180) }}</td>
                      <td :class="changeClass(pilotView.area.change_rate_180)">{{ formatRate(pilotView.area.change_rate_180) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <dl class="source-list">
                <div><dt>데이터 기준시각</dt><dd>{{ formatDateTime(pilotView.area.observed_at) }}</dd></div>
                <div><dt>출처</dt><dd>{{ pilotView.area.source ?? "승인 데이터 없음" }}</dd></div>
                <div><dt>이용 상태</dt><dd>데이터 없음</dd></div>
                <div><dt>Freshness</dt><dd>{{ pilotView.area.freshness === "NO_COMPLETE_SNAPSHOT" ? "완전한 Snapshot 없음" : pilotView.area.freshness }}</dd></div>
              </dl>
            </div>

            <div v-else-if="panel === 'spots'" class="panel-scroll spot-list-content">
              <p class="panel-intro">
                표시번호는 위치 구분용이며 우열을 뜻하지 않습니다. 한 곳을 눌러 상세를 확인하세요.
              </p>
              <div class="spot-card-list">
                <button
                  v-for="spot in pilotView.spot_options"
                  :key="spot.spot_option_id"
                  class="spot-card"
                  :class="{ selected: selectedSpotId === spot.spot_option_id }"
                  type="button"
                  @click="openSpot(spot.spot_option_id, $event)"
                >
                  <span class="spot-number">{{ spot.display_order }}</span>
                  <span class="spot-card-copy">
                    <strong>{{ spot.spot_name }}</strong>
                    <small>{{ spot.address }}</small>
                    <small v-if="formatDistance(spot)">{{ formatDistance(spot) }}</small>
                    <small v-else-if="isSpotDataUnavailable(spot)" class="data-unavailable">
                      {{ spotPrototypeContractInvalid ? "프로토타입 데이터 이용 불가" : "프로토타입 데이터 없음" }}
                    </small>
                  </span>
                  <span class="chevron" aria-hidden="true">›</span>
                  <span v-if="selectedSpotId === spot.spot_option_id" class="sr-only">선택됨</span>
                </button>
              </div>
            </div>

            <div v-else-if="panel === 'spot' && openedSpot" class="panel-scroll spot-detail">
              <section class="spot-identity">
                <span class="spot-number large">{{ openedSpot.display_order }}</span>
                <div>
                  <h3>{{ openedSpot.spot_name }}</h3>
                  <p>{{ openedSpot.address }}</p>
                  <p>유형: {{ openedSpot.spot_type }}</p>
                  <p v-if="formatDistance(openedSpot)" class="distance-text">
                    {{ formatDistance(openedSpot) }} · 현재 위치 기준
                  </p>
                </div>
              </section>

              <div class="badge-row" aria-label="데이터 성격">
                <span class="prototype-badge">프로토타입 데이터</span>
                <span
                  v-if="openedSpot.spot_population_source === 'PM_MANUAL_PROTOTYPE'"
                  class="manual-badge"
                >
                  PM 직접 입력
                </span>
              </div>

              <p v-if="isSpotDataUnavailable(openedSpot)" class="empty-notice">
                {{
                  spotPrototypeContractInvalid
                    ? "Spot별 프로토타입 인구 입력값을 안전하게 사용할 수 없어 표시하지 않았습니다."
                    : "Spot별 프로토타입 인구 데이터가 아직 입력되지 않았습니다."
                }}
              </p>

              <section aria-labelledby="population-title">
                <div class="section-heading">
                  <h4 id="population-title">유동인구 예상</h4>
                  <span>{{ formatDateTime(openedSpot.observed_at) }}</span>
                </div>
                <div class="table-scroll">
                  <table class="population-table spot-population-table">
                    <caption>후보 위치의 현재와 미래 프로토타입 인구</caption>
                    <thead>
                      <tr><th>시점</th><th>예상 범위</th><th>증감수</th><th>증감률</th></tr>
                    </thead>
                    <tbody>
                      <tr>
                        <th>현재</th>
                        <td>{{ formatRange(openedSpot.current_population) }}</td>
                        <td>—</td><td>—</td>
                      </tr>
                      <tr>
                        <th>1시간 후</th>
                        <td>{{ formatRange(openedSpot.forecast_60) }}</td>
                        <td :class="changeClass(openedSpot.change_amount_60)">{{ formatChange(openedSpot.change_amount_60) }}</td>
                        <td :class="changeClass(openedSpot.change_rate_60)">{{ formatRate(openedSpot.change_rate_60) }}</td>
                      </tr>
                      <tr>
                        <th>3시간 후</th>
                        <td>{{ formatRange(openedSpot.forecast_180) }}</td>
                        <td :class="changeClass(openedSpot.change_amount_180)">{{ formatChange(openedSpot.change_amount_180) }}</td>
                        <td :class="changeClass(openedSpot.change_rate_180)">{{ formatRate(openedSpot.change_rate_180) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>

              <section class="limitations" aria-labelledby="limitations-title">
                <h4 id="limitations-title">제한사항</h4>
                <ul>
                  <li v-for="item in limitationItems(openedSpot)" :key="item">{{ item }}</li>
                </ul>
                <p>현장검증이 필요합니다.</p>
              </section>

              <div class="sticky-action">
                <p v-if="selectedSpotId === openedSpot.spot_option_id" class="selection-status">
                  현재 선택한 후보 위치입니다. 다른 후보 위치로 변경할 수 있습니다.
                </p>
                <button class="primary-button" type="button" @click="selectSpot">
                  {{
                    selectedSpotId === openedSpot.spot_option_id
                      ? "선택 유지"
                      : "판촉 후보 위치로 선택"
                  }}
                </button>
              </div>
            </div>
        </aside>
      </section>
    </main>

    <div v-if="toastMessage" class="selection-toast" role="status" aria-live="polite">
      <strong>{{ selectedSpot?.spot_name }}</strong>
      <span>{{ toastMessage }}</span>
    </div>
  </div>
</template>
