import type { AnalysisFixture, AreaFixture } from "./prototype-types";

export const ANALYSIS_FIXTURE: AnalysisFixture = {
  analysis_period_label: "14일",
  analysis_basis_label: "평일·주말 포함",
  observations_per_time_bucket: 14,
  time_bucket_count: 6,
  total_observation_points: 84,
};

export const AREA_FIXTURES: readonly AreaFixture[] = [
  {
    area_code: "POI032", population_min: 5_400, population_max: 6_300, congestion_level: "보통", reference_time_label: "14:00",
    forecasts: [{ horizon_minutes: 60, population_min: 6_700, population_max: 7_500, target_time_label: "60분 후" }, { horizon_minutes: 120, population_min: 6_100, population_max: 6_900, target_time_label: "120분 후" }, { horizon_minutes: 180, population_min: 4_700, population_max: 5_500, target_time_label: "180분 후" }],
    time_buckets: [{ time_label: "06:00", population_min: 3_400, population_max: 4_000 }, { time_label: "09:00", population_min: 4_800, population_max: 5_600 }, { time_label: "12:00", population_min: 6_700, population_max: 7_500 }, { time_label: "15:00", population_min: 5_800, population_max: 6_600 }, { time_label: "18:00", population_min: 6_400, population_max: 7_200 }, { time_label: "21:00", population_min: 4_400, population_max: 5_100 }],
    repeated_peaks: [{ start_time: "11:00", end_time: "13:00", occurrence_count: 12 }, { start_time: "17:00", end_time: "19:00", occurrence_count: 10 }],
  },
  {
    area_code: "POI088", population_min: 6_400, population_max: 7_400, congestion_level: "혼잡", reference_time_label: "14:00",
    forecasts: [{ horizon_minutes: 60, population_min: 7_500, population_max: 8_500, target_time_label: "60분 후" }, { horizon_minutes: 120, population_min: 6_600, population_max: 7_600, target_time_label: "120분 후" }, { horizon_minutes: 180, population_min: 5_200, population_max: 6_200, target_time_label: "180분 후" }],
    time_buckets: [{ time_label: "06:00", population_min: 3_600, population_max: 4_300 }, { time_label: "09:00", population_min: 5_700, population_max: 6_700 }, { time_label: "12:00", population_min: 7_500, population_max: 8_500 }, { time_label: "15:00", population_min: 6_300, population_max: 7_200 }, { time_label: "18:00", population_min: 7_000, population_max: 7_900 }, { time_label: "21:00", population_min: 4_500, population_max: 5_300 }],
    repeated_peaks: [{ start_time: "11:00", end_time: "13:00", occurrence_count: 13 }, { start_time: "17:00", end_time: "19:00", occurrence_count: 11 }],
  },
  {
    area_code: "POI014", population_min: 6_800, population_max: 7_800, congestion_level: "혼잡", reference_time_label: "14:00",
    forecasts: [{ horizon_minutes: 60, population_min: 7_600, population_max: 8_600, target_time_label: "60분 후" }, { horizon_minutes: 120, population_min: 8_400, population_max: 9_600, target_time_label: "120분 후" }, { horizon_minutes: 180, population_min: 8_700, population_max: 10_100, target_time_label: "180분 후" }],
    time_buckets: [{ time_label: "06:00", population_min: 3_800, population_max: 4_500 }, { time_label: "09:00", population_min: 5_900, population_max: 6_900 }, { time_label: "12:00", population_min: 7_700, population_max: 8_800 }, { time_label: "15:00", population_min: 7_400, population_max: 8_400 }, { time_label: "18:00", population_min: 8_300, population_max: 9_500 }, { time_label: "21:00", population_min: 5_300, population_max: 6_200 }],
    repeated_peaks: [{ start_time: "11:00", end_time: "13:00", occurrence_count: 12 }, { start_time: "17:00", end_time: "19:00", occurrence_count: 14 }],
  },
  {
    area_code: "POI025", population_min: 4_500, population_max: 5_200, congestion_level: "보통", reference_time_label: "14:00",
    forecasts: [{ horizon_minutes: 60, population_min: 5_300, population_max: 6_100, target_time_label: "60분 후" }, { horizon_minutes: 120, population_min: 5_800, population_max: 6_600, target_time_label: "120분 후" }, { horizon_minutes: 180, population_min: 4_700, population_max: 5_500, target_time_label: "180분 후" }],
    time_buckets: [{ time_label: "06:00", population_min: 2_700, population_max: 3_200 }, { time_label: "09:00", population_min: 3_900, population_max: 4_600 }, { time_label: "12:00", population_min: 5_500, population_max: 6_300 }, { time_label: "15:00", population_min: 4_800, population_max: 5_600 }, { time_label: "18:00", population_min: 5_200, population_max: 6_000 }, { time_label: "21:00", population_min: 3_600, population_max: 4_200 }],
    repeated_peaks: [{ start_time: "11:00", end_time: "13:00", occurrence_count: 11 }, { start_time: "17:00", end_time: "19:00", occurrence_count: 10 }],
  },
  {
    area_code: "POI072", population_min: 7_200, population_max: 8_200, congestion_level: "혼잡", reference_time_label: "14:00",
    forecasts: [{ horizon_minutes: 60, population_min: 5_800, population_max: 6_800, target_time_label: "60분 후" }, { horizon_minutes: 120, population_min: 6_000, population_max: 7_000, target_time_label: "120분 후" }, { horizon_minutes: 180, population_min: 7_200, population_max: 8_400, target_time_label: "180분 후" }],
    time_buckets: [{ time_label: "06:00", population_min: 3_900, population_max: 4_600 }, { time_label: "09:00", population_min: 5_800, population_max: 6_700 }, { time_label: "12:00", population_min: 7_800, population_max: 8_900 }, { time_label: "15:00", population_min: 6_800, population_max: 7_800 }, { time_label: "18:00", population_min: 7_500, population_max: 8_600 }, { time_label: "21:00", population_min: 4_900, population_max: 5_700 }],
    repeated_peaks: [{ start_time: "11:00", end_time: "13:00", occurrence_count: 13 }, { start_time: "17:00", end_time: "19:00", occurrence_count: 12 }],
  },
];
