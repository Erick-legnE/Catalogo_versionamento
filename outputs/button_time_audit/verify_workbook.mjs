import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const outputDir = path.dirname(fileURLToPath(import.meta.url));
const outputPath = path.join(outputDir, "auditoria_tempos_botoes.xlsx");
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));

const savedSheets = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 3000 });
const inspections = {};
for (const sheetName of ["Resultados", "Incorretos", "Não Cadastrados"]) {
  const check = await workbook.inspect({
    kind: "table",
    range: `'${sheetName}'!A2:M18`,
    include: "values,formulas",
    tableMaxRows: 18,
    tableMaxCols: 13,
    maxChars: 9000,
  });
  inspections[sheetName] = check.ndjson;
  const preview = await workbook.render({ sheetName, range: "A1:M25", scale: 1.25, format: "png" });
  await fs.writeFile(path.join(outputDir, `preview_${sheetName.replace(/\s+/g, "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "saved workbook formula error scan",
  maxChars: 5000,
});

await fs.writeFile(
  path.join(outputDir, "saved_workbook_verification.json"),
  JSON.stringify({ savedSheets: savedSheets.ndjson, inspections, formulaErrors: formulaErrors.ndjson }, null, 2),
  "utf8",
);

console.log(JSON.stringify({ savedSheets: savedSheets.ndjson, formulaErrors: formulaErrors.ndjson }));
