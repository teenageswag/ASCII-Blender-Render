"""Run in an isolated foreground-capable Blender, without --background.

Exercises real new windows, workspace changes and temporary fullscreen screens.
"""
from pathlib import Path
import os
import sys
import traceback

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor, viewport

ascii_render.register()
scene = bpy.context.scene
compositor.install(scene)
first = bpy.context.window
original_workspace = first.workspace
space = next(a.spaces.active for a in first.screen.areas if a.type == 'VIEW_3D')
space.shading.use_compositor = 'CAMERA'
space.shading.type = 'SOLID'
scene.ascii_render.preview_in_viewport = True
phase = 0
second = None
second_original = None


def step():
    global phase, second, second_original
    if phase == 0:
        before = set(bpy.context.window_manager.windows)
        bpy.ops.wm.window_new_main()
        second = next(w for w in bpy.context.window_manager.windows if w not in before)
        other_space = next(a.spaces.active for a in second.screen.areas if a.type == 'VIEW_3D')
        second_original = 'CAMERA'  # A main window clones the parent's layout/bookmarks.
    elif phase == 1:
        viewport._watch()
        other_space = next(a.spaces.active for a in second.screen.areas if a.type == 'VIEW_3D')
        assert other_space.shading.use_compositor == 'ALWAYS'
        bookmarks = {s.name: viewport._records(s) for s in bpy.data.screens if viewport.KEY in s}
        scene.ascii_render.preview_in_viewport = False
        assert space.shading.use_compositor == 'CAMERA'
        assert other_space.shading.use_compositor == second_original, bookmarks
        scene.ascii_render.preview_in_viewport = True
        second.scene = bpy.data.scenes.new('No ASCII in this window')
        viewport._watch()
        assert other_space.shading.use_compositor == second_original
        assert space.shading.use_compositor == 'ALWAYS'
        target = next(w for w in bpy.data.workspaces if w != original_workspace)
        first.workspace = target
    elif phase == 2:
        viewport._watch()
        assert any(viewport.KEY in s for s in bpy.data.screens)
        scene.ascii_render.preview_in_viewport = False
        assert space.shading.use_compositor == 'CAMERA'
        assert not any(viewport.KEY in s for s in bpy.data.screens)
        first.workspace = original_workspace
    elif phase == 3:
        scene.ascii_render.preview_in_viewport = True
        viewport._watch()
        area = next(a for a in first.screen.areas if a.type == 'VIEW_3D')
        with bpy.context.temp_override(window=first, area=area):
            bpy.ops.screen.screen_full_area(use_hide_panels=True)
    elif phase == 4:
        viewport._watch()
        full_space = next(a.spaces.active for a in first.screen.areas if a.type == 'VIEW_3D')
        assert full_space.shading.use_compositor == 'ALWAYS'
        scene.ascii_render.preview_in_viewport = False
        assert full_space.shading.use_compositor == 'CAMERA', 'Fullscreen lost original state'
        scene.ascii_render.preview_in_viewport = True
        area = next(a for a in first.screen.areas if a.type == 'VIEW_3D')
        with bpy.context.temp_override(window=first, area=area):
            bpy.ops.screen.screen_full_area(use_hide_panels=True)
    elif phase == 5:
        viewport._watch()
        scene.ascii_render.preview_in_viewport = False
        assert space.shading.use_compositor == 'CAMERA', 'Leaving fullscreen lost original state'
        ascii_render.unregister()
        assert not any(viewport.KEY in s for s in bpy.data.screens)
        assert not any(viewport.BACKUP_KEY in s for s in bpy.data.scenes)
        print('ALL_VIEWPORT_UI_TESTS_PASSED', flush=True)
        bpy.ops.wm.quit_blender()
        return None
    phase += 1
    return 0.5


def guarded_step():
    try:
        return step()
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)


bpy.app.timers.register(guarded_step, first_interval=1)
