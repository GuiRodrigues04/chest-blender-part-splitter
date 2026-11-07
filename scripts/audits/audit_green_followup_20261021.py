import bpy,bmesh,sys,json,traceback
from pathlib import Path
ROOT=Path(r'C:\Users\guiro\.gemini\antigravity\scratch\chest-blender-part-splitter')
OUT=ROOT/'evidence'/'commercial_cube_20261021';OUT.mkdir(parents=True,exist_ok=True)
BLEND=Path(r'C:\Users\guiro\OneDrive\Desktop\Padrão Testes.blend')
sys.path.insert(0,str(ROOT));import src;src.register()
from src.geometry_material import slice_mesh_by_material,get_material_regions,analyze_material_structure
from src.geometry_loop import slice_mesh_by_loop_extrude
from src.diagnostic import validate_bmesh_mesh_geometry
results=[]
def row(case,status,**kw):
 r={'case':case,'status':status,**kw};results.append(r);print('FOLLOWUP',json.dumps(r,ensure_ascii=False,default=str))
def metrics(bm):
 bm.normal_update();d=validate_bmesh_mesh_geometry(bm,1000)
 mats={str(i):sum(1 for f in bm.faces if f.material_index==i) for i in sorted(set(f.material_index for f in bm.faces))}
 return {'verts':len(bm.verts),'faces':len(bm.faces),'volume_mm3':abs(bm.calc_volume())*1e9,'closed':all(e.is_manifold for e in bm.edges),'valid':d.get('is_valid'),'degenerate':len(d.get('degenerate_faces',[])),'nonmanifold':len(d.get('non_manifold_edges',[])),'material_counts':mats}
def areas(bm,mat=2):return sum(f.calc_area() for f in bm.faces if f.material_index==mat)*1e6
# Two failures from the first audit. Probe explicit material modes and shallow/through extraction.
bpy.ops.wm.open_mainfile(filepath=str(BLEND));
for name,reg_idx in [('Cubo Teste 2',1),('Cubo Teste 2__B',1)]:
 o=bpy.data.objects[name];slot=next((i for i,m in enumerate(o.data.materials) if m and m.name=='Funciona'),2)
 regions=get_material_regions((lambda bm: bm)(bmesh.new()),slot) if False else None
 bm0=bmesh.new();bm0.from_mesh(o.data);bm0.faces.ensure_lookup_table();face_regions=get_material_regions(bm0,slot);region_faces=face_regions[reg_idx];seed=region_faces[0];source_area=sum(bm0.faces[i].calc_area() for i in range(len(bm0.faces)) if bm0.faces[i].material_index==slot)*1e6;bm0.free()
 source=bmesh.new();source.from_mesh(o.data);source.transform(o.matrix_world);source_vol=abs(source.calc_volume())*1e9;source.free()
 analysis=analyze_material_structure(o,slot,reg_idx)
 row(f'overhang_inventory:{name}:region{reg_idx}','PASS',faces=len(region_faces),seed=seed,green_total_area_mm2=source_area,source_volume_mm3=source_vol,analysis={k:analysis.get(k) for k in ('valid','type','base_deviation_mm','has_holes','is_planar_base','error')})
 depths=[0.05,0.1,0.25,0.5,1.0,2.0,5.0,10.0,20.0]
 modes=[('BASE',2.0,False),*(('EXTRUDE',d,t) for d in depths for t in (False,True))]
 for mode,depth,through in modes:
  case=f'material:{name}:region{reg_idx}:{mode}:depth{depth}:through{through}'
  result=None
  try:
   result=slice_mesh_by_material(o,slot,depth_mm=depth,scene=bpy.context.scene,region_index=reg_idx,extraction_mode=mode,through_cut=through)
   ma,mb=metrics(result.bm_a),metrics(result.bm_b);green_area=areas(result.bm_a,slot)+areas(result.bm_b,slot);sumv=ma['volume_mm3']+mb['volume_mm3']
   good=ma['valid'] and mb['valid'] and ma['closed'] and mb['closed']
   row(case,'PASS' if good else 'GEOMETRY_INVALID',A=ma,B=mb,volume_sum_mm3=sumv,source_volume_mm3=source_vol,volume_delta_pct=(sumv-source_vol)/source_vol*100 if source_vol else None,green_area_mm2=green_area,green_area_delta_mm2=green_area-source_area,selected_region_face_count=len(region_faces))
  except Exception as e:
   row(case,'EXPECTED_REJECTION' if type(e).__name__ in ('LocalizedGeometryError','ValueError') else 'ERROR',error=repr(e),message=str(e))
  finally:
   if result: result.bm_a.free();result.bm_b.free()
 # Build same green region selection in actual Edit Mode and capture its boundary through the operator.
 try:
  s=bpy.context.scene.chest_splitter;s.target_object=o;s.split_mode='LOOP';s.loop_behavior='EXTRUDE';s.loop_extrude_depth_mm=2;s.loop_through_cut=False;s.connector_enabled=False;s.commit_next_target='NONE'
  o.hide_viewport=False;o.hide_set(False);bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
  bpy.ops.object.mode_set(mode='EDIT');bpy.context.tool_settings.mesh_select_mode=(False,False,True)
  bm=bmesh.from_edit_mesh(o.data);bm.faces.ensure_lookup_table();selected=set(region_faces)
  for f in bm.faces:f.select_set(f.index in selected)
  bm.faces.active=bm.faces[seed];bmesh.update_edit_mesh(o.data)
  cap=bpy.ops.chest.splitter_capture_face_boundary();indices=[int(x) for x in s.loop_vertex_indices.split(',') if x.strip()]
  caprec={'operator':list(cap),'captured':s.loop_is_captured,'vertex_count':s.loop_vertex_count,'seed':s.loop_seed_face_index,'face_count':len(region_faces),'index_count':len(indices)}
  bpy.ops.object.mode_set(mode='OBJECT')
  row(f'loop_capture:{name}:region{reg_idx}','PASS' if cap=={'FINISHED'} and s.loop_is_captured else 'FAIL',capture=caprec)
  for depth in depths:
   for through in (False,True):
    case=f'loop:{name}:region{reg_idx}:EXTRUDE:depth{depth}:through{through}';result=None
    try:
     result=slice_mesh_by_loop_extrude(o,o.name,indices,s.loop_seed_face_index,depth,through,bpy.context.scene,0.0,'PART',None)
     ma,mb=metrics(result.bm_a),metrics(result.bm_b);sumv=ma['volume_mm3']+mb['volume_mm3']
     row(case,'PASS' if ma['valid'] and mb['valid'] and ma['closed'] and mb['closed'] else 'GEOMETRY_INVALID',A=ma,B=mb,volume_sum_mm3=sumv,source_volume_mm3=source_vol,volume_delta_pct=(sumv-source_vol)/source_vol*100 if source_vol else None,green_area_mm2=areas(result.bm_a,slot)+areas(result.bm_b,slot))
    except Exception as e:row(case,'EXPECTED_REJECTION' if type(e).__name__ in ('LocalizedGeometryError','ValueError') else 'ERROR',error=repr(e),message=str(e))
    finally:
     if result:result.bm_a.free();result.bm_b.free()
 except Exception as e:
  if o.mode=='EDIT':bpy.ops.object.mode_set(mode='OBJECT')
  row(f'loop_capture:{name}:region{reg_idx}','ERROR',error=repr(e),trace=traceback.format_exc(limit=3))
# Exercise the working BASE alternative through the user-facing preview operator.
for name in ('Cubo Teste 2','Cubo Teste 2__B'):
 bpy.ops.wm.open_mainfile(filepath=str(BLEND));o=bpy.data.objects[name];s=bpy.context.scene.chest_splitter
 s.target_object=o;s.split_mode='MATERIAL';s.material_split_index=2;s.material_region_index=1;s.material_extraction_mode='BASE';s.connector_enabled=False;s.part_clearance_mm=0.;s.part_clearance_bottom_enable=False;s.commit_next_target='NONE'
 source_bm=bmesh.new();source_bm.from_mesh(o.data);source_bm.transform(o.matrix_world);source_volume=abs(source_bm.calc_volume())*1e9;source_bm.free()
 source_state=(tuple(tuple(v.co) for v in o.data.vertices),tuple(tuple(p.vertices) for p in o.data.polygons),tuple(p.material_index for p in o.data.polygons))
 try:
  ret=bpy.ops.chest.splitter_generate_preview();parts=[]
  for ob in bpy.context.scene.objects:
   if ob.type=='MESH' and ob.get('chest_role') in ('PREVIEW_A','PREVIEW_B'):
    bm=bmesh.new();bm.from_mesh(ob.data);m=metrics(bm);parts.append({'name':ob.name,**m});bm.free()
  valid=ret=={'FINISHED'} and len(parts)==2 and all(p['closed'] and p['valid'] for p in parts) and abs(sum(p['volume_mm3'] for p in parts)-source_volume)<=source_volume*1e-6
  row(f'operator_base:{name}:region1','PASS' if valid else 'FAIL',operator=list(ret),session_status=s.session_status,source_volume_mm3=source_volume,parts=parts,source_mesh_state_unchanged=source_state==(tuple(tuple(v.co) for v in o.data.vertices),tuple(tuple(p.vertices) for p in o.data.polygons),tuple(p.material_index for p in o.data.polygons)),selected_region_green_faces_in_A=next((p['material_counts'].get('2',0) for p in parts if p['name'].endswith('_A')),0))
  if valid:
   bpy.ops.wm.save_as_mainfile(filepath=str(OUT/f'green_overhang_BASE_{name.replace(" ","_")}_region1.blend'))
   commit=bpy.ops.chest.splitter_commit_parts();opid=s.active_operation_id or s.session_id;revert=bpy.ops.chest.splitter_revert_cut(operation_id=opid)
   row(f'operator_base:{name}:commit-revert','PASS' if commit=={'FINISHED'} and revert=={'FINISHED'} and source_state==(tuple(tuple(v.co) for v in o.data.vertices),tuple(tuple(p.vertices) for p in o.data.polygons),tuple(p.material_index for p in o.data.polygons)) else 'FAIL',commit=list(commit),revert=list(revert),source_mesh_state_restored=source_state==(tuple(tuple(v.co) for v in o.data.vertices),tuple(tuple(p.vertices) for p in o.data.polygons),tuple(p.material_index for p in o.data.polygons)))
 except Exception as e:row(f'operator_base:{name}:region1','ERROR',error=repr(e),trace=traceback.format_exc(limit=3),session_status=s.session_status)
# Explicit same-object LOOP -> MATERIAL transition retaining a real annulus capture.
transition_error=None
for obj_name in ('Cubo Teste','Cubo Teste 2','Cubo Teste 2__B'):
 if transition_error: break
 bpy.ops.wm.open_mainfile(filepath=str(BLEND));o=bpy.data.objects[obj_name];s=bpy.context.scene.chest_splitter
 try:
  s.target_object=o;s.split_mode='LOOP';s.loop_behavior='EXTRUDE';s.loop_extrude_depth_mm=2;s.loop_through_cut=False;s.connector_enabled=False;s.part_clearance_mm=0;s.part_clearance_bottom_enable=False
  fm=bmesh.new();fm.from_mesh(o.data);fm.faces.ensure_lookup_table();islands=get_material_regions(fm,2);candidates=[]
  for ri,fs in sorted(enumerate(islands),key=lambda x:-len(x[1])):
   fset=set(fs)
   for fi in fs:
    if all(len(e.link_faces)==2 and all(lf.index in fset for lf in e.link_faces) for e in fm.faces[fi].edges):
     candidates.append((ri,fs,fi));break
  fm.free();cap=None;chosen=None
  for ri,faces,hole in candidates:
   if ri==0: continue
   seed=faces[0];o.hide_viewport=False;o.hide_set(False);bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
   if o.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
   bpy.ops.object.mode_set(mode='EDIT');bpy.context.tool_settings.mesh_select_mode=(False,False,True);bm=bmesh.from_edit_mesh(o.data);bm.faces.ensure_lookup_table()
   for f in bm.faces:f.select_set(f.index in (set(faces)-{hole}))
   bm.faces.active=bm.faces[faces[0]];bmesh.update_edit_mesh(o.data)
   try:
    cap=bpy.ops.chest.splitter_capture_face_boundary()
    if cap=={'FINISHED'} and s.loop_region_face_indices and len(json.loads(s.loop_boundary_loops or '[]'))>=2:
     chosen=(ri,faces,hole);break
   except RuntimeError: pass
   bpy.ops.object.mode_set(mode='OBJECT')
  if not chosen: raise RuntimeError('No annulus capture candidate passed support-plane validation')
  bpy.ops.object.mode_set(mode='OBJECT');reg,faces,hole=chosen;other_seed=islands[0][0]
  loop_snapshot={k:getattr(s,k) for k in ('loop_is_captured','loop_vertex_count','loop_vertex_indices','loop_seed_face_index','loop_boundary_loops','loop_region_face_indices','loop_topology_signature')}
  loop_signature=(loop_snapshot['loop_is_captured'],loop_snapshot['loop_vertex_count'],loop_snapshot['loop_vertex_indices'],loop_snapshot['loop_seed_face_index'],loop_snapshot['loop_boundary_loops'],loop_snapshot['loop_region_face_indices'],loop_snapshot['loop_topology_signature'])
  stale_faces=json.loads(s.loop_region_face_indices or '[]');boundary_loops=json.loads(s.loop_boundary_loops or '[]')
  from src.geometry_loop import captured_region_faces
  legacy_would_reject_seed=(other_seed not in stale_faces)
  s.split_mode='MATERIAL';s.material_split_index=2;s.material_region_index=0;s.material_extraction_mode='EXTRUDE';s.material_extrude_depth_mm=2;s.connector_enabled=False;s.commit_next_target='NONE'
  resolver=captured_region_faces(o,[int(x) for x in s.loop_vertex_indices.split(',') if x.strip()],other_seed,bpy.context.scene)
  after={k:getattr(s,k) for k in loop_snapshot};after_signature=(after['loop_is_captured'],after['loop_vertex_count'],after['loop_vertex_indices'],after['loop_seed_face_index'],after['loop_boundary_loops'],after['loop_region_face_indices'],after['loop_topology_signature'])
  ret=bpy.ops.chest.splitter_generate_preview();
  parts=[]
  for ob in bpy.context.scene.objects:
   if ob.type=='MESH' and ob.get('chest_role') in ('PREVIEW_A','PREVIEW_B'):
    bm=bmesh.new();bm.from_mesh(ob.data);parts.append({'name':ob.name,**metrics(bm)});bm.free()
  row(f'state_transition:{obj_name}:LOOP_to_MATERIAL_same_target','PASS' if cap=={'FINISHED'} and len(boundary_loops)>=2 and len(stale_faces)>0 and resolver is None and legacy_would_reject_seed and ret=={'FINISHED'} and len(parts)==2 and all(p['closed'] and p['valid'] for p in parts) else 'FAIL',loop_capture_operator=list(cap),captured_hole_face=hole,stale_region_face_count=len(stale_faces),captured_boundary_loop_count=len(boundary_loops),legacy_would_reject_material_seed=legacy_would_reject_seed,updated_resolver_in_material_mode=resolver,loop_fields_preserved=(loop_signature==after_signature),loop_state_before=loop_snapshot,loop_state_after=after,mode=s.split_mode,preview_operator=list(ret),session_status=s.session_status,parts=parts,material_region=0)
  transition_error='done'
 except Exception as e:
  row(f'state_transition:{obj_name}:LOOP_to_MATERIAL_same_target','ERROR',error=repr(e),trace=traceback.format_exc(limit=3),session_status=getattr(s,'session_status',None))
(OUT/'green_overhang_transition_results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
summary={'cases':len(results),'pass':sum(x['status']=='PASS' for x in results),'geometry_invalid':sum(x['status']=='GEOMETRY_INVALID' for x in results),'expected_rejections':sum(x['status']=='EXPECTED_REJECTION' for x in results),'fail':sum(x['status']=='FAIL' for x in results),'errors':sum(x['status']=='ERROR' for x in results),'state_transition':[x for x in results if x['case'].startswith('state_transition')]}
print('FOLLOWUP_SUMMARY',json.dumps(summary,ensure_ascii=False,default=str))
