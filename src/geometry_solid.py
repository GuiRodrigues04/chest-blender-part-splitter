"""Módulo de corte volumétrico por cortador sólido personalizado (Fase 3).

Permite dividir modelos 3D usando sólidos fechados e manifold (primitivas como
caixa, cilindro, esfera e cápsula, ou qualquer objeto fechado da cena) através
de operações booleanas exatas (Interseção e Diferença).
"""
from .translations import localized_format

import math
from typing import List, Tuple, Dict, Any, Optional
import bpy
import bmesh
from mathutils import Vector, Matrix

from .constants import (
    COLLECTION_GUIDES_NAME,
    SOLID_CUTTER_NAME,
    VOLUME_REL_TOLERANCE,
)
from .geometry_plane import evaluate_bmesh_metrics, NoIntersectionError


class SolidCutterValidationError(Exception):
    """Exceção para cortador sólido inválido, aberto ou sem contato com o alvo."""
    pass


class SolidSliceError(Exception):
    """Exceção para falha na execução do corte booleano volumétrico."""
    pass


def create_bmesh_capsule(
    bm: bmesh.types.BMesh,
    radius: float,
    total_length: float,
    segments: int = 32,
    rings: int = 8,
):
    """Cria uma cápsula tridimensional 100% manifold orientada ao longo do eixo Z."""
    r = radius
    cyl_h = max(0.0, total_length - 2.0 * r)
    half_h = cyl_h / 2.0

    verts_grid = []

    # 1. Polo inferior (-Z)
    bot_pole = bm.verts.new((0.0, 0.0, -half_h - r))

    # 2. Anéis do hemisfério inferior
    for ring in range(1, rings):
        phi = -math.pi / 2.0 + (math.pi / 2.0) * (ring / rings)
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        z = -half_h + r * sin_phi
        ring_r = r * cos_phi
        ring_verts = []
        for s in range(segments):
            theta = 2.0 * math.pi * s / segments
            x = ring_r * math.cos(theta)
            y = ring_r * math.sin(theta)
            ring_verts.append(bm.verts.new((x, y, z)))
        verts_grid.append(ring_verts)

    # 3. Equador (único quando cyl_h é desprezível, ou inferior + superior quando há corpo cilíndrico)
    if cyl_h > max(1e-4, 0.01 * r):
        eq_bot = []
        for s in range(segments):
            theta = 2.0 * math.pi * s / segments
            eq_bot.append(bm.verts.new((r * math.cos(theta), r * math.sin(theta), -half_h)))
        verts_grid.append(eq_bot)

        eq_top = []
        for s in range(segments):
            theta = 2.0 * math.pi * s / segments
            eq_top.append(bm.verts.new((r * math.cos(theta), r * math.sin(theta), half_h)))
        verts_grid.append(eq_top)
    else:
        half_h = 0.0
        eq_mid = []
        for s in range(segments):
            theta = 2.0 * math.pi * s / segments
            eq_mid.append(bm.verts.new((r * math.cos(theta), r * math.sin(theta), 0.0)))
        verts_grid.append(eq_mid)

    # 5. Anéis do hemisfério superior
    for ring in range(1, rings):
        phi = (math.pi / 2.0) * (ring / rings)
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        z = half_h + r * sin_phi
        ring_r = r * cos_phi
        ring_verts = []
        for s in range(segments):
            theta = 2.0 * math.pi * s / segments
            x = ring_r * math.cos(theta)
            y = ring_r * math.sin(theta)
            ring_verts.append(bm.verts.new((x, y, z)))
        verts_grid.append(ring_verts)

    # 6. Polo superior (+Z)
    top_pole = bm.verts.new((0.0, 0.0, half_h + r))

    # Conecta polo inferior ao primeiro anel
    first_ring = verts_grid[0]
    for s in range(segments):
        s_next = (s + 1) % segments
        bm.faces.new((bot_pole, first_ring[s], first_ring[s_next]))

    # Conecta anéis consecutivos com quads
    for r_idx in range(len(verts_grid) - 1):
        r1 = verts_grid[r_idx]
        r2 = verts_grid[r_idx + 1]
        for s in range(segments):
            s_next = (s + 1) % segments
            bm.faces.new((r1[s], r2[s], r2[s_next], r1[s_next]))

    # Conecta último anel ao polo superior
    last_ring = verts_grid[-1]
    for s in range(segments):
        s_next = (s + 1) % segments
        bm.faces.new((last_ring[s_next], last_ring[s], top_pole))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def ensure_solid_outward_normals(bm: bmesh.types.BMesh) -> None:
    """Garante que todas as faces de uma malha fechada tenham normais apontando para o exterior."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    if not bm.verts or not bm.faces:
        return
    center = sum((v.co for v in bm.verts), Vector()) / float(len(bm.verts))
    signed_vol = sum(f.normal.dot(f.calc_center_median() - center) * f.calc_area() for f in bm.faces)
    if signed_vol < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()


def create_primitive_cutter_mesh(
    name: str,
    primitive_type: str,
    dims: Vector,
    segments: int = 32,
) -> bpy.types.Mesh:
    """Gera uma malha fechada e manifold para uso como cortador sólido."""
    bm = bmesh.new()

    dx = max(1e-4, dims.x)
    dy = max(1e-4, dims.y)
    dz = max(1e-4, dims.z)

    if primitive_type == 'BOX':
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((dx, dy, dz)), verts=bm.verts[:])

    elif primitive_type == 'CYLINDER':
        r = min(dx, dy) / 2.0
        depth = dz
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=segments,
            radius1=r,
            radius2=r,
            depth=depth,
        )

    elif primitive_type == 'SPHERE':
        rx = dx / 2.0
        ry = dy / 2.0
        rz = dz / 2.0
        bmesh.ops.create_uvsphere(
            bm,
            u_segments=segments,
            v_segments=max(8, segments // 2),
            radius=1.0,
        )
        bmesh.ops.scale(bm, vec=Vector((rx, ry, rz)), verts=bm.verts[:])

    elif primitive_type == 'CAPSULE':
        r = min(dx, dy) / 2.0
        total_len = max(dz, 2.0 * r + 1e-4)
        create_bmesh_capsule(
            bm,
            radius=r,
            total_length=total_len,
            segments=segments,
            rings=max(6, segments // 4),
        )

    else:
        # Fallback para cubo
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((dx, dy, dz)), verts=bm.verts[:])

    ensure_solid_outward_normals(bm)

    mesh_data = bpy.data.meshes.new(name)
    bm.to_mesh(mesh_data)
    bm.free()
    return mesh_data


def validate_solid_cutter(
    cutter_obj: Optional[bpy.types.Object],
    target_obj: Optional[bpy.types.Object],
    unit_scale: float = 1000.0,
) -> Dict[str, Any]:
    """Verifica se o cortador é válido, fechado, manifold e intersecta o alvo."""
    if bpy.context and hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

    from .scene_state import object_in_scene
    if not object_in_scene(cutter_obj, bpy.context.scene, mesh=True):
        raise SolidCutterValidationError("Nenhum objeto cortador sólido foi especificado ou o objeto foi excluído.")

    if cutter_obj.type != 'MESH':
        raise SolidCutterValidationError(localized_format('audit.dynamic.20', v0=cutter_obj.name))

    if target_obj and cutter_obj == target_obj:
        raise SolidCutterValidationError("O cortador não pode ser o próprio objeto alvo da divisão.")

    mesh = cutter_obj.data
    if not mesh or len(mesh.vertices) < 4 or len(mesh.polygons) < 4:
        raise SolidCutterValidationError(localized_format('audit.dynamic.21', v0=cutter_obj.name))

    # Avaliação com BMesh em espaço global
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.transform(cutter_obj.matrix_world)

    non_manifold = [e for e in bm.edges if not e.is_manifold]
    is_manifold = (len(non_manifold) == 0 and len(bm.verts) >= 4 and len(bm.faces) >= 4)

    if not is_manifold:
        count_open = len(non_manifold)
        bm.free()
        raise SolidCutterValidationError(
            localized_format('audit.dynamic.22', v0=cutter_obj.name, v1=count_open)
        )

    vol_bu = abs(bm.calc_volume())
    vol_mm3 = vol_bu * (unit_scale ** 3)
    triangles = sum(len(f.verts) - 2 for f in bm.faces)

    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    c_min = Vector((min(xs), min(ys), min(zs)))
    c_max = Vector((max(xs), max(ys), max(zs)))
    bm.free()

    if vol_mm3 < 1e-4:
        raise SolidCutterValidationError(localized_format('audit.dynamic.23', v0=cutter_obj.name))

    # Verificação de colisão de bounding box com o alvo
    if target_obj and target_obj.type == 'MESH':
        t_corners = [target_obj.matrix_world @ Vector(corner) for corner in target_obj.bound_box]
        t_xs = [c.x for c in t_corners]
        t_ys = [c.y for c in t_corners]
        t_zs = [c.z for c in t_corners]
        t_min = Vector((min(t_xs), min(t_ys), min(t_zs)))
        t_max = Vector((max(t_xs), max(t_ys), max(t_zs)))

        no_overlap = (
            c_max.x < t_min.x or c_min.x > t_max.x or
            c_max.y < t_min.y or c_min.y > t_max.y or
            c_max.z < t_min.z or c_min.z > t_max.z
        )
        if no_overlap:
            raise SolidCutterValidationError(
                localized_format('audit.dynamic.24', v0=cutter_obj.name)
            )

    return {
        "valid": True,
        "is_manifold": is_manifold,
        "non_manifold_edges": 0,
        "volume_mm3": vol_mm3,
        "triangles": triangles,
    }


def _cutter_snapshot(cutter, offset_bu, scene):
    """World-space miter offset in physical units; never scale about object origin."""
    import numpy as np
    evaluated = cutter.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.transform(cutter.matrix_world)
        ensure_solid_outward_normals(bm)
        if not bm.faces or not all(e.is_manifold for e in bm.edges) or abs(bm.calc_volume()) < 1e-18:
            raise SolidCutterValidationError("A malha avaliada do cortador deve ser um sólido fechado.")
        planes = [(f.index, f.verts[0].co.copy(), f.normal.copy(), (f.verts[1].co-f.verts[0].co).normalized()) for f in bm.faces]
        if abs(offset_bu) > 1e-12:
            changes = []
            deltas_by_vert = {}
            for vert in bm.verts:
                normals = np.array([tuple(f.normal) for f in vert.link_faces], dtype=float)
                delta, *_ = np.linalg.lstsq(normals, np.full(len(normals), offset_bu), rcond=None)
                error = np.max(np.abs(normals @ delta - offset_bu))
                if error > max(1e-8, abs(offset_bu)*0.01):
                    raise SolidSliceError("A folga não mantém as faces deste cortador. Use uma folga menor ou um cortador mais simples.")
                vec_delta = Vector(delta)
                changes.append((vert, vec_delta))
                deltas_by_vert[vert] = vec_delta
            for edge in bm.edges:
                v0, v1 = edge.verts
                e0 = v1.co - v0.co
                len0_sq = e0.length_squared
                if len0_sq > 1e-12:
                    e1 = e0 + (deltas_by_vert[v1] - deltas_by_vert[v0])
                    if e1.dot(e0) < len0_sq * 0.15:
                        raise SolidSliceError("A folga é grande demais para os detalhes do cortador.")
            for vert, delta in changes:
                vert.co += delta
            ensure_solid_outward_normals(bm)
            if any(abs((v.co-p).dot(n)-offset_bu) > max(1e-5, abs(offset_bu)*0.05)
                   for (idx,p,n,u), f in zip(planes, bm.faces) for v in f.verts):
                raise SolidSliceError("A folga deformaria uma face do cortador.")
        data = bpy.data.meshes.new('_solid_operand_mesh')
        bm.to_mesh(data)
        from .geometry_clearance import triangulated_source_mesh
        triangulated = triangulated_source_mesh(data)
        bpy.data.meshes.remove(data)
        data = triangulated
        for mat in cutter.data.materials:
            data.materials.append(mat)
        obj = bpy.data.objects.new('_solid_operand', data)
        scene.collection.objects.link(obj)
        return obj, planes
    finally:
        bm.free()
        evaluated.to_mesh_clear()


def _solid_contact_interface(mesh, planes, offset_bu, inside, unit_scale, face_index=-1):
    """Extract only the actual coplanar contact patch, with holes and concavities."""
    from .geometry_material import _order_boundary_loops
    from .geometry_contract import build_cut_interface
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.normal_update()
        tolerance = max(1e-5, 0.05 / unit_scale)
        best, best_area, best_index = None, -1, -1

        def _scan(target_face_idx):
            nonlocal best, best_area, best_index
            for index, p, n, axis_u in planes:
                if target_face_idx >= 0 and index != target_face_idx:
                    continue
                point = p + n * offset_bu
                normal = n if inside else -n
                faces = {f for f in bm.faces if f.normal.dot(normal) > 0.999
                         and all(abs((v.co - point).dot(n)) < tolerance for v in f.verts)}
                if not faces:
                    continue
                area = sum(f.calc_area() for f in faces)
                edges = {e for f in faces for e in f.edges
                         if sum(g in faces for g in e.link_faces) == 1}
                loops = _order_boundary_loops(list(edges))
                if not loops or area <= best_area:
                    continue
                coords = [[v.co.copy() for v in loop] for loop in loops]
                origin = sum((v.co * f.calc_area() / len(f.verts) for f in faces for v in f.verts), Vector()) / area
                # Keep the winding axis A->B even when this patch is taken from B.
                normal_a_to_b = n
                iface = build_cut_interface(origin, normal_a_to_b, [], unit_scale=unit_scale,
                                            source_mode='SOLID', boundary_loops_world=coords)
                from .geometry_contract import orient_interface
                iface = orient_interface(iface, axis_u)
                best, best_area, best_index = iface, area, index

        if face_index >= 0:
            _scan(face_index)
        if best is None:
            _scan(-1)

        return best, best_index
    finally:
        bm.free()


class SolidBooleanError(SolidSliceError):
    """An invalid Boolean result can be retried without changing parameters."""


def slice_mesh_by_solid(
    source_mesh, matrix_world, cutter_obj, target_mesh_a, target_mesh_b,
    invert_sides=False, unit_scale=1000.0, part_clearance_mm=0.0,
    part_clearance_apply_to='PART', interface_face_index=-1,
):
    arguments = dict(source_mesh=source_mesh, matrix_world=matrix_world,
                     cutter_obj=cutter_obj, target_mesh_a=target_mesh_a,
                     target_mesh_b=target_mesh_b, invert_sides=invert_sides,
                     unit_scale=unit_scale, part_clearance_mm=part_clearance_mm,
                     part_clearance_apply_to=part_clearance_apply_to,
                     interface_face_index=interface_face_index)
    try:
        return _slice_mesh_by_solid(**arguments)
    except SolidBooleanError:
        solvers = bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items
        if 'MANIFOLD' not in {item.identifier for item in solvers}:
            raise
        return _slice_mesh_by_solid(**arguments, _solver='MANIFOLD')


def _slice_mesh_by_solid(
    source_mesh, matrix_world, cutter_obj, target_mesh_a, target_mesh_b,
    invert_sides=False, unit_scale=1000.0, part_clearance_mm=0.0,
    part_clearance_apply_to='PART', interface_face_index=-1, _solver='EXACT',
):
    """Exact transactional booleans with independent physical A/B clearance operands."""
    from .scene_state import object_in_scene
    if not object_in_scene(cutter_obj, bpy.context.scene, mesh=True):
        raise SolidCutterValidationError("O cortador foi excluído da cena.")
    scene = bpy.context.scene
    amount = max(0.0, part_clearance_mm)/unit_scale
    gap_a = amount if part_clearance_apply_to == 'PART' else amount/2 if part_clearance_apply_to == 'BOTH' else 0.0
    gap_b = amount if part_clearance_apply_to == 'CAVITY' else amount/2 if part_clearance_apply_to == 'BOTH' else 0.0
    offsets = ((gap_a, -gap_b) if invert_sides else (-gap_a, gap_b))
    created, evaluated_objects = [], []
    results = {}
    interfaces = {}
    chosen_face = interface_face_index
    try:
        for side, destination, offset in (('A',target_mesh_a,offsets[0]),('B',target_mesh_b,offsets[1])):
            operand, planes = _cutter_snapshot(cutter_obj, offset, scene)
            created.append(operand)
            from .geometry_clearance import triangulated_source_mesh
            data = triangulated_source_mesh(source_mesh)
            work = bpy.data.objects.new('_solid_work', data)
            created.append(work)
            scene.collection.objects.link(work)
            work.matrix_world = matrix_world
            mod = work.modifiers.new('Solid boolean', 'BOOLEAN')
            inside = (side == 'A') != invert_sides
            mod.operation = 'INTERSECT' if inside else 'DIFFERENCE'
            mod.solver = _solver
            mod.material_mode = 'INDEX'
            mod.object = operand
            bpy.context.view_layer.update()
            evaluated = work.evaluated_get(bpy.context.evaluated_depsgraph_get())
            evaluated_objects.append(evaluated)
            result_mesh = evaluated.to_mesh()
            bm = bmesh.new()
            try:
                bm.from_mesh(result_mesh)
                bm.transform(matrix_world)
                bm.normal_update()
                from .diagnostic import sanitize_mesh_micro_degeneracies, validate_bmesh_mesh_geometry
                from .geometry_clearance import remove_boolean_wires
                remove_boolean_wires(bm)
                sanitize_mesh_micro_degeneracies(bm, unit_scale)
                remove_boolean_wires(bm)
                check = validate_bmesh_mesh_geometry(bm, unit_scale)
                metrics = evaluate_bmesh_metrics(bm, unit_scale)
                if not check['is_valid'] or not metrics['is_manifold'] or metrics['volume_mm3'] <= 1e-4:
                    raise SolidBooleanError("O cortador/folga não produziu duas partes fechadas com volume. Ajuste a interseção ou a folga.")
                destination.materials.clear()
                for mat in source_mesh.materials:
                    destination.materials.append(mat)
                for f in bm.faces:
                    if f.material_index >= len(source_mesh.materials):
                        f.material_index = 0
                destination.clear_geometry()
                bm.to_mesh(destination)
                destination.update()
                results[side] = metrics
            finally:
                bm.free()
            iface, selected = _solid_contact_interface(destination, planes, offset, inside,
                                                       unit_scale, chosen_face)
            if iface:
                # Its normal always points from A to B, independent of male selection.
                if invert_sides:
                    # Rebuild preserves a right handed UV frame.
                    from .geometry_contract import build_cut_interface, orient_interface
                    fixed_u = iface.axis_u_world.copy()
                    loops = [[iface.uv_to_world(*uv) for uv in poly]
                             for poly in iface.outer_contours_uv + iface.hole_contours_uv]
                    iface = build_cut_interface(iface.origin_world, -iface.normal_a_to_b_world, [],
                                                unit_scale=unit_scale, source_mode='SOLID', boundary_loops_world=loops)
                    iface = orient_interface(iface, fixed_u)
                interfaces[side] = iface
                if side == 'A':
                    chosen_face = selected
        results['interface'] = interfaces.get('A')
        results['interfaces'] = interfaces
        results['interface_face_index'] = chosen_face
        results['sum_volume_mm3'] = results['A']['volume_mm3'] + results['B']['volume_mm3']
        return results
    finally:
        for evaluated in evaluated_objects:
            evaluated.to_mesh_clear()
        for obj in reversed(created):
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)


def align_vertices(cutter, target, cutter_index, target_index, move_mode='OBJECT'):
    """World translation only; also works with parent transforms and unapplied scale."""
    if cutter == target or move_mode not in {'OBJECT', 'VERTEX'}:
        raise ValueError("Cortador e alvo devem ser objetos diferentes; escolha um modo de alinhamento válido.")
    if cutter.mode == 'EDIT':
        bm_c = bmesh.from_edit_mesh(cutter.data)
        bm_c.verts.ensure_lookup_table()
        if not (0 <= cutter_index < len(bm_c.verts)):
            raise ValueError("Selecione um vértice válido no cortador.")
        source = cutter.matrix_world @ bm_c.verts[cutter_index].co
    else:
        if not (0 <= cutter_index < len(cutter.data.vertices)):
            raise ValueError("Selecione um vértice válido no cortador.")
        source = cutter.matrix_world @ cutter.data.vertices[cutter_index].co

    if target.mode == 'EDIT':
        bm_t = bmesh.from_edit_mesh(target.data)
        bm_t.verts.ensure_lookup_table()
        if not (0 <= target_index < len(bm_t.verts)):
            raise ValueError("Selecione um vértice válido no alvo.")
        destination = target.matrix_world @ bm_t.verts[target_index].co
    else:
        if not (0 <= target_index < len(target.data.vertices)):
            raise ValueError("Selecione um vértice válido no alvo.")
        destination = target.matrix_world @ target.data.vertices[target_index].co

    if move_mode == 'VERTEX':
        if abs(cutter.matrix_world.determinant()) < 1e-12:
            raise ValueError("O cortador possui escala nula.")
        local_destination = cutter.matrix_world.inverted() @ destination
        if cutter.data.users > 1:
            if cutter.mode == 'EDIT':
                raise ValueError("A malha do cortador é compartilhada. Torne-a independente antes de editar.")
            cutter.data = cutter.data.copy()
        if cutter.mode == 'EDIT':
            bm_c.verts[cutter_index].co = local_destination
            bm_c.normal_update()
            bmesh.update_edit_mesh(cutter.data, loop_triangles=True, destructive=False)
        else:
            cutter.data.vertices[cutter_index].co = local_destination
            cutter.data.update()
        for key in ('chest_align_anchor_local', 'chest_align_ref_pos'):
            if key in cutter:
                del cutter[key]
    else:
        matrix = cutter.matrix_world.copy()
        matrix.translation += destination - source
        cutter.matrix_world = matrix


def compute_solid_explosion_offsets(
    obj_a: bpy.types.Object,
    obj_b: bpy.types.Object,
    explosion_distance_mm: float,
    unit_scale: float = 1000.0,
) -> Tuple[Vector, Vector]:
    """Calcula os vetores de deslocamento explodido baseados no vetor entre os centróides de A e B."""
    dist_bu = (explosion_distance_mm / unit_scale) / 2.0
    if dist_bu < 1e-6:
        return Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))

    center_a = Vector((0.0, 0.0, 0.0))
    center_b = Vector((0.0, 0.0, 0.0))

    if obj_a and obj_a.data and len(obj_a.data.vertices) > 0:
        corners_a = [obj_a.matrix_world @ Vector(c) for c in obj_a.bound_box]
        center_a = sum(corners_a, Vector((0.0, 0.0, 0.0))) / float(len(corners_a))

    if obj_b and obj_b.data and len(obj_b.data.vertices) > 0:
        corners_b = [obj_b.matrix_world @ Vector(c) for c in obj_b.bound_box]
        center_b = sum(corners_b, Vector((0.0, 0.0, 0.0))) / float(len(corners_b))

    direction = center_a - center_b
    if direction.length > 1e-4:
        norm = direction.normalized()
    else:
        norm = Vector((0.0, 0.0, 1.0))

    offset_a = norm * dist_bu
    offset_b = -norm * dist_bu
    return offset_a, offset_b
