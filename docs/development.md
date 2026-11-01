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
blender --background --factory-startup --command extension validate dist/ascii_render-1.1.1.zip
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
- **upgrade_registration:** upgrade the actual 1.1.0 archive to the current code without restarting Blender or clearing Python's module cache.

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
