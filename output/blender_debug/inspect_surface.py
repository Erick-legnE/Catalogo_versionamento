import bpy
import bmesh
from mathutils import Vector

body = max(
    (obj for obj in bpy.context.scene.objects if obj.type == "MESH" and not obj.name.startswith("Personalizado_")),
    key=lambda obj: obj.dimensions.x * obj.dimensions.y * max(obj.dimensions.z, 0.001),
)

corners = [body.matrix_world @ Vector(corner) for corner in body.bound_box]
bounds = {
    "min_x": min(point.x for point in corners),
    "max_x": max(point.x for point in corners),
    "min_y": min(point.y for point in corners),
    "max_y": max(point.y for point in corners),
    "min_z": min(point.z for point in corners),
    "max_z": max(point.z for point in corners),
}

depsgraph = bpy.context.evaluated_depsgraph_get()
print("BODY", body.name, "VERTICES", len(body.data.vertices), "POLYGONS", len(body.data.polygons))
print("BOUNDS", bounds)
mesh_copy = body.data.copy()
bm = bmesh.new()
bm.from_mesh(mesh_copy)
boundary_edges = sum(1 for edge in bm.edges if edge.is_boundary)
non_manifold_edges = sum(1 for edge in bm.edges if not edge.is_manifold)
bm.free()
bpy.data.meshes.remove(mesh_copy)
print("TOPOLOGY", {"boundary_edges": boundary_edges, "non_manifold_edges": non_manifold_edges})
print("PERSONALISATION_OBJECTS", [obj.name for obj in bpy.context.scene.objects if obj.name.startswith("Personalizado_")])
for x in (-6.0, -4.5, -3.0, -1.5, 0.0, 1.5, 3.0, 4.5, 6.0):
    origin = Vector((x, bounds["min_y"] - 2.0, 0.0))
    hit, location, normal, face_index, hit_object, matrix = bpy.context.scene.ray_cast(
        depsgraph, origin, Vector((0.0, 1.0, 0.0)), distance=(bounds["max_y"] - bounds["min_y"] + 4.0)
    )
    print("RAY", x, bool(hit), tuple(round(value, 6) for value in location) if hit else None, hit_object.name if hit_object else None)
