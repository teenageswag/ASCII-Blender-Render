"""ASCII Render for Blender 5.2 LTS."""

bl_info = {
    'name': 'ASCII Render',
    'author': 'ASCII Render contributors',
    'version': (1, 2, 1),
    'blender': (5, 2, 0),
    'location': 'Render Properties > ASCII Render; 3D View > Sidebar > ASCII',
    'description': 'Live ASCII compositing, still renders and animation',
    'category': 'Render',
}

import bpy
from bpy.props import BoolProperty, PointerProperty

# Blender reloads the package entry point on update but can keep its submodules
# cached. Stop the previous handlers before replacing their Python definitions.
if 'coverage' in locals():
    import importlib
    if ('_initialize_scenes' in locals()
            and bpy.app.timers.is_registered(_initialize_scenes)):
        bpy.app.timers.unregister(_initialize_scenes)
    coverage.unregister_handlers()
    if 'viewport' in locals():
        viewport.unregister_handlers()
    for _name in ('glyphs', 'smart', 'compositor', 'coverage', 'viewport', 'properties', 'operators', 'ui'):
        importlib.reload(importlib.import_module(f'.{_name}', __name__))

from . import compositor, coverage, operators, properties, ui, viewport

CLASSES = properties.CLASSES + operators.CLASSES + ui.CLASSES


def _registered_class(cls):
    # Cached/reimported Python classes may differ from the object actually
    # registered in Blender. PropertyGroups are not exposed via bpy.types.
    for base in (bpy.types.PropertyGroup, bpy.types.Operator, bpy.types.Panel):
        if issubclass(cls, base):
            identifier = cls.__name__
            if base is bpy.types.Operator:
                namespace, name = cls.bl_idname.split('.', 1)
                identifier = f'{namespace.upper()}_OT_{name}'
            elif base is bpy.types.Panel:
                identifier = cls.bl_idname
            return base.bl_rna_get_subclass_py(identifier, None)
    return None


def _owns_class(cls):
    parts = cls.__module__.split('.')
    return (len(parts) >= 2 and parts[-2] == 'ascii_render'
            and parts[-1] in {'properties', 'operators', 'ui'})


def _unregister_existing(*, all_copies=False):
    registered = [(_registered_class(cls), cls) for cls in CLASSES]
    if all_copies:
        for actual, _ in registered:
            if actual is not None and not _owns_class(actual):
                raise RuntimeError(
                    f'{actual.__name__} belongs to {actual.__module__}; '
                    'disable the conflicting add-on before enabling ASCII Render')
    elif not any(actual is not None and actual.__module__ == expected.__module__
                 for actual, expected in registered):
        # A second package may have taken over the RNA classes. An old copy's
        # disable must not tear down the active installation.
        return
    if bpy.app.timers.is_registered(_initialize_scenes):
        bpy.app.timers.unregister(_initialize_scenes)
    coverage.unregister_handlers(all_copies=all_copies)
    viewport.unregister_handlers(all_copies=all_copies)
    # Freeze before deleting RNA properties so the native graph remains usable.
    for scene in getattr(bpy.data, 'scenes', ()):
        node = compositor.effect_node(scene)
        if node:
            compositor.freeze_controls(node)
    if hasattr(bpy.types.Scene, 'ascii_render'):
        del bpy.types.Scene.ascii_render
    if hasattr(bpy.types.Object, 'ascii_render_enabled'):
        del bpy.types.Object.ascii_render_enabled
    for actual, expected in reversed(registered):
        if actual is not None and (all_copies or actual.__module__ == expected.__module__):
            bpy.utils.unregister_class(actual)


def _initialize_scenes():
    if (_registered_class(properties.ASCII_RenderSettings) is not properties.ASCII_RenderSettings
            or not hasattr(bpy.types.Scene, 'ascii_render')):
        return None
    for scene in bpy.data.scenes:
        node = compositor.effect_node(scene)
        if node:
            compositor.upgrade(scene)
            compositor.bind_controls(node, scene)
            coverage.sync_scene(scene)
    viewport.sync_all(loaded=True)
    return None


def register():
    _unregister_existing(all_copies=True)
    try:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.Scene.ascii_render = PointerProperty(type=properties.ASCII_RenderSettings)
        bpy.types.Object.ascii_render_enabled = BoolProperty(
            name='Use ASCII', description='Disable to keep this object in its original rendered style',
            get=properties.object_ascii_get, set=properties.object_ascii_set, options=set())
        coverage.register_handlers()
        viewport.register_handlers()
        if hasattr(bpy.data, 'scenes'):
            _initialize_scenes()
        else:
            # addon_utils.enable runs register() under RestrictBlend. Datablocks
            # can only be migrated/restored once Blender leaves that scope.
            bpy.app.timers.register(_initialize_scenes, first_interval=0)
    except Exception:
        # Blender does not automatically roll back classes from a failed enable.
        _unregister_existing()
        raise


def unregister():
    _unregister_existing()
