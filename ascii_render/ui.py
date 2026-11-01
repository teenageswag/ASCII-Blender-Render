import bpy

from .compositor import effect_node


def draw_panel(layout, context):
    scene = context.scene
    settings = scene.ascii_render
    layout.use_property_split = True
    layout.use_property_decorate = False
    if effect_node(scene) is None:
        layout.label(text='Render your scene as ASCII art.', icon='FONT_DATA')
        layout.operator('ascii_render.setup', icon='ADD')
        layout.label(text='Works with F12 and Ctrl+F12.')
        return

    layout.prop(settings, 'enabled')
    row = layout.row(align=True)
    row.operator('ascii_render.preview', icon='SHADING_RENDERED')
    row.operator('ascii_render.stop_preview', text='', icon='HIDE_ON')
    layout.prop(settings, 'preview_mode')
    if not scene.render.use_compositing:
        box = layout.box()
        box.label(text='Render compositing is disabled.', icon='ERROR')
        box.prop(scene.render, 'use_compositing', text='Use Compositing')
    row = layout.row(align=True)
    for key, label in (('TERMINAL', 'Terminal'), ('PAPER', 'Paper'), ('COLOR', 'Color'), ('COARSE', 'Coarse')):
        row.operator('ascii_render.preset', text=label).preset = key

    body = layout.column()
    body.active = settings.enabled
    box = body.box()
    box.label(text='Characters', icon='FONT_DATA')
    box.prop(settings, 'columns')
    box.prop(settings, 'cell_aspect')
    box.prop(settings, 'glyph_scale')
    box.prop(settings, 'character_set')
    if settings.character_set == 'CUSTOM':
        box.prop(settings, 'custom_characters')
        if any(not 32 <= ord(c) <= 126 for c in settings.custom_characters):
            box.label(text='Only printable ASCII is used (32–126).', icon='INFO')
        if not any(32 <= ord(c) <= 126 for c in settings.custom_characters):
            box.label(text='Empty ramp: Classic is used.', icon='INFO')
    box.prop(settings, 'sort_by_density')

    box = body.box()
    box.label(text='Color', icon='COLOR')
    box.prop(settings, 'color_mode')
    if settings.color_mode == 'MONO':
        box.prop(settings, 'foreground')
    else:
        box.prop(settings, 'color_gain', text='Brightness')
    background = box.column()
    background.active = not settings.transparent_background
    background.prop(settings, 'background')
    box.prop(settings, 'transparent_background', text='Transparent')

    box = body.box()
    box.label(text='Tone', icon='IMAGE_RGB')
    box.prop(settings, 'exposure', text='Exposure')
    for name in ('contrast', 'gamma', 'invert'):
        box.prop(settings, name)
    box = body.box()
    box.prop(settings, 'contours')
    row = box.row()
    row.active = settings.contours
    row.prop(settings, 'edge_threshold')
    body.prop(settings, 'strength', slider=True)
    layout.separator()
    layout.label(text='F12: frame  ·  Ctrl+F12: animation')
    layout.operator('ascii_render.remove', icon='X')


class ASCII_PT_render(bpy.types.Panel):
    bl_label = 'ASCII Render'
    bl_idname = 'ASCII_PT_render'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'

    def draw(self, context):
        draw_panel(self.layout, context)


class ASCII_PT_viewport(bpy.types.Panel):
    bl_label = 'ASCII Render'
    bl_idname = 'ASCII_PT_viewport'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ASCII'

    def draw(self, context):
        draw_panel(self.layout, context)


CLASSES = (ASCII_PT_render, ASCII_PT_viewport)
