"""Focused real-model regressions for the current 0.9.8 source tree.

Run with Blender 5.2 background and arguments: addon_root models_root output_json.
All sources are opened read-only; no blend file is saved.
"""
import sys, json, time, traceback, hashlib
from pathlib import Path
import bpy, bmesh
from mathutils import Vector, Matrix

addon_root, models_root, output = map(Path, sys.argv[sys.argv.index('--') + 1:])
sys.path.insert(0, str(addon_root))
import src
src.register()
from src import operators as ops
from src.geometry_region import slice_region, mesh_signature
from src.geometry_material import slice_mesh_by_material
from src.geometry_loop import slice_mesh_by_loop, get_topology_signature
from src.diagnostic import get_scene_scale_to_mm, validate_bmesh_mesh_geometry
from src.geometry_clearance_blade import _triangles
from src.geometry_contract import build_cut_interface
from src.geometry_connectors import compute_connector_layout
from src.connector_surface import cache_prepared_interface, clear_prepared_split_cache
from src.geometry_contract import build_cut_interface

models_root = Path(models_root)
plate = models_root/'03_Testes_Extensao_e_Templates/01_Regiao_Inteira/01_Simples/Placa_4_Testes_Multicontatos.blend'
cat = models_root/'02_Personagens_e_Criaturas/Gato_Cinza/Teste Gato.blend'
spot = models_root/'02_Personagens_e_Criaturas/spot/spot/Vaquinha pos cortes.blend'
spot_original = models_root/'02_Personagens_e_Criaturas/spot/spot/Vaquinha.blend'
loop_ids = [424,1648,425,1641,423,1659,427,1653,426,1669,429,1663,428,1677,430,1672]
results=[]

def mesh_metrics(mesh, scale):
    bm=bmesh.new(); bm.from_mesh(mesh); bm.normal_update()
    try:
        components=0; remaining=set(bm.faces)
        while remaining:
            components+=1; todo=[remaining.pop()]
            while todo:
                f=todo.pop()
                for e in f.edges:
                    for n in e.link_faces:
                        if n in remaining: remaining.remove(n); todo.append(n)
        return {'vertices':len(bm.verts),'faces':len(bm.faces),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
                'components':components,'volume_mm3':abs(bm.calc_volume())*scale**3}
    finally: bm.free()

def run_case(name, path, fn):
    row={'case':name,'file':str(path)}; start=time.perf_counter()
    try:
        bpy.ops.wm.open_mainfile(filepath=str(path), use_scripts=False)
        if bpy.context.mode!='OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        row.update(fn())
        row.setdefault('status','OK')
    except Exception as e:
        row.update(status='ERROR',error_type=type(e).__name__,error=str(e),traceback=traceback.format_exc())
    row['seconds']=round(time.perf_counter()-start,3); results.append(row); print(json.dumps(row,ensure_ascii=False),flush=True)

def region_case(slot):
    scene=bpy.context.scene; obj=bpy.data.objects['PLACA_ALVO']; scale=get_scene_scale_to_mm(scene); sig=mesh_signature(obj.data)
    s=scene.chest_splitter; s.target_object=obj; s.region_target=obj; s.split_mode='MATERIAL'; s.material_extraction_mode='WHOLE'; s.material_split_index=slot; s.material_region_index=0
    s.part_clearance_mm=0; s.part_clearance_bottom_enable=False; s.connector_enabled=False; s.invert_sides=False
    s.region_face_indices=','.join(str(f.index) for f in obj.data.polygons if f.material_index==slot); s.region_mesh_signature=sig
    out=[bpy.data.meshes.new('Region A'),bpy.data.meshes.new('Region B')]
    try:
        report=slice_region(obj,s,scene,*out); m=[mesh_metrics(x,scale) for x in out]
        assert mesh_signature(obj.data)==sig
        assert all(x['nonmanifold_edges']==0 and x['components']==1 and x['volume_mm3']>0 for x in m)
        return {'mode':'WHOLE','material_slot':slot,'contacts':len(report.get('contact_choices',[])),'parts':m,'source_signature_unchanged':True}
    finally:
        for x in out:
            if x.users==0: bpy.data.meshes.remove(x)

def region_loop_case(slot, behavior):
    scene=bpy.context.scene; obj=bpy.data.objects['PLACA_ALVO']; scale=get_scene_scale_to_mm(scene); sig=mesh_signature(obj.data)
    ids=[p.index for p in obj.data.polygons if p.material_index==slot]
    if not ids: raise RuntimeError('No faces for requested plate region slot')
    s=scene.chest_splitter; s.target_object=obj; s.split_mode='MATERIAL'; s.material_split_index=slot; s.material_region_index=0
    bpy.context.view_layer.objects.active=obj; obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.context.tool_settings.mesh_select_mode=(False,False,True)
    bm=bmesh.from_edit_mesh(obj.data); bm.faces.ensure_lookup_table()
    for f in bm.faces: f.select_set(f.index in set(ids))
    bmesh.update_edit_mesh(obj.data,loop_triangles=False)
    if behavior in ('EXTRUDE','DETACH'):
        s.split_mode='LOOP';s.loop_behavior=behavior;s.loop_extrude_depth_mm=1.
        s.loop_detach_add_base=False
        s.loop_through_cut=False;s.part_clearance_mm=0;s.connector_enabled=False
        if sorted(bpy.ops.chest.splitter_capture_face_boundary())!=['FINISHED']:
            raise RuntimeError('Could not capture plate face boundary')
        bpy.ops.object.mode_set(mode='OBJECT')
        if sorted(bpy.ops.chest.splitter_generate_preview())!=['FINISHED']:
            raise RuntimeError('Plate depth loop preview invalid: '+s.get_localized_status())
        parts=ops.get_current_session_parts(scene)
        metrics=[mesh_metrics(p.data,scale) for p in parts]
        assert len(parts)==2 and all(x['nonmanifold_edges']==0 and x['components']==1 and x['volume_mm3']>0 for x in metrics)
        assert mesh_signature(obj.data)==sig
        return {'mode':'LOOP_FACE_BOUNDARY_OPERATOR','behavior':behavior,'depth_mm':1. if behavior=='EXTRUDE' else 0.,
                'material_slot_boundary':slot,'selected_faces':len(ids),'parts':metrics,'source_signature_unchanged':True}
    bpy.ops.object.mode_set(mode='OBJECT')
    s.split_mode='MATERIAL'; s.material_split_index=slot; s.material_region_index=0
    if sorted(bpy.ops.chest.splitter_capture_region(use_material=True))!=['FINISHED']: raise RuntimeError('Could not capture region through operator')
    s.split_mode='LOOP'; s.loop_behavior='WHOLE'; s.loop_is_captured=True; s.part_clearance_mm=0
    s.connector_enabled=False; s.invert_sides=False; s.contact_patch_index=-1
    if behavior=='EXTRUDE': s.loop_behavior='EXTRUDE'; s.loop_extrude_depth_mm=5.0
    result=sorted(bpy.ops.chest.splitter_generate_preview()); parts=ops.get_current_session_parts(scene)
    if result!=['FINISHED'] or s.session_status!='PREVIEW_VALID' or len(parts)!=2: raise RuntimeError('Region LOOP preview invalid: '+s.get_localized_status())
    metrics=[mesh_metrics(p.data,scale) for p in parts]
    assert all(x['nonmanifold_edges']==0 and x['components']==1 and x['volume_mm3']>0 for x in metrics)
    assert mesh_signature(obj.data)==sig
    return {'mode':'LOOP_REGION_OPERATOR','behavior':behavior,'material_slot_boundary':slot,'selected_faces':len(ids),'parts':metrics,'source_signature_unchanged':True}

def cat_case(slot, private_absent=False):
    scene=bpy.context.scene; obj=bpy.data.objects['Gato Cinza Retopology']; scale=get_scene_scale_to_mm(scene); sig=mesh_signature(obj.data)
    if not private_absent:
        s=scene.chest_splitter; s.target_object=obj; s.split_mode='MATERIAL'; s.material_extraction_mode='WHOLE'; s.material_split_index=slot; s.material_region_index=0
        s.material_interface_mat_mode='EXTRACTED'; s.connector_enabled=False; s.part_clearance_mm=0; s.contact_patch_index=-1
        if sorted(bpy.ops.chest.splitter_generate_preview())!=['FINISHED']: raise RuntimeError('Initial WHOLE preview failed: '+s.get_localized_status())
        if sorted(bpy.ops.chest.splitter_choose_contact(index=0))!=['FINISHED']: raise RuntimeError('Could not choose contact 0')
        s.connector_enabled=True; s.connector_distribution='LINEAR_2'; s.connector_diameter_mm=8.; s.connector_length_mm=12.; s.part_clearance_mm=.1
        if sorted(bpy.ops.chest.splitter_generate_preview())!=['FINISHED']: raise RuntimeError('Pinned WHOLE preview failed: '+s.get_localized_status())
        parts=ops.get_current_session_parts(scene)
        if len(parts)!=2 or s.session_status!='PREVIEW_VALID': raise RuntimeError('WHOLE preview invalid: '+s.get_localized_status())
        m=[mesh_metrics(p.data,scale) for p in parts]
        assert all(x['nonmanifold_edges']==0 and x['components']==1 and x['volume_mm3']>0 for x in m)
        assert {f.material_index for f in parts[0].data.polygons}=={4}
        assert len({f.material_index for f in parts[1].data.polygons})>1
        assert mesh_signature(obj.data)==sig
        return {'mode':'WHOLE_OPERATOR_WITH_PINS','material_slot':slot,'contact_index':0,'distribution':'LINEAR_2','diameter_mm':8,'length_mm':12,'gap_mm':.1,'preview_status':s.session_status,'parts':m,'source_signature_unchanged':True}
    if private_absent:
        # Use a private copy and partition the same cat by a deterministic face boundary,
        # avoiding a skip when the historical slot-4 fixture is absent.
        material_indices={p.material_index for p in obj.data.polygons}
        if slot in material_indices: raise RuntimeError('private boundary case requires absent slot')
        ids=[p.index for p in obj.data.polygons if p.center.z < obj.dimensions.z*.32]
        if not ids: raise RuntimeError('No lower-paw boundary faces found')
        private=obj.data.copy(); obj.data=private
        s=scene.chest_splitter; s.target_object=obj; s.region_target=obj; s.split_mode='MATERIAL'; s.material_extraction_mode='WHOLE'; s.material_split_index=0; s.material_region_index=0
        s.region_face_indices=','.join(map(str,ids)); s.region_mesh_signature=mesh_signature(obj.data)
        meshes=[bpy.data.meshes.new('Cat paw A'),bpy.data.meshes.new('Cat paw B')]
        try:
            report=slice_region(obj,s,scene,*meshes); m=[mesh_metrics(x,scale) for x in meshes]
            assert mesh_signature(obj.data)==s.region_mesh_signature
            assert all(x['nonmanifold_edges']==0 and x['components']==1 and x['volume_mm3']>0 for x in m)
            return {'mode':'WHOLE_PRIVATE_FACE_BOUNDARY','requested_absent_slot':slot,'boundary_faces':len(ids),'contacts':len(report.get('contact_choices',[])),'parts':m,'original_working_mesh_unchanged':mesh_signature(obj.data)==s.region_mesh_signature}
        finally:
            for x in meshes:
                if x.users==0: bpy.data.meshes.remove(x)
    raise AssertionError('unreachable')

def operator_foot(gap, male):
    scene=bpy.context.scene; s=scene.chest_splitter; obj=bpy.data.objects.get('spot_quadrangulated')
    if obj is None: raise RuntimeError('Spot target missing')
    sig=mesh_signature(obj.data); s.target_object=obj; s.split_mode='LOOP'; s.loop_behavior='AUTO'; s.loop_through_cut=False; s.loop_detach_add_base=False
    s.part_clearance_mm=gap; s.part_clearance_apply_to='PART'; s.contact_patch_index=-1; s.contact_choices='[]'
    s.connector_enabled=True; s.connector_male_part=male; s.connector_distribution='CENTER'; s.connector_type='CYLINDER'
    s.connector_diameter_mm=6.; s.connector_length_mm=8.; s.connector_chamfer_mm=.8; s.connector_edge_margin_mm=.4
    s.clearance_per_side_mm=.15; s.end_clearance_mm=.2; s.assembly_clearance_preset='CUSTOM'
    result=sorted(bpy.ops.chest.splitter_generate_preview()); parts=ops.get_current_session_parts(scene)
    if result!=['FINISHED'] or s.session_status!='PREVIEW_VALID' or len(parts)!=2: raise RuntimeError('Preview invalid: '+s.get_localized_status())
    metrics=[]
    for p in parts:
        m=mesh_metrics(p.data,1000); metrics.append(m)
    assert all(x['nonmanifold_edges']==0 and x['components']==1 and x['volume_mm3']>0 for x in metrics)
    assert mesh_signature(obj.data)==sig
    return {'mode':'LOOP_OPERATOR','loop_indices':s.loop_vertex_indices,'seed_face':s.loop_seed_face_index,'gap_mm':gap,'male_part':male,'preview_status':s.session_status,'parts':metrics,'source_signature_unchanged':True}

def horn_center(diameter=1., length=8., factor=.4, gap=.1, male='A', suggest=False):
    if suggest:
        import importlib.util
        if importlib.util.find_spec('src.connector_sizing') is None:
            return {'status':'NOT_AVAILABLE','reason':'Dimension suggestion is new in 0.9.8'}
    scene=bpy.context.scene; obj=bpy.data.objects['spot_quadrangulated']; s=scene.chest_splitter
    source_path=str(bpy.data.filepath)
    obj.matrix_world = Matrix.Scale(factor,4) @ obj.matrix_world
    bpy.context.view_layer.update(); sig=mesh_signature(obj.data)
    s.target_object=obj; s.split_mode='LOOP'; s.loop_vertex_indices=','.join(map(str,loop_ids)); s.loop_seed_face_index=958; s.loop_behavior='AUTO'
    s.region_selection_enabled=False
    s.loop_is_captured=True; s.loop_topology_signature=get_topology_signature(obj); s.loop_region_face_indices=''; s.loop_boundary_loops=''
    s.loop_is_planar=False; s.loop_planarity_deviation_mm=0.
    s.loop_through_cut=False; s.loop_detach_add_base=False; s.part_clearance_mm=gap; s.part_clearance_apply_to='PART'
    s.connector_enabled=True; s.connector_type='CYLINDER'; s.connector_distribution='CENTER'; s.connector_male_part=male
    s.connector_diameter_mm=diameter; s.connector_length_mm=length; s.connector_chamfer_mm=.2; s.connector_edge_margin_mm=.4
    s.clearance_per_side_mm=.1; s.end_clearance_mm=.1; s.assembly_clearance_preset='CUSTOM'; s.contact_patch_index=-1; s.contact_choices='[]'
    suggestion=None
    if not suggest:
        result=sorted(bpy.ops.chest.splitter_generate_preview()); parts=ops.get_current_session_parts(scene)
        if result!=['FINISHED'] or s.session_status!='PREVIEW_VALID' or len(parts)!=2: raise RuntimeError('Centered horn preview invalid: '+s.get_localized_status())
    if suggest:
        if sorted(bpy.ops.chest.splitter_suggest_connector_dimensions())!=['FINISHED']:
            raise RuntimeError('Could not suggest dimensions: '+s.connector_sizing_status)
        diameter=s.connector_diameter_mm; length=s.connector_length_mm
        suggestion={'diameter_mm':diameter,'length_mm':length,'status':s.connector_sizing_status}
        if sorted(bpy.ops.chest.splitter_generate_preview())!=['FINISHED']:
            raise RuntimeError('Suggested-dimension preview invalid: '+s.get_localized_status())
        parts=ops.get_current_session_parts(scene)
        if len(parts)!=2 or s.session_status!='PREVIEW_VALID': raise RuntimeError('Suggested-dimension preview invalid: '+s.get_localized_status())
    pts=[obj.matrix_world @ obj.data.vertices[i].co for i in loop_ids]; nominal=sum(pts,Vector())/len(pts)
    # Compare against the center of the ORIGINAL loop projected in the nominal
    # cut frame before the prepared physical support can reduce its contours.
    clear_prepared_split_cache()
    # Rebuild the real loop interface from the same mesh and inspect the public
    # CENTER layout result directly; this avoids inferring location from cap topology.
    raw=slice_mesh_by_loop(obj,obj.name,loop_ids,958,scene,part_clearance_mm=gap,part_clearance_apply_to='PART')
    try:
        iface=raw.interface
        pts=[obj.matrix_world @ obj.data.vertices[i].co for i in loop_ids]
        full=build_cut_interface(iface.reference_origin_world or iface.origin_world,
                                 iface.normal_a_to_b_world,pts,
                                 interface_triangles=iface.interface_triangles_world,unit_scale=1000)
        # Reconstruct the original projected polygon before cache preparation;
        # area centroid is distinct from the vertex average on irregular loops.
        poly=[full.world_to_uv(p) for p in pts]
        from math import fsum
        twice=fsum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))
        if abs(twice)<1e-20: raise RuntimeError('Original loop projected area is degenerate')
        area_uv=(fsum((a[0]+b[0])*(a[0]*b[1]-b[0]*a[1]) for a,b in zip(poly,poly[1:]+poly[:1]))/(3*twice),
                 fsum((a[1]+b[1])*(a[0]*b[1]-b[0]*a[1]) for a,b in zip(poly,poly[1:]+poly[:1]))/(3*twice))
        full_center=full.uv_to_world(*area_uv)
        prep=cache_prepared_interface(bpy.context,iface)
        layout=compute_connector_layout(target_mesh=obj.data,matrix_world=obj.matrix_world,
            plane_origin=prep.surface_origin,plane_normal=prep.interface.normal_a_to_b_world,
            distribution='CENTER',edge_margin_mm=.4,unit_scale=1000,diameter_mm=diameter,
            clearance_per_side_mm=.1,interface=prep.interface,connector_type='CYLINDER')
        if len(layout.get('positions',[]))!=1: raise RuntimeError('CENTER did not return exactly one connector position')
        actual=Vector(layout['positions'][0])
        actual_uv=full.world_to_uv(actual)
        area_offset_uv_mm=((actual_uv[0]-area_uv[0])**2+(actual_uv[1]-area_uv[1])**2)**.5*1000
        uv0_offset_mm=(actual_uv[0]**2+actual_uv[1]**2)**.5*1000
        # A manual UV=0 probe tests the same complete source domain before
        # cache reduction, matching the editor's stored coordinates.
        manual=compute_connector_layout(target_mesh=obj.data,matrix_world=obj.matrix_world,
            plane_origin=prep.surface_origin,plane_normal=prep.interface.normal_a_to_b_world,
            distribution='MANUAL',edge_margin_mm=.4,unit_scale=1000,diameter_mm=diameter,
            clearance_per_side_mm=.1,interface=prep.interface,connector_type='CYLINDER',
            manual_specs=[{'u_mm':0.,'v_mm':0.,'yaw_deg':0.}])
        manual_valid=manual['manual_eval_results'][0]['is_valid']
    finally:
        for bm in raw: bm.free()
    metrics=[mesh_metrics(p.data,1000) for p in parts]
    assert all(x['nonmanifold_edges']==0 and x['components']==1 and x['volume_mm3']>0 for x in metrics)
    assert mesh_signature(obj.data)==sig
    if not suggest: assert area_offset_uv_mm <= .05, f'CENTER displaced {area_offset_uv_mm:.3f} mm from full-loop area centroid'
    return {'mode':'LOOP_CENTER_OPERATOR','source_file':source_path,'full_section_mm':[full.width_mm,full.height_mm],'loop_indices':loop_ids,'seed_face':958,'factor':factor,'gap_mm':gap,'diameter_mm':diameter,'length_mm':length,'male_part':male,'suggestion':suggestion,'actual_center_world':list(actual),'original_loop_projected_area_centroid_world':list(full_center),'original_loop_uv0_world':list(full.uv_to_world(0,0)),'nominal_loop_vertex_mean_world':list(nominal),'center_offset_from_full_area_centroid_mm':area_offset_uv_mm,'center_offset_from_uv0_mm':uv0_offset_mm,'manual_uv0_valid':manual_valid,'actual_to_loop_mean_3d_mm':(actual-nominal).length*1000,'preview_status':s.session_status,'parts':metrics,'source_signature_unchanged':True}

run_case('plate_region_green',plate,lambda:region_case(1))
run_case('plate_region_blue',plate,lambda:region_case(2))
run_case('plate_loop_region_green_detach',plate,lambda:region_loop_case(1,'DETACH'))
run_case('plate_loop_region_blue_whole',plate,lambda:region_loop_case(2,'WHOLE'))
run_case('cat_material_slot4_paw',cat,lambda:cat_case(4))
run_case('spot_horn_center_1x8_gap01',spot_original,lambda:horn_center())
run_case('spot_horn_suggested_maleA',spot_original,lambda:horn_center(male='A',suggest=True))
run_case('spot_horn_suggested_maleB',spot_original,lambda:horn_center(male='B',suggest=True))
run_case('spot_foot_6x8_gap01_maleA',spot,lambda:operator_foot(.1,'A'))
run_case('spot_foot_6x8_gap01_maleB',spot,lambda:operator_foot(.1,'B'))
run_case('spot_foot_6x8_gap1_maleA',spot,lambda:operator_foot(1.,'A'))
output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
