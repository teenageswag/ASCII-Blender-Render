"""ASCII Render for Blender 5.2 LTS."""

bl_info = {
    'name': 'ASCII Render',
    'author': 'ASCII Render contributors',
    'version': (1, 0, 0),
    'blender': (5, 2, 0),
    'location': 'Render Properties > ASCII Render; 3D View > Sidebar > ASCII',
    'description': 'Live ASCII compositing, still renders and animation',
    'category': 'Render',
}

import bpy
from bpy.props import PointerProperty

from . import compositor, operators, properties, ui

CLASSES = properties.CLASSES + operators.CLASSES + ui.CLASSES


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ascii_render = PointerProperty(type=properties.ASCII_RenderSettings)
    for scene in bpy.data.scenes:
        node = compositor.effect_node(scene)
        if node:
            compositor.bind_controls(node, scene)


def unregister():
    # Freeze before removing the Scene property, which invalidates its drivers.
    for scene in bpy.data.scenes:
        node = compositor.effect_node(scene)
        if node:
            compositor.freeze_controls(node)
    if hasattr(bpy.types.Scene, 'ascii_render'):
        del bpy.types.Scene.ascii_render
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
