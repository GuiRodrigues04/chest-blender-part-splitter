"""Complementary planar pin seats with a common straight assembly direction.

Only newly generated internal partition faces may change. Exterior boundary
vertices remain fixed; a narrow transition joins them to the planar seat.
"""
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
from .geometry_region import CONTACT, PATCH

_ASSEMBLY_CACHE = {}


def verify_straight_assembly(mesh_a,mesh_b,axis,scale):
    """Check sampled withdrawal positions in addition to the contact-normal test.

    This catches distant-body interference; it is not a continuous-motion proof.
    Geometry-based caching avoids repeating Booleans when only pin sizes change.
    """
    from .geometry_region import mesh_signature
    from .geometry_clearance import triangulated_source_mesh
    key=(mesh_signature(mesh_a),mesh_signature(mesh_b),tuple(axis),scale)
    if key in _ASSEMBLY_CACHE:return
    projections_a=[v.co.dot(axis) for v in mesh_a.vertices]
    projections_b=[v.co.dot(axis) for v in mesh_b.vertices]
    travel=max(projections_a)-min(projections_b)+.01/scale
    if travel<=0:return
    objects=[];meshes=[]
    try:
        for name,mesh in (('_assembly_piece',mesh_a),('_assembly_body',mesh_b)):
            data=triangulated_source_mesh(mesh);meshes.append(data)
            obj=bpy.data.objects.new(name,data);objects.append(obj);bpy.context.scene.collection.objects.link(obj)
        modifier=objects[0].modifiers.new('Assembly interference','BOOLEAN')
        modifier.operation='INTERSECT';modifier.object=objects[1]
        solvers=bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items
        modifier.solver='MANIFOLD' if 'MANIFOLD' in {item.identifier for item in solvers} else 'EXACT'
        initial=bmesh.new()
        try:initial.from_mesh(mesh_a);tolerance=max(.01,abs(initial.calc_volume())*scale**3*1e-8)
        finally:initial.free()
        for fraction in (.0001,.01,.1,.25,.5,1):
            objects[0].location=-axis*(travel*fraction)
            bpy.context.view_layer.update()
            evaluated=objects[0].evaluated_get(bpy.context.evaluated_depsgraph_get())
            bm=bmesh.new()
            try:
                bm.from_mesh(evaluated.to_mesh())
                if abs(bm.calc_volume())*scale**3>tolerance:
                    raise ValueError('A peça colide com o corpo durante a retirada nesta direção. Escolha outro contato ou faça outra divisão.')
            finally:bm.free();evaluated.to_mesh_clear()
        if len(_ASSEMBLY_CACHE)>=16:_ASSEMBLY_CACHE.clear()
        _ASSEMBLY_CACHE[key]=True
    finally:
        for obj in reversed(objects):bpy.data.objects.remove(obj,do_unlink=True)
        for mesh in meshes:
            if mesh.users==0:bpy.data.meshes.remove(mesh)


def fit_plane(faces):
    import numpy as np
    ordered = sorted(faces, key=lambda f:f.index)
    samples = np.array([tuple(v.co) for f in ordered for v in f.verts], dtype=float)
    weights = np.array([f.calc_area()/len(f.verts) for f in ordered for v in f.verts])
    center = np.average(samples, axis=0, weights=weights)
    offsets = samples-center
    _, vectors = np.linalg.eigh((offsets*weights[:,None]).T@offsets)
    normal = Vector(vectors[:,0]).normalized()
    mean = Vector(tuple(math.fsum(f.normal[i]*f.calc_area() for f in ordered) for i in range(3)))
    if normal.dot(mean)<0:normal=-normal
    deviation = max(abs((v.co-Vector(center)).dot(normal)) for f in ordered for v in f.verts)
    span = float(np.linalg.norm(samples.max(axis=0)-samples.min(axis=0)))
    return Vector(center), normal, deviation, span


def assembly_axis(preferred, contacts):
    """Project onto the intersection of inward-facing halfspaces on the unit sphere.

    Keep close to the intended seat normal; an infeasible or sideways solution
    is rejected rather than offering nonparallel pins or a locking joint.
    """
    normals = [f.normal.copy() for f in sorted(contacts,key=lambda f:f.index)]
    axis = preferred.copy()
    for _ in range(160):
        worst = min(normals, key=lambda n:n.dot(axis))
        error = worst.dot(axis)
        if error>=-1e-6:
            return axis if axis.dot(preferred)>=math.cos(math.radians(25)) else None
        axis -= worst*(error-1e-6)
        if axis.length<1e-8:return None
        axis.normalize()
    return None


def candidate_groups(bm, scale):
    """Connected surface regions, evaluated against one fitted global plane."""
    bm.normal_update();bm.faces.index_update()
    marker = bm.faces.layers.int.get(CONTACT)
    contacts = {f for f in bm.faces if marker and f[marker]}
    remaining = set(contacts)
    groups = []
    cosine = math.cos(math.radians(18))
    while remaining:
        seed = max(remaining,key=lambda f:(f.calc_area(),-f.index))
        group = {seed};remaining.remove(seed)
        stack = [seed]
        while stack:
            face = stack.pop()
            adjacent = sorted({g for e in face.edges for g in e.link_faces if g in remaining},key=lambda f:f.index)
            for other in adjacent:
                if other.normal.dot(seed.normal)<cosine:continue
                origin,normal,deviation,span = fit_plane(group|{other})
                if deviation>max(.05/scale,span*.025):continue
                if any(f.normal.dot(normal)<cosine for f in group|{other}):continue
                group.add(other);remaining.remove(other);stack.append(other)
        origin,normal,deviation,span = fit_plane(group)
        groups.append(dict(faces=group,origin=origin,normal=normal,deviation=deviation,
                           area=sum(f.calc_area() for f in group),axis=assembly_axis(normal,contacts)))
    groups.sort(key=lambda g:(-g['area'],min(f.index for f in g['faces'])))
    return groups


def _triangle_key(face):
    return tuple(sorted(tuple(v.co) for v in face.verts))


def _seat_geometry(group, axis, scale):
    from .geometry_material import _order_boundary_loops, _get_orthonormal_basis, offset_polygon_2d
    from .geometry_regions import area, validate_rings
    faces = group['faces']
    edges = list({e for f in faces for e in f.edges if sum(g in faces for g in e.link_faces)==1})
    edges.sort(key=lambda e:e.index)
    loops = _order_boundary_loops(edges)
    if not loops:raise ValueError('A área de encaixe não possui contorno contínuo.')
    origin = group['origin'];u,v = _get_orthonormal_basis(axis)
    data = [([Vector(((p.co-origin).dot(u)*scale,(p.co-origin).dot(v)*scale)) for p in loop],loop) for loop in loops]
    data.sort(key=lambda item:-abs(area(item[0])))
    rings = validate_rings([item[0] for item in data])
    data = [next(item for item in data if item[0] is ring) for ring in rings]
    # Fixed automatic transition width: 3% of the smaller footprint dimension.
    footprint = rings[0]
    span = min(max(p[i] for p in footprint)-min(p[i] for p in footprint) for i in (0,1))
    inset = span*.03
    if inset<=1e-5:raise ValueError('A área de encaixe é estreita demais.')
    inner=[]
    for i,ring in enumerate(rings):
        shifted,ok = offset_polygon_2d(ring,inset if i==0 else -inset)
        if not ok:raise ValueError('Não foi possível criar uma transição interna para esta área.')
        inner.append(shifted)
    validate_rings(inner)
    # Orient both copies identically; each transition then has a one-to-one border.
    old=[];flat=[]
    for i,((ring,loop),new) in enumerate(zip(data,inner)):
        indices = list(range(len(ring)))
        if (area(new)>0)!=(i==0):indices.reverse()
        old.append([loop[j].co.copy() for j in indices])
        flat.append([origin+(u*new[j].x+v*new[j].y)/scale for j in indices])
    all_new = [p for loop in flat for p in loop]
    polygon_2d=[[Vector(((p-origin).dot(u)*scale,(p-origin).dot(v)*scale,0)) for p in loop] for loop in flat]
    tris=tessellate_polygon(polygon_2d)
    expected=abs(area(inner[0]))-sum(abs(area(r)) for r in inner[1:])
    coords=[p for ring in polygon_2d for p in ring]
    measured=sum(abs(area([coords[i] for i in t])) for t in tris)
    if expected<=1e-6 or abs(measured-expected)>max(1e-5,expected*1e-5):
        raise ValueError('A área plana não preserva as aberturas da seleção.')
    triangles=[tuple(all_new[i] for i in tri) for tri in tris]
    ramps=[]
    for outer,inside in zip(old,flat):
        for i in range(len(outer)):
            j=(i+1)%len(outer)
            ramps.extend(((outer[i],outer[j],inside[j]),(outer[i],inside[j],inside[i])))
    def oriented(triangle):
        a,b,c=triangle
        dot=(b-a).cross(c-a).dot(axis)
        if abs(dot)*scale*scale<1e-7:
            raise ValueError('A transição da área plana contém uma face degenerada.')
        return triangle if dot>0 else (c,b,a)
    return origin,flat,[oriented(t) for t in triangles],[oriented(t) for t in ramps]


def prepare_planar_seat(mesh_a,mesh_b,chosen,scale,contains):
    """Replace one internal patch in BOTH pieces using exactly the same triangles."""
    from .geometry_region import _validate_caps
    from .geometry_contract import build_cut_interface
    from .geometry_solid import ensure_solid_outward_normals
    from .diagnostic import stable_signed_volume_mm3
    a=bmesh.new();b=bmesh.new()
    try:
        a.from_mesh(mesh_a);b.from_mesh(mesh_b)
        groups=candidate_groups(a,scale)
        if not 0<=chosen<len(groups):raise ValueError('Escolha uma área de encaixe da prévia atual.')
        group=groups[chosen];axis=group['axis']
        if axis is None:raise ValueError('Esta área não permite montagem por inserção reta. Escolha outro contato ou divida a peça novamente.')
        origin=group['origin']
        # If the full region is already genuinely planar, retain it without a rim.
        exact=max(abs((v.co-origin).dot(axis)) for f in group['faces'] for v in f.verts)*scale<=.001
        if exact:
            from .geometry_material import _order_boundary_loops
            faces=group['faces'];edges=list({e for f in faces for e in f.edges if sum(g in faces for g in e.link_faces)==1})
            edges.sort(key=lambda e:e.index)
            rings=[[v.co.copy() for v in loop] for loop in _order_boundary_loops(edges)]
            triangles=[]
            for face in sorted(faces,key=lambda f:f.index):
                points=[v.co.copy() for v in face.verts]
                for triangle in tessellate_polygon([points]):
                    triangles.append(tuple(points[i].copy() if isinstance(i,int) else i.copy() for i in triangle))
        else:
            origin,rings,triangles,ramps=_seat_geometry(group,axis,scale)
            previous=abs(stable_signed_volume_mm3(a,scale))+abs(stable_signed_volume_mm3(b,scale))
            keys={_triangle_key(f) for f in group['faces']}
            layer_b=b.faces.layers.int.get(CONTACT)
            other=[f for f in b.faces if layer_b and f[layer_b] and _triangle_key(f) in keys]
            if len(other)!=len(group['faces']):raise ValueError('As duas peças não possuem superfícies de contato correspondentes.')
            for bm,old,reverse in ((a,list(group['faces']),False),(b,other,True)):
                # Boundary vertices survive because retained adjacent faces own them.
                bmesh.ops.delete(bm,geom=old,context='FACES')
                vertices={tuple(v.co):v for v in bm.verts}
                marker=bm.faces.layers.int.get(CONTACT)
                label=bm.faces.layers.int.get(PATCH) or bm.faces.layers.int.new(PATCH)
                for is_seat,items in ((True,triangles),(False,ramps)):
                    for triangle in items:
                        points=[]
                        for point in triangle:
                            key=tuple(point)
                            if key not in vertices:vertices[key]=bm.verts.new(point)
                            points.append(vertices[key])
                        face=bm.faces.new(tuple(reversed(points)) if reverse else points)
                        face[marker]=1;face[label]=chosen+1 if is_seat else 0
                ensure_solid_outward_normals(bm)
                caps=[f for f in bm.faces if f[marker]]
                _validate_caps(bm,caps,contains,scale)
            after=abs(stable_signed_volume_mm3(a,scale))+abs(stable_signed_volume_mm3(b,scale))
            if abs(after-previous)>max(.001,previous*1e-8):raise ValueError('A preparação da área plana não conservou o volume.')
        # A common normal for all pin axes; transitions must not introduce undercuts.
        marker=a.faces.layers.int.get(CONTACT)
        if any(f.normal.dot(axis)<-1e-5 for f in a.faces if marker and f[marker]):
            raise ValueError('O fechamento possui uma trava na direção de inserção dos pinos.')
        interface=build_cut_interface(origin,axis,[],interface_triangles=triangles,
            boundary_loops_world=rings,unit_scale=scale,source_mode='REGION')
        if not interface.is_planar or interface.deviation_mm>.001:
            raise ValueError('Não foi possível produzir uma área de encaixe realmente plana.')
        a.to_mesh(mesh_a);b.to_mesh(mesh_b)
        verify_straight_assembly(mesh_a,mesh_b,axis,scale)
        return interface
    finally:
        a.free();b.free()
