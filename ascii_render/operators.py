import bpy
from bpy.props import BoolProperty, EnumProperty

from . import compositor


def _viewport_spaces(context):
    for window in context.window_manager.windows:
        if window.scene == context.scene:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    yield area.spaces.active


def start_preview(context):
    found = False
    for space in _viewport_spaces(context):
        space.shading.type = 'RENDERED'
        space.shading.use_compositor = context.scene.ascii_render.preview_mode
        if context.scene.ascii_render.preview_mode == 'CAMERA' and context.scene.camera:
            space.region_3d.view_perspective = 'CAMERA'
        found = True
    return found


class ASCII_OT_setup(bpy.types.Operator):
    bl_idname = 'ascii_render.setup'
    bl_label = 'Add ASCII Render'
    bl_description = 'Add ASCII before the scene compositor output and start live preview'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            compositor.install(context.scene)
            start_preview(context)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'ASCII Render added. F12 renders a frame; Ctrl+F12 renders animation.')
        return {'FINISHED'}


class ASCII_OT_remove(bpy.types.Operator):
    bl_idname = 'ascii_render.remove'
    bl_label = 'Remove ASCII Effect'
    bl_description = 'Remove the ASCII node and reconnect its original image source'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        compositor.remove(context.scene)
        return {'FINISHED'}


class ASCII_OT_preview(bpy.types.Operator):
    bl_idname = 'ascii_render.preview'
    bl_label = 'Live Preview'
    bl_description = 'Switch 3D views to Rendered mode and show ASCII compositing'

    def execute(self, context):
        if context.scene.ascii_render.preview_mode == 'CAMERA' and context.scene.camera is None:
            self.report({'WARNING'}, 'Add a camera or choose Whole Viewport')
            return {'CANCELLED'}
        if not start_preview(context):
            self.report({'WARNING'}, 'Open a 3D Viewport to use live preview')
            return {'CANCELLED'}
        return {'FINISHED'}


class ASCII_OT_stop_preview(bpy.types.Operator):
    bl_idname = 'ascii_render.stop_preview'
    bl_label = 'Hide Preview'
    bl_description = 'Disable viewport compositing; final renders still use ASCII'

    def execute(self, context):
        for space in _viewport_spaces(context):
            space.shading.use_compositor = 'DISABLED'
        return {'FINISHED'}


PRESETS = {
    'TERMINAL': dict(color_mode='MONO', foreground=(0.15, 1.0, 0.30, 1),
        background=(0.002, 0.006, 0.003, 1), columns=120, contrast=1.15,
        gamma=1.0, exposure=0.0, invert=False, character_set='CLASSIC', contours=True),
    'PAPER': dict(color_mode='MONO', foreground=(0.015, 0.012, 0.009, 1),
        background=(0.95, 0.91, 0.82, 1), columns=140, contrast=1.15,
        gamma=1.0, exposure=0.0, invert=True, character_set='DETAILED', contours=True),
    'COLOR': dict(color_mode='COLOR', background=(0.003, 0.003, 0.006, 1),
        columns=140, contrast=1.15, gamma=1.0, exposure=0.3, invert=False,
        character_set='DETAILED', color_gain=2.0, contours=True),
    'COARSE': dict(color_mode='MONO', foreground=(0.85, 0.93, 1.0, 1),
        background=(0.004, 0.007, 0.012, 1), columns=72, contrast=1.5,
        gamma=1.0, exposure=0.0, invert=False, character_set='MINIMAL', contours=False),
}


class ASCII_OT_preset(bpy.types.Operator):
    bl_idname = 'ascii_render.preset'
    bl_label = 'Apply ASCII Preset'
    bl_description = 'Apply a ready-made ASCII style'
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(items=[('TERMINAL', 'Terminal', ''), ('PAPER', 'Paper', ''),
                               ('COLOR', 'Color', ''), ('COARSE', 'Coarse', '')])

    def execute(self, context):
        settings = context.scene.ascii_render
        for name, value in PRESETS[self.preset].items():
            setattr(settings, name, value)
        settings.cell_aspect = 1.5
        settings.glyph_scale = 1.0
        settings.edge_threshold = 0.18
        settings.strength = 1.0
        settings.sort_by_density = True
        settings.transparent_background = False
        settings.enabled = True
        return {'FINISHED'}


class ASCII_OT_selected(bpy.types.Operator):
    bl_idname = 'ascii_render.selected'
    bl_label = 'Set ASCII on Selected Objects'
    bl_description = 'Choose whether selected objects use ASCII or their original rendered style'
    bl_options = {'REGISTER', 'UNDO'}

    enabled: BoolProperty(default=True)

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.is_editable:
                obj.ascii_render_enabled = self.enabled
                count += 1
        self.report({'INFO'}, f'ASCII {"enabled" if self.enabled else "disabled"} for {count} object(s)')
        return {'FINISHED'}


CLASSES = (ASCII_OT_setup, ASCII_OT_remove, ASCII_OT_preview, ASCII_OT_stop_preview, ASCII_OT_preset,
           ASCII_OT_selected)
