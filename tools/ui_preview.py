"""Load the isolated demo in a second Blender instance, without installing."""
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
ascii_render.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'build/verification/ascii_demo.blend'))
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.preview_samples = 8
scene.render.compositor_device = 'GPU'
def initialize_view():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'PROPERTIES':
                area.spaces.active.context = 'RENDER'
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'RENDERED'
                area.spaces.active.shading.use_compositor = 'CAMERA'
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.show_region_ui = True
    print('UI_PREVIEW_READY', flush=True)
    return None


bpy.app.timers.register(initialize_view, first_interval=2)

