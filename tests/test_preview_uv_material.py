"""Synthetic textured previews preserve multiple corner UV maps and material state."""
import sys
import unittest
import json
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src
from src.operators import get_current_session_parts
from src.geometry_clearance import triangulated_source_mesh


class PreviewUVMaterial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    @classmethod
    def tearDownClass(cls):
        src.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        if not hasattr(bpy.types.Scene, 'chest_splitter'):
            src.register()
        scene.unit_settings.scale_length = 1.0
        self.settings = scene.chest_splitter
        self.target = self.make_target()
        self.source = self.target.data
        self.source_state = self.snapshot(self.source)
        self.view_state = self.view_snapshot()
        self.settings.target_object = self.target
        self.settings.split_mode = 'PLANE'
        self.settings.plane_origin = (0.0, 0.0, 0.0)
        self.settings.plane_normal = (0.0, 0.0, 1.0)
        self.settings.part_clearance_mm = 0.1
        self.settings.part_clearance_apply_to = 'BOTH'
        self.settings.connector_enabled = False
        self.settings.commit_next_target = 'NONE'
        self.settings.view_mode = 'ASSEMBLED'

    def make_target(self):
        mesh = bpy.data.meshes.new('UV_target_mesh')
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.1)
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        surface = mesh.uv_layers.new(name='UV_Surface')
        rendered = mesh.uv_layers.new(name='UV_Render')
        for polygon in mesh.polygons:
            for loop_index in polygon.loop_indices:
                co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
                surface.data[loop_index].uv = (0.5 + 5.0 * co.x, 0.5 + 5.0 * co.y)
                rendered.data[loop_index].uv = (0.5 + 5.0 * co.y, 0.5 + 5.0 * co.z)
        mesh.uv_layers.active_index = 0
        mesh.uv_layers.active_render_index = 1

        image = bpy.data.images.new('UV_4_Color_Checker', width=64, height=64, alpha=True)
        colors = ((1., 0., 0., 1.), (0., 1., 0., 1.),
                  (0., 0., 1., 1.), (1., 1., 0., 1.))
        pixels = []
        for y in range(64):
            for x in range(64):
                pixels.extend(colors[(2 if y >= 32 else 0) + (1 if x >= 32 else 0)])
        image.pixels.foreach_set(pixels)
        image.pack()
        material = bpy.data.materials.new('UV_4_Color_Material')
        material.use_nodes = True
        principled = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        texture = material.node_tree.nodes.new('ShaderNodeTexImage')
        texture.image = image
        texture.interpolation = 'Closest'
        material.node_tree.links.new(texture.outputs['Color'], principled.inputs['Base Color'])
        mesh.materials.append(material)
        target = bpy.data.objects.new('UV_target', mesh)
        bpy.context.scene.collection.objects.link(target)
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        bpy.context.view_layer.update()
        return target

    @staticmethod
    def snapshot(mesh):
        return {
            'names': tuple(layer.name for layer in mesh.uv_layers),
            'active': mesh.uv_layers.active.name if mesh.uv_layers.active else None,
            'render': next((layer.name for layer in mesh.uv_layers if layer.active_render), None),
            'uv': {layer.name: tuple(tuple(round(float(c), 7) for c in item.uv)
                                     for item in layer.data) for layer in mesh.uv_layers},
            'materials': tuple(m.as_pointer() if m else None for m in mesh.materials),
        }

    @staticmethod
    def view_snapshot():
        state = []
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    sh = area.spaces.active.shading
                    state.append((screen.name, sh.type, sh.color_type, sh.light,
                                  sh.show_shadows, sh.use_scene_world, sh.use_scene_lights))
        return tuple(state)

    def retained_uv_report(self, part):
        mesh = self.source
        mesh.calc_loop_triangles()
        source_tris = list(mesh.loop_triangles)
        source_ids = [tuple(int(i) for i in tri.vertices) for tri in source_tris]
        points = [self.target.matrix_world @ v.co for v in mesh.vertices]
        tree = BVHTree.FromPolygons(points, source_ids, all_triangles=True)
        source_uv = {layer.name: [tuple(float(c) for c in item.uv) for item in layer.data]
                     for layer in mesh.uv_layers}
        output = part.data
        output.calc_loop_triangles()
        report = {name: {'triangles': 0, 'max_delta': 0.0, 'pixel_mismatches': 0,
                         'quadrants': set()} for name in source_uv}
        for tri in output.loop_triangles:
            pts = [output.vertices[i].co.copy() for i in tri.vertices]
            hit = tree.find_nearest(sum(pts, Vector()) / 3.0)
            if not hit or hit[0] is None or hit[3] > 1e-6:
                continue
            src_tri = source_tris[int(hit[2])]
            ids = source_ids[int(hit[2])]
            a, b, c = [points[i] for i in ids]
            v0, v1 = b-a, c-a
            d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
            den = d00*d11-d01*d01
            if abs(den) < 1e-20:
                continue
            for layer in output.uv_layers:
                if layer.name not in report:
                    continue
                src_values = [source_uv[layer.name][int(i)] for i in src_tri.loops]
                expected, actual = [], []
                for vi, li in zip(tri.vertices, tri.loops):
                    p = output.vertices[vi].co
                    d20, d21 = (p-a).dot(v0), (p-a).dot(v1)
                    wb, wc = (d11*d20-d01*d21)/den, (d00*d21-d01*d20)/den
                    wa = 1.0-wb-wc
                    expected.append(tuple(wa*src_values[0][k]+wb*src_values[1][k]+wc*src_values[2][k] for k in range(2)))
                    actual.append(tuple(float(x) for x in layer.data[int(li)].uv))
                row = report[layer.name]
                row['triangles'] += 1
                for e, v in zip(expected, actual):
                    row['max_delta'] = max(row['max_delta'], ((e[0]-v[0])**2+(e[1]-v[1])**2)**0.5)
                eu = tuple(sum(p[k] for p in expected)/3 for k in range(2))
                au = tuple(sum(p[k] for p in actual)/3 for k in range(2))
                def quadrant(uv):
                    return (2 if uv[1] % 1.0 >= 0.5 else 0) + (1 if uv[0] % 1.0 >= 0.5 else 0)
                ce, ca = quadrant(eu), quadrant(au)
                row['quadrants'].add(ce)
                row['pixel_mismatches'] += ce != ca
        for row in report.values():
            row['quadrants'] = sorted(row['quadrants'])
        return report

    def assert_textured_preview(self):
        parts = get_current_session_parts(bpy.context.scene)
        self.assertEqual(len(parts), 2)
        self.assertEqual(self.snapshot(self.source), self.source_state)
        covered_quadrants = {name: set() for name in self.source_state['names']}
        for part in parts:
            state = self.snapshot(part.data)
            self.assertEqual(state['names'], self.source_state['names'])
            self.assertEqual(state['active'], 'UV_Surface')
            self.assertEqual(state['render'], 'UV_Render')
            self.assertEqual(state['materials'], self.source_state['materials'])
            report = self.retained_uv_report(part)
            print('UV_TEXTURE_REPORT=' + json.dumps({'part': part.name, 'layers': report}, sort_keys=True))
            for name, row in report.items():
                self.assertGreater(row['triangles'], 0, json.dumps(report, sort_keys=True))
                self.assertLessEqual(row['max_delta'], 1e-5, json.dumps(report, sort_keys=True))
                self.assertEqual(row['pixel_mismatches'], 0, json.dumps(report, sort_keys=True))
                covered_quadrants[name].update(row['quadrants'])
        for name, quadrants in covered_quadrants.items():
            self.assertEqual(len(quadrants), 4, json.dumps({name: sorted(quadrants)}))
        self.assertEqual(self.view_snapshot(), self.view_state)
        return parts

    def test_bare_clearance_commit_revert_preserves_texture(self):
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'}, self.settings.get_localized_status())
        self.assert_textured_preview()
        self.assertFalse(self.settings.connector_enabled)
        self.assertTrue(self.target.hide_get())
        self.assertEqual(bpy.ops.chest.splitter_commit_parts(), {'FINISHED'})
        operation_id = self.settings.active_operation_id or self.settings.session_id
        self.assertEqual(bpy.ops.chest.splitter_revert_cut(operation_id=operation_id), {'FINISHED'})
        self.assertEqual(self.snapshot(self.target.data), self.source_state)
        self.assertFalse(self.target.hide_get())
        self.assertEqual(self.view_snapshot(), self.view_state)

    def test_center_pin_preserves_surface_texture(self):
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'CENTER'
        self.settings.connector_diameter_mm = 4.0
        self.settings.connector_length_mm = 4.0
        self.settings.end_clearance_mm = 0.2
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'}, self.settings.get_localized_status())
        self.assert_textured_preview()


    def test_loop_surface_cut_preserves_texture(self):
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(self.source)
        bm.faces.ensure_lookup_table()
        top = max(bm.faces, key=lambda face: face.normal.z)
        for face in bm.faces:
            face.select_set(face == top)
        bm.faces.active = top
        bmesh.update_edit_mesh(self.source)
        self.assertEqual(bpy.ops.chest.splitter_capture_face_boundary(), {'FINISHED'})
        bpy.ops.object.mode_set(mode='OBJECT')
        self.settings.split_mode = 'LOOP'
        self.settings.loop_behavior = 'EXTRUDE'
        self.settings.loop_extrude_depth_mm = 5.0
        self.settings.part_clearance_mm = 0.1
        self.settings.part_clearance_apply_to = 'PART'
        result = bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(result, {'FINISHED'}, self.settings.get_localized_status())
        self.assert_textured_preview()

    def test_triangle_copy_preserves_uv_seams_and_active_render_layer(self):
        for polygon in self.source.polygons:
            offset = polygon.index * 0.01
            for loop_index in polygon.loop_indices:
                surface = self.source.uv_layers['UV_Surface'].data[loop_index].uv
                rendered = self.source.uv_layers['UV_Render'].data[loop_index].uv
                surface.x += offset
                rendered.y -= offset
        self.source.calc_loop_triangles()
        triangles = list(self.source.loop_triangles)
        values_by_vertex = {}
        for polygon in self.source.polygons:
            for loop_index in polygon.loop_indices:
                vertex_index = self.source.loops[loop_index].vertex_index
                values_by_vertex.setdefault(vertex_index, set()).add(
                    tuple(round(float(c), 6) for c in self.source.uv_layers['UV_Surface'].data[loop_index].uv))
        self.assertTrue(any(len(values) > 1 for values in values_by_vertex.values()),
                        'Fixture must include a shared-vertex UV seam.')
        copied = triangulated_source_mesh(self.source)
        try:
            self.assertEqual(tuple(layer.name for layer in copied.uv_layers), self.source_state['names'])
            self.assertEqual(copied.uv_layers.active.name, 'UV_Surface')
            self.assertEqual(next(layer.name for layer in copied.uv_layers if layer.active_render), 'UV_Render')
            for triangle, polygon in zip(triangles, copied.polygons):
                for source_loop, copied_loop in zip(triangle.loops, polygon.loop_indices):
                    for name in self.source_state['names']:
                        expected = tuple(self.source.uv_layers[name].data[int(source_loop)].uv)
                        actual = tuple(copied.uv_layers[name].data[copied_loop].uv)
                        self.assertEqual(actual, expected, f'{name} seam corner was reassigned')
        finally:
            bpy.data.meshes.remove(copied)

    def test_triangle_copy_without_uv_layers_is_valid(self):
        mesh = bpy.data.meshes.new('NoUV_source')
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.1)
        bm.to_mesh(mesh)
        bm.free()
        copied = triangulated_source_mesh(mesh)
        try:
            self.assertEqual(len(mesh.uv_layers), 0)
            self.assertEqual(len(copied.uv_layers), 0)
            self.assertGreater(len(copied.polygons), 0)
        finally:
            bpy.data.meshes.remove(copied)
            bpy.data.meshes.remove(mesh)

if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PreviewUVMaterial))
    sys.exit(not result.wasSuccessful())
