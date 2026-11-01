import bpy

from .compositor import effect_node


def _section(layout, identifier, title, *, closed=False):
    header, body = layout.panel(identifier, default_closed=closed)
    header.label(text=title)
    return body


def draw_panel(layout, context):
    scene = context.scene
    settings = scene.ascii_render
    layout.use_property_split = True
    layout.use_property_decorate = True
    if effect_node(scene) is None:
        layout.label(text='Render your scene as ASCII art.', icon='FONT_DATA')
        layout.operator('ascii_render.setup', icon='ADD')
        layout.label(text='F12: frame  ·  Ctrl+F12: animation')
        return

    layout.prop(settings, 'enabled')
    layout.prop(settings, 'preview_in_viewport')
    if settings.preview_in_viewport:
        layout.prop(settings, 'preview_mode')
        space = context.space_data
        if space.type == 'VIEW_3D' and space.shading.type not in {'RENDERED', 'MATERIAL'}:
            layout.label(text='Use Rendered or Material Preview.', icon='INFO')
        elif space.type != 'VIEW_3D':
            layout.label(text='Preview needs Rendered / Material Preview.', icon='INFO')
        if settings.preview_mode == 'CAMERA':
            layout.label(text='Enter camera view with Numpad 0.', icon='INFO')
    if not scene.render.use_compositing:
        layout.label(text='Render compositing is disabled.', icon='ERROR')
        layout.prop(scene.render, 'use_compositing', text='Use Compositing')
    for presets in ((('TERMINAL', 'Terminal'), ('PAPER', 'Paper')),
                    (('COLOR', 'Color'), ('COARSE', 'Coarse'))):
        row = layout.row(align=True)
        for key, label in presets:
            row.operator('ascii_render.preset', text=label).preset = key

    layout.prop(settings, 'match_mode', expand=True)
    box = _section(layout, 'ascii_characters', 'Characters & Grid')
    if box:
        box.active = settings.enabled
        box.prop(settings, 'grid_mode')
        box.prop(settings, 'columns' if settings.grid_mode == 'COLUMNS' else 'cell_pixels')
        if settings.match_mode == 'SMART':
            box.label(text='Smart cell width: at least 8 input pixels.', icon='INFO')
        box.prop(settings, 'cell_aspect')
        box.prop(settings, 'glyph_scale')
        box.prop(settings, 'character_set')
        if settings.character_set == 'CUSTOM':
            box.prop(settings, 'custom_characters')
            if any(not 32 <= ord(c) <= 126 for c in settings.custom_characters):
                box.label(text='Use printable ASCII (32–126).', icon='INFO')
            if not any(32 <= ord(c) <= 126 for c in settings.custom_characters):
                box.label(text='Empty ramp: Classic characters are used.', icon='INFO')
        row = box.row()
        row.active = settings.match_mode == 'CLASSIC'
        row.prop(settings, 'sort_by_density')
        if settings.match_mode == 'SMART':
            box.label(text='Smart searches in ink-density order.', icon='INFO')
            box.prop(settings, 'shape_strength', slider=True)
            box.prop(settings, 'scale_strength', slider=True)
            scales = box.column(align=True)
            scales.active = settings.scale_strength > 0
            scales.prop(settings, 'min_scale')
            scales.prop(settings, 'max_scale')

    box = _section(layout, 'ascii_color', 'Color')
    if box:
        box.active = settings.enabled
        box.prop(settings, 'color_mode')
        if settings.color_mode == 'MONO':
            box.prop(settings, 'foreground')
        else:
            box.prop(settings, 'color_gain', text='Brightness')
            if settings.match_mode == 'SMART':
                box.prop(settings, 'color_source')
                box.prop(settings, 'saturation')
                if settings.color_source == 'DIFFUSE':
                    if scene.render.engine == 'CYCLES':
                        box.label(text='Cycles Rendered: Combined color.', icon='INFO')
                        box.label(text='F12: Diffuse Color.')
                    box.label(text='Diffuse Color excludes emission.', icon='INFO')
        if settings.match_mode == 'SMART':
            box.prop(settings, 'min_contrast')
        background = box.column()
        reference = settings.transparent_background and settings.match_mode == 'SMART'
        background.active = not settings.transparent_background or reference
        background.prop(settings, 'background', text='Contrast Reference' if reference else 'Background')
        box.prop(settings, 'transparent_background', text='Transparent')
        if settings.transparent_background and settings.match_mode == 'SMART':
            box.label(text='Contrast uses Background as reference.', icon='INFO')

    box = _section(layout, 'ascii_tone', 'Tone & Contours', closed=True)
    if box:
        box.active = settings.enabled
        if settings.match_mode == 'SMART':
            box.prop(settings, 'adaptive_strength', slider=True)
            box.prop(settings, 'adaptive_floor')
        box.prop(settings, 'exposure', text='Exposure')
        for name in ('contrast', 'gamma', 'invert'):
            box.prop(settings, name)
        box.prop(settings, 'contours')
        row = box.row()
        row.active = settings.contours
        row.prop(settings, 'edge_threshold')

    box = _section(layout, 'ascii_selection', 'Objects, World & Edges', closed=True)
    if box:
        box.active = settings.enabled
        if context.object:
            row = box.row()
            row.enabled = context.object.is_editable
            row.use_property_split = False
            row.prop(context.object, 'ascii_render_enabled', text='Use ASCII on Active Object')
        row = box.row(align=True)
        row.operator('ascii_render.selected', text='Include Selected').enabled = True
        row.operator('ascii_render.selected', text='Exclude Selected').enabled = False
        box.prop(settings, 'world_mode', text='World')
        box.prop(settings, 'remove_original_edge')
        if settings.remove_original_edge:
            box.prop(settings, 'edge_mask_threshold')
        from .coverage import needs_mask
        if needs_mask(scene) or settings.match_mode == 'SMART':
            box.prop_search(settings, 'mask_view_layer', scene, 'view_layers', text='Pass Layer')
        if scene.render.engine == 'CYCLES':
            box.label(text='Cycles Rendered: masks need F12.', icon='INFO')
            box.label(text='Use F12 or EEVEE to check selection.')
    layout.prop(settings, 'strength', slider=True)
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


class ASCII_PT_object(bpy.types.Panel):
    bl_label = 'ASCII Render'
    bl_idname = 'ASCII_PT_object'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        self.layout.enabled = context.object.is_editable
        self.layout.prop(context.object, 'ascii_render_enabled')


CLASSES += (ASCII_PT_object,)
