export type PopulationRange = Readonly<{
  min: number;
  max: number;
}>;

export type ForecastFixture = Readonly<{
  horizon_minutes: 60 | 120 | 180;
  population_min: number;
  population_max: number;
  target_time_label: string;
}>;

export type TimeBucketFixture = Readonly<{
  time_label: "06:00" | "09:00" | "12:00" | "15:00" | "18:00" | "21:00";
  population_min: number;
  population_max: number;
}>;

export type RepeatedPeakFixture = Readonly<{
  start_time: string;
  end_time: string;
  occurrence_count: number;
}>;

export type AreaFixture = Readonly<{
  area_code: "POI032" | "POI088" | "POI014" | "POI025" | "POI072";
  population_min: number;
  population_max: number;
  congestion_level: string;
  reference_time_label: "14:00";
  forecasts: readonly ForecastFixture[];
  time_buckets: readonly TimeBucketFixture[];
  repeated_peaks: readonly RepeatedPeakFixture[];
}>;

export type SpotFixture = Readonly<{
  area_code: AreaFixture["area_code"];
  spot_option_id: string;
  current_population_min: number;
  current_population_max: number;
  forecast_60_min: number;
  forecast_60_max: number;
  forecast_120_min: number;
  forecast_120_max: number;
  forecast_180_min: number;
  forecast_180_max: number;
  input_method_label: "화면 검토용";
}>;

export type AnalysisFixture = Readonly<{
  analysis_period_label: "14일";
  analysis_basis_label: "평일·주말 포함";
  observations_per_time_bucket: 14;
  time_bucket_count: 6;
  total_observation_points: 84;
}>;

export type ApiSpotIdentity = Readonly<{
  spot_option_id: string;
}>;

export type PrototypeDataMode = "fixture" | "unavailable" | "official";
