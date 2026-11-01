"""Build an installable Blender Extension ZIP using Python's standard library."""

from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'dist' / 'ascii_render-1.0.0.zip'
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((ROOT / 'ascii_render').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            archive.write(path, path.relative_to(ROOT / 'ascii_render'))
    archive.write(ROOT / 'README.md', 'README.md')
print(target)
