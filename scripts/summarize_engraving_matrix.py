"""Validate Blender engraving reports and create a labelled comparison sheet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--expected", type=int, default=6)
    args = parser.parse_args()

    reports = sorted(args.directory.glob("ref_*.json"))
    if len(reports) != args.expected:
        raise SystemExit(f"expected {args.expected} reports, found {len(reports)}")

    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 26)
    entries: list[dict[str, object]] = []
    tiles: list[Image.Image] = []

    for report_path in reports:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        geometry = report.get("geometry_diagnostics") or {}
        render_path = Path(str(report.get("render") or ""))
        output_path = Path(str(report.get("output") or ""))
        if not render_path.is_file() or not output_path.is_file():
            raise SystemExit(f"missing output or render for {report_path.name}")

        inspection_path = render_path.with_name(f"{render_path.stem}_inspection.png")
        visual_path = inspection_path if inspection_path.is_file() else render_path
        image = Image.open(visual_path).convert("RGB")
        variance = sum(ImageStat.Stat(image.convert("L")).var) / 1
        changed = geometry.get("body_vertices_after") != geometry.get("body_vertices_before")
        manifold = geometry.get("boundary_edges") == 0 and geometry.get("non_manifold_edges") == 0
        context = report.get("automation_context") or {}
        curvature = float(report.get("curvature", context.get("curvature", 0)) or 0)
        curve_geometry = geometry.get("curvature") or {}
        expected_glyphs = sum(not character.isspace() for character in str(report.get("text") or ""))
        size_preserved = (
            abs(curvature) < 1e-9
            or (
                curve_geometry.get("transformation") == "rigid_per_glyph"
                and curve_geometry.get("glyph_group_count") == expected_glyphs
                and float(curve_geometry.get("glyph_size_max_radius_error") or 0) <= 0.00001
            )
        )
        passed = bool(changed and manifold and variance > 1 and size_preserved)
        item = json.loads(Path(context["request_path"]).read_text(encoding="utf-8"))["item"]
        entry = {
            "reference": item["reference"],
            "size_tam": item["size_tam"],
            "text": report.get("text"),
            "font_family": context.get("font_family"),
            "position_mm": report.get("position_mm"),
            "rotation_degrees": report.get("rotation_degrees"),
            "curvature": curvature,
            "curvature_transformation": curve_geometry.get("transformation"),
            "glyph_group_count": curve_geometry.get("glyph_group_count"),
            "glyph_size_max_radius_error": curve_geometry.get("glyph_size_max_radius_error"),
            "size_preserved": size_preserved,
            "depth_mm": context.get("depth_mm"),
            "vertices_before": geometry.get("body_vertices_before"),
            "vertices_after": geometry.get("body_vertices_after"),
            "boundary_edges": geometry.get("boundary_edges"),
            "non_manifold_edges": geometry.get("non_manifold_edges"),
            "render_variance": round(variance, 3),
            "blend": str(output_path),
            "render": str(render_path),
            "inspection_render": str(inspection_path) if inspection_path.is_file() else None,
            "passed_structural_checks": passed,
        }
        entries.append(entry)

        image.thumbnail((600, 600), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (640, 690), "white")
        tile.paste(image, ((640 - image.width) // 2, 45))
        draw = ImageDraw.Draw(tile)
        status = "PASS" if passed else "FAIL"
        draw.rectangle((0, 0, 640, 40), fill="#2f855a" if passed else "#c53030")
        draw.text((16, 6), f"{status}  REF {item['reference']} / TAM {item['size_tam']} / {report.get('text')}", fill="white", font=font)
        draw.text((16, 650), f"{context.get('font_family')} | depth {context.get('depth_mm')} mm | rotation {report.get('rotation_degrees')} deg | curve {report.get('curvature', 0)}", fill="#111827", font=font)
        tiles.append(tile)

    sheet = Image.new("RGB", (1280, 2070), "#d1d5db")
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % 2) * 640, (index // 2) * 690))
    sheet_path = args.directory / "engraving_matrix_contact_sheet.png"
    sheet.save(sheet_path)

    summary = {
        "case_count": len(entries),
        "all_checks_passed": all(entry["passed_structural_checks"] for entry in entries),
        "all_structural_checks_passed": all(entry["passed_structural_checks"] for entry in entries),
        "contact_sheet": str(sheet_path.resolve()),
        "cases": entries,
    }
    summary_path = args.directory / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
