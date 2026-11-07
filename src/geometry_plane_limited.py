"""Separate only complete planar sections inside the finite guide; no side walls."""
import bmesh
from mathutils import Vector

from .geometry_plane import (PlaneSliceError, NoIntersectionError,
    cap_open_cut_boundaries, reconstruct_boundary_loops, evaluate_bmesh_metrics)


PARTIAL_MESSAGE = ('O corte não separa uma peça: a área limitada cobre apenas parte '
                   'da seção. Amplie ou reposicione o retângulo.')


def _eligible_edges(edges, region):
    remaining = set(edges)
    selected = set()
    while remaining:
        seed = remaining.pop()
        group, stack = {seed}, [seed]
        while stack:
            edge = stack.pop()
            for vert in edge.verts:
                for other in vert.link_edges:
                    if other in remaining:
                        remaining.remove(other)
                        group.add(other)
                        stack.append(other)
        if not any(region.clip_segment(e.verts[0].co, e.verts[1].co) for e in group):
            continue
        vertices = {v for e in group for v in e.verts}
        if (not all(region.contains(v.co) for v in vertices) or
                any(sum(e in group for e in v.link_edges) != 2 for v in vertices)):
            raise PlaneSliceError(PARTIAL_MESSAGE)
        selected.update(group)
    if not selected:
        raise NoIntersectionError('A área limitada não contém uma seção completa. Amplie ou reposicione o retângulo.')
    return selected


def _limited_side(source_mesh, matrix_world, origin, normal, region,
                  include_untouched, unit_scale, tolerance):
    bm = bmesh.new()
    try:
        bm.from_mesh(source_mesh)
        bm.transform(matrix_world)
        bm.normal_update()
        result = bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                                       plane_co=origin, plane_no=normal,
                                       clear_inner=False, clear_outer=False, dist=1e-7)
        cut = [e for e in result.get('geom_cut', []) if isinstance(e, bmesh.types.BMEdge) and e.is_valid]
        selected = _eligible_edges(cut, region)
        # Flood surface faces without crossing the selected closed sections.
        # Other sections of the infinite plane remain connected and unseparated.
        unvisited, keep = set(bm.faces), set()
        negative_found, positive_found = False, False
        while unvisited:
            start = unvisited.pop()
            component, stack, signs = {start}, [start], set()
            while stack:
                face = stack.pop()
                for edge in face.edges:
                    if edge in selected:
                        distances = [(v.co-origin).dot(normal) for v in face.verts]
                        farthest = max(distances, key=abs)
                        if abs(farthest) > 1e-8:
                            signs.add(-1 if farthest < 0 else 1)
                    else:
                        for other in edge.link_faces:
                            if other in unvisited:
                                unvisited.remove(other)
                                component.add(other)
                                stack.append(other)
            if signs == {-1, 1}:
                raise PlaneSliceError(PARTIAL_MESSAGE)
            negative_found |= signs == {-1}
            positive_found |= signs == {1}
            if signs == {-1} or (not signs and include_untouched):
                keep.update(component)
        if not negative_found or not positive_found:
            raise PlaneSliceError(PARTIAL_MESSAGE)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keep], context='FACES')
        boundaries = [e for e in selected if e.is_valid and e.is_boundary]
        loops = reconstruct_boundary_loops(boundaries)
        cap_open_cut_boundaries(bm, cut_edges=boundaries, plane_origin=origin,
                               plane_normal=normal, coplanar_tol_bu=tolerance)
        from .geometry_clearance import remove_boolean_wires
        from .diagnostic import sanitize_mesh_micro_degeneracies
        remove_boolean_wires(bm)
        sanitize_mesh_micro_degeneracies(bm, unit_scale)
        remove_boolean_wires(bm)
        bm.normal_update()
        metrics = evaluate_bmesh_metrics(bm, unit_scale)
        if not metrics['is_manifold'] or metrics['volume_mm3'] <= 0:
            raise PlaneSliceError('A área limitada não produziu duas peças fechadas. Amplie ou reposicione o retângulo.')
        return bm, metrics, loops
    except Exception:
        bm.free()
        raise


def slice_mesh_by_limited_plane(source_mesh, matrix_world, plane_origin, plane_normal,
                                target_mesh_a, target_mesh_b, plane_region,
                                invert_sides=False, unit_scale=1000.0,
                                coplanar_tol_mm=.05, plane_offset_mm=0.0,
                                part_clearance_mm=0.0, part_clearance_apply_to='PART'):
    norm = plane_normal.normalized()
    if norm.length < 1e-6:
        raise PlaneSliceError('Normal do plano inválida.')
    base = plane_origin + norm*(plane_offset_mm/unit_scale)
    effective = -norm if invert_sides else norm
    meshes, results, interface_loops = [], {}, []
    try:
        for key, normal in [('A', effective), ('B', -effective)]:
            shift = 0.0
            if part_clearance_apply_to == 'BOTH':
                shift = max(0, part_clearance_mm)/unit_scale/2
            elif ((key == 'A' and part_clearance_apply_to == 'PART') or
                  (key == 'B' and part_clearance_apply_to == 'CAVITY')):
                shift = max(0, part_clearance_mm)/unit_scale
            origin = base-normal*shift
            region = plane_region.shifted(origin-plane_origin)
            bm, metrics, loops = _limited_side(source_mesh, matrix_world, origin, normal,
                region, include_untouched=(key == ('A' if invert_sides else 'B')),
                unit_scale=unit_scale, tolerance=max(1e-6, coplanar_tol_mm/unit_scale))
            meshes.append(bm)
            results[key] = metrics
            if key == 'A':
                interface_loops = loops
        from .geometry_contract import build_cut_interface
        results['interface'] = build_cut_interface(base, effective,
            [p for loop in interface_loops for p in loop], unit_scale=unit_scale,
            source_mode='PLANE', boundary_loops_world=interface_loops)
        results['sum_volume_mm3'] = sum(results[k]['volume_mm3'] for k in ('A','B'))
        for bm, target in zip(meshes, (target_mesh_a, target_mesh_b)):
            target.clear_geometry()
            target.materials.clear()
            for mat in source_mesh.materials:
                target.materials.append(mat)
            bm.to_mesh(target)
            target.update()
        return results
    finally:
        for bm in meshes:
            bm.free()
