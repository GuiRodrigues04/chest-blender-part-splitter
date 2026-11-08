import bpy,bmesh,sys,json,traceback,statistics,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root));import src;src.register()
from src.geometry_loop import slice_mesh_by_loop
file=Path.home()/'OneDrive/Desktop/Modelos 3D e testes extensao/02_Personagens_e_Criaturas/spot/spot/Vaquinha pos cortes.blend'
results=[]
for gap,side in [(0.,'PART'),(.1,'PART'),(.2,'PART'),(.5,'PART'),(1.,'PART'),(.1,'CAVITY'),(.1,'BOTH'),(1.,'CAVITY'),(1.,'BOTH')]:
 bpy.ops.wm.open_mainfile(filepath=str(file),use_scripts=False);scene=bpy.context.scene;s=scene.chest_splitter;obj=s.target_object;ids=[int(i) for i in s.loop_vertex_indices.split(',')]
 row={'gap_mm':gap,'side':side}
 try:
  obj.data.calc_loop_triangles();source_points=[obj.matrix_world@v.co for v in obj.data.vertices]
  zero=slice_mesh_by_loop(obj,obj.name,ids,s.loop_seed_face_index,scene,part_clearance_mm=0.,part_clearance_apply_to=side) if gap>0 else None
  r=slice_mesh_by_loop(obj,obj.name,ids,s.loop_seed_face_index,scene,part_clearance_mm=gap,part_clearance_apply_to=side)
  row.update(status='OK',closure=r.interface.closure_strategy,strategy=getattr(r.interface,'clearance_strategy','OFFSET'),measurements=getattr(r.interface,'clearance_measurements',None),patches=[r.interface.final_contact_a is not None,r.interface.final_contact_b is not None],bad=[sum(not e.is_manifold for e in bm.edges) for bm in r])
  cutoff=3*gap+.1;origin=Vector(r.interface.origin_world);normal=Vector(r.interface.normal_a_to_b_world).normalized();sampled=[]
  zero_iface=(zero.interface if zero else r.interface);zcoords=[];zpolys=[];zlookup={}
  for tri in zero_iface.interface_triangles_world:
   face=[]
   for point in tri:
    key=tuple(float(x) for x in point)
    if key not in zlookup:zlookup[key]=len(zcoords);zcoords.append(Vector(point))
    face.append(zlookup[key])
   zpolys.append(face)
  zero_tree=BVHTree.FromPolygons(zcoords,zpolys,all_triangles=True)
  for tri in obj.data.loop_triangles:
   pts=[source_points[i] for i in tri.vertices];center=sum(pts,Vector())/3;nearest_zero=zero_tree.find_nearest(center)
   if nearest_zero and nearest_zero[0] is not None and nearest_zero[3]*1000.0>cutoff:sampled.append(center)
  coords=[];polys=[]
  for bm in r:
   visible=bpy.data.meshes.new('exterior_visible_tessellation');bm.to_mesh(visible);visible.calc_loop_triangles();offset=len(coords);coords.extend([v.co.copy() for v in visible.vertices]);polys.extend([tuple(offset+i for i in tri.vertices) for tri in visible.loop_triangles]);bpy.data.meshes.remove(visible)
  tree=BVHTree.FromPolygons(coords,polys,all_triangles=True)
  dists=[]
  for point in sampled:
   hit=tree.find_nearest(point)
   if hit and hit[0] is not None:dists.append(hit[3]*1000.0)
  row['exterior_probe']={'cutoff_mm':cutoff,'source_triangles':len(sampled),'max_deviation_mm':max(dists) if dists else None,'p95_deviation_mm':sorted(dists)[int(.95*(len(dists)-1))] if dists else None,'mean_deviation_mm':statistics.fmean(dists) if dists else None,'unmatched':len(sampled)-len(dists)}
  for bm in r:bm.free()
  if zero:
   for bm in zero:bm.free()
 except Exception as e:row.update(status='ERROR',error=str(e),traceback=traceback.format_exc())
 results.append(row);print(json.dumps(row),flush=True)
Path(__file__).with_name('foot_results_exterior_final.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
