import fs from "node:fs/promises";
import path from "node:path";

const sourcePath = process.argv[2];
const outputDir = process.argv[3];

if (!sourcePath || !outputDir) {
  throw new Error("Usage: node prepare_button_audit.mjs <source.txt> <output-dir>");
}

const allowedSizes = new Set([14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 40, 44, 54]);
const expectedTimes = {
  14: { BRILHO: 0.70, FOSCO: 0.30 },
  16: { BRILHO: 0.88, FOSCO: 0.38 },
  18: { BRILHO: 1.12, FOSCO: 0.48 },
  20: { BRILHO: 1.40, FOSCO: 0.60 },
  22: { BRILHO: 1.68, FOSCO: 0.72 },
  24: { BRILHO: 2.10, FOSCO: 0.90 },
  26: { BRILHO: 2.47, FOSCO: 1.06 },
  28: { BRILHO: 2.80, FOSCO: 1.20 },
  30: { BRILHO: 3.36, FOSCO: 1.44 },
  32: { BRILHO: 3.82, FOSCO: 1.64 },
  36: { BRILHO: 4.94, FOSCO: 2.12 },
  40: { BRILHO: 6.00, FOSCO: 2.57 },
  44: { BRILHO: 7.64, FOSCO: 3.27 },
  54: { BRILHO: 10.50, FOSCO: 4.50 },
};

function normalizedText(value) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
}

function classifyFinish(description) {
  const normalized = normalizedText(description);
  if (/\bBAS\b/.test(normalized)) {
    return { acabamento: "BRILHO", regra: "BAS" };
  }

  const afterSize = normalized.replace(/^.*?\bTAM\s+\d+(?:\s*\/\s*\d+)?\b/, "");
  const compact = afterSize.replace(/[^A-Z]/g, "");

  if (/F\s*O\s*S/.test(afterSize) || compact.includes("FOS") || compact.includes("FOCO")) {
    return { acabamento: "FOSCO", regra: "DESCRICAO_NORMALIZADA" };
  }
  if (
    /\bB\s*R(?:\b|\s|I)/.test(afterSize) ||
    compact.includes("BRILH") ||
    compact.includes("BRLHO") ||
    compact.includes("BILHO") ||
    compact.includes("BERPERS") ||
    compact.includes("BLITI")
  ) {
    return { acabamento: "BRILHO", regra: "DESCRICAO_NORMALIZADA" };
  }
  return { acabamento: "NAO_IDENTIFICADO", regra: "REVISAO_MANUAL" };
}

const text = await fs.readFile(sourcePath, "utf8");
const lines = text.split(/\r?\n/).filter(Boolean);
const records = [];

for (let index = 1; index < lines.length; index += 1) {
  const separator = lines[index].indexOf("\t");
  if (separator < 0) continue;
  const codigo = lines[index].slice(0, separator).trim();
  const descricao = lines[index].slice(separator + 1).trim();
  if (!/\bBOTAO\b/i.test(descricao)) continue;

  const sizeMatch = normalizedText(descricao).match(/\bTAM\s+(\d{1,3})/);
  if (!sizeMatch) continue;
  const tam = Number(sizeMatch[1]);
  if (!allowedSizes.has(tam)) continue;

  const { acabamento, regra } = classifyFinish(descricao);
  const tempoEsperado = acabamento === "NAO_IDENTIFICADO" ? null : expectedTimes[tam][acabamento];
  records.push({
    ordemFonte: index + 1,
    codigo,
    descricao,
    tam,
    acabamento,
    regra,
    tempoEsperado,
  });
}

const countsByFinish = records.reduce((acc, row) => {
  acc[row.acabamento] = (acc[row.acabamento] || 0) + 1;
  return acc;
}, {});
const codeCounts = records.reduce((acc, row) => {
  acc.set(row.codigo, (acc.get(row.codigo) || 0) + 1);
  return acc;
}, new Map());
const duplicateCodes = [...codeCounts.entries()].filter(([, count]) => count > 1);

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(path.join(outputDir, "targets.json"), JSON.stringify(records), "utf8");
await fs.writeFile(
  path.join(outputDir, "target_summary.json"),
  JSON.stringify({ total: records.length, countsByFinish, duplicateCodes }, null, 2),
  "utf8",
);

console.log(JSON.stringify({ total: records.length, countsByFinish, duplicateCodeCount: duplicateCodes.length }));
