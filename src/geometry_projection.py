"""Planar union of the complete selected shell, including a relief's overhang."""
import bmesh
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt


def projected_region_outline(obj, analysis, scale):
    from .geometry_loop import _get_orthonormal_basis
    from .geometry_material import _order_boundary_loops
    normal = -analysis['inward_dir_world']
    center = analysis['centroid_world']
    support = center + normal * min((p-center).dot(normal) for p in analysis['coords_world'])
    u, v = _get_orthonormal_basis(normal)
    mesh = obj.data
    mesh.calc_loop_triangles()
    selected = set(analysis['region_face_indices'])
    vertices, faces, lookup = [], [], {}
    for triangle in mesh.loop_triangles:
        if triangle.polygon_index not in selected:
            continue
        points = [obj.matrix_world @ mesh.vertices[i].co - support for i in triangle.vertices]
        points = [Vector((p.dot(u)*scale, p.dot(v)*scale)) for p in points]
        cross = (points[1]-points[0]).cross(points[2]-points[0])
        if abs(cross) < 1e-10:
            continue
        if cross < 0:
            points.reverse()
        indices = []
        for point in points:
            key = tuple(point)
            if key not in lookup:
                lookup[key] = len(vertices)
                vertices.append(point)
            indices.append(lookup[key])
        faces.append(indices)
    # Face provenance selects the UNION, never an even/odd subtraction of
    # overlapping projections. Millimetres keep the CDT tolerance physical.
    coords, _, triangles, _, _, origins = delaunay_2d_cdt(vertices, [], faces, 0, 1e-6, True)
    bm = bmesh.new()
    try:
        verts = [bm.verts.new((p.x, p.y, 0)) for p in coords]
        for triangle, origin in zip(triangles, origins):
            if origin:
                bm.faces.new([verts[i] for i in triangle])
        loops = _order_boundary_loops([e for e in bm.edges if e.is_boundary])
        # Hole-bearing selections use the dedicated region engine. A fallback
        # must not bridge disconnected outlines or fill a real hole.
        if not loops or len(loops) != 1:
            from .localized_errors import LocalizedGeometryError
            raise LocalizedGeometryError('geometry.depth_region_overhang')
        return [support + (p.co.x*u + p.co.y*v)/scale for p in loops[0]]
    finally:
        bm.free()
