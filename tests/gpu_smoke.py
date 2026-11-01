from pathlib import Path
import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
ascii_render.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'build/verification/ascii_demo.blend'))
scene = bpy.context.scene
scene.ascii_render.animation_data_clear() if hasattr(scene.ascii_render, 'animation_data_clear') else None
scene.ascii_render.columns = 110
scene.render.resolution_x = 480
scene.render.resolution_y = 320
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.render.compositor_device = 'GPU'
scene.render.filepath = str(ROOT / 'build/verification/gpu.png')
bpy.ops.render.render(write_still=True)
image = bpy.data.images.load(scene.render.filepath)
pixels = np.array(image.pixels[:]).reshape(320, 480, 4)
assert pixels[:, :, :3].std() > 0.03
print('GPU_COMPOSITOR_PASSED', pixels[:, :, :3].std())
scene.render.engine = 'CYCLES'
scene.render.compositor_device = 'CPU'
scene.render.filepath = str(ROOT / 'build/verification/reloaded.png')
bpy.ops.render.render(write_still=True)
print('RELOAD_PASSED')
scene.render.engine = 'CYCLES'
scene.render.compositor_device = 'CPU'
settings = scene.ascii_render
scene.animation_data_clear()
settings.columns = 110
scene.render.engine = 'CYCLES'
scene.render.compositor_device = 'GPU'
scene.cycles.samples = 8
scene.cycles.preview_samples = 8
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'RENDERED'
            area.spaces.active.shading.use_compositor = 'CAMERA'
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
            area.spaces.active.show_region_ui = True
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'build/verification/ascii_demo.blend'))
