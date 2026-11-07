import bpy,bmesh,sys,json
from pathlib import Path
ROOT=Path(r'C:\Users\guiro\.gemini\antigravity\scratch\chest-blender-part-splitter')
BLEND=Path(r'C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_Arco_Chest_Inteira.blend')
OUT=ROOT/'evidence'/'commercial_cube_20261021'/'arco_base_intersect_experiment.json'
sys.path.insert(0,str(ROOT));import src;src.register();bpy.ops.wm.open_mainfile(filepath=str(BLEND))
import src.geometry_material as gm
from src.geometry_plane import evaluate_bmesh_metrics
from src.geometry_clearance import weld_boolean_roundoff,remove_boolean_wires
from src.diagnostic import validate_bmesh_mesh_geometry
from mathutils.bvhtree import BVHTree
obj=bpy.data.objects['Placa_Arco_Chest_Inteira'];captured=[]
analysis=gm.analyze_material_structure(obj,1,0);target_face_indices=analysis.get('protrusion_face_indices') or analysis.get('region_face_indices')
orig=gm.evaluate_bmesh_metrics
def permit_capture(bm,scale):
 m=orig(bm,scale);captured.append((m.copy(),bm))
 if not m['is_manifold']:m['is_manifold']=True
 return m
gm.evaluate_bmesh_metrics=permit_capture
res=gm.slice_mesh_by_material(obj,1,depth_mm=2.,scene=bpy.context.scene,region_index=0,extraction_mode='BASE',part_clearance_mm=0.)
gm.evaluate_bmesh_metrics=orig
nominal_a,nominal_b=res.bm_a,res.bm_b
scale=bpy.context.scene.unit_settings.scale_length*1000
def mesh_obj(name,bm):
 mesh=bpy.data.meshes.new(name);bm.to_mesh(mesh);ob=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(ob);return ob,mesh
def run_boolean(source_bm,cutter_bm,operation,name,solver='EXACT'):
 source_ob,source_mesh=mesh_obj(name+'_source',source_bm);cutter_ob,cutter_mesh=mesh_obj(name+'_cutter',cutter_bm)
 mats=[];ev=None
 try:
  n=max((f.material_index for f in source_bm.faces),default=0)+1
  for _ in range(n):
   mat=bpy.data.materials.new(name+'_mat');mats.append(mat);source_mesh.materials.append(mat);cutter_mesh.materials.append(mat)
  mod=source_ob.modifiers.new(name,'BOOLEAN');mod.operation=operation;mod.solver=solver;mod.object=cutter_ob;bpy.context.view_layer.update()
  ev=source_ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();out=bmesh.new();out.from_mesh(mesh);weld_boolean_roundoff(out,scale);remove_boolean_wires(out);out.normal_update()
  return out
 finally:
  if ev:ev.to_mesh_clear()
  for ob in (source_ob,cutter_ob):bpy.data.objects.remove(ob,do_unlink=True)
  for mesh in (source_mesh,cutter_mesh):bpy.data.meshes.remove(mesh)
  for mat in mats:bpy.data.materials.remove(mat)
source=bmesh.new();source.from_mesh(obj.data);source.faces.ensure_lookup_table();source.transform(obj.matrix_world);source.normal_update()
source_volume=abs(source.calc_volume())*scale**3
coord_sig=lambda f:tuple(sorted(tuple(round(float(c),9) for c in v.co) for v in f.verts))
source_target_face_signatures={coord_sig(source.faces[fi]):fi for fi in target_face_indices}
nominal_signatures={coord_sig(f) for f in nominal_a.faces}
target_signatures_missing_from_nominal=[fi for sig,fi in source_target_face_signatures.items() if sig not in nominal_signatures]
nom_a_metrics=evaluate_bmesh_metrics(nominal_a,scale);nom_b_metrics=evaluate_bmesh_metrics(nominal_b,scale)
remainder_nominal=run_boolean(source,nominal_a,'DIFFERENCE','arco_base_subtract_nominal')
remainder_nom_metrics=evaluate_bmesh_metrics(remainder_nominal,scale)
def matcounts(bm):return {str(i):sum(f.material_index==i for f in bm.faces) for i in sorted({f.material_index for f in bm.faces})}
nom_tree=BVHTree.FromBMesh(nominal_a);nominal_target_samples=[]
for fi in target_face_indices:
 f=source.faces[fi];loc,norm,idx,dist=nom_tree.find_nearest(f.calc_center_median())
 nominal_target_samples.append({'face':fi,'source_material':f.material_index,'distance_mm':float(dist*scale) if loc else None,'area_mm2':float(f.calc_area()*scale*scale),'centroid_mm':[float(x*scale) for x in f.calc_center_median()]})
experiments=[]
for isolver in ('EXACT','MANIFOLD'):
 trim=run_boolean(source,nominal_a,'INTERSECT',f'arco_base_intersect_{isolver}',isolver)
 tree=BVHTree.FromBMesh(trim);face_lookup={f.index:f for f in source.faces};target_samples=[]
 for fi in target_face_indices:
  f=face_lookup[fi];co=f.calc_center_median();loc,norm,idx,dist=tree.find_nearest(co)
  target_samples.append({'face':fi,'source_material':f.material_index,'distance_mm':float(dist*scale) if loc else None,'area_mm2':float(f.calc_area()*scale*scale),'centroid_mm':[float(x*scale) for x in f.calc_center_median()]})
 for dsolver in ('EXACT','MANIFOLD'):
  rem=run_boolean(source,trim,'DIFFERENCE',f'arco_base_subtract_{isolver}_{dsolver}',dsolver)
  tm=evaluate_bmesh_metrics(trim,scale);rm=evaluate_bmesh_metrics(rem,scale)
  edge_report=lambda bm:[{'index':e.index,'nfaces':len(e.link_faces)} for e in bm.edges if not e.is_manifold]
  delta=tm['volume_mm3']+rm['volume_mm3']-source_volume
  experiments.append({'intersect_solver':isolver,'difference_solver':dsolver,'intersect_A':tm,'intersect_material_faces':matcounts(trim),'remainder_B':rm,'remainder_material_faces':matcounts(rem),'volume_sum_mm3':tm['volume_mm3']+rm['volume_mm3'],'volume_delta_mm3':delta,'volume_delta_pct':delta/source_volume*100,'nonmanifold_edges':{'A':edge_report(trim),'B':edge_report(rem)},'selected_exterior_sample_coverage':{'target_face_count':len(target_samples),'target_area_mm2':sum(x['area_mm2'] for x in target_samples),'centroid_sample_max_distance_mm':max((x['distance_mm'] or 0) for x in target_samples),'samples_over_0_001mm':sum(x['distance_mm'] is None or x['distance_mm']>0.001 for x in target_samples),'outlier_faces':[x for x in target_samples if x['distance_mm'] is None or x['distance_mm']>0.001]}})
  rem.free()
 trim.free()
result={'source_volume_mm3':source_volume,'nominal_A':nom_a_metrics,'nominal_A_material_faces':matcounts(nominal_a),'nominal_B':nom_b_metrics,'nominal_B_material_faces':matcounts(nominal_b),'source_minus_nominal_A':remainder_nom_metrics,'nominal_volume_sum_mm3':nom_a_metrics['volume_mm3']+nom_b_metrics['volume_mm3'],'nominal_volume_delta_mm3':nom_a_metrics['volume_mm3']+nom_b_metrics['volume_mm3']-source_volume,'nominal_selected_exterior_sample_coverage':{'target_face_count':len(nominal_target_samples),'max_distance_mm':max((x['distance_mm'] or 0) for x in nominal_target_samples),'samples_over_0_001mm':sum(x['distance_mm'] is None or x['distance_mm']>0.001 for x in nominal_target_samples),'target_face_signatures_missing_from_nominalA':target_signatures_missing_from_nominal,'missing_count':len(target_signatures_missing_from_nominal)},'solver_experiments':experiments,'original_failure_B_edges':[{'index':e.index,'nfaces':len(e.link_faces)} for e in nominal_b.edges if not e.is_manifold],'decision':{'integrate_fallback':False,'reason':'MANIFOLD/ MANIFOLD and EXACT/MANIFOLD close both solids and conserve total volume, but selected exterior faces/material ownership and BASE clearance/interface behavior are not fully validated. Keep the original BASE rejection until preservation is proven.','case':'Placa_Arco_Chest_Inteira, material slot 1, region 0, BASE, gap 0'}}
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding='utf-8');print('ARCO_BASE_INTERSECT',json.dumps(result,ensure_ascii=False,default=str))
source.free();nominal_a.free();nominal_b.free();remainder_nominal.free()
