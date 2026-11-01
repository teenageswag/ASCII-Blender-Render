"""Export the verified demo with portable output paths."""
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
ascii_render.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'build/selective/selective_demo.blend'))
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.filepath = '//renders/ascii_'
scene.ascii_render.world_mode = 'SOLID'
scene.frame_start, scene.frame_end = 1, 1
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'examples/selective.blend'), compress=True)
print('PORTABLE_EXAMPLE_SAVED')
