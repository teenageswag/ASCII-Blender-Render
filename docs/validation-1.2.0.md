# ASCII Render 1.2.0 validation

Tested on 2026-11-02 with Blender **5.2.3 LTS**, Windows, NVIDIA GeForce RTX 3060.

## Image behavior

- Classic reproduces the 1.1.1 checker/Suzanne image within the PNG pixel tolerance (0.005 maximum channel difference).
- Smart renders the same scene at 64 columns using six subcell samples, surface-weighted local tone, a perceptual noise floor, and 2×3 glyph descriptors.
- Smart searches five candidates in actual ink-coverage order. Custom ramp ordering/repeats remain intact in Classic; duplicate shapes do not crowd the Smart candidate window.
- Native EXR checks enforce the requested linear-luminance gap for dark, middle and light backgrounds, including saturated ink. This is before the view transform, for opaque ink at full Strength.
- A three-frame Smart rotation sequence checks finite output and bounded frame changes. It is a smoke test, not proof of temporal stability.
- A contrasting red ASCII sphere touching a native green sphere reproduces the legacy fringe. After cleanup, 600 partially covered Cycles silhouette pixels have no native color contamination; EEVEE's silhouette ring is checked too. Native interiors and untouched world pixels remain identical; transparent-world coverage has no holes above the cleanup threshold.
- Preview tests use real Blender Screens/Spaces: toggle, manual overrides, split inheritance (including disable before the first topology event), new editor conversion, enable/disable, source reload, save/load, removal, and handler/timer cleanup.
- An isolated UI test also verifies cloned main windows, independent window scenes, workspace changes, and entering/leaving temporary fullscreen Screens. Screen bookmarks have a per-space backup on the Scene so deleting a temporary Screen cannot lose the original setting. Both stores are cleared on restore/unregister.

Before/after: [Classic](images/smart-before.png), [Smart](images/smart-after.png).

## Actual free-viewport inputs

`tools/benchmark_viewport.py` connects Image Info to a temporary diagnostic output
and reads Blender's own Raw-view screenshot. The viewport region is **1920×1080**;
the scene render resolution is **960×600**. The 8-bit diagnostic decodes to about
1919×1076 (within its quantization error), confirming the viewport domain rather
than the render resolution. Empty pass inputs decode to 0×0.

| Input | EEVEE free viewport | Cycles Rendered free viewport |
| --- | --- | --- |
| Combined | Viewport image | Viewport image |
| Normal | Viewport image | Empty |
| Depth | Viewport image | Empty |
| Diffuse Color | Viewport image | Empty |
| ASCII shader AOV | Viewport image | Empty |
| Object Index | No socket | Socket exists; extra viewport passes unsupported |

Material Preview uses EEVEE. The add-on uses Combined for structural gradients;
Normal/Depth are verified but not required. Optional Diffuse Color supplies ink
color. A shader AOV supplies surface/exclusion coverage, because EEVEE does not
expose Object Index. Missing inputs fall back natively, using Image Info availability.

## 1080p performance

Free Rendered EEVEE viewport, the checker/Suzanne scene, 64 columns. Each measured
frame rotates the view by 0.002 radians and executes a real window draw/swap.
Eight warm-up frames are discarded; 30 frames are measured. These are end-to-end
UI/EEVEE/compositor timings, not isolated compositor GPU timings or a sustained FPS
guarantee. Source code for 1.1.1 is staged separately; the user's scene is not used.

| Version / mode | Effect graph nodes | Median frame | Mean-rate FPS |
| --- | ---: | ---: | ---: |
| 1.1.1 Classic | 141 | 10.22 ms | 96.94 |
| 1.2.0 Classic | 685 total | 11.02 ms | 90.38 |
| 1.2.0 Smart | 685 total | 36.59 ms | 26.87 |

Classic uses direct boolean Group Input → modern Switch connections, allowing
Blender 5.2 to skip Smart branches. The total node count includes both modes.
Smart is substantially more expensive; reduce viewport resolution for larger scenes.
Grid calculations use compositor input pixels: Columns preserves relative density;
Cell Pixels preserves pixel width, and therefore changes column count with resolution.
Smart clamps cells to at least 8 input pixels.

## Checks

The release checks cover `render_smoke`, `selective_render`, `lifecycle`,
`smart_render`, `smart_nodes`, `edge_render`, `viewport_preview`, `gpu_smoke`,
`registration`, `upgrade_registration` (shipped 1.1.1 → 1.2.0), and `migration`.
All passed, including the foreground-capable `viewport_ui` test. The headless GPU
test exits successfully but Blender prints a 0.023346 MB unfreed-memory diagnostic
at shutdown; the interactive UI tests exit cleanly. Viewport state cleanup is
checked separately, including persistent bookmarks and the topology timer.
Build with `python tools/build.py`; validate the resulting ZIP with Blender's
extension validator. Commands and benchmark reproduction are in [development.md](development.md).

## Limits and tradeoffs

This is bounded descriptor matching, not an exhaustive pixel comparison against
every atlas glyph. Spatial blur and a noise floor suppress noise; no temporal
history is maintained, so threshold crossings can still flicker. Features below
the grid resolution cannot be reconstructed.

Diffuse Color omits emission, specular color and lighting; Combined includes them.
Cycles Rendered live cannot provide the extra passes; use F12 or EEVEE to evaluate
selection and albedo. Solid cannot display the compositor.

Edge cleanup hardens covered silhouette pixels, including alpha against a
transparent world. Contributions below the configurable coverage threshold retain
the legacy blend. Strength below 1 intentionally brings back the original image.
Minimum Contrast uses the configured Background as a reference for transparent
output; it cannot guarantee contrast against an arbitrary background added later.
