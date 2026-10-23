"""Check a version folder before production release without changing files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-dir", required=True, type=Path)
    parser.add_argument("--require-pdf", action="store_true")
    args = parser.parse_args()
    root = args.version_dir.resolve()
    errors: list[str] = []
    if not root.is_dir():
        raise SystemExit(f"Version directory not found: {root}")
    blends = list(root.rglob("*.blend"))
    provenance = list(root.rglob("*.consistem.json"))
    if not blends:
        errors.append("missing .blend output")
    if not provenance:
        errors.append("missing .consistem.json provenance")
    for path in provenance:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Older runner outputs keep the original Consistem row instead of
            # the newer expected_geometry summary. Both carry the evidence.
            if not data.get("reference") or not data.get("size") or not (data.get("expected_geometry") or data.get("row")):
                errors.append(f"incomplete provenance: {path.name}")
        except (OSError, json.JSONDecodeError):
            errors.append(f"invalid provenance JSON: {path.name}")
    if args.require_pdf and not list(root.rglob("*.pdf")):
        errors.append("missing approved PDF")
    report = {"version_dir": str(root), "ok": not errors, "errors": errors, "blend_count": len(blends), "provenance_count": len(provenance)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
