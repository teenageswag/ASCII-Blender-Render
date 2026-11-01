"""Build an installable Blender Extension ZIP using Python's standard library."""

from pathlib import Path
import zipfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
manifest = tomllib.loads((ROOT / 'ascii_render/blender_manifest.toml').read_text(encoding='utf-8'))
target = ROOT / 'dist' / f"ascii_render-{manifest['version']}.zip"
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((ROOT / 'ascii_render').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            archive.write(path, path.relative_to(ROOT / 'ascii_render'))
    archive.write(ROOT / 'README.md', 'README.md')
print(target)
