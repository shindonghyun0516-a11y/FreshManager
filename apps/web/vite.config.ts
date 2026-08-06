import { readFileSync } from "node:fs";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { assertPrototypeFixtureSource } from "./src/prototype/prototype-source-policy";

for (const [fileName, fileUrl] of [
  ["area-fixtures.ts", new URL("./src/prototype/area-fixtures.ts", import.meta.url)],
  ["spot-fixtures.ts", new URL("./src/prototype/spot-fixtures.ts", import.meta.url)],
] as const) {
  assertPrototypeFixtureSource(fileName, readFileSync(fileUrl, "utf8"));
}

export default defineConfig(async () => {
  const { assertStaticPrototypeFixtures } = await import("./src/prototype/prototype-validation");
  assertStaticPrototypeFixtures();
  return {
    plugins: [vue()],
    server: {
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: false,
        },
      },
    },
  };
});
