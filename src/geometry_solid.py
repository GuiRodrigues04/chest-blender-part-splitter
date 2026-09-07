"""Módulo de corte volumétrico por cortador sólido personalizado (Fase 3).

Permite dividir modelos 3D usando sólidos fechados e manifold (primitivas como
caixa, cilindro, esfera e cápsula, ou qualquer objeto fechado da cena) através
de operações booleanas exatas (Interseção e Diferença).
"""

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

    # 3. Equador inferior
    eq_bot = []
    for s in range(segments):
        theta = 2.0 * math.pi * s / segments
        eq_bot.append(bm.verts.new((r * math.cos(theta), r * math.sin(theta), -half_h)))
    verts_grid.append(eq_bot)

    # 4. Equador superior
    eq_top = []
    for s in range(segments):
        theta = 2.0 * math.pi * s / segments
        eq_top.append(bm.verts.new((r * math.cos(theta), r * math.sin(theta), half_h)))
    verts_grid.append(eq_top)

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

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

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

    if not cutter_obj or cutter_obj.name not in bpy.data.objects:
        raise SolidCutterValidationError("Nenhum objeto cortador sólido foi especificado ou o objeto foi excluído.")

    if cutter_obj.type != 'MESH':
        raise SolidCutterValidationError(f"O cortador '{cutter_obj.name}' deve ser do tipo MESH (malha poligonal).")

    if target_obj and cutter_obj == target_obj:
        raise SolidCutterValidationError("O cortador não pode ser o próprio objeto alvo da divisão.")

    mesh = cutter_obj.data
    if not mesh or len(mesh.vertices) < 4 or len(mesh.polygons) < 4:
        raise SolidCutterValidationError(f"O cortador '{cutter_obj.name}' possui geometria insuficiente ou vazia.")

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
            f"O cortador '{cutter_obj.name}' não é um sólido fechado "
            f"({count_open} arestas abertas/não-manifold detectadas). "
            "Cortadores sólidos precisam ser volumes 3D perfeitamente estanques."
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
        raise SolidCutterValidationError(f"O cortador '{cutter_obj.name}' possui volume nulo.")

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
                f"O cortador sólido '{cutter_obj.name}' não intercepta o modelo alvo "
                "(as caixas delimitadoras não se tocam). Posicione o cortador sobre o modelo."
            )

    return {
        "valid": True,
        "is_manifold": is_manifold,
        "non_manifold_edges": 0,
        "volume_mm3": vol_mm3,
        "triangles": triangles,
    }


def slice_mesh_by_solid(
    source_mesh: bpy.types.Mesh,
    matrix_world: Matrix,
    cutter_obj: bpy.types.Object,
    target_mesh_a: bpy.types.Mesh,
    target_mesh_b: bpy.types.Mesh,
    invert_sides: bool = False,
    unit_scale: float = 1000.0,
) -> Dict[str, Any]:
    """Corta uma malha pelo cortador sólido gerando Parte A e Parte B fechadas.

    Convenção:
    - Normal (invert_sides=False):
        Parte A = Interseção (Target ∩ Cutter)  [Região interna ao cortador]
        Parte B = Diferença (Target \\ Cutter)  [Região externa ao cortador]
    - Invertido (invert_sides=True):
        Parte A = Diferença (Target \\ Cutter)
        Parte B = Interseção (Target ∩ Cutter)
    """
    if bpy.context and hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

    scene = bpy.context.scene
    temp_col = scene.collection

    # 1. Cria objeto de trabalho temporário para a operação de INTERSECT
    work_mesh_intersect = source_mesh.copy()
    work_obj_intersect = bpy.data.objects.new("temp_work_intersect", work_mesh_intersect)
    work_obj_intersect.matrix_world = matrix_world.copy()
    temp_col.objects.link(work_obj_intersect)

    mod_intersect = work_obj_intersect.modifiers.new(name="Mod_Intersect", type='BOOLEAN')
    mod_intersect.operation = 'INTERSECT'
    mod_intersect.solver = 'EXACT'
    mod_intersect.object = cutter_obj

    # 2. Cria objeto de trabalho temporário para a operação de DIFFERENCE
    work_mesh_diff = source_mesh.copy()
    work_obj_diff = bpy.data.objects.new("temp_work_diff", work_mesh_diff)
    work_obj_diff.matrix_world = matrix_world.copy()
    temp_col.objects.link(work_obj_diff)

    mod_diff = work_obj_diff.modifiers.new(name="Mod_Difference", type='BOOLEAN')
    mod_diff.operation = 'DIFFERENCE'
    mod_diff.solver = 'EXACT'
    mod_diff.object = cutter_obj

    depsgraph = bpy.context.evaluated_depsgraph_get()

    try:
        eval_intersect = work_obj_intersect.evaluated_get(depsgraph)
        eval_mesh_intersect = eval_intersect.to_mesh()

        eval_diff = work_obj_diff.evaluated_get(depsgraph)
        eval_mesh_diff = eval_diff.to_mesh()

        # Atribuição conforme invert_sides
        mesh_part_a = eval_mesh_diff if invert_sides else eval_mesh_intersect
        mesh_part_b = eval_mesh_intersect if invert_sides else eval_mesh_diff

        results = {}

        for side_key, eval_m in [("A", mesh_part_a), ("B", mesh_part_b)]:
            bm = bmesh.new()
            bm.from_mesh(eval_m)
            bm.transform(matrix_world)

            if len(bm.verts) == 0:
                bm.free()
                raise NoIntersectionError(
                    f"O corte sólido não produziu geometria válida para a Parte {side_key}. "
                    "Certifique-se de que o cortador intersecta o modelo adequadamente."
                )

            metrics = evaluate_bmesh_metrics(bm, unit_scale=unit_scale)
            results[side_key] = metrics

            dest_mesh = target_mesh_a if side_key == "A" else target_mesh_b
            dest_mesh.clear_geometry()
            bm.to_mesh(dest_mesh)
            dest_mesh.update()
            bm.free()

        eval_intersect.to_mesh_clear()
        eval_diff.to_mesh_clear()

        results["sum_volume_mm3"] = results["A"]["volume_mm3"] + results["B"]["volume_mm3"]
        return results

    finally:
        for temp_obj in (work_obj_intersect, work_obj_diff):
            t_mesh = temp_obj.data
            temp_col.objects.unlink(temp_obj)
            bpy.data.objects.remove(temp_obj, do_unlink=True)
            if t_mesh and t_mesh.users == 0:
                bpy.data.meshes.remove(t_mesh, do_unlink=True)


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
