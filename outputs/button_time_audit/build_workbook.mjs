import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.dirname(fileURLToPath(import.meta.url));
const inputPath = path.join(outputDir, "final_results.json");
const outputPath = path.join(outputDir, "auditoria_tempos_botoes.xlsx");

const rows = JSON.parse(await fs.readFile(inputPath, "utf8"));
const statusCounts = rows.reduce((acc, row) => {
  acc[row.status] = (acc[row.status] || 0) + 1;
  return acc;
}, {});

const incorrectStatuses = new Set(["INCORRETO", "OPERAÇÃO 6 AUSENTE", "MÚLTIPLAS OPERAÇÕES 6"]);
const incorrectRows = rows.filter(row => incorrectStatuses.has(row.status));
const notRegisteredRows = rows.filter(row => row.status === "NÃO CADASTRADO");

const headers = [
  "Código Reduzido",
  "Descrição Fonte",
  "Descrição API",
  "TAM",
  "Acabamento",
  "Regra",
  "Tempo Esperado",
  "Tempo API",
  "Diferença",
  "Qtd. Operação 6",
  "Status",
  "HTTP",
  "Observação",
];

function rowValues(row) {
  return [
    row.codigo,
    row.descricao,
    row.apiDescription || "",
    row.tam,
    row.acabamento === "NAO_IDENTIFICADO" ? "NÃO IDENTIFICADO" : row.acabamento,
    row.regra,
    row.tempoEsperado ?? null,
    row.tempoApi ?? null,
    row.diferenca ?? null,
    row.op6Times.length,
    row.status,
    row.httpStatus,
    row.observacao || "",
  ];
}

function styleSheet(sheet, dataRows, options) {
  const headerRow = 8;
  const firstDataRow = headerRow + 1;
  const lastRow = headerRow + dataRows.length;
  const usedLastRow = Math.max(lastRow, headerRow);

  sheet.showGridLines = false;
  sheet.tabColor = options.tabColor;
  sheet.getRange("A2").values = [[options.title]];
  sheet.getRange("A2:M2").format.font = { name: "Arial", size: 14, bold: true, color: "#1F1F1F" };
  sheet.getRange("A2:M2").format.rowHeight = 24;
  sheet.getRange("A3:M3").format.borders = { bottom: { style: "thin", color: "#B4C6E7" } };

  options.summaryWriter(sheet);
  sheet.getRange("A6").values = [[options.sourceNote]];
  sheet.getRange("A6:M6").format.font = { name: "Arial", size: 9, italic: true, color: "#666666" };

  sheet.getRange(`A${headerRow}:M${headerRow}`).values = [headers];
  sheet.getRange(`A${headerRow}:M${headerRow}`).format = {
    fill: options.headerColor,
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { insideVertical: { style: "thin", color: "#FFFFFF" } },
  };
  sheet.getRange(`A${headerRow}:M${headerRow}`).format.rowHeight = 30;

  if (dataRows.length) {
    const matrix = dataRows.map(rowValues);
    sheet.getRangeByIndexes(firstDataRow - 1, 0, matrix.length, headers.length).values = matrix;
    const body = sheet.getRange(`A${firstDataRow}:M${lastRow}`);
    body.format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
    body.format.verticalAlignment = "center";
    body.format.rowHeight = 18;
    sheet.getRange(`A${firstDataRow}:A${lastRow}`).format.numberFormat = "@";
    sheet.getRange(`D${firstDataRow}:D${lastRow}`).format.numberFormat = "0";
    sheet.getRange(`G${firstDataRow}:G${lastRow}`).format.numberFormat = "0.00";
    sheet.getRange(`H${firstDataRow}:I${lastRow}`).format.numberFormat = "0.0000";
    sheet.getRange(`J${firstDataRow}:J${lastRow}`).format.numberFormat = "0";
    sheet.getRange(`L${firstDataRow}:L${lastRow}`).format.numberFormat = "0";
    sheet.getRange(`A${firstDataRow}:A${lastRow}`).format.horizontalAlignment = "left";
    sheet.getRange(`D${firstDataRow}:D${lastRow}`).format.horizontalAlignment = "right";
    sheet.getRange(`G${firstDataRow}:J${lastRow}`).format.horizontalAlignment = "right";
    sheet.getRange(`L${firstDataRow}:L${lastRow}`).format.horizontalAlignment = "right";
    sheet.getRange(`B${firstDataRow}:C${lastRow}`).format.wrapText = false;
    sheet.getRange(`M${firstDataRow}:M${lastRow}`).format.wrapText = false;

    const statusRange = sheet.getRange(`K${firstDataRow}:K${lastRow}`);
    statusRange.conditionalFormats.add("containsText", {
      text: "INCORRETO",
      format: { fill: "#FCE8E6", font: { bold: true, color: "#B91C1C" } },
    });
    statusRange.conditionalFormats.add("containsText", {
      text: "OPERAÇÃO 6 AUSENTE",
      format: { fill: "#FFF4CE", font: { bold: true, color: "#8A4B08" } },
    });
    statusRange.conditionalFormats.add("containsText", {
      text: "MÚLTIPLAS OPERAÇÕES 6",
      format: { fill: "#FFF4CE", font: { bold: true, color: "#8A4B08" } },
    });
    statusRange.conditionalFormats.add("containsText", {
      text: "NÃO CADASTRADO",
      format: { fill: "#E7E6E6", font: { bold: true, color: "#595959" } },
    });
    statusRange.conditionalFormats.add("containsText", {
      text: "ACABAMENTO NÃO IDENTIFICADO",
      format: { fill: "#FFF2CC", font: { bold: true, color: "#7F6000" } },
    });
    statusRange.conditionalFormats.add("containsText", {
      text: "ERRO API",
      format: { fill: "#F4CCCC", font: { bold: true, color: "#990000" } },
    });
  }

  const table = sheet.tables.add(`A${headerRow}:M${usedLastRow}`, true, options.tableName);
  table.style = "TableStyleMedium2";
  table.showBandedColumns = false;
  table.showFilterButton = true;

  const widths = [16, 52, 52, 8, 16, 24, 15, 14, 13, 16, 31, 9, 52];
  for (let column = 0; column < widths.length; column += 1) {
    sheet.getRangeByIndexes(1, column, usedLastRow - 1, 1).format.columnWidth = widths[column];
  }
  sheet.freezePanes.freezeRows(headerRow);
  sheet.freezePanes.freezeColumns(2);
}

const workbook = Workbook.create();
const resultsSheet = workbook.worksheets.add("Resultados");
const incorrectSheet = workbook.worksheets.add("Incorretos");
const notRegisteredSheet = workbook.worksheets.add("Não Cadastrados");

styleSheet(resultsSheet, rows, {
  title: "Auditoria de tempo padrão dos botões",
  sourceNote: "Fontes: lista de códigos fornecida e API Consistem homologação /engenharia/{id}, empresa 1. Consulta em 16/10/2026.",
  headerColor: "#1F4E78",
  tabColor: "#1F4E78",
  tableName: "ResultadosAuditoria",
  summaryWriter(sheet) {
    sheet.getRange("A4:L5").format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
    sheet.getRange("A4:L5").values = [
      ["Total auditado", rows.length, "Corretos", statusCounts.CORRETO || 0, "Incorretos", statusCounts.INCORRETO || 0, "Op. 6 ausente", statusCounts["OPERAÇÃO 6 AUSENTE"] || 0, "Múltiplas op. 6", statusCounts["MÚLTIPLAS OPERAÇÕES 6"] || 0, "Não cadastrados", statusCounts["NÃO CADASTRADO"] || 0],
      ["Acab. não ident.", statusCounts["ACABAMENTO NÃO IDENTIFICADO"] || 0, "Erro API", statusCounts["ERRO API"] || 0, "", null, "", null, "", null, "", null],
    ];
    sheet.getRange("A4:L5").format.borders = { bottom: { style: "thin", color: "#D9E2F3" } };
    sheet.getRange("A4:L5").format.verticalAlignment = "center";
    sheet.getRange("A4:L5").format.rowHeight = 20;
    for (const cell of ["A4", "C4", "E4", "G4", "I4", "K4", "A5", "C5"]) {
      sheet.getRange(cell).format.font = { name: "Arial", size: 10, bold: true, color: "#44546A" };
    }
    for (const cell of ["B4", "D4", "F4", "H4", "J4", "L4", "B5", "D5"]) {
      sheet.getRange(cell).format.numberFormat = "#,##0";
      sheet.getRange(cell).format.font = { name: "Arial", size: 11, bold: true, color: "#1F1F1F" };
    }
  },
});

styleSheet(incorrectSheet, incorrectRows, {
  title: "Registros com tempo incorreto ou operação 6 inconsistente",
  sourceNote: "Inclui tempo divergente, operação 6 ausente e múltiplas operações 6. Os não cadastrados ficam em uma aba separada.",
  headerColor: "#9C0006",
  tabColor: "#C00000",
  tableName: "ResultadosIncorretos",
  summaryWriter(sheet) {
    sheet.getRange("A4:D4").values = [["Total nesta aba", incorrectRows.length, "Tempos divergentes", statusCounts.INCORRETO || 0]];
    sheet.getRange("A5:F5").values = [["Op. 6 ausente", statusCounts["OPERAÇÃO 6 AUSENTE"] || 0, "Múltiplas op. 6", statusCounts["MÚLTIPLAS OPERAÇÕES 6"] || 0, "", null]];
    sheet.getRange("A4:F5").format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
    for (const cell of ["A4", "C4", "A5", "C5"]) sheet.getRange(cell).format.font = { name: "Arial", size: 10, bold: true, color: "#7F0000" };
    for (const cell of ["B4", "D4", "B5", "D5"]) sheet.getRange(cell).format.numberFormat = "#,##0";
  },
});

styleSheet(notRegisteredSheet, notRegisteredRows, {
  title: "Engenharias não cadastradas na API",
  sourceNote: "A API retornou HTTP 400 com a mensagem de que a engenharia não está cadastrada.",
  headerColor: "#595959",
  tabColor: "#7F7F7F",
  tableName: "ResultadosNaoCadastrados",
  summaryWriter(sheet) {
    sheet.getRange("A4:B4").values = [["Não cadastrados", notRegisteredRows.length]];
    sheet.getRange("A4").format.font = { name: "Arial", size: 10, bold: true, color: "#595959" };
    sheet.getRange("B4").format.numberFormat = "#,##0";
    sheet.getRange("B4").format.font = { name: "Arial", size: 11, bold: true, color: "#1F1F1F" };
  },
});

workbook.recalculate();

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
}

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
  maxChars: 5000,
});

const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

await fs.writeFile(
  path.join(outputDir, "workbook_verification.json"),
  JSON.stringify({ inspections, formulaErrors: formulaErrors.ndjson }, null, 2),
  "utf8",
);

console.log(JSON.stringify({
  outputPath,
  totalRows: rows.length,
  incorrectRows: incorrectRows.length,
  notRegisteredRows: notRegisteredRows.length,
  statusCounts,
  formulaErrors: formulaErrors.ndjson,
}));
