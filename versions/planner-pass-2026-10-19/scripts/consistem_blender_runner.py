"""Build a Blender button from one Consistem workbook row.

The original criador_blender.py is copied and configured per run. It is never
modified. The copied script then imports the selected DXFs and runs the user's
Boolean/UV/topology pipeline in headless mode.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any


def clean_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def text(value: object) -> str:
    return str(value or "").strip()


def number(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raw = text(value)
    raw = raw.replace(".", "").replace(",", ".") if "," in raw else raw
    try:
        return float(raw)
    except ValueError:
        return default


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".xlsx":
        import openpyxl

        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = [clean_key(value) for value in next(rows)]
        return [dict(zip(headers, row)) for row in rows if any(value not in (None, "") for value in row)]
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        rows = value.get("rows", value) if isinstance(value, dict) else value
        return [{clean_key(key): value for key, value in row.items()} for row in rows]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{clean_key(key): value for key, value in row.items()} for row in reader]


def row_reference(row: dict[str, Any]) -> str:
    description = text(row.get("descricao_produto"))
    mask = text(row.get("mascara"))
    match = re.search(r"(?:BOTAO|BUTTON)\s+\S+\s+(\d+)\s+\d+F\s+TAM", description, re.I)
    if match:
        return str(int(match.group(1)))
    masks = re.findall(r"(?:^|\.)(\d{3,6})(?:\.|$)", mask)
    return str(int(masks[0])) if masks else ""


def row_size(row: dict[str, Any]) -> int | None:
    match = re.search(r"\bTAM\s+(\d+)", text(row.get("descricao_produto")), re.I)
    if match:
        return int(match.group(1))
    value = number(row.get("medida_em_mm"), 0)
    return int(value) if value else None


def find_row(rows: list[dict[str, Any]], reference: str, size: int) -> dict[str, Any]:
    wanted = str(int(reference))
    matches = [row for row in rows if row_reference(row) == wanted and row_size(row) == size]
    if not matches:
        raise SystemExit(f"Consistem row not found for reference={reference}, size={size}")
    return matches[0]


def validate_row(row: dict[str, Any]) -> dict[str, float | int]:
    """Reject unsafe/incomplete production inputs before Blender is launched."""
    diameter = row_size(row)
    thickness = number(row.get("espessura_final"))
    holes = int(number(row.get("num_furos")))
    drill = number(row.get("broca"))
    spacing = number(row.get("distancia_furos"))
    faca = text(row.get("faca_frente"))
    if diameter is None or diameter <= 0:
        raise SystemExit("Consistem row has no valid TAM/diameter")
    if thickness <= 0:
        raise SystemExit("Consistem row has no valid final thickness")
    if holes < 0:
        raise SystemExit("Consistem row has an invalid negative hole count")
    if holes and (drill <= 0 or spacing <= 0):
        raise SystemExit("Consistem row with holes requires valid drill and hole spacing")
    if not faca:
        raise SystemExit("Consistem row has no front faca")
    return {
        "diameter_mm": diameter,
        "thickness_mm": thickness,
        "hole_count": holes,
        "hole_radius_mm": drill / 2 if holes else 0.0,
        "hole_distance_mm": spacing / 2 if holes else 0.0,
    }


def resolve_front_dxf(faca: str, size: int, faca_dir: Path) -> Path:
    normalized = re.sub(r"\s+", "", faca).upper()
    candidates: list[Path] = []
    if normalized.startswith("OP"):
        candidates += [faca_dir / f"opn-{size}.dxf", faca_dir / f"op-{size}.dxf"]
    else:
        prefix = str(int(re.search(r"\d+", normalized).group(0))) if re.search(r"\d+", normalized) else normalized
        candidates = sorted(faca_dir.glob(f"{prefix}-*.dxf"))
        candidates = [path for path in candidates if re.search(rf"(?<!\d){size}(?!\d)", path.stem)] + candidates
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(f"No DXF found for front faca={faca!r}, size={size} in {faca_dir}")


def replace_assignment(source: str, name: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(name)}\s*=.*$"
    return re.sub(pattern, lambda _match: f"{name} = {value}", source, count=1)


def configure_builder(source: str, row: dict[str, Any], front_dxf: Path, back_dxf: Path, output: Path, render: Path | None) -> str:
    configured = source
    configured = replace_assignment(configured, "FRONT_DXF_PATH", repr(str(front_dxf)))
    configured = replace_assignment(configured, "BACK_DXF_PATH", repr(str(back_dxf)))
    configured = replace_assignment(configured, "ASK_EXACT_SIZE_ON_START", "False")
    configured = replace_assignment(configured, "DEFAULT_TARGET_DIAMETER_MM", repr(float(row_size(row))))
    configured = replace_assignment(configured, "DEFAULT_TARGET_THICKNESS_MM", repr(number(row.get("espessura_final"))))
    configured = replace_assignment(configured, "INTERACTIVE_STEP_MODE", "False")
    configured = replace_assignment(configured, "HOLE_COUNT", str(int(number(row.get("num_furos")))))
    configured = replace_assignment(configured, "HOLE_RADIUS_MM", repr(number(row.get("broca")) / 2))
    configured = replace_assignment(configured, "HOLE_DISTANCE_MM", repr(number(row.get("distancia_furos")) / 2))
    popup_guard = """\n    if bpy.app.background:\n        log(f\"HEADLESS POPUP: {title}: {message}\")\n        return\n"""
    configured = configured.replace("def show_popup(message, title=\"DXF Button Builder v28\", icon='INFO'):\n", "def show_popup(message, title=\"DXF Button Builder v28\", icon='INFO'):" + popup_guard, 1)
    render_code = ""
    if render:
        render_code = f"\nbpy.context.scene.render.filepath = {str(render)!r}\nbpy.ops.render.render(write_still=True)"
    configured += f"\n\nif bpy.app.background:\n    bpy.ops.wm.save_as_mainfile(filepath={str(output)!r}){render_code}\n"
    return configured


def configure_texture(
    source: str,
    color_code: str,
    front_image: Path,
    verso_image: Path,
    side_image: Path,
    output: Path,
    report: Path,
    mode: str,
) -> str:
    """Stage the user's texture script without modifying the original file."""
    configured = source
    configured = replace_assignment(configured, "COLOR_CODE", repr(color_code))
    configured = replace_assignment(configured, "FRONT_IMAGE_PATH", repr(str(front_image)))
    configured = replace_assignment(configured, "VERSO_IMAGE_PATH", repr(str(verso_image)))
    configured = replace_assignment(configured, "SIDE_IMAGE_PATH", repr(str(side_image)))
    configured = replace_assignment(configured, "DEBUG_MODE", repr(mode))
    configured = replace_assignment(configured, "OUTPUT_BLEND_PATH", repr(str(output)))
    configured = replace_assignment(configured, "OUTPUT_REPORT_PATH", repr(str(report)))
    return configured


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--consistem", required=True, type=Path)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--size", required=True, type=int)
    parser.add_argument("--builder", required=True, type=Path)
    parser.add_argument("--blender", required=True, type=Path)
    parser.add_argument("--faca-dir", required=True, type=Path)
    parser.add_argument("--back-dxf", type=Path, required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--render", type=Path)
    parser.add_argument("--texture-script", type=Path)
    parser.add_argument("--front-image", type=Path)
    parser.add_argument("--verso-image", type=Path)
    parser.add_argument("--side-image", type=Path)
    parser.add_argument("--color-code")
    parser.add_argument("--texture-mode", choices=("PHOTO", "EXPOSURE", "LAYER_IDS", "LAYER_COLORS", "Y_GRADIENT", "SEMANTIC", "MARBLE_3D"), default="PHOTO")
    parser.add_argument("--texture-output", type=Path)
    parser.add_argument("--texture-report", type=Path)
    args = parser.parse_args()

    if not args.consistem.is_file() or not args.builder.is_file() or not args.blender.is_file():
        raise SystemExit("Consistem workbook, builder script, or Blender executable was not found")
    if not args.faca_dir.is_dir():
        raise SystemExit(f"Faca directory not found: {args.faca_dir}")
    row = find_row(load_rows(args.consistem), args.reference, args.size)
    expected_geometry = validate_row(row)
    front_dxf = resolve_front_dxf(text(row.get("faca_frente")), args.size, args.faca_dir)
    back_dxf = args.back_dxf.resolve()
    if not back_dxf.is_file():
        raise SystemExit(f"Back DXF not found: {back_dxf}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.render:
        args.render.parent.mkdir(parents=True, exist_ok=True)
    staged = args.output.resolve().with_name(args.output.stem + "_builder.py")
    configured = configure_builder(args.builder.read_text(encoding="utf-8"), row, front_dxf, back_dxf, args.output.resolve(), args.render.resolve() if args.render else None)
    staged.write_text(configured, encoding="utf-8")
    texture_context = None
    if args.texture_script:
        required = (args.front_image, args.verso_image, args.side_image, args.color_code)
        if any(value is None for value in required):
            raise SystemExit("Texturing requires --front-image, --verso-image, --side-image, and --color-code")
        for image in (args.front_image, args.verso_image, args.side_image):
            if not image.is_file():
                raise SystemExit(f"Texture image not found: {image}")
        texture_output = (args.texture_output or args.output.with_name(args.output.stem + "_textured.blend")).resolve()
        texture_report = (args.texture_report or args.output.with_name(args.output.stem + "_texture_report.json")).resolve()
        staged_texture = args.output.resolve().with_name(args.output.stem + "_texture.py")
        texture_source = configure_texture(
            args.texture_script.read_text(encoding="utf-8"),
            args.color_code,
            args.front_image.resolve(),
            args.verso_image.resolve(),
            args.side_image.resolve(),
            texture_output,
            texture_report,
            args.texture_mode,
        )
        staged_texture.write_text(texture_source, encoding="utf-8")
        texture_context = {
            "script": str(staged_texture),
            "output": str(texture_output),
            "report": str(texture_report),
            "mode": args.texture_mode,
            "color_code": args.color_code,
            "front_image": str(args.front_image.resolve()),
            "verso_image": str(args.verso_image.resolve()),
            "side_image": str(args.side_image.resolve()),
        }
    context = {"reference": args.reference, "size": args.size, "row": row, "expected_geometry": expected_geometry, "front_dxf": str(front_dxf), "back_dxf": str(back_dxf), "output": str(args.output.resolve()), "texture": texture_context}
    args.output.with_suffix(".consistem.json").write_text(json.dumps(context, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result = subprocess.run([str(args.blender), "--background", "--python", str(staged)], cwd=str(args.output.parent), check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    if texture_context:
        texture_result = subprocess.run(
            [str(args.blender), "--background", str(args.output.resolve()), "--python", texture_context["script"]],
            cwd=str(args.output.parent),
            check=False,
        )
        if texture_result.returncode:
            raise SystemExit(texture_result.returncode)
    print(json.dumps(context, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
