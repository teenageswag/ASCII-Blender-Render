"""Real Screen/Space lifecycle, persisted bookmarks and input-sized grid checks."""
from pathlib import Path
import importlib
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor, viewport

ascii_render.register()
scene = bpy.context.scene
node = compositor.install(scene)
screen = bpy.context.window.screen
area = next(a for a in screen.areas if a.type == 'VIEW_3D')
space = area.spaces.active
space.shading.type = 'SOLID'
space.shading.use_compositor = 'CAMERA'
space.region_3d.view_perspective = 'PERSP'
settings = scene.ascii_render
assert settings.preview_mode == 'ALWAYS'
settings.preview_in_viewport = True
assert space.shading.use_compositor == 'ALWAYS'
assert space.shading.type == 'SOLID' and space.region_3d.view_perspective == 'PERSP'
assert viewport.KEY in screen
settings.preview_mode = 'CAMERA'
assert space.shading.use_compositor == 'CAMERA'
settings.preview_mode = 'ALWAYS'
settings.preview_in_viewport = False
assert space.shading.use_compositor == 'CAMERA'
assert viewport.KEY not in screen

# A split inherits the owned ALWAYS value; both halves must restore CAMERA.
settings.preview_in_viewport = True
with bpy.context.temp_override(window=bpy.context.window, area=area):
    bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
settings.preview_in_viewport = False  # Before any topology notification/timer.
assert all(a.spaces.active.shading.use_compositor == 'CAMERA' for a in screen.areas if a.type == 'VIEW_3D')
settings.preview_in_viewport = True
viewport._watch()
split_spaces = [a.spaces.active for a in screen.areas if a.type == 'VIEW_3D']
assert len(split_spaces) == 2
assert all(s.shading.use_compositor == 'ALWAYS' for s in split_spaces)
split_bookmarks = viewport._records(screen)
settings.preview_in_viewport = False
assert all(s.shading.use_compositor == 'CAMERA' for s in split_spaces), split_bookmarks
# Close the new half again so the persistence checks retain a simple layout.
new_area = next(a for a in screen.areas if a.type == 'VIEW_3D' and a.spaces.active != space)
new_area.type = 'CONSOLE'

# Manual changes are retained both during sync and when preview is disabled.
settings.preview_in_viewport = True
space.shading.use_compositor = 'DISABLED'
viewport.sync_all()
settings.preview_mode = 'CAMERA'
assert space.shading.use_compositor == 'DISABLED'
settings.preview_in_viewport = False
assert space.shading.use_compositor == 'DISABLED'

# A newly converted editor is discovered without a depsgraph/redraw callback.
space.shading.use_compositor = 'CAMERA'
settings.preview_mode = 'ALWAYS'
settings.preview_in_viewport = True
other_area = next(a for a in screen.areas if a.type == 'PROPERTIES')
other_area.type = 'VIEW_3D'
other_space = other_area.spaces.active
other_space.shading.use_compositor = 'DISABLED'
viewport._watch()
assert other_space.shading.use_compositor == 'ALWAYS'
settings.enabled = False
assert space.shading.use_compositor == 'CAMERA'
assert other_space.shading.use_compositor == 'DISABLED'
settings.enabled = True
assert other_space.shading.use_compositor == 'ALWAYS'

# Simulate in-place source reload, then disable: original state must survive.
importlib.reload(ascii_render)
ascii_render.register()
viewport = ascii_render.viewport
assert space.shading.use_compositor == 'ALWAYS'
scene.ascii_render.preview_in_viewport = False
assert space.shading.use_compositor == 'CAMERA'
assert other_space.shading.use_compositor == 'DISABLED'

# Save/load replaces all RNA pointers. Stored paths must recover each bookmark.
scene.ascii_render.preview_in_viewport = True
path = ROOT / 'build/viewport-preview.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
scene = bpy.context.scene
screen = bpy.context.window.screen
spaces = list(viewport._spaces(screen))
assert len(spaces) == 3  # Includes the cached VIEW_3D space in the Console area.
assert all(a.spaces.active.shading.use_compositor == 'ALWAYS' for a in screen.areas if a.type == 'VIEW_3D')
scene.ascii_render.preview_in_viewport = False
assert sorted(s.shading.use_compositor for s in spaces) == ['CAMERA', 'CAMERA', 'DISABLED']
assert viewport.KEY not in screen

# Grid controls are native drivers; resolution comes from Image Info, not Python.
scene.ascii_render.grid_mode = 'PIXELS'
scene.ascii_render.cell_pixels = 16
scene.frame_set(1)
node = compositor.effect_node(scene)
assert node.inputs['Grid Mode'].default_value == 1
assert node.inputs['Cell Pixels'].default_value == 16
assert node.node_tree.nodes['Image size'].bl_idname == 'CompositorNodeImageInfo'
scene.ascii_render.preview_in_viewport = True
compositor.remove(scene)
assert sorted(s.shading.use_compositor for s in spaces) == ['CAMERA', 'CAMERA', 'DISABLED']
assert viewport.KEY not in screen
compositor.install(scene)
viewport.sync_all()
assert all(a.spaces.active.shading.use_compositor == 'ALWAYS' for a in screen.areas if a.type == 'VIEW_3D')
ascii_render.unregister()
assert sorted(s.shading.use_compositor for s in spaces) == ['CAMERA', 'CAMERA', 'DISABLED']
assert not bpy.app.timers.is_registered(viewport._watch)
assert not any(viewport.KEY in s for s in bpy.data.screens)
assert not any(viewport.BACKUP_KEY in s for s in bpy.data.scenes)
print('ALL_VIEWPORT_PREVIEW_TESTS_PASSED', flush=True)
