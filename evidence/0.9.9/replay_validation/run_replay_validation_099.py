"""Physical repeat-preview validation for all ten LOOP/AUTO .15 mm cases."""
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
import bpy
import src
from test_release_workflows import ReleaseWorkflows, capture_preview_geometry, repeated_preview_metrics
from src.geometry_loop import analyze_loop_region
from mathutils import Vector


def source_signature(obj):
    mesh = obj.data
    return {
        'coordinates': tuple(tuple(v.co) for v in mesh.vertices),
        'faces': tuple(tuple(p.vertices) for p in mesh.polygons),
        'face_material_indices': tuple(p.material_index for p in mesh.polygons),
        'material_slots': tuple((m.name, tuple(m.diffuse_color)) if m else None for m in mesh.materials),
        'matrix_world': tuple(tuple(row) for row in obj.matrix_world),
        'uv_layers': tuple((layer.name, tuple(tuple(float(c) for c in data.uv) for data in layer.data))
                           for layer in mesh.uv_layers),
    }


def main():
    src.register()
    ReleaseWorkflows.setUpClass()
    report = {'phase': 'repeat_preview_validation', 'blender_version': bpy.app.version_string,
              'precision': {'face_coordinate_rounding_mm': 1e-6, 'triangle_coordinate_rounding_mm': 1e-6,
                            'face_uv_rounding': 1e-7,
                            'vertex_bijection_tolerance_mm': .001,
                            'face_semantics': 'oriented cyclic vertex indices after bijection, material index, all UV layers',
                            'surface_tolerance_mm': .001, 'bbox_tolerance_mm': .001,
                            'volume_tolerance_mm3': 'max(0.001, abs(per-part volume) * 1e-6); total volume uses same relative tolerance'},
              'cases': []}
    for item in ReleaseWorkflows.items:
        for depth in (1, 2, 5, 10, 15):
            row = {'body': item['name'], 'route': 'LOOP', 'behavior': 'AUTO',
                   'gap_mm': .15, 'depth_mm': depth}
            case = ReleaseWorkflows()
            try:
                case.setup_case(item, 'LOOP', 'AUTO', .15)
                case.s.loop_extrude_depth_mm = depth
                row['configured_gap_mm'] = case.s.part_clearance_mm
                row['gap_applies_to'] = case.s.part_clearance_apply_to
                original_source = source_signature(case.target)
                analysis = analyze_loop_region(
                    case.target, [int(i) for i in case.s.loop_vertex_indices.split(',') if i.strip()],
                    case.s.loop_seed_face_index, bpy.context.scene)
                row['max_avail_depth_mm'] = analysis['max_avail_depth_mm']
                if depth > analysis['max_avail_depth_mm'] + 1e-3:
                    case.assert_preview_rejected('wall thickness')
                    row.update(result='rejected_as_expected')
                else:
                    first_parts = case.generate()
                    row['detected_mode'] = case.s.loop_detected_mode
                    row['selected_depth_mm'] = case.s.loop_extrude_depth_mm
                    inward = Vector(analysis['inward_dir_world']).normalized()
                    outward = -inward
                    centroid = Vector(analysis['centroid_world'])
                    coords = [Vector(point) for point in analysis['coords_world']]
                    support = centroid + outward * min((point-centroid).dot(outward) for point in coords)
                    measured_depth = (Vector(case.s.loop_interface_origin) - support).dot(inward) * 1000
                    row['measured_reference_depth_mm'] = measured_depth
                    case.assert_preserved_materials(first_parts)
                    first_total = case.s.part_sum_volume_mm3
                    row['first_total_volume_mm3'] = first_total
                    first_by_role = {part.get('chest_role'): capture_preview_geometry(part) for part in first_parts}
                    row['material_preservation_pass'] = all(
                        part['material_slots'] == case.original_materials for part in first_by_role.values())
                    case.generate()
                    repeat_parts = __import__('src.operators', fromlist=['get_current_session_parts']).get_current_session_parts(bpy.context.scene)
                    repeat_by_role = {part.get('chest_role'): capture_preview_geometry(part) for part in repeat_parts}
                    row['part_count_first'] = len(first_parts)
                    row['part_count_repeat'] = len(repeat_parts)
                    row['parts'] = []
                    for role, part in first_by_role.items():
                        metrics = repeated_preview_metrics(part, repeat_by_role[role])
                        metrics['role'] = role
                        row['parts'].append(metrics)
                    row['repeat_total_volume_mm3'] = case.s.part_sum_volume_mm3
                    row['source_unchanged'] = original_source == source_signature(case.target)
                    row['source_uv_present'] = bool(original_source['uv_layers'])
                    row['source_uv_layer_names'] = [layer[0] for layer in original_source['uv_layers']]
                    row['passed'] = (
                        len(first_parts) == 2 and len(repeat_parts) == 2
                        and len(first_by_role) == 2 and len(repeat_by_role) == 2
                        and abs(case.s.part_clearance_mm - .15) <= 1e-5
                        and case.s.part_clearance_apply_to == 'PART'
                        and case.original_materials == tuple((m.name, tuple(m.diffuse_color))
                                                             for m in case.target.data.materials)
                        and row['material_preservation_pass']
                        and abs(row['measured_reference_depth_mm'] - depth) <= .02
                        and case.s.loop_detected_mode == 'EXTRUDE' and case.s.loop_extrude_depth_mm == depth
                        and abs(measured_depth - depth) <= .02
                        and row['source_unchanged'] and row['material_preservation_pass']
                        and abs(row['repeat_total_volume_mm3'] - first_total) <= max(.001, abs(first_total) * 1e-6)
                        and all(
                            p['vertex_bijection_within_0_001mm']
                            and p['faces_semantic_equal_after_reindex']
                            and p['material_slots_equal'] and p['uv_layers_equal']
                            and p['volume_delta_mm3'] <= max(.001, abs(p['volume_first_mm3']) * 1e-6)
                            and p['bbox_delta_mm'] <= .001
                            and p['bidirectional_sample_to_surface_max_mm'] <= .001
                            for p in row['parts'])
                    )
                    row['result'] = 'passed' if row['passed'] else 'failed'
            except Exception as exc:
                row.update(result='error', error=repr(exc), traceback=traceback.format_exc())
            report['cases'].append(row)
            print('REPLAY_CASE', json.dumps(row, sort_keys=True), flush=True)
    report['totals'] = {'cases': len(report['cases']),
                        'passed': sum(c.get('result') in ('passed', 'rejected_as_expected') for c in report['cases']),
                        'failed': sum(c.get('result') not in ('passed', 'rejected_as_expected') for c in report['cases']),
                        'uv_source_cases': sum(bool(c.get('source_uv_present')) for c in report['cases'])}
    out = Path(__file__).resolve().parent / 'replay_validation_099.json'
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('REPLAY_TOTALS', json.dumps(report['totals']), flush=True)
    return 0 if report['totals']['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
