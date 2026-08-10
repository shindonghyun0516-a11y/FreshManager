const TYPE_ONLY_FIXTURE_IMPORT = /^\s*import\s+type\s+\{[^}]+\}\s+from\s+["']\.\/prototype-types["'];?\s*$/;
const IMPORT_LINE = /^\s*import[^\n]*$/gm;
const GENERATED_VALUE = /=>|\b(?:function|class|new|await)\b|\b(?:Math|Date|process|global|globalThis|window|document|navigator|localStorage|sessionStorage|indexedDB|XMLHttpRequest)\b|\b[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*\s*\(/;

export function assertPrototypeFixtureSource(fileName: string, source: string): void {
  const imports = source.match(IMPORT_LINE) ?? [];
  if (!imports.every((line) => TYPE_ONLY_FIXTURE_IMPORT.test(line))) {
    throw new Error(`prototype_fixture_invalid: ${fileName}_runtime_import_forbidden`);
  }
  if (GENERATED_VALUE.test(source.replace(IMPORT_LINE, ""))) {
    throw new Error(`prototype_fixture_invalid: ${fileName}_generated_value_forbidden`);
  }
}
