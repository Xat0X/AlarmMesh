// Development-only upstream inventory. Install the exact official converter
// package in a Git-ignored directory; never include node_modules in the product.
const fs = require("node:fs");
const path = require("node:path");
const DOCS = "df1ef4602fdc2c5bc54c9b7352590afc98e2366b";

async function main() {
  const [npmRoot, output, reviewPath] = process.argv.slice(2);
  if (!npmRoot || !output) throw Error("Usage: node extract.cjs <npm-project-directory> <ignored-output.json>");
  const root = path.resolve(npmRoot, "node_modules/zigbee-herdsman-converters");
  const metadata = JSON.parse(fs.readFileSync(path.join(root, "package.json")));
  if (metadata.version !== "26.131.0") throw Error("Use the reviewed converter version 26.131.0");
  const response = await fetch(`https://raw.githubusercontent.com/Koenkk/zigbee2mqtt.io/${DOCS}/docs/supported-devices/README.md`);
  if (!response.ok) throw Error(`Official dataset HTTP ${response.status}`);
  const text = await response.text();
  const match = text.match(/window\.ZIGBEE2MQTT_SUPPORTED_DEVICES\s*=\s*(\[[\s\S]*?\]);/);
  if (!match) throw Error("Official dataset structure changed; review required");
  // Same predicate as the official website's exposes filter, no model guessing.
  const rows = JSON.parse(match[1]).filter(row => row.exposes.includes("smoke"));
  const definitions = [];
  for (const file of fs.readdirSync(path.join(root, "dist/devices")).sort()) {
    if (file.endsWith(".js")) for (const definition of require(path.join(root, "dist/devices", file)).definitions || []) {
      definitions.push({ ...definition, source_file: `src/devices/${file.replace(/\.js$/, ".ts")}` });
    }
  }
  const selected = new Map();
  for (const row of rows) {
    const candidates = definitions.filter(d => d.model === row.model && d.vendor === row.vendor || (d.whiteLabel || []).some(w => w.model === row.model && w.vendor === row.vendor));
    if (candidates.length !== 1) throw Error(`Ambiguous upstream definition: ${row.vendor} ${row.model}`);
    const d = candidates[0], key = `${d.vendor}\0${d.model}`;
    if (!selected.has(key)) selected.set(key, { vendor: d.vendor, model: d.model, source_file: d.source_file, zigbee_models: d.zigbeeModel || [], fingerprints: d.fingerprint || [], variants: [] });
    selected.get(key).variants.push({ vendor: row.vendor, model: row.model, link: row.link });
  }
  const result = { docs_commit: DOCS, converter_package: metadata.version, definitions: [...selected.values()].sort((a, b) => `${a.vendor} ${a.model}`.localeCompare(`${b.vendor} ${b.model}`)), website_rows: rows.length };
  if (reviewPath) {
    const review = JSON.parse(fs.readFileSync(reviewPath, "utf8"));
    const pairs = definitions => definitions.flatMap(d => (d.variants || [{ vendor: d.vendor, model: d.model }, ...d.aliases]).map(a => `${d.vendor} / ${d.model} -> ${a.vendor} / ${a.model}`)).sort();
    if (review.website_rows !== rows.length || JSON.stringify(pairs(result.definitions)) !== JSON.stringify(pairs(review.entries))) throw Error("Inventory differs from reviewed canonical/variant relationships");
  }
  fs.writeFileSync(output, JSON.stringify(result, (key, value) => value instanceof RegExp ? { regex: value.source } : value, 2) + "\n");
  console.log(`${result.definitions.length} definitions / ${rows.length} website rows; review provider assessments separately`);
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
