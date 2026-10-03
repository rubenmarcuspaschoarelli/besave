// Gate de CI do contrato: fixtures "ok" devem passar, fixtures "invalido" devem falhar,
// e todo alvo do mapeamento.json deve existir no enum.
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const load = (p) => JSON.parse(readFileSync(join(root, p), "utf8"));

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
for (const f of readdirSync(join(root, "schema"))) ajv.addSchema(load(`schema/${f}`));

const casos = [
  ["fixtures/chunk-ok.json",         "https://besave.com.br/contract/chunk.schema.json",         true],
  ["fixtures/chunk-invalido.json",   "https://besave.com.br/contract/chunk.schema.json",         false],
  ["fixtures/oferta-pagina-ok.json", "https://besave.com.br/contract/oferta-pagina.schema.json", true],
  ["fixtures/manifest-ok.json",      "https://besave.com.br/contract/manifest.schema.json",      true],
];

let falhas = 0;
for (const [fixture, schemaId, esperado] of casos) {
  const validate = ajv.getSchema(schemaId);
  const ok = validate(load(fixture));
  const passou = ok === esperado;
  console.log(`${passou ? "PASS" : "FAIL"}  ${fixture}  (válido=${ok}, esperado=${esperado})`);
  if (!passou) { falhas++; if (!ok) console.log(validate.errors); }
  if (!ok && !esperado) console.log(`      rejeitado como esperado: ${validate.errors.length} erro(s) em ${new Set(validate.errors.map(e=>e.instancePath.split("/")[1])).size} registro(s)`);
}

const enums = load("schema/enums.schema.json").$defs;
const map = load("mapeamento.json");
for (const [campo, def] of [["loja", "Loja"], ["publico", "Publico"], ["area", "Area"]]) {
  for (const [k, v] of Object.entries(map[campo])) {
    if (!enums[def].enum.includes(v)) { console.log(`FAIL  mapeamento.${campo}["${k}"] -> "${v}" não está no enum ${def}`); falhas++; }
  }
}
if (falhas) { console.error(`\n${falhas} falha(s)`); process.exit(1); }
console.log("\ncontrato OK");
