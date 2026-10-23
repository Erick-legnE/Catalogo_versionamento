"""Generate a simple Blender button from Consistem hole metadata.

Usage inside Blender:
  blender --background --python scripts/blender_button.py -- --reference 16 --size 18 --output outputs/button_16_18.blend
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_geometry(reference: str, size: int, data_root: Path) -> dict:
    refs = json.loads((data_root / "referencias_consistem.json").read_text(encoding="utf-8"))["references"]
    patterns = json.loads((data_root / "hole_patterns.json").read_text(encoding="utf-8"))["patterns"]
    ref = refs.get(str(reference).lstrip("0"), {})
    size_data = ref.get("by_size", {}).get(str(size), {})
    count = int(size_data.get("num_furos") or 0)
    pattern_name = {0: "none", 1: "one_center", 2: "two_horizontal", 3: "three_triangle", 4: "four_square"}.get(count, "four_square")
    pattern = patterns.get(pattern_name, patterns["four_square"])
    radius = float(size) / 2
    points = [(round(x * radius, 3), round(y * radius, 3)) for x, y in pattern.get("points", [])[:count or 0]]
    return {"reference": str(reference), "size": size, "thickness_mm": float(size_data.get("espessura_final_mm") or max(1.5, size * 0.08)), "hole_diameter_mm": float(size_data.get("broca_mm") or 1.5), "hole_count": count, "pattern": pattern_name, "points_mm": points}


def build_scene(geometry: dict, output: Path, render: bool = False) -> dict:
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    radius = geometry["size"] / 2
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=geometry["thickness_mm"], location=(0, 0, 0))
    body = bpy.context.object
    body.name = f"Button_{geometry['reference']}_{geometry['size']}mm"
    bevel = body.modifiers.new("Soft edge", "BEVEL")
    bevel.width = min(0.6, geometry["thickness_mm"] * 0.2)
    bevel.segments = 3
    material = bpy.data.materials.new("Button material")
    material.use_nodes = True
    body_bsdf = material.node_tree.nodes.get("Principled BSDF")
    body_bsdf.inputs["Base Color"].default_value = (0.02, 0.32, 0.42, 1)
    body_bsdf.inputs["Roughness"].default_value = 0.28
    body.data.materials.append(material)
    hole_material = bpy.data.materials.new("Hole material")
    hole_material.use_nodes = True
    hole_bsdf = hole_material.node_tree.nodes.get("Principled BSDF")
    hole_bsdf.inputs["Base Color"].default_value = (0.002, 0.004, 0.006, 1)
    hole_bsdf.inputs["Roughness"].default_value = 0.65
    for index, (x, y) in enumerate(geometry["points_mm"], 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=geometry["hole_diameter_mm"] / 2, depth=0.15, location=(x, y, geometry["thickness_mm"] / 2 + 0.08))
        hole = bpy.context.object
        hole.name = f"Hole_{index:02d}"
        hole.data.materials.append(hole_material)
    bpy.ops.object.camera_add(location=(0, -radius * 2.2, radius * 1.7))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(0, -radius, radius * 2.5))
    bpy.context.object.data.energy = 700
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = radius * 2
    bpy.ops.object.light_add(type="AREA", location=(-radius * 1.3, radius * 0.8, radius * 1.4))
    bpy.context.object.data.energy = 450
    bpy.context.object.data.size = radius
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.world.color = (0.04, 0.04, 0.05)
    scene.render.resolution_x = 700
    scene.render.resolution_y = 700
    scene.render.resolution_percentage = 100
    if render:
        scene.render.filepath = str(output.with_suffix(".png"))
        bpy.ops.render.render(write_still=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    return geometry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--size", required=True, type=int)
    parser.add_argument("--data-root", type=Path, default=Path("docs/data"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--geometry-output", type=Path)
    blender_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(blender_args)
    geometry = load_geometry(args.reference, args.size, args.data_root)
    if args.geometry_output:
        args.geometry_output.parent.mkdir(parents=True, exist_ok=True)
        args.geometry_output.write_text(json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.dry_run:
        build_scene(geometry, args.output, args.render)
    print(json.dumps(geometry, ensure_ascii=False))


if __name__ == "__main__":
    main()
