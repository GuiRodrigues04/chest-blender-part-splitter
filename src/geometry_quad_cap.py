"""Conservative disk grid, with fixed boundary and smooth interior interpolation."""
import bmesh
from mathutils import Vector


def grid_coordinates(boundary, normal):
    n = len(boundary)
    if n < 4 or n > 128 or n % 2:
        return None
    # Opposite sides have the same number of edges. Try the cyclic alignments
    # and retain the most regular valid patch, rather than an arbitrary fan.
    width = n // 4
    height = n // 2 - width
    best = None
    for offset in range(n):
        p = boundary[offset:] + boundary[:offset]
        bottom = p[:width + 1]
        right = p[width:width + height + 1]
        top = list(reversed(p[width + height:2 * width + height + 1]))
        left = [p[0]] + list(reversed(p[2 * width + height + 1:])) + [p[2 * width + height]]
        points = []
        refs = []
        for j in range(height + 1):
            v = j / height
            for i in range(width + 1):
                u = i / width
                point = ((1-v)*bottom[i] + v*top[i] + (1-u)*left[j] + u*right[j]
                         - ((1-u)*(1-v)*bottom[0] + u*(1-v)*bottom[-1]
                            + (1-u)*v*top[0] + u*v*top[-1]))
                points.append(point)
                ref = i if j == 0 else (width+j if i == width else
                      (2*width+height-i if j == height else
                       ((n-j) % n if i == 0 else None)))
                refs.append((ref + offset) % n if ref is not None else None)
        faces = []
        score = 0.
        valid = True
        for j in range(height):
            for i in range(width):
                a = j*(width+1)+i
                f = (a, a+1, a+width+2, a+width+1)
                q = [points[k] for k in f]
                edges = [(q[(k+1)%4]-q[k]).length for k in range(4)]
                cross = [(q[(k+1)%4]-q[k]).cross(q[(k+2)%4]-q[(k+1)%4]).dot(normal) for k in range(4)]
                if min(edges) < 1e-10 or min(cross) <= 1e-14 or max(edges)/min(edges) > 12:
                    valid = False
                    break
                score += max(edges)/min(edges)
                faces.append(f)
            if not valid:
                break
        if valid and (best is None or score < best[0]):
            best = score, points, refs, faces
    return best[1:] if best else None


def try_quad_pair(bm_a, bm_b, loop_a, loop_b, coords, normal, unit_scale):
    """Build and validate on copies, leaving both inputs untouched on failure."""
    from .geometry_clearance import cap_crossing_pairs
    grid = grid_coordinates(coords, normal)
    if grid is None:
        return None

    points, refs, faces = grid
    # Avoid strongly twisted cells. Mild curvature remains editable as quads;
    # physical coincidence of both tessellated caps is checked below.
    for face in faces:
        a, b, c, d = [points[i] for i in face]
        plane = (b-a).cross(c-a)
        if plane.length < 1e-15 or plane.normalized().dot((c-a).cross(d-a).normalized()) < .98:
            return None
    copies = []
    caps = []
    previous_marks = []
    try:
        for source, loop in ((bm_a, loop_a), (bm_b, loop_b)):
            source.verts.index_update()
            ids = [v.index for v in loop]
            mesh = source.copy()
            copies.append(mesh)
            mesh.verts.ensure_lookup_table()
            layer = mesh.faces.layers.int.get('splitter_contact_surface') or mesh.faces.layers.int.new('splitter_contact_surface')
            previous_marks.append([f[layer] for f in mesh.faces])
            for face in mesh.faces:
                face[layer] = 0
            mesh.verts.ensure_lookup_table()
            # Adding a custom-data layer can invalidate existing BMesh handles.
            boundary = [mesh.verts[i] for i in ids]
            verts = [boundary[ref] if ref is not None else mesh.verts.new(p)
                     for p, ref in zip(points, refs)]
            generated = [mesh.faces.new([verts[i] for i in f]) for f in faces]
            caps.append(generated)
            for f in generated:
                f[layer] = 1
            bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
            if any(not e.is_manifold for e in mesh.edges) or cap_crossing_pairs(mesh, generated, .0001/unit_scale):
                raise ValueError('Grid crosses the source surface')
        from mathutils.bvhtree import BVHTree
        triangles = []
        for mesh in copies:
            sample = mesh.copy()
            try:
                marker = sample.faces.layers.int.get('splitter_contact_surface')
                bmesh.ops.triangulate(sample, faces=[f for f in sample.faces if f[marker]])
                triangles.append([tuple(v.co.copy() for v in f.verts) for f in sample.faces if f[marker]])
            finally:
                sample.free()
        for source, target in ((triangles[0], triangles[1]), (triangles[1], triangles[0])):
            coords = [p for tri in target for p in tri]
            tree = BVHTree.FromPolygons(coords, [tuple(range(i, i+3)) for i in range(0,len(coords),3)], all_triangles=True)
            for tri in source:
                sample = sum(tri, Vector())/3
                if tree.find_nearest(sample)[3]*unit_scale > .001:
                    raise ValueError('Opposite quad tessellations do not coincide')
        # Validation marks are temporary. The caller archives only genuinely
        # inherited contacts before assigning the current operation's marker.
        for mesh, previous in zip(copies, previous_marks):
            layer = mesh.faces.layers.int.get('splitter_contact_surface')
            for i, face in enumerate(mesh.faces):
                face[layer] = previous[i] if i < len(previous) else 0
        return copies[0], copies[1], caps[0], caps[1]
    except (ValueError, RuntimeError):
        for mesh in copies:
            mesh.free()
        return None


def validate_grid_gap(bm_a, bm_b, gap_mm, unit_scale):
    """Reject a grid whose tessellated interior samples lose physical clearance."""
    from mathutils.bvhtree import BVHTree
    triangles = []
    for mesh in (bm_a, bm_b):
        sample = mesh.copy()
        try:
            marker = sample.faces.layers.int.get('splitter_contact_surface')
            bmesh.ops.triangulate(sample, faces=[f for f in sample.faces if f[marker]])
            triangles.append([tuple(v.co.copy() for v in f.verts) for f in sample.faces if f[marker]])
        finally:
            sample.free()
    for source, target in ((triangles[0],triangles[1]), (triangles[1],triangles[0])):
        coords = [p for tri in target for p in tri]
        tree = BVHTree.FromPolygons(coords,[tuple(range(i,i+3)) for i in range(0,len(coords),3)],all_triangles=True)
        for tri in source:
            for weights in ((1/3,1/3,1/3),(.6,.2,.2),(.2,.6,.2),(.2,.2,.6)):
                p = sum((v*w for v,w in zip(tri,weights)),Vector())
                if abs(tree.find_nearest(p)[3]*unit_scale-gap_mm) > .003:
                    from .localized_errors import LocalizedGeometryError
                    raise LocalizedGeometryError('geometry.clearance_unresolved')


def contact_triangles(mesh):
    """Tessellate a copy for interfaces; leave the editable quads untouched."""
    sample = mesh.copy()
    try:
        marker = sample.faces.layers.int.get('splitter_contact_surface')
        if marker is None:
            return []
        bmesh.ops.triangulate(sample, faces=[f for f in sample.faces if f[marker]])
        return [tuple(v.co.copy() for v in f.verts) for f in sample.faces if f[marker]]
    finally:
        sample.free()


def finish_cut_mesh(mesh, source_tree, unit_scale, use_contact_marks=True):
    """Regrid only planar generated patches; preserve their exact physical surface.

    Runs after clearance for every preview method, before connectors. Work on
    a private BMesh so a rejected grid cannot damage the valid cut result.
    """
    from .geometry_material import _order_boundary_loops
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.normal_update()
        marker = bm.faces.layers.int.get('splitter_contact_surface')
        tolerance = .0001 / unit_scale
        if marker and use_contact_marks:
            selected = {f for f in bm.faces if f[marker]}
        else:
            # Plane/solid results do not always carry contact marks. Detect
            # generated faces from actual triangle samples, not warped centroids.
            mesh.calc_loop_triangles()
            generated = set()
            for tri in mesh.loop_triangles:
                p = sum((mesh.vertices[i].co for i in tri.vertices), Vector())/3
                hit = source_tree.find_nearest(p)
                if hit[0] is not None and hit[3] > tolerance:
                    generated.add(tri.polygon_index)
            bm.faces.ensure_lookup_table()
            selected = {bm.faces[i] for i in generated}
        if not selected:
            return dict(quads_created=0, fallback=False, patches=0)
        original_selected = {f.index for f in selected}
        before_volume = bm.calc_volume()
        layers = list(bm.faces.layers.int.values())
        def attributes(face):
            return (face.material_index, face.smooth, tuple(face[layer] for layer in layers))
        remaining = set(selected)
        groups = []
        while remaining:
            seed = min(remaining, key=lambda f:f.index)
            group = {seed}; remaining.remove(seed); stack = [seed]
            origin = seed.verts[0].co.copy(); normal = seed.normal.copy(); data = attributes(seed)
            while stack:
                face = stack.pop()
                for edge in face.edges:
                    for other in edge.link_faces:
                        if (other in remaining and attributes(other)==data
                                and other.normal.dot(normal) > .999999
                                and all(abs((v.co-origin).dot(normal)) <= tolerance for v in other.verts)):
                            remaining.remove(other);group.add(other);stack.append(other)
            groups.append((group,normal,data))
        created = []
        quad_count = 0
        for group, normal, data in groups:
            if all(len(f.verts)==4 for f in group):
                continue
            edges = {e for f in group for e in f.edges if sum(g in group for g in e.link_faces)==1}
            try:
                loops = _order_boundary_loops(list(edges))
            except ValueError:
                continue
            if len(loops)!=1:
                continue  # Preserve holes and disconnected boundaries.
            loop = loops[0]
            coords = [v.co.copy() for v in loop]
            from .geometry_contract import boundary_normal
            if boundary_normal(coords).dot(normal)<0:
                loop.reverse();coords.reverse()
            grid = grid_coordinates(coords,normal)
            if grid is None:
                continue
            points, refs, faces = grid
            area = sum(f.calc_area() for f in group)
            new_area = sum((points[f[1]]-points[f[0]]).cross(points[f[2]]-points[f[0]]).length/2
                         +(points[f[2]]-points[f[0]]).cross(points[f[3]]-points[f[0]]).length/2 for f in faces)
            if (any(abs((p-coords[0]).dot(normal))>tolerance for p in points)
                    or abs(area-new_area)>max(area*1e-5,tolerance*tolerance)):
                continue
            old_edges = {e for f in group for e in f.edges}
            old_verts = {v for f in group for v in f.verts}
            bmesh.ops.delete(bm,geom=list(group),context='FACES_ONLY')
            wires = [e for e in old_edges if e.is_valid and not e.link_faces]
            if wires:bmesh.ops.delete(bm,geom=wires,context='EDGES')
            unused = [v for v in old_verts if v.is_valid and not v.link_edges and v not in loop]
            if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
            verts = [loop[ref] if ref is not None else bm.verts.new(p) for p,ref in zip(points,refs)]
            for corners in faces:
                f = bm.faces.new([verts[i] for i in corners]);f.material_index=data[0];f.smooth=data[1]
                for layer,value in zip(layers,data[2]):f[layer]=value
                created.append(f)
            quad_count += len(faces)
        retained = [f for f in selected if f.is_valid]
        current = retained+created
        # A valid cut is retained as triangles when a regular grid cannot fit.
        ngons = [f for f in current if len(f.verts)>4]
        if ngons:
            result = bmesh.ops.triangulate(bm,faces=ngons)
            current = [f for f in current if f.is_valid]+list(result['faces'])
        bm.normal_update()
        if (any(not e.is_manifold for e in bm.edges)
                or abs(bm.calc_volume()-before_volume)>max(abs(before_volume)*1e-6,1e-5/unit_scale**3)):
            return dict(quads_created=0,fallback=True,patches=len(groups))
        stats = dict(quads_created=quad_count,fallback=any(len(f.verts)!=4 for f in current),patches=len(groups))
        if not quad_count and not ngons:
            return stats
        bm.faces.index_update()
        if not _same_cut_surface(mesh,bm,original_selected,{f.index for f in current if f.is_valid},unit_scale):
            return dict(quads_created=0,fallback=True,patches=len(groups))
        bm.to_mesh(mesh);mesh.update()
        return stats
    except (ValueError,RuntimeError,ReferenceError):
        # A failed topology improvement must never destroy an already valid cut.
        return dict(quads_created=0,fallback=True,patches=0)
    finally:
        bm.free()


def _same_cut_surface(original, candidate, original_ids, candidate_ids, unit_scale):
    """Check actual tessellated surfaces, rather than centers of warped quads."""
    import bpy
    from mathutils.bvhtree import BVHTree
    temporary=bpy.data.meshes.new('_quad_surface_check')
    try:
        candidate.to_mesh(temporary)
        meshes=(original,temporary)
        trees=[]
        for mesh in meshes:
            mesh.calc_loop_triangles()
            trees.append(BVHTree.FromPolygons([v.co for v in mesh.vertices],
                [tuple(t.vertices) for t in mesh.loop_triangles],all_triangles=True))
        for mesh,ids,tree in ((original,original_ids,trees[1]),(temporary,candidate_ids,trees[0])):
            for tri in mesh.loop_triangles:
                if tri.polygon_index not in ids:continue
                points=[mesh.vertices[i].co for i in tri.vertices]
                for weights in ((1/3,1/3,1/3),(.6,.2,.2),(.2,.6,.2),(.2,.2,.6)):
                    sample=sum((p*w for p,w in zip(points,weights)),Vector())
                    hit=tree.find_nearest(sample)
                    if hit[0] is None or hit[3]*unit_scale>.0001:return False
        return True
    finally:
        bpy.data.meshes.remove(temporary)


def finish_cut_pair(mesh_a, mesh_b, source_mesh, matrix_world, unit_scale, use_contact_marks=True):
    """Common topology-only finalization for loop, plane, solid and regions."""
    from mathutils.bvhtree import BVHTree
    source_mesh.calc_loop_triangles()
    tree = BVHTree.FromPolygons([matrix_world@v.co for v in source_mesh.vertices],
        [tuple(t.vertices) for t in source_mesh.loop_triangles],all_triangles=True)
    stats = [finish_cut_mesh(mesh,tree,unit_scale,use_contact_marks) for mesh in (mesh_a,mesh_b)]
    return dict(quads_created=sum(s['quads_created'] for s in stats),
                fallback=any(s['fallback'] for s in stats),parts=stats)
