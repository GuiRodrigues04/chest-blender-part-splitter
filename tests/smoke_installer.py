import sys, zipfile, types, importlib, tempfile
from pathlib import Path
import bpy
from mathutils import Vector

temporary = tempfile.TemporaryDirectory(prefix="part_splitter_smoke_")
base = Path(temporary.name)
folder = base / "bl_ext/user_default/chest_part_splitter"
folder.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(
    Path(__file__).resolve().parents[1] / "dist/chest_part_splitter-0.8.13.zip"
) as z:
    z.extractall(folder)
for name, path in [
    ("bl_ext", base / "bl_ext"),
    ("bl_ext.user_default", base / "bl_ext/user_default"),
]:
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(path)]
    sys.modules[name] = pkg
name = "bl_ext.user_default.chest_part_splitter"
addon = importlib.import_module(name)
addon.register()
entry = bpy.context.preferences.addons.new()
entry.module = name
pref = entry.preferences
assert pref is not None
trans = importlib.import_module(name + ".src.translations")
pref.language = "EN_US"
assert trans.localize_text("Alinhar por Vértices") == "Align by Vertices"
pref.language = "PT_BR"
assert trans.localize_text("Alinhar por Vértices") == "Alinhar por Vértices"
geo = importlib.import_module(name + ".src.geometry_solid")
scene = bpy.context.scene
scene.unit_settings.scale_length = 0.001
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)


def box(label, dims, location):
    me = geo.create_primitive_cutter_mesh(label, "BOX", Vector(dims))
    obj = bpy.data.objects.new(label, me)
    scene.collection.objects.link(obj)
    obj.location = location
    return obj


s = scene.chest_splitter
s.target_object = box("body", (40, 40, 40), (0, 0, 0))
s.solid_cutter_object = box("cutter", (24, 24, 40), (0, 0, 18))
s.split_mode = "SOLID"
s.connector_enabled = True
s.connector_distribution = "MANUAL"
s.part_clearance_mm = 0.2
bpy.context.view_layer.update()
assert bpy.ops.chest.splitter_edit_manual_connectors() == {"FINISHED"}
s.manual_connectors.add()
assert bpy.ops.chest.splitter_confirm_manual_connectors() == {"FINISHED"}
assert bpy.ops.chest.splitter_commit_parts() == {"FINISHED"}
assert bpy.ops.chest.splitter_revert_cut() == {"FINISHED"}
addon.unregister()
bpy.context.preferences.addons.remove(entry)
print(
    "ZIP_SMOKE_OK: namespace, PT/EN, solid clearance, manual pins, preview, commit, revert, unregister"
)

temporary.cleanup()
