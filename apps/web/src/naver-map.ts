export type MapSpot = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  displayOrder: number;
};

export type MapPoint = { latitude: number; longitude: number };

export type MapInitialLocation = MapPoint & {
  zoom: number;
  title: string;
};

type NaverMarker = {
  setIcon(icon: { content: string; anchor: NaverPoint }): void;
  setMap(map: null): void;
  setZIndex(zIndex: number): void;
};

type NaverCircle = {
  setMap(map: null): void;
};

type NaverPoint = object;

type NaverMaps = {
  Map: new (
    element: HTMLElement,
    options: Record<string, unknown>,
  ) => {
    fitBounds(bounds: object, options?: Record<string, number>): void;
    destroy(): void;
  };
  Marker: new (options: Record<string, unknown>) => NaverMarker;
  Circle: new (options: Record<string, unknown>) => NaverCircle;
  LatLng: new (latitude: number, longitude: number) => object;
  LatLngBounds: new () => { extend(point: object): void };
  Point: new (x: number, y: number) => NaverPoint;
  Event: {
    addListener(target: object, event: string, handler: () => void): object;
    removeListener(listener: object): void;
  };
};

declare global {
  interface Window {
    naver?: { maps: NaverMaps };
  }
}

let loader: Promise<NaverMaps> | undefined;

const PROTOTYPE_ZONE_RADIUS_METERS = 120;
const PROTOTYPE_ZONE_COLORS = ["#0072b2", "#e69f00", "#cc79a7"] as const;

function assertMapContainerAvailable(element: HTMLElement) {
  if (typeof element.getBoundingClientRect !== "function") return;
  const { width, height } = element.getBoundingClientRect();
  if (!(width > 0 && height > 0)) {
    throw new Error("NAVER_MAP_CONTAINER_UNAVAILABLE");
  }
}

function loadMaps(clientId: string): Promise<NaverMaps> {
  if (window.naver?.maps) return Promise.resolve(window.naver.maps);
  if (loader) return loader;

  loader = new Promise<NaverMaps>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      "script[data-freshmanager-naver-map]",
    );
    const script = existing ?? document.createElement("script");
    const cleanupListeners = () => {
      script.removeEventListener("load", finish);
      script.removeEventListener("error", rejectLoad);
    };
    const rejectLoad = () => {
      cleanupListeners();
      script.remove();
      loader = undefined;
      reject(new Error("NAVER_MAP_UNAVAILABLE"));
    };
    const finish = () => {
      const maps = window.naver?.maps;
      if (!maps) {
        rejectLoad();
        return;
      }
      cleanupListeners();
      resolve(maps);
    };

    script.addEventListener("load", finish, { once: true });
    script.addEventListener("error", rejectLoad, { once: true });

    if (!existing) {
      script.dataset.freshmanagerNaverMap = "true";
      script.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${encodeURIComponent(clientId)}`;
      script.async = true;
      document.head.append(script);
    }
  });

  return loader;
}

function markerContent(order: number, state: "default" | "opened" | "selected") {
  const selected = state === "selected";
  const background = selected ? "#008577" : state === "opened" ? "#dff5f0" : "#ffffff";
  const color = selected ? "#ffffff" : "#006b5e";
  const border = state === "default" ? "#008577" : "#006b5e";
  const label = selected
    ? '<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 12 4 4 8-9"/></svg>'
    : String(order);
  return {
    content: `<span aria-hidden="true" style="display:grid;place-items:center;width:44px;height:44px;border:2px solid ${border};border-radius:50% 50% 50% 12px;background:${background};color:${color};font:700 14px/1 'Pretendard Variable',Pretendard,system-ui,sans-serif;box-shadow:0 4px 14px rgba(21,47,41,.10);transform:rotate(-45deg)"><span style="display:grid;place-items:center;transform:rotate(45deg)">${label}</span></span>`,
  };
}

function initialLocationMarkerContent() {
  return {
    content:
      '<span aria-hidden="true" style="display:flex;align-items:center;gap:6px;padding:8px 10px;border:1px solid #008577;border-radius:999px;background:#fff;color:#006b5e;font:700 13px/1 system-ui,sans-serif;box-shadow:0 4px 14px rgba(21,47,41,.10)"><span style="display:block;width:8px;height:8px;border-radius:50%;background:#008577"></span>hy 기준 위치</span>',
  };
}

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
  try {
    assertMapContainerAvailable(element);
  } catch (error) {
    map.destroy();
    throw error;
  }
  const bounds = new maps.LatLngBounds();
  const listeners: object[] = [];
  const markers = new Map<string, { marker: NaverMarker; order: number }>();
  const zones: NaverCircle[] = [];
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

  let userMarker: NaverMarker | undefined;

  return {
    setMarkerState(openedId: string | null, selectedId: string | null) {
      for (const [id, entry] of markers) {
        const state = id === selectedId ? "selected" : id === openedId ? "opened" : "default";
        entry.marker.setIcon({
          ...markerContent(entry.order, state),
          anchor: new maps.Point(22, 44),
        });
        entry.marker.setZIndex(state === "selected" ? 30 : state === "opened" ? 20 : 10);
      }
    },
    setUserLocation(point: MapPoint | null) {
      userMarker?.setMap(null);
      userMarker = undefined;
      if (!point) return;
      userMarker = new maps.Marker({
        map,
        position: new maps.LatLng(point.latitude, point.longitude),
        title: "내 위치",
        icon: {
          content:
            '<span aria-hidden="true" style="display:block;width:20px;height:20px;border:4px solid #fff;border-radius:50%;background:#7657d5;box-shadow:0 4px 14px rgba(21,47,41,.10)"></span>',
          anchor: new maps.Point(10, 10),
        },
      });
    },
    destroy() {
      listeners.forEach((listener) => maps.Event.removeListener(listener));
      initialLocationMarker?.setMap(null);
      userMarker?.setMap(null);
      markers.forEach(({ marker }) => marker.setMap(null));
      zones.forEach((zone) => zone.setMap(null));
      map.destroy();
    },
  };
}

export type NaverMapController = Awaited<ReturnType<typeof createNaverMap>>;
