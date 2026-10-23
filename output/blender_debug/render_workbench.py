import bpy
import sys
from mathutils import Vector

arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
view = "BACK" if "--back" in arguments else "FRONT"

body = max(
    (obj for obj in bpy.context.scene.objects if obj.type == "MESH" and not obj.name.startswith("Personalizado_")),
    key=lambda obj: obj.dimensions.x * obj.dimensions.y * max(obj.dimensions.z, 0.001),
)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.studio_light = "paint.sl"
scene.display.shading.color_type = "SINGLE"
scene.display.shading.single_color = (0.72, 0.74, 0.78)
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = "WORLD"
scene.display.shading.curvature_ridge_factor = 2.0
scene.display.shading.curvature_valley_factor = 2.0
scene.display.shading.background_type = "VIEWPORT"
scene.display.shading.background_color = (0.055, 0.065, 0.085)

camera = bpy.data.objects.get("ENGRAVING_VERIFICATION_CAMERA")
if not camera:
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "ENGRAVING_VERIFICATION_CAMERA"
camera.data.type = "ORTHO"
camera.data.ortho_scale = 38.0
camera.location = Vector((0.0, 60.0 if view == "BACK" else -60.0, 8.0))
target = Vector((0.0, 0.0, 0.0))
camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = camera
scene.render.resolution_x = 1000
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
blend_stem = bpy.path.basename(bpy.data.filepath).rsplit(".", 1)[0]
scene.render.filepath = str(bpy.path.abspath(f"//{blend_stem}_workbench.png"))
bpy.ops.render.render(write_still=True)
if "--save-view" in arguments:
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
