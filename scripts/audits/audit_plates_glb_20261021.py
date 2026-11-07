"""End-to-end audit of delivered plate GLBs with Blender and Chest Part Splitter.

Run with Blender 5.2 in background. Imports each file into a fresh scene; all
repairs/cuts happen on transient in-memory objects and no source is saved.
"""
import json, sys, traceback
from pathlib import Path
import bpy, bmesh

ROOT = Path(__file__).resolve().parents[2]
GLB_DIR = Path(r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras")
OUT = ROOT / "evidence" / "commercial_plates_glb_20261021"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
import src
from src.diagnostic import validate_bmesh_mesh_geometry
from src.geometry_material import analyze_material_structure, get_material_regions
from src.operators import get_current_session_parts, verify_preview_current

src.register()

def bmesh_stats(obj):
    bm=bmesh.new(); bm.from_mesh(obj.data)
    try:
        bm.normal_update()
        report=validate_bmesh_mesh_geometry(bm,1000)
        return {"verts":len(bm.verts),"edges":len(bm.edges),"faces":len(bm.faces),
          "triangles":sum(len(f.verts)-2 for f in bm.faces),
          "nonmanifold_edges":sum(not e.is_manifold for e in bm.edges),
          "loose_edges":sum(len(e.link_faces)==0 for e in bm.edges),
          "components":len(bmesh.ops.split(bm, edges=bm.edges[:], verts=bm.verts[:], faces=bm.faces[:], use_only_faces=False).get('geom',[])) if False else None,
          "volume_mm3":abs(bm.calc_volume())*1e9,"valid":report['is_valid'],"manifold":report['is_manifold'],
          "degenerate_faces":len(report['degenerate_faces']),"bounds_mm":[round(float(x)*1000,6) for x in obj.dimensions]}
    finally: bm.free()

def mesh_snapshot(obj):
    return (tuple(tuple(round(float(c),9) for c in v.co) for v in obj.data.vertices),
            tuple(tuple(p.vertices) for p in obj.data.polygons),
            tuple(p.material_index for p in obj.data.polygons))

def component_count(obj):
    bm=bmesh.new(); bm.from_mesh(obj.data)
    try:
        unseen=set(bm.verts); n=0
        while unseen:
            n+=1; stack=[unseen.pop()]
            while stack:
                v=stack.pop()
                for e in v.link_edges:
                    w=e.other_vert(v)
                    if w in unseen: unseen.remove(w); stack.append(w)
        return n
    finally:bm.free()

def valid_parts(parts):
    out=[]
    for part in parts:
        bm=bmesh.new(); bm.from_mesh(part.data)
        try:
            bm.transform(part.matrix_world); bm.normal_update()
            r=validate_bmesh_mesh_geometry(bm,1000)
            out.append({"object":part.name,"verts":len(bm.verts),"faces":len(bm.faces),
                "volume_mm3":abs(bm.calc_volume())*1e9,"manifold":r['is_manifold'],
                "valid":r['is_valid'],"nonmanifold_edges":sum(not e.is_manifold for e in bm.edges),
                "components":component_count(part)})
        finally:bm.free()
    return out

def attempt_cut(obj, mode, mat_index, region_index, behavior, gap):
    s=bpy.context.scene.chest_splitter
    previous_mode=s.split_mode
    previous_capture=bool(s.loop_is_captured)
    previous_seed=int(s.loop_seed_face_index)
    s.target_object=obj; s.split_mode=mode
    s.assembly_clearance_preset='NONE'
    s.part_clearance_mm=gap; s.part_clearance_apply_to='PART'; s.part_clearance_bottom_enable=False
    s.connector_enabled=False; s.commit_next_target='NONE'
    s.material_split_index=mat_index; s.material_region_index=region_index
    s.material_extraction_mode=behavior if mode=='MATERIAL' else 'EXTRUDE'; s.material_extrude_depth_mm=1.0
    s.loop_behavior=behavior if mode=='LOOP' else 'AUTO'; s.loop_extrude_depth_mm=1.0
    before=mesh_snapshot(obj)
    out={"mode":mode,"material_index":mat_index,"region_index":region_index,"behavior":behavior,"gap_mm":gap,
         "previous_split_mode":previous_mode,"previous_loop_capture_active":previous_capture,"previous_loop_seed_face_index":previous_seed}
    out['effective_part_clearance_mm']=float(s.part_clearance_mm)
    out['effective_bottom_clearance_mm']=float(s.part_clearance_bottom_mm if s.part_clearance_bottom_enable else s.part_clearance_mm)
    out['connectors_enabled']=bool(s.connector_enabled)
    if abs(out['effective_part_clearance_mm']-float(gap))>1e-8:
        out['configuration_error']='requested/effective part clearance mismatch'
        return out
    try:
        if mode=='LOOP':
            # Select the exact connected region found through the visible material island.
            bm=bmesh.new(); bm.from_mesh(obj.data); bm.faces.ensure_lookup_table()
            reg=get_material_regions(bm,mat_index)[region_index]
            bm.free()
            bpy.context.view_layer.objects.active=obj
            for x in bpy.context.selected_objects:x.select_set(False)
            obj.select_set(True)
            bpy.context.tool_settings.mesh_select_mode=(False,False,True)
            bpy.ops.object.mode_set(mode='EDIT')
            ebm=bmesh.from_edit_mesh(obj.data); ebm.faces.ensure_lookup_table()
            for f in ebm.faces:f.select_set(f.index in set(reg))
            bmesh.update_edit_mesh(obj.data)
            out['capture_operator']=str(bpy.ops.chest.splitter_capture_face_boundary())
            out['captured']=bool(s.loop_is_captured);out['loop_vertices']=s.loop_vertex_count
            bpy.ops.object.mode_set(mode='OBJECT')
            if not s.loop_is_captured: raise RuntimeError('loop boundary capture returned without a captured loop')
        result=bpy.ops.chest.splitter_generate_preview()
        out['preview_operator']=str(result);out['status']=s.session_status;out['message']=s.get_localized_status()
        parts=get_current_session_parts(bpy.context.scene)
        out['preview_current']=verify_preview_current(bpy.context)[0]
        out['parts']=valid_parts(parts)
        out['closed_solid_parts']=(len(parts)==2 and all(x['valid'] and x['manifold'] and x['volume_mm3']>0 for x in out['parts']))
        if out['closed_solid_parts']:
            bm=bmesh.new();bm.from_mesh(obj.data)
            try: out['source_volume_mm3']=abs(bm.calc_volume())*1e9
            finally:bm.free()
            out['parts_volume_mm3']=sum(x['volume_mm3'] for x in out['parts'])
            out['volume_delta_mm3']=out['parts_volume_mm3']-out['source_volume_mm3']
            # Commit/revert exercises lifecycle while proving the imported target is restored.
            committed=bpy.ops.chest.splitter_commit_parts();out['commit_operator']=str(committed)
            out['source_unchanged_after_commit']=mesh_snapshot(obj)==before
            operation_id=s.active_operation_id or s.session_id
            reverted=bpy.ops.chest.splitter_revert_cut(operation_id=operation_id);out['revert_operator']=str(reverted)
            out['source_unchanged_after_revert']=mesh_snapshot(obj)==before
        else:
            # Return to source scene state on the next case; this record preserves expected rejects.
            out['source_unchanged_after_preview']=mesh_snapshot(obj)==before
    except Exception as exc:
        out['exception']=type(exc).__name__+': '+str(exc)
        out['failure_classification']='reproduced_stale_loop_capture_mode_switch' if 'face escolhida não pertence à moldura capturada' in str(exc).lower() else 'geometry_or_configuration_rejection'
        out['traceback']=traceback.format_exc(limit=4)
        out['source_unchanged_on_failure']=mesh_snapshot(obj)==before
    return out

records=[]
for filepath in sorted(GLB_DIR.glob('*.glb')):
    if not filepath.is_file(): continue
    print('AUDIT', filepath.name, flush=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene; scene.unit_settings.scale_length=1
    rec={"file":filepath.name,"path":str(filepath),"import":None,"materials":[],"cases":[]}
    try:
        result=bpy.ops.import_scene.gltf(filepath=str(filepath))
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
        rec['import']={"operator":str(result),"mesh_objects":len(meshes),"object_names":[o.name for o in meshes]}
        if len(meshes)!=1: raise RuntimeError('Expected exactly one plate mesh object')
        obj=meshes[0]; scene.chest_splitter.target_object=obj
        rec['raw']=bmesh_stats(obj);rec['raw']['connected_components']=component_count(obj)
        rec['material_slots']=[{"name":m.name if m else None,"diffuse_color":list(m.diffuse_color) if m else None} for m in obj.data.materials]
        for mi,mat in enumerate(obj.data.materials):
            bm=bmesh.new();bm.from_mesh(obj.data)
            try:
                regs=get_material_regions(bm,mi)
                info={"index":mi,"name":mat.name,"faces":sum(f.material_index==mi for f in bm.faces),"regions":len(regs),"region_face_counts":[len(x) for x in regs]}
            finally:bm.free()
            try:
                analysis=analyze_material_structure(obj,mi,0)
                info['largest_region_analysis']={k:analysis.get(k) for k in ('valid','error','has_holes','boundary_loops','area_mm2','deviation_mm','region_face_count')}
            except Exception as e:info['analysis_error']=type(e).__name__+': '+str(e)
            rec['materials'].append(info)
        # Test repair as a transient copy on the imported target.
        rec['raw_mesh_datablock']=obj.data.name
        rec['repair_operator']=str(bpy.ops.chest.splitter_repair_target_mesh())
        rec['repair_message']=scene.chest_splitter.get_localized_status()
        repaired=obj.data is not None
        rec['repaired']=bmesh_stats(obj);rec['repaired']['connected_components']=component_count(obj)
        rec['repair_created_separate_datablock']=(obj.data.name != rec['raw_mesh_datablock'])
        # Capture the largest meaningful colored island in each slot, then also cut one valid region using MATERIAL.
        for mi,mat in enumerate(obj.data.materials):
            bm=bmesh.new();bm.from_mesh(obj.data)
            try: regs=get_material_regions(bm,mi)
            finally:bm.free()
            if not regs: continue
            # Only attempt meaningful regions; full-body material is valid for BASE/EXTRUDE but not a boundary cut.
            order=sorted(range(len(regs)),key=lambda i:len(regs[i]),reverse=True)
            for ri in order[:2]:
                try:
                    analysis=analyze_material_structure(obj,mi,ri)
                    if not analysis.get('valid'): 
                        rec['cases'].append({"mode":"MATERIAL","material_index":mi,"region_index":ri,"classification":"expected_rejection_invalid_material_region","reason":analysis.get('error')});continue
                except Exception as e:
                    rec['cases'].append({"mode":"MATERIAL","material_index":mi,"region_index":ri,"classification":"analysis_exception","reason":type(e).__name__+': '+str(e)});continue
                # Zero clearance is baseline; small clearance probes the FDM path on a selected region.
                for gap in (0.0,0.1):
                    case=attempt_cut(obj,'MATERIAL',mi,ri,'EXTRUDE',gap)
                    rec['cases'].append(case)
                # Real edit-mode capture of this color island exercises the Loop workflow too.
                case=attempt_cut(obj,'LOOP',mi,ri,'AUTO',0.0)
                rec['cases'].append(case)
                break
        # Blender's own merge_vertices import switch is measured separately from
        # the validated extension repair, since these are distinct import paths.
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene=bpy.context.scene;scene.unit_settings.scale_length=1
        merge_result=bpy.ops.import_scene.gltf(filepath=str(filepath),merge_vertices=True)
        merge_objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
        if len(merge_objs)==1:
            rec['import_merge_vertices']={"operator":str(merge_result),"stats":bmesh_stats(merge_objs[0]),"connected_components":component_count(merge_objs[0])}
        else: rec['import_merge_vertices']={"operator":str(merge_result),"mesh_objects":len(merge_objs)}
        rec['case_counts']={"total":len(rec['cases']),"closed_solid_previews":sum(c.get('closed_solid_parts',False) for c in rec['cases']),"failures":sum('exception' in c or ('preview_operator' in c and c.get('preview_operator')!="{'FINISHED'}") for c in rec['cases'])}
        rec['stale_loop_capture_bug_reproduced']=any(c.get('failure_classification')=='reproduced_stale_loop_capture_mode_switch' and c.get('previous_loop_capture_active') for c in rec['cases'])
    except Exception as exc:
        rec['fatal']=type(exc).__name__+': '+str(exc);rec['traceback']=traceback.format_exc(limit=6)
    records.append(rec)
    (OUT/(filepath.stem+'.json')).write_text(json.dumps(rec,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({"file":filepath.name,"raw_edges":(rec.get('raw') or {}).get('nonmanifold_edges'),"repair_edges":(rec.get('repaired') or {}).get('nonmanifold_edges'),"cases":rec.get('case_counts'),"fatal":rec.get('fatal')},ensure_ascii=False),flush=True)

summary={"blender_version":bpy.app.version_string,"glb_directory":str(GLB_DIR),"files_seen":len(records),"files":records}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
print('SUMMARY',len(records), 'files', flush=True)
