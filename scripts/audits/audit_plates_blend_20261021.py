"""Audit MATERIAL and face-captured LOOP cuts on the supplied Blender plates.

Run with ordinary Python, for example:
  py scripts/audits/audit_plates_blend_20261021.py --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --models "C:/.../Blender" --threads 2

Each source .blend is loaded in its own background Blender process and never saved.
Results and logs are written under evidence/commercial_plates_blend_20261021.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "commercial_plates_blend_20261021"


def worker(blend_path: Path, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    import bpy
    import bmesh
    from mathutils import Vector
    sys.path.insert(0, str(ROOT))
    import src
    from src.geometry_material import list_material_regions, analyze_material_structure, slice_mesh_by_material
    from src.diagnostic import validate_bmesh_mesh_geometry, get_scene_scale_to_mm
    from src.input_state import cut_signature
    src.register()
    result = {"file": str(blend_path), "status": "ok", "objects": [], "cases": [], "loop_cases": [], "operator_cases": []}
    operator_cls = bpy.types.Operator.bl_rna_get_subclass_py('CHEST_OT_splitter_generate_preview')
    operator_module = getattr(operator_cls, "__module__", None)
    result["effective_preview_operator_module"] = operator_module
    if operator_module != "src.operators":
        raise RuntimeError(f"Expected src.operators preview operator, got {operator_module!r}")
    meshes = sorted((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.polygons), reverse=True)
    for obj in meshes:
        info = {"object": obj.name, "vertices": len(obj.data.vertices), "edges": len(obj.data.edges),
                "faces": len(obj.data.polygons), "materials": [m.name if m else None for m in obj.data.materials]}
        result["objects"].append(info)
    if not meshes:
        raise RuntimeError("No mesh objects in source file")
    source_obj = meshes[0]
    original = {"vertices": [tuple(v.co) for v in source_obj.data.vertices],
                "faces": [tuple(p.vertices) for p in source_obj.data.polygons],
                "materials": [p.material_index for p in source_obj.data.polygons],
                "slots": [m.name if m else None for m in source_obj.data.materials]}
    scene = bpy.context.scene
    scale = get_scene_scale_to_mm(scene)
    obj = source_obj
    bm_source = bmesh.new()
    bm_source.from_mesh(source_obj.data)
    bm_source.transform(source_obj.matrix_world)
    source_report = validate_bmesh_mesh_geometry(bm_source, scale)
    bm_source.free()
    result["source_diagnostics"] = {k: source_report.get(k) for k in
        ("is_valid", "is_manifold", "non_manifold_edges", "degenerate_faces", "zero_area_faces", "volume_mm3", "errors")}
    result["scale_to_mm"] = scale
    if not source_report.get("is_valid") or not source_report.get("is_manifold"):
        # The safe repair runs on a duplicate object and duplicate mesh datablock.
        # The source object remains a byte-for-byte geometry reference in memory.
        obj = source_obj.copy()
        obj.data = source_obj.data.copy()
        repair_obj = obj
        repair_obj_name = obj.name
        obj.name = source_obj.name + "_AUDIT_REPAIR_COPY"
        scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        for item in bpy.context.view_layer.objects:
            item.select_set(item == obj)
        s = scene.chest_splitter
        s.target_object = obj
        before_repair = {"vertices": len(obj.data.vertices), "faces": len(obj.data.polygons),
                         "materials": [m.name if m else None for m in obj.data.materials]}
        repair_result = bpy.ops.chest.splitter_repair_target_mesh()
        bm_after = bmesh.new()
        bm_after.from_mesh(obj.data)
        bm_after.transform(obj.matrix_world)
        after_report = validate_bmesh_mesh_geometry(bm_after, scale)
        bm_after.free()
        result["repair"] = {"operator": sorted(repair_result), "status": s.get_localized_status(), "before": before_repair,
            "after": {"vertices": len(obj.data.vertices), "faces": len(obj.data.polygons),
                      "materials": [m.name if m else None for m in obj.data.materials],
                      "valid": after_report.get("is_valid"), "manifold": after_report.get("is_manifold"),
                      "volume_mm3": after_report.get("volume_mm3"), "errors": after_report.get("errors", [])}}
        if repair_result != {'FINISHED'} or not after_report.get("is_valid") or not after_report.get("is_manifold"):
            result["repair"]["usable_copy"] = False
            obj = source_obj
        else:
            result["repair"]["usable_copy"] = True
    else:
        result["repair"] = {"status": "not_needed", "usable_copy": False}

    def complete_operator(operator_case, mode, preview, copy_suffix):
        from src.operators import get_current_session_parts, verify_preview_current
        operator_case["fdm_preview_result"] = sorted(preview)
        operator_case["fdm_status"] = scene.chest_splitter.get_localized_status()
        if preview != {'FINISHED'}:
            try: bpy.ops.chest.splitter_remove_preview()
            except Exception: pass
            s = scene.chest_splitter
            s.assembly_clearance_preset = 'NONE'
            s.split_mode = mode
            s.connector_enabled = True
            try:
                retry = bpy.ops.chest.splitter_generate_preview()
            except Exception as exc:
                retry = {'CANCELLED'}
                operator_case["zero_gap_with_pins_error"] = f"{type(exc).__name__}: {exc}"
            operator_case["zero_gap_with_pins_result"] = sorted(retry)
            operator_case["zero_gap_with_pins_status"] = s.get_localized_status()
            if retry != {'FINISHED'}:
                try: bpy.ops.chest.splitter_remove_preview()
                except Exception: pass
                s.connector_enabled = False
                try:
                    retry = bpy.ops.chest.splitter_generate_preview()
                except Exception as exc:
                    retry = {'CANCELLED'}
                    operator_case["zero_gap_without_pins_error"] = f"{type(exc).__name__}: {exc}"
                operator_case["zero_gap_without_pins_result"] = sorted(retry)
                operator_case["zero_gap_without_pins_status"] = s.get_localized_status()
            if retry != {'FINISHED'}:
                operator_case["preview_result"] = sorted(retry)
                return
            operator_case["profile_used"] = 'NONE'
            operator_case["pins_used"] = bool(s.connector_enabled)
            preview = retry
        else:
            operator_case["profile_used"] = 'FDM'
            operator_case["pins_used"] = True
        operator_case["preview_result"] = sorted(preview)
        operator_case["preview_current"] = bool(verify_preview_current(bpy.context)[0])
        operator_case["manifold"] = [bool(scene.chest_splitter.part_a_is_manifold), bool(scene.chest_splitter.part_b_is_manifold)]
        parts = get_current_session_parts(scene); pv = []
        for part in parts:
            part_bm = bmesh.new(); part_bm.from_mesh(part.data)
            report = validate_bmesh_mesh_geometry(part_bm, scale); part_bm.free(); pv.append(report.get("volume_mm3"))
        operator_case["preview_volumes_mm3"] = pv
        review_dir = OUT / "manual_review"; review_dir.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(review_dir / (blend_path.stem + copy_suffix)), copy=True)
        commit = bpy.ops.chest.splitter_commit_parts(); operator_case["commit_result"] = sorted(commit)
        committed = get_current_session_parts(scene); cv = []
        for part in committed:
            part_bm = bmesh.new(); part_bm.from_mesh(part.data)
            report = validate_bmesh_mesh_geometry(part_bm, scale); part_bm.free(); cv.append(report.get("volume_mm3"))
        operator_case["commit_volumes_mm3"] = cv
        operator_case["preview_commit_equal"] = sorted(round(v or 0, 7) for v in pv) == sorted(round(v or 0, 7) for v in cv)
        operator_case["revert_result"] = sorted(bpy.ops.chest.splitter_revert_cut())

    try:
        for mat_index in range(len(obj.data.materials)):
            regions = list_material_regions(obj, mat_index)
            if not regions:
                result["cases"].append({"material": mat_index, "outcome": "expected_empty_slot"})
                continue
            for region in regions:
                case = {"material": mat_index, "region": region["index"], "region_faces": region["face_count"], "outcome": "ok"}
                if region["face_count"] < 16:
                    case["outcome"] = "micro_island_recorded_not_a_success"
                    result["cases"].append(case)
                    continue
                analysis = analyze_material_structure(obj, mat_index, region["index"])
                case["analysis_valid"] = bool(analysis.get("valid"))
                case["analysis_error"] = analysis.get("error")
                if not analysis.get("valid"):
                    case["outcome"] = "expected_invalid_configuration"
                    result["cases"].append(case)
                    continue
                depth = 2.0
                case["depth_mm"] = depth
                case["trials"] = []
                is_dominant = region["face_count"] == max(r["face_count"] for r in regions)

                def check_parts(label, call):
                    direct_result = None
                    trial = {"label": label, "outcome": "pass"}
                    import src.geometry_material as gm
                    original_evaluate = gm.evaluate_bmesh_metrics
                    nonmanifold_details = []
                    def observe_metrics(part_bm, unit_scale):
                        report = original_evaluate(part_bm, unit_scale)
                        if not report.get("is_manifold"):
                            for edge in part_bm.edges:
                                if edge.is_manifold:
                                    continue
                                nonmanifold_details.append({
                                    "link_faces": len(edge.link_faces), "is_wire": edge.is_wire,
                                    "length_mm": edge.calc_length() * unit_scale,
                                    "verts_world": [tuple(obj.matrix_world @ vert.co) for vert in edge.verts],
                                    "adjacent_materials": [face.material_index for face in edge.link_faces]})
                        return report
                    gm.evaluate_bmesh_metrics = observe_metrics
                    try:
                        direct_result = call()
                        reports = []
                        for part_bm in direct_result[:2]:
                            report = validate_bmesh_mesh_geometry(part_bm, scale)
                            reports.append({"valid": bool(report.get("is_valid")), "manifold": bool(report.get("is_manifold")),
                                            "volume_mm3": report.get("volume_mm3"), "errors": report.get("errors", [])})
                        trial["parts"] = reports
                        trial["interface_loops"] = len(getattr(direct_result.interface, "hole_contours_uv", [])) + (1 if getattr(direct_result.interface, "outer_contours_uv", []) else 0)
                        if not all(p["valid"] and p["manifold"] and (p["volume_mm3"] or 0) > 0 for p in reports):
                            trial["outcome"] = "geometry_failure"
                    except Exception as exc:
                        trial["outcome"] = "rejected_or_failed"
                        trial["error"] = f"{type(exc).__name__}: {exc}"
                    finally:
                        gm.evaluate_bmesh_metrics = original_evaluate
                        if nonmanifold_details:
                            trial["nonmanifold_edges"] = nonmanifold_details
                        if direct_result:
                            for part_bm in direct_result[:2]: part_bm.free()
                    return trial

                # Leave the captured Loop state intact while explicitly switching
                # back to MATERIAL. This covers the historical stale-capture bug.
                scene.chest_splitter.split_mode = 'MATERIAL'
                case["trials"].append(check_parts("EXTRUDE depth=2mm gap=0", lambda: slice_mesh_by_material(
                    obj, mat_index, depth_mm=depth, scene=scene, region_index=region["index"],
                    extraction_mode='EXTRUDE', part_clearance_mm=0)))
                case["trials"].append(check_parts("EXTRUDE depth=2mm gap=0.1mm", lambda: slice_mesh_by_material(
                    obj, mat_index, depth_mm=depth, scene=scene, region_index=region["index"],
                    extraction_mode='EXTRUDE', part_clearance_mm=.1)))
                if analysis.get("is_planar_base"):
                    scene.chest_splitter.split_mode = 'MATERIAL'
                    case["trials"].append(check_parts("BASE gap=0", lambda: slice_mesh_by_material(
                        obj, mat_index, depth_mm=depth, scene=scene, region_index=region["index"],
                        extraction_mode='BASE', part_clearance_mm=0)))
                case["outcome"] = "pass" if any(t["outcome"] == "pass" for t in case["trials"]) else "material_rejected_or_failed"

                s = scene.chest_splitter
                s.target_object = obj
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                # Capture each significant connected painted region as a Loop.
                if obj.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
                s.split_mode = 'LOOP'
                bpy.ops.object.mode_set(mode='EDIT')
                bm = bmesh.from_edit_mesh(obj.data); bm.faces.ensure_lookup_table()
                from src.geometry_material import get_material_regions
                expected_region_faces = set(get_material_regions(bm, mat_index)[region['index']])
                for f in bm.faces: f.select_set(f.index in expected_region_faces)
                bm.faces.active = next((f for f in bm.faces if f.select), None)
                bm.select_mode = {'FACE'}; bpy.context.tool_settings.mesh_select_mode = (False, False, True)
                bm.select_flush_mode(); bmesh.update_edit_mesh(obj.data)
                try:
                    op_result = bpy.ops.chest.splitter_capture_face_boundary()
                    captured = json.loads(s.loop_region_face_indices or '[]')
                    boundary_loops = json.loads(s.loop_boundary_loops) if s.loop_boundary_loops else [[int(v) for v in s.loop_vertex_indices.split(',') if v.strip()]]
                    case_loop = {"material": mat_index, "region": region["index"], "face_count": region["face_count"],
                        "capture_result": sorted(op_result), "captured_faces": len(captured), "expected_faces": region["face_count"],
                        "captured_matches_region": (set(captured) == expected_region_faces) if len(boundary_loops) > 1 else None,
                        "loops": len(boundary_loops), "outcome": "pass" if op_result == {'FINISHED'} and
                        (len(boundary_loops) == 1 or set(captured) == expected_region_faces) else "capture_mismatch"}
                    if case_loop["outcome"] == "pass" and case["outcome"] == "pass" and is_dominant and not any(
                        str(c.get("mode", "")).startswith("MATERIAL") and c.get("preview_result") == ["FINISHED"] for c in result["operator_cases"]):
                        # Deliberately switch LOOP -> MATERIAL after capture, then generate
                        # the material preview with the saved capture still present.
                        saved_loop = {name: getattr(s, name) for name in (
                            "loop_is_captured", "loop_vertex_indices", "loop_boundary_loops",
                            "loop_region_face_indices", "loop_seed_face_index", "loop_topology_signature")}
                        bpy.ops.object.mode_set(mode='OBJECT')
                        s.split_mode = 'MATERIAL'; s.material_split_index = mat_index; s.material_region_index = region["index"]
                        s.material_extraction_mode = 'EXTRUDE'; s.material_extrude_depth_mm = depth
                        s.material_interface_mat_mode = 'EXTRACTED'; s.assembly_clearance_preset = 'FDM'
                        s.connector_enabled = True; s.connector_distribution = 'AUTO_SHAPE'
                        s.connector_diameter_mm = 1.2; s.connector_length_mm = 1.5; s.connector_chamfer_mm = .1
                        s.connector_edge_margin_mm = .4; s.commit_next_target = 'NONE'
                        operator_case = {"mode": "MATERIAL_after_LOOP_capture", "material": mat_index,
                            "region": region["index"], "depth_mm": depth, "profile": "FDM",
                            "connectors_requested": True, "captured_loop_retained": bool(s.loop_is_captured)}
                        try:
                            try: preview = bpy.ops.chest.splitter_generate_preview()
                            except Exception as exc:
                                operator_case["fdm_error"] = f"{type(exc).__name__}: {exc}"
                                preview = {'CANCELLED'}
                            complete_operator(operator_case, 'MATERIAL', preview, "_MATERIAL_after_LOOP_preview.blend")
                        except Exception as exc:
                            operator_case["error"] = f"{type(exc).__name__}: {exc}"
                            try: bpy.ops.chest.splitter_remove_preview()
                            except Exception: pass
                        result["operator_cases"].append(operator_case)
                        for name, value in saved_loop.items(): setattr(s, name, value)

                    if case_loop["outcome"] == "pass" and is_dominant and not any(
                        c.get("mode") == "LOOP" and c.get("preview_result") == ["FINISHED"] for c in result["operator_cases"]):
                        bpy.ops.object.mode_set(mode='OBJECT')
                        s.loop_behavior = 'EXTRUDE'; s.loop_extrude_depth_mm = depth; s.loop_through_cut = False
                        s.split_mode = 'LOOP'; s.assembly_clearance_preset = 'FDM'
                        s.connector_enabled = True; s.connector_distribution = 'AUTO_SHAPE'
                        s.connector_diameter_mm = 1.2; s.connector_length_mm = 1.5; s.connector_chamfer_mm = .1
                        s.connector_edge_margin_mm = .4; s.commit_next_target = 'NONE'
                        operator_case = {"mode": "LOOP", "material": mat_index, "region": region["index"],
                            "depth_mm": depth, "profile": "FDM", "connectors_requested": True}
                        try:
                            try: preview = bpy.ops.chest.splitter_generate_preview()
                            except Exception as exc:
                                operator_case["fdm_error"] = f"{type(exc).__name__}: {exc}"
                                preview = {'CANCELLED'}
                            complete_operator(operator_case, 'LOOP', preview, "_LOOP_preview.blend")
                        except Exception as exc:
                            operator_case["error"] = f"{type(exc).__name__}: {exc}"
                            try: bpy.ops.chest.splitter_remove_preview()
                            except Exception: pass
                        result["operator_cases"].append(operator_case)
                    elif obj.mode == 'EDIT':
                        bpy.ops.object.mode_set(mode='OBJECT')
                    result["loop_cases"].append(case_loop)
                except Exception as exc:
                    result["loop_cases"].append({"material": mat_index, "region": region["index"], "outcome": "capture_failure", "error": f"{type(exc).__name__}: {exc}"})
                finally:
                    if obj.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
                result["cases"].append(case)
    finally:
        if obj.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        after = {"vertices": [tuple(v.co) for v in source_obj.data.vertices],
                 "faces": [tuple(p.vertices) for p in source_obj.data.polygons],
                 "materials": [p.material_index for p in source_obj.data.polygons],
                 "slots": [m.name if m else None for m in source_obj.data.materials]}
        result["source_unchanged"] = original == after
        if obj != source_obj:
            bpy.data.objects.remove(obj, do_unlink=True)
        if 'repair_obj_name' in locals() and repair_obj_name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[repair_obj_name], do_unlink=True)
    output_path.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    print("AUDIT_RESULT=" + json.dumps({"file": blend_path.name, "status": result["status"],
        "material_cases": len(result["cases"]), "loop_cases": len(result["loop_cases"]),
        "source_unchanged": result["source_unchanged"]}))


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--blender')
    parser.add_argument('--models')
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--output-dir')
    parser.add_argument('--worker', nargs=2, metavar=('BLEND', 'OUTPUT'))
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)
    if args.worker:
        try: worker(Path(args.worker[0]), Path(args.worker[1]))
        except Exception as exc:
            out = Path(args.worker[1]); out.write_text(json.dumps({"file": args.worker[0], "status": "crash", "error": str(exc), "traceback": traceback.format_exc()}, indent=2), encoding='utf-8')
            raise
        return
    if not args.blender or not args.models:
        parser.error('--blender and --models are required outside Blender')
    if args.output_dir:
        OUT = Path(args.output_dir).resolve()
    models = Path(args.models)
    files = sorted(models.rglob('*.blend'))
    OUT.mkdir(parents=True, exist_ok=True)
    pending = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    def run(blend):
        output = OUT / (blend.stem + '.json')
        log = OUT / (blend.stem + '.log')
        command = [args.blender, '--background', '--factory-startup', '--threads', str(args.threads), str(blend), '--python-exit-code', '1', '--python', str(Path(__file__).resolve()), '--', '--worker', str(blend), str(output)]
        with log.open('w', encoding='utf-8') as stream:
            proc = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=900)
        return {"file": blend.name, "returncode": proc.returncode, "json": str(output), "log": str(log)}
    with ThreadPoolExecutor(max_workers=max(1, args.threads)) as pool:
        for future in as_completed([pool.submit(run, f) for f in files]):
            pending.append(future.result())
            print(json.dumps(pending[-1]))
    summary = {"models_directory": str(models), "blender": args.blender, "files": pending}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f"Audited {len(files)} files; evidence: {OUT}")


if __name__ == '__main__': main()
