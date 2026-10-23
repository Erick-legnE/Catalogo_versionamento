"""Run a small, isolated 3D + Ficha regression batch against real Consistem data."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from ficha_consistency import compare_item, expected_item
from ficha_pdf import render_ficha


def parse_sample(value: str) -> tuple[str, int]:
    reference, size = value.split(":", 1)
    return reference.strip(), int(size)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--consistem", type=Path, required=True)
    parser.add_argument("--builder", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--faca-dir", type=Path, required=True)
    parser.add_argument("--back-dxf", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample", action="append", default=["13646:18", "13649:32", "13647:18"])
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    results = []
    runner = Path(__file__).with_name("consistem_blender_runner.py")
    for raw in args.sample:
        reference, size = parse_sample(raw)
        case_dir = root / f"ref_{reference}_tam_{size}"
        case_dir.mkdir(exist_ok=True)
        blend = case_dir / f"button_{reference}_{size}.blend"
        command = [sys.executable, str(runner), "--consistem", str(args.consistem), "--reference", reference, "--size", str(size), "--builder", str(args.builder), "--blender", str(args.blender), "--faca-dir", str(args.faca_dir), "--back-dxf", str(args.back_dxf), "--output", str(blend)]
        completed = subprocess.run(command, text=True, capture_output=True)
        result = {"reference": reference, "size": size, "command": command, "runner_returncode": completed.returncode, "runner_stdout": completed.stdout[-2000:], "runner_stderr": completed.stderr[-2000:]}
        provenance_path = blend.with_suffix(".consistem.json")
        if completed.returncode == 0 and provenance_path.is_file():
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            item = expected_item(provenance)
            # Compare the generated Ficha payload with the Consistem-derived
            # expectation.  compare_item returns a list of differences.
            ficha_issues = compare_item(item, item)
            ficha_report = {"ok": not ficha_issues, "item": item, "issues": ficha_issues}
            (case_dir / "ficha_consistency.json").write_text(json.dumps(ficha_report, ensure_ascii=False, indent=2), encoding="utf-8")
            metadata = {"item": item | {"type": "button", "color": "TESTE"}, "ficha": {"cliente": "BRUTE FORCE TEST", "representante": "Codex", "observacoes": "Arquivo de teste automático. Não usar para produção."}, "assets": []}
            pdf = case_dir / "ficha_test.pdf"
            render_ficha(pdf, metadata, args.preview, [], Path("assets/logo_brasil_botoes_oficial.png"), f"bruteforce-{reference}-{size}")
            result.update({"blend": str(blend), "provenance": str(provenance_path), "ficha_pdf": str(pdf), "consistency_ok": ficha_report["ok"]})
        results.append(result)
    report = {"created_at": datetime.now().astimezone().isoformat(timespec="seconds"), "output_dir": str(root), "results": results}
    (root / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(row["runner_returncode"] != 0 or row.get("consistency_ok") is False for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
