"""Build only the Blender installer, excluding tests, evidence and bytecode."""

from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
output = root / "dist" / "chest_part_splitter-0.8.13.zip"
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
