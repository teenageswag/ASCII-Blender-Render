"""ASCII Render for Blender 5.2 LTS."""

bl_info = {
    'name': 'ASCII Render',
    'author': 'ASCII Render contributors',
    'version': (1, 1, 0),
    'blender': (5, 2, 0),
    'location': 'Render Properties > ASCII Render; 3D View > Sidebar > ASCII',
    'description': 'Live ASCII compositing, still renders and animation',
    'category': 'Render',
}

import bpy
from bpy.props import BoolProperty, PointerProperty

from . import compositor, coverage, operators, properties, ui

CLASSES = properties.CLASSES + operators.CLASSES + ui.CLASSES


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ascii_render = PointerProperty(type=properties.ASCII_RenderSettings)
    bpy.types.Object.ascii_render_enabled = BoolProperty(
        name='Use ASCII', description='Disable to keep this object in its original rendered style',
        get=properties.object_ascii_get, set=properties.object_ascii_set, options=set())
    for scene in bpy.data.scenes:
        node = compositor.effect_node(scene)
        if node:
            compositor.upgrade(scene)
            compositor.bind_controls(node, scene)
            coverage.sync_scene(scene)
    coverage.register_handlers()


def unregister():
    coverage.unregister_handlers()
    # Freeze before removing the Scene property, which invalidates its drivers.
    for scene in bpy.data.scenes:
        node = compositor.effect_node(scene)
        if node:
            compositor.freeze_controls(node)
    if hasattr(bpy.types.Scene, 'ascii_render'):
        del bpy.types.Scene.ascii_render
    if hasattr(bpy.types.Object, 'ascii_render_enabled'):
        del bpy.types.Object.ascii_render_enabled
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
