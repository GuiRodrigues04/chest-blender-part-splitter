"""Study only: natural loop closure + extended Solidify blade + Exact Boolean."""
import bpy,bmesh,sys,json,traceback
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
import src;src.register()
from src.geometry_clearance import subtract_closed_region,triangulated_source_mesh
from src.geometry_material import _order_boundary_loops
from src.geometry_contract import boundary_normal
bpy.ops.wm.open_mainfile(filepath=str(Path(__file__).parent/'initial_comparison.blend'))
scene=bpy.context.scene
foot=bpy.data.objects['direct_surface_foot'];body=bpy.data.objects['direct_surface_body']
visible=triangulated_source_mesh(foot.data)
source=bmesh.new();source.from_mesh(visible);bpy.data.meshes.remove(visible);source.normal_update()
marker=source.faces.layers.int.get('splitter_contact_surface');cap=[f for f in source.faces if f[marker]]
boundary=[e for e in source.edges if sum(f in cap for f in e.link_faces)==1]
loop=_order_boundary_loops(boundary)[0]
normal=sum((f.normal*f.calc_area() for f in cap),Vector()).normalized()
if boundary_normal([v.co for v in loop]).dot(normal)<0:loop.reverse()
center=sum((v.co for v in loop),Vector())/len(loop)

def cap_tree(mesh):
 bm=bmesh.new();bm.from_mesh(mesh);layer=bm.faces.layers.int.get('splitter_contact_surface')
 bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if layer and f[layer]])
 triangles=[tuple(v.co.copy() for v in f.verts) for f in bm.faces if layer and f[layer]]
 coords=[p for tri in triangles for p in tri]
 tree=BVHTree.FromPolygons(coords,[tuple(range(i,i+3)) for i in range(0,len(coords),3)],all_triangles=True)
 samples=[sum((p*w for p,w in zip(tri,weights)),Vector()) for tri in triangles
          for weights in ((1/3,1/3,1/3),(.6,.2,.2),(.2,.6,.2),(.2,.2,.6))]
 bm.free();return tree,samples

body_tree,body_samples=cap_tree(body.data)
results=[]
for gap in (.1,1.):
 for subdivision in (0,3):
  mode='NON_MANIFOLD'
  row=dict(gap_mm=gap,solidify_mode=mode,subdivision=subdivision)
  sheet=bmesh.new();sheet_marker=sheet.faces.layers.int.new('splitter_contact_surface')
  lookup={v:sheet.verts.new(v.co) for f in cap for v in f.verts}
  for f in cap:
   new=sheet.faces.new([lookup[v] for v in f.verts]);new[sheet_marker]=1
  outer=[]
  for v in loop:
   direction=v.co-center;direction-=normal*direction.dot(normal)
   outer.append(sheet.verts.new(v.co+direction.normalized()*.02))
  for i,v in enumerate(loop):
   j=(i+1)%len(loop);new=sheet.faces.new((lookup[v],outer[i],outer[j],lookup[loop[j]]));new[sheet_marker]=1
  if subdivision:
   bmesh.ops.triangulate(sheet,faces=sheet.faces[:])
   bmesh.ops.subdivide_edges(sheet,edges=sheet.edges[:],cuts=subdivision,use_grid_fill=True)
  sheet.normal_update()
  mesh=bpy.data.meshes.new('Blade surface');sheet.to_mesh(mesh);sheet.free()
  knife=bpy.data.objects.new(f'Blade_{gap}_{mode}',mesh);scene.collection.objects.link(knife)
  modifier=knife.modifiers.new('Measured clearance blade','SOLIDIFY');modifier.thickness=gap/1000;modifier.offset=-1
  modifier.solidify_mode=mode;modifier.use_even_offset=True;modifier.use_quality_normals=True
  if mode=='NON_MANIFOLD':modifier.nonmanifold_thickness_mode='CONSTRAINTS'
  modifier.thickness_clamp=0
  evaluated=None;cutter=None;result=None
  try:
   scene.view_layers[0].update();evaluated=knife.evaluated_get(bpy.context.evaluated_depsgraph_get())
   cutter=bmesh.new();cutter.from_mesh(evaluated.to_mesh());cutter.normal_update()
   row['blade_bad_edges']=sum(not e.is_manifold for e in cutter.edges)
   if row['blade_bad_edges']:raise ValueError('Blade is not closed')
   result=subtract_closed_region(source,cutter,1000.)
   output=bpy.data.meshes.new('Blade result');result.to_mesh(output)
   obj=bpy.data.objects.new(f'foot_refined_{gap}_{subdivision}',output);scene.collection.objects.link(obj);obj.hide_set(True)
   tree,samples=cap_tree(output)
   distances=[body_tree.find_nearest(p)[3]*1000 for p in samples]
   opposite=[tree.find_nearest(p)[3]*1000 for p in body_samples]
   ray_distances=[];missed=0
   for p in body_samples:
    hit=body_tree.find_nearest(p);direction=hit[1]
    ray=tree.ray_cast(p-direction*1e-6,direction)
    if ray[0] is None:missed+=1
    else:ray_distances.append((ray[3]-1e-6)*1000)
   row.update(status='OK',bad_edges=sum(not e.is_manifold for e in result.edges),
      vertices=len(result.verts),faces=len(result.faces),volume_mm3=abs(result.calc_volume())*1e9,
      removed_mm3=(abs(source.calc_volume())-abs(result.calc_volume()))*1e9,
      nearest_from_foot_mm=[min(distances),sum(distances)/len(distances),max(distances)],
      nearest_from_body_mm=[min(opposite),sum(opposite)/len(opposite),max(opposite)],
      normal_ray_mm=[min(ray_distances),sum(ray_distances)/len(ray_distances),max(ray_distances)] if ray_distances else [],ray_misses=missed)
  except Exception as error:row.update(status='ERROR',error=str(error),traceback=traceback.format_exc())
  finally:
   if evaluated:evaluated.to_mesh_clear()
   if cutter:cutter.free()
   if result:result.free()
   knife.hide_set(True)
  results.append(row);print('BLADE',json.dumps(row),flush=True)
source.free()
(Path(__file__).parent/'refined_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for obj in scene.objects:obj.hide_set(True)
body.hide_set(False)
if 'foot_refined_1.0_3' in bpy.data.objects:
 obj=bpy.data.objects['foot_refined_1.0_3'];obj.hide_set(False);bpy.context.view_layer.objects.active=obj
bpy.ops.wm.save_as_mainfile(filepath=str(Path(__file__).parent/'refined_comparison.blend'))
