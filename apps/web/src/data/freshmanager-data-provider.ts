import type {
  AreaPilotResponse,
  AreasResponse,
  SpotOption,
} from "../generated/api-types";
import type { PrototypeDataMode } from "../prototype/prototype-types";

export type FreshManagerDataProvider = Readonly<{
  listAreas: () => Promise<AreasResponse>;
  getPilotView: (
    areaCode: string,
    signal?: AbortSignal,
  ) => Promise<AreaPilotResponse>;
}>;

type AreaListRequest = () => Promise<AreasResponse>;
type PilotViewRequest = (
  areaCode: string,
  signal?: AbortSignal,
) => Promise<AreaPilotResponse>;

const STATIC_AREAS = [
  ["POI032", "서울식물원·마곡나루역"],
  ["POI088", "광화문광장"],
  ["POI014", "강남역"],
  ["POI025", "뚝섬역"],
  ["POI072", "여의도"],
] as const;

const STATIC_SPOTS = [
  ["POI032", "POI032-OPT-01", "서울식물원 열린숲", "PARK_ZONE", "대한민국 서울특별시 강서구 가양제1동 678 서울식물원 열린숲", 37.5658219, 126.831933, 1],
  ["POI032", "POI032-OPT-02", "서울식물원 식물문화센터", "VENUE", "서울 강서구 마곡동 812", 37.5693507823043, 126.835026023981, 2],
  ["POI032", "POI032-OPT-03", "서울식물원 호수원", "PARK_ZONE", "서울 강서구 마곡동 812", 37.57195751126966, 126.83194015080619, 3],
  ["POI088", "POI088-OPT-01", "육조마당", "PUBLIC_SPACE", "서울 종로구 세종로 1-68", 37.5741885600571, 126.97665327859869, 1],
  ["POI088", "POI088-OPT-02", "해치마당", "PUBLIC_SPACE", "서울 종로구 세종로 81-3", 37.57188566701743, 126.97690756151474, 2],
  ["POI088", "POI088-OPT-03", "광장숲", "PUBLIC_SPACE", "서울 종로구 세종로 1-68", 37.5708909077637, 126.976599973568, 3],
  ["POI014", "POI014-OPT-01", "강남스퀘어", "PUBLIC_SPACE", "서울 강남구 역삼동 804", 37.49835486341528, 127.02788728853392, 1],
  ["POI014", "POI014-OPT-02", "CGV강남 앞", "VENUE", "대한민국 서울특별시 강남구 강남대로 438 스타플렉스", 37.5015586, 127.026319, 2],
  ["POI014", "POI014-OPT-03", "점프밀라노 앞", "VENUE", "대한민국 서울특별시 강남구 역삼동 619-4", 37.5012103, 127.0266055, 3],
  ["POI025", "POI025-OPT-01", "뚝섬역 4번 출구", "TRANSIT_EXIT", "서울 성동구 성수동1가 14-17", 37.54687689826925, 127.04898713589128, 1],
  ["POI025", "POI025-OPT-02", "뚝섬역 6번 출구", "TRANSIT_EXIT", "서울 성동구 성수동1가 656-284", 37.54683220890765, 127.04811011414718, 2],
  ["POI025", "POI025-OPT-03", "뚝섬역 8번 출구", "TRANSIT_EXIT", "서울 성동구 성수동1가 656-853", 37.54753582441832, 127.04601142262756, 3],
  ["POI072", "POI072-OPT-01", "여의도공원 문화의마당", "PARK_ZONE", "서울 영등포구 여의도동 17", 37.524630704323, 126.920336120685, 1],
  ["POI072", "POI072-OPT-02", "여의도공원 잔디마당", "PARK_ZONE", "서울 영등포구 여의도동 1", 37.5307652481477, 126.915894664452, 2],
  ["POI072", "POI072-OPT-03", "여의도공원 자연생태의숲", "PARK_ZONE", "서울 영등포구 여의도동 1-10", 37.5233674712091, 126.91766771733, 3],
] as const;

const LIMITATIONS = [
  "실제 판매 허용 여부는 현장 확인이 필요합니다.",
  "접근성을 현장에서 확인해야 합니다.",
  "안전성을 현장에서 확인해야 합니다.",
  "카트 정차 가능성을 현장에서 확인해야 합니다.",
  "시간대별 운영 가능성을 현장에서 확인해야 합니다.",
] as const;

function staticSpot(
  row: (typeof STATIC_SPOTS)[number],
): SpotOption {
  const [, spotOptionId, spotName, spotType, address, latitude, longitude, displayOrder] = row;
  return {
    address,
    change_amount_180: null,
    change_amount_60: null,
    change_rate_180: null,
    change_rate_60: null,
    current_population: null,
    data_status: null,
    display_order: displayOrder,
    field_verification_status: "UNAVAILABLE",
    forecast_180: null,
    forecast_60: null,
    input_method: null,
    latitude,
    limitations: [...LIMITATIONS],
    longitude,
    observed_at: null,
    operational_suitability_status: "NOT_VERIFIED",
    prototype_data_status: "SPOT_PROTOTYPE_DATA_UNAVAILABLE",
    spot_name: spotName,
    spot_option_id: spotOptionId,
    spot_population_source: null,
    spot_type: spotType,
    updated_at: null,
  };
}

export class StaticPrototypeProvider implements FreshManagerDataProvider {
  async listAreas(): Promise<AreasResponse> {
    return {
      areas: STATIC_AREAS.map(([area_code, area_name], index) => ({
        area_code,
        area_name,
        display_order: index + 1,
        selection_mode: "USER_CHOICE",
      })),
      selection_mode: "USER_CHOICE",
    };
  }

  async getPilotView(
    areaCode: string,
    signal?: AbortSignal,
  ): Promise<AreaPilotResponse> {
    signal?.throwIfAborted();
    const area = STATIC_AREAS.find(([code]) => code === areaCode);
    if (!area) throw new Error("AREA_NOT_SUPPORTED");

    return {
      area: {
        area_code: area[0],
        area_name: area[1],
        availability: "DATA_UNAVAILABLE",
        change_amount_180: null,
        change_amount_60: null,
        change_rate_180: null,
        change_rate_60: null,
        congestion_level: null,
        current_population: null,
        forecast_180: null,
        forecast_180_congestion_level: null,
        forecast_180_target_at: null,
        forecast_60: null,
        forecast_60_congestion_level: null,
        forecast_60_target_at: null,
        freshness: "NO_COMPLETE_SNAPSHOT",
        observed_at: null,
        source: null,
      },
      area_auto_recommendation: false,
      area_selection_mode: "USER_CHOICE",
      machine_learning_used_for_recommendation: false,
      official_recommendation_allowed: false,
      spot_auto_recommendation: false,
      spot_options: STATIC_SPOTS.filter(([code]) => code === areaCode).map(staticSpot),
      spot_selection_mode: "USER_CHOICE",
      view_status: "DATA_UNAVAILABLE",
      warnings: ["DATA_UNAVAILABLE", "SPOT_PROTOTYPE_DATA_UNAVAILABLE"],
    };
  }
}

export class ApiDataProvider implements FreshManagerDataProvider {
  constructor(
    private readonly areaListRequest: AreaListRequest,
    private readonly pilotViewRequest: PilotViewRequest,
  ) {}

  listAreas(): Promise<AreasResponse> {
    return this.areaListRequest();
  }

  getPilotView(
    areaCode: string,
    signal?: AbortSignal,
  ): Promise<AreaPilotResponse> {
    return this.pilotViewRequest(areaCode, signal);
  }
}

export function selectFreshManagerDataProvider(
  mode: PrototypeDataMode,
  apiProvider: ApiDataProvider,
): FreshManagerDataProvider {
  if (mode === "fixture") return new StaticPrototypeProvider();
  if (mode === "official" || mode === "unavailable") return apiProvider;
  throw new Error("DATA_MODE_UNAVAILABLE");
}
