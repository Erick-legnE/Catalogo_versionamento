"""Validate a copied server-data backup before relying on it for recovery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup-dir", required=True, type=Path)
    args = parser.parse_args()
    root = args.backup_dir.resolve()
    manifests = list(root.rglob("manifest.json"))
    errors: list[str] = []
    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not manifest.get("id") or not manifest.get("status"):
                errors.append(f"incomplete manifest: {manifest_path}")
            pdf = manifest_path.parent / "ficha_tecnica.pdf"
            if pdf.exists() and not pdf.read_bytes().startswith(b"%PDF"):
                errors.append(f"invalid PDF header: {pdf}")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid manifest {manifest_path}: {exc}")
    result = {"backup_dir": str(root), "manifest_count": len(manifests), "ok": bool(manifests) and not errors, "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
