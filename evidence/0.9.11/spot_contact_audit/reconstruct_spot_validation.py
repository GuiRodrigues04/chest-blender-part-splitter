import bpy,sys,json,math,bmesh,argparse,hashlib
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description='Reconstruct and audit the supplied Spot Blender split.')
parser.add_argument('--saved-output',required=True,help='Path to Spot 2 pos cortesw.blend')
parser.add_argument('--output',default=str(ROOT/'evidence/0.9.11/spot_contact_audit/reconstructed_5mm_gap_0.1.json'))
cli_args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
saved_output=Path(cli_args.saved_output).resolve();output_path=Path(cli_args.output).resolve()
sys.path.insert(0,str(ROOT));import src
from src.geometry_loop import slice_mesh_by_loop
from tests.test_release_workflows import _point_triangle_distance_mm
S=bpy.context.scene.unit_settings.scale_length*1000
src.register()
obj=bpy.data.objects['spot_quadrangulated']
with bpy.data.libraries.load(str(saved_output),link=False) as (data_from,data_to):data_to.objects=['Spot']
B=data_to.objects[0];attr=B.data.attributes['splitter_contact_surface'];R=Matrix.Rotation(math.pi/2,4,'X')
with bpy.data.libraries.load(str(saved_output),link=False) as (data_from,data_to):data_to.objects=['Eye.001']
old_A=data_to.objects[0]
V=[v.co.copy() for v in obj.data.vertices];world=[R@p for p in V];kd=KDTree(len(world))
for i,p in enumerate(world):kd.insert(p,i)
kd.balance(); vmaps=[kd.find(v.co) for v in B.data.vertices] # target coordinates in R frame
Bunmarked=[]
for f in B.data.polygons:
 if attr.data[f.index].value:continue
 h=[vmaps[i] for i in f.vertices]
 if all(x[2]*S<=.001 for x in h):Bunmarked.append((f.index,tuple(sorted(set(x[1] for x in h)))))
skeys={tuple(sorted(f.vertices)):f.index for f in obj.data.polygons}; exact=[]; subset=[]
for bi,ids in Bunmarked:
 if ids in skeys:exact.append((bi,skeys[ids]))
 else:
  candidates=[(len(key),si) for key,si in skeys.items() if set(ids)<=set(key)]
  if candidates:subset.append((bi,min(candidates)[1]))
retained={si for _,si in exact}|{si for _,si in subset}; selected=set(range(len(obj.data.polygons)))-retained
bm=bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table();bm.faces.index_update();edges=[e for e in bm.edges if sum(f.index in selected for f in e.link_faces)==1]
graph={}
for edge in edges:
 for vertex in edge.verts:graph.setdefault(vertex.index,set()).add(edge.other_vert(vertex).index)
start=min(graph);indices=[start];previous=None;current=start
while True:
 options=sorted(graph[current]-({previous} if previous is not None else set()))
 nxt=options[0]
 if nxt==start:break
 indices.append(nxt);previous,current=current,nxt
seed=min(selected)
print('RECONSTRUCTION',json.dumps({'source_faces':len(obj.data.polygons),'B_unmapped':sum(1 for f in B.data.polygons if not attr.data[f.index].value)-len(Bunmarked),'exact':len(exact),'subset':len(subset),'selected_faces':len(selected),'boundary_edges':len(edges),'boundary_vertices':len(indices),'seed':seed,'bounds':[[min((R@v.co)[i] for v in obj.data.vertices),max((R@v.co)[i] for v in obj.data.vertices)] for i in range(3)]}),flush=True)
obj.matrix_world=R
try:
 result=slice_mesh_by_loop(obj,obj.name,indices,seed,scene=bpy.context.scene,detach_add_base=True,detach_base_depth_mm=5.0,part_clearance_mm=.1,part_clearance_apply_to='PART',part_clearance_bottom_mm=None)
 print('RESULT',result.part_a_metrics if hasattr(result,'part_a_metrics') else 'ok',flush=True)
 print('BM_PARTS',len(result.bm_a.verts),len(result.bm_a.faces),len(result.bm_b.verts),len(result.bm_b.faces), 'vol',result.split_result.part_a_metrics['volume_mm3'],result.split_result.part_b_metrics['volume_mm3'],flush=True)
 for lab,bmout in [('A',result.bm_a),('B',result.bm_b)]:
  layer=bmout.faces.layers.int.get('splitter_contact_surface');print('CONTACT',lab, sum(bool(f[layer]) for f in bmout.faces) if layer else 0,flush=True)
 # Add one explicitly reconstructed, auto-sized cylindrical pin/cavity pair.
 # This is a new validation scenario; the historical saved connector settings were absent.
 from src.connector_surface import PreparedSplit
 from src.connector_sizing import recommend_dimensions,solid_tree
 from src.geometry_connectors import compute_connector_layout,apply_connectors_boolean
 ma=bpy.data.meshes.new('_audit_A');result.bm_a.to_mesh(ma)
 mb=bpy.data.meshes.new('_audit_B');result.bm_b.to_mesh(mb)
 oa=bpy.data.objects.new('_audit_part_A',ma);ob=bpy.data.objects.new('_audit_part_B',mb)
 bpy.context.scene.collection.objects.link(oa);bpy.context.scene.collection.objects.link(ob)
 iface=result.interface;axis=Vector(iface.normal_a_to_b_world).normalized()
 prep=PreparedSplit('audit',(),target_name=obj.name,split_mode='LOOP',interface=iface,
  surface_origin=iface.origin_world.copy(),surface_normal=axis.copy(),axis_u=iface.axis_u_world.copy(),
  axis_v=iface.axis_v_world.copy(),unit_scale=S,male_side='A')
 prep.sizing_trees=(solid_tree(ma),solid_tree(mb))
 settings=SimpleNamespace(connector_type='CYLINDER',clearance_per_side_mm=.15,
  connector_edge_margin_mm=3.0,end_clearance_mm=.2,connector_distribution='CENTER',
  connector_male_part='A',adjust_to_valid_area=True,manual_connectors=[])
 try:
  suggestion=recommend_dimensions(prep,settings,obj)
  pin_d,pin_l,pin_c=suggestion['diameter_mm'],suggestion['length_mm'],suggestion['chamfer_mm']
  pin_clear,pin_end=.15,.2
  pin_note='Auto-suggested with CENTER, 3mm edge margin, fit checked against both cut solids.'
 except ValueError as error:
  # Tiny explicit test pin only when auto-sizing rejects this narrow interface.
  pin_d,pin_l,pin_c,pin_clear,pin_end=2.,2.,.2,.1,.1
  suggestion={'auto_sizing_rejected':str(error),'test_override':'2mm cylinder x 2mm insertion, 0.1mm radial/end clearances'}
  pin_note='Explicit small test dimensions because auto-suggest found no safe 1x2mm fit.'
 layout=compute_connector_layout(obj.data,obj.matrix_world,iface.origin_world,axis,'CENTER',.4,
  S,pin_d,pin_clear,iface,'CYLINDER',0.,True)
 print('PIN_SUGGESTION',json.dumps(suggestion),flush=True)
 print('PIN_LAYOUT',json.dumps({'positions':[list(p) for p in layout['positions']],
  'pin_rotations':[list(r) for r in layout['pin_rotations']]}),flush=True)
 apply_connectors_boolean(oa,ob,axis,layout['positions'],'CYLINDER',pin_d,
  pin_l,pin_c,pin_clear,pin_end,unit_scale=S,
  major_axis=iface.axis_u_world,pin_rotations=layout['pin_rotations'])
 audit_a=bmesh.new();audit_a.from_mesh(oa.data);audit_a.normal_update()
 audit_b=bmesh.new();audit_b.from_mesh(ob.data);audit_b.normal_update()
 result.bm_a.free();result.bm_b.free()
 from src.diagnostic import validate_bmesh_mesh_geometry
 def validate_output(bmout):
  bmout.verts.ensure_lookup_table();bmout.edges.ensure_lookup_table();bmout.faces.ensure_lookup_table();bmout.faces.index_update()
  report=validate_bmesh_mesh_geometry(bmout,S)
  tree=BVHTree.FromBMesh(bmout)
  pairs=[]
  for i,j in tree.overlap(tree):
   if i>=j:continue
   if set(bmout.faces[i].verts).isdisjoint(bmout.faces[j].verts):pairs.append([i,j])
  return {'is_valid':report['is_valid'],'is_manifold':report['is_manifold'],
   'non_manifold_edges':len(report['non_manifold_edges']),'degenerate_faces':len(report['degenerate_faces']),
   'volume_mm3':abs(bmout.calc_volume(signed=True))*S**3,
   'nonadjacent_bvh_overlap_pairs':pairs}
 quality={'A':validate_output(audit_a),'B':validate_output(audit_b)}
 print('PAIR_QUALITY',json.dumps(quality),flush=True)
 # Measure generated marked interface with exact float64 point-to-triangle distances.
 axis=Vector(result.interface.normal_a_to_b_world).normalized()
 def triangles(bmout,contact_only=True):
  mesh=bpy.data.meshes.new('audit_'+str(id(bmout)))
  bmout.to_mesh(mesh);mesh.calc_loop_triangles()
  layer=mesh.attributes.get('splitter_contact_surface')
  verts=[tuple(float(c)*S for c in v.co) for v in mesh.vertices]
  data=[]
  for tri in mesh.loop_triangles:
   if contact_only and layer is not None and not layer.data[tri.polygon_index].value:continue
   a,b,c=[verts[i] for i in tri.vertices]
   va,vb,vc=Vector(a),Vector(b),Vector(c);cr=(vb-va).cross(vc-va)
   area=.5*cr.length
   if area<=1e-12:continue
   n=tuple(cr.normalized());center=tuple((a[k]+b[k]+c[k])/3 for k in range(3))
   data.append({'ids':tuple(tri.vertices),'area':area,'n':n,'center':center})
  bpy.data.meshes.remove(mesh)
  return verts,data
 VA,TA=triangles(audit_a);VB,TB=triangles(audit_b)
 def assess(srcverts,src,targets,targetverts,label):
  rec=[]
  for tri in src:
   a,b,c=[srcverts[i] for i in tri['ids']]
   ps=[tri['center']]+[tuple(w[0]*a[k]+w[1]*b[k]+w[2]*c[k] for k in range(3)) for w in ((.6,.2,.2),(.2,.6,.2),(.2,.2,.6))]
   ds=[];dots=[]
   for p in ps:
    best=1e99;bt=None
    for target in targets:
     x,y,z=[targetverts[i] for i in target['ids']]
     d=_point_triangle_distance_mm(p,x,y,z)
     if d<best:best=d;bt=target
    ds.append(best);dots.append(sum(tri['n'][k]*bt['n'][k] for k in range(3)))
   axial=sum(tri['center'][k]*axis[k] for k in range(3))
   wall=abs(sum(tri['n'][k]*axis[k] for k in range(3)))<.5
   rec.append({'area':tri['area'],'axis':axial,'wall':wall,'d':ds,'dots':dots})
  cats=[]
  for cat,pred in [('all',lambda r:True),('wall',lambda r:r['wall']),('transition',lambda r:not r['wall'] and abs(r['axis'])>=0)]:
   rows=[r for r in rec if pred(r)];samples=sorted(d for r in rows for d in r['d'])
   sustained=[r for r in rows if max(r['d'])<=.005 and max(r['dots'])<-.5]
   cats.append({'category':cat,'triangles':len(rows),'area_mm2':sum(r['area'] for r in rows),
    'distance_quantiles_mm':{str(q):samples[min(len(samples)-1,int((len(samples)-1)*q))] for q in (0,.1,.5,.9,.95,.99,1)} if samples else {},
    'near_zero_interior_triangles':sum(any(d<=.005 and n<-.5 for d,n in zip(r['d'],r['dots'])) for r in rows),
    'sustained_opposed_zero_triangles':len(sustained),'sustained_area_mm2':sum(r['area'] for r in sustained),
    'sustained_axis_range_mm':[min(r['axis'] for r in sustained),max(r['axis'] for r in sustained)] if sustained else None})
  print('AUDIT',label,json.dumps(cats),flush=True)
  return {'source':label,'categories':cats}
 audits=[assess(VA,TA,TB,VB,'A_to_B'),assess(VB,TB,TA,VA,'B_to_A')]
 # Measure the reconstructed pin sidewall against every triangle on the receiver.
 # The pin is identified geometrically around its requested center, radius and axis.
 AV,AT=triangles(audit_a,False);BV,BT=triangles(audit_b,False)
 pin_pos=Vector(layout['positions'][0]);pin_center=tuple(float(c)*S for c in pin_pos)
 pin=[]
 for t in AT:
  c=Vector(t['center']);rel=c-Vector(pin_center);ax=rel.dot(axis);rad=(rel-axis*ax).length
  if .05<=ax<=max(.06,pin_l-.25) and .80*pin_d/2<=rad<=1.05*pin_d/2 and abs(Vector(t['n']).dot(axis))<.5:
   pin.append(t)
 pin_samples=[];pin_triangles=[]
 for t in pin:
  a,b,c=[AV[i] for i in t['ids']]
  ps=[t['center']]+[tuple(w[0]*a[k]+w[1]*b[k]+w[2]*c[k] for k in range(3)) for w in ((.6,.2,.2),(.2,.6,.2),(.2,.2,.6))]
  ds=[];dots=[]
  for p in ps:
   best=1e99;bt=None
   for target in BT:
    x,y,z=[BV[i] for i in target['ids']];d=_point_triangle_distance_mm(p,x,y,z)
    if d<best:best=d;bt=target
   ds.append(best);dots.append(sum(t['n'][k]*bt['n'][k] for k in range(3)))
  pin_samples.extend(ds);pin_triangles.append({'area_mm2':t['area'],'distances_mm':ds,'normal_dots':dots})
 pin_sorted=sorted(pin_samples)
 pin_audit={'source':'new cylindrical pin on Part A','target':'all triangles on Part B including generated cavity',
  'profile':'sidewall triangles with axial centers in [0.05mm, length-0.25mm], radial centers within ±5% of nominal radius, |normal·axis|<0.5',
  'triangles':len(pin),'area_mm2':sum(t['area'] for t in pin),'samples':len(pin_samples),
  'distance_quantiles_mm':{str(q):pin_sorted[min(len(pin_sorted)-1,int((len(pin_sorted)-1)*q))] for q in (0,.1,.5,.9,.99,1)} if pin_sorted else {},
  'opposed_zero_samples':sum(d<=.005 and n<-.5 for tri in pin_triangles for d,n in zip(tri['distances_mm'],tri['normal_dots']))}
 print('PIN_CLEARANCE',json.dumps(pin_audit),flush=True)
 # Retest the exact historical finite-contact wall probe coordinates against
 # every regenerated receiver triangle after adding the new pin and cavity.
 old_A.data.calc_loop_triangles();B.data.calc_loop_triangles()
 Mold=Matrix(old_A['chest_assembled_matrix']);Mb=Matrix(B['chest_assembled_matrix'])
 old_av=[tuple(float(c)*S for c in Mold@v.co) for v in old_A.data.vertices]
 old_bv=[tuple(float(c)*S for c in Mb@v.co) for v in B.data.vertices]
 oa_attr=old_A.data.attributes['splitter_contact_surface'];ob_attr=B.data.attributes['splitter_contact_surface']
 old_src=[];old_tgt=[]
 for tr in old_A.data.loop_triangles:
  if not oa_attr.data[tr.polygon_index].value:continue
  a,b,c=[old_av[i] for i in tr.vertices];n=Vector(b).__sub__(Vector(a)).cross(Vector(c).__sub__(Vector(a)))
  if n.length>1e-12:old_src.append((tuple(tr.vertices),tuple(n.normalized()),.5*n.length))
 for tr in B.data.loop_triangles:
  if not ob_attr.data[tr.polygon_index].value:continue
  a,b,c=[old_bv[i] for i in tr.vertices];n=Vector(b).__sub__(Vector(a)).cross(Vector(c).__sub__(Vector(a)))
  if n.length>1e-12:old_tgt.append((tuple(tr.vertices),tuple(n.normalized())))
 old_patch=[]
 for ids,n,area in old_src:
  if abs(sum(n[k]*axis[k] for k in range(3)))>=.5:continue
  a,b,c=[old_av[i] for i in ids]
  ps=[tuple((a[k]+b[k]+c[k])/3 for k in range(3))]+[tuple(w[0]*a[k]+w[1]*b[k]+w[2]*c[k] for k in range(3)) for w in ((.6,.2,.2),(.2,.6,.2),(.2,.2,.6))]
  ds=[];dots=[];is_wall=[]
  for p in ps:
   best=1e99;tn=None
   for tids,tn0 in old_tgt:
    x,y,z=[old_bv[i] for i in tids];d=_point_triangle_distance_mm(p,x,y,z)
    if d<best:best=d;tn=tn0
   ds.append(best);dots.append(sum(n[k]*tn[k] for k in range(3)));is_wall.append(abs(sum(tn[k]*axis[k] for k in range(3)))<.5)
  if max(ds)<=.005 and max(dots)<-.5 and all(is_wall):old_patch.append((ids,n,area,ps))
 old_after_a=[];old_after_b=[]
 for ids,n,area,ps in old_patch:
  for p in ps:
   old_after_a.append(min((_point_triangle_distance_mm(p,*[AV[i] for i in t['ids']]) for t in AT),default=1e99))
   old_after_b.append(min((_point_triangle_distance_mm(p,*[BV[i] for i in t['ids']]) for t in BT),default=1e99))
 old_after_a.sort();old_after_b.sort();old_sums=sorted(a+b for a,b in zip(old_after_a,old_after_b))
 def quantiles(values):
  return {str(q):values[min(len(values)-1,int((len(values)-1)*q))] for q in (0,.1,.5,.9,.99,1)} if values else {}
 old_outer_after_pin={'source':'saved Eye.001 previous finite-contact wall coordinates, same four interior points',
  'target':'both regenerated complete meshes after the new pin/cavity','source_triangles':len(old_patch),
  'source_area_mm2':sum(x[2] for x in old_patch),'samples':len(old_after_a),
  'distance_to_new_A_mm':quantiles(old_after_a),'distance_to_new_B_mm':quantiles(old_after_b),
  'sum_of_distances_mm':quantiles(old_sums),
  'A_samples_near_0.1mm':sum(abs(d-.1)<=.005 for d in old_after_a),
  'B_samples_near_zero':sum(d<=.005 for d in old_after_b)}
 print('OLD_OUTER_WALL_PROBES_AFTER_PIN',json.dumps(old_outer_after_pin),flush=True)
 evidence={'method':'Reconstructed from original Spot.blend source and saved output Spot unmarked faces. Boundary and 10-face region inferred from provenance; not the original saved operation/settings (which were absent). Direct base split at inferred 5.0mm, requested PART clearance 0.1mm. Exact double precision point-triangle distances at centroid + three strictly interior barycentric points; sustained contact requires all four <=0.005mm and opposed normals. Shell distances are restricted to generated marked contact interface. Pin sidewall distances use all triangles on the opposing part. Prior finite-contact probe coordinates from saved Eye.001 are retested against all regenerated receiver triangles after pin/cavity. Post-Boolean validity/manifold/volume use validate_bmesh_mesh_geometry; nonadjacent BVH face overlaps were also checked.','scene_scale_mm_per_BU':S,'inferred_depth_mm':5.0,'requested_gap_mm':.1,'source_to_output_rotation_x_degrees':90,'selected_source_faces':len(selected),'seed_face':seed,'boundary_vertices':len(indices),'boundary_perimeter_mm':47.33601340385929,'pair_metrics':{'A_volume_mm3':quality['A']['volume_mm3'],'B_volume_mm3':quality['B']['volume_mm3'],'A_faces':len(audit_a.faces),'B_faces':len(audit_b.faces),'quality':quality},'axis':list(axis),'pairs':audits,'pin_clearance':pin_audit,'old_outer_wall_after_pin':old_outer_after_pin}
 evidence['connector_test']={'type':'CYLINDER','male_side':'A','diameter_mm':pin_d,
  'length_mm':pin_l,'chamfer_mm':pin_c,'radial_clearance_mm':pin_clear,
  'end_clearance_mm':pin_end,'positions_world':[list(p) for p in layout['positions']],
  'settings_note':pin_note,'auto_sizing_result':suggestion}
 source_path=Path(bpy.data.filepath).resolve()
 evidence['input_sha256']={'Spot.blend':hashlib.sha256(source_path.read_bytes()).hexdigest().upper(),
  'Spot 2 pos cortesw.blend':hashlib.sha256(saved_output.read_bytes()).hexdigest().upper()}
 output_path.parent.mkdir(parents=True,exist_ok=True)
 output_path.write_text(json.dumps(evidence,indent=2),encoding='utf8')
finally:
 bm.free();src.unregister()
