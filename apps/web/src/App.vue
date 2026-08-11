<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import PopulationPatternChart from "./components/PopulationPatternChart.vue";
import PopulationRangeChart from "./components/PopulationRangeChart.vue";
import {
  ApiDataProvider,
  selectFreshManagerDataProvider,
} from "./data/freshmanager-data-provider";
import {
  createNaverMap,
  type MapPoint,
  type NaverMapController,
} from "./naver-map";
import type {
  AreaListItem,
  AreaPilotResponse,
  AreasResponse,
  PopulationRange,
  SpotOption,
} from "./generated/api-types";
import { ANALYSIS_FIXTURE, AREA_FIXTURES } from "./prototype/area-fixtures";
import { SPOT_FIXTURES } from "./prototype/spot-fixtures";
import type { SpotFixture } from "./prototype/prototype-types";
import { assertApiSpotIdentity, resolvePrototypeDataMode } from "./prototype/prototype-validation";

type Panel = "none" | "area" | "spots" | "spot";
type RequestState = "idle" | "loading" | "ready" | "error";
type MapState = "idle" | "loading" | "available" | "unavailable";
type GeolocationState =
  | "idle"
  | "requesting"
  | "available"
  | "denied"
  | "unavailable";

type ForecastSlot = {
  id: "current" | "60" | "120" | "180";
  label: string;
  range: PopulationRange | null;
  contractPending?: boolean;
};

const dataMode = resolvePrototypeDataMode(
  import.meta.env.VITE_FRESHMANAGER_DATA_MODE,
  import.meta.env.DEV,
);
const fixtureMode = dataMode === "fixture";

const HY_DEFAULT_MAP_LOCATION = {
  latitude: 37.51325,
  longitude: 127.01982,
  zoom: 16,
  title: "FreshManager 시작하기",
} as const;

const numberFormatter = new Intl.NumberFormat("ko-KR", {
  maximumFractionDigits: 1,
});

const SPOT_TYPE_LABELS: Readonly<Record<string, string>> = {
  PARK_ZONE: "공원 구역",
  PUBLIC_SPACE: "공공장소",
  TRANSIT_EXIT: "대중교통 출입구",
  VENUE: "주요 시설",
};

const areas = ref<AreaListItem[]>([]);
const areasState = ref<RequestState>("loading");
const selectedAreaCode = ref("");
const pilotView = ref<AreaPilotResponse | null>(null);
const viewState = ref<RequestState>("idle");
const viewErrorMessage = ref("Area 정보를 불러오지 못했습니다");
const panel = ref<Panel>("none");
const openedSpotId = ref<string | null>(null);
const selectedSpotId = ref<string | null>(null);
const helpOpen = ref(false);
const mapState = ref<MapState>("idle");
const geolocationState = ref<GeolocationState>("idle");
const userLocation = ref<MapPoint | null>(null);
const mapCanvas = ref<HTMLElement | null>(null);
const panelHeading = ref<HTMLElement | null>(null);

let viewAbortController: AbortController | undefined;
let mapController: NaverMapController | undefined;
let mapGeneration = 0;
let returnFocusElement: HTMLElement | null = null;

const openedSpot = computed(
  () =>
    pilotView.value?.spot_options.find(
      (spot) => spot.spot_option_id === openedSpotId.value,
    ) ?? null,
);

const areaFixture = computed(() =>
  fixtureMode
    ? AREA_FIXTURES.find((fixture) => fixture.area_code === selectedAreaCode.value) ?? null
    : null,
);

const openedSpotFixture = computed<SpotFixture | null>(() =>
  fixtureMode
    ? SPOT_FIXTURES.find((fixture) => fixture.spot_option_id === openedSpotId.value) ?? null
    : null,
);

const panelTitle = computed(() => {
  if (panel.value === "area") return "구역 정보";
  if (panel.value === "spots") return "판매 위치 목록";
  if (panel.value === "spot") return "판매 위치 상세";
  return "";
});

const visibleTimestampLabel = computed(() => {
  if (fixtureMode) return areaFixture.value?.reference_time_label ?? "—";
  if (dataMode === "unavailable") return "—";
  return formatDateTime(pilotView.value?.area.observed_at ?? null);
});

const compactObservedTimeLabel = computed(() => {
  if (fixtureMode) {
    const label = areaFixture.value?.reference_time_label.trim() ?? "";
    return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(label) ? label : "—";
  }
  if (dataMode === "unavailable") return "—";
  const value = pilotView.value?.area.observed_at;
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
});

const areaForecastSlots = computed<ForecastSlot[]>(() => {
  const area = pilotView.value?.area;
  if (!area) return [];
  const fixture = areaFixture.value;
  if (fixtureMode && fixture) {
    return [
      { id: "current", label: "현재", range: { min: fixture.population_min, max: fixture.population_max } },
      ...fixture.forecasts.map((forecast) => ({
        id: String(forecast.horizon_minutes) as "60" | "120" | "180",
        label: `${forecast.horizon_minutes}분`,
        range: { min: forecast.population_min, max: forecast.population_max },
      })),
    ];
  }
  if (dataMode === "unavailable") return [
    { id: "current", label: "현재", range: null },
    { id: "60", label: "60분", range: null },
    { id: "120", label: "120분", range: null },
    { id: "180", label: "180분", range: null },
  ];
  return [
    { id: "current", label: "현재", range: area.current_population },
    { id: "60", label: "60분", range: area.forecast_60 },
    { id: "120", label: "120분", range: null, contractPending: true },
    { id: "180", label: "180분", range: area.forecast_180 },
  ];
});

const spotForecastSlots = computed<ForecastSlot[]>(() => {
  const spot = openedSpot.value;
  if (!spot) return [];
  const fixture = openedSpotFixture.value;
  if (fixtureMode && fixture) return [
    { id: "current", label: "현재", range: { min: fixture.current_population_min, max: fixture.current_population_max } },
    { id: "60", label: "60분", range: { min: fixture.forecast_60_min, max: fixture.forecast_60_max } },
    { id: "120", label: "120분", range: { min: fixture.forecast_120_min, max: fixture.forecast_120_max } },
    { id: "180", label: "180분", range: { min: fixture.forecast_180_min, max: fixture.forecast_180_max } },
  ];
  if (dataMode === "unavailable") return [
    { id: "current", label: "현재", range: null },
    { id: "60", label: "60분", range: null },
    { id: "120", label: "120분", range: null },
    { id: "180", label: "180분", range: null },
  ];
  return [
    { id: "current", label: "현재", range: spot.current_population },
    { id: "60", label: "60분", range: spot.forecast_60 },
    { id: "120", label: "120분", range: null, contractPending: true },
    { id: "180", label: "180분", range: spot.forecast_180 },
  ];
});

const areaPopulationAvailable = computed(() =>
  areaForecastSlots.value.some((slot) => slot.range !== null),
);

const spotPopulationAvailable = computed(() =>
  spotForecastSlots.value.some((slot) => slot.range !== null),
);

function formatRange(value: PopulationRange | null) {
  if (!value) return "—";
  return `${numberFormatter.format(value.min)}~${numberFormatter.format(value.max)}명`;
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

function formatSpotType(value: string) {
  return SPOT_TYPE_LABELS[value] ?? "기타 판매 위치";
}

async function loadAreas() {
  areasState.value = "loading";
  try {
    const payload = await dataProvider.listAreas();
    areas.value = payload.areas;
    areasState.value = "ready";
  } catch {
    areas.value = [];
    areasState.value = "error";
  }
}

async function requestAreasFromApi(): Promise<AreasResponse> {
  const response = await fetch("/api/v1/areas", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("AREA_LIST_UNAVAILABLE");
  return (await response.json()) as AreasResponse;
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
  viewErrorMessage.value = "Area 정보를 불러오지 못했습니다";

  if (!selectedAreaCode.value) {
    viewState.value = "idle";
    await setupMap();
    return;
  }

  viewState.value = "loading";
  viewAbortController = new AbortController();
  try {
    const payload = await dataProvider.getPilotView(
      selectedAreaCode.value,
      viewAbortController.signal,
    );
    if (fixtureMode) {
      try {
        assertApiSpotIdentity(selectedAreaCode.value, payload.spot_options);
      } catch (error) {
        if (import.meta.env.DEV) console.error("Prototype Spot fixture identity validation failed", error);
        viewErrorMessage.value = "판매 위치 정보를 불러오지 못했습니다.";
        viewState.value = "error";
        mapState.value = "unavailable";
        return;
      }
    }
    pilotView.value = payload;
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

async function requestPilotViewFromApi(
  areaCode: string,
  signal?: AbortSignal,
): Promise<AreaPilotResponse> {
  const response = await fetch(
    `/api/v1/areas/${encodeURIComponent(areaCode)}/pilot-view`,
    {
      headers: { Accept: "application/json" },
      signal,
    },
  );
  if (!response.ok) throw new Error("AREA_VIEW_UNAVAILABLE");
  return (await response.json()) as AreaPilotResponse;
}

const apiDataProvider = new ApiDataProvider(
  requestAreasFromApi,
  requestPilotViewFromApi,
);
const dataProvider = selectFreshManagerDataProvider(dataMode, apiDataProvider);

function destroyMap() {
  mapGeneration += 1;
  mapController?.destroy();
  mapController = undefined;
}

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
  void setupMap();
  document.addEventListener("keydown", handleDocumentKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleDocumentKeydown);
  viewAbortController?.abort();
  destroyMap();
});
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <a class="brand" href="#main-content" aria-label="FreshManager 메인으로 이동">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M19.5 4.5c-7.8.2-12.4 3.6-13.8 8.2-1.1 3.6 1.4 6.8 4.8 6.8 5.6 0 8.6-6.4 9-15Z" />
            <path d="M5 19c1.5-4.1 4.7-7.1 9.8-9.2" />
          </svg>
        </span>
        <span>FreshManager</span>
      </a>

      <div class="header-area-field">
        <label class="sr-only" for="area-select">담당 구역 선택</label>
        <select
          id="area-select"
          v-model="selectedAreaCode"
          :disabled="areasState === 'loading'"
          @change="selectArea"
        >
          <option value="">
            {{
              areasState === "loading"
                ? "담당 구역을 불러오는 중입니다"
                : "담당 구역을 선택해 주세요"
            }}
          </option>
          <option
            v-for="area in areas"
            :key="area.area_code"
            :value="area.area_code"
          >
            {{ area.area_name }}
          </option>
        </select>
        <svg
          class="ui-icon chevron select-chevron"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path d="m7 9 5 5 5-5" />
        </svg>
      </div>

      <p class="data-time" aria-live="polite">
        <span>데이터 기준시각</span>
        <strong>{{ visibleTimestampLabel }}</strong>
      </p>

      <div class="help-wrap">
        <button
          class="help-button"
          type="button"
          :aria-expanded="helpOpen"
          aria-controls="help-panel"
          @click="helpOpen = !helpOpen"
        >
          <svg class="ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="M9.8 9.2a2.35 2.35 0 0 1 4.5.9c0 1.7-2.3 2.1-2.3 3.6" />
            <path d="M12 17h.01" />
          </svg>
          <span class="help-label">도움말</span>
        </button>
        <div v-if="helpOpen" id="help-panel" class="help-panel" role="status">
          <p>담당 구역을 직접 고른 뒤 지도나 판매 위치 목록을 확인하세요. 판매 위치는 현장검증 전의 선택지입니다.</p>
          <p v-if="fixtureMode">현재 화면의 인구·시간대·변화 값과 기준시각은 서비스 화면과 사용 흐름을 검토하기 위한 고정 시뮬레이션 값입니다.</p>
          <p v-if="fixtureMode">색상 Zone은 판매 위치를 구분하기 위한 화면 검토용 표시이며, 실제 판매 범위나 행정 경계가 아닙니다.</p>
          <p v-else-if="dataMode === 'official'">구역 정보는 API가 제공한 값만 표시하며, 제공되지 않은 값은 만들지 않습니다.</p>
          <p v-else>인구 데이터가 준비되지 않아 값을 표시하지 않으며, 누락값을 임의로 만들지 않습니다.</p>
        </div>
      </div>
    </header>

    <main id="main-content" class="app-main">
      <div v-if="areasState === 'error'" class="top-alert" role="alert">
        <span>담당 구역 목록을 불러오지 못했습니다.<br />잠시 후 다시 시도해 주세요.</span>
        <button class="secondary-button" type="button" @click="loadAreas">담당 구역 다시 불러오기</button>
      </div>

      <section
        class="map-shell"
        :data-map-state="mapState"
        :data-panel-open="panel !== 'none'"
        :aria-label="selectedAreaCode ? '판매 위치 지도와 정보' : 'FreshManager 시작하기 지도와 담당 구역 선택'"
      >
        <div ref="mapCanvas" class="map-canvas" :aria-hidden="mapState !== 'available'"></div>

        <div
          v-if="viewState === 'idle' && mapState !== 'available'"
          class="map-fallback map-empty"
        >
          <span class="map-fallback-icon" aria-hidden="true">
            <svg class="ui-icon" viewBox="0 0 24 24" fill="none">
              <path d="m3.5 6.5 5-2.5 7 2.5 5-2.5v13.5l-5 2.5-7-2.5-5 2.5Z" />
              <path d="M8.5 4v13.5M15.5 6.5V20" />
            </svg>
          </span>
          <h1>담당 구역을 선택해 주세요</h1>
          <p>승인된 5개 구역 중 담당 구역을 고르면 판매 위치 목록을 확인할 수 있습니다.</p>
        </div>

        <div v-else-if="viewState === 'loading'" class="map-fallback" role="status">
          <span class="loading-dot" aria-hidden="true"></span>
          <h1>Area 정보를 불러오는 중입니다</h1>
          <p>이전 Area 정보와 판매 위치 선택은 초기화되었습니다.</p>
        </div>

        <div v-else-if="viewState === 'error'" class="map-fallback" role="alert">
          <h1>{{ viewErrorMessage }}</h1>
          <p>확인되지 않은 값은 표시하지 않았습니다.</p>
          <button class="secondary-button" type="button" @click="selectArea">다시 시도</button>
        </div>

        <div
          v-else-if="pilotView && mapState !== 'available'"
          class="map-fallback map-list-fallback"
        >
          <div class="fallback-map-grid" aria-hidden="true"></div>
          <div class="fallback-map-copy">
            <span class="status-pill">지도 없이 목록 이용</span>
            <h1>{{ pilotView.area.area_name }}</h1>
            <p v-if="mapState === 'loading'">지도를 불러오는 동안 판매 위치 목록을 이용할 수 있습니다.</p>
            <p v-else>지도는 표시하지 못했지만 판매 위치의 정적 정보와 선택 기능은 이용할 수 있습니다.</p>
            <button v-if="pilotView && viewState === 'ready' && mapState === 'unavailable'" class="secondary-button" type="button" @click="setupMap" aria-label="지도 다시 시도">
              <svg class="ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M20 11a8 8 0 1 0-2.3 5.7" />
                <path d="M20 5v6h-6" />
              </svg>
              지도 다시 시도
            </button>
          </div>
        </div>

        <template v-if="pilotView && viewState === 'ready'">
          <div class="map-tools-dock">
            <nav class="map-actions" aria-label="지도 정보 열기">
              <button type="button" @click="openPanel('area', $event)">
                <svg class="ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 11v5M12 8h.01" />
                </svg>
                구역 정보
              </button>
              <button type="button" @click="openPanel('spots', $event)">
                <svg class="ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M12 21s6-5.1 6-11a6 6 0 1 0-12 0c0 5.9 6 11 6 11Z" />
                  <circle cx="12" cy="10" r="2" />
                </svg>
                판매 위치 목록
              </button>
              <button
                type="button"
                :disabled="geolocationState === 'requesting'"
                @click="requestLocation"
              >
                <svg class="ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="6" />
                  <circle cx="12" cy="12" r="1.5" />
                  <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
                </svg>
                {{ geolocationState === "requesting" ? "위치 확인 중" : "내 위치 표시" }}
              </button>
            </nav>

            <div class="map-legend" aria-label="지도 표시 설명">
              <span><i class="legend-dot spot-dot"></i>판매 위치</span>
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
          </div>
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
                aria-label="판매 위치 목록으로 돌아가기"
                @click="backToSpotList"
              >
                <svg class="ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="m15 18-6-6 6-6" />
                </svg>
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
                판매 위치 상세
              </h2>
              <button
                class="panel-icon-button panel-close"
                type="button"
                aria-label="정보 닫기"
                @click="closePanel"
              >
                <svg class="ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="m6 6 12 12M18 6 6 18" />
                </svg>
              </button>
            </header>

            <div v-if="panel === 'area'" class="panel-scroll area-content">
              <section class="panel-context-header">
                <p class="context-label">선택한 담당 구역</p>
                <h3>{{ pilotView.area.area_name }}</h3>
              </section>

              <section class="info-section" aria-labelledby="area-current-title">
                <div class="section-heading">
                  <h4 id="area-current-title">현재 유동인구</h4>
                </div>
                <dl class="metric-grid metric-grid-three">
                  <div class="metric-population"><dt>예상 유동인구 범위</dt><dd>{{ formatRange(areaForecastSlots[0]?.range ?? null) }}</dd></div>
                  <div class="metric-congestion"><dt>혼잡도</dt><dd>{{ fixtureMode ? (areaFixture?.congestion_level ?? "—") : (dataMode === "official" ? (pilotView.area.congestion_level ?? "—") : "—") }}</dd></div>
                  <div class="metric-observed-time"><dt>기준시각</dt><dd>{{ compactObservedTimeLabel }}</dd></div>
                </dl>
                <p v-if="!areaPopulationAvailable" class="section-note">구역 인구 데이터가 준비되지 않아 값을 표시하지 않습니다.</p>
              </section>

              <section class="info-section" aria-labelledby="area-change-title">
                <div class="section-heading">
                  <h4 id="area-change-title">오늘의 변화</h4>
                </div>
                <PopulationRangeChart
                  v-if="areaPopulationAvailable"
                  ariaPrefix="선택 구역의 오늘 변화"
                  :slots="areaForecastSlots"
                  testId="area-forecast-chart"
                />
                <p v-else class="section-note">구역의 현재·미래 인구 데이터가 준비되면 표시됩니다.</p>
              </section>

              <section class="info-section" aria-labelledby="area-pattern-title">
                <div class="section-heading">
                  <h4 id="area-pattern-title">반복 패턴</h4>
                </div>
                <PopulationPatternChart
                  v-if="fixtureMode && areaFixture"
                  :analysis="ANALYSIS_FIXTURE"
                  :buckets="areaFixture.time_buckets"
                  :peaks="areaFixture.repeated_peaks"
                />
                <p v-else class="section-note">반복 패턴 데이터가 준비되면 표시됩니다.</p>
              </section>

              <section class="info-section data-basis" aria-labelledby="area-basis-title">
                <div class="section-heading">
                  <h4 id="area-basis-title">데이터 기준</h4>
                </div>
                <dl class="source-list">
                  <div><dt>데이터 출처</dt><dd>{{ fixtureMode ? "서울열린데이터광장" : (dataMode === "official" ? (pilotView.area.source ?? "—") : "—") }}</dd></div>
                  <div><dt>분석기간</dt><dd>{{ fixtureMode ? ANALYSIS_FIXTURE.analysis_period_label : "—" }}</dd></div>
                  <div><dt>관측 시점</dt><dd>{{ fixtureMode ? `${ANALYSIS_FIXTURE.total_observation_points}개` : "—" }}</dd></div>
                  <div><dt>기준시각</dt><dd>{{ fixtureMode ? (areaFixture?.reference_time_label ?? "—") : compactObservedTimeLabel }}</dd></div>
                  <div><dt>실제 서울시 연동</dt><dd>{{ fixtureMode ? "연결 완료" : dataMode === "official" ? "연결됨" : "연결 전" }}</dd></div>
                </dl>
              </section>
            </div>

            <div v-else-if="panel === 'spots'" class="panel-scroll spot-list-content">
              <p class="context-label">{{ pilotView.area.area_name }}</p>
              <p class="panel-intro">
                표시번호는 위치 구분용이며 우열을 뜻하지 않습니다. 한 곳을 눌러 상세를 확인하세요.
              </p>
              <div class="spot-card-list">
                <button
                  v-for="spot in pilotView.spot_options"
                  :key="spot.spot_option_id"
                  class="spot-card"
                  :class="{
                    opened: openedSpotId === spot.spot_option_id,
                    selected: selectedSpotId === spot.spot_option_id,
                  }"
                  type="button"
                  @click="openSpot(spot.spot_option_id, $event)"
                >
                  <span class="spot-number">{{ spot.display_order }}</span>
                  <span class="spot-card-copy">
                    <strong>{{ spot.spot_name }}</strong>
                    <small>{{ spot.address }}</small>
                    <small v-if="formatDistance(spot)">{{ formatDistance(spot) }}</small>
                    <span v-if="selectedSpotId === spot.spot_option_id" class="selected-label">
                      <svg class="ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path d="m6 12 4 4 8-9" />
                      </svg>
                      선택됨
                    </span>
                  </span>
                  <svg class="ui-icon chevron" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="m9 6 6 6-6 6" />
                  </svg>
                </button>
              </div>
            </div>

            <div v-else-if="panel === 'spot' && openedSpot" class="panel-scroll spot-detail">
              <section class="spot-identity">
                <span class="spot-number large">{{ openedSpot.display_order }}</span>
                <div>
                  <h3>{{ openedSpot.spot_name }}</h3>
                  <p>{{ openedSpot.address }}</p>
                  <p class="spot-type">유형: {{ formatSpotType(openedSpot.spot_type) }}</p>
                  <p v-if="formatDistance(openedSpot)" class="distance-text">
                    {{ formatDistance(openedSpot) }} · 현재 위치 기준
                  </p>
                  <p v-else class="distance-text">현재 위치 직선거리: 확인 불가</p>
                  <span
                    v-if="openedSpot.operational_suitability_status === 'NOT_VERIFIED'"
                    class="field-status"
                  >
                    현장 확인 전
                  </span>
                </div>
              </section>

              <section class="info-section" aria-labelledby="area-context-title">
                <div class="section-heading">
                  <h4 id="area-context-title">선택 구역 전망</h4>
                </div>
                <p class="section-note area-context-note">
                  이 정보는 판매 위치 자체가 아니라 선택한 구역 전체의 정보입니다.
                </p>
                <PopulationRangeChart
                  v-if="areaPopulationAvailable"
                  ariaPrefix="선택 구역 전망"
                  :slots="areaForecastSlots"
                  testId="spot-area-forecast-chart"
                />
                <p v-else class="section-note">선택 구역의 현재·미래 인구 데이터가 준비되면 표시됩니다.</p>
              </section>

              <section class="info-section" aria-labelledby="spot-population-title">
                <div class="section-heading">
                  <h4 id="spot-population-title">판매 위치별 예상 인구</h4>
                </div>
                <PopulationRangeChart
                  v-if="spotPopulationAvailable"
                  ariaPrefix="판매 위치별 예상 인구"
                  :slots="spotForecastSlots"
                  testId="spot-population-chart"
                />
                <p v-else class="section-note">판매 위치별 인구 데이터가 아직 준비되지 않았습니다.</p>
              </section>

              <section class="limitations info-section" aria-labelledby="limitations-title">
                <h4 id="limitations-title">제한사항</h4>
                <p class="limitation-primary">
                  실제 판매 가능 여부, 접근성, 안전성 및 카트 정차 가능성은 현장에서 확인해야 합니다.
                </p>
              </section>
            </div>
            <footer v-if="panel === 'spot' && openedSpot" class="panel-footer sticky-action">
              <p
                v-if="selectedSpotId === openedSpot.spot_option_id"
                class="selection-status"
                role="status"
                aria-live="polite"
                aria-label="현재 선택한 판매 위치입니다. 다른 판매 위치로 변경할 수 있습니다."
              >
                <svg class="ui-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="9" />
                  <path d="m7.5 12 3 3 6-6" />
                </svg>
                <span><strong>판매 위치로 선택했습니다.</strong> 다른 판매 위치로 변경할 수 있습니다.</span>
              </p>
              <button class="primary-button" type="button" @click="selectSpot">
                {{
                  selectedSpotId === openedSpot.spot_option_id
                    ? "선택 유지"
                    : "판매 위치로 선택"
                }}
              </button>
            </footer>
        </aside>
      </section>
    </main>
  </div>
</template>
