"""A shared footprint and real supporting surfaces for curved cut contacts.

Internal tessellation edges are not physical boundaries. Preserve the common
projected contact domain, and keep each part's triangles for picking/anchoring.
"""
import math
from mathutils import Vector
from .geometry_contract import build_cut_interface, interface_point


def complete_contact_pair(a, b, axis, scale, origin):
    from .geometry_clearance_blade import _triangles
    from .geometry_material import _order_boundary_loops
    from .geometry_plane import common_planar_interface, PlaneSliceError

    normal = axis.normalized()
    surfaces, boundaries = [], []
    for part, sign in ((a, 1), (b, -1)):
        marker = part.faces.layers.int.get('splitter_contact_surface')
        caps = {f for f in part.faces if marker and f[marker]}
        if not caps:
            return None
        triangles = _triangles(part)
        projected_area = 0.0
        for p, q, r in triangles:
            cross = (q-p).cross(r-p)
            # A folded/vertical surface needs its existing local-contact path.
            if cross.length < 1e-16 or sign*cross.normalized().dot(normal) <= .02:
                return None
            projected_area += abs(cross.dot(normal))*.5
        edges = [e for e in part.edges if sum(f in caps for f in e.link_faces) == 1]
        loops = [[v.co.copy() for v in loop] for loop in _order_boundary_loops(edges)]
        if not loops:
            return None
        frame = build_cut_interface(origin, normal, [], boundary_loops_world=loops, unit_scale=scale)
        # Projected area conservation rejects overlapping/folded cap domains.
        if abs(projected_area*scale**2-frame.area_mm2) > max(.001, frame.area_mm2*1e-5):
            return None
        surfaces.append(triangles)
        boundaries.append(loops)
    try:
        common = common_planar_interface(*boundaries, origin, normal, scale)
    except PlaneSliceError:
        return None
    if common.area_mm2 <= .0001:
        return None
    loops = [[common.uv_to_world(*uv) for uv in poly]
             for poly in common.outer_contours_uv+common.hole_contours_uv]
    patches = []
    for triangles, sign in zip(surfaces, (1, -1)):
        support = build_cut_interface(origin, normal, [], interface_triangles=triangles,
                                      boundary_loops_world=loops, unit_scale=scale)
        support.is_planar = False
        anchor = interface_point(support, 0., 0.)
        patches.append(dict(origin=anchor, normal=normal*sign, loops=loops,
                            boundary=max(loops, key=len), triangles=triangles))
    return tuple(patches)


def domain_centroid(outer, holes):
    """Area centroid, independent of triangulation and boundary vertex density."""
    area = xsum = ysum = 0.0
    for contours, sign in ((outer, 1), (holes, -1)):
        for poly in contours:
            terms = [(p[0]*q[1]-q[0]*p[1], p, q)
                     for p, q in zip(poly, poly[1:]+poly[:1])]
            twice = math.fsum(cross for cross, _, _ in terms)
            if abs(twice) < 1e-20:
                continue
            weight = sign*abs(twice)*.5
            xsum += weight*math.fsum((p[0]+q[0])*cross for cross,p,q in terms)/(3*twice)
            ysum += weight*math.fsum((p[1]+q[1])*cross for cross,p,q in terms)/(3*twice)
            area += weight
    return (xsum/area, ysum/area) if area > 1e-20 else None
