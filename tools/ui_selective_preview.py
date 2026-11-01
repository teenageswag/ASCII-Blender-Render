"""Open the selective demo in an isolated Blender process for visual QA."""
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
scene.ascii_render.preview_mode = 'CAMERA'


def initialize_view():
    window = bpy.context.window_manager.windows[0]
    area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    with bpy.context.temp_override(window=window, area=area):
        bpy.ops.screen.screen_full_area(use_hide_panels=False)
    area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    space = area.spaces.active
    space.shading.type = 'RENDERED'
    space.shading.use_compositor = 'CAMERA'
    space.overlay.show_overlays = False
    space.region_3d.view_perspective = 'CAMERA'
    space.region_3d.view_camera_zoom = 12
    space.show_region_ui = True
    print('SELECTIVE_PREVIEW_READY', flush=True)
    return None


bpy.app.timers.register(initialize_view, first_interval=2)
