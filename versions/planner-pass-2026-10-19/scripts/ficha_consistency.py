"""Validate Ficha metadata against a Consistem/Blender provenance file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def text(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any) -> float | None:
    try:
        return float(text(value).replace(",", "."))
    except ValueError:
        return None


def expected_item(provenance: dict[str, Any]) -> dict[str, Any]:
    geometry = provenance.get("expected_geometry") or {}
    row = provenance.get("row") or {}
    return {
        "reference": text(provenance.get("reference")),
        "size_tam": text(provenance.get("size")),
        "diametro_mm": geometry.get("diameter_mm"),
        "espessura_final_mm": geometry.get("thickness_mm"),
        "num_furos": geometry.get("hole_count"),
        "broca_mm": number(row.get("broca")),
        "distancia_furos_mm": number(row.get("distancia_furos")),
        "faca_frente": text(row.get("faca_frente")),
        "fundo": text(row.get("fundo")),
        "acabamento": text(row.get("acabamento")),
    }


def compare_item(item: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for field, wanted in expected.items():
        actual = item.get(field)
        if wanted in (None, ""):
            continue
        if field in {"diametro_mm", "espessura_final_mm", "broca_mm", "distancia_furos_mm"}:
            if number(actual) != float(wanted):
                issues.append({"field": field, "expected": wanted, "actual": actual})
        elif text(actual) != text(wanted):
            issues.append({"field": field, "expected": wanted, "actual": actual})
    return issues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provenance", required=True, type=Path)
    parser.add_argument("--item-json", required=True, type=Path, help="JSON object with the Ficha item fields")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
    supplied = json.loads(args.item_json.read_text(encoding="utf-8"))
    item = supplied.get("item", supplied)
    if not isinstance(item, dict):
        raise SystemExit("--item-json must contain an item object")
    expected = expected_item(provenance)
    issues = compare_item(item, expected)
    report = {"ok": not issues, "expected": expected, "item": item, "issues": issues}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
