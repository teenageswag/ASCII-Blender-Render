"""Real renders that verify object isolation, world modes and shared materials."""
from pathlib import Path
import math
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor, coverage

OUT = ROOT / 'build/selective'
OUT.mkdir(parents=True, exist_ok=True)
ascii_render.register()
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 8
scene.render.resolution_x, scene.render.resolution_y = 1200, 720
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.dither_intensity = 0
scene.render.compositor_device = 'CPU'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat('-Z', 'Y').to_euler()


white = bpy.data.materials.new('Porcelain • shared by cube and cylinder')
white.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.8, 0.82, 0.86, 1)
white.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.32
bpy.ops.mesh.primitive_cube_add(size=1.7, location=(-1.25, 0, 0.9))
cube = bpy.context.object
cube.name = 'Cube • ASCII'
cube.data.materials.append(white)
cube.rotation_euler.z = math.radians(-12)
bevel = cube.modifiers.new('Soft edges', 'BEVEL')
bevel.width, bevel.segments = 0.07, 3
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.78, depth=1.85, location=(1.25, 0, 0.95))
cylinder = bpy.context.object
cylinder.name = 'Cylinder • Original'
cylinder.data.materials.append(white)
bevel = cylinder.modifiers.new('Soft edges', 'BEVEL')
bevel.width, bevel.segments = 0.06, 3
for polygon in cylinder.data.polygons:
    polygon.use_smooth = len(polygon.vertices) == 4
bpy.ops.object.camera_add(location=(3.2, -9, 3.4))
scene.camera = bpy.context.object
scene.camera.data.type = 'ORTHO'
scene.camera.data.ortho_scale = 6.7
aim(scene.camera, (0, 0, 0.95))
for location, energy, size in (((-3, -4, 6), 1100, 5), ((4, 1, 5), 850, 3)):
    bpy.ops.object.light_add(type='AREA', location=location)
    bpy.context.object.data.energy = energy
    bpy.context.object.data.shape = 'DISK'
    bpy.context.object.data.size = size
    aim(bpy.context.object, (0, 0, 1))
world = scene.world
texture = world.node_tree.nodes.new('ShaderNodeTexNoise')
texture.inputs['Scale'].default_value = 2.5
texture.inputs['Detail'].default_value = 2
coordinates = world.node_tree.nodes.new('ShaderNodeTexCoord')
world.node_tree.links.new(coordinates.outputs['Normal'], texture.inputs['Vector'])
ramp = world.node_tree.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.006, 0.012, 0.025, 1)
ramp.color_ramp.elements[1].color = (0.08, 0.12, 0.16, 1)
world.node_tree.links.new(texture.outputs['Fac'], ramp.inputs[0])
world.node_tree.links.new(ramp.outputs['Color'], world.node_tree.nodes['Background'].inputs['Color'])
node = compositor.install(scene)
settings = scene.ascii_render
settings.foreground = (0.45, 1.0, 0.73, 1)
settings.background = (0.002, 0.004, 0.007, 1)
settings.columns = 110
settings.exposure = -0.5


def render(name, raw=False):
    path = OUT / f'{name}.{"exr" if raw else "png"}'
    scene.render.image_settings.file_format = 'OPEN_EXR' if raw else 'PNG'
    if raw:
        scene.render.image_settings.color_depth = '32'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = np.array(image.pixels[:]).reshape(image.size[1], image.size[0], 4)
    bpy.data.images.remove(image)
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '8'
    print('RENDERED', name, flush=True)
    return pixels


settings.enabled = False
original = render('original')
settings.enabled = True
full = render('full_ascii')
cylinder.ascii_render_enabled = False
settings.world_mode = 'ORIGINAL'
hybrid = render('hybrid')
assert cube.data.materials[0] == cylinder.data.materials[0], 'Do not duplicate shared materials'
tree = scene.compositing_node_group
output = next(n for n in tree.nodes if n.type == 'GROUP_OUTPUT')
mask_source = next(n for n in tree.nodes if n.get(coverage.OWNED) == 'source')
tree.links.new(mask_source.outputs[coverage.AOV_NAME], output.inputs['Image'])
mask = render('mask', raw=True)
tree.links.new(node.outputs['Image'], output.inputs['Image'])
excluded = mask[:, :, 0] > 1 - 1e-7
included = (mask[:, :, 1] > 1 - 1e-7) & (mask[:, :, 0] < 1e-7)
background = mask[:, :, 1] < 1e-7
assert excluded.sum() > 10000 and included.sum() > 10000 and background.sum() > 10000
assert np.abs(hybrid[excluded] - original[excluded]).max() < 0.005, 'Excluded cylinder must match original'
assert np.abs(hybrid[background] - original[background]).max() < 0.005, 'World texture must stay original'
assert np.abs(hybrid[included] - original[included]).mean() > 0.1, 'Cube must be ASCII'
settings.world_mode = 'SOLID'
solid = render('solid_world')
assert solid[background, :3].std(axis=0).max() < 0.001
assert np.abs(solid[excluded] - original[excluded]).max() < 0.005
settings.world_mode = 'TRANSPARENT'
transparent = render('transparent_world')
assert transparent[background, 3].max() < 0.005
assert transparent[excluded, 3].min() > 0.99
settings.world_mode = 'ASCII'
excluded_full = render('excluded_full_world')
assert np.abs(excluded_full[excluded] - original[excluded]).max() < 0.005

# The same mask and selection must work with the EEVEE final renderer.
settings.world_mode = 'ORIGINAL'
scene.render.engine = 'BLENDER_EEVEE'
eevee = render('eevee_hybrid')
assert eevee[excluded, :3].mean() > 0.2

# Save a reproducible showcase scene and make sure callbacks prepare new meshes
# that have no material slots. Removing the effect must undo that preparation.
scene.render.engine = 'CYCLES'
bpy.ops.object.select_all(action='DESELECT')
cylinder.select_set(True)
bpy.context.view_layer.objects.active = cylinder
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'selective_demo.blend'))
bpy.ops.mesh.primitive_cube_add(location=(0, 0, -10))
empty = bpy.context.object
assert len(empty.data.materials) == 0
coverage.sync_scene(scene)
assert len(empty.data.materials) == 1
compositor.remove(scene)
assert len(empty.data.materials) == 0
assert not any(n.get(coverage.OWNED) for n in white.node_tree.nodes)
assert not any(a.name == coverage.AOV_NAME for a in scene.view_layers[0].aovs)
print('ALL_SELECTIVE_TESTS_PASSED', flush=True)
