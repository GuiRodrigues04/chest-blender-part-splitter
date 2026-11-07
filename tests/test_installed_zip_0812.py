"""Smoke test of the release ZIP in Blender's installed extension namespace.
Checks preferences PT/EN, registration, cut, commit, revert and unregister.
"""
import bpy,sys,types,importlib,pathlib,tempfile,zipfile
root_dir=pathlib.Path(__file__).resolve().parents[1]
import tomllib
manifest=tomllib.loads((root_dir/'blender_manifest.toml').read_text(encoding='utf-8'))
archive=root_dir/'dist'/f"{manifest['id']}-{manifest['version']}.zip"
temporary=tempfile.TemporaryDirectory()
base=pathlib.Path(temporary.name)
with zipfile.ZipFile(archive) as z:
    assert z.read('src/properties.py')==(root_dir/'src/properties.py').read_bytes()
    z.extractall(base/'chest_part_splitter')
root=types.ModuleType('bl_ext');root.__path__=[];sys.modules['bl_ext']=root
repo=types.ModuleType('bl_ext.user_default');repo.__path__=[str(base)];sys.modules[repo.__name__]=repo
addon=importlib.import_module('bl_ext.user_default.chest_part_splitter')
addon.register()
assert hasattr(bpy.types.Scene,'chest_splitter')
pref=bpy.context.preferences.addons.new()
pref.module=addon.__name__
assert pref.preferences is not None, 'Installed addon preferences must resolve by the extension root'
pref.preferences.language='PT_BR'
assert addon.src.translations.get_addon_locale()=='pt_BR'
pref.preferences.language='EN_US'
assert addon.src.translations.get_addon_locale()=='en_US'
bpy.context.preferences.addons.remove(pref)

bpy.ops.mesh.primitive_cube_add(size=.1)
bpy.ops.chest.splitter_set_target()
assert bpy.ops.chest.splitter_generate_preview()=={'FINISHED'}
assert bpy.ops.chest.splitter_commit_parts()=={'FINISHED'}
assert bpy.ops.chest.splitter_revert_cut()=={'FINISHED'}
addon.unregister()
assert not hasattr(bpy.types.Scene,'chest_splitter')
print('INSTALL_NAMESPACE_SMOKE_OK',bpy.app.version_string)

temporary.cleanup()
