export type MapSpot = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  displayOrder: number;
};

export type MapPoint = { latitude: number; longitude: number };

type NaverMarker = {
  setIcon(icon: { content: string; anchor: NaverPoint }): void;
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

function loadMaps(clientId: string): Promise<NaverMaps> {
  if (window.naver?.maps) return Promise.resolve(window.naver.maps);
  if (loader) return loader;

  loader = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      "script[data-freshmanager-naver-map]",
    );
    const script = existing ?? document.createElement("script");

    const finish = () =>
      window.naver?.maps
        ? resolve(window.naver.maps)
        : reject(new Error("NAVER_MAP_UNAVAILABLE"));

    script.addEventListener("load", finish, { once: true });
    script.addEventListener(
      "error",
      () => reject(new Error("NAVER_MAP_UNAVAILABLE")),
      { once: true },
    );

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
  const background = selected ? "#5b21b6" : state === "opened" ? "#0f766e" : "#ffffff";
  const color = state === "default" ? "#0f4f4a" : "#ffffff";
  const border = selected ? "#ffffff" : "#0f766e";
  return {
    content: `<span aria-hidden="true" style="display:grid;place-items:center;width:42px;height:42px;border:3px solid ${border};border-radius:50% 50% 50% 8px;background:${background};color:${color};font:800 15px/1 system-ui;box-shadow:0 6px 16px rgba(15,49,46,.25);transform:rotate(-45deg)"><span style="transform:rotate(45deg)">${selected ? "✓" : order}</span></span>`,
  };
}

export async function createNaverMap(
  element: HTMLElement,
  clientId: string,
  spots: MapSpot[],
  onSpotClick: (spotId: string) => void,
) {
  if (!clientId || spots.length === 0) throw new Error("NAVER_MAP_UNAVAILABLE");

  const maps = await loadMaps(clientId);
  const center = new maps.LatLng(spots[0].latitude, spots[0].longitude);
  const map = new maps.Map(element, {
    center,
    zoom: 14,
    minZoom: 10,
    zoomControl: true,
  });
  const bounds = new maps.LatLngBounds();
  const listeners: object[] = [];
  const markers = new Map<string, { marker: NaverMarker; order: number }>();

  for (const spot of spots) {
    const position = new maps.LatLng(spot.latitude, spot.longitude);
    bounds.extend(position);
    const marker = new maps.Marker({
      map,
      position,
      title: spot.name,
      icon: {
        ...markerContent(spot.displayOrder, "default"),
        anchor: new maps.Point(21, 42),
      },
    });
    listeners.push(
      maps.Event.addListener(marker, "click", () => onSpotClick(spot.id)),
    );
    markers.set(spot.id, { marker, order: spot.displayOrder });
  }

  map.fitBounds(bounds, { top: 80, right: 80, bottom: 100, left: 80 });

  let userMarker: NaverMarker | undefined;

  return {
    setMarkerState(openedId: string | null, selectedId: string | null) {
      for (const [id, entry] of markers) {
        const state = id === selectedId ? "selected" : id === openedId ? "opened" : "default";
        entry.marker.setIcon({
          ...markerContent(entry.order, state),
          anchor: new maps.Point(21, 42),
        });
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
            '<span aria-hidden="true" style="display:block;width:20px;height:20px;border:4px solid #fff;border-radius:50%;background:#6d28d9;box-shadow:0 3px 12px rgba(30,20,70,.35)"></span>',
          anchor: new maps.Point(10, 10),
        },
      });
    },
    destroy() {
      listeners.forEach((listener) => maps.Event.removeListener(listener));
      userMarker?.setMap(null);
      markers.forEach(({ marker }) => marker.setMap(null));
      map.destroy();
    },
  };
}

export type NaverMapController = Awaited<ReturnType<typeof createNaverMap>>;
