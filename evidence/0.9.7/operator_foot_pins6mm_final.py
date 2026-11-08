"""Test the real saved Spot foot loop through the public preview operator."""
import bpy,bmesh,sys,json,traceback,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root));import src;src.register()
from src import operators as ops
from src.diagnostic import validate_bmesh_mesh_geometry
model=Path.home()/"OneDrive/Desktop/Modelos 3D e testes extensao/02_Personagens_e_Criaturas/spot/spot/Vaquinha pos cortes.blend"
out=[]
cases=[(.1,'PART','A'),(.1,'PART','B'),(1.0,'PART','A')]
for gap,apply_to,male in cases:
  row={'gap_mm':gap,'clearance_apply_to':apply_to,'male_part':male,'model':str(model),'split_mode':'LOOP','loop_behavior':'AUTO','connector_enabled':True,
       'connector_type':'CYLINDER','connector_distribution':'CENTER','diameter_mm':6.0,'length_mm':8.0,'chamfer_mm':0.8,
       'clearance_per_side_mm':0.15,'end_clearance_mm':0.2,'edge_margin_mm':0.4}
  try:
   start=time.perf_counter();bpy.ops.wm.open_mainfile(filepath=str(model),use_scripts=False)
   if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
   scene=bpy.context.scene;s=scene.chest_splitter;obj=bpy.data.objects.get('spot_quadrangulated')
   if obj is None:raise RuntimeError('Model target spot_quadrangulated not found')
   s.target_object=obj;s.split_mode='LOOP';s.loop_behavior='AUTO';s.loop_through_cut=False;s.loop_detach_add_base=False
   s.part_clearance_mm=gap;s.part_clearance_apply_to=apply_to;s.contact_patch_index=-1;s.contact_choices='[]'
   s.connector_enabled=True;s.connector_male_part=male;s.connector_distribution='CENTER';s.connector_type='CYLINDER'
   s.connector_diameter_mm=6.0;s.connector_length_mm=8.0;s.connector_chamfer_mm=.8;s.connector_edge_margin_mm=.4
   s.clearance_per_side_mm=.15;s.end_clearance_mm=.2;s.assembly_clearance_preset='CUSTOM'
   row['loop_indices']=s.loop_vertex_indices;row['seed_face']=s.loop_seed_face_index
   row['operator_result']=sorted(bpy.ops.chest.splitter_generate_preview());row['session_status']=s.session_status;row['localized_status']=s.get_localized_status()
   parts=ops.get_current_session_parts(scene);row['preview_object_count']=len(parts);row['part_metrics']=[]
   if row['operator_result']!=['FINISHED'] or s.session_status!='PREVIEW_VALID':raise RuntimeError('Pinned preview invalid: '+s.get_localized_status())
   if len(parts)!=2:raise RuntimeError('Expected two preview solids; got '+str(len(parts)))
   for part in parts:
    bm=bmesh.new();bm.from_mesh(part.data);bm.transform(part.matrix_world);bm.normal_update()
    try:
     geom=validate_bmesh_mesh_geometry(bm,1000)
     met={'name':part.name,'verts':len(bm.verts),'faces':len(bm.faces),'volume_mm3':abs(bm.calc_volume())*1e9,
          'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'is_valid':geom.get('is_valid'),
          'reported_non_manifold_edges':geom.get('non_manifold_edges')}
     row['part_metrics'].append(met)
     if not met['is_valid'] or met['nonmanifold_edges'] or met['volume_mm3']<=0:raise RuntimeError('Invalid preview solid: '+json.dumps(met))
    finally:bm.free()
   row['elapsed_seconds']=round(time.perf_counter()-start,3);row['status']='OK'
  except Exception as e:
   row['status']='ERROR';row['error_type']=type(e).__name__;row['error']=str(e);row['traceback']=traceback.format_exc();row['session_status']=getattr(locals().get('s',None),'session_status',None);row['localized_status']=getattr(locals().get('s',None),'get_localized_status',lambda:'' )()
  out.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
Path(__file__).with_name('operator_foot_pins6mm_final_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
