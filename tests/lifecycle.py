"""Test scene integration and lifecycle without rendering."""
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor

ascii_render.register()
scene = bpy.context.scene
tree = bpy.data.node_groups.new('Existing compositor', 'CompositorNodeTree')
tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
scene.compositing_node_group = tree
source = tree.nodes.new('CompositorNodeRLayers')
existing = tree.nodes.new('CompositorNodeExposure')
tree.links.new(source.outputs['Image'], existing.inputs['Image'])
output = tree.nodes.new('NodeGroupOutput')
viewer = tree.nodes.new('CompositorNodeViewer')
tree.links.new(existing.outputs[0], output.inputs['Image'])
tree.links.new(existing.outputs[0], viewer.inputs[0])
existing.inputs['Exposure'].default_value = 0.75
existing.inputs['Exposure'].driver_add('default_value').driver.expression = '0.75'
original_nodes = set(tree.nodes)
node = compositor.install(scene)
assert len(tree.nodes) == len(original_nodes) + 1
assert node.inputs['Image'].links[0].from_node == existing
assert viewer.inputs[0].links[0].from_node == node
assert output.inputs[0].links[0].from_node == node

settings = scene.ascii_render
settings.character_set = 'CUSTOM'
settings.sort_by_density = False
settings.custom_characters = '@ .'
assert node.node_tree.nodes['Glyph atlas'].image['ascii_characters'] == '@ .-|/\\'
assert node.node_tree.nodes['Fill glyph index'].inputs[1].default_value == 3
assert node.node_tree.nodes['Last fill index'].inputs[1].default_value == 2
assert node.node_tree.nodes['Atlas U'].inputs[1].default_value == 7
settings.custom_characters = 'Я🙂'
assert node.node_tree.nodes['Glyph atlas'].image['ascii_characters'].startswith(' .:-=')
settings.custom_characters = '@'
assert node.node_tree.nodes['Atlas U'].inputs[1].default_value == 5
settings.character_set = 'DETAILED'
settings.columns = 173
scene.frame_set(1)
assert node.inputs['Columns'].default_value == 173
assert node.node_tree.nodes['Glyph atlas'].image.packed_file is not None

# Disabling the extension freezes the current native graph, then enabling it
# again restores drivers without accumulating duplicate variables.
ascii_render.unregister()
assert node.inputs['Columns'].default_value == 173
assert len(tree.animation_data.drivers) == 1
ascii_render.register()
scene.frame_set(2)
node = compositor.effect_node(scene)
assert node.inputs['Columns'].default_value == 173
assert all(len(f.driver.variables) == 1 for f in tree.animation_data.drivers if f.driver.expression == 'value')
compositor.remove(scene)
assert set(tree.nodes) == original_nodes
assert output.inputs['Image'].links[0].from_node == existing
assert viewer.inputs[0].links[0].from_node == existing
assert len(tree.animation_data.drivers) == 1
assert tree.animation_data.drivers[0].driver.expression == '0.75'

# Installing on a shared compositor must leave the other scene untouched.
other = bpy.data.scenes.new('Shared compositor scene')
other.compositing_node_group = tree
compositor.install(scene)
assert other.compositing_node_group == tree
assert compositor.effect_node(other) is None
assert scene.compositing_node_group != tree
compositor.remove(scene)

# Test the public setup operator, panel registration and preview selectors.
node = compositor.install(scene)
assert bpy.ops.ascii_render.setup() == {'FINISHED'}
assert bpy.types.ASCII_PT_viewport.bl_category == 'ASCII'
assert bpy.ops.ascii_render.preset(preset='PAPER') == {'FINISHED'}
assert scene.ascii_render.invert
assert bpy.ops.ascii_render.preset(preset='COLOR') == {'FINISHED'}
assert scene.ascii_render.color_mode == 'COLOR'
compositor.remove(scene)
ascii_render.unregister()
print('ALL_LIFECYCLE_TESTS_PASSED')
