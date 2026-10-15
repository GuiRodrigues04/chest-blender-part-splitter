import os
import shutil
import zipfile

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dist_dir = os.path.join(repo_root, "dist")
os.makedirs(dist_dir, exist_ok=True)
zip_path = os.path.join(dist_dir, "chest_part_splitter-0.8.11.zip")
target_install_dir = os.path.expanduser(
    r"~\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default\chest_part_splitter"
)
downloads_dir = os.path.expanduser(r"~\Downloads")

print("--- BUILDING CHEST PART SPLITTER 0.8.11 ZIP ---")

# Files to pack
files_to_pack = [
    "blender_manifest.toml",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "__init__.py",
]

src_dir = os.path.join(repo_root, "src")
src_files = []
for root, dirs, files in os.walk(src_dir):
    if "__pycache__" in root:
        continue
    for f in sorted(files):
        if f.endswith(".py"):
            rel_from_root = os.path.relpath(os.path.join(root, f), repo_root)
            src_files.append(rel_from_root)

all_files = files_to_pack + sorted(src_files)

# Create Zip
if os.path.exists(zip_path):
    os.remove(zip_path)

with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for rel_path in all_files:
        full_path = os.path.join(repo_root, rel_path)
        if os.path.exists(full_path):
            zf.write(full_path, arcname=rel_path.replace("\\", "/"))
            print(f"  + {rel_path}")
        else:
            print(f"  ! Warning: {rel_path} not found")

print(f"ZIP package created: {zip_path} ({os.path.getsize(zip_path)} bytes)")

# Copy to Downloads
for dl_name in ["chest_part_splitter-0.8.11.zip", "chest-blender-part-splitter-0.8.11.zip"]:
    dest = os.path.join(downloads_dir, dl_name)
    shutil.copy2(zip_path, dest)
    print(f"Copied to: {dest}")

# Clean and Install into Blender 5.2
print(f"\nInstalling into Blender 5.2: {target_install_dir}")
if os.path.exists(target_install_dir):
    shutil.rmtree(target_install_dir)
os.makedirs(target_install_dir, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as zf:
    zf.extractall(target_install_dir)

# Remove any __pycache__ in target
for root, dirs, files in os.walk(target_install_dir):
    if "__pycache__" in dirs:
        shutil.rmtree(os.path.join(root, "__pycache__"), ignore_errors=True)

print("Installation into Blender 5.2 completed successfully!")
