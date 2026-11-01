"""Render regression for the disconnected outputs/control links left by 1.2.0."""
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor

ascii_render.register()
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x, scene.render.resolution_y = 320, 200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
scene.ascii_render.world_mode = 'SOLID'
scene.ascii_render.match_mode = 'SMART'
scene.ascii_render.character_set = 'MINIMAL'
scene.ascii_render.columns = 32
scene.ascii_render.contours = False
scene.ascii_render.min_contrast = 0.5
node = compositor.install(scene)
tree = scene.compositing_node_group
output = next(n for n in tree.nodes if n.type == 'GROUP_OUTPUT' and n.is_active_output)
mask = node.inputs['Object Mask'].links[0].from_socket
out = ROOT / 'build/migration-render'
out.mkdir(parents=True, exist_ok=True)

# Reproduce the observed 1.2.0 state, including a persisted broken scene.
node.node_tree['ascii_schema'] = 6
tree.links.new(mask, node.inputs['Match Mode'])
for link in list(output.inputs['Image'].links):
    tree.links.remove(link)
path = out / 'broken-1.2.0.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
scene = bpy.context.scene
node = compositor.effect_node(scene)
tree = scene.compositing_node_group
output = next(n for n in tree.nodes if n.type == 'GROUP_OUTPUT' and n.is_active_output)
assert node.node_tree['ascii_schema'] == compositor.SCHEMA
assert output.inputs['Image'].links[0].from_node == node
assert node.inputs['Image'].links[0].from_node.type == 'R_LAYERS'
assert node.inputs['Object Mask'].is_linked
assert not any(node.inputs[name].is_linked for name, _, _, _ in compositor.CONTROLS)
assert scene.ascii_render.match_mode == 'SMART'
assert scene.ascii_render.character_set == 'MINIMAL'
assert scene.ascii_render.world_mode == 'SOLID'

for device in ('CPU', 'GPU'):
    scene.render.compositor_device = device
    path = out / f'repaired-{device}.exr'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = np.array(image.pixels[:]).reshape(200, 320, 4)
    bpy.data.images.remove(image)
    assert np.isfinite(pixels).all()
    assert (pixels[:, :, :3].max(axis=2) > 0.4).sum() > 200, f'{device}: glyphs vanished after upgrade'
print('MIGRATION_RENDER_PASSED', flush=True)
