import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty

from . import compositor


def _refresh_characters(self, context):
    compositor.refresh_atlas(self.id_data)


def _refresh_mask(self, context):
    from .coverage import sync_scene
    sync_scene(self.id_data)


def object_ascii_get(obj):
    from .coverage import EXCLUDE_KEY
    return not bool(obj.get(EXCLUDE_KEY, 0))


def object_ascii_set(obj, value):
    from .coverage import EXCLUDE_KEY, sync_scene
    obj[EXCLUDE_KEY] = float(not value)
    obj.update_tag()
    for scene in obj.users_scene:
        sync_scene(scene)


class ASCII_RenderSettings(bpy.types.PropertyGroup):
    enabled: BoolProperty(name='Enable ASCII', default=True,
        description='Apply ASCII to the scene compositor output')
    match_mode: EnumProperty(name='Matching', default='CLASSIC',
        items=[('CLASSIC', 'Classic', 'Original brightness ramp and contour selection', 0),
               ('SMART', 'Smart', 'Six subcell samples, local tone and 2x3 ink-shape matching', 1)],
        update=_refresh_mask)
    adaptive_strength: FloatProperty(name='Local Adaptation', default=0.55, min=0, max=1,
        subtype='FACTOR', description='Blend global tone with mask-aware local contrast; high values can increase flicker')
    adaptive_floor: FloatProperty(name='Noise Floor', default=0.12, min=0.02, max=0.5,
        description='Minimum perceptual local range; larger values suppress noise on flat surfaces')
    shape_strength: FloatProperty(name='Shape Matching', default=0.5, min=0, max=1,
        subtype='FACTOR', description='Compare six ink-coverage features for five candidates ordered by ink density')
    min_scale: FloatProperty(name='Minimum Scale', default=0.65, min=0.25, max=1,
        description='Smallest Smart glyph relative to its cell; effective limits are sorted automatically')
    max_scale: FloatProperty(name='Maximum Scale', default=1, min=0.25, max=1,
        description='Largest Smart glyph; always clipped to its cell')
    scale_strength: FloatProperty(name='Scale Variation', default=0.6, min=0, max=1,
        subtype='FACTOR', description='Vary Smart glyph size with cell tone and edge importance')
    color_source: EnumProperty(name='Color Source', default='COMBINED', options=set(),
        items=[('COMBINED', 'Combined', 'Shaded scene color including emission'),
               ('DIFFUSE', 'Diffuse Color', 'Unlit diffuse color; falls back to Combined in Cycles viewport; excludes emission')],
        update=_refresh_mask)
    saturation: FloatProperty(name='Saturation', default=1, min=0, max=2,
        description='Saturation of Smart scene-colored glyphs')
    min_contrast: FloatProperty(name='Minimum Contrast', default=0.18, min=0, max=0.5,
        description='Minimum linear-luminance gap between opaque Smart ink and Background at full Strength; transparency uses this reference color')
    remove_original_edge: BoolProperty(name='Remove Original Edge', default=True,
        description='Fully replace pixels covered by ASCII surfaces; removes native antialiasing fringe and hardens the silhouette at full Strength')
    edge_mask_threshold: FloatProperty(name='Edge Coverage Threshold', default=0.01,
        min=0.001, max=0.1, precision=3,
        description='Minimum surface coverage to replace completely; lower values remove finer filtered fringes without expanding into neighboring objects')
    columns: IntProperty(name='Columns', default=120, min=8, max=600, soft_max=240,
        description='Number of characters across the image; more columns means smaller characters')
    cell_aspect: FloatProperty(name='Cell Aspect', default=1.5, min=0.5, max=3.0,
        description='Cell height divided by cell width')
    glyph_scale: FloatProperty(name='Glyph Scale', default=1.0, min=0.25, max=1.5,
        description='Size of each glyph inside its cell')
    character_set: EnumProperty(name='Character Set', default='CLASSIC', options=set(),
        items=[('CLASSIC', 'Classic', 'Ten familiar ASCII characters'),
               ('DETAILED', 'Detailed', 'A long ramp of letters, digits and punctuation'),
               ('MINIMAL', 'Minimal', 'Six characters'),
               ('BLOCKS', 'Dots & Circles', 'Sparse round characters'),
               ('CUSTOM', 'Custom', 'Your own printable ASCII character ramp')],
        update=_refresh_characters)
    custom_characters: StringProperty(name='Characters', default=' .:-=+*#%@', maxlen=128,
        options=set(), description='Printable ASCII only (32–126); include a leading space for empty shadows',
        update=_refresh_characters)
    sort_by_density: BoolProperty(name='Sort by Ink Density', default=True, options=set(),
        description='Order glyphs from least to most filled; disable to use your exact character order',
        update=_refresh_characters)
    color_mode: EnumProperty(name='Color Mode', default='MONO',
        items=[('MONO', 'Monochrome', 'One foreground color', 0),
               ('COLOR', 'Scene Colors', 'Use the average scene color in each cell', 1)])
    foreground: FloatVectorProperty(name='Foreground', subtype='COLOR', size=4,
        default=(0.82, 1.0, 0.88, 1.0), min=0, max=1,
        description='Color of monochrome glyphs (alpha is controlled by Transparent Background)')
    background: FloatVectorProperty(name='Background', subtype='COLOR', size=4,
        default=(0.004, 0.007, 0.009, 1.0), min=0, max=1,
        description='Background color (alpha is controlled by Transparent Background)')
    color_gain: FloatProperty(name='Color Brightness', default=1.8, min=0.05, max=10, soft_max=4,
        description='Brightness multiplier for scene-colored glyphs')
    exposure: FloatProperty(name='Density Exposure', default=0, min=-10, max=10, soft_min=-4, soft_max=4,
        description='Exposure in stops used for choosing glyph density')
    contrast: FloatProperty(name='Contrast', default=1.15, min=0, max=5, soft_max=3,
        description='Contrast of the glyph density ramp')
    gamma: FloatProperty(name='Gamma', default=1.0, min=0.1, max=5, soft_max=3,
        description='Midtone adjustment of the glyph density ramp')
    invert: BoolProperty(name='Invert Density', default=False,
        description='Use dense glyphs in shadows and sparse glyphs in highlights')
    contours: BoolProperty(name='Contours', default=True,
        description='Use directional line characters along image edges')
    edge_threshold: FloatProperty(name='Edge Threshold', default=0.18, min=0.005, max=2.0,
        soft_max=0.7, precision=3,
        description='Minimum brightness gradient for a contour; lower values show more edges')
    transparent_background: BoolProperty(name='Transparent Background', default=False,
        description='Output only glyphs over transparency instead of a solid background')
    world_mode: EnumProperty(name='World Background', default='ASCII', options=set(),
        items=[('ASCII', 'ASCII', 'Convert the world background to ASCII too', 0),
               ('ORIGINAL', 'Original', 'Keep the original world or compositor background', 1),
               ('SOLID', 'Solid Color', 'Replace the world with the ASCII background color', 2),
               ('TRANSPARENT', 'Transparent', 'Remove the world background', 3)],
        update=_refresh_mask)
    mask_view_layer: StringProperty(name='Mask View Layer', default='', options=set(),
        description='View layer supplying object and world coverage; empty selects the main Render Layers source',
        update=_refresh_mask)
    strength: FloatProperty(name='Strength', default=1, min=0, max=1, subtype='FACTOR',
        description='Mix the original image with ASCII')
    preview_mode: EnumProperty(name='Preview Area', default='CAMERA', options=set(),
        items=[('CAMERA', 'Camera', 'Preview compositing in camera view'),
               ('ALWAYS', 'Whole Viewport', 'Preview compositing in the entire rendered viewport')])


CLASSES = (ASCII_RenderSettings,)
