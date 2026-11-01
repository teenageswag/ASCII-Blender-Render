"""Run with Blender --background --factory-startup --python tests/render_smoke.py."""

from pathlib import Path
import math
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor

OUT = ROOT / 'build' / 'verification'
OUT.mkdir(parents=True, exist_ok=True)
ascii_render.register()
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 8
scene.render.resolution_x, scene.render.resolution_y = 960, 640
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.compositor_device = 'CPU'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)


def material(name, color, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = 0.3
    bsdf.inputs['Metallic'].default_value = metallic
    return mat


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


bpy.ops.mesh.primitive_monkey_add(location=(-1.0, 0, 1.1))
monkey = bpy.context.object
monkey.rotation_euler.z = math.radians(-12)
monkey.data.materials.append(material('Jade', (0.045, 0.65, 0.32), 0.15))
sub = monkey.modifiers.new('Smooth surface', 'SUBSURF')
sub.levels = sub.render_levels = 1
for polygon in monkey.data.polygons:
    polygon.use_smooth = True
monkey.rotation_euler.z = -0.2
monkey.keyframe_insert('rotation_euler', frame=1)
monkey.rotation_euler.z = 0.5
monkey.keyframe_insert('rotation_euler', frame=3)
bpy.ops.mesh.primitive_torus_add(major_radius=0.8, minor_radius=0.25,
    location=(1.2, 0.15, 1.15), rotation=(math.radians(72), 0, math.radians(15)))
bpy.context.object.data.materials.append(material('Coral', (0.85, 0.07, 0.035), 0.3))
for polygon in bpy.context.object.data.polygons:
    polygon.use_smooth = True
bpy.ops.mesh.primitive_plane_add(size=200)
bpy.context.object.data.materials.append(material('Ground', (0.035, 0.05, 0.085)))
bpy.ops.object.camera_add(location=(5.0, -10, 5))
scene.camera = bpy.context.object
scene.camera.data.type = 'ORTHO'
scene.camera.data.ortho_scale = 6.4
aim(scene.camera, (0, 0, 0.9))
for location, power, size in (((-3, -4, 6), 1400, 5), ((4, 1, 5), 1800, 4)):
    bpy.ops.object.light_add(type='AREA', location=location)
    lamp = bpy.context.object
    lamp.data.energy, lamp.data.shape, lamp.data.size = power, 'DISK', size
    aim(lamp, (0, 0, 1))
scene.world.color = (0.08, 0.08, 0.08)
scene.frame_set(1)
node = compositor.install(scene)
assert compositor.install(scene) == node, 'Setup must be idempotent'
settings = scene.ascii_render
settings.columns = 110


def render(name):
    path = OUT / f'{name}.png'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = np.array(image.pixels[:], dtype=np.float32).reshape(image.size[1], image.size[0], 4)
    bpy.data.images.remove(image)
    assert pixels.shape == (scene.render.resolution_y, scene.render.resolution_x, 4), pixels.shape
    assert np.isfinite(pixels).all()
    print('RENDER', name, 'range', pixels[:, :, :3].min(), pixels[:, :, :3].max(), 'std', pixels[:, :, :3].std())
    return pixels


settings.enabled = False
original = render('original')
settings.enabled = True
mono = render('monochrome')
assert np.abs(mono - original).mean() > 0.02
assert mono[:, :, :3].std() > 0.05, 'ASCII must contain visible ink'
settings.color_mode = 'COLOR'
color = render('color')
assert np.abs(color - mono).mean() > 0.005
assert node.inputs['Color Mode'].default_value == 1, 'Enum driver must update'
settings.contours = False
without_edges = render('without_contours')
assert np.abs(without_edges - color).mean() > 0.0005
settings.contours = True
settings.transparent_background = True
transparent = render('transparent')
assert transparent[:, :, 3].min() == 0 and transparent[:, :, 3].max() == 1
settings.transparent_background = False
settings.character_set = 'CUSTOM'
settings.custom_characters = ' .o@'
assert node.node_tree.nodes['Glyph atlas'].image['ascii_characters'] == ' .o@-|/\\'
custom = render('custom')
assert np.abs(custom - color).mean() > 0.001
settings.character_set = 'CLASSIC'

# Keyframe settings and render an actual image sequence through Blender's
# standard animation operator. Numeric drivers must evaluate without handlers.
settings.columns = 90
settings.keyframe_insert('columns', frame=1)
settings.columns = 130
settings.keyframe_insert('columns', frame=3)
scene.frame_set(1)
assert node.inputs['Columns'].default_value == 90
scene.frame_set(3)
assert node.inputs['Columns'].default_value == 130
settings.animation_data_clear() if hasattr(settings, 'animation_data_clear') else None
scene.render.resolution_x, scene.render.resolution_y = 480, 320
scene.cycles.samples = 2
scene.frame_start, scene.frame_end = 1, 3
scene.render.filepath = str(OUT / 'animation_')
bpy.ops.render.render(animation=True)
assert all((OUT / f'animation_{frame:04}.png').exists() for frame in range(1, 4))
scene.render.resolution_x, scene.render.resolution_y = 960, 640
scene.cycles.samples = 8
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'ascii_demo.blend'))

# Removal must restore the original connection and remove only ASCII drivers.
tree = scene.compositing_node_group
output = next(n for n in tree.nodes if n.type == 'GROUP_OUTPUT')
source = node.inputs['Image'].links[0].from_socket
compositor.remove(scene)
assert output.inputs['Image'].links[0].from_socket == source
assert not tree.animation_data or not tree.animation_data.drivers
assert compositor.effect_node(scene) is None
print('ALL_SMOKE_TESTS_PASSED')
