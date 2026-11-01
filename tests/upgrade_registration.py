"""Upgrade the actual 1.1.0 ZIP in one Blender session, retaining its module cache."""
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
with zipfile.ZipFile(ROOT / 'releases/ascii_render-1.1.0.zip') as archive:
    archive.extractall(package)
sys.path.insert(0, str(stage))
import ascii_render
assert ascii_render.bl_info['version'] == (1, 1, 0)
ascii_render.register()
scene = bpy.context.scene
scene.ascii_render.columns = 163
node = ascii_render.compositor.install(scene)
scene.frame_set(1)
assert node.inputs['Columns'].default_value == 163

shutil.copytree(ROOT / 'ascii_render', package, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('__pycache__'))
importlib.invalidate_caches()
importlib.reload(ascii_render)
assert ascii_render.bl_info['version'] == (1, 1, 1)
ascii_render.register()
scene.frame_set(2)
assert scene.ascii_render.columns == 163
assert node.inputs['Columns'].default_value == 163
assert bpy.ops.ascii_render.preset(preset='COLOR') == {'FINISHED'}
ascii_render.unregister()
ascii_render.unregister()
assert not hasattr(bpy.types.Scene, 'ascii_render')
print('IN_PLACE_UPGRADE_PASSED')
