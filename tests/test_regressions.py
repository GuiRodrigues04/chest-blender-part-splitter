"""Run with Blender's bpy Python: python tests/test_regressions.py [addon_directory]."""

import sys
import unittest
import importlib
from pathlib import Path

args = (
    sys.argv[sys.argv.index("--") + 1 :]
    if "--" in sys.argv
    else sys.argv[1:]
    if "--python" not in sys.argv
    else []
)
root = Path(args[0]).resolve() if args else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent))
addon = importlib.import_module(root.name)
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

cs = importlib.import_module(root.name + ".src.connector_surface")
gl = importlib.import_module(root.name + ".src.geometry_loop")
gm = importlib.import_module(root.name + ".src.geometry_material")
gs = importlib.import_module(root.name + ".src.geometry_solid")
gc = importlib.import_module(root.name + ".src.geometry_connectors")
contract = importlib.import_module(root.name + ".src.geometry_contract")
life = importlib.import_module(root.name + ".src.lifecycle")
state = importlib.import_module(root.name + ".src.scene_state")
operators = importlib.import_module(root.name + ".src.operators")
addon.register()


def box(name, dims, center=(0, 0, 0)):
    mesh = gs.create_primitive_cutter_mesh(name, "BOX", Vector(dims))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = center
    bpy.context.view_layer.update()
    return obj


def patch(relief=False, nonplanar=False):
    xy = [-20, -12, 12, 20]
    vertices = [
        (x, y, 20 + (4 if nonplanar and i == 1 and j == 1 else 0))
        for j, y in enumerate(xy)
        for i, x in enumerate(xy)
    ]
    vertices += [(x, y, -20) for y in xy for x in xy]
    faces, orange = [], []
    for j in range(3):
        for i in range(3):
            a = j * 4 + i
            quad = (a, a + 1, a + 5, a + 4)
            if i == 1 and j == 1 and relief:
                apex = len(vertices)
                vertices.append((0, 0, 32))
                for k in range(4):
                    orange.append(len(faces))
                    faces.append((quad[k], quad[(k + 1) % 4], apex))
            else:
                if i == 1 and j == 1:
                    orange.append(len(faces))
                faces.append(quad)
            faces.append(tuple(k + 16 for k in reversed(quad)))
    rim = [0, 1, 2, 3, 7, 11, 15, 14, 13, 12, 8, 4]
    for k, a in enumerate(rim):
        b = rim[(k + 1) % len(rim)]
        faces.append((a, a + 16, b + 16, b))
    mesh = bpy.data.meshes.new("patch")
    mesh.from_pydata(vertices, [], faces)
    for name in ("body", "orange"):
        mesh.materials.append(bpy.data.materials.new(name))
    for i in orange:
        mesh.polygons[i].material_index = 1
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:]) if nonplanar else None
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("patch", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return (
        obj,
        [5, 6, 10, 9],
        next(p.index for p in mesh.polygons if p.material_index == 1),
    )


class Regressions(unittest.TestCase):
    def setUp(self):
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        s = bpy.context.scene.chest_splitter
        for prop in s.bl_rna.properties:
            if prop.identifier not in {"rna_type", "name"}:
                try:
                    s.property_unset(prop.identifier)
                except (TypeError, RuntimeError):
                    pass
        s.manual_connectors.clear()
        s.manual_binding = ""
        bpy.context.scene.unit_settings.scale_length = 0.001
        bpy.context.scene.unit_settings.system = "METRIC"
        cs.clear_prepared_split_cache()
        self.s = s

    def cut_patch(self, material, relief=False, nonplanar=False, transform=False):
        obj, loop, seed = patch(relief, nonplanar)
        if transform:
            obj.matrix_world = (
                Matrix.Translation((30, -10, 5))
                @ Euler((0.4, 0.7, 0.2)).to_matrix().to_4x4()
                @ Matrix.Diagonal((1.2, 0.8, 1.1, 1))
            )
        bpy.context.view_layer.update()
        result = (
            gm.slice_mesh_by_material(
                obj, 1, 5, scene=bpy.context.scene, interface_mat_mode="EXTRACTED"
            )
            if material
            else gl.slice_mesh_by_loop_extrude(
                obj, obj.name, loop, seed, 5, scene=bpy.context.scene
            )
        )
        try:
            for bm in (result[0], result[1]):
                self.assertTrue(all(e.is_manifold for e in bm.edges))
                self.assertGreater(abs(bm.calc_volume()), 1)
            original = bmesh.new()
            original.from_mesh(obj.data)
            original.transform(obj.matrix_world)
            volume = abs(original.calc_volume())
            original.free()
            self.assertAlmostEqual(
                abs(result[0].calc_volume()) + abs(result[1].calc_volume()),
                volume,
                delta=volume * 1e-4,
            )
            self.assertTrue(result.interface.is_planar)
        finally:
            result[0].free()
            result[1].free()

    def test_loop_planar_depth(self):
        self.cut_patch(False)

    def test_loop_relief_depth(self):
        self.cut_patch(False, True)

    def test_loop_nonplanar_boundary_depth(self):
        self.cut_patch(False, True, True)

    def test_loop_transformed_depth(self):
        self.cut_patch(False, True, False, True)

    def test_material_planar_depth(self):
        self.cut_patch(True)

    def test_material_relief_depth(self):
        self.cut_patch(True, True)

    def test_material_nonplanar_boundary_depth(self):
        self.cut_patch(True, True, True)

    def test_material_transformed_depth(self):
        self.cut_patch(True, True, False, True)

    def test_loop_depth_colors(self):
        obj, loop, seed = patch(True)
        result = gl.slice_mesh_by_loop_extrude(
            obj, obj.name, loop, seed, 5, scene=bpy.context.scene
        )
        try:
            self.assertTrue(all(f.material_index == 1 for f in result[0].faces))
            self.assertTrue(all(f.material_index == 0 for f in result[1].faces))
        finally:
            result[0].free()
            result[1].free()

    def test_detach_base_colors(self):
        obj, loop, seed = patch(True)
        result = gl.slice_mesh_by_loop(
            obj,
            obj.name,
            loop,
            seed,
            bpy.context.scene,
            detach_add_base=True,
            detach_base_depth_mm=3,
        )
        try:
            self.assertTrue(all(f.material_index == 1 for f in result[0].faces))
            self.assertTrue(all(f.material_index == 0 for f in result[1].faces))
        finally:
            result[0].free()
            result[1].free()

    def solid(self, gap=0, apply="PART", invert=False):
        t = box("body", (40, 40, 40))
        c = box("cutter", (24, 24, 40), (0, 0, 18))
        self.s.target_object = t
        self.s.solid_cutter_object = c
        self.s.split_mode = "SOLID"
        a = bpy.data.meshes.new("a")
        b = bpy.data.meshes.new("b")
        result = gs.slice_mesh_by_solid(
            t.data, t.matrix_world, c, a, b, invert, 1, gap, apply
        )
        return t, c, a, b, result

    def test_solid_nominal(self):
        *_, r = self.solid()
        self.assertAlmostEqual(r["sum_volume_mm3"], 64000, delta=0.1)
        self.assertIsNotNone(r["interface"])

    def test_solid_part_gap(self):
        t, c, a, b, r = self.solid(0.2)
        self.assertLess(r["A"]["volume_mm3"], 12672)
        self.assertAlmostEqual(r["B"]["volume_mm3"], 51328, delta=0.1)
        self.assertAlmostEqual(r["interfaces"]["A"].origin_world.z, -1.8, places=4)
        self.assertAlmostEqual(r["interfaces"]["B"].origin_world.z, -2, places=4)
        self.assertEqual(tuple(c.dimensions), (24, 24, 40))

    def test_solid_cavity_gap(self):
        t, c, a, b, r = self.solid(0.2, "CAVITY")
        self.assertAlmostEqual(r["A"]["volume_mm3"], 12672, delta=0.1)
        self.assertLess(r["B"]["volume_mm3"], 51328)

    def test_solid_both_gap_inverted(self):
        t, c, a, b, r = self.solid(0.2, "BOTH", True)
        self.assertLess(r["sum_volume_mm3"], 64000)
        self.assertGreater(r["interface"].normal_a_to_b_world.z, 0.99)

    def test_deleted_cutter_retained_datablock(self):
        t, c, *_ = self.solid()
        for col in list(c.users_collection):
            col.objects.unlink(c)
        self.assertIn(c.name, bpy.data.objects)
        self.assertFalse(state.object_in_scene(c, bpy.context.scene))
        with self.assertRaises(gs.SolidCutterValidationError):
            gs.validate_solid_cutter(c, t)
        with self.assertRaises(gs.SolidCutterValidationError):
            gs.slice_mesh_by_solid(
                t.data,
                t.matrix_world,
                c,
                bpy.data.meshes.new("a"),
                bpy.data.meshes.new("b"),
            )

    def test_vertex_align_world_with_parent(self):
        t, c, *_ = self.solid()
        parent = bpy.data.objects.new("parent", None)
        bpy.context.scene.collection.objects.link(parent)
        parent.matrix_world = (
            Matrix.Translation((3, 4, 5)) @ Euler((0.2, 0.1, 0.7)).to_matrix().to_4x4()
        )
        c.parent = parent
        c.rotation_euler = (0.1, 0.2, 0.3)
        c.scale = (2, 0.5, 1.1)
        bpy.context.view_layer.update()
        before = c.matrix_world.to_3x3().copy()
        gs.align_vertices(c, t, 2, 5)
        bpy.context.view_layer.update()
        self.assertLess(
            (
                (c.matrix_world @ c.data.vertices[2].co)
                - (t.matrix_world @ t.data.vertices[5].co)
            ).length,
            1e-4,
        )
        for row, brow in zip(c.matrix_world.to_3x3(), before):
            self.assertLess((row - brow).length, 1e-5)

    def test_no_preview_no_explosion(self):
        self.s.target_object = box("body", (40, 40, 40))
        self.s.split_mode = "PLANE"
        self.s.explosion_distance_mm = 100
        p = cs.prepare_split_candidates(bpy.context, True)
        self.assertEqual(cs.get_explosion_display_offset(self.s, p).length, 0)

    def test_cut_change_invalidates_markers(self):
        self.s.target_object = box("body", (40, 40, 40))
        self.s.split_mode = "PLANE"
        cs.prepare_split_candidates(bpy.context, True)
        self.s.plane_offset_mm = 2
        self.assertIsNone(cs.get_cached_prepared_split())

    def test_loop_change_does_not_reuse_manual_pins(self):
        obj, loop, seed = patch(True)
        s = self.s
        s.target_object = obj
        s.split_mode = "MATERIAL"
        s.material_split_index = 1
        s.material_extraction_mode = "BASE"
        cs.prepare_split_candidates(bpy.context, True)
        s.manual_connectors.add().u_mm = 4
        # New region identity: keep a different domain, never reuse stale coordinates.
        s.split_mode = "PLANE"
        cs.prepare_split_candidates(bpy.context, True)
        self.assertEqual(len(s.manual_connectors), 0)

    def test_nonplanar_pin_position_lifted(self):
        n = Vector((0, 0, 1))
        pts = [
            Vector((-10, -10, 0)),
            Vector((10, -10, 0)),
            Vector((10, 10, 4)),
            Vector((-10, 10, 0)),
        ]
        iface = contract.build_cut_interface(
            Vector(), n, pts, [(pts[0], pts[1], pts[2]), (pts[0], pts[2], pts[3])], 1
        )
        self.assertFalse(iface.is_planar)
        uv = iface.world_to_uv(Vector((0, 0, 2)))
        self.assertAlmostEqual(contract.interface_point(iface, *uv).z, 2, places=4)
        p = gc.compute_connector_layout(
            None,
            Matrix.Identity(4),
            Vector(),
            n,
            "MANUAL",
            0,
            1,
            2,
            0.15,
            iface,
            manual_specs=[{"u_mm": uv[0], "v_mm": uv[1]}],
        )
        self.assertAlmostEqual(p["positions"][0].z, 2, places=4)
        self.assertGreater((p["pin_rotations"][0].to_matrix() @ n).dot(n), 0.99999)

    def test_two_pins_concave_u(self):
        pts = [
            (-25, -20),
            (25, -20),
            (25, 20),
            (12, 20),
            (12, -8),
            (-12, -8),
            (-12, 20),
            (-25, 20),
        ]
        iface = contract.build_cut_interface(
            Vector(),
            Vector((0, 0, 1)),
            [Vector((x, y, 0)) for x, y in pts],
            unit_scale=1,
        )
        layout = gc.compute_connector_layout(
            None,
            Matrix.Identity(4),
            Vector(),
            Vector((0, 0, 1)),
            "LINEAR_2",
            2,
            1,
            4,
            0.15,
            iface,
        )
        self.assertEqual(len(layout["positions"]), 2)
        gc.validate_connectors(layout["positions"], 4, 0.15, 1)

    def test_rotations_for_b_male(self):
        iface = contract.build_cut_interface(
            Vector(),
            Vector((0.2, 0.5, 0.7)),
            [
                Vector((-20, -20, 0)),
                Vector((20, -20, 0)),
                Vector((20, 20, 0)),
                Vector((-20, 20, 0)),
            ],
            unit_scale=1,
        )
        n = -iface.normal_a_to_b_world
        layout = gc.compute_connector_layout(
            None, Matrix.Identity(4), Vector(), n, "CENTER", 1, 1, 2, 0.15, iface
        )
        axis = layout["pin_rotations"][0].to_matrix() @ Vector((0, 0, 1))
        self.assertGreater(axis.dot(n), 0.99999)

    def preview_pins(self, solid=False, gap=0):
        s = self.s
        if solid:
            self.solid()
        else:
            s.target_object = box("body", (40, 40, 40))
            s.split_mode = "PLANE"
        s.view_mode = "EXPLODED"
        s.part_clearance_mm = gap
        s.connector_enabled = True
        s.connector_distribution = "MANUAL"
        self.assertEqual(bpy.ops.chest.splitter_edit_manual_connectors(), {"FINISHED"})
        s.manual_connectors.add()
        self.assertEqual(
            bpy.ops.chest.splitter_confirm_manual_connectors(), {"FINISHED"}
        )
        self.assertEqual(s.session_status, "PREVIEW_VALID")
        prep = cs.get_cached_prepared_split()
        self.assertIsNotNone(prep)
        bpy.context.view_layer.update()
        delta = cs.get_explosion_display_offset(s, prep)
        self.assertGreater(delta.length, 0)
        self.assertTrue(life.remove_preview(bpy.context, op_id=s.session_id)[0])
        self.assertEqual(cs.get_explosion_display_offset(s, prep).length, 0)
        self.assertEqual(bpy.ops.chest.splitter_edit_manual_connectors(), {"FINISHED"})
        self.assertEqual(
            cs.get_explosion_display_offset(s, cs.get_cached_prepared_split()).length, 0
        )

    def test_plane_manual_preview_cancel_reedit(self):
        self.preview_pins()

    def test_solid_manual_preview_cancel_reedit(self):
        self.preview_pins(True)

    def test_plane_manual_with_gap(self):
        self.preview_pins(False, 0.2)

    def test_solid_manual_with_gap(self):
        self.preview_pins(True, 0.2)

    def test_all_automatic_distributions(self):
        obj = box("body", (80, 60, 40))
        self.s.target_object = obj
        prep = cs.prepare_split_candidates(bpy.context, True)
        for dist, count in [
            ("CENTER", 1),
            ("LINEAR_2", 2),
            ("LINEAR_3", 3),
            ("GRID_4", 4),
        ]:
            self.s.connector_distribution = dist
            layout = cs.prepared_connector_layout(prep, self.s, obj)
            self.assertEqual(len(layout["positions"]), count)
            self.assertIs(layout, cs.prepared_connector_layout(prep, self.s, obj))
            gc.validate_connectors(layout["positions"], 6, 0.15, 1)

    def test_solid_moving_grid_follows_face(self):
        t, c, *_ = self.solid()
        p1 = cs.prepare_split_candidates(bpy.context, True)
        point1 = p1.uv_mm_to_world(0, 0)
        c.location.x += 3
        c.location.z -= 1
        bpy.context.view_layer.update()
        p2 = cs.prepare_split_candidates(bpy.context, True)
        self.assertNotEqual(p1.cut_signature, p2.cut_signature)
        self.assertAlmostEqual(p2.surface_origin.z, p1.surface_origin.z - 1, places=4)
        self.assertAlmostEqual(p2.surface_origin.x, p1.surface_origin.x + 3, places=4)
        self.assertEqual(len(cs.generate_positioning_grid_points(p2)) > 0, True)

    def test_solid_selected_face(self):
        t, c, *_ = self.solid()
        face = next(f for f in c.data.polygons if f.normal.x > 0.99)
        self.s.solid_interface_face_index = face.index
        prep = cs.prepare_split_candidates(bpy.context, True)
        self.assertGreater(prep.surface_normal.x, 0.99)
        self.assertAlmostEqual(prep.surface_origin.x, 12, places=4)

    def test_solid_face_capture_operator(self):
        t, c, *_ = self.solid()
        bpy.context.view_layer.objects.active = c
        c.select_set(True)
        for f in c.data.polygons:
            f.select = False
        idx = next(f.index for f in c.data.polygons if f.normal.x > 0.99)
        c.data.polygons[idx].select = True
        bpy.ops.object.mode_set(mode="EDIT")
        self.assertEqual(bpy.ops.chest.splitter_capture_solid_face(), {"FINISHED"})
        self.assertEqual(self.s.solid_interface_face_index, idx)
        bpy.ops.object.mode_set(mode="OBJECT")

    def test_vertex_operator(self):
        t, c, *_ = self.solid()
        self.assertEqual(
            bpy.ops.chest.splitter_align_solid_vertices(
                cutter_vertex=0, target_vertex=3
            ),
            {"FINISHED"},
        )
        self.assertLess(
            (
                (c.matrix_world @ c.data.vertices[0].co)
                - (t.matrix_world @ t.data.vertices[3].co)
            ).length,
            1e-4,
        )

    def test_solid_nonuniform_scale_gap(self):
        t, c, *_ = self.solid()
        c.scale = (0.8, 1.1, 0.9)
        c.rotation_euler = (0.1, 0.3, 0.2)
        bpy.context.view_layer.update()
        a = bpy.data.meshes.new("newa")
        b = bpy.data.meshes.new("newb")
        r = gs.slice_mesh_by_solid(
            t.data, t.matrix_world, c, a, b, unit_scale=1, part_clearance_mm=0.2
        )
        self.assertTrue(r["A"]["is_manifold"])
        self.assertTrue(r["B"]["is_manifold"])
        self.assertLess(r["sum_volume_mm3"], 64000)

    def test_depth_thickness_excess_rejected(self):
        obj, loop, seed = patch()
        with self.assertRaises(ValueError):
            gl.slice_mesh_by_loop_extrude(
                obj, obj.name, loop, seed, 50, scene=bpy.context.scene
            )
        with self.assertRaises(ValueError):
            gm.slice_mesh_by_material(obj, 1, 50, scene=bpy.context.scene)

    def test_depth_through_cut_preserved(self):
        obj, loop, seed = patch()
        result = gl.slice_mesh_by_loop_extrude(
            obj, obj.name, loop, seed, 50, True, bpy.context.scene
        )
        try:
            self.assertTrue(all(e.is_manifold for e in result[0].edges))
            self.assertTrue(all(e.is_manifold for e in result[1].edges))
        finally:
            result[0].free()
            result[1].free()

    def test_material_base_preserved(self):
        obj, loop, seed = patch(True)
        r = gm.slice_mesh_by_material(
            obj, 1, 5, scene=bpy.context.scene, extraction_mode="BASE"
        )
        try:
            self.assertTrue(r.split_result.part_a_metrics["is_manifold"])
            self.assertAlmostEqual(
                r.split_result.part_a_metrics["volume_mm3"], 2304, delta=0.1
            )
        finally:
            r[0].free()
            r[1].free()

    def test_material_manual_preview(self):
        obj, loop, seed = patch(True)
        s = self.s
        s.target_object = obj
        s.split_mode = "MATERIAL"
        s.material_split_index = 1
        s.material_extrude_depth_mm = 5
        s.connector_enabled = True
        s.connector_distribution = "MANUAL"
        self.assertEqual(bpy.ops.chest.splitter_edit_manual_connectors(), {"FINISHED"})
        s.manual_connectors.add()
        self.assertEqual(
            bpy.ops.chest.splitter_confirm_manual_connectors(), {"FINISHED"}
        )
        self.assertEqual(s.session_status, "PREVIEW_VALID")

    def test_loop_manual_preview(self):
        obj, loop, seed = patch(True)
        s = self.s
        s.target_object = obj
        s.split_mode = "LOOP"
        s.loop_vertex_indices = ",".join(map(str, loop))
        s.loop_seed_face_index = seed
        s.loop_is_captured = True
        s.loop_topology_signature = gl.get_topology_signature(obj)
        s.loop_behavior = "EXTRUDE"
        s.loop_extrude_depth_mm = 5
        s.connector_enabled = True
        s.connector_distribution = "MANUAL"
        self.assertEqual(bpy.ops.chest.splitter_edit_manual_connectors(), {"FINISHED"})
        s.manual_connectors.add()
        self.assertEqual(
            bpy.ops.chest.splitter_confirm_manual_connectors(), {"FINISHED"}
        )
        self.assertEqual(s.session_status, "PREVIEW_VALID")

    def test_prepare_preview_cancel_does_not_move_marker(self):
        obj = box("body", (40, 40, 40))
        s = self.s
        s.target_object = obj
        s.connector_enabled = True
        s.connector_distribution = "CENTER"
        s.view_mode = "EXPLODED"
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {"FINISHED"})
        self.assertTrue(life.remove_preview(bpy.context, op_id=s.session_id)[0])
        p = cs.prepare_split_candidates(bpy.context, True)
        self.assertEqual(cs.get_explosion_display_offset(s, p).length, 0)
        self.assertLess(p.uv_mm_to_world(0, 0).length, 1e-5)

    def test_commit_revert_preserved(self):
        s = self.s
        t = box("body", (40, 40, 40))
        s.target_object = t
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {"FINISHED"})
        self.assertEqual(bpy.ops.chest.splitter_commit_parts(), {"FINISHED"})
        self.assertEqual(s.session_status, "COMMITTED")
        self.assertEqual(bpy.ops.chest.splitter_revert_cut(), {"FINISHED"})
        self.assertTrue(state.object_in_scene(t, bpy.context.scene))
        self.assertEqual(len(t.data.vertices), 8)

    def test_failure_preserves_previous_preview(self):
        self.solid()
        s = self.s
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {"FINISHED"})
        before = {
            o.as_pointer()
            for o in bpy.context.scene.objects
            if o.get("chest_role") in ("PREVIEW_A", "PREVIEW_B")
        }
        self.assertEqual(len(before), 2)
        s.solid_cutter_object.location.x = 500
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {"CANCELLED"})
        after = {
            o.as_pointer()
            for o in bpy.context.scene.objects
            if o.get("chest_role") in ("PREVIEW_A", "PREVIEW_B")
        }
        self.assertEqual(before, after)

    def test_solid_operand_cleanup_success_failure(self):
        self.solid()
        self.assertFalse(any(o.name.startswith("_solid_") for o in bpy.data.objects))
        s = self.s
        t = s.target_object
        c = s.solid_cutter_object
        with self.assertRaises(gs.SolidSliceError):
            gs.slice_mesh_by_solid(
                t.data,
                t.matrix_world,
                c,
                bpy.data.meshes.new("a"),
                bpy.data.meshes.new("b"),
                unit_scale=1,
                part_clearance_mm=100,
            )
        self.assertFalse(any(o.name.startswith("_solid_") for o in bpy.data.objects))
        self.assertFalse(any(m.name.startswith("_solid_") for m in bpy.data.meshes))

    def test_manual_binding_survives_reprepare(self):
        self.s.target_object = box("body", (40, 40, 40))
        s = self.s
        s.split_mode = "PLANE"
        p = cs.prepare_split_candidates(bpy.context, True)
        s.manual_connectors.add().u_mm = 5
        cs.clear_prepared_split_cache()
        cs.prepare_split_candidates(bpy.context, True)
        self.assertEqual(len(s.manual_connectors), 1)
        self.assertAlmostEqual(s.manual_connectors[0].u_mm, 5)

    def test_scene_delete_invalidates_preview(self):
        self.solid()
        s = self.s
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {"FINISHED"})
        for col in list(s.solid_cutter_object.users_collection):
            col.objects.unlink(s.solid_cutter_object)
        bpy.context.view_layer.update()
        self.assertNotEqual(s.session_status, "PREVIEW_VALID")
        self.assertIsNone(cs.get_cached_prepared_split())

    def test_hole_rejected_in_layout(self):
        outer = [
            Vector((x, y, 0)) for x, y in [(-20, -20), (20, -20), (20, 20), (-20, 20)]
        ]
        hole = [Vector((x, y, 0)) for x, y in [(-4, -4), (-4, 4), (4, 4), (4, -4)]]
        iface = contract.build_cut_interface(
            Vector(),
            Vector((0, 0, 1)),
            [],
            unit_scale=1,
            boundary_loops_world=[outer, hole],
        )
        self.assertEqual(len(iface.hole_contours_uv), 1)
        uv = iface.world_to_uv(Vector())
        r = gc.compute_connector_layout(
            None,
            Matrix.Identity(4),
            Vector(),
            Vector((0, 0, 1)),
            "MANUAL",
            0,
            1,
            2,
            0.1,
            iface,
            manual_specs=[{"u_mm": uv[0], "v_mm": uv[1]}],
        )
        self.assertFalse(r["manual_eval_results"][0]["is_valid"])

    def test_ui_controls_registered_all_modes(self):
        from types import SimpleNamespace

        ui = importlib.import_module(root.name + ".src.ui")
        panel = next(
            c
            for c in vars(ui).values()
            if isinstance(c, type)
            and c is not bpy.types.Panel
            and issubclass(c, bpy.types.Panel)
        )

        class Layout:
            def row(self, *a, **kw):
                return self

            column = box = split = grid_flow = row

            def label(self, *a, **kw):
                pass

            def separator(self, *a, **kw):
                pass

            def prop(self, obj, name, *a, **kw):
                getattr(obj, name)

            def operator(self, name, *a, **kw):
                namespace, op = name.split(".")
                getattr(getattr(bpy.ops, namespace), op).get_rna_type()
                return SimpleNamespace()

            def template_list(self, *a, **kw):
                pass

        self.solid()
        for mode in ("PLANE", "SOLID", "LOOP", "MATERIAL"):
            self.s.split_mode = mode
            self.s.connector_enabled = True
            self.s.connector_distribution = "MANUAL"
            panel.draw(SimpleNamespace(layout=Layout()), bpy.context)

    def test_solid_uv_rotates_with_cutter(self):
        t, c, *_ = self.solid()
        p1 = cs.prepare_split_candidates(bpy.context, True)
        axis = p1.axis_u.copy()
        c.rotation_euler.z = 0.4
        bpy.context.view_layer.update()
        p2 = cs.prepare_split_candidates(bpy.context, True)
        expected = Matrix.Rotation(0.4, 3, "Z") @ axis
        self.assertGreater(expected.dot(p2.axis_u), 0.99999)

    def test_square_interface_frame_stable(self):
        pts = [
            Vector((-10, -10, 0)),
            Vector((10, -10, 0)),
            Vector((10, 10, 0)),
            Vector((-10, 10, 0)),
        ]
        a = contract.build_cut_interface(Vector(), Vector((0, 0, 1)), pts, unit_scale=1)
        for k in range(4):
            b = contract.build_cut_interface(
                Vector(), Vector((0, 0, 1)), pts[k:] + pts[:k], unit_scale=1
            )
            self.assertGreater(a.axis_u_world.dot(b.axis_u_world), 0.99999)

    def test_capsule_marker_axis_matches_geometry(self):
        obj = box("body", (50, 40, 40))
        self.s.target_object = obj
        self.s.connector_type = "CAPSULE"
        self.s.connector_capsule_length_mm = 10
        prep = cs.prepare_split_candidates(bpy.context, True)
        for yaw in (0, 37, 90):
            spec = dict(u_mm=0, v_mm=0, yaw_deg=yaw)
            result = gc.compute_connector_layout(
                obj.data,
                obj.matrix_world,
                prep.surface_origin,
                prep.surface_normal,
                "MANUAL",
                1,
                1,
                4,
                0.15,
                prep.interface,
                "CAPSULE",
                10,
                False,
                [spec],
            )
            import math

            expected = (
                math.cos(math.radians(yaw)) * prep.axis_u
                + math.sin(math.radians(yaw)) * prep.axis_v
            )
            actual = result["pin_rotations"][0].to_matrix() @ Vector((0, 1, 0))
            self.assertGreater(actual.dot(expected), 0.99999)

    def test_solid_auto_face_button(self):
        self.solid()
        cs.prepare_split_candidates(bpy.context, True)
        self.assertGreaterEqual(self.s.solid_interface_face_index, 0)
        self.assertEqual(bpy.ops.chest.splitter_auto_solid_face(), {"FINISHED"})
        self.assertEqual(self.s.solid_interface_face_index, -1)
    def test_view_alignment_smart_and_flip(self):
        import math
        ce = importlib.import_module(root.name + ".src.connector_editor")
        
        class DummyRegion3D:
            def __init__(self, quat, loc, dist=1.0):
                self.view_rotation = quat.copy()
                self.view_location = loc.copy()
                self.view_distance = dist
                self.view_perspective = 'PERSP'

        class DummySpace:
            def __init__(self, r3d):
                self.type = 'VIEW_3D'
                self.region_3d = r3d

        class DummyArea:
            def __init__(self, space):
                self.type = 'VIEW_3D'
                self.spaces = type('Spaces', (), {'active': space})()
            def tag_redraw(self):
                pass

        class DummyPrep:
            def __init__(self, normal):
                self.surface_normal = normal.copy()
                self.surface_origin = Vector((0.0, 0.0, 0.0))
                self.interface = None
                self.unit_scale = 1000.0

        # Caso 1: Normal vertical (0, 0, 1). Observador olhando de baixo para cima (view_dir.z > 0)
        # Quat olhando para cima: (w=0, x=1, y=0, z=0) -> cam_z = (0, 0, -1), view_dir = (0, 0, 1)
        # Simulamos o usuário levemente inclinado olhando de baixo:
        q_looking_up = Euler((math.radians(110), 0, 0)).to_quaternion()
        r3d = DummyRegion3D(q_looking_up, Vector((0, 0, 0)), 1.0)
        area = DummyArea(DummySpace(r3d))
        prep = DummyPrep(Vector((0.0, 0.0, 1.0)))

        # Alinhamento inteligente: deve manter a visão vindo de baixo, SEM pular para trás do bloco!
        success = ce.align_viewport_to_cut_surface(area, prep)
        self.assertTrue(success)
        curr_view_dir = -(r3d.view_rotation.to_matrix().col[2])
        self.assertGreater(curr_view_dir.dot(Vector((0, 0, 1))), 0.99)

        # Segundo clique/chamada estando já alinhado: deve alternar (toggle 180°) para o topo
        success = ce.align_viewport_to_cut_surface(area, prep)
        self.assertTrue(success)
        curr_view_dir = -(r3d.view_rotation.to_matrix().col[2])
        self.assertGreater(curr_view_dir.dot(Vector((0, 0, -1))), 0.99)

        # Inversão explícita com flip=True: deve retornar para olhar de baixo
        success = ce.align_viewport_to_cut_surface(area, prep, flip=True)
        self.assertTrue(success)
        curr_view_dir = -(r3d.view_rotation.to_matrix().col[2])
        self.assertGreater(curr_view_dir.dot(Vector((0, 0, 1))), 0.99)

        # Verificação de rotação para superfícies angulares e horizontais (zero roll, horizonte nivelado)
        for test_norm in [Vector((0, 1, 0)), Vector((1, 0, 0)), Vector((1, 1, 0.5)).normalized()]:
            prep_angled = DummyPrep(test_norm)
            success = ce.align_viewport_to_cut_surface(area, prep_angled)
            self.assertTrue(success)
            mat = r3d.view_rotation.to_matrix()
            self.assertAlmostEqual(mat.determinant(), 1.0, places=4)
            self.assertAlmostEqual(mat.col[0].z, 0.0, places=4)  # cam_x.z == 0 garante zero roll
            self.assertGreaterEqual(mat.col[1].z, -1e-4)        # cam_y.z >= 0 garante up positivo


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Regressions)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    addon.unregister()
    sys.exit(0 if result.wasSuccessful() else 1)
