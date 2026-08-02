import assert from "node:assert/strict";
import { after, test } from "node:test";

import { createServer } from "vite";

const vite = await createServer({
  appType: "custom",
  configFile: false,
  logLevel: "silent",
  root: process.cwd(),
  server: { middlewareMode: true },
});

const [{ AREA_FIXTURES, ANALYSIS_FIXTURE }, { SPOT_FIXTURES }, calculations, sourcePolicy, validation] = await Promise.all([
  vite.ssrLoadModule("/src/prototype/area-fixtures.ts"),
  vite.ssrLoadModule("/src/prototype/spot-fixtures.ts"),
  vite.ssrLoadModule("/src/prototype/prototype-calculations.ts"),
  vite.ssrLoadModule("/src/prototype/prototype-source-policy.ts"),
  vite.ssrLoadModule("/src/prototype/prototype-validation.ts"),
]);

after(() => vite.close());

test("static prototype fixtures meet the five-Area display contract", () => {
  assert.doesNotThrow(() => validation.assertStaticPrototypeFixtures());
  assert.throws(
    () => validation.assertStaticPrototypeFixtures(AREA_FIXTURES.slice(1), SPOT_FIXTURES, ANALYSIS_FIXTURE),
    /area_count_invalid/,
  );
  assert.deepEqual(
    AREA_FIXTURES.map((area) => area.area_code),
    ["POI032", "POI088", "POI014", "POI025", "POI072"],
  );
  assert.equal(SPOT_FIXTURES.length, 15);
  assert.equal(ANALYSIS_FIXTURE.total_observation_points, 84);
  assert.deepEqual(
    AREA_FIXTURES.map((area) => area.reference_time_label),
    ["14:00", "14:00", "14:00", "14:00", "14:00"],
  );
  assert.equal(
    SPOT_FIXTURES.every(
      (spot) => !("reference_time_label" in spot) && !("observed_at_label" in spot),
    ),
    true,
  );
});

test("Area forecast slots keep the display order 60, 120, 180", () => {
  const reorderedArea = {
    ...AREA_FIXTURES[0],
    forecasts: [...AREA_FIXTURES[0].forecasts].reverse(),
  };
  assert.throws(
    () => validation.assertStaticPrototypeFixtures(
      [reorderedArea, ...AREA_FIXTURES.slice(1)],
      SPOT_FIXTURES,
      ANALYSIS_FIXTURE,
    ),
    /forecast_order_invalid/,
  );
});

test("population calculations use range midpoints and preserve a zero-base null rate", () => {
  assert.deepEqual(calculations.calculatePopulationChange({ min: 200, max: 400 }, { min: 300, max: 500 }), {
    amount: 100,
    rate: 100 / 300,
  });
  assert.deepEqual(calculations.calculatePopulationChange({ min: 0, max: 0 }, { min: 10, max: 20 }), {
    amount: 15,
    rate: null,
  });
  assert.equal(calculations.midpoint({ min: 180, max: 900 }), 540);
});

test("runtime Spot identity validation accepts exactly the selected Area's three API IDs", () => {
  assert.doesNotThrow(() =>
    validation.assertApiSpotIdentity("POI014", [
      { spot_option_id: "POI014-OPT-01" },
      { spot_option_id: "POI014-OPT-02" },
      { spot_option_id: "POI014-OPT-03" },
    ]),
  );
  assert.throws(
    () => validation.assertApiSpotIdentity("POI014", [{ spot_option_id: "POI014-OPT-01" }]),
    /prototype_spot_identity_mismatch/,
  );
});

test("Spot fixtures keep identity-only keys and distinct values within each Area", () => {
  const forbiddenFields = ["name", "address", "latitude", "longitude", "coordinate"];
  for (const fixture of SPOT_FIXTURES) {
    for (const field of forbiddenFields) assert.equal(field in fixture, false);
  }
  for (const area of AREA_FIXTURES) {
    const spots = SPOT_FIXTURES.filter((spot) => spot.area_code === area.area_code);
    assert.equal(new Set(spots.map((spot) => `${spot.current_population_min}:${spot.current_population_max}`)).size, 3);
    assert.equal(spots.some((spot) => spot.current_population_min === area.population_min && spot.current_population_max === area.population_max), false);
  }
});

test("prototype data mode is explicit first, then uses only the build environment default", () => {
  assert.equal(validation.resolvePrototypeDataMode("fixture", false), "fixture");
  assert.equal(validation.resolvePrototypeDataMode("unavailable", true), "unavailable");
  assert.equal(validation.resolvePrototypeDataMode("official", false), "official");
  assert.equal(validation.resolvePrototypeDataMode(undefined, true), "fixture");
  assert.equal(validation.resolvePrototypeDataMode(undefined, false), "unavailable");
  assert.throws(() => validation.resolvePrototypeDataMode("typo", true), /data_mode_invalid/);
});

test("fixture source policy rejects runtime imports and generated values", () => {
  assert.doesNotThrow(() =>
    sourcePolicy.assertPrototypeFixtureSource(
      "area-fixtures.ts",
      'import type { AreaFixture } from "./prototype-types";\nexport const AREAS: readonly AreaFixture[] = [];',
    ),
  );
  assert.throws(
    () => sourcePolicy.assertPrototypeFixtureSource("area-fixtures.ts", 'import { rows } from "../../actual-data";'),
    /runtime_import_forbidden/,
  );
  assert.throws(
    () => sourcePolicy.assertPrototypeFixtureSource("spot-fixtures.ts", "export const value = Math.random();"),
    /generated_value_forbidden/,
  );
});
