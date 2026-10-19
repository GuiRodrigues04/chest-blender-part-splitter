"""Build only the Blender installer, excluding tests, evidence and bytecode."""

from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
# Read version from blender_manifest.toml
import re
manifest = (root / "blender_manifest.toml").read_text(encoding="utf-8")
m = re.search(r'^\s*version\s*=\s*"([^"]+)"', manifest, re.MULTILINE)
version = m.group(1) if m else "0.8.14"
output = root / "dist" / f"chest_part_splitter-{version}.zip"
output.parent.mkdir(exist_ok=True)
files = [
    root / n
    for n in (
        "__init__.py",
        "blender_manifest.toml",
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
    )
]
files += sorted((root / "src").glob("*.py"))
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in files:
        archive.write(path, path.relative_to(root).as_posix())
print(output)
