"""EXR silhouette-ring regression: no native color in cleaned ASCII pixels."""
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor, coverage

ascii_render.register()
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.render.resolution_x, scene.render.resolution_y = 400, 280
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
scene.render.compositor_device = 'CPU'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)


def sphere(name, location, color):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=location)
    obj = bpy.context.object
    obj.name = name
    mat = bpy.data.materials.new(name)
    tree = mat.node_tree
    emission = tree.nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (*color, 1)
    tree.links.new(emission.outputs[0], tree.nodes['Material Output'].inputs['Surface'])
    obj.data.materials.append(mat)
    return obj


sphere('ASCII red', (-0.65, 0, 0), (0.9, 0.01, 0.01))
native = sphere('Native green, touching', (0.8, -0.2, 0), (0.01, 0.8, 0.01))
bpy.ops.object.camera_add(location=(0, -8, 1.2))
scene.camera = bpy.context.object
scene.camera.data.type = 'ORTHO'
scene.camera.data.ortho_scale = 4.9
scene.camera.rotation_euler = (-scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.12, 0.8, 1)
node = compositor.install(scene)
settings = scene.ascii_render
settings.foreground, settings.background = (1, 1, 1, 1), (0, 0, 0, 1)
settings.columns = 32
native.ascii_render_enabled = False
settings.world_mode = 'ORIGINAL'
tree = scene.compositing_node_group
output = next(n for n in tree.nodes if n.type == 'GROUP_OUTPUT')
mask_source = next(n for n in tree.nodes if n.get(coverage.OWNED) == 'source')
out = ROOT / 'build/edges'
out.mkdir(parents=True, exist_ok=True)


def render(name):
    path = out / f'{name}.exr'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    values = np.array(image.pixels[:]).reshape(280, 400, 4)
    bpy.data.images.remove(image)
    return values


settings.enabled = False
original = render('original')
settings.enabled = True
tree.links.new(mask_source.outputs[coverage.AOV_NAME], output.inputs['Image'])
mask = render('mask')
tree.links.new(node.outputs[0], output.inputs['Image'])
included = mask[:, :, 1] - mask[:, :, 0]
ring = (included > settings.edge_mask_threshold) & (included < 0.99) & (mask[:, :, 0] < 1e-6)
assert ring.sum() > 50
settings.remove_original_edge = False
legacy = render('legacy')
settings.remove_original_edge = True
clean = render('clean')
assert np.abs(legacy[ring, 0] - legacy[ring, 1]).max() > 0.01, 'Fixture must reproduce colored fringe'
assert np.abs(clean[ring, 0] - clean[ring, 1]).max() < 1e-5, 'Native color leaked into silhouette ring'
native_interior = mask[:, :, 0] > 1 - 1e-6
assert np.abs(clean[native_interior] - original[native_interior]).max() < 1e-5
world = mask[:, :, 1] < 1e-7
assert np.abs(clean[world] - original[world]).max() < 1e-5, 'Do not dilate into the world'
settings.world_mode = 'TRANSPARENT'
transparent = render('transparent')
assert transparent[ring, 3].min() > 0.999, 'Clean silhouette must have no alpha holes'
assert transparent[world, 3].max() < 1e-5
settings.world_mode = 'ASCII'
native.ascii_render_enabled = True
full = render('full')
assert np.abs(full[:, :, 0] - full[:, :, 1]).max() < 1e-5, 'Full-frame must contain only monochrome ASCII'
print('ALL_EDGE_TESTS_PASSED', 'ring_pixels', int(ring.sum()), flush=True)
