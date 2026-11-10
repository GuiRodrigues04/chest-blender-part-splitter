"""Measure the real Spot eye's wall and floor clearance below its shoulder.

This reads the user's blend, calls the geometry API directly (so no preview
explosion transforms are involved), and never saves the source file.
"""
import sys, json, hashlib, traceback
from pathlib import Path
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

REPO = Path(__file__).resolve().parents[2]
BLEND = Path(r"C:\Users\guiro\OneDrive\Desktop\Spot corte bugado.blend")
OUT = Path(__file__).with_name('eye_wall_floor_measurements.json')
sys.path.insert(0, str(REPO))
import src
src.register()
bpy.ops.wm.open_mainfile(filepath=str(BLEND), use_scripts=False)
scene = bpy.context.scene
settings = scene.chest_splitter
obj = settings.target_object
if obj.mode == 'EDIT':
    obj.update_from_editmode(); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='OBJECT')

from src.geometry_loop import analyze_loop_region, slice_mesh_by_loop_extrude
from src.geometry_region import mesh_signature
from src.diagnostic import get_scene_scale_to_mm, validate_bmesh_mesh_geometry
from src.geometry_clearance_blade import _samples

file_hash_before = hashlib.sha256(BLEND.read_bytes()).hexdigest()
signature_before = mesh_signature(obj.data)
indices = [int(x) for x in settings.loop_vertex_indices.split(',') if x.strip()]
seed = int(settings.loop_seed_face_index)
depth = float(settings.loop_extrude_depth_mm)
scale = get_scene_scale_to_mm(scene)
analysis = analyze_loop_region(obj, indices, seed, scene=scene, probe_direct_closure=False)
axis = Vector(analysis['inward_dir_world']).normalized()
coords = analysis['coords_world']
center = Vector(analysis['centroid_world'])
n_out = -axis
support = center + n_out * min((Vector(p)-center).dot(n_out) for p in coords)
trim_support = None
epsilon = max(1e-7, .0001/scale)
results = []

def percentile(values, q):
    values = sorted(values)
    return values[min(len(values)-1, int(q*(len(values)-1)))]

def visible_target(bm):
    """Build target BVH from Blender's displayed loop-triangle tessellation."""
    mesh=bpy.data.meshes.new('_eye_visible_target')
    try:
        bm.to_mesh(mesh); mesh.calc_loop_triangles()
        marker=mesh.attributes.get('splitter_contact_surface')
        triangles=list(mesh.loop_triangles)
        tree=BVHTree.FromPolygons([tuple(v.co) for v in mesh.vertices],
                                  [tuple(t.vertices) for t in triangles], all_triangles=True)
        info=[{'polygon':t.polygon_index,
               'marked':bool(marker and marker.data[t.polygon_index].value),
               'normal':t.normal.copy().normalized()} for t in triangles]
        return tree,info
    finally:
        bpy.data.meshes.remove(mesh)

for gap in (0.0, 0.1):
    reference_result = slice_mesh_by_loop_extrude(
        obj, obj.name, indices, seed, depth_mm=depth, through_cut=False,
        scene=scene, part_clearance_mm=0.0, part_clearance_apply_to='PART')
    result = reference_result if gap == 0.0 else slice_mesh_by_loop_extrude(
        obj, obj.name, indices, seed, depth_mm=depth, through_cut=False,
        scene=scene, part_clearance_mm=gap, part_clearance_apply_to='PART')
    # For the zero-gap case both references are the same pair; the .1 case uses
    # the independently generated zero-gap contact patch as its reference.
    if gap == 0.0:
        ref_pair = reference_result
    else:
        ref_pair = reference_result
    ref = ref_pair[0]
    marker = ref.faces.layers.int.get('splitter_contact_surface')
    if marker is None:
        raise RuntimeError('Reference split has no marked contact surface')
    if trim_support is None:
        generated=set(f for f in ref.faces if f[marker])
        retained={v for f in ref.faces if f not in generated for v in f.verts}
        trim_support=support+n_out*min((v.co-support).dot(n_out) for v in retained)
    boundary = [e for e in ref.edges if sum(bool(f[marker]) for f in e.link_faces) == 1]

    def boundary_distance(p):
        values=[]
        for edge in boundary:
            a,b=(v.co for v in edge.verts); d=b-a
            t=max(0.,min(1.,(p-a).dot(d)/d.length_squared)) if d.length_squared else 0.
            values.append((p-(a+d*t)).length)
        return min(values, default=0.)

    # Build visible triangles in the same way as Blender's output tessellation.
    mesh=bpy.data.meshes.new('_eye_clearance_reference')
    try:
        ref.to_mesh(mesh); mesh.calc_loop_triangles()
        marker_attr=mesh.attributes.get('splitter_contact_surface')
        triangles=[]
        for tri in mesh.loop_triangles:
            if marker_attr and marker_attr.data[tri.polygon_index].value:
                points=tuple(mesh.vertices[i].co.copy() for i in tri.vertices)
                normal=tri.normal.copy().normalized()
                triangles.append((points,normal))
    finally:
        bpy.data.meshes.remove(mesh)

    targets=[visible_target(part) for part in result]
    trees=[target[0] for target in targets]
    groups={'lateral':[], 'floor':[], 'sloped':[]}
    nearest_groups={'lateral':[], 'floor':[], 'sloped':[]}
    zero_ray_samples=[]
    missed=0; excluded_shoulder=0; excluded_rim=0
    for tri,normal in triangles:
        axial=abs(normal.dot(axis))
        category='floor' if axial>=.9 else ('lateral' if axial<=.5 else 'sloped')
        for point in _samples([tri]):
            depth_below=(point-trim_support).dot(axis)
            if depth_below <= .01/scale:
                excluded_shoulder+=1; continue
            if boundary_distance(point)*scale <= .01:
                excluded_rim+=1; continue
            hit_a=trees[0].ray_cast(point+normal*epsilon,-normal)
            hit_b=trees[1].ray_cast(point-normal*epsilon,normal)
            near_a=trees[0].find_nearest(point)
            near_b=trees[1].find_nearest(point)
            nearest_groups[category].append((near_a[3]+near_b[3])*scale)
            if hit_a[0] is None or hit_b[0] is None:
                missed+=1; continue
            measured=max(0.,(hit_a[3]+hit_b[3]-2*epsilon)*scale)
            groups[category].append(measured)
            if category=='lateral' and measured <= .01:
                def hit_info(target, index):
                    item=target[1][index] if 0 <= index < len(target[1]) else None
                    return {'marked':item['marked'],'normal_dot_reference':item['normal'].dot(normal)} if item else None
                zero_ray_samples.append({'point_world':list(point),'depth_below_support_mm':depth_below*scale,
                    'nearest_sum_mm':(near_a[3]+near_b[3])*scale,
                    'nearest_A':hit_info(targets[0],near_a[2]),'nearest_B':hit_info(targets[1],near_b[2]),
                    'ray_A':hit_info(targets[0],hit_a[2]),'ray_B':hit_info(targets[1],hit_b[2])})

    part_metrics=[]
    for part in result:
        report=validate_bmesh_mesh_geometry(part,scale)
        part_metrics.append({'valid':report['is_valid'],'manifold':report['is_manifold'],
                             'components':report.get('components',None),
                             'volume_mm3':abs(part.calc_volume())*scale**3})
    row={'gap_mm':gap,'axis_world':list(axis),'trim_support_world':list(trim_support),
         'parts':part_metrics,'reference_triangles':len(triangles),
         'excluded_shoulder_samples':excluded_shoulder,'excluded_rim_samples':excluded_rim,
         'ray_misses':missed,'explosion_transforms_applied':False,'sample_method':'visible triangle centroids + three interior barycentric points',
         'zero_lateral_ray_samples':zero_ray_samples,'groups':{}}
    for name,values in groups.items():
        if values:
            row['groups'][name]={'samples':len(values),'min_mm':min(values),'p10_mm':percentile(values,.1),
                                 'median_mm':percentile(values,.5),'p90_mm':percentile(values,.9),
                                 'max_mm':max(values)}
        else:
            row['groups'][name]={'samples':0}
    row['nearest_surface_gap_sum']={}
    for name,values in nearest_groups.items():
        if values:
            row['nearest_surface_gap_sum'][name]={'samples':len(values),'min_mm':min(values),
                'p10_mm':percentile(values,.1),'median_mm':percentile(values,.5),
                'p90_mm':percentile(values,.9),'max_mm':max(values)}
        else:
            row['nearest_surface_gap_sum'][name]={'samples':0}
    if zero_ray_samples:
        from collections import Counter
        row['zero_lateral_hit_summary']={}
        for relation in ('nearest_A','nearest_B','ray_A','ray_B'):
            row['zero_lateral_hit_summary'][relation]=dict(Counter(
                'no_hit' if item[relation] is None else
                ('marked' if item[relation]['marked'] else 'unmarked')
                for item in zero_ray_samples))
    results.append(row)
    print('EYE_WALL_FLOOR=' + json.dumps(row,ensure_ascii=False),flush=True)
    if gap > 0:
        for name in ('lateral','floor'):
            values=groups[name]
            if not values:
                raise AssertionError(f'No {name} samples below shoulder')
            if abs(percentile(values,.5)-gap) > max(.02,.05*gap):
                raise AssertionError(f'{name} median {percentile(values,.5):.4f} mm != requested {gap} mm')
    if result is not reference_result:
        for part in result: part.free()
    for part in reference_result: part.free()

file_hash_after=hashlib.sha256(BLEND.read_bytes()).hexdigest()
payload={'blend':str(BLEND),'source_sha256_before':file_hash_before,'source_sha256_after':file_hash_after,
         'source_signature_unchanged':mesh_signature(obj.data)==signature_before,'seed_face':seed,
         'loop_vertices':len(indices),'depth_mm':depth,'measurements':results}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
assert file_hash_before==file_hash_after
assert file_hash_before.lower()=='66f7213e14b5867b7f7bb453ee3d88b1fe7af6d43b6de99f6dda12c061d847de'
assert payload['source_signature_unchanged']
for row in results:
    if row['gap_mm'] > 0:
        tolerance=max(.005,.05*row['gap_mm'])
        for surface in ('lateral','floor'):
            metrics=row['groups'].get(surface,{})
            if (metrics.get('samples',0)==0 or metrics.get('min_mm',0) < row['gap_mm']-tolerance
                    or metrics.get('p10_mm',0) < row['gap_mm']-tolerance):
                raise AssertionError(f"{surface} min/p10={metrics.get('min_mm')}/{metrics.get('p10_mm')} mm fails requested {row['gap_mm']} mm; details in {OUT}")
print('EYE_WALL_FLOOR_OK='+str(OUT),flush=True)
