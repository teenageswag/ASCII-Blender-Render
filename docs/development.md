# Development

The extension lives in **ascii_render/**. It targets Blender 5.2's compositor API:
scene-level compositing node groups, modern math/mix nodes and image-coordinate nodes.

## Build

Run **python tools/build.py** with Python 3.11 or newer.
The version comes from **ascii_render/blender_manifest.toml**.
The script creates an installable ZIP in **dist/**.
The copy in **releases/** is the downloadable package committed with this release.

Validate the archive with Blender:

~~~sh
blender --background --factory-startup --command extension validate dist/ascii_render-1.2.1.zip
~~~

## Checks

Run from the repository root:

~~~sh
blender --background --factory-startup --python-exit-code 1 --python tests/render_smoke.py
blender --background --factory-startup --python-exit-code 1 --python tests/selective_render.py
blender --background --factory-startup --python-exit-code 1 --python tests/lifecycle.py
blender --background --factory-startup --python-exit-code 1 --python tests/gpu_smoke.py
blender --background --factory-startup --python-exit-code 1 --python tests/migration.py
blender --background --factory-startup --python-exit-code 1 --python tests/registration.py
blender --background --factory-startup --python-exit-code 1 --python tests/upgrade_registration.py
~~~

- **render_smoke:** ordinary renders, color, contours, custom characters, transparency and a three-frame animation.
- **selective_render:** shared materials, native excluded objects, world preservation/replacement, EEVEE and cleanup. Pixel comparisons use a 32-bit EXR mask so PNG rounding cannot turn antialiased edge pixels into fully covered pixels.
- **lifecycle:** existing compositor connections, drivers, presets, shared node trees and extension re-registration.
- **gpu_smoke:** GPU compositing and reloading the demo produced by render_smoke.
- **migration:** compositor upgrade and preservation of the source connection in a saved demo. To check a 1.0 project, place that project at build/verification/ascii_demo.blend before running it.
- **registration:** repeated/partial registration, rollback on failure, namespace collisions, Preferences enable/disable and deferred scene initialization.
- **upgrade_registration:** upgrade the shipped 1.1.1 archive to the current code without restarting Blender or clearing Python's module cache.

## Selective rendering

One color AOV, **ASCII_RenderMask**, carries exclusion in red and surface coverage in green.
Three tagged nodes are added to local materials: Object Attribute, Combine XYZ and AOV Output.
They leave the existing surface shader connections intact.
Objects can share a material and still have different ASCII toggles.

Mask setup runs when filtering changes, after loading a scene, before rendering, and after new object/material assignments in the UI.
Numeric image controls use native drivers; they do not need per-frame Python updates.
Remove ASCII Effect reconnects the original compositor output and removes owned mask data when no other scene uses it.

## Reproduce the images

**tests/selective_render.py** creates the cube/cylinder scene in build/selective.
**tests/render_smoke.py** creates the Suzanne/torus examples in build/verification.
**tools/export_example.py** saves the selective scene to examples/selective.blend with a relative output path.
**tools/ui_selective_preview.py** opens an isolated EEVEE preview for visual checks.

The example contains procedural materials and a packed glyph atlas; it has no external texture dependencies.

## 1.2.0 verification

See [validation-1.2.0.md](validation-1.2.0.md) for measured 1080p viewport timings,
pass availability and the native input-size diagnostic.

~~~sh
blender --background --factory-startup --python-exit-code 1 --python tests/smart_render.py
blender --background --factory-startup --python-exit-code 1 --python tests/smart_nodes.py
blender --background --factory-startup --python-exit-code 1 --python tests/edge_render.py
blender --background --factory-startup --python-exit-code 1 --python tests/viewport_preview.py
~~~

Smart stores six features per glyph in two packed data images, plus a 256-entry
coverage-to-rank lookup. Repeated Custom characters are deduplicated only for Smart
search. Image creation and density sorting run only on atlas changes. The graph
compares five coverage-neighbor candidates, independent of ramp length/order.
A boolean Group Input wired directly to modern Switch nodes allows Blender 5.2's
[static lazy evaluation](https://projects.blender.org/blender/blender/commit/cdb3b4455ea0fa177d3b478a2d22ea539c63e5c1)
to omit Smart analysis in Classic; a float condition or a Mix does not do that.

Preview bookmarks live on Screen ID properties because SpaceView3D does not support
custom ID properties. RNA paths survive serialization; live pointers track area
reordering. Split geometry and copied Screen bookmarks preserve parent state.
Per-space backups on the Scene survive deletion of temporary fullscreen Screens;
these are removed along with Screen bookmarks when preview is restored.
The watcher observes topology only, every 0.75 seconds while preview is active.
No Python image processing or redraw/depsgraph preview handler is installed.

To repeat the UI benchmark after smart_render creates build/smart/benchmark.blend:

~~~sh
blender --factory-startup --window-geometry 0 0 1920 1080 --python tools/benchmark_viewport.py -- --baseline
blender --factory-startup --window-geometry 0 0 1920 1080 --python tools/benchmark_viewport.py
~~~

These commands launch isolated Blender instances and quit automatically. The
baseline is staged from releases/ascii_render-1.1.1.zip. JSON results go to build/.
The current-code run also draws the Render Properties panel and probes Image Info
through a Raw-view diagnostic screenshot in the actual free viewport.

`blender --factory-startup --python tests/viewport_ui.py` checks real main windows,
independent scenes, workspaces and fullscreen transitions in an isolated UI session.
It quits automatically; do not run it inside an existing user session.

## 1.2.1 migration repair

Group-interface identifiers change when sockets are inserted. Migration now clears
retargeted input links, restores image/mask inputs and all captured output targets
by semantic name, and repairs an unlinked active Group Output left by 1.2.0.
Scene-driven control sockets cannot retain a shader-AOV connection.

`tests/upgrade_registration.py` upgrades a real 1.1.1 selective graph with both
Group Output and Viewer attached. `tests/migration_render.py` saves and reloads
a broken schema-6 scene and checks visible Smart glyphs in CPU and GPU compositors.
