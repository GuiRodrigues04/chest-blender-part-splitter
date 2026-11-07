"""Conservative convex-region completion; never accepts an uncontained hull."""
import bpy,bmesh
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree

def projection_is_simple(points,normal,scale):
 from mathutils.geometry import intersect_line_line_2d
 # The bounded triangulator reports its own vertex limit. Do not run a
 # quadratic projection audit on arbitrarily dense character boundaries.
 if len(points)>128:return True
 if normal.length<1e-8:return False
 u=normal.orthogonal().normalized();v=normal.cross(u).normalized();origin=points[0]
 xy=[Vector(((p-origin).dot(u),(p-origin).dot(v))) for p in points]
 if any((b-a).length*scale<.0001 for a,b in zip(xy,xy[1:]+xy[:1])):return False
 count=len(xy)
 for i in range(count):
  a,b=xy[i],xy[(i+1)%count]
  for j in range(i+1,count):
   if j==i+1 or (i==0 and j==count-1):continue
   c,d=xy[j],xy[(j+1)%count]
   if intersect_line_line_2d(a,b,c,d) is not None:return False
   if min((a-c).length,(a-d).length,(b-c).length,(b-d).length)*scale<.0001:return False
   direction=b-a;length=direction.length
   if length>0 and abs(direction.x*(c-a).y-direction.y*(c-a).x)/length*scale<.0001:
    if abs(direction.x*(d-a).y-direction.y*(d-a).x)/length*scale<.0001:
     u0=(c-a).dot(direction)/(length*length);u1=(d-a).dot(direction)/(length*length)
     if min(1.,max(u0,u1))-max(0.,min(u0,u1))>.0001/(length*scale):return False
 return True

def complete(obj,selected,scale):
 from .geometry_region import mesh_tree,Containment,CONTACT,WEIGHTS
 from .interface_history import archive_contact_marks
 from .geometry_solid import ensure_solid_outward_normals
 from .geometry_clearance import triangulated_source_mesh
 from .geometry_plane import evaluate_bmesh_metrics
 contains=Containment(mesh_tree(obj.data),.0001/scale)
 bm=bmesh.new();objects=[];meshes=[]
 try:
  ids={v for i in selected for v in obj.data.polygons[i].vertices}
  for i in sorted(ids):bm.verts.new(obj.data.vertices[i].co)
  bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
  bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
  ensure_solid_outward_normals(bm)
  metric=evaluate_bmesh_metrics(bm,scale)
  if not metric['is_manifold'] or metric['components']!=1 or metric['volume_mm3']<=.0001:return None
  tree=BVHTree.FromBMesh(bm)
  # Only planar exterior selections supported by the hull qualify.
  for i in selected:
   f=obj.data.polygons[i];p=f.center;hit=tree.find_nearest(p)
   normal=f.normal
   if hit[3]*scale>.0001 or hit[1].dot(normal)<.99999:return None
  for f in bm.faces:
   points=[v.co for v in f.verts]
   if not contains(f.calc_center_median()):return None
   for v in points:
    if not contains(v):return None
   from mathutils.geometry import tessellate_polygon
   for tri in tessellate_polygon([points]):
    tri=[points[p] if isinstance(p,int) else p for p in tri]
    if not all(contains(sum((p*w for p,w in zip(tri,weights)),Vector())) for weights in WEIGHTS):return None
  hull=bpy.data.meshes.new('_region_hull');meshes.append(hull);bm.to_mesh(hull)
  origin=sum((v.co for v in hull.vertices),Vector())/len(hull.vertices)
  src=triangulated_source_mesh(obj.data);meshes.append(src)
  obj.data.calc_loop_triangles()
  provenance=src.attributes.new('_region_source_face','INT','FACE')
  provenance.data.foreach_set('value',[t.polygon_index for t in obj.data.loop_triangles])
  history=bmesh.new()
  try:history.from_mesh(src);ensure_solid_outward_normals(history);archive_contact_marks(history);history.to_mesh(src)
  finally:history.free()
  def difference(left,right):
   data=left.copy();operand=right.copy();meshes.extend((data,operand))
   data.transform(Matrix.Translation(-origin));operand.transform(Matrix.Translation(-origin))
   a=bpy.data.objects.new('_region_boolean',data);b=bpy.data.objects.new('_region_operand',operand);objects.extend((a,b))
   bpy.context.scene.collection.objects.link(a);bpy.context.scene.collection.objects.link(b)
   mod=a.modifiers.new('Contained region','BOOLEAN');mod.operation='DIFFERENCE';mod.object=b
   mod.solver='MANIFOLD' if 'MANIFOLD' in {p.identifier for p in bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items} else 'EXACT'
   bpy.context.view_layer.update();ev=a.evaluated_get(bpy.context.evaluated_depsgraph_get())
   try:
    result=ev.to_mesh().copy();meshes.append(result);result.transform(Matrix.Translation(origin))
    from .geometry_clearance import remove_boolean_wires,weld_boolean_roundoff
    from .diagnostic import sanitize_mesh_micro_degeneracies
    cleaned=bmesh.new()
    try:
     cleaned.from_mesh(result);remove_boolean_wires(cleaned);weld_boolean_roundoff(cleaned,scale)
     sanitize_mesh_micro_degeneracies(cleaned,scale);ensure_solid_outward_normals(cleaned);cleaned.to_mesh(result)
    finally:cleaned.free()
    return result
   finally:ev.to_mesh_clear()
  remainder=difference(src,hull);part=difference(src,remainder)
  source_tree=mesh_tree(src)
  obj.data.calc_loop_triangles()
  src.calc_loop_triangles()
  polygon_ids=[src.attributes['_region_source_face'].data[t.polygon_index].value for t in src.loop_triangles]
  expected_area=sum((obj.data.vertices[t.vertices[1]].co-obj.data.vertices[t.vertices[0]].co).cross(
                    obj.data.vertices[t.vertices[2]].co-obj.data.vertices[t.vertices[0]].co).length*.5
                    for t in obj.data.loop_triangles if t.polygon_index in selected)
  for mesh,partner in ((part,remainder),(remainder,part)):
   check=bmesh.new()
   try:
    check.from_mesh(mesh);ensure_solid_outward_normals(check)
    metric=evaluate_bmesh_metrics(check,scale)
    if not metric['is_manifold'] or metric['components']!=1:return None
    marker=check.faces.layers.int.get(CONTACT) or check.faces.layers.int.new(CONTACT)
    other=mesh_tree(partner)
    exterior_area=0.
    for f in check.faces:
     hit=other.find_nearest(f.calc_center_median());f[marker]=int(hit[0] is not None and hit[3]*scale<.0001 and hit[1].dot(f.normal)<-.99)
     if mesh==part and not f[marker]:
      original=source_tree.find_nearest(f.calc_center_median())
      if (original[0] is None or original[3]*scale>.001 or original[1].dot(f.normal)<.9999
          or polygon_ids[original[2]] not in selected):
       return None
      exterior_area+=f.calc_area()
    if mesh==part and abs(exterior_area-expected_area)*scale*scale>max(.005,expected_area*scale*scale*1e-6):return None
    check.to_mesh(mesh)
   finally:check.free()
  original=bmesh.new();original.from_mesh(src);total=abs(original.calc_volume());original.free()
  volumes=[]
  for mesh in (part,remainder):
   q=bmesh.new();q.from_mesh(mesh);volumes.append(abs(q.calc_volume()));q.free()
  if abs(sum(volumes)-total)*scale**3>max(.001,total*scale**3*1e-7):return None
  output=[]
  for data in (part,remainder):
   result=data.copy();result.transform(obj.matrix_world)
   oriented=bmesh.new()
   try:oriented.from_mesh(result);ensure_solid_outward_normals(oriented);oriented.to_mesh(result)
   finally:oriented.free()
   output.append(result)
  return tuple(output)
 finally:
  bm.free()
  for ob in objects:bpy.data.objects.remove(ob,do_unlink=True)
  for mesh in reversed(meshes):
   if mesh.users==0:bpy.data.meshes.remove(mesh)
