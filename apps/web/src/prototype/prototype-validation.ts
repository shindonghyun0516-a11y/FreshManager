import { ANALYSIS_FIXTURE, AREA_FIXTURES } from "./area-fixtures";
import { midpoint } from "./prototype-calculations";
import { SPOT_FIXTURES } from "./spot-fixtures";
import type { AnalysisFixture, ApiSpotIdentity, AreaFixture, PopulationRange, PrototypeDataMode, SpotFixture } from "./prototype-types";

const AREA_CODES = ["POI032", "POI088", "POI014", "POI025", "POI072"] as const;
const HORIZONS = [60, 120, 180] as const;
const TIME_BUCKETS = ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00"] as const;
const SPOT_FORBIDDEN_FIELDS = ["name", "address", "latitude", "longitude", "coordinate"] as const;
const SPOT_TIME_FIELDS = ["observed_at_label", "reference_time_label"] as const;

function fail(message: string): never {
  throw new Error(`prototype_fixture_invalid: ${message}`);
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) fail(message);
}

function range(min: number, max: number): PopulationRange {
  return { min, max };
}

function assertRange(value: PopulationRange, context: string): void {
  assert(Number.isFinite(value.min) && Number.isFinite(value.max), `${context}_not_finite`);
  assert(value.min >= 0 && value.max >= 0 && value.min < value.max, `${context}_range_invalid`);
}

function minutes(value: string): number {
  const match = /^(\d{2}):(\d{2})$/.exec(value);
  assert(match && Number(match[1]) < 24 && Number(match[2]) < 60, `time_invalid:${value}`);
  return Number(match[1]) * 60 + Number(match[2]);
}

function assertPeakConsistency(area: AreaFixture): void {
  const highestMidpoint = Math.max(...area.time_buckets.map((bucket) => midpoint(range(bucket.population_min, bucket.population_max))));
  for (const peak of area.repeated_peaks) {
    const start = minutes(peak.start_time);
    const end = minutes(peak.end_time);
    assert(start < end, `${area.area_code}_peak_order_invalid`);
    assert(peak.occurrence_count >= 1 && peak.occurrence_count <= 14, `${area.area_code}_peak_occurrence_invalid`);
    assert(
      area.time_buckets.some((bucket) => {
        const time = minutes(bucket.time_label);
        return start <= time && time <= end && midpoint(range(bucket.population_min, bucket.population_max)) >= highestMidpoint * 0.9;
      }),
      `${area.area_code}_peak_not_near_high_bucket`,
    );
  }
}

function assertAreaPattern(area: AreaFixture): void {
  const current = range(area.population_min, area.population_max);
  const forecasts = new Map(area.forecasts.map((forecast) => [forecast.horizon_minutes, range(forecast.population_min, forecast.population_max)]));
  const [at60, at120, at180] = HORIZONS.map((horizon) => forecasts.get(horizon));
  assert(at60 && at120 && at180, `${area.area_code}_forecast_missing`);
  const currentMidpoint = midpoint(current);
  const values = [midpoint(at60), midpoint(at120), midpoint(at180)];
  assert(values.every((value) => {
    const rate = (value - currentMidpoint) / currentMidpoint;
    return rate >= -0.25 && rate <= 0.3;
  }), `${area.area_code}_forecast_change_out_of_range`);
  const [first, second, third] = values;
  const isExpected = {
    POI032: first > currentMidpoint && second < first && third < second,
    POI088: first > currentMidpoint && second < first && third < second,
    POI014: currentMidpoint < first && first < second && second < third,
    POI025: first > currentMidpoint && second > first && third < second,
    POI072: first < currentMidpoint && second > first && third > second,
  }[area.area_code];
  assert(isExpected, `${area.area_code}_pattern_invalid`);
}

function assertSpotFixture(spot: SpotFixture): void {
  const record = spot as Record<string, unknown>;
  for (const field of SPOT_FORBIDDEN_FIELDS) assert(!(field in record), `${spot.spot_option_id}_forbidden_${field}`);
  for (const field of SPOT_TIME_FIELDS) assert(!(field in record), `${spot.spot_option_id}_duplicated_${field}`);
  const current = range(spot.current_population_min, spot.current_population_max);
  assertRange(current, `${spot.spot_option_id}_current`);
  assert(midpoint(current) >= 180 && midpoint(current) <= 900, `${spot.spot_option_id}_current_midpoint_out_of_range`);
  for (const horizon of HORIZONS) {
    const forecast = range(spot[`forecast_${horizon}_min`], spot[`forecast_${horizon}_max`]);
    assertRange(forecast, `${spot.spot_option_id}_${horizon}`);
  }
  assert(spot.input_method_label === "화면 검토용", `${spot.spot_option_id}_input_method_invalid`);
}

function areaRanges(area: AreaFixture): readonly PopulationRange[] {
  return [
    range(area.population_min, area.population_max),
    ...HORIZONS.map((horizon) => {
      const forecast = area.forecasts.find((candidate) => candidate.horizon_minutes === horizon);
      assert(forecast, `${area.area_code}_${horizon}_forecast_missing`);
      return range(forecast.population_min, forecast.population_max);
    }),
  ];
}

function spotRanges(spot: SpotFixture): readonly PopulationRange[] {
  return [
    range(spot.current_population_min, spot.current_population_max),
    ...HORIZONS.map((horizon) => range(spot[`forecast_${horizon}_min`], spot[`forecast_${horizon}_max`])),
  ];
}

export function assertStaticPrototypeFixtures(
  areas: readonly AreaFixture[] = AREA_FIXTURES,
  spots: readonly SpotFixture[] = SPOT_FIXTURES,
  analysis: AnalysisFixture = ANALYSIS_FIXTURE,
): void {
  assert(areas.length === AREA_CODES.length, "area_count_invalid");
  assert(new Set(areas.map((area) => area.area_code)).size === AREA_CODES.length, "area_code_duplicate");
  assert(AREA_CODES.every((code) => areas.some((area) => area.area_code === code)), "area_code_invalid");
  assert(analysis.analysis_period_label === "14일" && analysis.analysis_basis_label === "평일·주말 포함", "analysis_label_invalid");
  assert(analysis.observations_per_time_bucket === 14 && analysis.time_bucket_count === 6 && analysis.total_observation_points === 84, "analysis_count_invalid");
  assert(analysis.observations_per_time_bucket * analysis.time_bucket_count === analysis.total_observation_points, "analysis_total_invalid");

  for (const area of areas) {
    const current = range(area.population_min, area.population_max);
    assertRange(current, `${area.area_code}_current`);
    assert(midpoint(current) >= 3_000 && midpoint(current) <= 9_000, `${area.area_code}_current_midpoint_out_of_range`);
    assert(area.reference_time_label === "14:00", `${area.area_code}_reference_time_invalid`);
    assert(new Set(area.forecasts.map((forecast) => forecast.horizon_minutes)).size === HORIZONS.length, `${area.area_code}_forecast_duplicate`);
    assert(HORIZONS.every((horizon) => area.forecasts.some((forecast) => forecast.horizon_minutes === horizon)), `${area.area_code}_forecast_horizon_invalid`);
    assert(area.forecasts.every((forecast, index) => forecast.horizon_minutes === HORIZONS[index]), `${area.area_code}_forecast_order_invalid`);
    for (const forecast of area.forecasts) {
      assertRange(range(forecast.population_min, forecast.population_max), `${area.area_code}_${forecast.horizon_minutes}`);
      assert(forecast.target_time_label === `${forecast.horizon_minutes}분 후`, `${area.area_code}_${forecast.horizon_minutes}_target_label_invalid`);
    }
    assert(area.time_buckets.length === TIME_BUCKETS.length && new Set(area.time_buckets.map((bucket) => bucket.time_label)).size === TIME_BUCKETS.length, `${area.area_code}_time_bucket_count_invalid`);
    assert(TIME_BUCKETS.every((time) => area.time_buckets.some((bucket) => bucket.time_label === time)), `${area.area_code}_time_bucket_invalid`);
    for (const bucket of area.time_buckets) assertRange(range(bucket.population_min, bucket.population_max), `${area.area_code}_${bucket.time_label}`);
    assert(area.repeated_peaks.length === 2, `${area.area_code}_peak_count_invalid`);
    assertPeakConsistency(area);
    assertAreaPattern(area);
  }

  assert(spots.length === 15, "spot_count_invalid");
  assert(new Set(spots.map((spot) => spot.spot_option_id)).size === spots.length, "spot_id_duplicate");
  for (const areaCode of AREA_CODES) {
    const area = areas.find((candidate) => candidate.area_code === areaCode);
    const areaSpots = spots.filter((spot) => spot.area_code === areaCode);
    assert(area && areaSpots.length === 3, `${areaCode}_spot_count_invalid`);
    const expectedAreaRanges = areaRanges(area);
    assert(
      new Set(areaSpots.map((spot) => `${spot.current_population_min}:${spot.current_population_max}`)).size === 3,
      `${areaCode}_spot_current_values_not_distinct`,
    );
    assert(
      areaSpots.every((spot) => spotRanges(spot).every((spotRange, index) => {
        const areaRange = expectedAreaRanges[index];
        const isCopy = spotRange.min === areaRange.min && spotRange.max === areaRange.max;
        const isThird = spotRange.min * 3 === areaRange.min && spotRange.max * 3 === areaRange.max;
        return !isCopy && !isThird;
      })),
      `${areaCode}_spot_values_copy_area`,
    );
  }
  for (const spot of spots) assertSpotFixture(spot);
}

export function assertApiSpotIdentity(areaCode: string, apiSpots: readonly ApiSpotIdentity[]): void {
  const expected = SPOT_FIXTURES.filter((spot) => spot.area_code === areaCode).map((spot) => spot.spot_option_id);
  const received = apiSpots.map((spot) => spot.spot_option_id);
  const receivedSet = new Set(received);
  if (
    expected.length !== 3 || received.length !== 3 || receivedSet.size !== received.length ||
    expected.some((id) => !receivedSet.has(id)) || received.some((id) => !expected.includes(id))
  ) {
    throw new Error(`prototype_spot_identity_mismatch:${areaCode}: expected=${expected.join(",")} received=${received.join(",")}`);
  }
}

export function resolvePrototypeDataMode(explicitValue: string | undefined, isDev: boolean): PrototypeDataMode {
  if (explicitValue === "fixture" || explicitValue === "unavailable" || explicitValue === "official") return explicitValue;
  if (explicitValue !== undefined && explicitValue !== "") fail(`data_mode_invalid:${explicitValue}`);
  return isDev ? "fixture" : "unavailable";
}
