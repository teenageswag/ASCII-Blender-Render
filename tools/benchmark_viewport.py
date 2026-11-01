"""Isolated UI benchmark; launch at 1920x1080, never in the user's scene.

--baseline imports build/baseline/ascii_render (staged 1.1.1 source).
Each measured frame changes the view and redraws/swaps the actual GPU viewport.
This includes EEVEE and UI costs, not just compositor GPU execution time.
"""
from pathlib import Path
import json
import statistics
import sys
import time

import bpy
from mathutils import Quaternion

ROOT = Path(__file__).resolve().parents[1]
baseline = '--baseline' in sys.argv
if baseline and not (ROOT / 'build/baseline/ascii_render/__init__.py').exists():
    import zipfile
    with zipfile.ZipFile(ROOT / 'releases/ascii_render-1.1.1.zip') as archive:
        archive.extractall(ROOT / 'build/baseline/ascii_render')
sys.path.insert(0, str(ROOT / 'build/baseline' if baseline else ROOT))
import ascii_render
from ascii_render import compositor
if baseline:
    assert ascii_render.bl_info['version'] == (1, 1, 1), 'Benchmark baseline must be 1.1.1'

ascii_render.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'build/smart/benchmark.blend'))
scene = bpy.context.scene
scene.compositing_node_group = None
node = compositor.install(scene)
scene.render.engine = 'BLENDER_EEVEE'


def run():
    import gpu
    window = bpy.context.window_manager.windows[0]
    properties = next((a for a in window.screen.areas if a.type == 'PROPERTIES'), None)
    if properties:
        properties.spaces.active.context = 'RENDER'
    # Draw the actual shared panel once as a UI/API smoke check.
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)
    bpy.ops.wm.window_fullscreen_toggle()
    area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    with bpy.context.temp_override(window=window, area=area):
        bpy.ops.screen.screen_full_area(use_hide_panels=True)
    area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    space = area.spaces.active
    space.show_region_ui = False
    space.show_region_toolbar = False
    space.show_region_header = False
    space.show_region_tool_header = False
    space.overlay.show_overlays = False
    space.shading.type = 'RENDERED'
    space.shading.use_compositor = 'ALWAYS'
    space.region_3d.view_perspective = 'PERSP'
    space.region_3d.view_location = (0, 0, 1)
    space.region_3d.view_distance = 8
    space.region_3d.view_rotation = scene.camera.rotation_euler.to_quaternion()
    bpy.app.timers.register(lambda: measure(window, area, space), first_interval=1)


def measure(window, area, space):
    import gpu
    results = dict(version=ascii_render.bl_info['version'], gpu=gpu.platform.renderer_get(),
                   nodes=len(node.node_tree.nodes), frames=30, measurements={})
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)
        for mode in (('CLASSIC',) if baseline else ('CLASSIC', 'SMART')):
            if not baseline:
                scene.ascii_render.match_mode = mode
            times = []
            for frame in range(38):
                space.region_3d.view_rotation = Quaternion((0, 0, 1), 0.002) @ space.region_3d.view_rotation
                area.tag_redraw()
                start = time.perf_counter()
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                elapsed = time.perf_counter() - start
                if frame >= 8:
                    times.append(elapsed)
            results['measurements'][mode] = dict(median_ms=statistics.median(times) * 1000,
                fps=1 / statistics.mean(times), min_ms=min(times) * 1000, max_ms=max(times) * 1000)
        if not baseline:
            try:
                results['viewport_inputs'] = probe_inputs(area, region)
            except Exception as exc:
                results['probe_error'] = repr(exc)
    results['region_pixels'] = [region.width, region.height]
    target = ROOT / ('build/benchmark-before.json' if baseline else 'build/benchmark-after.json')
    target.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('VIEWPORT_BENCHMARK', json.dumps(results), flush=True)
    bpy.ops.wm.quit_blender()


def probe_inputs(area, region):
    """Read an Image Info diagnostic through the actual viewport framebuffer."""
    from ascii_render import coverage
    settings = scene.ascii_render
    settings.color_source = 'DIFFUSE'
    settings.match_mode = 'SMART'
    coverage.sync_scene(scene)
    tree = scene.compositing_node_group
    output = next(n for n in tree.nodes if n.type == 'GROUP_OUTPUT' and n.is_active_output)
    original = output.inputs['Image'].links[0].from_socket
    source = next(n for n in tree.nodes if n.get(coverage.OWNED) == 'source')
    scene.view_layers[0].use_pass_normal = True
    scene.view_layers[0].use_pass_z = True
    scene.view_layers[0].use_pass_object_index = True
    transform = scene.view_settings.view_transform
    scene.view_settings.view_transform = 'Raw'
    results = {}
    try:
        for engine in ('BLENDER_EEVEE', 'CYCLES'):
            scene.render.engine = engine
            source.update()
            results[engine] = dict(sockets=[s.name for s in source.outputs], approximate_dimensions={})
            for name in ('Image', 'Normal', 'Depth', 'Object Index', 'Diffuse Color', coverage.AOV_NAME):
                if name not in source.outputs:
                    continue
                g = compositor.Graph(tree)
                info = g.node('CompositorNodeImageInfo', 'Viewport input probe')
                g.put(info.inputs[0], source.outputs[name])
                size = g.separate(info.outputs['Dimensions'], 'Probe size')
                encoded = g.xyz(g.math('DIVIDE', size[0], 2048), g.math('DIVIDE', size[1], 2048), 0.25)
                tree.links.new(encoded, output.inputs['Image'])
                area.tag_redraw()
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=3)
                path = ROOT / 'build/viewport-input-probe.png'
                bpy.ops.screen.screenshot(filepath=str(path))
                image = bpy.data.images.load(str(path), check_existing=False)
                offset = ((image.size[1] // 2) * image.size[0] + image.size[0] // 2) * 4
                values = image.pixels[offset:offset+4]
                bpy.data.images.remove(image)
                assert len(values) == 4 and abs(values[2] - 0.25) < 0.01, values
                results[engine]['approximate_dimensions'][name] = [round(v * 2048) for v in values[:2]]
    finally:
        tree.links.new(original, output.inputs['Image'])
        scene.view_settings.view_transform = transform
        scene.render.engine = 'BLENDER_EEVEE'
    return results


bpy.app.timers.register(run, first_interval=2)
