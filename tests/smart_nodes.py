"""Numerical regression checks for descriptors, ink contrast and Classic pixels."""
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ascii_render
from ascii_render import compositor, smart

ascii_render.register()
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.render.resolution_x, scene.render.resolution_y = 96, 64
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
scene.render.compositor_device = 'CPU'
out = ROOT / 'build/smart'
out.mkdir(parents=True, exist_ok=True)

assert len({smart.descriptor(c)[0] for c in "-_' ."}) == 5
node = compositor.install(scene)
settings = scene.ascii_render
settings.character_set = 'CUSTOM'
settings.sort_by_density = False
settings.custom_characters = '@ .|/\\-'
atlas = node.node_tree.nodes['Glyph atlas'].image
descriptors, features, order = smart.descriptors_for(atlas)
data = np.array(features.pixels[:]).reshape(-1, 4)
assert np.all(np.diff(data[:, 3]) >= -1e-6), 'Smart order must use ink coverage'
assert atlas['ascii_characters'].startswith('@ .'), 'Classic must retain custom order'
assert all(i.packed_file for i in (atlas, descriptors, features, order))

# Isolate the actual native ink graph and measure its EXR output for dark,
# middle and light backgrounds, including saturated colors and the extremes.
tree = bpy.data.node_groups.new('Ink contrast regression', 'CompositorNodeTree')
tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
scene.compositing_node_group = tree
g = compositor.Graph(tree)
output = g.node('NodeGroupOutput', 'Output')
for index, (color, bg, gap) in enumerate((
    ((0.01, 0.02, 0.03), 0.02, 0.3), ((0.8, 0.8, 0.8), 0.8, 0.3),
    ((0.5, 0.5, 0.5), 0.5, 0.5), ((0.02, 0.8, 0.01), 0.5, 0.4),
)):
    source = g.mix(0, (*color, 1), (*color, 1), color=True)
    ink = smart.readable_color(g, source, (bg, bg, bg, 1), 1.5, 1, gap)
    luminance = g.luminance(ink, f'Check luminance {index}')
    g.put(output.inputs['Image'], luminance)
    path = out / f'contrast_{index}.exr'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    actual = image.pixels[0]
    bpy.data.images.remove(image)
    assert abs(actual - bg) >= gap - 1e-5, (actual, bg, gap)

before = ROOT / 'docs/images/smart-before.png'
classic = out / 'classic.png'
if before.exists() and classic.exists():
    a = bpy.data.images.load(str(before), check_existing=False)
    b = bpy.data.images.load(str(classic), check_existing=False)
    assert np.abs(np.array(a.pixels[:]) - np.array(b.pixels[:])).max() < 0.005, 'Classic appearance drifted'
    bpy.data.images.remove(a)
    bpy.data.images.remove(b)
print('ALL_SMART_NODE_TESTS_PASSED', flush=True)
