"""Full curved contact, centered/manual pins and physical initial dimensions."""
import sys
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT));sys.path.insert(0, str(ROOT/'tests'))
import src
src.register()
from test_natural_clearance import fixture
from src.geometry_loop import slice_mesh_by_loop, get_topology_signature
from src.connector_surface import cache_prepared_interface, clear_prepared_split_cache, prepare_split_candidates
from src.connector_domain import domain_centroid, complete_contact_pair
from src.connector_sizing import recommend_dimensions, apply_suggestion, defaults_untouched
from src.geometry_connectors import compute_connector_layout, ConnectorValidationError
from src.geometry_contract import build_cut_interface


class ConnectorDomainSizing(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.obj, self.ring, self.seed = fixture()
        self.scene = bpy.context.scene
        self.scene.unit_settings.scale_length = 1
        self.s = self.scene.chest_splitter
        self.s.target_object = self.obj;self.s.split_mode = 'LOOP'
        self.s.loop_behavior = 'DETACH'
        self.s.loop_vertex_indices = ','.join(map(str, self.ring))
        self.s.loop_seed_face_index = self.seed
        self.s.loop_is_captured = True
        self.s.loop_topology_signature = get_topology_signature(self.obj)
        self.s.connector_edge_margin_mm = .4
        self.s.clearance_per_side_mm = .1;self.s.end_clearance_mm = .1
        self.s.connector_distribution = 'CENTER'
        clear_prepared_split_cache()

    def test_curved_contact_keeps_entire_domain_and_center_for_both_male_sides(self):
        nominal = None
        for gap, side in ((0.,'A'),(.1,'A'),(.1,'B')):
            with self.subTest(gap=gap, side=side):
                self.s.connector_male_part = side
                result = slice_mesh_by_loop(self.obj, self.obj.name, self.ring, self.seed,
                    self.scene, part_clearance_mm=gap)
                try:
                    self.assertTrue(result.interface.complete_contact_domain)
                    prepared = cache_prepared_interface(bpy.context, result.interface)
                    interface = prepared.interface
                    self.assertGreater(interface.area_mm2, 290.)
                    center = domain_centroid(interface.outer_contours_uv, interface.hole_contours_uv)
                    layout = compute_connector_layout(self.obj.data, self.obj.matrix_world,
                        prepared.surface_origin, prepared.surface_normal, 'CENTER', .4, 1000.,
                        2., .1, interface=interface)
                    uv = interface.world_to_uv(layout['positions'][0])
                    self.assertLess(sum((x-y)**2 for x,y in zip(center,uv)), 1e-16)
                    self.assertLess((layout['positions'][0].xy).length*1000, .01)
                    manual = compute_connector_layout(self.obj.data, self.obj.matrix_world,
                        prepared.surface_origin, prepared.surface_normal, 'MANUAL', .4, 1000.,
                        2., .1, interface=interface,
                        manual_specs=[dict(u_mm=uv[0]*1000,v_mm=uv[1]*1000,yaw_deg=0.)])
                    self.assertTrue(manual['manual_eval_results'][0]['is_valid'])
                    self.assertLess((manual['positions'][0]-layout['positions'][0]).length, 1e-7)
                    nominal = layout['positions'][0]
                finally:
                    for part in result:part.free()

    def test_suggestion_checks_real_receiver_and_preserves_custom_values(self):
        self.assertTrue(defaults_untouched(self.s))
        prepared = prepare_split_candidates(bpy.context, include_solids=True)
        before = (self.s.connector_diameter_mm, self.s.connector_length_mm)
        suggestion = recommend_dimensions(prepared, self.s, self.obj)
        self.assertGreaterEqual(suggestion['diameter_mm'], 1.)
        self.assertGreaterEqual(suggestion['length_mm'], 2.)
        self.assertLess(suggestion['length_mm']+.1+.4, suggestion['receiver_depth_mm'])
        self.assertEqual(before, (self.s.connector_diameter_mm, self.s.connector_length_mm))
        self.s.connector_diameter_mm = 3.;self.s.connector_length_mm = 5.
        self.assertFalse(defaults_untouched(self.s))
        self.assertIsNone(apply_suggestion(bpy.context, only_defaults=True))
        self.assertEqual((3.,5.), (self.s.connector_diameter_mm,self.s.connector_length_mm))
        self.assertEqual(bpy.ops.chest.splitter_suggest_connector_dimensions(), {'FINISHED'})

    def test_manual_distribution_without_positions_uses_center_for_sizing_only(self):
        prepared = prepare_split_candidates(bpy.context, include_solids=True)
        self.s.connector_distribution = 'MANUAL'
        self.s.manual_connectors.clear()
        result = recommend_dimensions(prepared, self.s, self.obj)
        self.assertTrue(result['manual_reference'])
        self.assertEqual(self.s.connector_distribution, 'MANUAL')
        self.assertEqual(len(self.s.manual_connectors), 0)
        self.assertGreaterEqual(result['diameter_mm'], 1.)
        self.assertGreaterEqual(result['length_mm'], 2.)

    def test_manual_position_is_used_for_complex_contact_sizing(self):
        prepared = prepare_split_candidates(bpy.context, include_solids=True)
        from src.connector_domain import domain_centroid
        u, v = domain_centroid(prepared.interface.outer_contours_uv,
                               prepared.interface.hole_contours_uv)
        self.s.connector_distribution = 'MANUAL'
        item = self.s.manual_connectors.add()
        item.u_mm = u*prepared.unit_scale; item.v_mm = v*prepared.unit_scale
        before = (item.u_mm, item.v_mm, item.yaw_deg)
        result = recommend_dimensions(prepared, self.s, self.obj)
        self.assertFalse(result['manual_reference'])
        self.assertEqual((item.u_mm, item.v_mm, item.yaw_deg), before)
        self.assertEqual(self.s.connector_distribution, 'MANUAL')

    def test_saved_historical_defaults_remain_eligible_but_custom_values_do_not(self):
        self.s.connector_diameter_mm = 6.
        self.s.connector_length_mm = 8.
        self.s.connector_chamfer_mm = .8
        self.s.connector_dimensions_customized = False
        self.assertTrue(defaults_untouched(self.s))
        self.s.connector_diameter_mm = 3.
        self.s.connector_dimensions_customized = False
        self.assertFalse(defaults_untouched(self.s))
        self.s.connector_diameter_mm = 6.
        self.s.connector_dimensions_customized = True
        self.assertFalse(defaults_untouched(self.s))

    def test_captured_region_prepares_its_only_contact_before_preview(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=.05)
        obj = bpy.context.object
        region = [f.index for f in obj.data.polygons
                  if sum(obj.data.vertices[i].co.z for i in f.vertices)/len(f.vertices) > .00001]
        s = bpy.context.scene.chest_splitter
        s.target_object = obj; s.split_mode = 'LOOP'; s.loop_behavior = 'WHOLE'
        s.region_selection_enabled = True; s.region_target = obj
        s.region_face_indices = ','.join(map(str, region))
        from src.geometry_region import mesh_signature
        s.region_mesh_signature = mesh_signature(obj.data)
        s.part_clearance_mm = 0.; s.connector_enabled = True; s.contact_patch_index = -1
        s.connector_diameter_mm = 6.; s.connector_length_mm = 8.
        s.connector_dimensions_customized = False
        clear_prepared_split_cache()
        self.assertEqual(bpy.ops.chest.splitter_suggest_connector_dimensions(), {'FINISHED'})
        self.assertEqual(s.contact_patch_index, 0)
        self.assertEqual(len(json.loads(s.contact_choices)), 1)
        prepared = prepare_split_candidates(bpy.context, include_solids=True)
        self.assertTrue(prepared.sizing_trees)
        self.assertTrue(s.connector_enabled)
        self.assertTrue(s.connector_sizing_status)
        self.assertNotIn('SPLITTER_PREVIEW_A', bpy.data.objects)
        self.assertNotIn('SPLITTER_PREVIEW_B', bpy.data.objects)

    def test_captured_region_with_multiple_contacts_does_not_guess(self):
        from src.geometry_region import mesh_signature
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        s = bpy.context.scene.chest_splitter
        s.target_object = obj; s.split_mode = 'LOOP'; s.loop_behavior = 'WHOLE'
        s.region_selection_enabled = True; s.region_target = obj
        s.region_face_indices = '0,1,2'; s.region_mesh_signature = mesh_signature(obj.data)
        s.contact_patch_index = -1
        choices = [{'index': 0, 'area_mm2': 10.}, {'index': 1, 'area_mm2': 8.}]
        clear_prepared_split_cache()
        with patch('src.geometry_region.slice_region', return_value={
                'interface': None, 'contact_choices': choices}):
            with self.assertRaisesRegex(ValueError, 'mais de um contato'):
                prepare_split_candidates(bpy.context, include_solids=True, auto_contact=True)
        self.assertEqual(s.contact_patch_index, -1)
        self.assertEqual(len(json.loads(s.contact_choices)), 2)

    def test_narrow_10_by_4_contact_suggests_before_preview_and_fits_either_side(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .0005))
        obj = bpy.context.object; obj.dimensions = (.0101, .0042, .012)
        bpy.context.view_layer.update()
        s = bpy.context.scene.chest_splitter
        s.target_object = obj; s.split_mode = 'PLANE'
        s.plane_origin = (0, 0, 0); s.plane_normal = (0, 0, 1)
        s.connector_distribution = 'CENTER'; s.connector_male_part = 'A'
        s.connector_edge_margin_mm = .4; s.clearance_per_side_mm = .15
        s.end_clearance_mm = .2; s.part_clearance_mm = 0.; s.connector_enabled = False
        s.connector_diameter_mm = 6.; s.connector_length_mm = 8.
        s.connector_chamfer_mm = .8; s.connector_dimensions_customized = False
        clear_prepared_split_cache()
        s.connector_enabled = True
        with self.assertRaises(RuntimeError):
            bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(s.session_status, 'PREVIEW_INVALID')
        s.connector_enabled = False
        result = bpy.ops.chest.splitter_suggest_connector_dimensions()
        self.assertEqual(result, {'FINISHED'})
        self.assertAlmostEqual(s.connector_diameter_mm, 3.)
        self.assertAlmostEqual(s.connector_length_mm, 4.5)
        self.assertLessEqual(s.connector_diameter_mm, 4.2 - 2*(.4+.15))
        s.connector_enabled = True
        for side in ('A', 'B'):
            with self.subTest(male_side=side):
                s.connector_male_part = side
                self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'})
                self.assertEqual(s.session_status, 'PREVIEW_VALID')
                self.assertTrue(s.part_a_is_manifold and s.part_b_is_manifold)

    def test_500mm_body_with_100mm2_contact_uses_scene_millimetres(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.object; obj.dimensions = (.01, .01, .5)
        bpy.context.view_layer.update()
        s = bpy.context.scene.chest_splitter
        s.target_object = obj; s.split_mode = 'PLANE'
        s.plane_origin = (0, 0, 0); s.plane_normal = (0, 0, 1)
        s.connector_distribution = 'CENTER'; s.connector_edge_margin_mm = .4
        s.clearance_per_side_mm = .15; s.end_clearance_mm = .2
        clear_prepared_split_cache()
        prepared = prepare_split_candidates(bpy.context, include_solids=True)
        result = recommend_dimensions(prepared, s, obj)
        self.assertAlmostEqual(prepared.interface.area_mm2, 100., delta=.01)
        self.assertAlmostEqual(max(prepared.interface.width_mm, prepared.interface.height_mm), 10., delta=.01)
        self.assertLessEqual(result['diameter_mm'], 10.-2*(.4+.15))
        self.assertGreater(result['receiver_depth_mm'], 249.)
        self.assertLessEqual(result['length_mm'], 50.)

    def test_too_thin_contact_does_not_replace_dimensions(self):
        for vertex in self.obj.data.vertices:
            if vertex.co.z < -.01:vertex.co.z = -.001
        self.obj.data.update()
        self.s.loop_topology_signature = get_topology_signature(self.obj)
        before = (self.s.connector_diameter_mm,self.s.connector_length_mm)
        self.assertEqual(bpy.ops.chest.splitter_suggest_connector_dimensions(), {'CANCELLED'})
        self.assertEqual(before,(self.s.connector_diameter_mm,self.s.connector_length_mm))
        self.assertTrue(self.s.connector_sizing_status)

    def test_interactive_initial_toggle_suggests_but_preserves_delayed_user_edit(self):
        from src import properties
        self.s.connector_enabled = True
        callbacks=[]
        app=SimpleNamespace(background=False,timers=SimpleNamespace(
            register=lambda callback,first_interval:callbacks.append(callback)))
        view=SimpleNamespace(scene=self.scene,area=SimpleNamespace(type='VIEW_3D'),
                             region=SimpleNamespace(type='UI'))
        with patch.object(properties,'bpy',SimpleNamespace(app=app,context=bpy.context)):
            console=SimpleNamespace(scene=self.scene,area=SimpleNamespace(type='CONSOLE'),
                                    region=SimpleNamespace(type='WINDOW'))
            properties._on_connector_enabled(self.s,console)
            self.assertEqual(len(callbacks),0)
            properties._on_connector_enabled(self.s,view)
            self.assertEqual(len(callbacks),1)
            callbacks.pop()()
        self.assertGreaterEqual(self.s.connector_diameter_mm, 1.)
        self.assertGreaterEqual(self.s.connector_length_mm, 2.)
        from src.connector_sizing import automatic_suggestion_current
        self.assertTrue(automatic_suggestion_current(bpy.context))
        self.s.connector_type = 'CAPSULE'
        self.assertFalse(automatic_suggestion_current(bpy.context))
        self.s.connector_type = 'CYLINDER'
        self.assertTrue(automatic_suggestion_current(bpy.context))
        # A pending calculation cannot overwrite an edit made before it runs.
        self.s.connector_male_part = 'B'  # A new cut signature schedules a fresh calculation.
        self.s.connector_dimensions_customized = False
        with patch.object(properties,'bpy',SimpleNamespace(app=app,context=bpy.context)):
            properties._on_connector_enabled(self.s,view)
            self.assertEqual(len(callbacks),1)
            self.s.connector_diameter_mm=3.
            callbacks.pop()()
        self.assertEqual(self.s.connector_diameter_mm,3.)

    def test_complete_contact_keeps_hole_and_adjusts_only_when_requested(self):
        parts = []
        outer = [(-.01,-.01),(.01,-.01),(.01,.01),(-.01,.01)]
        inner = [(-.002,-.002),(.002,-.002),(.002,.002),(-.002,.002)]
        try:
            for sign,z in ((1,0.),(-1,.0001)):
                bm=bmesh.new();parts.append(bm)
                vertices=[bm.verts.new((x,y,z)) for x,y in outer+inner]
                marker=bm.faces.layers.int.new('splitter_contact_surface')
                for i in range(4):
                    j=(i+1)%4
                    face=bm.faces.new([vertices[k] for k in (i,j,4+j,4+i)])
                    if sign<0:face.normal_flip()
                    face[marker]=1
                bm.normal_update()
            patches=complete_contact_pair(*parts,Vector((0,0,1)),1000.,Vector())
            self.assertIsNotNone(patches)
            raw=build_cut_interface(Vector(),Vector((0,0,1)),[],unit_scale=1000.,
                boundary_loops_world=patches[0]['loops'],interface_triangles=patches[0]['triangles'])
            raw.complete_contact_domain=True;raw.final_contact_a,raw.final_contact_b=patches
            prepared=cache_prepared_interface(bpy.context,raw)
            self.assertEqual(len(prepared.interface.hole_contours_uv),1)
            with self.assertRaises(ConnectorValidationError):
                compute_connector_layout(self.obj.data,Matrix.Identity(4),prepared.surface_origin,
                    prepared.surface_normal,'CENTER',.4,1000.,2.,.1,interface=prepared.interface)
            adjusted=compute_connector_layout(self.obj.data,Matrix.Identity(4),prepared.surface_origin,
                prepared.surface_normal,'CENTER',.4,1000.,2.,.1,interface=prepared.interface,adjust_to_valid_area=True)
            self.assertGreater(adjusted['positions'][0].length*1000,3.)
        finally:
            for part in parts:part.free()

    def test_physical_suggestion_is_independent_of_scene_units(self):
        first = recommend_dimensions(prepare_split_candidates(bpy.context, include_solids=True), self.s, self.obj)
        self.obj.data.transform(Matrix.Scale(1000., 4))
        self.scene.unit_settings.scale_length = .001
        self.s.loop_topology_signature = get_topology_signature(self.obj)
        clear_prepared_split_cache()
        second = recommend_dimensions(prepare_split_candidates(bpy.context, include_solids=True), self.s, self.obj)
        self.assertEqual(first['diameter_mm'], second['diameter_mm'])
        self.assertEqual(first['length_mm'], second['length_mm'])

    def test_uv_source_survives_scaled_clearance_and_restore(self):
        uv = self.obj.data.uv_layers.new(name='SurfaceUV')
        attribute = self.obj.data.attributes[uv.name]
        for index, value in enumerate(attribute.data):value.vector = (index/1000., (index%7)/10.)
        original = [tuple(v.vector) for v in attribute.data]
        self.obj.matrix_world = Matrix.Scale(.4,4)
        self.s.loop_topology_signature = get_topology_signature(self.obj)
        def key(point):return tuple(round(float(c),7) for c in point)
        source = self.obj.data
        expected = {frozenset(key(self.obj.matrix_world@source.vertices[i].co) for i in face.vertices):
                    {key(self.obj.matrix_world@source.vertices[source.loops[i].vertex_index].co):original[i]
                     for i in face.loop_indices} for face in source.polygons}
        result = slice_mesh_by_loop(self.obj,self.obj.name,self.ring,self.seed,self.scene,part_clearance_mm=.1)
        try:
            self.assertEqual(original,[tuple(v.vector) for v in self.obj.data.attributes['SurfaceUV'].data])
            self.assertTrue(all(e.is_manifold for part in result for e in part.edges))
            checked=0
            for part in result:
                layer=part.loops.layers.uv.get('SurfaceUV');self.assertIsNotNone(layer)
                marker=part.faces.layers.int.get('splitter_contact_surface')
                for face in part.faces:
                    values=expected.get(frozenset(key(v.co) for v in face.verts))
                    if not values or (marker and face[marker]):continue
                    for loop in face.loops:
                        for actual,wanted in zip(loop[layer].uv,values[key(loop.vert.co)]):
                            self.assertAlmostEqual(actual,wanted,places=6)
                    checked+=1
            self.assertGreater(checked,4)
        finally:
            for part in result:part.free()


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ConnectorDomainSizing))
    if not result.wasSuccessful():raise SystemExit(1)
