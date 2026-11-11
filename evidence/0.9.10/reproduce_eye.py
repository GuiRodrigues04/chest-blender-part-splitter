"""Reproduce the user's eye spot LOOP clearance failure without saving the source blend."""
import sys, json, traceback, hashlib
from pathlib import Path
import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[2]
BLEND = Path(r"C:\Users\guiro\OneDrive\Desktop\Spot corte bugado.blend")
sys.path.insert(0, str(REPO))
import src
src.register()

bpy.ops.wm.open_mainfile(filepath=str(BLEND), use_scripts=False)
# Re-register after opening the file, then expose the same root import alias as
# the installed-extension evidence driver (the source tree is the tested addon).
if not hasattr(bpy.types.Scene, 'chest_splitter'):
    src.register()
for name, module in list(sys.modules.items()):
    if name == 'src' or name.startswith('src.'):
        sys.modules.setdefault('src' + name[3:], module)

scene = bpy.context.scene
settings = scene.chest_splitter

def obj_name(value):
    return getattr(value, 'name', None)

initial = {
    'blend': str(BLEND),
    'scene': scene.name,
    'target': obj_name(getattr(settings, 'target_object', None)),
    'split_mode': getattr(settings, 'split_mode', None),
    'loop_behavior': getattr(settings, 'loop_behavior', None),
    'loop_is_captured': getattr(settings, 'loop_is_captured', None),
    'loop_vertex_count': getattr(settings, 'loop_vertex_count', None),
    'loop_vertex_indices': getattr(settings, 'loop_vertex_indices', None),
    'loop_seed_face_index': getattr(settings, 'loop_seed_face_index', None),
    'loop_extrude_depth_mm': getattr(settings, 'loop_extrude_depth_mm', None),
    'part_clearance_mm': getattr(settings, 'part_clearance_mm', None),
    'part_clearance_bottom_enable': getattr(settings, 'part_clearance_bottom_enable', None),
    'part_clearance_bottom_mm': getattr(settings, 'part_clearance_bottom_mm', None),
    'connector_enabled': getattr(settings, 'connector_enabled', None),
    'pins': getattr(settings, 'connector_enabled', None),
}
print('SCENE_STATE=' + json.dumps(initial, ensure_ascii=False, default=str), flush=True)

from src.geometry_loop import validate_capture
from src.operators import get_current_session_parts
from src.diagnostic import get_scene_scale_to_mm, validate_bmesh_mesh_geometry
import bmesh
from mathutils.bvhtree import BVHTree

def source_signature(mesh):
    uv_values = []
    for layer in mesh.uv_layers:
        attribute = mesh.attributes.get(layer.name)
        uv_values.append([tuple(entry.vector) for entry in attribute.data] if attribute else
                         [tuple(loop.uv) for loop in layer.data])
    payload = {
        'vertices': [tuple(v.co) for v in mesh.vertices],
        'polygons': [tuple(p.vertices) for p in mesh.polygons],
        'uv': uv_values,
        'materials': [m.name if m else None for m in mesh.materials],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

def source_snapshot(mesh):
    uv_values = []
    uv_lengths = []
    for layer in mesh.uv_layers:
        attribute = mesh.attributes.get(layer.name)
        data = attribute.data if attribute else layer.data
        uv_values.append([tuple(entry.vector) for entry in data] if attribute else
                         [tuple(loop.uv) for loop in data])
        uv_lengths.append(len(data))
    return {'data_name': mesh.name, 'vertices': [tuple(v.co) for v in mesh.vertices],
            'polygons': [tuple(p.vertices) for p in mesh.polygons],
            'uv': uv_values, 'uv_lengths': uv_lengths, 'loop_count': len(mesh.loops),
            'materials': [m.name if m else None for m in mesh.materials]}

def part_metrics(obj, scale):
    bm = bmesh.new(); bm.from_mesh(obj.data); bm.normal_update()
    try:
        remaining = set(bm.faces); components = 0
        while remaining:
            components += 1; todo = [remaining.pop()]
            while todo:
                f = todo.pop()
                for e in f.edges:
                    for neighbor in e.link_faces:
                        if neighbor in remaining:
                            remaining.remove(neighbor); todo.append(neighbor)
        report = validate_bmesh_mesh_geometry(bm, scale)
        marks = obj.data.attributes.get('splitter_contact_surface')
        marked_faces = sum(bool(marks.data[p.index].value) for p in obj.data.polygons) if marks else 0
        return {'name': obj.name, 'vertices': len(bm.verts), 'faces': len(bm.faces),
                'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
                'components': components, 'volume_mm3': abs(bm.calc_volume())*scale**3,
                'valid_report': report, 'uv_layers': len(obj.data.uv_layers),
                'marked_contact_faces': marked_faces,
                'attributes': [a.name for a in obj.data.attributes]}
    finally: bm.free()

# Independent trials reload the original blend; no generated result is saved.
input_hash_before = hashlib.sha256(BLEND.read_bytes()).hexdigest()
case_rows = []
for trial, gap in enumerate((0.1, 0.0, 0.2, 1.0)):
    if trial:
        bpy.ops.wm.open_mainfile(filepath=str(BLEND), use_scripts=False)
    scene = bpy.context.scene
    settings = scene.chest_splitter
    obj = getattr(settings, 'target_object', None)
    capture_validation = validate_capture(obj, settings, bpy.context) if obj else (False, 'no target')
    print('VALIDATE=' + json.dumps(capture_validation, ensure_ascii=False), flush=True)
    scale = get_scene_scale_to_mm(scene)
    if obj.mode == 'EDIT':
        obj.update_from_editmode()
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='OBJECT')
    source_before = source_snapshot(obj.data)
    source_sig_before = source_signature(obj.data)
    source_mesh_id = obj.data.as_pointer()
    settings.part_clearance_mm = gap
    print('CASE_START=' + json.dumps({'gap_mm': gap}), flush=True)
    try:
        result = bpy.ops.chest.splitter_generate_preview()
        parts = get_current_session_parts(scene)
        metrics = [part_metrics(part, scale) for part in parts]
        if obj.mode == 'EDIT':
            obj.update_from_editmode()
        source_after = source_snapshot(obj.data)
        uv_diffs = []
        for layer_index in range(min(len(source_before['uv']), len(source_after['uv']))):
            before_uv = source_before['uv'][layer_index]; after_uv = source_after['uv'][layer_index]
            for loop_index, (before_uv_value, after_uv_value) in enumerate(zip(before_uv, after_uv)):
                if before_uv_value != after_uv_value:
                    uv_diffs.append({'layer': layer_index, 'loop': loop_index,
                                     'before': before_uv_value, 'after': after_uv_value})
                    if len(uv_diffs) >= 8: break
            if len(uv_diffs) >= 8: break
        source_deltas = {key: {'before': len(source_before[key]) if isinstance(source_before[key], list) else source_before[key],
                               'after': len(source_after[key]) if isinstance(source_after[key], list) else source_after[key],
                               'equal': source_before[key] == source_after[key]}
                         for key in source_before if source_before[key] != source_after[key]}
        marked = []
        signed_marked = []
        interface_origin = Vector(settings.loop_interface_origin)
        interface_normal = Vector(settings.loop_interface_normal)
        if interface_normal.length:
            interface_normal.normalize()
        for part in parts:
            attr = part.data.attributes.get('splitter_contact_surface')
            tris = [tuple(t.vertices) for t in part.data.loop_triangles
                    if attr and attr.data[t.polygon_index].value]
            below_tris = [tuple(t.vertices) for t in part.data.loop_triangles
                          if attr and attr.data[t.polygon_index].value and
                          ((part.matrix_world @ part.data.polygons[t.polygon_index].center - interface_origin).dot(interface_normal) < 0)]
            marked.append((part, tris, below_tris))
            signed_marked.append(sorted(((part.matrix_world @ poly.center - interface_origin).dot(interface_normal)
                                         for poly in part.data.polygons
                                         if attr and attr.data[poly.index].value)))
        spacing = {}
        if len(marked) == 2 and marked[0][2] and marked[1][1]:
            target, target_tris, _ = marked[1]
            target_bvh = BVHTree.FromPolygons([tuple(v.co) for v in target.data.vertices], target_tris,
                                              all_triangles=True)
            source_part, _, below_tris = marked[0]
            vertex_ids = sorted({v for tri in below_tris for v in tri})
            distances = sorted((target_bvh.find_nearest(source_part.data.vertices[i].co)[3] or 0)*scale
                               for i in vertex_ids)
            if distances:
                spacing['A_to_B_below_shoulder'] = {
                    'samples': len(distances), 'min_mm': distances[0],
                    'p50_mm': distances[len(distances)//2], 'p90_mm': distances[int(.9*(len(distances)-1))],
                    'max_mm': distances[-1]}
        case_row = {'gap_mm': gap, 'operator': str(result), 'last_status': settings.last_status,
              'capture_valid': bool(capture_validation[0]), 'parts': metrics, 'marked_surface_spacing': spacing, 'source_signature_unchanged': source_signature(obj.data)==source_sig_before,
              'source_data_pointer_unchanged': obj.data.as_pointer()==source_mesh_id, 'source_deltas': source_deltas,
              'source_uv_first_differences': uv_diffs,
              'source_buffer_sizes': {'before': {'loops': source_before['loop_count'], 'uv': source_before['uv_lengths']},
                                      'after': {'loops': source_after['loop_count'], 'uv': source_after['uv_lengths']},
                                      'mode': obj.mode},
              'marked_face_signed_distance_bu': [{'min': values[0], 'p50': values[len(values)//2], 'max': values[-1]} if values else None for values in signed_marked],
              'interface_origin': list(settings.loop_interface_origin), 'interface_normal': list(settings.loop_interface_normal)}
        case_rows.append(case_row)
        print('CASE_RESULT=' + json.dumps(case_row, ensure_ascii=False), flush=True)
    except Exception as exc:
        case_row = {'gap_mm': gap, 'error': repr(exc), 'traceback': traceback.format_exc()}
        case_rows.append(case_row)
        print('CASE_ERROR=' + json.dumps(case_row, ensure_ascii=False), flush=True)

input_hash_after = hashlib.sha256(BLEND.read_bytes()).hexdigest()
results_path = Path(__file__).with_name('real_results.json')
results_path.write_text(json.dumps({'blend': str(BLEND), 'sha256_before': input_hash_before,
                                   'sha256_after': input_hash_after, 'cases': case_rows},
                                  ensure_ascii=False, indent=2), encoding='utf-8')
assert input_hash_before == input_hash_after, 'The original blend file changed during reproduction.'
assert input_hash_before.lower() == '66f7213e14b5867b7f7bb453ee3d88b1fe7af6d43b6de99f6dda12c061d847de'
for row in case_rows:
    assert row.get('operator') == "{'FINISHED'}", row
    assert row.get('capture_valid'), row
    assert row.get('source_signature_unchanged') and row.get('source_data_pointer_unchanged'), row
    assert not row.get('source_deltas') and not row.get('source_uv_first_differences'), row
    assert len(row['parts']) == 2 and all(p['components'] == 1 and p['nonmanifold_edges'] == 0 and
                                             p['valid_report']['is_valid'] for p in row['parts']), row
expected_gap = {round(row['gap_mm'], 3): row for row in case_rows}
for requested, target in ((0.0, 0.0), (0.1, 0.1), (0.2, 0.2), (1.0, 1.0)):
    measured = expected_gap[requested]['marked_surface_spacing']['A_to_B_below_shoulder']['p90_mm']
    assert abs(measured-target) <= max(0.01, target*0.02), (requested, measured)
print('REAL_EYE_REGRESSION_OK=' + str(results_path), flush=True)
