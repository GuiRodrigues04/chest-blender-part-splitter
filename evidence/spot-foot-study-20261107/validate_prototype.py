import bpy,bmesh,json,sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
folder=Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(folder/'refined_comparison.blend'))
reference=bpy.data.objects['direct_surface_foot'].data;reference.calc_loop_triangles()
tag=reference.attributes['splitter_contact_surface']
cap_triangles=[t for t in reference.loop_triangles if tag.data[t.polygon_index].value]
cap=BVHTree.FromPolygons([v.co for v in reference.vertices],[tuple(t.vertices) for t in cap_triangles],all_triangles=True)
rows=[]
for gap in (.1,1.):
 obj=bpy.data.objects[f'foot_refined_{gap}_3'];mesh=obj.data;mesh.calc_loop_triangles()
 tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
 distances=[]
 for tri in reference.loop_triangles:
  if tag.data[tri.polygon_index].value:continue
  p=sum((reference.vertices[i].co for i in tri.vertices),Vector())/3
  if cap.find_nearest(p)[3] <= (2*gap+.5)/1000:continue
  distances.append(tree.find_nearest(p)[3]*1000)
 bm=bmesh.new();bm.from_mesh(mesh);remaining=set(bm.faces);components=0
 while remaining:
  components+=1;stack=[remaining.pop()]
  while stack:
   face=stack.pop()
   for edge in face.edges:
    for other in edge.link_faces:
     if other in remaining:remaining.remove(other);stack.append(other)
 row=dict(gap_mm=gap,components=components,nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
          exterior_samples=len(distances),exterior_max_distance_mm=max(distances))
 assert row['components']==1 and row['nonmanifold_edges']==0
 assert row['exterior_max_distance_mm']<.001
 rows.append(row);print('VALIDATE',json.dumps(row),flush=True);bm.free()
(folder/'prototype_validation.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
