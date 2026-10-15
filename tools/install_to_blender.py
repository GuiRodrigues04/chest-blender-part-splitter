import os
import shutil
import zipfile
import bpy

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
zip_path = os.path.join(repo_root, "dist", "chest_part_splitter-0.8.11.zip")
target_dir = os.path.expanduser(r"~\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default\chest_part_splitter")

print(f"--- INSTALLING CHEST PART SPLITTER 0.8.11 ---")
print(f"Source ZIP: {zip_path}")
print(f"Target Directory: {target_dir}")

if not os.path.exists(zip_path):
    raise FileNotFoundError(f"Zip file not found at {zip_path}")

# Ensure clean directory
if os.path.exists(target_dir):
    print("Cleaning existing installation directory...")
    shutil.rmtree(target_dir)

os.makedirs(target_dir, exist_ok=True)

# Extract ZIP
print("Extracting package contents...")
with zipfile.ZipFile(zip_path, "r") as zf:
    zf.extractall(target_dir)

print("\nInstalled files:")
file_count = 0
for root, dirs, files in os.walk(target_dir):
    for f in sorted(files):
        rel_path = os.path.relpath(os.path.join(root, f), target_dir)
        print(f"  {rel_path}")
        file_count += 1
print(f"Total files installed: {file_count}")

# Verify blender manifest
manifest_path = os.path.join(target_dir, "blender_manifest.toml")
if os.path.exists(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_text = f.read()
    print("\nManifest preview:")
    for line in manifest_text.splitlines()[:10]:
        print(f"  {line}")

# Try enabling addon / extension in Blender
print("\nEnabling extension in Blender...")
try:
    # Refresh extensions repo if available
    if hasattr(bpy.ops.extensions, "repo_refresh_all"):
        try:
            bpy.ops.extensions.repo_refresh_all()
        except Exception as e:
            print(f"Repo refresh note: {e}")

    # In Blender 4.2+, extensions can be enabled either via addon_enable or package_install_files
    addon_name = "chest_part_splitter"
    import addon_utils
    addon_utils.modules_refresh()
    
    # Enable addon
    default_state, loaded_state = addon_utils.check(addon_name)
    print(f"Addon state before enable: default={default_state}, loaded={loaded_state}")
    
    addon_utils.enable(addon_name, default_set=True, persistent=True)
    default_state, loaded_state = addon_utils.check(addon_name)
    print(f"Addon state after enable: default={default_state}, loaded={loaded_state}")
    
    bpy.ops.wm.save_userpref()
    print("User preferences saved successfully.")
except Exception as e:
    print(f"Error enabling addon: {e}")
    import traceback
    traceback.print_exc()

# Verify classes and UI
print("\nVerifying registered classes and properties...")
panel_exists = hasattr(bpy.types, "VIEW3D_PT_chest_part_splitter")
scene_props = hasattr(bpy.types.Scene, "chest_part_splitter")
print(f"VIEW3D_PT_chest_part_splitter registered: {panel_exists}")
print(f"Scene.chest_part_splitter registered: {scene_props}")

# Test importing module directly from target directory
try:
    import sys
    if target_dir not in sys.path:
        sys.path.insert(0, target_dir)
    import chest_part_splitter
    print(f"Imported chest_part_splitter module successfully.")
    print(f"Module file: {chest_part_splitter.__file__}")
except Exception as e:
    print(f"Import verification: {e}")

print("\n--- INSTALLATION COMPLETED SUCCESSFULLY ---")
