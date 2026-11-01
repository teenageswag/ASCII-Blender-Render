"""Low-density visual regression scene; --before records the 1.1.1 baseline."""
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

ascii_render.register()
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.render.resolution_x, scene.render.resolution_y = 960, 600
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.compositor_device = 'CPU'
scene.render.dither_intensity = 0
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat('-Z', 'Y').to_euler()


bpy.ops.mesh.primitive_cube_add(size=1.65, location=(-1.3, 0, 1))
cube = bpy.context.object
cube.rotation_euler = (0.08, 0.12, -0.22)
mat = bpy.data.materials.new('Checker texture')
checker = mat.node_tree.nodes.new('ShaderNodeTexChecker')
checker.inputs['Color1'].default_value = (0.02, 0.045, 0.12, 1)
checker.inputs['Color2'].default_value = (0.85, 0.3, 0.055, 1)
checker.inputs['Scale'].default_value = 5
mat.node_tree.links.new(checker.outputs['Color'], mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
cube.data.materials.append(mat)
bpy.ops.mesh.primitive_monkey_add(location=(1.2, 0, 1.05))
monkey = bpy.context.object
monkey.rotation_euler.z = -0.12
sub = monkey.modifiers.new('Smooth', 'SUBSURF')
sub.levels = sub.render_levels = 1
for polygon in monkey.data.polygons:
    polygon.use_smooth = True
mat = bpy.data.materials.new('Suzanne diffuse')
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.18, 0.65, 0.38, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.65
monkey.data.materials.append(mat)
bpy.ops.object.camera_add(location=(3.1, -12, 4.3))
scene.camera = bpy.context.object
scene.camera.data.type = 'ORTHO'
scene.camera.data.ortho_scale = 6.4
aim(scene.camera, (0, 0, 1))
for location, energy, size in (((-3, -4, 6), 1300, 3), ((3, 2, 5), 650, 3)):
    bpy.ops.object.light_add(type='AREA', location=location)
    bpy.context.object.data.energy = energy
    bpy.context.object.data.size = size
    aim(bpy.context.object, (0, 0, 1))
scene.world.color = (0.015, 0.015, 0.015)
node = compositor.install(scene)
settings = scene.ascii_render
settings.columns = 64
settings.color_mode = 'COLOR'
settings.color_gain = 1.5
settings.background = (0.003, 0.005, 0.009, 1)
settings.character_set = 'DETAILED'
settings.edge_threshold = 0.23
images = ROOT / 'docs/images'
images.mkdir(parents=True, exist_ok=True)


def render(path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = np.array(image.pixels[:]).reshape(600, 960, 4)
    bpy.data.images.remove(image)
    assert np.isfinite(pixels).all()
    return pixels


if '--before' in sys.argv:
    render(images / 'smart-before.png')
else:
    out = ROOT / 'build/smart'
    out.mkdir(parents=True, exist_ok=True)
    classic = render(out / 'classic.png')
    settings.match_mode = 'SMART'
    smart = render(images / 'smart-after.png')
    assert node.inputs['Match Mode'].default_value == 1
    assert np.abs(smart - classic).mean() > 0.002
    assert smart[:, 100:430, :3].std() > 0.04, 'Checker must retain visible variation'
    assert smart[:, 510:850, :3].std() > 0.04, 'Suzanne must retain visible ink'
    settings.color_source = 'DIFFUSE'
    render(out / 'diffuse.png')
    assert node.inputs['Albedo'].is_linked
    settings.scale_strength = 0.85
    settings.min_scale, settings.max_scale = 0.5, 1.0
    scaled = render(out / 'scaled.png')
    assert np.abs(scaled - smart).mean() > 0.001
    settings.character_set = 'CUSTOM'
    settings.custom_characters = ' .o@'
    render(out / 'custom.png')
    settings.adaptive_strength = 0.2
    settings.keyframe_insert('adaptive_strength', frame=1)
    settings.adaptive_strength = 0.9
    settings.keyframe_insert('adaptive_strength', frame=3)
    scene.frame_set(1)
    assert abs(node.inputs['Adaptive Strength'].default_value - 0.2) < 1e-5
    scene.frame_set(3)
    assert abs(node.inputs['Adaptive Strength'].default_value - 0.9) < 1e-5
    print('ALL_SMART_RENDER_TESTS_PASSED', flush=True)
