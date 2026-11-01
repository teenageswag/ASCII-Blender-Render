"""Upgrade a saved 1.0 demo without losing its original compositor connection."""
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor

ascii_render.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'build/verification/ascii_demo.blend'))
scene = bpy.context.scene
node = compositor.effect_node(scene)
assert node.node_tree['ascii_schema'] == compositor.SCHEMA
assert node.inputs['Image'].is_linked
assert node.inputs['Image'].links[0].from_node.type == 'R_LAYERS'
assert node.inputs['Columns'].is_linked is False
assert compositor.install(scene) == node
assert node.inputs.get('World Mode') is not None
assert node.inputs.get('Object Mask') is not None
print('MIGRATION_PASSED')
