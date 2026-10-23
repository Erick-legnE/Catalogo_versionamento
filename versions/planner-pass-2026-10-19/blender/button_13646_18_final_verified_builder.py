import bpy
import bmesh
import math
import os
from mathutils import Vector

# ============================================================================
# DXF BUTTON BUILDER v28
# ============================================================================
# Topology-first version.
#
# The previous versions used Bridge Edge Loops + Mesh Spin on the bridged mesh.
# That did produce the button silhouette, but the final mesh could become
# massively non-manifold (v11 reported boundary_edges=0 but
# nonmanifold_edges=16368). That is why the shading and Boolean holes became
# increasingly strange.
#
# v12 keeps the useful/manual parts of the workflow:
#   IMPORT FRONT + BACK DXF
#       -> convert to mesh
#       -> Merge by Distance
#       -> rotate BACK 180 degrees around Z
#       -> align one endpoint
#       -> scale BACK so the opposite endpoint matches
#       -> resample both profiles
#
# Instead of asking Blender's Spin operator to repair a complicated bridged
# surface, v12 closes the two facas into ONE clean 2D cross-section and builds
# the surface of revolution directly. This is mathematically the same
# operation as revolving that bridged cross-section, but gives us explicit
# control over seam/axis vertices and produces a predictable manifold mesh.
#
# Holes are then cut with Boolean Difference on that clean solid.
# Textures/materials are intentionally NOT included.
# ============================================================================

# ----------------------------------------------------------------------------
# FILES
# ----------------------------------------------------------------------------
FRONT_DXF_PATH = 'C:\\Users\\Aprendiz Financeiro\\BRASIL BOTOES LTDA\\Desenvolvimento - Documentos\\facas\\opn-18.dxf'
BACK_DXF_PATH = 'C:\\Users\\Aprendiz Financeiro\\BRASIL BOTOES LTDA\\Desenvolvimento - Documentos\\facas\\op-40-44.dxf'

# Leave empty only when you intentionally want to duplicate the front profile.
# For your current setup, keep the real back DXF here.

# Optional hard-coded operator id. Leave empty to auto-detect the same DXF
# operator style used by the working Claude script.
DXF_IMPORT_OPERATOR_ID = ""

# ----------------------------------------------------------------------------
# PROFILE / FIT SETTINGS
# ----------------------------------------------------------------------------
# v23 orientation:
# - FRONT stays exactly as imported.
# - BACK rotates 180 degrees around its own geometric X axis before fitting.
BACK_ROTATE_180_X = True

# The DXF importer in your setup is producing millimeter-like coordinates
# directly as Blender scene units.
SCENE_UNITS_PER_MM = 1.0

# Merge-by-distance cleanup for imported facas.
WELD_TOLERANCE = 0.01

# Number of samples along each faca before the final revolution.
PROFILE_POINT_COUNT = 128

# v25 MANUAL-FIT MODEL
#
# The two endpoints have DIFFERENT jobs:
#
#   AXIS endpoint (visual LEFT in your current step preview)
#       - FRONT and BACK stay separated in Y.
#       - They only need the same X so the connecting segment lies on the
#         Y revolution axis.
#
#   MERGE endpoint (visual RIGHT)
#       - FRONT and BACK should occupy the exact same point.
#       - This is the point that would be joined by Blender's Merge by Distance.
#
# The BACK is therefore anchored at the MERGE endpoint, then uniformly scaled
# so its opposite/AXIS endpoint reaches the FRONT axis X.
FIT_BACK_TO_FRONT = True

# Keep False for this manual-fit model. Rotating in XY would change which
# endpoint lies on the common Y revolution axis.
FIT_ALLOW_ENDPOINT_ROTATION = False

# Revolve axis endpoint.
#
# v24 IMPORTANT:
# The previous code only supported a profile extending toward +X from the
# revolution axis, so it effectively forced the MIN_X endpoint to be the axis.
# In the current facas that appears on the visual RIGHT side in your viewport.
#
# For this button we want the opposite endpoint: the visual LEFT side, which
# corresponds to MAX_X in the profile coordinates shown by the step preview.
#
# Supported modes:
#   "MIN_X"   = smaller-X endpoint
#   "MAX_X"   = larger-X endpoint
#   "CENTER_X"= bounding-box center (normally not for this workflow)
#   "CUSTOM"  = REVOLVE_AXIS_X
REVOLVE_AXIS_MODE = "MAX_X"
REVOLVE_AXIS_X = 0.0

# Snap the axis endpoint exactly onto the calculated revolution axis.
# This is intentionally separate from the endpoint fit. It prevents a tiny CAD
# coordinate mismatch from becoming a visible central hole after revolution.
SNAP_AXIS_ENDPOINT = True
AXIS_SNAP_TOLERANCE = 0.05
# v28 IMPORTANT: AXIS_SNAP_TOLERANCE is only for validating the true
# end vertex supplied by CAD. Do not collapse all near-axis vertices within
# that distance! At an 11.43 mm diameter, the first real surface vertex may
# be only 0.048 mm from the axis; collapsing it produces a T-junction where
# the profile overlaps the center-axis closure. This much smaller value is
# used to distinguish a real circular ring from an actual axis vertex.
AXIS_TOPOLOGY_EPS_MM = 0.000001

# ----------------------------------------------------------------------------
# EXACT BUTTON SIZE
# ----------------------------------------------------------------------------
# v28 can ask for the desired FINAL external button diameter and thickness in
# millimeters when the script starts.
#
# Enter 0 in the popup to preserve the DXF dimension on that axis and fall back
# to BUTTON_RADIAL_SCALE / BUTTON_AXIAL_SCALE below.
ASK_EXACT_SIZE_ON_START = False

DEFAULT_TARGET_DIAMETER_MM = 18.0
DEFAULT_TARGET_THICKNESS_MM = 3.2

# Legacy/fallback scale controls.
# These are used only when the matching target-mm value is 0.
BUTTON_RADIAL_SCALE = 1.00
BUTTON_AXIAL_SCALE = 1.00

# v28 PASTILHA MODEL (only used when Final Thickness is greater than zero).
# The final thickness belongs to the original flat sheet / pastilha, NOT to a
# rescaling of the cutting tools. We measure the real profile heights after
# uniform XY scaling to the requested final diameter and reserve the rest as
# a straight, uncut connector between the front and back surfaces.
PASTILHA_THICKNESS_MODE = True

# Rigidly rotate each open DXF curve so the chord between its two endpoints is
# horizontal BEFORE measuring its relief depth. This compensates for drawings
# whose straight baseline is slightly tilted, without stretching the curve.
# Set False for a faca whose intentional design requires the original tilt.
LEVEL_FACA_ENDPOINT_CHORDS = True
MAX_CHORD_LEVEL_ANGLE_DEG = 25.0

# A very small minimum positive gap prevents coincident front/back surfaces.
# The value is expressed in real millimeters, not Blender coordinates.
MIN_PASTILHA_CORE_MM = 0.02

# Kept only as a legacy/manual option. For this workflow it should remain 0.
# A non-zero Z separation is a radial offset after Y revolution and can create
# an unintended center radius/hole.
FACA_SEPARATION_Z = 0.0

# Revolution quality. 64 was working well for you and is kept intentionally.
SPIN_STEPS = 64

# Small radius used to decide whether a profile vertex lies on the revolution
# axis. Increase only if your imported CAD coordinates have noticeable noise.
REVOLVE_AXIS_EPSILON = 1e-6

# ----------------------------------------------------------------------------
# SOURCE OBJECT HANDLING
# ----------------------------------------------------------------------------
KEEP_IMPORTED_FACA_OBJECTS = True

# Keep a diagnostic copy of the manually bridged facas in the generated collection.
# False keeps the normal scene cleaner; True is useful when debugging the bridge step.
KEEP_BRIDGE_PREVIEW = False

SOURCE_COLLECTION_NAME = "DXF_Button_Source"
GENERATED_COLLECTION_NAME = "DXF_Button_Generated"
TEMP_COLLECTION_NAME = "DXF_Button_Temp"
OUTPUT_OBJECT_NAME = "Button_3D"
BRIDGE_PREVIEW_NAME = "Button_Bridge_Preview"

# ----------------------------------------------------------------------------
# HOLES
# ----------------------------------------------------------------------------
CREATE_HOLES = True
HOLE_COUNT = 4
HOLE_RADIUS_MM = 0.9
HOLE_DISTANCE_MM = 2.8
HOLE_ANGLE_OFFSET_DEG = 45.0
HOLE_SEGMENTS = 24
HOLE_CUTTER_MARGIN_MM = 2.0
HOLE_BOOLEAN_SOLVER = "EXACT"

# ----------------------------------------------------------------------------
# DISPLAY
# ----------------------------------------------------------------------------
SHADE_SMOOTH = True
FINAL_ROTATE_X_DEG = 0.0
FINAL_ROTATE_Y_DEG = 0.0
FINAL_ROTATE_Z_DEG = 0.0

# ----------------------------------------------------------------------------
# INTERACTIVE STEP-BY-STEP MODE
# ----------------------------------------------------------------------------
# When True, running this script starts a Blender modal operator.
# Press ENTER / NUMPAD ENTER to execute the next major action.
# Press ESC at any point to stop and leave the current geometry visible.
INTERACTIVE_STEP_MODE = False

# Show algorithmic FRONT/BACK profile previews between the profile steps.
# These previews are recreated after every rotate/fit/scale/snap action, so
# you can literally watch the cross-section change as you press Enter.
STEP_SHOW_PROFILE_PREVIEWS = True

# Hide the raw converted DXF meshes once the algorithmic profile previews are
# visible, to make the current step easier to inspect.
STEP_HIDE_RAW_DXF_AFTER_EXTRACT = True

STEP_FRONT_PREVIEW_NAME = "__DXF_STEP_FRONT_PROFILE__"
STEP_BACK_PREVIEW_NAME = "__DXF_STEP_BACK_PROFILE__"
STEP_AXIS_PREVIEW_NAME = "__DXF_STEP_REVOLVE_AXIS__"
STEP_AXIS_CLOSURE_PREVIEW_NAME = "__DXF_STEP_AXIS_CLOSURE__"
STEP_OUTER_CLOSURE_PREVIEW_NAME = "__DXF_STEP_OUTER_CLOSURE__"
STEP_MERGE_MARKER_NAME = "__DXF_STEP_MERGE_POINT__"

# ----------------------------------------------------------------------------
# TEXTURE-READY OUTPUT
# ----------------------------------------------------------------------------
# v19 keeps the geometry workflow unchanged, but gives Button_3D a stable
# semantic/material/UV foundation for the separate texture script.
TEXTURE_READY_OUTPUT = True

# Move the final mesh so its local origin is the geometric center. This makes
# X/Z planar mapping and Y-based layer lookup predictable for every button.
RECENTER_OUTPUT = True

# Keep source facas for debugging, but hide them so they do not compete with
# Button_3D in the texture/render viewport.
HIDE_SOURCE_FACAS = True
CLEAR_SOURCE_COLLECTION_ON_START = True

TEXTURE_UV_MAP_NAME = "Button_Texture"
SURFACE_TYPE_ATTRIBUTE = "dxf_surface_type"
LAYER_Y_ATTRIBUTE = "dxf_layer_y"
PLANAR_U_ATTRIBUTE = "dxf_planar_u"
PLANAR_V_ATTRIBUTE = "dxf_planar_v"
SIDE_U_ATTRIBUTE = "dxf_side_u"
RADIAL_ATTRIBUTE = "dxf_radial_norm"

# Stable semantic face codes used by both the mesh attribute and the material
# slots. They deliberately do not depend on Blender's material slot ordering.
SURFACE_FRONT = 0
SURFACE_VERSO = 1
SURFACE_SIDE = 2
SURFACE_INTERIOR = 3

FRONT_MATERIAL_NAME = "BTN_FRONT_EXTERNAL"
VERSO_MATERIAL_NAME = "BTN_VERSO_EXTERNAL"
SIDE_MATERIAL_NAME = "BTN_SIDE_EXTERNAL"
INTERIOR_MATERIAL_NAME = "BTN_INTERIOR_CUT"


# ============================================================================
# LOGGING / UI
# ============================================================================

def log(message):
    print(f"[DXF BUTTON v28] {message}")


def show_popup(message, title="DXF Button Builder v28", icon='INFO'):
    if bpy.app.background:
        log(f"HEADLESS POPUP: {title}: {message}")
        return
    def draw(self, context):
        for line in str(message).split("\n"):
            self.layout.label(text=line[:240])
    try:
        bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
    except Exception:
        print(f"[{title}] {message}")


# ============================================================================
# COLLECTIONS / OBJECT HELPERS
# ============================================================================

def get_or_create_collection(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    else:
        try:
            if bpy.context.scene.collection.children.get(collection.name) is None:
                bpy.context.scene.collection.children.link(collection)
        except Exception:
            pass
    return collection


def clear_collection(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        return
    for obj in list(collection.objects):
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except ReferenceError:
            pass
        except Exception as exc:
            log(f"Cleanup warning: {exc}")


def safe_select_active(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def move_to_collection(obj, collection):
    for coll in list(obj.users_collection):
        try:
            coll.objects.unlink(obj)
        except Exception:
            pass
    collection.objects.link(obj)


# ============================================================================
# DXF IMPORT
# ============================================================================

def get_dxf_import_operator():
    if DXF_IMPORT_OPERATOR_ID:
        parts = DXF_IMPORT_OPERATOR_ID.split(".")
        if len(parts) != 2:
            raise RuntimeError(
                "DXF_IMPORT_OPERATOR_ID must look like 'import_scene.dxf'."
            )
        return getattr(getattr(bpy.ops, parts[0]), parts[1])

    for category_name in dir(bpy.ops):
        try:
            category = getattr(bpy.ops, category_name)
        except Exception:
            continue
        for op_name in dir(category):
            full_id = f"{category_name}.{op_name}".lower()
            if "dxf" in full_id and "import" in full_id:
                try:
                    return getattr(category, op_name)
                except Exception:
                    pass
    return None


def geometry_children(objects):
    result = []
    seen = set()
    for obj in objects:
        try:
            ptr = obj.as_pointer()
            if ptr in seen:
                continue
            seen.add(ptr)
        except Exception:
            pass

        if obj.type in {'CURVE', 'MESH', 'SURFACE'}:
            result.append(obj)
        elif obj.type == 'EMPTY':
            for child in obj.children_recursive:
                if child.type not in {'CURVE', 'MESH', 'SURFACE'}:
                    continue
                try:
                    ptr = child.as_pointer()
                    if ptr in seen:
                        continue
                    seen.add(ptr)
                except Exception:
                    pass
                result.append(child)
    return result


def import_dxf_file(filepath, label):
    if not filepath:
        raise RuntimeError(f"{label}: DXF path is empty.")
    if not os.path.exists(filepath):
        raise RuntimeError(f"{label}: DXF file not found:\n{filepath}")

    dxf_op = get_dxf_import_operator()
    if dxf_op is None:
        raise RuntimeError(
            f"{label}: no DXF import operator was found.\n"
            "Your working DXF extension may not be enabled."
        )

    before = set(bpy.context.scene.objects)
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)

    log(f"{label}: importing {filename}")
    try:
        # This is deliberately the same invocation style as the working Claude
        # script you supplied.
        dxf_op(
            filepath=filepath,
            directory=directory + os.sep,
            files=[{"name": filename}],
        )
    except Exception as exc:
        raise RuntimeError(f"{label}: DXF import operator failed: {exc}") from exc

    new_objects = list(set(bpy.context.scene.objects) - before)
    geom = geometry_children(new_objects)
    log(
        f"{label}: importer created {len(new_objects)} object(s), "
        f"usable geometry objects={len(geom)}"
    )
    for obj in geom:
        log(f"  {label} object: {obj.name} [{obj.type}]")

    if not geom:
        raise RuntimeError(
            f"{label}: importer returned successfully but created no usable geometry."
        )

    return geom


# ============================================================================
# IMPORTED MESH PREPARATION
# ============================================================================

def convert_join_weld(objects, label, target_collection):
    if not objects:
        raise RuntimeError(f"{label}: no geometry objects to prepare.")

    # Convert everything to mesh. The importer may return curves or mesh data.
    safe_select = []
    for obj in objects:
        try:
            obj.hide_viewport = False
            obj.hide_set(False)
            safe_select.append(obj)
        except Exception:
            pass

    bpy.ops.object.select_all(action='DESELECT')
    for obj in safe_select:
        try:
            obj.select_set(True)
        except Exception:
            pass

    if not safe_select:
        raise RuntimeError(f"{label}: imported objects disappeared before conversion.")

    bpy.context.view_layer.objects.active = safe_select[0]
    try:
        bpy.ops.object.convert(target='MESH')
    except Exception as exc:
        raise RuntimeError(f"{label}: could not convert DXF geometry to mesh: {exc}") from exc

    # Re-read selection after conversion because Blender may replace datablocks.
    meshes = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    if not meshes:
        raise RuntimeError(f"{label}: no mesh object remained after conversion.")

    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = f"{label}_Prepared"
    move_to_collection(obj, target_collection)

    # Manual equivalent of Edit Mode -> A -> M -> By Distance.
    safe_select_active(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    try:
        bpy.ops.mesh.merge_by_distance(distance=WELD_TOLERANCE)
    except Exception:
        bpy.ops.mesh.remove_doubles(threshold=WELD_TOLERANCE)
    bpy.ops.mesh.dissolve_degenerate(threshold=min(WELD_TOLERANCE, 1e-4))
    bpy.ops.object.mode_set(mode='OBJECT')

    log(f"{label}: converted to mesh + Merge by Distance complete.")
    return obj


# ============================================================================
# PROFILE EXTRACTION
# ============================================================================

def connected_components(adjacency):
    unseen = set(adjacency.keys())
    components = []
    while unseen:
        start = next(iter(unseen))
        stack = [start]
        unseen.remove(start)
        component = set()
        while stack:
            v = stack.pop()
            component.add(v)
            for n in adjacency[v]:
                if n in unseen:
                    unseen.remove(n)
                    stack.append(n)
        components.append(component)
    return components


def order_open_chain(component, adjacency, positions):
    endpoints = [
        v for v in component
        if len(adjacency[v] & component) == 1
    ]
    if len(endpoints) != 2:
        return None

    start = min(endpoints)
    ordered = [start]
    previous = None
    current = start

    while True:
        candidates = [
            n for n in adjacency[current]
            if n in component and n != previous
        ]
        if not candidates:
            break
        nxt = candidates[0]
        ordered.append(nxt)
        previous, current = current, nxt
        if current in endpoints and current != start:
            break
        if len(ordered) > len(component):
            return None

    if len(ordered) != len(component):
        return None
    return [positions[i].copy() for i in ordered]


def extract_profile_chain(obj, label):
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        positions = [v.co.copy() for v in bm.verts]
        adjacency = {v.index: set() for v in bm.verts}
        for e in bm.edges:
            a = e.verts[0].index
            b = e.verts[1].index
            adjacency[a].add(b)
            adjacency[b].add(a)

        components = connected_components(adjacency)
        candidates = []
        for component in components:
            chain = order_open_chain(component, adjacency, positions)
            if chain is None:
                continue
            length = sum(
                (chain[i + 1] - chain[i]).length
                for i in range(len(chain) - 1)
            )
            candidates.append((length, chain))

        if not candidates:
            degree_counts = {}
            for v, neighbours in adjacency.items():
                degree = len(neighbours)
                degree_counts[degree] = degree_counts.get(degree, 0) + 1
            raise RuntimeError(
                f"{label}: could not find a single simple open profile chain.\n"
                f"Components={len(components)}\n"
                f"Vertex degree counts={degree_counts}"
            )

        length, chain = max(candidates, key=lambda x: x[0])
        log(
            f"{label}: selected open profile | vertices={len(chain)} | "
            f"length={length:.6g}"
        )
        return chain
    finally:
        bm.free()


# ============================================================================
# PROFILE MATH / FITTING
# ============================================================================

def bounds_center(points):
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, 0.0))


def rotate_180_z(points):
    c = bounds_center(points)
    return [
        Vector((
            c.x - (p.x - c.x),
            c.y - (p.y - c.y),
            p.z,
        ))
        for p in points
    ]


def rotate_180_x(points):
    """Rotate a profile 180 degrees around X through its own geometric center.

    A 180° X rotation maps:
        X -> X
        Y -> 2*center_y - Y
        Z -> 2*center_z - Z

    For the imported 2D DXF profiles, this effectively flips the BACK profile
    in Y while preserving its X/radial coordinates.
    """
    ys = [p.y for p in points]
    zs = [p.z for p in points]

    cy = (min(ys) + max(ys)) * 0.5
    cz = (min(zs) + max(zs)) * 0.5

    return [
        Vector((
            p.x,
            cy - (p.y - cy),
            cz - (p.z - cz),
        ))
        for p in points
    ]


def translate_xy(points, delta):
    return [Vector((p.x + delta.x, p.y + delta.y, p.z)) for p in points]


def rotate_chain_xy(points, angle_rad, pivot):
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    result = []
    for p in points:
        dx = p.x - pivot.x
        dy = p.y - pivot.y
        result.append(Vector((
            pivot.x + dx * c - dy * s,
            pivot.y + dx * s + dy * c,
            p.z,
        )))
    return result


def normalize_chain_to_axis(points):
    """Orient a profile so points[0] is always the intended axis endpoint."""
    if len(points) < 2:
        return list(points)

    if REVOLVE_AXIS_MODE == "MIN_X":
        want_first = points[0].x <= points[-1].x
    elif REVOLVE_AXIS_MODE == "MAX_X":
        want_first = points[0].x >= points[-1].x
    elif REVOLVE_AXIS_MODE == "CUSTOM":
        want_first = (
            abs(points[0].x - REVOLVE_AXIS_X)
            <= abs(points[-1].x - REVOLVE_AXIS_X)
        )
    elif REVOLVE_AXIS_MODE == "CENTER_X":
        center_x = bounds_center(points).x
        want_first = (
            abs(points[0].x - center_x)
            <= abs(points[-1].x - center_x)
        )
    else:
        raise ValueError(
            "REVOLVE_AXIS_MODE must be MIN_X, MAX_X, CENTER_X, or CUSTOM."
        )

    return list(points) if want_first else list(reversed(points))


def fit_back_to_front_endpoints(front, back):
    """Manual-equivalent fit with independent AXIS and MERGE endpoints.

    After normalize_chain_to_axis():
        [0]  = AXIS endpoint (visual LEFT in the current workflow)
        [-1] = MERGE endpoint (visual RIGHT)

    We emulate the manual Blender workflow:
        1) put BACK's MERGE endpoint exactly on FRONT's MERGE endpoint;
        2) uniformly scale BACK about that merged point until BACK's AXIS
           endpoint has the same X as FRONT's AXIS endpoint;
        3) keep the AXIS endpoints separated in Y;
        4) snap the MERGE endpoint exactly, equivalent to Merge by Distance.

    The left/axis endpoints are NOT merged together. Their Y separation is the
    thickness/section gap that closes along the Y revolution axis.
    """
    front = normalize_chain_to_axis(front)
    back = normalize_chain_to_axis(back)

    if FIT_ALLOW_ENDPOINT_ROTATION:
        raise RuntimeError(
            "FIT_ALLOW_ENDPOINT_ROTATION must remain False for the v25 "
            "merge-endpoint / axis-endpoint workflow."
        )

    f_axis = front[0].copy()
    f_merge = front[-1].copy()

    b_axis = back[0].copy()
    b_merge = back[-1].copy()

    front_x_span = f_axis.x - f_merge.x
    back_x_span = b_axis.x - b_merge.x

    if abs(front_x_span) <= 1e-12:
        raise RuntimeError(
            "FRONT endpoint X span is effectively zero; cannot determine "
            "radial scale from MERGE endpoint to AXIS endpoint."
        )

    if abs(back_x_span) <= 1e-12:
        raise RuntimeError(
            "BACK endpoint X span is effectively zero; cannot determine "
            "radial scale from MERGE endpoint to AXIS endpoint."
        )

    scale = front_x_span / back_x_span

    if scale <= 0.0:
        raise RuntimeError(
            "FRONT/BACK endpoint directions disagree after normalization. "
            f"Computed scale={scale:.9g}. Check BACK 180° X rotation."
        )

    # Uniformly scale BACK about its own merge endpoint, while translating that
    # merge endpoint directly onto FRONT's merge endpoint.
    fitted = []

    for p in back:
        local = p - b_merge

        fitted.append(Vector((
            f_merge.x + local.x * scale,
            f_merge.y + local.y * scale,
            f_merge.z + local.z * scale,
        )))

    # Manual "Merge by Distance" equivalent: make the right/merge endpoint
    # literally identical in the point arrays.
    fitted[-1] = f_merge.copy()

    axis_x_residual_before_snap = fitted[0].x - f_axis.x
    axis_y_separation = fitted[0].y - f_axis.y

    # The scale was chosen specifically to match this X. Remove only tiny
    # floating-point residue. DO NOT merge the axis endpoints in Y.
    fitted[0].x = f_axis.x

    merge_error = (fitted[-1] - f_merge).length

    log(
        "Manual fit endpoints: "
        f"MERGE error={merge_error:.9g}; "
        f"AXIS X residual(before snap)={axis_x_residual_before_snap:.9g}; "
        f"AXIS Y separation={axis_y_separation:.9g}"
    )

    # Preserve the old return shape so the interactive caller remains simple.
    # 'angle' is always zero; 'residual' now means AXIS-X residual.
    return (
        front,
        fitted,
        scale,
        0.0,
        abs(axis_x_residual_before_snap),
    )


def calculate_revolve_axis_x(front_points):
    if REVOLVE_AXIS_MODE == "CUSTOM":
        return float(REVOLVE_AXIS_X)

    if REVOLVE_AXIS_MODE == "CENTER_X":
        return bounds_center(front_points).x

    if REVOLVE_AXIS_MODE in {"MIN_X", "MAX_X"}:
        oriented = normalize_chain_to_axis(front_points)
        return float(oriented[0].x)

    raise ValueError(
        "REVOLVE_AXIS_MODE must be MIN_X, MAX_X, CENTER_X, or CUSTOM."
    )


def scale_profiles_radially(front, back, axis_x, scale):
    if abs(scale - 1.0) <= 1e-12:
        return front, back

    def apply(points):
        return [Vector((
            axis_x + (p.x - axis_x) * scale,
            p.y,
            p.z,
        )) for p in points]

    return apply(front), apply(back)


def scale_profiles_axially(front, back, scale):
    if abs(scale - 1.0) <= 1e-12:
        return front, back, None

    y0 = bounds_center(front).y
    y1 = bounds_center(back).y
    center_y = 0.5 * (y0 + y1)

    def apply(points):
        return [Vector((
            p.x,
            center_y + (p.y - center_y) * scale,
            p.z,
        )) for p in points]

    return apply(front), apply(back), center_y


def measure_profile_size(front, back, axis_x):
    """Measure planned revolution diameter and axial thickness in scene units."""
    all_points = list(front) + list(back)

    if not all_points:
        raise RuntimeError("Cannot measure an empty profile.")

    max_radius = max(
        abs(float(p.x - axis_x))
        for p in all_points
    )

    diameter = 2.0 * max_radius

    ys = [
        float(p.y)
        for p in all_points
    ]

    thickness = max(ys) - min(ys)

    return diameter, thickness


def exact_size_scales(
    front,
    back,
    axis_x,
    target_diameter_mm,
    target_thickness_mm,
):
    """Return radial/axial scales needed to hit requested physical dimensions.

    A target value <= 0 means "do not force this dimension"; the corresponding
    legacy BUTTON_*_SCALE value is used instead.
    """
    current_diameter, current_thickness = measure_profile_size(
        front,
        back,
        axis_x,
    )

    if current_diameter <= 1e-12:
        raise RuntimeError(
            "Current profile diameter is effectively zero."
        )

    if current_thickness <= 1e-12:
        raise RuntimeError(
            "Current profile thickness is effectively zero."
        )

    target_diameter_scene = (
        float(target_diameter_mm)
        * SCENE_UNITS_PER_MM
    )

    target_thickness_scene = (
        float(target_thickness_mm)
        * SCENE_UNITS_PER_MM
    )

    if target_diameter_mm > 0.0:
        radial_scale = (
            target_diameter_scene
            / current_diameter
        )
    else:
        radial_scale = float(
            BUTTON_RADIAL_SCALE
        )

    if target_thickness_mm > 0.0:
        axial_scale = (
            target_thickness_scene
            / current_thickness
        )
    else:
        axial_scale = float(
            BUTTON_AXIAL_SCALE
        )

    if radial_scale <= 0.0:
        raise RuntimeError(
            f"Computed radial scale is invalid: {radial_scale}"
        )

    if axial_scale <= 0.0:
        raise RuntimeError(
            f"Computed axial scale is invalid: {axial_scale}"
        )

    return (
        radial_scale,
        axial_scale,
        current_diameter,
        current_thickness,
    )


def level_faca_endpoint_chord(points, label):
    """Rigid rotation: level the endpoint chord without deforming the cutter.

    We use the small-angle solution because the AXIS point can lie to the
    LEFT of the OUTER point. atan2(dy, dx) would flip the cutter by 180°.
    """
    points = normalize_chain_to_axis(points)
    axis_endpoint, outer_endpoint = points[0], points[-1]
    dx = axis_endpoint.x - outer_endpoint.x
    dy = axis_endpoint.y - outer_endpoint.y
    if abs(dx) <= 1e-10:
        raise RuntimeError(f"{label}: cannot level the DXF; endpoints have equal X.")
    angle = math.atan(-dy / dx)
    degrees = math.degrees(angle)
    if abs(degrees) > MAX_CHORD_LEVEL_ANGLE_DEG:
        raise RuntimeError(
            f"{label}: endpoint chord angle {degrees:.2f} deg exceeds "
            f"MAX_CHORD_LEVEL_ANGLE_DEG={MAX_CHORD_LEVEL_ANGLE_DEG}. "
            "Check profile orientation or disable LEVEL_FACA_ENDPOINT_CHORDS."
        )
    leveled = rotate_chain_xy(points, angle, outer_endpoint)
    log(f"{label}: chord-level rigid rotation={degrees:.5f} deg; "
        f"endpoint delta Y={leveled[0].y - leveled[-1].y:.9g}")
    return leveled


def uniformly_scale_faca_geometry(front, back, axis_x, factor):
    """Same XY multiplier on both profiles; never squeeze the relief along Y.

    Each curve is scaled about its own Y midpoint because its absolute DXF
    Y offset is irrelevant: the sheet model positions each surface afterward.
    Both share the same radial revolution axis in X.
    """
    if factor <= 0.0:
        raise RuntimeError(f"Invalid uniform profile scale: {factor}")

    def apply(points):
        y_center = 0.5 * (
            min(p.y for p in points) + max(p.y for p in points)
        )
        return [Vector((
            axis_x + (p.x - axis_x) * factor,
            y_center + (p.y - y_center) * factor,
            p.z * factor,
        )) for p in points]

    return apply(front), apply(back)


def place_facas_in_pastilha(front, back, final_thickness_mm):
    """Position unmodified cutter profiles within fixed final sheet thickness.

    We deliberately measure the full Y relief of EACH profile, including
    curves between the axis and the outer edge. After alignment:

        FRONT (highest surface)  - max(front_y) = +T/2
        BACK  (lowest surface)   - min(back_y)  = -T/2
        Minimum body clearance = T - front_height - back_height

    Thus the final total Y extent is exactly T, with no axial scaling. The
    connector at the OUTER edge is normally longer than this minimum gap
    when a profile's extrema occur away from the outer edge.
    """
    t = float(final_thickness_mm) * SCENE_UNITS_PER_MM
    f_y = [p.y for p in front]
    b_y = [p.y for p in back]
    h_front = max(f_y) - min(f_y)
    h_back = max(b_y) - min(b_y)
    core = t - h_front - h_back
    safe_gap = MIN_PASTILHA_CORE_MM * SCENE_UNITS_PER_MM

    log("Faca relief height: FRONT={:.6f} mm; BACK={:.6f} mm; "
        "requested={:.6f} mm; remaining BODY={:.6f} mm".format(
            h_front / SCENE_UNITS_PER_MM,
            h_back / SCENE_UNITS_PER_MM,
            t / SCENE_UNITS_PER_MM,
            core / SCENE_UNITS_PER_MM,
        ))

    if core < safe_gap - 1e-9:
        minimum = (h_front + h_back + safe_gap) / SCENE_UNITS_PER_MM
        raise RuntimeError(
            "The two faca profiles are too deep for the requested thickness.\n"
            f"FRONT relief={h_front / SCENE_UNITS_PER_MM:.4f} mm\n"
            f"BACK relief={h_back / SCENE_UNITS_PER_MM:.4f} mm\n"
            f"Requested thickness={final_thickness_mm:.4f} mm\n"
            f"Minimum safe thickness={minimum:.4f} mm\n\n"
            "No profile was squashed. Increase thickness, check the "
            "target diameter/DXF scale, or review the CAD profile."
        )

    front_shift = +0.5 * t - max(f_y)
    back_shift = -0.5 * t - min(b_y)
    shifted_front = [Vector((p.x, p.y + front_shift, p.z)) for p in front]
    shifted_back = [Vector((p.x, p.y + back_shift, p.z)) for p in back]

    outer_gap = shifted_front[-1].y - shifted_back[-1].y
    axis_gap = shifted_front[0].y - shifted_back[0].y
    if min(outer_gap, axis_gap) < safe_gap - 1e-8:
        raise RuntimeError(
            "One of the axis/outer closures crossed after placement. "
            "Check the DXF profiles."
        )
    total = max(p.y for p in shifted_front) - min(p.y for p in shifted_back)
    if abs(total - t) > 1e-7 * max(t, 1.0):
        raise RuntimeError("Internal error: fixed-thickness placement drifted.")

    log("Pastilha placement: minimum body={:.6f} mm, OUTER connector={:.6f} "
        "mm, AXIS connector={:.6f} mm".format(
            core / SCENE_UNITS_PER_MM,
            outer_gap / SCENE_UNITS_PER_MM,
            axis_gap / SCENE_UNITS_PER_MM,
        ))
    return shifted_front, shifted_back, {
        'front_faca_height_mm': h_front / SCENE_UNITS_PER_MM,
        'back_faca_height_mm': h_back / SCENE_UNITS_PER_MM,
        'body_gap_mm': core / SCENE_UNITS_PER_MM,
        'outer_connector_mm': outer_gap / SCENE_UNITS_PER_MM,
        'axis_connector_mm': axis_gap / SCENE_UNITS_PER_MM,
    }


def validate_pastilha_section(front, back, axis_x):
    """Reject 2D overlaps before the revolution rather than 'fix' the mesh."""
    sign = profile_radial_sign(front, back, axis_x)
    boundary = [Vector((sign * (p.x - axis_x), p.y, 0.0)) for p in front]
    boundary += [Vector((sign * (p.x - axis_x), p.y, 0.0))
                 for p in reversed(back)]
    validate_cross_section(boundary, 0.0)


def resample_open_chain(points, count):
    if len(points) < 2:
        raise RuntimeError("An open profile requires at least two vertices.")

    points = [Vector((p.x, p.y, p.z)) for p in points]
    cumulative = [0.0]
    for i in range(len(points) - 1):
        cumulative.append(cumulative[-1] + (points[i + 1] - points[i]).length)

    total = cumulative[-1]
    if total <= 1e-12:
        raise RuntimeError("Profile chain has zero length.")

    result = []
    seg = 0
    for i in range(count):
        target = total * i / (count - 1)
        while seg < len(points) - 2 and cumulative[seg + 1] < target:
            seg += 1
        a = points[seg]
        b = points[seg + 1]
        seg_len = (b - a).length
        t = 0.0 if seg_len <= 1e-12 else (target - cumulative[seg]) / seg_len
        result.append(a.lerp(b, max(0.0, min(1.0, t))))
    return result


def profile_radial_sign(front, back, axis_x):
    """Return +1 or -1 depending on which side of the Y axis the profiles occupy.

    +1: profile extends toward X > axis_x
    -1: profile extends toward X < axis_x

    A full revolution only needs positive radius magnitudes, but validating the
    side prevents an accidental profile crossing through the axis.
    """
    deltas = []

    for points in (front, back):
        for p in points:
            d = float(p.x - axis_x)
            if abs(d) > AXIS_SNAP_TOLERANCE:
                deltas.append(d)

    if not deltas:
        return 1.0

    positive = sum(1 for d in deltas if d > 0.0)
    negative = sum(1 for d in deltas if d < 0.0)

    if positive and negative:
        # Allow only tiny numerical contamination; a real mix means the
        # profile crosses the revolution axis.
        pos_mag = max((d for d in deltas if d > 0.0), default=0.0)
        neg_mag = max((-d for d in deltas if d < 0.0), default=0.0)

        if min(pos_mag, neg_mag) > AXIS_SNAP_TOLERANCE:
            raise RuntimeError(
                "The profiles lie on BOTH sides of the selected revolution "
                "axis. Choose the other endpoint or inspect the fit step."
            )

    return 1.0 if positive >= negative else -1.0


def snap_axis_endpoints(front, back, axis_x):
    """Snap ONLY the intended axis endpoint of each open DXF profile.

    AXIS_SNAP_TOLERANCE is an error bound for the CAD endpoint, NOT a radius
    within which surface vertices are flattened. Snapping a second nearby
    vertex onto the axis creates an overlapping center-axis edge and breaks
    the otherwise valid closed cross-section at smaller target diameters.
    """
    front = [p.copy() for p in front]
    back = [p.copy() for p in back]
    front = normalize_chain_to_axis(front)
    back = normalize_chain_to_axis(back)
    radial_sign = profile_radial_sign(front, back, axis_x)
    geometric_eps = max(1e-9, AXIS_TOPOLOGY_EPS_MM * SCENE_UNITS_PER_MM)

    for label, points in (("FRONT", front), ("BACK", back)):
        true_axis_error = abs(points[0].x - axis_x)
        if true_axis_error > AXIS_SNAP_TOLERANCE:
            raise RuntimeError(
                f"{label}: intended AXIS endpoint is {true_axis_error:.6g} "
                f"units from the axis (limit {AXIS_SNAP_TOLERANCE:.6g}). "
                "Check the axis selection and STEP 6 endpoint alignment."
            )
        if SNAP_AXIS_ENDPOINT:
            points[0].x = axis_x

        for i, p in enumerate(points[1:], start=1):
            signed_radius = radial_sign * (p.x - axis_x)
            if signed_radius < -geometric_eps:
                raise RuntimeError(
                    f"{label}: profile crosses the revolve axis at point {i} "
                    f"(signed radius={signed_radius:.9g})."
                )
            # Tiny negative drift due to floating point arithmetic may be
            # corrected, but positive radial vertices must NEVER be erased.
            if signed_radius < 0.0:
                p.x = axis_x

    log(
        "Axis snap: 2 true CAD endpoints aligned; all intermediate radial "
        "vertices preserved (no near-axis flattening)."
    )
    return front, back


# ============================================================================
# 2D CROSS-SECTION VALIDATION
# ============================================================================

def polygon_signed_area(points):
    area2 = 0.0
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        area2 += a.x * b.y - b.x * a.y
    return 0.5 * area2


def orient2d(a, b, c):
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def on_segment(a, b, p, eps=1e-8):
    return (
        min(a.x, b.x) - eps <= p.x <= max(a.x, b.x) + eps
        and min(a.y, b.y) - eps <= p.y <= max(a.y, b.y) + eps
        and abs(orient2d(a, b, p)) <= eps
    )


def segments_intersect_2d(a, b, c, d, eps=1e-8):
    o1 = orient2d(a, b, c)
    o2 = orient2d(a, b, d)
    o3 = orient2d(c, d, a)
    o4 = orient2d(c, d, b)

    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and \
       ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)):
        return True

    if abs(o1) <= eps and on_segment(a, b, c, eps):
        return True
    if abs(o2) <= eps and on_segment(a, b, d, eps):
        return True
    if abs(o3) <= eps and on_segment(c, d, a, eps):
        return True
    if abs(o4) <= eps and on_segment(c, d, b, eps):
        return True
    return False


def validate_cross_section(points, axis_x):
    if len(points) < 4:
        raise RuntimeError("The combined front/back cross-section has too few points.")

    # Remove exact/near-exact consecutive duplicates.
    cleaned = [points[0]]
    for p in points[1:]:
        if (p - cleaned[-1]).length > 1e-9:
            cleaned.append(p)
    points[:] = cleaned

    if len(points) < 4:
        raise RuntimeError("Cross-section collapsed after duplicate-point cleanup.")

    # A genuinely self-intersecting profile would produce a folded/spiky
    # revolution seen in the earlier versions. Catch it before making any 3D mesh.
    n = len(points)
    for i in range(n):
        a = points[i]
        b = points[(i + 1) % n]
        if (b - a).length <= 1e-9:
            continue
        for j in range(i + 1, n):
            # Adjacent segments share endpoints by design.
            if j == i or (j == i + 1) or (i == 0 and j == n - 1):
                continue
            c = points[j]
            d = points[(j + 1) % n]
            if segments_intersect_2d(a, b, c, d, eps=max(1e-7, WELD_TOLERANCE * 0.01)):
                raise RuntimeError(
                    "The combined front/back cross-section self-intersects.\n"
                    f"Segments {i} and {j} intersect.\n\n"
                    "Check the two profile curves for a real overlap. "
                    "A near-axis snap issue is also possible if a non-v28 "
                    "profile generator was used."
                )

    # No actual section point should live inside the axis by more than tolerance.
    for i, p in enumerate(points):
        r = p.x - axis_x
        if r < -AXIS_SNAP_TOLERANCE:
            raise RuntimeError(
                f"Cross-section point {i} is on the wrong side of the revolve axis "
                f"(radius={r:.6g})."
            )

    area = polygon_signed_area(points)
    if abs(area) <= 1e-9:
        raise RuntimeError("Combined front/back cross-section has near-zero area.")
    log(f"Cross-section validation: simple polygon, signed area={area:.6g}")


# ============================================================================
# CLEAN REVOLUTION MESH
# ============================================================================

def make_open_chain_object(name, points, z_offset, collection):
    """Create a Blender mesh containing one open polyline chain."""
    if len(points) < 2:
        raise RuntimeError(f"{name}: an open chain needs at least 2 points.")

    verts = [(p.x, p.y, z_offset) for p in points]
    edges = [(i, i + 1) for i in range(len(points) - 1)]

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, edges, [])
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def remove_duplicate_faces(obj):
    """Remove coincident faces that can be left by a closed 360-degree spin."""
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        seen = set()
        duplicates = []
        for face in bm.faces:
            key = tuple(sorted(v.index for v in face.verts))
            if key in seen:
                duplicates.append(face)
            else:
                seen.add(key)

        if duplicates:
            bmesh.ops.delete(bm, geom=duplicates, context='FACES')
            log(f"Removed {len(duplicates)} duplicate faces after Spin.")

        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()


def add_revolved_profile_strip(
    faces, rings_a, rings_b, steps, axis_eps,
    surface_code=None, face_surface_types=None,
):
    """Add the swept faces between two neighboring profile vertices.

    Each profile pair is revolved one angular step at a time. If one endpoint
    lies on the Y axis, the corresponding quad collapses to a triangle fan.
    If both endpoints lie on the axis, there is no surface area and the
    segment is intentionally skipped.
    """
    ra = rings_a
    rb = rings_b
    a_axis = len(set(ra)) == 1
    b_axis = len(set(rb)) == 1

    if a_axis and b_axis:
        return

    def add_face(face):
        faces.append(face)
        if face_surface_types is not None:
            face_surface_types.append(surface_code)

    for k in range(steps):
        nk = (k + 1) % steps
        if not a_axis and not b_axis:
            add_face((ra[k], rb[k], rb[nk], ra[nk]))
        elif a_axis and not b_axis:
            add_face((ra[k], rb[k], rb[nk]))
        elif not a_axis and b_axis:
            add_face((ra[k], rb[k], ra[nk]))


def ensure_mesh_attribute(mesh, name, data_type='FLOAT', domain='POINT'):
    """Create/reuse a named mesh attribute with a known type/domain."""
    attr = mesh.attributes.get(name)
    if attr is not None and (attr.data_type != data_type or attr.domain != domain):
        try:
            mesh.attributes.remove(attr)
        except Exception:
            attr = None
    if attr is None:
        attr = mesh.attributes.new(name=name, type=data_type, domain=domain)
    return attr


def write_face_surface_attribute(mesh, values):
    if len(values) != len(mesh.polygons):
        raise RuntimeError(
            f"Surface attribute length mismatch: values={len(values)}, "
            f"polygons={len(mesh.polygons)}"
        )
    attr = ensure_mesh_attribute(
        mesh,
        SURFACE_TYPE_ATTRIBUTE,
        data_type='INT',
        domain='FACE',
    )
    for poly in mesh.polygons:
        code = values[poly.index]
        attr.data[poly.index].value = SURFACE_FRONT if code is None else int(code)


def get_material(name, base_color=(0.5, 0.5, 0.5, 1.0), roughness=0.45):
    """Get/create a simple neutral material that the texture script can replace."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes if mat.node_tree else None
    if nodes is not None:
        bsdf = nodes.get('Principled BSDF')
        if bsdf is not None:
            try:
                bsdf.inputs['Base Color'].default_value = base_color
            except Exception:
                pass
            try:
                bsdf.inputs['Roughness'].default_value = roughness
            except Exception:
                pass
    return mat


def ensure_semantic_material_slots(obj):
    """Ensure stable semantic material slots exist on Button_3D."""
    if not TEXTURE_READY_OUTPUT:
        return {}

    specs = [
        (FRONT_MATERIAL_NAME, (0.5, 0.5, 0.5, 1.0)),
        (VERSO_MATERIAL_NAME, (0.5, 0.5, 0.5, 1.0)),
        (SIDE_MATERIAL_NAME, (0.5, 0.5, 0.5, 1.0)),
        (INTERIOR_MATERIAL_NAME, (0.45, 0.45, 0.45, 1.0)),
    ]
    materials = {name: get_material(name, color) for name, color in specs}

    existing = {mat.name: i for i, mat in enumerate(obj.data.materials) if mat}
    slots = {}
    for name, _ in specs:
        if name not in existing:
            obj.data.materials.append(materials[name])
            existing = {mat.name: i for i, mat in enumerate(obj.data.materials) if mat}
        slots[name] = existing[name]

    obj['dxf_material_front'] = slots[FRONT_MATERIAL_NAME]
    obj['dxf_material_verso'] = slots[VERSO_MATERIAL_NAME]
    obj['dxf_material_side'] = slots[SIDE_MATERIAL_NAME]
    obj['dxf_material_interior'] = slots[INTERIOR_MATERIAL_NAME]
    return slots


def assign_surface_material_indices(obj):
    """Map dxf_surface_type face codes to stable material slots."""
    if not TEXTURE_READY_OUTPUT:
        return
    slots = ensure_semantic_material_slots(obj)
    attr = obj.data.attributes.get(SURFACE_TYPE_ATTRIBUTE)
    if attr is None or attr.domain != 'FACE' or attr.data_type != 'INT':
        return
    mapping = {
        SURFACE_FRONT: slots[FRONT_MATERIAL_NAME],
        SURFACE_VERSO: slots[VERSO_MATERIAL_NAME],
        SURFACE_SIDE: slots[SIDE_MATERIAL_NAME],
        SURFACE_INTERIOR: slots[INTERIOR_MATERIAL_NAME],
    }
    for poly in obj.data.polygons:
        poly.material_index = mapping.get(attr.data[poly.index].value, slots[FRONT_MATERIAL_NAME])


def hole_center_points(axis_x):
    """Return the configured hole centers in the current pre-recenter coordinates."""
    if HOLE_COUNT <= 0:
        return []
    distance = HOLE_DISTANCE_MM * SCENE_UNITS_PER_MM
    offset = math.radians(HOLE_ANGLE_OFFSET_DEG)
    return [
        Vector((
            axis_x + distance * math.cos(offset + i * 2.0 * math.pi / HOLE_COUNT),
            0.0,
            distance * math.sin(offset + i * 2.0 * math.pi / HOLE_COUNT),
        ))
        for i in range(HOLE_COUNT)
    ]


def mark_hole_faces_as_interior(obj, axis_x):
    """Mark cylindrical hole-wall faces as INTERIOR for the future texture shader."""
    if not TEXTURE_READY_OUTPUT or not CREATE_HOLES or HOLE_COUNT <= 0:
        return 0

    mesh = obj.data
    mesh.update()
    attr = ensure_mesh_attribute(
        mesh,
        SURFACE_TYPE_ATTRIBUTE,
        data_type='INT',
        domain='FACE',
    )
    slots = ensure_semantic_material_slots(obj)
    interior_slot = slots[INTERIOR_MATERIAL_NAME]

    min_y = min((v.co.y for v in mesh.vertices), default=0.0)
    max_y = max((v.co.y for v in mesh.vertices), default=0.0)
    radius = HOLE_RADIUS_MM * SCENE_UNITS_PER_MM
    radial_tol = max(radius * 0.35, WELD_TOLERANCE * 2.0, 0.05)
    y_margin = max(WELD_TOLERANCE * 4.0, 1e-4)

    centers = hole_center_points(axis_x)
    marked = 0
    for poly in mesh.polygons:
        center = poly.center
        if center.y < min_y - y_margin or center.y > max_y + y_margin:
            continue
        # Hole walls run through Y, so their normals are primarily in X/Z.
        if abs(poly.normal.y) > 0.6:
            continue
        for hc in centers:
            dx = center.x - hc.x
            dz = center.z - hc.z
            radial = math.hypot(dx, dz)
            if abs(radial - radius) <= radial_tol:
                attr.data[poly.index].value = SURFACE_INTERIOR
                poly.material_index = interior_slot
                marked += 1
                break

    log(f"Texture semantic marking: {marked} face(s) tagged INTERIOR from hole cuts.")
    return marked


def recenter_output_geometry(obj):
    """Move mesh vertices so the object's local origin is its geometric center."""
    if not obj.data.vertices:
        return Vector((0.0, 0.0, 0.0))
    min_x, max_x, min_y, max_y, min_z, max_z = button_local_bounds(obj)
    center = Vector((
        0.5 * (min_x + max_x),
        0.5 * (min_y + max_y),
        0.5 * (min_z + max_z),
    ))
    if center.length <= 1e-12:
        return center
    for vert in obj.data.vertices:
        vert.co -= center
    obj.data.update()
    log(
        f"Output recentered to local origin: shifted mesh by "
        f"({center.x:.9g}, {center.y:.9g}, {center.z:.9g})."
    )
    return center


def finalize_texture_ready_data(obj, original_axis_x):
    """Write the stable texture contract without relying on POINT attributes.

    Blender can expose zero-sized custom POINT attribute collections after some
    mesh-building/Boolean combinations. v20 deliberately avoids that fragile
    path. The future texture script can derive normalized Y (and radial/angle
    coordinates) directly from Geometry > Position using the stored bounds.
    The semantic FACE attribute, material slots and UV map remain available.
    """
    if not TEXTURE_READY_OUTPUT:
        return

    mesh = obj.data
    mesh.update()
    ensure_semantic_material_slots(obj)

    min_x, max_x, min_y, max_y, min_z, max_z = button_local_bounds(obj)
    width = max(max_x - min_x, 1e-12)
    height = max(max_y - min_y, 1e-12)
    depth = max(max_z - min_z, 1e-12)
    radial_max = max(
        (math.hypot(v.co.x, v.co.z) for v in mesh.vertices),
        default=1.0,
    )
    radial_max = max(radial_max, 1e-12)

    # Reapply semantic face -> material mapping after Booleans/recentering.
    assign_surface_material_indices(obj)

    # Build one UV map. UV data lives on CORNER/loop elements and is much more
    # stable for this purpose than custom POINT attributes.
    uv = mesh.uv_layers.get(TEXTURE_UV_MAP_NAME)
    if uv is None:
        uv = mesh.uv_layers.new(name=TEXTURE_UV_MAP_NAME)

    surf_attr = mesh.attributes.get(SURFACE_TYPE_ATTRIBUTE)
    hole_centers = []
    if CREATE_HOLES and HOLE_COUNT > 0:
        distance = HOLE_DISTANCE_MM * SCENE_UNITS_PER_MM
        offset = math.radians(HOLE_ANGLE_OFFSET_DEG)
        hole_centers = [
            Vector((
                distance * math.cos(offset + i * 2.0 * math.pi / HOLE_COUNT),
                0.0,
                distance * math.sin(offset + i * 2.0 * math.pi / HOLE_COUNT),
            ))
            for i in range(HOLE_COUNT)
        ]

    for poly in mesh.polygons:
        code = SURFACE_FRONT
        if surf_attr is not None and surf_attr.domain == 'FACE' and surf_attr.data_type == 'INT':
            if poly.index < len(surf_attr.data):
                code = int(surf_attr.data[poly.index].value)

        for loop_index in poly.loop_indices:
            vi = mesh.loops[loop_index].vertex_index
            co = mesh.vertices[vi].co

            if code in (SURFACE_FRONT, SURFACE_VERSO):
                u = (co.x - min_x) / width
                v = (co.z - min_z) / depth
            elif code == SURFACE_SIDE:
                u = (math.atan2(co.z, co.x) + math.pi) / (2.0 * math.pi)
                v = (co.y - min_y) / height
            else:
                # Interior/cut fallback: unwrap around the nearest known hole.
                best = None
                best_d = float('inf')
                for hc in hole_centers:
                    d = math.hypot(co.x - hc.x, co.z - hc.z)
                    if d < best_d:
                        best_d = d
                        best = hc
                if best is None:
                    u = (math.atan2(co.z, co.x) + math.pi) / (2.0 * math.pi)
                else:
                    u = (math.atan2(co.z - best.z, co.x - best.x) + math.pi) / (2.0 * math.pi)
                v = (co.y - min_y) / height

            uv.data[loop_index].uv = (
                max(0.0, min(1.0, u)),
                max(0.0, min(1.0, v)),
            )

    # Stable object metadata for the separate texture script.
    # IMPORTANT: normalized layer Y is intentionally defined as a shader-side
    # operation from Geometry Position Y + these bounds, rather than as a custom
    # POINT attribute. This avoids the v19 Attribute.data[vertex.index]
    # IndexError while preserving the exact same concept.
    obj['dxf_texture_ready'] = True
    obj['dxf_builder_version'] = '26'
    obj['dxf_texture_uv_map'] = TEXTURE_UV_MAP_NAME
    obj['dxf_surface_type_attribute'] = SURFACE_TYPE_ATTRIBUTE
    obj['dxf_layer_y_attribute'] = ''
    obj['dxf_layer_y_source'] = 'LOCAL_POSITION_Y_NORMALIZED'
    obj['dxf_layer_axis'] = 'Y'
    obj['dxf_surface_codes'] = 'FRONT=0;VERSO=1;SIDE=2;INTERIOR=3'
    obj['dxf_original_revolve_axis_x'] = float(original_axis_x)
    obj['dxf_local_revolve_axis_x'] = 0.0
    obj['dxf_y_min'] = float(min_y)
    obj['dxf_y_max'] = float(max_y)
    obj['dxf_thickness'] = float(height)
    obj['dxf_diameter_x'] = float(width)
    obj['dxf_diameter_z'] = float(depth)
    obj['dxf_radial_radius'] = float(radial_max)
    obj['dxf_hole_count'] = int(HOLE_COUNT if CREATE_HOLES else 0)
    obj['dxf_hole_radius_mm'] = float(HOLE_RADIUS_MM)
    obj['dxf_hole_distance_mm'] = float(HOLE_DISTANCE_MM)
    obj['dxf_hole_angle_offset_deg'] = float(HOLE_ANGLE_OFFSET_DEG)
    obj['dxf_texture_mapping'] = (
        'FRONT/VERSO=XZ planar; SIDE=angle(Y-axis circumference)+Y; '
        'INTERIOR=Geometry Position Y layer lookup'
    )

    if CREATE_HOLES and HOLE_COUNT > 0:
        flat_centers = []
        distance = HOLE_DISTANCE_MM * SCENE_UNITS_PER_MM
        offset = math.radians(HOLE_ANGLE_OFFSET_DEG)
        for i in range(HOLE_COUNT):
            theta = offset + i * 2.0 * math.pi / HOLE_COUNT
            flat_centers.extend([
                float(distance * math.cos(theta)),
                float(distance * math.sin(theta)),
            ])
        obj['dxf_hole_centers_xz'] = flat_centers
    else:
        obj['dxf_hole_centers_xz'] = []

    mesh.update()

    # Explicitly report the texture contract so the next script can be built
    # against a known, stable interface.
    log(
        f"Texture-ready data: UV map='{TEXTURE_UV_MAP_NAME}', "
        f"surface attr='{SURFACE_TYPE_ATTRIBUTE}', "
        f"layer-Y source='LOCAL_POSITION_Y_NORMALIZED'."
    )
    log(
        f"Texture-ready bounds: X={min_x:.6g}..{max_x:.6g}, "
        f"Y={min_y:.6g}..{max_y:.6g}, Z={min_z:.6g}..{max_z:.6g}."
    )


def build_surface_of_revolution(front_points, back_points, axis_x, steps):
    """Build a clean closed surface directly from the two open faca chains.

    This is the key geometry change in v17.

    The earlier versions revolved the *bridged faces* with Mesh Spin. Spin is
    an extrusion-style operation: when faces are selected, the source faces
    remain and the swept copies are added. That can leave the original bridge
    sheet embedded inside the revolved surface, which is a likely cause of the
    huge non-manifold count seen in v17. Blender documents Spin as creating
    copies along the sweep, with Auto Merge available for a full revolution.

    Instead, v14 revolves the *boundary curves of the bridge* directly:
        FRONT chain + BACK chain + outer connecting edge.

    This is topologically the same intended surface, but it never creates the
    internal starting face sheet and it explicitly collapses axis vertices.
    """
    if len(front_points) != len(back_points):
        raise RuntimeError("Front and back profiles must have equal point counts.")
    if len(front_points) < 2:
        raise RuntimeError("Profiles need at least two points each.")
    if steps < 3:
        raise RuntimeError("SPIN_STEPS must be at least 3.")

    # The faca profiles should be planar XY curves. A non-zero Z here is only
    # supported for tiny numerical noise; a deliberate FACA_SEPARATION_Z is
    # still discouraged because it changes the radial geometry.
    max_abs_z = max(
        max(abs(p.z) for p in front_points),
        max(abs(p.z) for p in back_points),
    )
    if max_abs_z > max(WELD_TOLERANCE, 1e-5):
        raise RuntimeError(
            "Profile chains contain a significant Z offset. Keep "
            "FACA_SEPARATION_Z at 0 for the Y-axis revolve workflow."
        )

    # STEP 8 already performed equal-length resampling and explicit endpoint
    # snapping. A second resample here subtly changes the cut profile again.
    # Build the actual mesh from the coordinates that were validated/pre-viewed.
    front = [p.copy() for p in front_points]
    back = [p.copy() for p in back_points]

    # Only genuinely zero-radius points are collapsed to centerline vertices.
    # The much larger CAD FIT tolerance must NOT be used for topology.
    axis_eps = max(1e-9, AXIS_TOPOLOGY_EPS_MM * SCENE_UNITS_PER_MM)

    radial_sign = profile_radial_sign(
        front,
        back,
        axis_x,
    )

    log(
        "Revolve radial side: "
        + ("+X from axis" if radial_sign > 0 else "-X from axis")
    )

    def radial(p):
        r = radial_sign * (p.x - axis_x)

        if r < -axis_eps:
            raise RuntimeError(
                f"Profile crosses the revolution axis at x={p.x:.9g}; "
                f"axis={axis_x:.9g}; radial_sign={radial_sign:+.0f}."
            )

        return max(0.0, r)

    front_r = [radial(p) for p in front]
    back_r = [radial(p) for p in back]

    # The axis endpoint is explicitly snapped. This is what prevents the
    # accidental little hole at the center.
    for points, radii in ((front, front_r), (back, back_r)):
        if radii[0] <= axis_eps:
            points[0].x = axis_x
            points[0].z = 0.0
            radii[0] = 0.0
        else:
            raise RuntimeError(
                "The first/axis endpoints of the facas are not on the selected "
                f"revolve axis. FRONT radius={front_r[0]:.6g}, BACK radius={back_r[0]:.6g}."
            )

    def make_ring(p, r):
        if r <= axis_eps:
            return None
        ring = []
        for k in range(steps):
            theta = 2.0 * math.pi * k / steps
            ring.append(len(verts))
            verts.append((
                axis_x + r * math.cos(theta),
                p.y,
                r * math.sin(theta),
            ))
        return ring

    verts = []
    front_rings = []
    back_rings = []

    # Axis endpoints are represented by one actual vertex each, shared across
    # every angular sector. Non-axis points receive a full circular ring.
    for p, r in zip(front, front_r):
        if r <= axis_eps:
            idx = len(verts)
            verts.append((axis_x, p.y, 0.0))
            front_rings.append([idx] * steps)
        else:
            front_rings.append(make_ring(p, r))

    for p, r in zip(back, back_r):
        if r <= axis_eps:
            idx = len(verts)
            verts.append((axis_x, p.y, 0.0))
            back_rings.append([idx] * steps)
        else:
            back_rings.append(make_ring(p, r))

    faces = []
    face_surface_types = []

    # Sweep the FRONT boundary curve.
    for i in range(len(front) - 1):
        add_revolved_profile_strip(
            faces,
            front_rings[i],
            front_rings[i + 1],
            steps,
            axis_eps,
            SURFACE_FRONT,
            face_surface_types,
        )

    # Sweep the BACK boundary curve. Face orientation is corrected globally.
    for i in range(len(back) - 1):
        add_revolved_profile_strip(
            faces,
            back_rings[i],
            back_rings[i + 1],
            steps,
            axis_eps,
            SURFACE_VERSO,
            face_surface_types,
        )

    # OUTER endpoints are separated in pastilha mode to form the sidewall.
    # The legacy mode may still merge them to one common ring.
    outer_close_error = (front[-1] - back[-1]).length
    if outer_close_error <= max(WELD_TOLERANCE, 1e-5):
        # Re-use the FRONT outer ring as the BACK outer ring, but only when the
        # physical endpoints really coincide. This closes the shell without
        # creating duplicate coincident surfaces.
        back_rings[-1] = front_rings[-1]
        log(f"Outer endpoints coincide; shared outer ring used (error={outer_close_error:.6g}).")
    else:
        add_revolved_profile_strip(
            faces,
            front_rings[-1],
            back_rings[-1],
            steps,
            axis_eps,
            SURFACE_SIDE,
            face_surface_types,
        )

    # LEFT connecting edge joins the two separated axis endpoints.
    # It lies exactly on the Y revolution axis. When revolved, that edge
    # collapses onto the axis itself, so it creates no surface faces. This is
    # the direct-revolution equivalent of explicitly connecting those two
    # vertices before using Blender Spin.
    inner_error = (front[0] - back[0]).copy()
    log(
        f"Revolve section: inner endpoint delta=(dx={inner_error.x:.6g}, "
        f"dy={inner_error.y:.6g}); outer endpoint delta={outer_close_error:.6g}"
    )

    mesh = bpy.data.meshes.new(f"{OUTPUT_OBJECT_NAME}_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.validate(verbose=False)

    if len(face_surface_types) != len(mesh.polygons):
        raise RuntimeError(
            f"Revolution semantic face count mismatch: labels={len(face_surface_types)}, "
            f"polygons={len(mesh.polygons)}"
        )
    write_face_surface_attribute(mesh, face_surface_types)

    obj = bpy.data.objects.new(OUTPUT_OBJECT_NAME, mesh)
    get_or_create_collection(GENERATED_COLLECTION_NAME).objects.link(obj)

    # Clean up exact duplicate vertices only if they are genuinely coincident.
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(
            bm,
            verts=list(bm.verts),
            dist=min(float(WELD_TOLERANCE), 1e-5),
        )
        bmesh.ops.dissolve_degenerate(
            bm,
            edges=list(bm.edges),
            dist=min(float(WELD_TOLERANCE) * 0.1, 1e-6),
        )
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        mesh.update()
    finally:
        bm.free()

    return obj


def build_bridge_and_revolve(front_points, back_points, axis_x, steps):
    """Create a bridge preview, then build the final revolution from its edges.

    We still execute Bridge Edge Loops so the intermediate geometry matches the
    user's manual workflow. For the final object, however, v14 revolves the
    two boundary chains instead of revolving the filled bridge faces. This
    avoids embedding the original bridge sheet inside the finished button.
    """
    generated = get_or_create_collection(GENERATED_COLLECTION_NAME)

    # Keep an optional visual bridge preview exactly like the manual operation.
    if KEEP_BRIDGE_PREVIEW:
        front_obj = make_open_chain_object(
            "Front_Faca_Loop",
            front_points,
            +FACA_SEPARATION_Z * 0.5,
            generated,
        )
        back_obj = make_open_chain_object(
            "Back_Faca_Loop",
            back_points,
            -FACA_SEPARATION_Z * 0.5,
            generated,
        )

        safe_select_active(front_obj)
        back_obj.select_set(True)
        bpy.context.view_layer.objects.active = front_obj
        bpy.ops.object.join()
        combined = bpy.context.view_layer.objects.active

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        try:
            bpy.ops.mesh.bridge_edge_loops(
                type='SINGLE',
                use_merge=False,
                merge_factor=0.5,
                twist_offset=0,
                number_cuts=0,
            )
        except Exception as exc:
            bpy.ops.object.mode_set(mode='OBJECT')
            raise RuntimeError(f"Bridge Edge Loops preview failed: {exc}") from exc
        bpy.ops.object.mode_set(mode='OBJECT')
        combined.name = BRIDGE_PREVIEW_NAME
        log("Bridge Edge Loops preview: SUCCESS")

    # Final object is generated directly from the two matched boundary chains.
    button = build_surface_of_revolution(front_points, back_points, axis_x, steps)
    log("Direct boundary revolution: SUCCESS")

    topo = mesh_topology(button)
    log(f"Direct revolution topology: {topo}")

    if topo["boundary_edges"] != 0 or topo["nonmanifold_edges"] != 0:
        raise RuntimeError(
            "Direct boundary revolution produced invalid topology.\n"
            f"boundary_edges={topo['boundary_edges']}\n"
            f"nonmanifold_edges={topo['nonmanifold_edges']}\n\n"
            "The two profile boundaries or their axis endpoints need correction."
        )

    if SHADE_SMOOTH:
        safe_select_active(button)
        try:
            bpy.ops.object.shade_smooth()
        except Exception as exc:
            log(f"Shade smooth skipped: {exc}")

    return button

def mesh_topology(obj):
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        return {
            "verts": len(bm.verts),
            "edges": len(bm.edges),
            "faces": len(bm.faces),
            "boundary_edges": sum(1 for e in bm.edges if e.is_boundary),
            "nonmanifold_edges": sum(1 for e in bm.edges if not e.is_manifold),
            "wire_edges": sum(1 for e in bm.edges if e.is_wire),
        }
    finally:
        bm.free()


# ============================================================================
# HOLES
# ============================================================================

def button_local_bounds(obj):
    if not obj.data.vertices:
        raise RuntimeError("Button has no vertices.")
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def ensure_outward_normals(obj):
    """Make the closed button mesh consistently outward-facing before Booleans."""
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        if not bm.faces:
            return
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        try:
            signed_volume = bm.calc_volume(signed=True)
        except TypeError:
            signed_volume = bm.calc_volume()
        if signed_volume < 0.0:
            bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
            log(f"Button normals were inward; reversed all faces (signed volume={signed_volume:.6g}).")
        else:
            log(f"Button normals already outward (signed volume={signed_volume:.6g}).")
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()


def remove_disconnected_face_islands(obj):
    """Keep only the largest connected face island in the button mesh.

    The intended button is one connected solid.  If a Boolean leaves behind
    a detached cylindrical shell/plug, it becomes a small separate face
    component.  Remove those detached components while preserving the main
    button body.
    """
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        faces = set(bm.faces)
        components = []
        while faces:
            seed = next(iter(faces))
            stack = [seed]
            comp = set()
            while stack:
                face = stack.pop()
                if face not in faces:
                    continue
                faces.remove(face)
                comp.add(face)
                for edge in face.edges:
                    for linked in edge.link_faces:
                        if linked in faces:
                            stack.append(linked)
            components.append(comp)

        if len(components) <= 1:
            log("Connected-component check: 1 face island (OK).")
            return 1

        components.sort(key=len, reverse=True)
        keep = components[0]
        doomed = [f for comp in components[1:] for f in comp]
        sizes = [len(c) for c in components]
        log(f"Connected-component check: {len(components)} face islands, sizes={sizes}. Keeping largest={len(keep)}.")
        if doomed:
            bmesh.ops.delete(bm, geom=doomed, context='FACES')
            # Remove loose geometry left by deleted islands.
            loose = [v for v in bm.verts if not v.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
            loose_edges = [e for e in bm.edges if not e.link_faces]
            if loose_edges:
                bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
            bm.to_mesh(obj.data)
            obj.data.update()
            log(f"Removed {len(doomed)} detached faces from Boolean leftovers.")
        return len(components)
    finally:
        bm.free()



def cutter_bounds(obj):
    if not obj.data.vertices:
        raise RuntimeError("Cutter has no vertices.")
    ys = [v.co.y for v in obj.data.vertices]
    return min(ys), max(ys)


def prepare_boolean_mesh(obj, label):
    """Apply object transforms and recalculate normals without guessing volume sign."""
    safe_select_active(obj)
    try:
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    except Exception as exc:
        log(f"{label}: transform apply skipped: {exc}")

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        if bm.faces:
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()


def create_combined_hole_cutters(button_obj, axis_x):
    """Create all four Y-axis cutters and join them into ONE operand mesh."""
    if not CREATE_HOLES or HOLE_COUNT <= 0:
        return None

    _, _, min_y, max_y, _, _ = button_local_bounds(button_obj)
    y_center = 0.5 * (min_y + max_y)
    thickness = max_y - min_y
    margin = HOLE_CUTTER_MARGIN_MM * SCENE_UNITS_PER_MM
    depth = thickness + 2.0 * margin

    radius = HOLE_RADIUS_MM * SCENE_UNITS_PER_MM
    distance = HOLE_DISTANCE_MM * SCENE_UNITS_PER_MM
    if radius <= 0.0:
        raise RuntimeError("HOLE_RADIUS_MM must be greater than zero.")
    if distance <= radius:
        raise RuntimeError("HOLE_DISTANCE_MM must be larger than HOLE_RADIUS_MM.")

    temp_collection = get_or_create_collection(TEMP_COLLECTION_NAME)
    cutters = []
    offset = math.radians(HOLE_ANGLE_OFFSET_DEG)

    for i in range(HOLE_COUNT):
        theta = offset + i * 2.0 * math.pi / HOLE_COUNT
        x = axis_x + distance * math.cos(theta)
        z = distance * math.sin(theta)

        bpy.ops.mesh.primitive_cylinder_add(
            vertices=HOLE_SEGMENTS,
            radius=radius,
            depth=depth,
            end_fill_type='NGON',
            align='WORLD',
            enter_editmode=False,
            location=(x, y_center, z),
            rotation=(math.radians(90.0), 0.0, 0.0),
        )
        cutter = bpy.context.view_layer.objects.active
        cutter.name = f"__DXF_HOLE_CUTTER_{i + 1:02d}__"
        cutter["dxf_button_hole_cutter"] = True
        cutter["dxf_button_hole_index"] = i + 1
        move_to_collection(cutter, temp_collection)
        prepare_boolean_mesh(cutter, f"Hole cutter {i + 1}/{HOLE_COUNT}")
        cutters.append(cutter)

    safe_select_active(cutters[0])
    for cutter in cutters[1:]:
        cutter.select_set(True)
    bpy.context.view_layer.objects.active = cutters[0]
    if len(cutters) > 1:
        bpy.ops.object.join()

    result = bpy.context.view_layer.objects.active
    result.name = "__DXF_COMBINED_HOLE_CUTTER__"
    result["dxf_button_hole_cutter"] = True
    result["dxf_button_hole_count"] = HOLE_COUNT

    # Give the cutter a dedicated interior material so a Boolean transfer can
    # carry that semantic onto newly generated cut faces. We still explicitly
    # mark the final hole faces afterward, so the texture pipeline does not
    # depend on Blender's material-transfer implementation alone.
    if TEXTURE_READY_OUTPUT:
        interior_mat = get_material(INTERIOR_MATERIAL_NAME, (0.45, 0.45, 0.45, 1.0))
        result.data.materials.clear()
        result.data.materials.append(interior_mat)
        for poly in result.data.polygons:
            poly.material_index = 0

    min_cy, max_cy = cutter_bounds(result)
    log(
        f"Combined hole cutter: count={HOLE_COUNT}, radius={radius:.6g}, "
        f"distance={distance:.6g}, Y bounds={min_cy:.6g} .. {max_cy:.6g}, depth={depth:.6g}"
    )
    return result


def delete_cutter(cutter):
    """Delete a cutter object and its unused mesh datablock."""
    if cutter is None:
        return
    try:
        mesh_data = cutter.data if hasattr(cutter, 'data') else None
        name = cutter.name
        bpy.data.objects.remove(cutter, do_unlink=True)
        if mesh_data is not None and getattr(mesh_data, 'users', 0) == 0:
            try:
                bpy.data.meshes.remove(mesh_data)
            except Exception:
                pass
        log(f"Deleted hole cutter: {name}")
    except Exception as exc:
        log(f"Hole cutter delete warning: {exc}")


def purge_hole_cutter_objects():
    """Aggressively remove current and legacy hole-cutter objects."""
    legacy_prefixes = (
        "hole_cutter",
        "button_hole_cutters",
        "__dxf_hole_cutter_",
        "__dxf_combined_hole_cutter__",
    )

    doomed = []
    for obj in list(bpy.data.objects):
        name = obj.name.lower()
        tagged = bool(obj.get("dxf_button_hole_cutter", False))
        legacy = name.startswith(legacy_prefixes)
        if tagged or legacy:
            doomed.append(obj)

    for obj in doomed:
        delete_cutter(obj)

    leftovers = []
    for obj in list(bpy.data.objects):
        name = obj.name.lower()
        tagged = bool(obj.get("dxf_button_hole_cutter", False))
        legacy = name.startswith(legacy_prefixes)
        if tagged or legacy:
            leftovers.append(obj.name)

    if leftovers:
        log(f"WARNING: tagged/legacy cutter objects still remain: {leftovers}")
    else:
        log("Cutter cleanup verification: ZERO tagged/legacy cutter objects remain.")


def purge_stale_blender_cylinders():
    """Remove default Cylinder* leftovers from older builder runs."""
    doomed = []
    for obj in list(bpy.data.objects):
        if obj.type != 'MESH':
            continue
        name = obj.name.lower()
        if name == "cylinder" or name.startswith("cylinder."):
            doomed.append(obj)

    for obj in doomed:
        log(f"Removing stale default cylinder object: {obj.name}")
        delete_cutter(obj)

    remaining = [
        obj.name for obj in bpy.data.objects
        if obj.type == 'MESH' and (obj.name.lower() == "cylinder" or obj.name.lower().startswith("cylinder."))
    ]
    if remaining:
        log(f"WARNING: stale default cylinders remain: {remaining}")
    else:
        log("Stale default-cylinder cleanup: ZERO Cylinder* mesh objects remain.")


def duplicate_mesh_state(obj, name):
    """Create a hidden temporary mesh-only backup of an object for Boolean fallback."""
    backup_mesh = obj.data.copy()
    backup = bpy.data.objects.new(name, backup_mesh)
    get_or_create_collection(TEMP_COLLECTION_NAME).objects.link(backup)
    backup.hide_viewport = True
    backup.hide_render = True
    try:
        backup.hide_set(True)
    except Exception:
        pass
    backup.matrix_world = obj.matrix_world.copy()
    return backup


def restore_mesh_state(obj, backup):
    """Restore only the mesh datablock from a backup object."""
    old_mesh = obj.data
    obj.data = backup.data.copy()
    if old_mesh.users == 0:
        try:
            bpy.data.meshes.remove(old_mesh)
        except Exception:
            pass


def delete_backup(backup):
    if backup is None:
        return
    try:
        mesh_data = backup.data
        bpy.data.objects.remove(backup, do_unlink=True)
        if mesh_data is not None and mesh_data.users == 0:
            try:
                bpy.data.meshes.remove(mesh_data)
            except Exception:
                pass
    except Exception:
        pass


def boolean_difference(button, cutter, solver):
    """Apply a single Boolean Difference and return its topology."""
    safe_select_active(button)
    modifier = button.modifiers.new(name="Button_Holes", type='BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.object = cutter
    modifier.solver = solver

    # Exact solver options. Hole-tolerant is intentionally OFF for the primary
    # path because the input button/cutter are both manifold. It is enabled only
    # in the fallback path when needed.
    try:
        modifier.use_hole_tolerant = False
    except Exception:
        pass
    try:
        modifier.use_self = False
    except Exception:
        pass
    if TEXTURE_READY_OUTPUT:
        try:
            modifier.material_mode = 'TRANSFER'
            log("Boolean material mode: TRANSFER (interior cut semantics enabled).")
        except Exception:
            pass

    bpy.ops.object.modifier_apply(modifier=modifier.name)
    return mesh_topology(button)


def apply_holes(button, axis_x):
    """
    Cut all four holes with ONE Boolean Difference operation.

    This returns to the geometry path that was already observed in v14.1 to
    produce zero boundary/non-manifold edges. v17's one-hole-at-a-time approach
    accumulated Boolean topology damage after hole 2; doing the four disjoint
    cylinders as one operand avoids those intermediate states.
    """
    if not CREATE_HOLES or HOLE_COUNT <= 0:
        log("Holes disabled.")
        return button

    before = mesh_topology(button)
    log(f"Before holes topology: {before}")
    if before["boundary_edges"] != 0 or before["nonmanifold_edges"] != 0:
        raise RuntimeError(
            "The generated button is not manifold before hole cutting.\n"
            f"boundary_edges={before['boundary_edges']}\n"
            f"nonmanifold_edges={before['nonmanifold_edges']}"
        )

    # IMPORTANT: do not flip the button based on calc_volume sign here. The
    # proven v14.1 Boolean path did not do that, and signed-volume sign alone is
    # not a reliable way to infer Blender's preferred face winding convention.
    prepare_boolean_mesh(button, "Button")

    backup = duplicate_mesh_state(button, "__DXF_BUTTON_HOLE_BACKUP__")
    cutter = None
    chosen = None
    try:
        cutter = create_combined_hole_cutters(button, axis_x)
        if cutter is None:
            return button

        # Hide only after the modifier has its operand. The cutter must remain a
        # normal mesh object during evaluation; hiding is strictly presentation.
        cutter.hide_viewport = True
        cutter.hide_render = True
        try:
            cutter.hide_set(True)
        except Exception:
            pass

        # Primary: Exact, matching v14.1 and Blender's recommended behavior for
        # manifold boolean participants.
        for solver_name in ("EXACT", "MANIFOLD"):
            if solver_name == "MANIFOLD":
                # Older Blender versions may not expose the Manifold solver.
                try:
                    test_mod = button.modifiers.new(name="__DXF_SOLVER_TEST__", type='BOOLEAN')
                    test_mod.solver = 'MANIFOLD'
                    button.modifiers.remove(test_mod)
                except Exception:
                    log("MANIFOLD solver not available in this Blender; skipping fallback solver.")
                    continue

            restore_mesh_state(button, backup)
            topo = boolean_difference(button, cutter, solver_name)
            log(f"Combined Boolean ({solver_name}) topology: {topo}")

            _, _, min_y_before, max_y_before, _, _ = button_local_bounds(backup)
            _, _, min_y_after, max_y_after, _, _ = button_local_bounds(button)
            y_before = max_y_before - min_y_before
            y_after = max_y_after - min_y_after
            log(f"Combined Boolean ({solver_name}) Y thickness check: before={y_before:.6g}, after={y_after:.6g}")

            manifold_ok = topo["boundary_edges"] == 0 and topo["nonmanifold_edges"] == 0
            thickness_ok = abs(y_after - y_before) <= max(1e-5, WELD_TOLERANCE * 4.0)
            if manifold_ok and thickness_ok:
                chosen = solver_name
                break

            log(
                f"Combined Boolean ({solver_name}) rejected: "
                f"manifold_ok={manifold_ok}, thickness_ok={thickness_ok}. Restoring backup."
            )

            # Remove any partial modifier state before the next attempt.
            for mod in list(button.modifiers):
                if mod.type == 'BOOLEAN' and mod.name.startswith("Button_Holes"):
                    try:
                        button.modifiers.remove(mod)
                    except Exception:
                        pass

            # Recreate one fresh cutter if Blender consumed/changed the operand.
            if cutter is None or cutter.name not in bpy.data.objects:
                cutter = create_combined_hole_cutters(button, axis_x)
                cutter.hide_viewport = True
                cutter.hide_render = True
                try:
                    cutter.hide_set(True)
                except Exception:
                    pass

        if chosen is None:
            # Last Exact fallback with hole-tolerant enabled, still as ONE Boolean.
            restore_mesh_state(button, backup)
            if cutter is None or cutter.name not in bpy.data.objects:
                cutter = create_combined_hole_cutters(button, axis_x)
            safe_select_active(button)
            modifier = button.modifiers.new(name="Button_Holes", type='BOOLEAN')
            modifier.operation = 'DIFFERENCE'
            modifier.object = cutter
            modifier.solver = 'EXACT'
            try:
                modifier.use_hole_tolerant = True
            except Exception:
                pass
            try:
                modifier.use_self = False
            except Exception:
                pass
            if TEXTURE_READY_OUTPUT:
                try:
                    modifier.material_mode = 'TRANSFER'
                except Exception:
                    pass
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            topo = mesh_topology(button)
            log(f"Combined Boolean (EXACT + hole-tolerant) topology: {topo}")
            chosen = "EXACT+HOLE_TOLERANT"

        log(f"Hole cut path accepted: {chosen}")
        if TEXTURE_READY_OUTPUT:
            mark_hole_faces_as_interior(button, axis_x)
            assign_surface_material_indices(button)
        return button
    finally:
        delete_cutter(cutter)
        delete_backup(backup)
        purge_hole_cutter_objects()



# ============================================================================
# CLEANUP / VIEWPORT
# ============================================================================

def cleanup_imported_objects(front_obj, back_obj):
    if KEEP_IMPORTED_FACA_OBJECTS:
        source = get_or_create_collection(SOURCE_COLLECTION_NAME)
        for obj in (front_obj, back_obj):
            move_to_collection(obj, source)
            if HIDE_SOURCE_FACAS:
                obj.hide_viewport = True
                obj.hide_render = True
                try:
                    obj.hide_set(True)
                except Exception:
                    pass
        return

    for obj in (front_obj, back_obj):
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass


def frame_object(obj):
    try:
        safe_select_active(obj)
        for area in bpy.context.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for region in area.regions:
                if region.type != 'WINDOW':
                    continue
                override = {
                    'window': bpy.context.window,
                    'screen': bpy.context.screen,
                    'area': area,
                    'region': region,
                    'scene': bpy.context.scene,
                    'active_object': obj,
                }
                try:
                    bpy.ops.view3d.view_selected(override)
                    return
                except Exception:
                    pass
    except Exception as exc:
        log(f"Viewport framing skipped: {exc}")


# ============================================================================
# INTERACTIVE STEP-BY-STEP BUILD
# ============================================================================

def force_viewport_redraw():
    """Request an immediate UI redraw before returning to the event loop."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:
        pass


def _delete_step_preview(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        return

    data = getattr(obj, "data", None)

    try:
        bpy.data.objects.remove(obj, do_unlink=True)
    except Exception:
        return

    if data is not None:
        try:
            if data.users == 0:
                bpy.data.meshes.remove(data)
        except Exception:
            pass


def clear_step_previews():
    _delete_step_preview(STEP_FRONT_PREVIEW_NAME)
    _delete_step_preview(STEP_BACK_PREVIEW_NAME)
    _delete_step_preview(STEP_AXIS_PREVIEW_NAME)
    _delete_step_preview(STEP_AXIS_CLOSURE_PREVIEW_NAME)
    _delete_step_preview(STEP_OUTER_CLOSURE_PREVIEW_NAME)

    merge_obj = bpy.data.objects.get(STEP_MERGE_MARKER_NAME)
    if merge_obj is not None:
        try:
            bpy.data.objects.remove(merge_obj, do_unlink=True)
        except Exception:
            pass


def make_step_profile_preview(name, points, rgba):
    """Create a simple in-front polyline showing the exact profile data."""
    _delete_step_preview(name)

    if not points:
        return None

    mesh = bpy.data.meshes.new(name + "_Mesh")

    verts = [
        (float(p.x), float(p.y), float(p.z))
        for p in points
    ]
    edges = [
        (i, i + 1)
        for i in range(len(verts) - 1)
    ]

    mesh.from_pydata(verts, edges, [])
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    get_or_create_collection(TEMP_COLLECTION_NAME).objects.link(obj)

    obj.show_in_front = True
    obj.display_type = 'WIRE'
    obj.color = rgba
    obj["dxf_step_preview"] = True

    return obj


def update_step_axis_preview(axis_x, front, back):
    """Draw the selected Y revolution axis as a bright green line."""
    _delete_step_preview(STEP_AXIS_PREVIEW_NAME)

    ys = [p.y for p in front] + [p.y for p in back]

    if not ys:
        return None

    y0 = min(ys)
    y1 = max(ys)
    span = max(y1 - y0, 1.0)
    margin = max(span * 0.75, 1.0)

    points = [
        Vector((axis_x, y0 - margin, 0.0)),
        Vector((axis_x, y1 + margin, 0.0)),
    ]

    obj = make_step_profile_preview(
        STEP_AXIS_PREVIEW_NAME,
        points,
        (0.1, 1.0, 0.1, 1.0),
    )

    if obj is not None:
        obj["dxf_step_axis_preview"] = True

    force_viewport_redraw()
    return obj


def update_step_section_closure_preview(front, back):
    """Visualize the exact section closure expected before revolution.

    LEFT / AXIS:
        a yellow line joins FRONT[0] to BACK[0].
        These vertices stay separate but must share the same X.

    RIGHT / MERGE:
        a magenta sphere marks the one shared FRONT[-1]/BACK[-1] point.
        This is the manual Merge-by-Distance location.
    """
    _delete_step_preview(
        STEP_AXIS_CLOSURE_PREVIEW_NAME
    )
    _delete_step_preview(
        STEP_OUTER_CLOSURE_PREVIEW_NAME
    )

    old_marker = bpy.data.objects.get(
        STEP_MERGE_MARKER_NAME
    )

    if old_marker is not None:
        try:
            bpy.data.objects.remove(
                old_marker,
                do_unlink=True,
            )
        except Exception:
            pass

    if not front or not back:
        return

    # Axis closure line between the two LEFT endpoints.
    make_step_profile_preview(
        STEP_AXIS_CLOSURE_PREVIEW_NAME,
        [
            front[0].copy(),
            back[0].copy(),
        ],
        (1.0, 0.75, 0.05, 1.0),
    )

    # The outer endpoints become a visible SIDE wall after Step 7.
    # Before sizing they still coincide, so the preview has zero length.
    make_step_profile_preview(
        STEP_OUTER_CLOSURE_PREVIEW_NAME,
        [front[-1].copy(), back[-1].copy()],
        (0.15, 0.9, 0.45, 1.0),
    )

    # Magenta marker at the midpoint of the SIDE wall (old merge point).
    merge_point = (
        front[-1] + back[-1]
    ) * 0.5

    all_points = list(front) + list(back)
    xs = [p.x for p in all_points]
    ys = [p.y for p in all_points]

    display_size = max(
        (max(xs) - min(xs)) * 0.018,
        (max(ys) - min(ys)) * 0.018,
        0.08,
    )

    marker = bpy.data.objects.new(
        STEP_MERGE_MARKER_NAME,
        None,
    )

    get_or_create_collection(
        TEMP_COLLECTION_NAME
    ).objects.link(marker)

    marker.empty_display_type = 'SPHERE'
    marker.empty_display_size = display_size
    marker.location = merge_point
    marker.show_in_front = True
    marker.color = (
        1.0,
        0.0,
        1.0,
        1.0,
    )
    marker["dxf_step_merge_marker"] = True

    force_viewport_redraw()


def update_step_profile_previews(front, back, front_obj=None, back_obj=None):
    if not STEP_SHOW_PROFILE_PREVIEWS:
        return

    front_preview = make_step_profile_preview(
        STEP_FRONT_PREVIEW_NAME,
        front,
        (1.0, 0.18, 0.12, 1.0),
    )

    back_preview = make_step_profile_preview(
        STEP_BACK_PREVIEW_NAME,
        back,
        (0.10, 0.45, 1.0, 1.0),
    )

    if STEP_HIDE_RAW_DXF_AFTER_EXTRACT:
        for obj in (front_obj, back_obj):
            if obj is not None:
                try:
                    obj.hide_set(True)
                    obj.hide_viewport = True
                except Exception:
                    pass

    # Keep previews selected so they are visually obvious.
    try:
        bpy.ops.object.select_all(action='DESELECT')
        if front_preview is not None:
            front_preview.select_set(True)
            bpy.context.view_layer.objects.active = front_preview
        if back_preview is not None:
            back_preview.select_set(True)
    except Exception:
        pass

    force_viewport_redraw()


def step_prompt(number, total, text):
    return (
        f"STEP {number}/{total}: {text}  |  "
        "Press ENTER to run this action. ESC cancels."
    )


def build_button_steps(target_diameter_mm=0.0, target_thickness_mm=0.0):
    """
    Generator that pauses BEFORE every major operation.

    The modal operator calls next() only when Enter is pressed. Because control
    returns to Blender after every yield, the viewport redraws and the result
    of each completed action is visible before the next keypress.

    target_diameter_mm and target_thickness_mm are exact requested physical
    dimensions. A value of 0 preserves the DXF dimension on that axis.
    """
    total = 14

    front_geom = None
    back_geom = None
    front_obj = None
    back_obj = None
    front = None
    back = None
    axis_x = None
    button = None

    # ------------------------------------------------------------------
    yield step_prompt(
        1, total,
        "Clean old generated/temp objects and old Boolean cutters"
    )

    try:
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        pass

    clear_collection(GENERATED_COLLECTION_NAME)
    clear_collection(TEMP_COLLECTION_NAME)

    if CLEAR_SOURCE_COLLECTION_ON_START:
        clear_collection(SOURCE_COLLECTION_NAME)

    purge_hole_cutter_objects()
    purge_stale_blender_cylinders()
    clear_step_previews()

    log("STEP 1 complete: old generated/temp geometry cleaned.")
    force_viewport_redraw()

    # ------------------------------------------------------------------
    yield step_prompt(
        2, total,
        "Import FRONT and BACK DXF files"
    )

    front_geom = import_dxf_file(FRONT_DXF_PATH, "FRONT")
    back_geom = import_dxf_file(BACK_DXF_PATH, "BACK")

    log("STEP 2 complete: DXFs imported.")
    force_viewport_redraw()

    # ------------------------------------------------------------------
    yield step_prompt(
        3, total,
        "Convert imported DXFs to welded mesh objects"
    )

    temp = get_or_create_collection(TEMP_COLLECTION_NAME)

    front_obj = convert_join_weld(
        front_geom,
        "FRONT",
        temp,
    )

    back_obj = convert_join_weld(
        back_geom,
        "BACK",
        temp,
    )

    log("STEP 3 complete: imported geometry converted + welded.")
    force_viewport_redraw()

    # ------------------------------------------------------------------
    yield step_prompt(
        4, total,
        "Extract the real FRONT/BACK open profile chains"
    )

    front = extract_profile_chain(
        front_obj,
        "FRONT",
    )

    back = extract_profile_chain(
        back_obj,
        "BACK",
    )

    update_step_profile_previews(
        front,
        back,
        front_obj,
        back_obj,
    )

    log(
        "STEP 4 complete: algorithmic profile previews are now visible "
        "(FRONT red, BACK blue when object color display is enabled)."
    )

    # FRONT stays exactly as imported in v23.

    # ------------------------------------------------------------------
    yield step_prompt(
        5, total,
        "Rotate the BACK faca 180 degrees around X"
    )

    if BACK_ROTATE_180_X:
        back = rotate_180_x(back)
        log(
            "BACK: rotated 180° around X around its own geometric center."
        )
    else:
        log("BACK 180° X rotation is disabled.")

    update_step_profile_previews(
        front,
        back,
        front_obj,
        back_obj,
    )

    # ------------------------------------------------------------------
    yield step_prompt(
        6, total,
        "MERGE the RIGHT endpoints, then scale BACK so the LEFT endpoints share axis X"
    )

    if PASTILHA_THICKNESS_MODE and target_thickness_mm > 0.0 and LEVEL_FACA_ENDPOINT_CHORDS:
        front = level_faca_endpoint_chord(front, "FRONT")
        back = level_faca_endpoint_chord(back, "BACK")

    if FIT_BACK_TO_FRONT:
        front, back, fit_scale, fit_angle, residual = (
            fit_back_to_front_endpoints(
                front,
                back,
            )
        )

        log(
            f"BACK fit: uniform scale={fit_scale:.9g}, "
            f"XY rotation={fit_angle:.6g}°, "
            f"axis-X residual={residual:.6g}"
        )

        merge_error = (front[-1] - back[-1]).length
        axis_dx = back[0].x - front[0].x
        axis_dy = back[0].y - front[0].y

        log(
            "STEP 6 endpoint result: "
            f"RIGHT/MERGE distance={merge_error:.9g}; "
            f"LEFT/AXIS dx={axis_dx:.9g}; "
            f"LEFT/AXIS dy={axis_dy:.9g}"
        )

        if merge_error > min(
            WELD_TOLERANCE,
            1e-5,
        ):
            raise RuntimeError(
                "RIGHT/MERGE endpoints were not merged exactly after fitting."
            )

        if abs(axis_dx) > max(
            WELD_TOLERANCE,
            AXIS_SNAP_TOLERANCE,
        ):
            raise RuntimeError(
                "LEFT/AXIS endpoints do not share the same X after fitting."
            )
    else:
        front = normalize_chain_to_axis(front)
        back = normalize_chain_to_axis(back)
        back = translate_xy(
            back,
            front[0] - back[0],
        )

    update_step_profile_previews(
        front,
        back,
        front_obj,
        back_obj,
    )

    update_step_section_closure_preview(
        front,
        back,
    )

    log(
        "STEP 6 visual check (temporary alignment): MAGENTA = right common "
        "anchor, YELLOW = left axis connection. Step 7 inserts sheet thickness."
    )

    # ------------------------------------------------------------------
    yield step_prompt(
        7, total,
        "Set diameter uniformly; add uncut BODY gap to reach final Y thickness"
    )

    # Make the chosen endpoint explicit before selecting the axis.
    front = normalize_chain_to_axis(front)
    back = normalize_chain_to_axis(back)

    axis_x = calculate_revolve_axis_x(front)

    radial_sign = profile_radial_sign(
        front,
        back,
        axis_x,
    )

    log(
        f"Revolve axis: Y with X={axis_x:.9g} "
        f"({REVOLVE_AXIS_MODE}); profile extends "
        f"{'+X' if radial_sign > 0 else '-X'} from the axis."
    )

    update_step_axis_preview(
        axis_x,
        front,
        back,
    )

    if PASTILHA_THICKNESS_MODE and target_thickness_mm > 0.0:
        initial_diameter, initial_thickness = measure_profile_size(front, back, axis_x)
        if initial_diameter <= 1e-12:
            raise RuntimeError("No radial span in the DXF profiles.")
        uniform_scale = (
            target_diameter_mm * SCENE_UNITS_PER_MM / initial_diameter
            if target_diameter_mm > 0.0
            else float(BUTTON_RADIAL_SCALE)
        )
        log("PASTILHA THICKNESS MODE — uniform XY scaling, NO axial squeezing.")
        log(f"Pre-size: diameter={initial_diameter / SCENE_UNITS_PER_MM:.6g} mm; "
            f"combined source Y extent={initial_thickness / SCENE_UNITS_PER_MM:.6g} mm")
        log(f"Uniform geometric scale={uniform_scale:.9g}")
        front, back = uniformly_scale_faca_geometry(front, back, axis_x, uniform_scale)
        front, back, pastilha_stats = place_facas_in_pastilha(
            front, back, target_thickness_mm
        )
        final_dia, final_t = measure_profile_size(front, back, axis_x)
        log(f"Measured final planned section: diameter={final_dia / SCENE_UNITS_PER_MM:.6g} "
            f"mm, thickness={final_t / SCENE_UNITS_PER_MM:.6g} mm")
    else:
        log("Legacy size mode: target thickness 0 — use prior DXF axial settings.")
        (
            radial_scale,
            axial_scale,
            pre_size_diameter,
            pre_size_thickness,
        ) = exact_size_scales(
            front,
            back,
            axis_x,
            target_diameter_mm,
            target_thickness_mm,
        )

        log(
            "Pre-size profile: "
            f"diameter={pre_size_diameter / SCENE_UNITS_PER_MM:.6g} mm, "
            f"thickness={pre_size_thickness / SCENE_UNITS_PER_MM:.6g} mm"
        )

        if target_diameter_mm > 0.0:
            log(
                f"Target diameter={target_diameter_mm:.6g} mm -> "
                f"radial scale={radial_scale:.9g}"
            )
        else:
            log(
                "Target diameter=0 -> preserve DXF diameter using "
                f"BUTTON_RADIAL_SCALE={radial_scale:.6g}"
            )

        if target_thickness_mm > 0.0:
            log(
                f"Target thickness={target_thickness_mm:.6g} mm -> "
                f"axial scale={axial_scale:.9g}"
            )
        else:
            log(
                "Target thickness=0 -> preserve DXF thickness using "
                f"BUTTON_AXIAL_SCALE={axial_scale:.6g}"
            )

        front, back = scale_profiles_radially(
            front,
            back,
            axis_x,
            radial_scale,
        )

        front, back, axial_center_y = scale_profiles_axially(
            front,
            back,
            axial_scale,
        )

        post_size_diameter, post_size_thickness = measure_profile_size(
            front,
            back,
            axis_x,
        )

        log(
            "Post-size profile: "
            f"diameter={post_size_diameter / SCENE_UNITS_PER_MM:.6g} mm, "
            f"thickness={post_size_thickness / SCENE_UNITS_PER_MM:.6g} mm"
        )

        if axial_center_y is not None:
            log(
                f"Axial sizing center Y={axial_center_y:.9g}"
            )

    if abs(FACA_SEPARATION_Z) > 1e-12:
        log(
            "WARNING: FACA_SEPARATION_Z is non-zero. For the custom Y-axis "
            "revolution this is an actual radial offset, not button thickness."
        )

        front = [
            Vector((
                p.x,
                p.y,
                p.z + FACA_SEPARATION_Z * 0.5,
            ))
            for p in front
        ]

        back = [
            Vector((
                p.x,
                p.y,
                p.z - FACA_SEPARATION_Z * 0.5,
            ))
            for p in back
        ]

    update_step_profile_previews(
        front,
        back,
        front_obj,
        back_obj,
    )

    update_step_axis_preview(
        axis_x,
        front,
        back,
    )

    update_step_section_closure_preview(
        front,
        back,
    )

    # ------------------------------------------------------------------
    yield step_prompt(
        8, total,
        "Resample; preserve OUTER side connector and snap LEFT axis endpoints"
    )

    front = resample_open_chain(
        front,
        PROFILE_POINT_COUNT,
    )

    back = resample_open_chain(
        back,
        PROFILE_POINT_COUNT,
    )

    front, back = snap_axis_endpoints(
        front,
        back,
        axis_x,
    )

    if PASTILHA_THICKNESS_MODE and target_thickness_mm > 0.0:
        # Sampling can slightly miss the very highest/lowest original arc
        # point. Re-translate (never stretch) to retain exact overall Y size.
        front, back, final_pastilha_stats = place_facas_in_pastilha(
            front, back, target_thickness_mm
        )
        # Only X/radius is shared: Y stays separated by the side connector.
        back[-1].x = front[-1].x
        validate_pastilha_section(front, back, axis_x)
    else:
        # Legacy v26: RIGHT endpoints are a single point.
        back[-1] = front[-1].copy()

    if (
        abs(front[0].x - axis_x) > 1e-9
        or abs(back[0].x - axis_x) > 1e-9
    ):
        raise RuntimeError(
            "Axis endpoint snapping did not produce an exact axis coordinate."
        )

    log(
        f"Axis endpoints: "
        f"FRONT=(X={front[0].x:.9g}, Y={front[0].y:.9g}), "
        f"BACK=(X={back[0].x:.9g}, Y={back[0].y:.9g})"
    )

    log(
        f"Section spans: "
        f"width={max(p.x for p in front) - min(p.x for p in front):.6g}, "
        f"front/back Y range="
        f"{min(min(p.y for p in front), min(p.y for p in back)):.6g} .. "
        f"{max(max(p.y for p in front), max(p.y for p in back)):.6g}"
    )

    update_step_profile_previews(
        front,
        back,
        front_obj,
        back_obj,
    )

    update_step_axis_preview(
        axis_x,
        front,
        back,
    )

    update_step_section_closure_preview(
        front,
        back,
    )

    log(
        f"Pre-revolve closure: RIGHT merge distance="
        f"{(front[-1] - back[-1]).length:.9g}; "
        f"LEFT axis dy={(back[0].y - front[0].y):.9g}; "
        f"RIGHT side dy={(back[-1].y - front[-1].y):.9g}"
    )

    # ------------------------------------------------------------------
    yield step_prompt(
        9, total,
        "Revolve the section: LEFT axis closure + RIGHT straight side wall"
    )

    button = build_bridge_and_revolve(
        front,
        back,
        axis_x,
        SPIN_STEPS,
    )

    topo = mesh_topology(button)
    log(f"Revolved button topology: {topo}")

    if (
        topo["boundary_edges"] != 0
        or topo["nonmanifold_edges"] != 0
    ):
        raise RuntimeError(
            "Custom revolution produced invalid topology.\n"
            f"boundary_edges={topo['boundary_edges']}\n"
            f"nonmanifold_edges={topo['nonmanifold_edges']}\n\n"
            "The cross-section itself likely needs to be corrected."
        )

    clear_step_previews()

    try:
        front_obj.hide_set(True)
        front_obj.hide_viewport = True
        back_obj.hide_set(True)
        back_obj.hide_viewport = True
    except Exception:
        pass

    frame_object(button)
    force_viewport_redraw()

    # ------------------------------------------------------------------
    yield step_prompt(
        10, total,
        "Smooth shading and assign semantic FRONT/VERSO/SIDE material regions"
    )

    if SHADE_SMOOTH:
        safe_select_active(button)
        bpy.ops.object.shade_smooth()

    if TEXTURE_READY_OUTPUT:
        ensure_semantic_material_slots(button)
        assign_surface_material_indices(button)

    force_viewport_redraw()

    # ------------------------------------------------------------------
    yield step_prompt(
        11, total,
        (
            f"Cut {HOLE_COUNT} button holes with the Boolean workflow"
            if CREATE_HOLES
            else "Skip hole cutting (CREATE_HOLES is False)"
        )
    )

    if CREATE_HOLES:
        button = apply_holes(
            button,
            axis_x,
        )
    else:
        log("Holes disabled.")

    frame_object(button)
    force_viewport_redraw()

    # ------------------------------------------------------------------
    yield step_prompt(
        12, total,
        "Purge cutters and clean temporary/source import objects"
    )

    purge_hole_cutter_objects()
    purge_stale_blender_cylinders()

    scene_meshes = [
        obj.name
        for obj in bpy.context.scene.objects
        if obj.type == 'MESH'
    ]

    log(
        f"Final scene mesh objects: {scene_meshes}"
    )

    log(
        f"Final Button_3D: name={button.name!r}, "
        f"visible={not button.hide_viewport}, "
        f"in_scene={button.name in bpy.context.scene.objects}"
    )

    log(
        "Generated collection objects: "
        f"{[obj.name for obj in get_or_create_collection(GENERATED_COLLECTION_NAME).objects]}"
    )

    cleanup_imported_objects(
        front_obj,
        back_obj,
    )

    clear_collection(
        TEMP_COLLECTION_NAME
    )

    force_viewport_redraw()

    # ------------------------------------------------------------------
    yield step_prompt(
        13, total,
        "Apply final presentation transform, recenter, UVs, and texture-ready metadata"
    )

    if any(
        abs(v) > 1e-12
        for v in (
            FINAL_ROTATE_X_DEG,
            FINAL_ROTATE_Y_DEG,
            FINAL_ROTATE_Z_DEG,
        )
    ):
        button.rotation_euler = (
            math.radians(FINAL_ROTATE_X_DEG),
            math.radians(FINAL_ROTATE_Y_DEG),
            math.radians(FINAL_ROTATE_Z_DEG),
        )

        if TEXTURE_READY_OUTPUT:
            log(
                "Presentation rotation kept on the object (not baked) "
                "to preserve canonical texture coordinates."
            )
        else:
            safe_select_active(button)
            bpy.ops.object.transform_apply(
                rotation=True
            )

    if (
        TEXTURE_READY_OUTPUT
        and RECENTER_OUTPUT
    ):
        recenter_output_geometry(button)

    if TEXTURE_READY_OUTPUT:
        finalize_texture_ready_data(
            button,
            axis_x,
        )

    frame_object(button)
    force_viewport_redraw()

    # ------------------------------------------------------------------
    yield step_prompt(
        14, total,
        "Finish the build and print the final topology/dimensions report"
    )

    dims = button.dimensions.copy()
    final_topo = mesh_topology(button)

    log("============================================")
    log("BUTTON BUILD SUCCESS")
    log(
        f"Dimensions: "
        f"{dims.x:.6g} x {dims.y:.6g} x {dims.z:.6g}"
    )
    log(f"Topology: {final_topo}")
    log(
        "Requested exact size: "
        f"diameter={target_diameter_mm:.6g} mm, "
        f"thickness={target_thickness_mm:.6g} mm "
        "(0 means use legacy/fallback setting)"
    )
    log(
        "Final measured size: "
        f"diameter≈{max(dims.x, dims.z) / SCENE_UNITS_PER_MM:.6g} mm, "
        f"thickness≈{dims.y / SCENE_UNITS_PER_MM:.6g} mm"
    )
    log(
        f"Texture-ready output: "
        f"{TEXTURE_READY_OUTPUT}"
    )
    log(
        f"Output recentered: "
        f"{TEXTURE_READY_OUTPUT and RECENTER_OUTPUT}"
    )
    log(
        f"Spin/revolution steps: "
        f"{SPIN_STEPS}"
    )
    log(
        f"Revolve axis X: "
        f"{axis_x:.6g}"
    )
    log(
        f"Revolve axis mode: "
        f"{REVOLVE_AXIS_MODE}"
    )
    log(
        "Front orientation: unchanged / as imported"
    )
    log(
        f"Back rotated 180 X: "
        f"{BACK_ROTATE_180_X}"
    )
    log(
        f"Holes: "
        f"{HOLE_COUNT if CREATE_HOLES else 0} | "
        f"radius={HOLE_RADIUS_MM:.6g} mm | "
        f"distance={HOLE_DISTANCE_MM:.6g} mm"
    )
    log("============================================")

    show_popup(
        "DXF button generated successfully.\n\n"
        f"Dimensions: "
        f"{dims.x:.4g} x {dims.y:.4g} x {dims.z:.4g}\n"
        f"Topology: boundary={final_topo['boundary_edges']}, "
        f"non-manifold={final_topo['nonmanifold_edges']}\n"
        f"Holes: {HOLE_COUNT if CREATE_HOLES else 0}\n"
        f"Texture-ready: {TEXTURE_READY_OUTPUT}",
        title="DXF Button Builder v28",
        icon='CHECKMARK',
    )

    force_viewport_redraw()


# ============================================================================
# MODAL OPERATOR
# ============================================================================

class DXF_OT_step_button_build(bpy.types.Operator):
    bl_idname = "dxf.step_button_build"
    bl_label = "DXF Button Step Build"
    bl_description = (
        "Build a DXF button step-by-step using exact requested dimensions"
    )
    bl_options = {'REGISTER'}

    target_diameter_mm: bpy.props.FloatProperty(
        name="Final Diameter (mm)",
        description=(
            "Requested final outside button diameter. "
            "Use 0 to preserve the DXF diameter."
        ),
        default=DEFAULT_TARGET_DIAMETER_MM,
        min=0.0,
        precision=3,
    )

    target_thickness_mm: bpy.props.FloatProperty(
        name="Final Thickness (mm)",
        description=(
            "Requested final button thickness along Y. "
            "Use 0 to use the legacy DXF thickness fit."
        ),
        default=DEFAULT_TARGET_THICKNESS_MM,
        min=0.0,
        precision=3,
    )

    def _set_status(self, context, message):
        self._message = message

        log("")
        log(">>> " + message)

        status = (
            message
            + "    [ENTER = continue]    [ESC = cancel]"
        )

        try:
            context.workspace.status_text_set(
                status
            )
        except Exception:
            pass

        try:
            if context.area is not None:
                context.area.header_text_set(
                    text=status
                )
        except Exception:
            pass

        try:
            self.report(
                {'INFO'},
                message[:250],
            )
        except Exception:
            pass

        force_viewport_redraw()

    def _clear_status(self, context):
        try:
            context.workspace.status_text_set(
                None
            )
        except Exception:
            pass

        try:
            if context.area is not None:
                context.area.header_text_set(
                    text=None
                )
        except Exception:
            pass

    def draw(self, context):
        layout = self.layout

        layout.label(
            text="Exact final button size"
        )

        layout.prop(
            self,
            "target_diameter_mm",
        )

        layout.prop(
            self,
            "target_thickness_mm",
        )

        layout.separator()

        layout.label(
            text="Use 0 for either value to preserve that DXF dimension."
        )

    def invoke(self, context, event):
        if ASK_EXACT_SIZE_ON_START:
            return context.window_manager.invoke_props_dialog(
                self,
                width=420,
            )

        return self.execute(context)

    def execute(self, context):
        self._generator = build_button_steps(
            target_diameter_mm=float(
                self.target_diameter_mm
            ),
            target_thickness_mm=float(
                self.target_thickness_mm
            ),
        )

        log(
            "Requested size from dialog: "
            f"diameter={self.target_diameter_mm:.6g} mm, "
            f"thickness={self.target_thickness_mm:.6g} mm"
        )

        try:
            first_prompt = next(
                self._generator
            )
        except StopIteration:
            return {'FINISHED'}
        except Exception as exc:
            show_popup(
                str(exc),
                title="DXF Button Builder v28 - Error",
                icon='ERROR',
            )
            return {'CANCELLED'}

        self._set_status(
            context,
            first_prompt,
        )

        context.window_manager.modal_handler_add(
            self
        )

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if (
            event.type == 'ESC'
            and event.value == 'PRESS'
        ):
            self._clear_status(context)

            log("============================================")
            log("STEP BUILD CANCELLED BY USER")
            log(
                "Current geometry was intentionally left in the scene "
                "for inspection."
            )
            log("============================================")

            force_viewport_redraw()
            return {'CANCELLED'}

        if (
            event.type in {'RET', 'NUMPAD_ENTER'}
            and event.value == 'PRESS'
        ):
            try:
                next_prompt = next(
                    self._generator
                )

                self._set_status(
                    context,
                    next_prompt,
                )

                # Do not pass the Enter key through to the Text Editor.
                return {'RUNNING_MODAL'}

            except StopIteration:
                self._clear_status(context)

                log("")
                log(
                    "Interactive build finished. "
                    "No more steps remain."
                )

                force_viewport_redraw()
                return {'FINISHED'}

            except Exception as exc:
                self._clear_status(context)

                log("============================================")
                log("BUILD FAILED")
                log(str(exc))
                log(
                    "Current/imported/temp geometry was intentionally "
                    "left where possible so you can inspect the failed step."
                )
                log("============================================")

                show_popup(
                    str(exc),
                    title="DXF Button Builder v28 - Error",
                    icon='ERROR',
                )

                force_viewport_redraw()
                return {'CANCELLED'}

        # Let viewport orbit/pan/zoom and other normal UI events continue to
        # work while the step builder waits for Enter.
        return {'PASS_THROUGH'}


def register_step_operator():
    # Safe when rerunning the script from Blender's Text Editor.
    old_class = getattr(
        bpy.types,
        "DXF_OT_step_button_build",
        None,
    )

    if old_class is not None:
        try:
            bpy.utils.unregister_class(
                old_class
            )
        except Exception:
            pass

    bpy.utils.register_class(
        DXF_OT_step_button_build
    )


def run_all_steps_without_pausing():
    """Fallback/debug mode when INTERACTIVE_STEP_MODE is False."""
    generator = build_button_steps(
        target_diameter_mm=DEFAULT_TARGET_DIAMETER_MM,
        target_thickness_mm=DEFAULT_TARGET_THICKNESS_MM,
    )

    try:
        while True:
            prompt = next(generator)
            log(
                "AUTO MODE: "
                + prompt.replace(
                    "Press ENTER to run this action. ESC cancels.",
                    ""
                )
            )
    except StopIteration:
        pass


def main():
    if INTERACTIVE_STEP_MODE:
        register_step_operator()

        log("============================================")
        log("INTERACTIVE STEP MODE")
        log(
            "First choose the desired diameter/thickness in the size popup. "
            "Then press ENTER / NUMPAD ENTER for each major action."
        )
        log(
            "Press ESC to stop; the current geometry will remain "
            "visible for inspection."
        )
        log("============================================")

        bpy.ops.dxf.step_button_build(
            'INVOKE_DEFAULT'
        )
    else:
        run_all_steps_without_pausing()


main()


if bpy.app.background:
    bpy.ops.wm.save_as_mainfile(filepath='C:\\Users\\Aprendiz Financeiro\\Downloads\\Erick\\site\\versions\\planner-pass-2026-10-19\\blender\\button_13646_18_final_verified.blend')
