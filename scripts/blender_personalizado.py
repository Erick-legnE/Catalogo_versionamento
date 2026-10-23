"""Add a personalised name, letters, or image/logo to an existing button .blend.

This is deliberately a separate finishing script: it never changes the original
button builder.  It opens a copy of a generated button, adds the personalised
feature, and saves a new .blend for comparison.

Examples (run with Blender):
  blender --background base_button.blend --python scripts/blender_personalizado.py -- \
    --output versions/c2622_ana_engraved.blend --text "ANA" --mode ENGRAVE

  blender --background base_button.blend --python scripts/blender_personalizado.py -- \
    --output versions/c2622_logo.blend --image assets/logo.png --mode RAISE

Text can be made into real Boolean-cut geometry with --geometry BOOLEAN.  Image
files are rendered as an accurately positioned printable/decal simulation;
turning a raster image into a manufacturable cut path still requires vectorising
and approving its contours.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]


def parse_color(value: str) -> tuple[float, float, float, float]:
    value = value.strip().lstrip("#")
    if len(value) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
        raise argparse.ArgumentTypeError("colour must be RRGGBB, for example 1A1A1A")
    return tuple(int(value[index : index + 2], 16) / 255 for index in range(0, 6, 2)) + (1.0,)


def parse_xy(value: str) -> tuple[float, float]:
    try:
        x, y = (float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("position must be X,Y in millimetres, for example 0,0") from exc
    return x, y


AUTOMATION_FONTS = {
    "Arial": Path(r"C:\Windows\Fonts\arial.ttf"),
    "Times New Roman": Path(r"C:\Windows\Fonts\times.ttf"),
    "Georgia": Path(r"C:\Windows\Fonts\georgia.ttf"),
    "Trebuchet MS": Path(r"C:\Windows\Fonts\trebuc.ttf"),
    "Courier New": Path(r"C:\Windows\Fonts\cour.ttf"),
}


def automation_layer_settings(path: Path, layer_number: int) -> dict:
    """Translate one automacao.html text layer from preview pixels to millimetres."""
    data = json.loads(path.read_text(encoding="utf-8"))
    item = data.get("item") or {}
    personalization = data.get("personalization") or {}
    assets = personalization.get("assets") or []
    matches = [asset for asset in assets if int(asset.get("layer", 0) or 0) == layer_number]
    if len(matches) != 1:
        raise RuntimeError(f"Automation layer {layer_number} was not found exactly once")
    asset = matches[0]
    if asset.get("kind") != "text" or not str(asset.get("text") or "").strip():
        raise RuntimeError(f"Automation layer {layer_number} is not a native text layer")
    size_mm = float(item.get("size_tam") or 0)
    if size_mm <= 0:
        raise RuntimeError("Automation request has no valid button TAM")
    coordinate_system = personalization.get("coordinate_system") or {}
    diameter_px = float(coordinate_system.get("button_diameter_px") or 518)
    if diameter_px <= 0:
        raise RuntimeError("Automation coordinate system has an invalid button diameter")
    footprint = asset.get("preview_footprint_px") or {}
    width_px = float(footprint.get("width_px") or 0)
    height_px = float(footprint.get("height_px") or 0)
    if width_px <= 0 or height_px <= 0:
        raise RuntimeError("Automation text layer has no valid preview footprint")
    curvature = float(asset.get("curvature") or 0)
    if not -1.0 <= curvature <= 1.0:
        raise RuntimeError("Automation text curvature must be between -1 and 1")
    mm_per_px = size_mm / diameter_px
    selected_face = ((data.get("visual_reference") or {}).get("pastilha_faces") or {}).get("selected", "front")
    # The builder's physically visible photo-facing side is +Y (BACK in the
    # legacy script terminology).  Keep the schema-facing names intuitive.
    blender_face = "BACK" if selected_face == "front" else "FRONT"
    font_family = str(asset.get("font_family") or "Arial")
    custom_font = personalization.get("custom_font") if isinstance(personalization, dict) else None
    uploaded_font_path = None
    if isinstance(custom_font, dict) and custom_font.get("filename"):
        candidate = (path.parent / str(custom_font["filename"])).resolve()
        # The request package is the trust boundary: the custom font may only
        # be read from its own folder, never from a client-controlled path.
        if candidate.parent == path.parent.resolve() and candidate.is_file():
            uploaded_font_path = candidate
            font_family = str(custom_font.get("family_name") or font_family)
        else:
            raise RuntimeError("The request declares an uploaded font, but its stored file is unavailable")
    font_path = uploaded_font_path or AUTOMATION_FONTS.get(font_family)
    production_rules = personalization.get("production_rules") if isinstance(personalization, dict) else {}
    return {
        "request_path": str(path.resolve()),
        "layer": layer_number,
        "text": str(asset["text"]).strip(),
        "font_family": font_family,
        "font_path": str(font_path) if font_path and font_path.is_file() else None,
        "font_source": "uploaded" if uploaded_font_path else "system_mapping",
        "font_sha256": custom_font.get("sha256") if isinstance(custom_font, dict) else None,
        "mode": str(asset.get("geometry_mode") or "ENGRAVE").upper(),
        "depth_mm": float(asset.get("depth_mm") or 0.35),
        "curvature": curvature,
        "face": blender_face,
        "source_face": selected_face,
        "position_mm": (
            float(asset.get("position_x") or 0) * mm_per_px * (-1 if blender_face == "BACK" else 1),
            -float(asset.get("position_y") or 0) * mm_per_px,
        ),
        "rotation_degrees": -float(asset.get("rotation_deg") or 0),
        "target_width_mm": width_px * mm_per_px,
        "target_height_mm": height_px * mm_per_px,
        "flip_x": bool(asset.get("flip_x")),
        "flip_y": bool(asset.get("flip_y")),
        "mm_per_preview_px": mm_per_px,
        "pastilha_back_face_recess_mm": float((production_rules or {}).get("pastilha_back_face_recess_mm") or 0.2),
    }


def find_button_body():
    import bpy  # type: ignore

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and not obj.name.startswith("Personalizado_")]
    if not meshes:
        raise RuntimeError("No mesh was found in the input .blend. Generate or open the base button first.")
    named = [obj for obj in meshes if "button" in obj.name.lower()]
    return max(named or meshes, key=lambda obj: obj.dimensions.x * obj.dimensions.y * max(obj.dimensions.z, 0.001))


def body_bounds(body) -> dict[str, float]:
    from mathutils import Vector  # type: ignore

    corners = [body.matrix_world @ Vector(corner) for corner in body.bound_box]
    return {
        "min_x": min(point.x for point in corners), "max_x": max(point.x for point in corners),
        "min_y": min(point.y for point in corners), "max_y": max(point.y for point in corners),
        "min_z": min(point.z for point in corners), "max_z": max(point.z for point in corners),
    }


def surface_spec(body, face: str) -> dict:
    """Describe where the personalisation sits and which way it faces."""
    bounds = body_bounds(body)
    centre_x = (bounds["min_x"] + bounds["max_x"]) / 2
    centre_y = (bounds["min_y"] + bounds["max_y"]) / 2
    centre_z = (bounds["min_z"] + bounds["max_z"]) / 2
    if face == "FRONT":  # The builder's standard product-facing side: -Y.
        return {"base": (centre_x, bounds["min_y"], centre_z), "outward": (0, -1, 0), "position_axes": ((1, 0, 0), (0, 0, 1)), "rotation": (math.pi / 2, 0, 0), "bounds": bounds}
    if face == "BACK":
        return {"base": (centre_x, bounds["max_y"], centre_z), "outward": (0, 1, 0), "position_axes": ((1, 0, 0), (0, 0, 1)), "rotation": (-math.pi / 2, 0, 0), "bounds": bounds}
    return {"base": (centre_x, centre_y, bounds["max_z"]), "outward": (0, 0, 1), "position_axes": ((1, 0, 0), (0, 1, 0)), "rotation": (0, 0, 0), "bounds": bounds}


def surface_location(surface: dict, position: tuple[float, float], outward_offset: float) -> tuple[float, float, float]:
    base = surface["base"]
    first_axis, second_axis = surface["position_axes"]
    outward = surface["outward"]
    return tuple(
        base[index] + position[0] * first_axis[index] + position[1] * second_axis[index] + outward_offset * outward[index]
        for index in range(3)
    )


def raycast_body_surface(body, surface: dict, position: tuple[float, float]):
    """Return the real body surface near the requested two-dimensional position.

    The bounding box is only an outer limit.  A domed button can be several
    tenths of a millimetre behind that limit at its centre, which is enough to
    leave a shallow Boolean cutter floating in front of the actual mesh.
    """
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    outward = Vector(surface["outward"]).normalized()
    inward = -outward
    first_axis = Vector(surface["position_axes"][0])
    second_axis = Vector(surface["position_axes"][1])
    target = Vector(surface_location(surface, position, 0.0))
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    inverse = evaluated.matrix_world.inverted()
    normal_matrix = evaluated.matrix_world.inverted().transposed().to_3x3()
    ray_distance = max(body.dimensions) * 2 + 10.0
    sample_offsets = (
        (0.0, 0.0), (0.25, 0.0), (-0.25, 0.0), (0.0, 0.25), (0.0, -0.25),
        (0.5, 0.0), (-0.5, 0.0), (0.0, 0.5), (0.0, -0.5),
        (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
    )
    for first_offset, second_offset in sample_offsets:
        outside = target + first_axis * first_offset + second_axis * second_offset + outward * 2.0
        local_origin = inverse @ outside
        local_direction = (inverse.to_3x3() @ inward).normalized()
        hit, location, normal, _face_index = evaluated.ray_cast(local_origin, local_direction, distance=ray_distance)
        if not hit:
            continue
        world_location = evaluated.matrix_world @ location
        world_normal = (normal_matrix @ normal).normalized()
        if world_normal.dot(outward) > 0.2:
            return world_location, world_normal
    raise RuntimeError("Could not find the actual button surface near the requested engraving position")


def material(name: str, rgba: tuple[float, float, float, float], metallic: float = 0.0):
    import bpy  # type: ignore

    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    bsdf = result.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = 0.35
    return result


def create_text(text: str, args, surface: dict, outward_offset: float):
    import bpy  # type: ignore

    curve = bpy.data.curves.new("Personalizado_TextCurve", type="FONT")
    curve.body = text
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = args.font_size
    curve.extrude = args.depth / 2
    if getattr(args, "geometry", "VISUAL") == "BOOLEAN":
        # A small bevel makes the converted font mesh more robust for Blender's
        # Boolean solver, especially with thin glyph strokes and counters.
        curve.bevel_depth = min(args.depth * 0.08, 0.03)
        curve.bevel_resolution = 2
    curve.resolution_u = 10
    curve.offset = 0.0
    if args.font:
        font_path = Path(args.font).expanduser().resolve()
        if not font_path.is_file():
            raise RuntimeError(f"Font not found: {font_path}")
        curve.font = bpy.data.fonts.load(str(font_path), check_existing=True)
    obj = bpy.data.objects.new("Personalizado_Text", curve)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.update()
    scale_x = 1.0
    scale_y = 1.0
    if args.target_width_mm:
        scale_x = args.target_width_mm / max(obj.dimensions.x, 1e-9)
    if args.target_height_mm:
        scale_y = args.target_height_mm / max(obj.dimensions.y, 1e-9)
    if args.face == "BACK":
        # Looking at the +Y face reverses the face-local horizontal axis.  Flip
        # both text-plane axes so the glyphs remain readable and upright from
        # outside the button.
        scale_x *= -1.0
        scale_y *= -1.0
    if args.flip_x:
        scale_x *= -1.0
    if args.flip_y:
        scale_y *= -1.0
    obj.scale.x = scale_x
    obj.scale.y = scale_y
    obj.location = surface_location(surface, args.position, outward_offset)
    obj.rotation_euler = surface["rotation"]
    obj.rotation_euler.rotate_axis("Z", math.radians(args.rotation))
    obj.data.materials.append(material("Personalizado_Text_Material", args.color, metallic=0.15 if args.mode == "RAISE" else 0.0))
    return obj


def preview_curve_vertex(
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
    curvature: float,
) -> tuple[float, float]:
    """Move a point along the size-preserving Ficha curvature baseline.

    Browser canvas Y points down while Blender text-local Y points up, hence
    the subtraction of the browser displacement below.
    """
    min_x, max_x, min_y, max_y = bounds
    width = max_x - min_x
    height = max_y - min_y
    if width <= 1e-9 or height <= 1e-9 or math.isclose(curvature, 0.0, abs_tol=1e-9):
        return x, y
    normalized_x = max(-1.0, min(1.0, ((x - min_x) / width) * 2.0 - 1.0))
    browser_displacement = curvature * (normalized_x * normalized_x - 0.333) * height * 0.62
    return x, y - browser_displacement


def preview_curve_pose(
    x: float,
    bounds: tuple[float, float, float, float],
    curvature: float,
) -> tuple[float, float]:
    """Return the rigid vertical offset and tangent angle for one glyph."""
    min_x, max_x, min_y, max_y = bounds
    width = max_x - min_x
    height = max_y - min_y
    if width <= 1e-9 or height <= 1e-9 or math.isclose(curvature, 0.0, abs_tol=1e-9):
        return 0.0, 0.0
    normalized_x = max(-1.0, min(1.0, ((x - min_x) / width) * 2.0 - 1.0))
    offset = -curvature * (normalized_x * normalized_x - 0.333) * height * 0.62
    slope = -curvature * 4.0 * normalized_x * height * 0.62 / width
    return offset, math.atan(slope)


def rigid_curve_point(
    x: float,
    y: float,
    pivot_x: float,
    pivot_y: float,
    offset: float,
    angle: float,
) -> tuple[float, float]:
    """Rotate and translate a glyph point without changing its scale."""
    delta_x = x - pivot_x
    delta_y = y - pivot_y
    cosine, sine = math.cos(angle), math.sin(angle)
    return (
        pivot_x + cosine * delta_x - sine * delta_y,
        pivot_y + sine * delta_x + cosine * delta_y + offset,
    )


def connected_glyph_groups(mesh, expected_glyphs: int = 0) -> tuple[list[list[int]], int]:
    """Group connected mesh pieces into glyphs, including dots and accents."""
    neighbours: list[set[int]] = [set() for _ in mesh.vertices]
    for edge in mesh.edges:
        first, second = edge.vertices
        neighbours[first].add(second)
        neighbours[second].add(first)
    remaining = set(range(len(mesh.vertices)))
    components: list[list[int]] = []
    while remaining:
        start = remaining.pop()
        component = [start]
        stack = [start]
        while stack:
            current = stack.pop()
            attached = neighbours[current] & remaining
            remaining.difference_update(attached)
            stack.extend(attached)
            component.extend(attached)
        components.append(component)

    def interval(indices: list[int]) -> tuple[float, float]:
        values = [mesh.vertices[index].co.x for index in indices]
        return min(values), max(values)

    ordered = sorted(components, key=lambda indices: interval(indices)[0])
    component_count = len(ordered)
    if expected_glyphs > 0 and len(ordered) >= expected_glyphs:
        groups = [list(component) for component in ordered]
        while len(groups) > expected_glyphs:
            centres = [sum(interval(group)) / 2.0 for group in groups]
            merge_at = min(range(len(groups) - 1), key=lambda index: abs(centres[index + 1] - centres[index]))
            groups[merge_at].extend(groups.pop(merge_at + 1))
        return groups, component_count

    groups: list[list[int]] = []
    group_intervals: list[tuple[float, float]] = []
    for component in ordered:
        component_min, component_max = interval(component)
        if groups and component_min <= group_intervals[-1][1] + 1e-6:
            groups[-1].extend(component)
            previous_min, previous_max = group_intervals[-1]
            group_intervals[-1] = (min(previous_min, component_min), max(previous_max, component_max))
        else:
            groups.append(list(component))
            group_intervals.append((component_min, component_max))
    return groups, component_count


def apply_text_curvature(text_obj, curvature: float, expected_glyphs: int = 0) -> dict:
    """Curve text with rigid per-glyph transforms that preserve letter size."""
    import bpy  # type: ignore

    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = text_obj
    text_obj.select_set(True)
    if text_obj.type != "MESH":
        bpy.ops.object.convert(target="MESH")
    vertices = list(text_obj.data.vertices)
    if not vertices:
        raise RuntimeError("Converted text has no vertices")
    min_x = min(vertex.co.x for vertex in vertices)
    max_x = max(vertex.co.x for vertex in vertices)
    min_y = min(vertex.co.y for vertex in vertices)
    max_y = max(vertex.co.y for vertex in vertices)
    bounds = (min_x, max_x, min_y, max_y)
    groups, component_count = connected_glyph_groups(text_obj.data, expected_glyphs)
    maximum_radius_error = 0.0
    offsets: list[float] = []
    angles: list[float] = []
    for group in groups:
        group_vertices = [text_obj.data.vertices[index] for index in group]
        group_min_x = min(vertex.co.x for vertex in group_vertices)
        group_max_x = max(vertex.co.x for vertex in group_vertices)
        group_min_y = min(vertex.co.y for vertex in group_vertices)
        group_max_y = max(vertex.co.y for vertex in group_vertices)
        pivot_x = (group_min_x + group_max_x) / 2.0
        pivot_y = (group_min_y + group_max_y) / 2.0
        offset, angle = preview_curve_pose(pivot_x, bounds, curvature)
        offsets.append(offset)
        angles.append(angle)
        for vertex in group_vertices:
            delta_x = vertex.co.x - pivot_x
            delta_y = vertex.co.y - pivot_y
            radius_before = math.hypot(delta_x, delta_y)
            vertex.co.x, vertex.co.y = rigid_curve_point(
                vertex.co.x, vertex.co.y, pivot_x, pivot_y, offset, angle
            )
            radius_after = math.hypot(vertex.co.x - pivot_x, vertex.co.y - (pivot_y + offset))
            maximum_radius_error = max(maximum_radius_error, abs(radius_after - radius_before))
    text_obj.data.update()
    return {
        "applied": not math.isclose(curvature, 0.0, abs_tol=1e-9),
        "value": curvature,
        "vertex_count": len(vertices),
        "connected_component_count": component_count,
        "glyph_group_count": len(groups),
        "transformation": "rigid_per_glyph",
        "glyph_size_max_radius_error": round(maximum_radius_error, 9),
        "local_y_offset_min": round(min(offsets, default=0.0), 6),
        "local_y_offset_max": round(max(offsets, default=0.0), 6),
        "tangent_angle_min_degrees": round(math.degrees(min(angles, default=0.0)), 6),
        "tangent_angle_max_degrees": round(math.degrees(max(angles, default=0.0)), 6),
    }


def apply_text_boolean(body, text_obj, surface: dict, args) -> dict:
    """Carve text into the body. Boolean is intentionally opt-in."""
    import bmesh  # type: ignore
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    surface_point, surface_normal = raycast_body_surface(body, surface, args.position)
    outward = Vector(surface["outward"]).normalized()
    body_outer = max(
        (body.matrix_world @ Vector(corner)).dot(outward)
        for corner in body.bound_box
    )
    surface_projection = surface_point.dot(outward)
    clearance = max(args.depth * 0.2, 0.05)
    desired_inner = surface_projection - args.depth
    desired_outer = body_outer + clearance
    if desired_outer <= desired_inner:
        raise RuntimeError("The calculated engraving cutter has no usable depth")

    curvature_diagnostics = apply_text_curvature(
        text_obj, args.curvature, sum(not character.isspace() for character in (args.text or ""))
    )
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # Remap the cutter's extrusion axis so that it starts at the requested
    # engraving depth and extends beyond the outermost body bound.  This makes
    # the cutter cross a domed surface instead of merely crossing its bounding
    # box plane.
    world_points = [text_obj.matrix_world @ vertex.co for vertex in text_obj.data.vertices]
    current_projections = [point.dot(outward) for point in world_points]
    current_inner = min(current_projections)
    current_outer = max(current_projections)
    if math.isclose(current_inner, current_outer, abs_tol=1e-9):
        raise RuntimeError("Converted text cutter has no thickness")
    inverse_text = text_obj.matrix_world.inverted()
    for vertex, world_point, current in zip(text_obj.data.vertices, world_points, current_projections):
        ratio = (current - current_inner) / (current_outer - current_inner)
        target_projection = desired_inner + ratio * (desired_outer - desired_inner)
        adjusted_world = world_point + outward * (target_projection - current)
        vertex.co = inverse_text @ adjusted_world
    text_obj.data.update()
    bpy.context.view_layer.objects.active = text_obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    remesh = text_obj.modifiers.new("Personalizado_CutterRemesh", type="REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = max(min(args.depth / 12, 0.03), 0.005)
    bpy.context.view_layer.objects.active = text_obj
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    bpy.context.view_layer.update()
    vertices_before = len(body.data.vertices)
    polygons_before = len(body.data.polygons)
    cutter_vertices = len(text_obj.data.vertices)
    modifier = body.modifiers.new("Personalizado_Engraving", type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "MANIFOLD"
    modifier.object = text_obj
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.context.view_layer.update()
    vertices_after = len(body.data.vertices)
    polygons_after = len(body.data.polygons)
    bpy.data.objects.remove(text_obj, do_unlink=True)
    if vertices_after == vertices_before and polygons_after == polygons_before:
        raise RuntimeError("Boolean engraving did not change the button mesh")

    # Validate rather than capping boundary loops.  Filling those loops can
    # conceal the engraving even though it technically closes the mesh.
    bm = bmesh.new()
    bm.from_mesh(body.data)
    boundary_edges = sum(1 for edge in bm.edges if edge.is_boundary)
    non_manifold_edges = sum(1 for edge in bm.edges if not edge.is_manifold)
    bm.free()
    if boundary_edges or non_manifold_edges:
        raise RuntimeError(
            "Boolean engraving left invalid topology: "
            f"boundary={boundary_edges}, non_manifold={non_manifold_edges}"
        )
    return {
        "surface_point_world": tuple(round(value, 6) for value in surface_point),
        "surface_normal_world": tuple(round(value, 6) for value in surface_normal),
        "surface_projection": round(surface_projection, 6),
        "cutter_inner_projection": round(desired_inner, 6),
        "cutter_outer_projection": round(desired_outer, 6),
        "cutter_vertices": cutter_vertices,
        "body_vertices_before": vertices_before,
        "body_vertices_after": vertices_after,
        "body_polygons_before": polygons_before,
        "body_polygons_after": polygons_after,
        "boundary_edges": boundary_edges,
        "non_manifold_edges": non_manifold_edges,
        "curvature": curvature_diagnostics,
    }


def create_image_decal(image_path: Path, args, surface: dict, outward_offset: float):
    import bpy  # type: ignore

    if not image_path.is_file():
        raise RuntimeError(f"Image not found: {image_path}")
    image = bpy.data.images.load(str(image_path.resolve()), check_existing=True)
    width, height = image.size
    if not width or not height:
        raise RuntimeError(f"Image has no usable dimensions: {image_path}")
    aspect = width / height
    decal_width = args.max_width
    decal_height = decal_width / aspect
    if decal_height > args.max_height:
        decal_height = args.max_height
        decal_width = decal_height * aspect
    bpy.ops.mesh.primitive_plane_add(size=1, location=surface_location(surface, args.position, outward_offset), rotation=surface["rotation"])
    decal = bpy.context.object
    decal.name = "Personalizado_Image"
    decal.dimensions = (decal_width, decal_height, 1)
    decal.rotation_euler.rotate_axis("Z", math.radians(args.rotation))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mat = bpy.data.materials.new("Personalizado_Image_Material")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if "Alpha" in tex.outputs and "Alpha" in bsdf.inputs:
        links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.4
    bsdf.inputs["Metallic"].default_value = 0.1 if args.mode == "RAISE" else 0.0
    # Blender 4/5 uses surface_render_method; older installs use blend_method.
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    elif hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    decal.data.materials.append(mat)
    return decal


def apply_material_preset(body, style: str) -> None:
    palettes = {
        "DARK": ((0.015, 0.035, 0.045, 1), 0.15, 0.28),
        "LIGHT": ((0.72, 0.75, 0.73, 1), 0.05, 0.38),
        "GOLD": ((0.44, 0.23, 0.05, 1), 0.62, 0.24),
    }
    color, metallic, roughness = palettes[style]
    preset = material(f"Personalizado_Preset_{style}", color, metallic)
    preset.node_tree.nodes.get("Principled BSDF").inputs["Roughness"].default_value = roughness
    body.data.materials.clear()
    body.data.materials.append(preset)


def prepare_preview_scene(body, surface: dict, style: str) -> None:
    """Create a predictable preview aimed at the selected personalisation face."""
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    bounds = body_bounds(body)
    min_x, max_x, min_y, max_y = bounds["min_x"], bounds["max_x"], bounds["min_y"], bounds["max_y"]
    centre = Vector(surface["base"])
    outward = Vector(surface["outward"]).normalized()
    horizontal = Vector(surface["position_axes"][0]).normalized()
    vertical = Vector(surface["position_axes"][1]).normalized()
    radius = max(max_x - min_x, max_y - min_y) / 2
    camera = bpy.data.objects.get("PERSONALIZADO_PREVIEW_CAMERA")
    if not camera:
        bpy.ops.object.camera_add()
        camera = bpy.context.object
        camera.name = "PERSONALIZADO_PREVIEW_CAMERA"
    # Earlier previews always placed the camera on -Y, which photographed the
    # opposite side whenever Automacao's selected "front" mapped to the
    # builder's legacy BACK/+Y face.  Build the camera and lights from the
    # selected surface basis instead of from a hard-coded world direction.
    camera.location = centre + outward * (radius * 4.5) + vertical * (radius * 3.5)
    camera.rotation_euler = (centre - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 50
    bpy.context.scene.camera = camera
    light_setup = {
        "DARK": ((800, 500), (0.05, 0.05, 0.05)),
        "LIGHT": ((1100, 700), (0.72, 0.72, 0.72)),
        "GOLD": ((950, 380), (0.09, 0.06, 0.025)),
    }[style]
    for (name, offset, _energy, size), energy in zip((
        ("PERSONALIZADO_KEY", horizontal * (radius * 2.0) + outward * (radius * 2.5) + vertical * (radius * 2.0), 0, radius * 1.3),
        ("PERSONALIZADO_FILL", -horizontal * (radius * 1.5) + outward * (radius * 1.8) + vertical * (radius * 0.4), 0, radius),
    ), light_setup[0]):
        light = bpy.data.objects.get(name)
        if not light:
            bpy.ops.object.light_add(type="AREA")
            light = bpy.context.object
            light.name = name
        light.location = centre + offset
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size
        light.rotation_euler = (centre - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.world.color = light_setup[1]


def render_if_requested(output: Path, should_render: bool, body, surface: dict, preview_camera: bool, preview_style: str) -> Path | None:
    import bpy  # type: ignore

    if not should_render:
        return None
    scene = bpy.context.scene
    if preview_camera:
        prepare_preview_scene(body, surface, preview_style)
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:  # Compatibility with older Blender releases.
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.filepath = str(output.with_suffix(".png"))
    bpy.ops.render.render(write_still=True)
    return output.with_suffix(".png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New personalised .blend; base file is left untouched")
    parser.add_argument("--automation-json", type=Path, help="solicitacao.json exported by automacao.html")
    parser.add_argument("--automation-layer", type=int, default=1, help="One-based native text layer from --automation-json")
    parser.add_argument("--text", help="Name, letters, numbers, or other UTF-8 text")
    parser.add_argument("--image", type=Path, help="PNG/JPG/logo image to simulate on the button surface")
    parser.add_argument("--mode", choices=("ENGRAVE", "RAISE"), default="ENGRAVE")
    parser.add_argument("--face", choices=("FRONT", "BACK", "TOP"), default="FRONT", help="Button face to personalise; FRONT is the usual product-facing side")
    parser.add_argument("--geometry", choices=("VISUAL", "BOOLEAN"), default="VISUAL", help="BOOLEAN creates a true cut for text only")
    parser.add_argument("--position", type=parse_xy, default=(0.0, 0.0), help="X,Y in mm from button centre")
    parser.add_argument("--rotation", type=float, default=0.0, help="Degrees around button centre")
    parser.add_argument("--curvature", type=float, default=0.0, help="Ficha curvature from -1 (downward centre) to 1 (upward centre)")
    parser.add_argument("--font", help="Optional .ttf/.otf font path")
    parser.add_argument("--font-size", type=float, default=3.0, help="Text height in mm")
    parser.add_argument("--target-width-mm", type=float, help="Exact text footprint width, normally supplied by automacao.html")
    parser.add_argument("--target-height-mm", type=float, help="Exact text footprint height, normally supplied by automacao.html")
    parser.add_argument("--flip-x", action="store_true", help="Mirror the layer horizontally after face correction")
    parser.add_argument("--flip-y", action="store_true", help="Mirror the layer vertically")
    parser.add_argument("--depth", type=float, default=0.25, help="Raise/engraving depth in mm")
    parser.add_argument("--color", type=parse_color, default=parse_color("171717"), help="RRGGBB feature colour")
    parser.add_argument("--max-width", type=float, default=9.0, help="Maximum image width in mm")
    parser.add_argument("--max-height", type=float, default=9.0, help="Maximum image height in mm")
    parser.add_argument("--render", action="store_true", help="Also render a PNG next to the output")
    parser.add_argument("--preview-camera", action="store_true", help="Use a consistent product-preview camera and lighting when rendering")
    parser.add_argument("--preview-style", choices=("DARK", "LIGHT", "GOLD"), default="DARK", help="Lighting/world preset for --preview-camera")
    parser.add_argument("--material-preset", action="store_true", help="Replace the button's materials with the selected preset")
    parser.add_argument("--report", type=Path, help="Optional JSON summary")
    args = parser.parse_args(blender_args())
    automation_context = None
    if args.automation_json:
        automation_context = automation_layer_settings(args.automation_json.resolve(), args.automation_layer)
        args.text = automation_context["text"]
        args.mode = automation_context["mode"]
        args.geometry = "BOOLEAN" if args.mode == "ENGRAVE" else "VISUAL"
        args.face = automation_context["face"]
        args.position = automation_context["position_mm"]
        args.rotation = automation_context["rotation_degrees"]
        args.curvature = automation_context["curvature"]
        args.depth = automation_context["depth_mm"]
        args.target_width_mm = automation_context["target_width_mm"]
        args.target_height_mm = automation_context["target_height_mm"]
        args.flip_x = automation_context["flip_x"]
        args.flip_y = automation_context["flip_y"]
        if automation_context["font_path"]:
            args.font = automation_context["font_path"]
    if not args.text and not args.image:
        parser.error("provide --text, --image, or both")
    if args.depth <= 0 or args.font_size <= 0 or args.max_width <= 0 or args.max_height <= 0:
        parser.error("depth, font size, and image limits must be positive")
    if not -1.0 <= args.curvature <= 1.0:
        parser.error("curvature must be between -1 and 1")
    if args.geometry == "BOOLEAN" and args.mode != "ENGRAVE":
        parser.error("--geometry BOOLEAN is only valid with --mode ENGRAVE")
    if args.geometry == "BOOLEAN" and args.image:
        parser.error("raster images use VISUAL mode; vectorise the art before making a manufacturing cut")

    body = find_button_body()
    if args.material_preset:
        apply_material_preset(body, args.preview_style)
    surface = surface_spec(body, args.face)
    visual_offset = args.depth / 2 + 0.005 if args.mode == "RAISE" else 0.006
    created = []
    geometry_diagnostics = None
    if args.text:
        text_obj = create_text(args.text, args, surface, visual_offset)
        if args.geometry == "BOOLEAN":
            geometry_diagnostics = apply_text_boolean(body, text_obj, surface, args)
        else:
            if not math.isclose(args.curvature, 0.0, abs_tol=1e-9):
                apply_text_curvature(
                    text_obj, args.curvature, sum(not character.isspace() for character in (args.text or ""))
                )
            created.append(text_obj.name)
    if args.image:
        created.append(create_image_decal(args.image, args, surface, visual_offset).name)

    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_if_requested(args.output, args.render, body, surface, args.preview_camera, args.preview_style)
    import bpy  # type: ignore

    bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
    report = {
        "output": str(args.output), "base_button": body.name,
        "mode": args.mode, "geometry": args.geometry,
        "text": args.text, "image": str(args.image.resolve()) if args.image else None,
        "face": args.face, "position_mm": args.position, "surface_base_world": surface["base"], "rotation_degrees": args.rotation, "curvature": args.curvature, "preview_style": args.preview_style, "material_preset": args.material_preset,
        "geometry_diagnostics": geometry_diagnostics,
        "automation_context": automation_context,
        "created_objects": created, "render": str(rendered) if rendered else None,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
