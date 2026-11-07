"""Exercise the exact manifest-version ZIP in an isolated extension namespace.

Run after scripts/build.py. No user installation or preference file is changed.
"""
import importlib
import pathlib
import struct
import sys
import tempfile
import tomllib
import types
import unittest
import zipfile
import xml.etree.ElementTree as ET

import bpy

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = tomllib.loads((ROOT / 'blender_manifest.toml').read_text(encoding='utf-8'))


class ReleasePackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='splitter_candidate_')
        base = pathlib.Path(cls.temporary.name)
        folder = base / 'chest_part_splitter'
        archive = ROOT / 'dist' / f"{MANIFEST['id']}-{MANIFEST['version']}.zip"
        with zipfile.ZipFile(archive) as z:
            expected = {'__init__.py', 'blender_manifest.toml', 'LICENSE', 'README.md', 'CHANGELOG.md', 'docs/GUIA_RAPIDO_PT_EN.md'}
            expected.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'src').rglob('*.py'))
            actual = {n for n in z.namelist() if not n.endswith('/')}
            if actual != expected:
                raise AssertionError(f'Package contents differ: {actual ^ expected}')
            for name in expected:
                if z.read(name) != (ROOT / name).read_bytes():
                    raise AssertionError(f'Package does not match source: {name}')
            z.extractall(folder)
        for name, paths in [('bl_ext', []), ('bl_ext.user_default', [str(base)])]:
            module = types.ModuleType(name)
            module.__path__ = paths
            sys.modules[name] = module
        for k in list(sys.modules.keys()):
            if k.startswith('bl_ext.user_default.chest_part_splitter'):
                del sys.modules[k]
        importlib.invalidate_caches()
        cls.addon = importlib.import_module('bl_ext.user_default.chest_part_splitter')
        cls.addon.register()
        cls.entry = bpy.context.preferences.addons.get(cls.addon.__name__) or bpy.context.preferences.addons.new()
        cls.entry.module = cls.addon.__name__

    @classmethod
    def tearDownClass(cls):
        bpy.context.preferences.addons.remove(cls.entry)
        cls.addon.unregister()
        cls.temporary.cleanup()

    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        bpy.context.scene.unit_settings.scale_length = 0.001
        self.settings = bpy.context.scene.chest_splitter
        self.entry.preferences.language = 'EN_US'

    def test_identity_and_locales(self):
        version = tuple(map(int, MANIFEST['version'].split('.')))
        self.assertEqual(self.addon.bl_info['version'], version)
        self.assertEqual(self.addon.src.constants.ADDON_VERSION, version)
        trans = self.addon.src.translations
        for locale, expected in [('EN_US', 'Align by Vertices'), ('PT_BR', 'Alinhar por Vértices')]:
            self.entry.preferences.language = locale
            self.assertEqual(trans.localize_text('Alinhar por Vértices'), expected)

    def test_cut_export_dimensions_commit_revert(self):
        bpy.ops.mesh.primitive_cube_add(size=40)
        original = bpy.context.object
        self.assertEqual(bpy.ops.chest.splitter_set_target(), {'FINISHED'})
        self.settings.connector_enabled = False
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'})
        self.assertTrue(self.settings.part_a_is_manifold)
        self.assertTrue(self.settings.part_b_is_manifold)
        # Exploded display must not affect exported assembly coordinates.
        self.settings.view_mode = 'EXPLODED'
        self.settings.explosion_distance_mm = 75
        with tempfile.TemporaryDirectory(prefix='splitter_exports_') as temp:
            self.settings.export_directory = temp
            for format_id, extension in [('STL_PARTS', '*.stl'), ('3MF', '*.3mf'), ('OBJ', '*.obj')]:
                with self.subTest(format=format_id):
                    self.settings.export_format = format_id
                    self.assertEqual(bpy.ops.chest.splitter_export_parts(), {'FINISHED'})
                    paths = list(pathlib.Path(temp).glob(extension))
                    self.assertTrue(paths)
                    coords = []
                    for path in paths:
                        if path.suffix == '.stl':
                            data = path.read_bytes()
                            count = struct.unpack_from('<I', data, 80)[0]
                            self.assertEqual(len(data), 84 + count * 50)
                            for i in range(count):
                                record = struct.unpack_from('<12fH', data, 84 + 50*i)
                                coords.extend([record[3:6], record[6:9], record[9:12]])
                        elif path.suffix == '.3mf':
                            with zipfile.ZipFile(path) as z:
                                for member in z.namelist():
                                    if member.endswith('.model'):
                                        model = ET.fromstring(z.read(member))
                                        self.assertEqual(model.get('unit'), 'millimeter')
                                        coords.extend(tuple(float(v.get(a)) for a in 'xyz') for v in model.iter() if v.tag.endswith('}vertex'))
                        else:
                            coords.extend(tuple(map(float, line.split()[1:4])) for line in path.read_text().splitlines() if line.startswith('v '))
                    self.assertTrue(coords)
                    for axis in range(3):
                        self.assertAlmostEqual(min(v[axis] for v in coords), -20, delta=0.01)
                        self.assertAlmostEqual(max(v[axis] for v in coords), 20, delta=0.01)
        self.assertEqual(bpy.ops.chest.splitter_commit_parts(), {'FINISHED'})
        self.assertEqual(bpy.ops.chest.splitter_revert_cut(), {'FINISHED'})
        self.assertTrue(any(o.type == 'MESH' and not o.hide_get() for o in bpy.context.scene.objects))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
