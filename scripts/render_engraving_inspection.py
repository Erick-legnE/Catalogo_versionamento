"""Render a neutral, face-on inspection image from an engraved Blender file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy  # type: ignore
from mathutils import Vector  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_personalizado import body_bounds, find_button_body, surface_spec


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--face", choices=("FRONT", "BACK", "TOP"), default="BACK")
    args = parser.parse_args(blender_args())

    body = find_button_body()
    surface = surface_spec(body, args.face)
    bounds = body_bounds(body)
    diameter = max(bounds["max_x"] - bounds["min_x"], bounds["max_z"] - bounds["min_z"])
    centre = Vector(surface["base"])
    outward = Vector(surface["outward"]).normalized()

    bpy.ops.object.camera_add(location=centre + outward * (diameter * 2.5))
    camera = bpy.context.object
    camera.name = "ENGRAVING_INSPECTION_CAMERA"
    camera.rotation_euler = (centre - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = diameter * 1.2

    scene = bpy.context.scene
    scene.camera = camera
    try:
        scene.render.engine = "BLENDER_WORKBENCH_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "SINGLE"
    shading.single_color = (0.62, 0.66, 0.72)
    shading.show_shadows = True
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.curvature_ridge_factor = 2.0
    shading.curvature_valley_factor = 2.0

    scene.render.resolution_x = 700
    scene.render.resolution_y = 700
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.filepath = str(args.output.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    print(f"INSPECTION_RENDER {args.output.resolve()}")


if __name__ == "__main__":
    main()
