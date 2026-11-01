import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty

from . import compositor


def _refresh_characters(self, context):
    compositor.refresh_atlas(self.id_data)


class ASCII_RenderSettings(bpy.types.PropertyGroup):
    enabled: BoolProperty(name='Enable ASCII', default=True,
        description='Apply ASCII to the scene compositor output')
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
    strength: FloatProperty(name='Strength', default=1, min=0, max=1, subtype='FACTOR',
        description='Mix the original image with ASCII')
    preview_mode: EnumProperty(name='Preview Area', default='CAMERA', options=set(),
        items=[('CAMERA', 'Camera', 'Preview compositing in camera view'),
               ('ALWAYS', 'Whole Viewport', 'Preview compositing in the entire rendered viewport')])


CLASSES = (ASCII_RenderSettings,)
