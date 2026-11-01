"""Upgrade the shipped 1.1.1 ZIP in one session, retaining its module cache."""
from pathlib import Path
import importlib
import shutil
import sys
import zipfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
stage = ROOT / 'build/upgrade_registration'
package = stage / 'ascii_render'
package.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(ROOT / 'releases/ascii_render-1.1.1.zip') as archive:
    archive.extractall(package)
sys.path.insert(0, str(stage))
import ascii_render
assert ascii_render.bl_info['version'] == (1, 1, 1)
ascii_render.register()
scene = bpy.context.scene
scene.ascii_render.columns = 163
scene.ascii_render.world_mode = 'SOLID'
node = ascii_render.compositor.install(scene)
assert node.inputs['Object Mask'].is_linked
mask_source = node.inputs['Object Mask'].links[0].from_socket
image_source = node.inputs['Image'].links[0].from_socket
tree = scene.compositing_node_group
output = next(n for n in tree.nodes if n.type == 'GROUP_OUTPUT' and n.is_active_output)
viewer = tree.nodes.new('CompositorNodeViewer')
tree.links.new(node.outputs['Image'], viewer.inputs['Image'])
scene.frame_set(1)
assert node.inputs['Columns'].default_value == 163

shutil.copytree(ROOT / 'ascii_render', package, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('__pycache__'))
importlib.invalidate_caches()
importlib.reload(ascii_render)
assert ascii_render.bl_info['version'] == (1, 2, 1)
ascii_render.register()
scene.frame_set(2)
assert scene.ascii_render.columns == 163
assert node.inputs['Columns'].default_value == 163
assert node.inputs['Image'].links[0].from_socket == image_source
assert node.inputs['Object Mask'].links[0].from_socket == mask_source
assert not any(node.inputs[name].is_linked for name, _, _, _ in ascii_render.compositor.CONTROLS)
assert output.inputs['Image'].links[0].from_node == node
assert viewer.inputs['Image'].links[0].from_node == node
assert bpy.ops.ascii_render.preset(preset='COLOR') == {'FINISHED'}
ascii_render.unregister()
ascii_render.unregister()
assert not hasattr(bpy.types.Scene, 'ascii_render')
print('IN_PLACE_UPGRADE_PASSED')
