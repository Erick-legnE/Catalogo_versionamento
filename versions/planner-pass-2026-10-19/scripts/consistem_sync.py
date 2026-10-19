"""Import a Consistem export into a deduplicated CSV without SQL.

Run once with --once, or poll the export every minute with --watch.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Iterable


def normalize_header(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "campo"


def read_rows(source: Path) -> list[dict[str, str]]:
    if source.suffix.lower() == ".json":
        value = json.loads(source.read_text(encoding="utf-8"))
        rows = value if isinstance(value, list) else value.get("rows", [])
        return [{normalize_header(k): str(v or "").strip() for k, v in row.items()} for row in rows if isinstance(row, dict)]
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel_tab if "\t" in sample else csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        return [
            {normalize_header(k): str(v or "").strip() for k, v in row.items() if k is not None}
            for row in reader
        ]


def row_key(row: dict[str, str]) -> str:
    for field in ("reduzido", "codigo", "codigo_produto", "id", "referencia"):
        if row.get(field):
            return f"{field}:{row[field]}"
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sync_once(source: Path, output: Path) -> dict[str, int | str]:
    incoming = read_rows(source)
    existing: dict[str, dict[str, str]] = {}
    if output.is_file():
        existing_rows = read_rows(output)
        existing = {row_key(row): row for row in existing_rows}
    for row in incoming:
        existing[row_key(row)] = row
    rows = list(existing.values())
    headers = sorted({key for row in rows for key in row})
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".part")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in headers} for row in rows)
    temp.replace(output)
    report = {"source": str(source), "output": str(output), "incoming": len(incoming), "total": len(rows)}
    output.with_name("sync_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    last_mtime = None
    while True:
        mtime = args.source.stat().st_mtime_ns
        if mtime != last_mtime:
            print(json.dumps(sync_once(args.source, args.output), ensure_ascii=False), flush=True)
            last_mtime = mtime
        if not args.watch:
            return
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    main()
