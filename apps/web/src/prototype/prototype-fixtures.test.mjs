import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { after, test } from "node:test";

import { createServer } from "vite";

const vite = await createServer({
  appType: "custom",
  configFile: false,
  logLevel: "silent",
  root: process.cwd(),
  server: { middlewareMode: true },
});

const [{ AREA_FIXTURES, ANALYSIS_FIXTURE }, { SPOT_FIXTURES }, calculations, sourcePolicy, validation, providers] = await Promise.all([
  vite.ssrLoadModule("/src/prototype/area-fixtures.ts"),
  vite.ssrLoadModule("/src/prototype/spot-fixtures.ts"),
  vite.ssrLoadModule("/src/prototype/prototype-calculations.ts"),
  vite.ssrLoadModule("/src/prototype/prototype-source-policy.ts"),
  vite.ssrLoadModule("/src/prototype/prototype-validation.ts"),
  vite.ssrLoadModule("/src/data/freshmanager-data-provider.ts"),
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

test("fixture mode selects a static provider and performs zero API requests", async () => {
  let apiRequests = 0;
  const apiProvider = new providers.ApiDataProvider(
    async () => {
      apiRequests += 1;
      throw new Error("unexpected Area API request");
    },
    async () => {
      apiRequests += 1;
      throw new Error("unexpected pilot-view API request");
    },
  );
  const provider = providers.selectFreshManagerDataProvider("fixture", apiProvider);

  const areas = await provider.listAreas();
  const views = await Promise.all(
    areas.areas.map((area) => provider.getPilotView(area.area_code)),
  );

  assert.equal(provider instanceof providers.StaticPrototypeProvider, true);
  assert.equal(apiRequests, 0);
  assert.equal(areas.areas.length, 5);
  assert.equal(views.flatMap((view) => view.spot_options).length, 15);
});

test("static provider preserves the five canonical Area and fifteen Spot identities", async () => {
  const provider = new providers.StaticPrototypeProvider();
  const areas = await provider.listAreas();
  assert.deepEqual(
    areas.areas.map(({ area_code, area_name, display_order }) => ({ area_code, area_name, display_order })),
    [
      { area_code: "POI032", area_name: "서울식물원·마곡나루역", display_order: 1 },
      { area_code: "POI088", area_name: "광화문광장", display_order: 2 },
      { area_code: "POI014", area_name: "강남역", display_order: 3 },
      { area_code: "POI025", area_name: "뚝섬역", display_order: 4 },
      { area_code: "POI072", area_name: "여의도", display_order: 5 },
    ],
  );

  const views = await Promise.all(
    areas.areas.map((area) => provider.getPilotView(area.area_code)),
  );
  const spots = views.flatMap((view) => view.spot_options);
  assert.equal(new Set(spots.map((spot) => spot.spot_option_id)).size, 15);
  assert.deepEqual(
    spots.map((spot) => spot.spot_option_id),
    SPOT_FIXTURES.map((spot) => spot.spot_option_id),
  );
  for (const view of views) {
    assert.equal(view.spot_options.length, 3);
    assert.deepEqual(view.spot_options.map((spot) => spot.display_order), [1, 2, 3]);
    assert.equal(view.spot_options.every((spot) => Number.isFinite(spot.latitude) && Number.isFinite(spot.longitude)), true);
    assert.equal(view.spot_options.every((spot) => spot.current_population === null), true);
    assert.equal(view.area.current_population, null);
  }

  const csv = readFileSync(
    resolve(process.cwd(), "../../data/prototype/pilot_spot_options.csv"),
    "utf8",
  ).trim().split(/\r?\n/).map((line) => line.split(","));
  const headers = csv[0];
  assert.equal(headers.length, 20);
  assert.equal(csv.slice(1).every((row) => row.length === headers.length), true);
  const column = (name) => headers.indexOf(name);
  const expected = csv.slice(1).map((row) => ({
    area_code: row[column("pilot_area_code")],
    spot_option_id: row[column("spot_option_id")],
    spot_name: row[column("spot_name")],
    spot_type: row[column("spot_type")],
    address: row[column("address")],
    latitude: Number(row[column("latitude")]),
    longitude: Number(row[column("longitude")]),
    display_order: Number(row[column("display_order")]),
    field_verification_status: row[column("field_verification_status")],
    operational_suitability_status: row[column("operational_suitability_status")],
  }));
  const actual = views.flatMap((view) => view.spot_options.map((spot) => ({
    area_code: view.area.area_code,
    spot_option_id: spot.spot_option_id,
    spot_name: spot.spot_name,
    spot_type: spot.spot_type,
    address: spot.address,
    latitude: spot.latitude,
    longitude: spot.longitude,
    display_order: spot.display_order,
    field_verification_status: spot.field_verification_status,
    operational_suitability_status: spot.operational_suitability_status,
  })));
  assert.deepEqual(actual, expected);
});

test("official mode preserves the API provider and unsupported Area fails closed", async () => {
  const requestedAreas = [];
  const apiProvider = new providers.ApiDataProvider(
    async () => ({ areas: [], selection_mode: "USER_CHOICE" }),
    async (areaCode) => {
      requestedAreas.push(areaCode);
      return { area: { area_code: areaCode } };
    },
  );

  assert.equal(
    providers.selectFreshManagerDataProvider("official", apiProvider),
    apiProvider,
  );
  await apiProvider.getPilotView("POI032");
  assert.deepEqual(requestedAreas, ["POI032"]);
  assert.throws(
    () => providers.selectFreshManagerDataProvider("typo", apiProvider),
    /DATA_MODE_UNAVAILABLE/,
  );
  await assert.rejects(
    new providers.StaticPrototypeProvider().getPilotView("POI999"),
    /AREA_NOT_SUPPORTED/,
  );
});

test("static responses contain no score, rank, or automatic recommendation fields", async () => {
  const provider = new providers.StaticPrototypeProvider();
  const areas = await provider.listAreas();
  for (const area of areas.areas) {
    const view = await provider.getPilotView(area.area_code);
    const keys = Object.keys(view).concat(
      Object.keys(view.area),
      ...view.spot_options.map((spot) => Object.keys(spot)),
    );
    assert.equal(keys.some((key) => /score|rank/i.test(key)), false);
    assert.equal(view.area_auto_recommendation, false);
    assert.equal(view.spot_auto_recommendation, false);
    assert.equal(view.official_recommendation_allowed, false);
  }
});
