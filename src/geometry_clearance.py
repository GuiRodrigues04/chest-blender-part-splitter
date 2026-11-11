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
            raise LocalizedGeometryError('geometry.clearance_unresolved')
    if any(abs(n.dot(delta) - d) > tolerance for n, d in constraints):
        raise LocalizedGeometryError('geometry.clearance_unresolved')
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

def trim_depth_contact(bm, contacts, axis, lateral, bottom, unit_scale, support):
    """Subtract the complete inward contact band, retaining the exterior relief.

    Offset contact planes at both ends of each wall. A boundary shared with the
    relief is closed with a rim, so the result has a shoulder rather than a ramp.
    Lateral and bottom offsets remain independent, including zero on either axis.
    """
    bm.normal_update()
    contacts = set(contacts)
    axis = axis.normalized()
    tolerance = 0.00001 / unit_scale
    active_contacts = set()
    for face in contacts:
        axial = abs(face.normal.dot(axis))
        distance = math.sqrt((bottom * axial)**2 + lateral*lateral * max(0., 1.-axial*axial))
        if distance > tolerance:
            active_contacts.add(face)
    if not active_contacts:
        if lateral <= tolerance and bottom <= tolerance:
            return bm.copy()
        raise LocalizedGeometryError('geometry.clearance_unresolved')
    shifts = {}
    for vertex in {v for f in contacts for v in f.verts}:
        constraints = []
        for face in vertex.link_faces:
            if face in contacts:
                axial = abs(face.normal.dot(axis))
                distance = math.sqrt((bottom * axial)**2 + lateral*lateral * max(0., 1.-axial*axial))
                constraints.append((face.normal.copy(), -distance))
        shifts[vertex] = _constrained_delta(constraints, tolerance)
    for edge in bm.edges:
        # Only edges on the contact surface are represented in the offset
        # cutter band. A retained exterior edge can connect a shifted contact
        # vertex to an unshifted relief vertex without producing an inverted
        # edge in the band, so exclude it from this virtual-offset guard.
        if not any(face in contacts for face in edge.link_faces):
            continue
        a, b = edge.verts
        old = b.co - a.co
        new = old + shifts.get(b, Vector()) - shifts.get(a, Vector())
        if old.length > tolerance and new.dot(old) <= 0:
            raise LocalizedGeometryError('geometry.clearance_excessive')
    band = bmesh.new()
    try:
        marker = band.faces.layers.int.new('splitter_contact_surface')
        active_vertices = {v for face in active_contacts for v in face.verts}
        # Avoid a coplanar Boolean between the band shell and the captured
        # source interface. Move only the cutter's outer shell a tiny amount
        # outward, satisfying every incident contact plane independently.
        # The inner shell remains the exact requested clearance surface.
        outer_epsilon = max(0.001 / unit_scale, 100.0 * tolerance)
        outer_shifts = {}
        for vertex in active_vertices:
            constraints = [(face.normal.copy(), outer_epsilon)
                           for face in vertex.link_faces if face in contacts]
            outer_shifts[vertex] = _constrained_delta(constraints, tolerance)
        outer = {v: band.verts.new(v.co + outer_shifts[v]) for v in active_vertices}
        inner = {v: band.verts.new(v.co + shifts[v]) if shifts[v].length > tolerance else outer[v]
                 for v in active_vertices}

        def face(vertices, material):
            corners = []
            for vertex in vertices:
                if vertex not in corners:
                    corners.append(vertex)
            if len(corners) < 3:
                return
            existing = band.faces.get(corners)
            if existing is None:
                created = band.faces.new(corners)
                created.material_index = material
                created[marker] = 1

        for source in active_contacts:
            face([outer[v] for v in source.verts], source.material_index)
            face([inner[v] for v in reversed(list(source.verts))], source.material_index)
            for loop in source.loops:
                if sum(f in active_contacts for f in loop.edge.link_faces) == 1:
                    a, b = loop.vert, loop.link_loop_next.vert
                    face([outer[b], outer[a], inner[a], inner[b]], source.material_index)
        # A nonplanar capture can climb far up the selected relief. Clearance
        # belongs only to the insertion below its supporting plane.
        bmesh.ops.bisect_plane(band, geom=band.verts[:] + band.edges[:] + band.faces[:],
                               dist=tolerance, plane_co=support, plane_no=-axis,
                               clear_outer=True, clear_inner=False)
        boundary = [e for e in band.edges if e.is_boundary]
        if boundary:
            # A clipped band can expose nested outer/inner contours. Filling
            # each contour separately creates overlapping disks that close a
            # real annular hole; the planar helper preserves the nested parity.
            from .geometry_plane import cap_open_cut_boundaries
            previous_faces = set(band.faces)
            cap_open_cut_boundaries(band, cut_edges=boundary, plane_origin=support,
                                    plane_normal=-axis, coplanar_tol_bu=tolerance)
            for cap in set(band.faces) - previous_faces:
                cap[marker] = 1
                cap.material_index = next(iter(contacts)).material_index
        bmesh.ops.dissolve_degenerate(band, edges=band.edges[:], dist=tolerance)
        remove_boolean_wires(band)
        from .geometry_solid import ensure_solid_outward_normals
        ensure_solid_outward_normals(band)
        if not band.faces or any(not e.is_manifold for e in band.edges):
            raise LocalizedGeometryError('geometry.clearance_unresolved')
        result = subtract_closed_region(bm, band, unit_scale)
        if abs(result.calc_volume()) >= abs(bm.calc_volume()):
            result.free()
            raise LocalizedGeometryError('geometry.clearance_unresolved')
        return result
    finally:
        band.free()


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
    tolerance = max(0.01 / unit_scale, 1e-5)
    selected = set(f for f in faces if all(abs((v.co-origin).dot(normal)) <= tolerance for v in f.verts))
    if not selected:
        return None
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
    if not components:
        return None
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
    """Use visible tessellation explicitly, retaining per-corner UV data.

    Nonplanar n-gons otherwise acquire different diagonals independently in
    INTERSECT/DIFFERENCE, so their outputs need not conserve the same shell.
    """
    import array
    import bpy
    mesh.calc_loop_triangles()
    triangles = list(mesh.loop_triangles)
    active_uv_name = mesh.uv_layers.active.name if mesh.uv_layers.active else None
    active_render_uv_name = next((layer.name for layer in mesh.uv_layers
                                  if layer.active_render), None)
    uv_payloads = []
    for source_layer in mesh.uv_layers:
        source_attribute = mesh.attributes.get(source_layer.name)
        if (source_attribute is not None
                and source_attribute.domain == 'CORNER'
                and source_attribute.data_type == 'FLOAT2'
                and len(source_attribute.data) == len(mesh.loops)):
            source_values = [tuple(value.vector) for value in source_attribute.data]
        else:
            source_values = [tuple(value.uv) for value in source_layer.data]
        if len(source_values) != len(mesh.loops):
            raise RuntimeError(f'UV layer {source_layer.name!r} has incomplete corner data.')
        values = array.array('f', (component
                                   for triangle in triangles
                                   for loop_index in triangle.loops
                                   for component in source_values[int(loop_index)]))
        uv_payloads.append((source_layer.name, values))

    # Validate all source UV data before allocating a mesh so incomplete legacy
    # buffers cannot leave an unused temporary data block behind.
    result = bpy.data.meshes.new(mesh.name + '_surface_triangles')
    try:
        result.from_pydata([v.co.copy() for v in mesh.vertices], [],
                           [tuple(t.vertices) for t in triangles])
        for mat in mesh.materials:
            result.materials.append(mat)
        for polygon, triangle in zip(result.polygons, triangles):
            original = mesh.polygons[triangle.polygon_index]
            polygon.material_index = original.material_index
            polygon.use_smooth = original.use_smooth

        # Triangle loop order corresponds to MeshLoopTriangle.loops exactly;
        # copying corners preserves seams even at shared source vertices.
        for name, values in uv_payloads:
            layer = result.uv_layers.new(name=name)
            layer.data.foreach_set('uv', values)
        if active_uv_name is not None and active_uv_name in result.uv_layers:
            result.uv_layers.active_index = next(i for i, layer in enumerate(result.uv_layers)
                                                 if layer.name == active_uv_name)
        if active_render_uv_name is not None and active_render_uv_name in result.uv_layers:
            result.uv_layers.active_render_index = next(i for i, layer in enumerate(result.uv_layers)
                                                        if layer.name == active_render_uv_name)

        # Face provenance must survive tessellation: future depth cuts use these
        # markers to distinguish earlier cavities from the outside wall.
        for attribute in mesh.attributes:
            if (attribute.domain == 'FACE' and attribute.data_type == 'INT'
                    and attribute.name.startswith('splitter_')):
                copied = result.attributes.new(attribute.name, 'INT', 'FACE')
                copied.data.foreach_set('value', [attribute.data[t.polygon_index].value
                                                   for t in triangles])
        result.update()
        return result
    except Exception:
        bpy.data.meshes.remove(result)
        raise

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


def remove_boolean_wires(bm):
    """Remove Boolean-only wire remnants, never edges belonging to faces.

    A loose edge has no surface area or solid volume. Blender's MANIFOLD
    solver can leave one behind at microscopic colour islands. Removing
    such wires preserves every surface face and its material assignment.
    Do not use this to repair open boundary edges (which have one face).
    """
    wires = [edge for edge in bm.edges if not edge.link_faces]
    if wires:
        bmesh.ops.delete(bm, geom=wires, context='EDGES')
    isolated = [vert for vert in bm.verts if not vert.link_edges and not vert.link_faces]
    if isolated:
        bmesh.ops.delete(bm, geom=isolated, context='VERTS')
    return bool(wires or isolated)
