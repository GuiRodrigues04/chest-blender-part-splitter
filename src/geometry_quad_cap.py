"""Conservative disk grid, with fixed boundary and smooth interior interpolation."""
import bmesh
from mathutils import Vector


def grid_coordinates(boundary, normal):
    n = len(boundary)
    if n < 8 or n > 128 or n % 2:
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
