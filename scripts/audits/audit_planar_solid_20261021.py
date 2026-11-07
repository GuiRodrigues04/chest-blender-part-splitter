"""Read-only original files; isolated real PLANE/SOLID operator audit."""
from pathlib import Path
import sys,json,time,traceback,hashlib,subprocess,argparse,math,os
ROOT=Path(__file__).resolve().parents[2]
ASSETS=Path(r'C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras')
EVIDENCE=Path(os.environ.get('SPLITTER_AUDIT_OUTPUT',str(ROOT/'evidence/commercial_planar_solid_20261021')))
BINARY=r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
CASES=[('PLANE_X_ZERO','PLANE',0,0.,False),('PLANE_Z_FDM_PINS','PLANE',2,.1,True),('PLANE_X_FDM','PLANE',0,.1,False),('PLANE_DIAGONAL_ZERO','PLANE',-1,0.,False),('SOLID_CORNER_ZERO','SOLID',0,0.,False),('SOLID_CORNER_FDM','SOLID',0,.1,False)]
if os.environ.get('SPLITTER_AUDIT_CASE'):
 CASES=[case for case in CASES if case[0]==os.environ['SPLITTER_AUDIT_CASE']]
 assert CASES,'Unknown audit case filter'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def driver():
 EVIDENCE.mkdir(parents=True,exist_ok=True)
 paths=sorted(ASSETS.rglob('*.blend'))+sorted(ASSETS.glob('*.glb'))+[Path(r'C:\Users\guiro\OneDrive\Desktop\Padrão Testes.blend')]
 manifest=[dict(path=str(p),sha256=digest(p),bytes=p.stat().st_size) for p in paths]
 (EVIDENCE/'originals_before.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
 runs=[]
 for index,path in enumerate(paths):
  name=path.stem+'_'+path.suffix[1:]
  log=EVIDENCE/(name+'.log');start=time.monotonic()
  print('AUDIT_ASSET',index+1,len(paths),name,flush=True)
  try:
   with log.open('wb') as stream:
    result=subprocess.run([BINARY,'-b','--factory-startup','--threads','2','--python-exit-code','1','--python',str(Path(__file__)),'--','--asset',str(path)],stdout=stream,stderr=subprocess.STDOUT,cwd=ROOT,timeout=240)
   code=result.returncode
  except subprocess.TimeoutExpired:code=124
  runs.append(dict(asset=str(path),exit_code=code,seconds=round(time.monotonic()-start,2)))
  (EVIDENCE/'runs.json').write_text(json.dumps(runs,indent=2,ensure_ascii=False),encoding='utf-8')
 for row in manifest:row['unchanged']=digest(Path(row['path']))==row['sha256']
 (EVIDENCE/'originals_after.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
 assert all(x['unchanged'] for x in manifest),'ORIGINAL FILE CHANGED'
 print('ALL_ASSETS_COMPLETE',len(runs),flush=True)

def asset_run(path):
 import bpy,bmesh
 from mathutils import Vector,Matrix
 sys.path.insert(0,str(ROOT));import src;src.register()
 from src.diagnostic import validate_bmesh_mesh_geometry
 from src.operators import get_current_session_parts,verify_preview_current
 EVIDENCE.mkdir(exist_ok=True,parents=True);rows=[]
 output=EVIDENCE/(path.stem+'_'+path.suffix[1:]+'.json')
 def save():output.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
 def load():
  bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=1.
  if path.suffix=='.glb':
   bpy.ops.import_scene.gltf(filepath=str(path))
   objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
  else:
   with bpy.data.libraries.load(str(path)) as (a,b):b.objects=list(a.objects)
   objects=[]
   for obj in b.objects:
    if obj is not None and obj.type=='MESH' and not obj.name.startswith(('SPLITTER','_splitter')):
     bpy.context.scene.collection.objects.link(obj);objects.append(obj)
  assert objects,'No target mesh'
  target=max(objects,key=lambda o:len(o.data.polygons))
  for obj in bpy.context.selected_objects:obj.select_set(False)
  target.select_set(True);bpy.context.view_layer.objects.active=target;bpy.context.view_layer.update()
  bpy.ops.chest.splitter_set_target()
  target=bpy.context.scene.chest_splitter.target_object
  return target,len(objects)
 def bm_world(obj):
  bm=bmesh.new();bm.from_mesh(obj.data);bm.transform(obj.matrix_world)
  if obj.matrix_world.determinant()<0:bmesh.ops.reverse_faces(bm,faces=bm.faces[:])
  return bm
 def signature(obj):
  return (tuple(tuple(v.co) for v in obj.data.vertices),tuple((tuple(f.vertices),f.material_index) for f in obj.data.polygons),tuple(m.name if m else None for m in obj.data.materials))
 def classify(error):
  text=str(error).lower()
  if any(x in text for x in ('clearance','folga','espessura','thickness','margem','margin','connector','pino','encaixe','footprint','intersect','interse','área sólida','solid area')):return 'configuration_rejected'
  return 'failure'
 for name,mode,axis,gap,pins in CASES:
  started=time.monotonic();row=dict(asset=str(path),case=name,mode=mode,gap=gap,pins=pins,status='running');rows.append(row);save()
  try:
   target,count=load();row['import_mesh_objects']=count
   s=bpy.context.scene.chest_splitter
   bm=bm_world(target);before=validate_bmesh_mesh_geometry(bm,1000);bm.free();row['source_before']={k:(len(v) if isinstance(v,list) else v) for k,v in before.items()}
   if not before['is_valid'] or not before['is_manifold']:
    try:row['repair_result']=str(bpy.ops.chest.splitter_repair_target_mesh())
    except RuntimeError as err:row['repair_result']=str(err)
    bm=bm_world(target);check=validate_bmesh_mesh_geometry(bm,1000);bm.free()
    if not check['is_valid'] or not check['is_manifold']:
     row.update(status='source_blocked',reason=s.get_localized_status());continue
   snapshot=signature(target);bm=bm_world(target);volume=abs(bm.calc_volume())*1e9;bm.free();row['source_volume']=volume
   world=[target.matrix_world@v.co for v in target.data.vertices]
   low=Vector(tuple(min(v[i] for v in world) for i in range(3)));high=Vector(tuple(max(v[i] for v in world) for i in range(3)));span=high-low;center=(low+high)/2
   row['dimensions_mm']=list(span*1000)
   s.split_mode=mode;s.view_mode='ASSEMBLED';s.commit_next_target='NONE';s.assembly_clearance_preset='FDM' if gap else 'NONE'
   s.part_clearance_apply_to='PART';s.part_clearance_mm=gap;s.connector_enabled=pins
   s.connector_diameter_mm=2.;s.connector_length_mm=2.;s.connector_chamfer_mm=.2;s.connector_edge_margin_mm=.4;s.connector_distribution='AUTO_SHAPE'
   if mode=='PLANE':
    normal=Vector((1,0,0)) if axis==0 else Vector((0,0,1)) if axis==2 else Vector((.73,.21,.65)).normalized()
    # Off-centre diagonal avoids aligned CAD seams; other cuts bisect bounds.
    origin=center+normal*(max(span)*.07 if axis<0 else 0.)
    s.plane_origin=origin;s.plane_normal=normal;s.plane_offset_mm=0.
    from src.constants import PLANE_GUIDE_NAME
    guide=bpy.data.objects.get(PLANE_GUIDE_NAME)
    if guide:guide.matrix_world=Matrix.Translation(origin)@normal.to_track_quat('Z','Y').to_matrix().to_4x4()
   else:
    # A volumetric half-space box intersects the right third, crossing full other dimensions.
    cut_center=center.copy();cut_center.x=low.x+span.x*.82
    dims=Vector((span.x*.72,span.y*1.6,span.z*1.6))
    bpy.ops.mesh.primitive_cube_add(size=1.,location=cut_center)
    cutter=bpy.context.object;cutter.name='AUDIT_CUTTER';cutter.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    s.solid_source='EXISTING';s.solid_cutter_object=cutter;s.solid_interface_face_index=-1
   bpy.context.view_layer.update()
   result=bpy.ops.chest.splitter_generate_preview();row['preview_return']=str(result)
   if result!={'FINISHED'}:raise RuntimeError(s.get_localized_status())
   assert verify_preview_current(bpy.context)[0],'Preview unexpectedly stale'
   parts=get_current_session_parts(bpy.context.scene);assert len(parts)==2,'Expected exactly two parts'
   metrics=[];cap_positions=[]
   for part in parts:
    bm=bm_world(part);check=validate_bmesh_mesh_geometry(bm,1000)
    assert check['is_valid'] and check['is_manifold'],str(check)
    assert check['volume_mm3']>0,'Nonpositive result volume'
    assert all(0<=f.material_index<len(part.data.materials) for f in bm.faces),'Invalid material index'
    metrics.append(dict(name=part.name,volume=check['volume_mm3'],faces=len(bm.faces)))
    if mode=='PLANE' and not pins:
     values=[]
     for face in bm.faces:
      if abs(face.normal.dot(normal))>.9999:
       positions=[(v.co-origin).dot(normal)*1000 for v in face.verts]
       if max(positions)-min(positions)<.001 and max(abs(x) for x in positions)<gap+.002:
        values.append((face.calc_area(),sum(positions)/len(positions)))
     assert values,'Missing planar contact face'
     cap_positions.append(max(values)[1])
    bm.free()
   row['parts']=metrics
   total=sum(x['volume'] for x in metrics);row['sum_volume']=total
   if gap==0 and not pins:assert abs(total-volume)<=max(.01,volume*1e-5),'No-clearance volume not conserved'
   if not pins:assert total<=volume+max(.01,volume*1e-5),'Cut added unexpected material'
   if cap_positions:
    actual=abs(cap_positions[0]-cap_positions[1]);row['measured_plane_gap_mm']=actual
    assert abs(actual-gap)<.002,'Measured clearance differs from requested: '+str(actual)
   assert signature(target)==snapshot,'Source mesh changed during preview'
   assert bpy.ops.chest.splitter_commit_parts()=={'FINISHED'},s.get_localized_status()
   committed=get_current_session_parts(bpy.context.scene)
   after=[]
   for part in committed:
    bm=bm_world(part);after.append(validate_bmesh_mesh_geometry(bm,1000)['volume_mm3']);bm.free()
   assert sorted(after)==sorted(x['volume'] for x in metrics),'Preview/final volume mismatch'
   assert signature(target)==snapshot,'Source mesh changed during commit'
   row['status']='pass'
   if name=='PLANE_Z_FDM_PINS':
    manual=EVIDENCE/'manual';manual.mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(manual/(path.stem+'_'+path.suffix[1:]+'_planar_pins.blend')))
    row['manual_file']=str(manual/(path.stem+'_'+path.suffix[1:]+'_planar_pins.blend'))
   assert bpy.ops.chest.splitter_revert_cut()=={'FINISHED'},s.get_localized_status()
   assert signature(target)==snapshot,'Source mesh changed after revert'
   row['revert']='pass'
  except Exception as err:
   row['status']=classify(err) if not isinstance(err,AssertionError) else 'assertion_failed'
   row['error']=str(err);row['traceback']=traceback.format_exc()
  finally:
   row['seconds']=round(time.monotonic()-started,3);save();print('AUDIT_CASE',path.name,name,row['status'],row.get('error',''),flush=True)
 print('ASSET_DONE',output,flush=True)

if __name__=='__main__':
 args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
 parser=argparse.ArgumentParser();parser.add_argument('--driver',action='store_true');parser.add_argument('--asset',type=Path);opts=parser.parse_args(args)
 if opts.driver:driver()
 elif opts.asset:asset_run(opts.asset)
 else:parser.error('--driver or --asset required')
