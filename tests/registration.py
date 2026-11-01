"""Registration must survive repeated calls, failed enables and a new package namespace."""
from pathlib import Path
import importlib.util
import sys
import types
from unittest.mock import patch

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor

ascii_render.register()
scene = bpy.context.scene
scene.ascii_render.columns = 157
node = compositor.install(scene)
scene.frame_set(1)
assert node.inputs['Columns'].default_value == 157

# Reproduce the exact "already registered as a subclass" report.
ascii_render.register()
assert scene.ascii_render.columns == 157
assert node.inputs['Columns'].default_value == 157
assert bpy.types.PropertyGroup.bl_rna_get_subclass_py('ASCII_RenderSettings') is ascii_render.properties.ASCII_RenderSettings

ascii_render.unregister()
ascii_render.unregister()
assert not hasattr(bpy.types.Scene, 'ascii_render')

# Blender can leave classes from an enable that stopped before RNA properties
# or handlers were installed. A subsequent enable must recover.
bpy.utils.register_class(ascii_render.properties.ASCII_RenderSettings)
ascii_render.register()
assert scene.ascii_render.columns == 157
ascii_render.unregister()

# A legacy add-on and a Blender Extension have different Python namespaces but
# the same RNA names. Exercise that collision with a second import of the code.
ascii_render.register()
parent_name = 'registration_test'
parent = types.ModuleType(parent_name)
parent.__path__ = []
sys.modules[parent_name] = parent
module_name = f'{parent_name}.ascii_render'
spec = importlib.util.spec_from_file_location(
    module_name, ROOT / 'ascii_render/__init__.py',
    submodule_search_locations=[str(ROOT / 'ascii_render')])
other = importlib.util.module_from_spec(spec)
sys.modules[module_name] = other
spec.loader.exec_module(other)
other.register()
assert scene.ascii_render.columns == 157
scene.frame_set(2)
assert node.inputs['Columns'].default_value == 157
assert bpy.types.PropertyGroup.bl_rna_get_subclass_py('ASCII_RenderSettings') is other.properties.ASCII_RenderSettings
ascii_render.unregister()  # A stale copy must not disable the replacement.
assert hasattr(bpy.types.Scene, 'ascii_render')
for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.render_pre,
                 bpy.app.handlers.depsgraph_update_post):
    callbacks = [f for f in handlers if '.ascii_render.coverage' in f.__module__
                 or f.__module__ == 'ascii_render.coverage']
    assert len(callbacks) == 1, [(f.__module__, f.__name__) for f in callbacks]
other.unregister()
other.unregister()

# A genuine enable error must leave no partial RNA classes behind.
original_register = bpy.utils.register_class


def fail_mid_registration(cls):
    if cls is ascii_render.ui.ASCII_PT_viewport:
        raise RuntimeError('simulated registration failure')
    return original_register(cls)


with patch.object(bpy.utils, 'register_class', side_effect=fail_mid_registration):
    try:
        ascii_render.register()
        raise AssertionError('Expected the simulated enable failure')
    except RuntimeError as exc:
        assert str(exc) == 'simulated registration failure'
assert not hasattr(bpy.types.Scene, 'ascii_render')
assert not any(ascii_render._registered_class(cls) for cls in ascii_render.CLASSES)

ascii_render.register()
scene.frame_set(3)
assert scene.ascii_render.columns == 157

# Match the add-on enable/disable operations used by Blender Preferences.
assert bpy.ops.preferences.addon_enable(module='ascii_render') == {'FINISHED'}
assert scene.ascii_render.columns == 157
assert bpy.app.timers.is_registered(ascii_render._initialize_scenes)
ascii_render._initialize_scenes()  # Simulate Blender's next UI event-loop tick.
scene.frame_set(4)
assert node.inputs['Columns'].default_value == 157
assert bpy.ops.preferences.addon_disable(module='ascii_render') == {'FINISHED'}
assert not bpy.app.timers.is_registered(ascii_render._initialize_scenes)
ascii_render.unregister()

foreign = type('ASCII_RenderSettings', (bpy.types.PropertyGroup,),
               {'__module__': 'another_addon.properties'})
bpy.utils.register_class(foreign)
try:
    ascii_render.register()
    raise AssertionError('Do not unregister another add-on with a colliding name')
except RuntimeError as exc:
    assert 'another_addon.properties' in str(exc)
assert bpy.types.PropertyGroup.bl_rna_get_subclass_py('ASCII_RenderSettings') is foreign
bpy.utils.unregister_class(foreign)
print('ALL_REGISTRATION_TESTS_PASSED')
