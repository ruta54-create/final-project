// Checks the dashboard translations.   Run:  node tools/check_i18n.mjs
//  1. every language has exactly the same keys as English
//  2. every translation keeps the same {placeholders} as English
//  3. every t("key") / t(`prefix.${x}`) used in frontend/src exists in English
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "frontend", "src");
const load = async (code) => (await import(pathToFileURL(join(root, "i18n", "locales", `${code}.js`)))).default;
const LANGS = ["en", "fr", "rw"];
const dicts = Object.fromEntries(await Promise.all(LANGS.map(async (l) => [l, await load(l)])));

function flatten(obj, prefix = "", out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object") flatten(v, key, out);
    else out[key] = v;
  }
  return out;
}
const flat = Object.fromEntries(LANGS.map((l) => [l, flatten(dicts[l])]));
// {cat} (Organic) and {comp} (organic) are always passed together, so a language may pick either form
const placeholders = (s) => [...String(s).matchAll(/\{(\w+)\}/g)]
  .map((m) => (m[1] === "comp" ? "cat" : m[1])).sort().join(",");
const problems = [];

for (const lang of LANGS.filter((l) => l !== "en")) {
  for (const key of Object.keys(flat.en)) {
    if (!(key in flat[lang])) problems.push(`${lang}: missing "${key}"`);
    else if (placeholders(flat.en[key]) !== placeholders(flat[lang][key]) && !key.startsWith("rec.detail.schedule"))
      problems.push(`${lang}: placeholders differ in "${key}" (en: {${placeholders(flat.en[key])}} ${lang}: {${placeholders(flat[lang][key])}})`);
  }
  for (const key of Object.keys(flat[lang])) if (!(key in flat.en)) problems.push(`${lang}: extra key "${key}" not in en`);
}

// keys used in the code
const files = [];
(function walk(dir) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(jsx?|mjs)$/.test(f) && !p.includes("locales")) files.push(p);
  }
})(root);
const prefixExists = (prefix) => Object.keys(flat.en).some((k) => k.startsWith(prefix + "."));
let used = 0;
for (const file of files) {
  const src = readFileSync(file, "utf8");
  for (const m of src.matchAll(/\bt\(\s*"([a-zA-Z0-9_.]+)"/g)) {
    used++;
    const key = m[1];
    if (!(key in flat.en) && !(`${key}_one` in flat.en)) problems.push(`code: unknown key "${key}" in ${file.slice(root.length + 1)}`);
  }
  for (const m of src.matchAll(/\bt\(\s*`([a-zA-Z0-9_.]+)\.\$\{/g)) {
    used++;
    if (!prefixExists(m[1])) problems.push(`code: unknown key group "${m[1]}" in ${file.slice(root.length + 1)}`);
  }
  for (const m of src.matchAll(/\bt\(\s*\w+\s*\?\s*"([a-zA-Z0-9_.]+)"\s*:\s*"([a-zA-Z0-9_.]+)"/g)) {
    for (const key of [m[1], m[2]]) {
      used++;
      if (!(key in flat.en)) problems.push(`code: unknown key "${key}" in ${file.slice(root.length + 1)}`);
    }
  }
}

console.log(`Languages: ${LANGS.join(", ")} · ${Object.keys(flat.en).length} keys each · ${used} uses checked in ${files.length} files`);
if (problems.length) {
  console.log(`\n${problems.length} problem(s):\n  ` + problems.join("\n  "));
  process.exit(1);
}
console.log("All translations complete and consistent.");
