"""Local contact offsets that retain the supporting planes of exterior faces."""
import math
import bmesh
from mathutils import Vector
from .localized_errors import LocalizedGeometryError


def weld_boolean_roundoff(bm, scale_to_mm):
    """Collapse connected roundoff endpoints; never globally merge nearby details.

    The bound is 0.0001 mm (100 times below the 0.01 mm surface tolerance).
    Only existing near-zero edges participate, so nearby unrelated walls cannot weld.
    """
    tolerance = 0.0001 / scale_to_mm
    for _ in range(3):
        pairs = [(e.verts[0], e.verts[1]) for e in bm.edges if e.calc_length() <= tolerance]
        for face in bm.faces:
            corners = list(face.verts)
            pairs.extend((a, b) for i, a in enumerate(corners) for b in corners[i + 1:]
                         if (a.co - b.co).length <= tolerance)
        targetmap = {}
        for a, b in pairs:
            while a in targetmap:
                a = targetmap[a]
            while b in targetmap:
                b = targetmap[b]
            if a is not b and (a.co - b.co).length <= tolerance:
                targetmap[b] = a
        if not targetmap:
            break
        for vertex in list(targetmap):
            target = targetmap[vertex]
            while target in targetmap:
                target = targetmap[target]
            targetmap[vertex] = target
        bmesh.ops.weld_verts(bm, targetmap=targetmap)
        bm.normal_update()
    for _ in range(3):
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=tolerance)
    bm.normal_update()


def _constrained_delta(constraints, tolerance):
    # Modified Gram-Schmidt solves n.dot(delta)=distance while retaining all
    # preceding supporting planes, including redundant normals at triangulated faces.
    basis = []
    delta = Vector()
    for normal, distance in constraints:
        residual = normal.copy()
        for q in basis:
            residual -= q * residual.dot(q)
        length = residual.length
        error = distance - normal.dot(delta)
        if length > 1e-3:
            q = residual / length
            delta += q * (error / normal.dot(q))
            basis.append(q)
        elif abs(error) > tolerance:
            raise LocalizedGeometryError('geometry.clearance_excessive')
    if any(abs(n.dot(delta) - d) > tolerance for n, d in constraints):
        raise LocalizedGeometryError('geometry.clearance_excessive')
    return delta


def cap_crossing_pairs(bm, contact_faces, tolerance):
    """Find contact-cap triangles that cross retained source surfaces off their boundary."""
    from mathutils.bvhtree import BVHTree
    marker=bm.faces.layers.int.get('splitter_contact_surface')
    if marker is None or not contact_faces:
        return []
    cap=bm.copy();source=bm.copy()
    try:
        cap_marker=cap.faces.layers.int.get('splitter_contact_surface')
        source_marker=source.faces.layers.int.get('splitter_contact_surface')
        cap.faces.ensure_lookup_table();source.faces.ensure_lookup_table()
        cap.faces.index_update();source.faces.index_update()
        cap_faces=[face for face in cap.faces if cap_marker and face[cap_marker]]
        if not cap_faces:
            return []
        bmesh.ops.delete(source,geom=[face for face in source.faces if source_marker and face[source_marker]],context='FACES')
        source.faces.ensure_lookup_table();source.faces.index_update()
        if not source.faces:
            return []
        cap_tree=BVHTree.FromBMesh(cap,epsilon=tolerance)
        source_tree=BVHTree.FromBMesh(source,epsilon=tolerance)
        cap_by_index={face.index:face for face in cap_faces}
        source_by_index={face.index:face for face in source.faces}
        pairs=[]
        for cap_index,source_index in cap_tree.overlap(source_tree):
            cap_face=cap_by_index.get(cap_index);source_face=source_by_index.get(source_index)
            if cap_face is None or source_face is None:
                continue
            # The designed shared loop boundary is allowed. Any other triangle
            # intersection means the closure cuts through retained geometry.
            shared=any((a.co-b.co).length <= tolerance for a in cap_face.verts for b in source_face.verts)
            if not shared:
                pairs.append((cap_index,source_index))
        return pairs
    finally:
        cap.free();source.free()


def offset_contact_surface(bm, contact_faces, origin, axial_normal,
                           lateral, bottom, planar=False, inward=None, unit_scale=None):
    """Trim planar interfaces; intersect incident planes for spatial interfaces.

    Exterior vertices are allowed to slide only in their original incident planes.
    Every generated face is offset in its own normal, avoiding mean-normal ramps.
    """
    bm.faces.index_update()
    indices = [f.index for f in contact_faces if f.is_valid]
    contact_layer = bm.faces.layers.int.get('splitter_contact_surface') or bm.faces.layers.int.new('splitter_contact_surface')
    bm.faces.ensure_lookup_table()
    contacts = set(bm.faces[i] for i in indices)
    for face in contacts:
        face[contact_layer] = 1
    if not contacts or max(lateral, bottom) <= 1e-12:
        return
    bm.normal_update()
    from .diagnostic import get_scene_scale_to_mm
    import bpy
    scale_to_mm = unit_scale if unit_scale is not None else get_scene_scale_to_mm(bpy.context.scene)
    if planar:
        # Clipping also handles dense source topology: it introduces intersections
        # instead of dragging original exterior vertices past a neighboring edge.
        if bottom <= 1e-12:
            return
        material = next(iter(contacts)).material_index
        bmesh.ops.bisect_plane(
            bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            dist=1e-8, plane_co=origin + inward * bottom,
            plane_no=inward, clear_inner=True, clear_outer=False,
        )
        boundary = [e for e in bm.edges if e.is_boundary]
        if boundary:
            result = bmesh.ops.holes_fill(bm, edges=boundary, sides=len(boundary))
            for f in result.get('faces', []):
                f.material_index = material
                f[contact_layer] = 1
        if any(not e.is_manifold for e in bm.edges):
            raise LocalizedGeometryError('geometry.clearance_excessive')
    else:
        displacements = {}
        try:
            for vertex in set(v for f in contacts for v in f.verts):
                constraints = [(f.normal.copy(), 0.0) for f in vertex.link_faces if f not in contacts]
                for face in vertex.link_faces:
                    if face in contacts:
                        axial = abs(face.normal.dot(axial_normal))
                        distance = math.sqrt((bottom*axial)**2 + lateral*lateral*max(0.0,1.0-axial*axial))
                        constraints.append((face.normal.copy(), -distance))
                delta = _constrained_delta(constraints, max(0.001 / scale_to_mm,max(lateral,bottom)*1e-4))
                if delta.length > 32 * max(lateral, bottom):
                    raise LocalizedGeometryError('geometry.clearance_excessive')
                displacements[vertex] = delta
            for edge in bm.edges:
                a,b = edge.verts
                old = b.co-a.co
                new = old+displacements.get(b,Vector())-displacements.get(a,Vector())
                if old.length_squared>1e-16 and new.dot(old)<=0:
                    raise LocalizedGeometryError('geometry.clearance_excessive')
        except LocalizedGeometryError:
            # A single shared-vertex offset cannot satisfy these exact support constraints.
            raise
        else:
            for vertex,delta in displacements.items():
                vertex.co += delta
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

def final_contact_patch(bm, direction, unit_scale):
    """Return the largest planar contact patch from the final Boolean topology."""
    from .geometry_material import _order_boundary_loops
    from mathutils.geometry import tessellate_polygon
    layer = bm.faces.layers.int.get('splitter_contact_surface')
    if layer is None:
        return None
    faces = [f for f in bm.faces if f[layer] and f.normal.dot(direction) > 0.99]
    if not faces:
        return None
    anchor = max(faces, key=lambda f:f.calc_area())
    origin = anchor.calc_center_median()
    normal = anchor.normal.copy()
    tolerance = 0.001 / unit_scale
    selected = set(f for f in faces if all(abs((v.co-origin).dot(normal)) <= tolerance for v in f.verts))
    # Retain the largest connected coplanar patch; preserve all its hole loops.
    components = []
    remaining = set(selected)
    while remaining:
        seed = remaining.pop()
        component = {seed}
        queue = [seed]
        while queue:
            face = queue.pop()
            for edge in face.edges:
                for other in edge.link_faces:
                    if other in remaining:
                        remaining.remove(other); component.add(other); queue.append(other)
        components.append(component)
    selected = max(components, key=lambda group:sum(f.calc_area() for f in group))
    boundary = [e for e in bm.edges if sum(f in selected for f in e.link_faces)==1]
    loops = _order_boundary_loops(boundary)
    if not loops:
        return None
    loop = max(loops, key=lambda points:sum((points[(i+1)%len(points)].co-p.co).length for i,p in enumerate(points)))
    triangles = []
    for face in selected:
        points = [v.co.copy() for v in face.verts]
        for tri in tessellate_polygon([points]):
            triangles.append(tuple(points[i].copy() if isinstance(i,int) else i.copy() for i in tri))
    return dict(origin=origin, normal=normal, boundary=[v.co.copy() for v in loop], loops=[[v.co.copy() for v in ring] for ring in loops], triangles=triangles)

def triangulated_source_mesh(mesh):
    """Use Blender's visible tessellation explicitly before Boolean intersections.

    Nonplanar n-gons otherwise acquire different diagonals independently in
    INTERSECT/DIFFERENCE, so their outputs need not conserve the same shell.
    """
    import bpy
    mesh.calc_loop_triangles()
    result = bpy.data.meshes.new(mesh.name + '_surface_triangles')
    triangles = list(mesh.loop_triangles)
    result.from_pydata([v.co.copy() for v in mesh.vertices], [], [tuple(t.vertices) for t in triangles])
    for mat in mesh.materials:
        result.materials.append(mat)
    for polygon, triangle in zip(result.polygons, triangles):
        original = mesh.polygons[triangle.polygon_index]
        polygon.material_index = original.material_index
        polygon.use_smooth = original.use_smooth
    result.update()
    return result

def convex_contact_planes(bm, unit_scale):
    """Return deduplicated supporting planes only for a genuinely convex shell."""
    # This reconstruction is for small polyhedral corners. Dense curved shells
    # use the local constraint path rather than cubic plane enumeration.
    if len(bm.faces) > 256:
        return None
    bm.normal_update()
    marker=bm.faces.layers.int.get('splitter_contact_surface')
    if marker is None:return None
    tolerance=0.001/unit_scale
    planes=[]
    for face in bm.faces:
        normal=face.normal.copy();origin=face.verts[0].co.copy()
        if any((v.co-origin).dot(normal)>tolerance for v in bm.verts):return None
        contact=bool(face[marker]);distance=normal.dot(origin)
        if not any(contact==plane['contact'] and normal.dot(plane['normal'])>1-1e-6 and abs(distance-plane['distance'])<tolerance for plane in planes):
            planes.append(dict(normal=normal,distance=distance,contact=contact,material=face.material_index,source=face))
            if len(planes) > 24:
                return None
    return planes


def convex_offset_from_planes(bm, planes, axis, lateral, bottom, sign, unit_scale, exterior_extension=0.0):
    """Rebuild a convex region by exact intersections of its supporting planes."""
    from itertools import combinations
    from mathutils import Matrix
    shifted=[]
    for plane in planes:
        item=dict(plane);normal=item['normal'];axial=abs(normal.dot(axis))
        offset=(math.sqrt((bottom*axial)**2+lateral*lateral*max(0.0,1-axial*axial))) if item['contact'] else exterior_extension
        item['distance']+=sign*offset if item['contact'] else exterior_extension
        shifted.append(item)
    tolerance=0.0001/unit_scale
    points=[]
    for a,b,c in combinations(shifted,3):
        matrix=Matrix((a['normal'],b['normal'],c['normal']))
        if abs(matrix.determinant())<1e-7:continue
        point=matrix.inverted()@Vector((a['distance'],b['distance'],c['distance']))
        if all(item['normal'].dot(point)<=item['distance']+tolerance for item in shifted):
            if not any((point-other).length<tolerance for other in points):points.append(point)
    if len(points)<4:raise LocalizedGeometryError('geometry.clearance_excessive')
    result=bmesh.new();vertices=[result.verts.new(p) for p in points]
    contact_layer=result.faces.layers.int.new('splitter_contact_surface')
    # Retain per-face provenance used by material and exterior verification.
    source_layers={name:result.faces.layers.int.new(name) for name in bm.faces.layers.int.keys() if name!='splitter_contact_surface'}
    from .geometry_material import _get_orthonormal_basis
    for item in shifted:
        indices=[i for i,p in enumerate(points) if abs(item['normal'].dot(p)-item['distance'])<tolerance*8]
        if len(indices)<3:continue
        center=sum((points[i] for i in indices),Vector())/len(indices)
        u,v=_get_orthonormal_basis(item['normal'])
        indices.sort(key=lambda i:math.atan2((points[i]-center).dot(v),(points[i]-center).dot(u)))
        face=result.faces.new([vertices[i] for i in indices]);face.material_index=item['material'];face[contact_layer]=int(item['contact'])
        for name,layer in source_layers.items():face[layer]=item['source'][bm.faces.layers.int[name]]
    from .geometry_solid import ensure_solid_outward_normals
    ensure_solid_outward_normals(result)
    if any(not edge.is_manifold for edge in result.edges):
        result.free();raise LocalizedGeometryError('geometry.clearance_excessive')
    return result


def subtract_closed_region(source_bm, cutter_bm, unit_scale):
    """Subtract a closed region while retaining source exterior coordinates."""
    import bpy
    meshes=[];objects=[];materials=[];evaluated=None
    try:
        for name,bm in (('_contact_source',source_bm),('_contact_cutter',cutter_bm)):
            mesh=bpy.data.meshes.new(name);meshes.append(mesh);bm.to_mesh(mesh)
            obj=bpy.data.objects.new(name,mesh);objects.append(obj);bpy.context.scene.collection.objects.link(obj)
        count=max((f.material_index for f in source_bm.faces),default=0)+1
        for _ in range(count):
            mat=bpy.data.materials.new('_contact_material');materials.append(mat)
            for mesh in meshes:mesh.materials.append(mat)
        modifier=objects[0].modifiers.new('Clearance contact', 'BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=objects[1]
        bpy.context.view_layer.update();evaluated=objects[0].evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        result=bmesh.new();result.from_mesh(mesh);weld_boolean_roundoff(result,unit_scale)
        if not result.faces or any(not edge.is_manifold for edge in result.edges):
            result.free();raise LocalizedGeometryError('geometry.clearance_excessive')
        return result
    finally:
        if evaluated is not None:evaluated.to_mesh_clear()
        for obj in objects:bpy.data.objects.remove(obj,do_unlink=True)
        for mesh in meshes:bpy.data.meshes.remove(mesh)
        for mat in materials:bpy.data.materials.remove(mat)
