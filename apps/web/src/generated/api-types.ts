// Generated from FastAPI OpenAPI. Do not edit manually.

export type HealthResponse = {
  service: "freshmanager-api";
  status: "ok";
};

export type ErrorDetail = {
  code: string;
  message: string;
};

export type ErrorResponse = {
  error: ErrorDetail;
};

export type AreaListItem = {
  area_code: string;
  area_name: string;
  display_order: number;
  selection_mode: "USER_CHOICE";
};

export type AreasResponse = {
  areas: AreaListItem[];
  selection_mode: "USER_CHOICE";
};

export type PopulationRange = {
  max: number;
  min: number;
};

export type AreaPilotData = {
  area_code: string;
  area_name: string;
  availability: "DATA_UNAVAILABLE";
  change_amount_180: number | null;
  change_amount_60: number | null;
  change_rate_180: number | null;
  change_rate_60: number | null;
  congestion_level: string | null;
  current_population: PopulationRange | null;
  forecast_180: PopulationRange | null;
  forecast_180_congestion_level: string | null;
  forecast_180_target_at: string | null;
  forecast_60: PopulationRange | null;
  forecast_60_congestion_level: string | null;
  forecast_60_target_at: string | null;
  freshness: "NO_COMPLETE_SNAPSHOT";
  observed_at: string | null;
  source: string | null;
};

export type SpotOption = {
  address: string;
  change_amount_180: number | null;
  change_amount_60: number | null;
  change_rate_180: number | null;
  change_rate_60: number | null;
  current_population: PopulationRange | null;
  data_status: "PROTOTYPE" | null;
  display_order: number;
  field_verification_status: "UNAVAILABLE";
  forecast_180: PopulationRange | null;
  forecast_60: PopulationRange | null;
  input_method: "PM_MANUAL" | null;
  latitude: number;
  limitations: string[];
  longitude: number;
  observed_at: string | null;
  operational_suitability_status: "NOT_VERIFIED";
  prototype_data_status: "PROTOTYPE" | "SPOT_PROTOTYPE_DATA_UNAVAILABLE";
  spot_name: string;
  spot_option_id: string;
  spot_population_source: "PM_MANUAL_PROTOTYPE" | null;
  spot_type: string;
  updated_at: string | null;
};

export type AreaPilotResponse = {
  area: AreaPilotData;
  area_auto_recommendation: false;
  area_selection_mode: "USER_CHOICE";
  machine_learning_used_for_recommendation: false;
  official_recommendation_allowed: false;
  spot_auto_recommendation: false;
  spot_options: SpotOption[];
  spot_selection_mode: "USER_CHOICE";
  view_status: "DATA_UNAVAILABLE";
  warnings: string[];
};
