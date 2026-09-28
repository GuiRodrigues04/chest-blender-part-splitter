"""Módulo de modelagem geométrica e posicionamento de encaixes (Fase 2).

Gera corpos sólidos de pinos macho (com chanfro de entrada) e cavidades fêmea
(com folga radial por lado e folga de fundo), executando uniões e diferenças
booleanas robustas.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion, Euler

from .constants import (
    CLEARANCE_PRESETS,
)


class ConnectorValidationError(Exception):
    """Exceção para violações de limites geométricos de encaixes."""
    pass


def create_capsule_2d_profile(w: float, half_len: float, segments: int = 32, offset: float = 0.0) -> List[Tuple[float, float]]:
    """Gera pontos 2D fechados e ordenados para o perfil de estádio/cápsula com suporte a offset uniforme de chanfro."""
    pts = []
    half_segs = max(8, segments // 2)
    r = max(1e-5, w - offset)
    # Arco superior: centro (0, half_len), ângulo de 0 a pi
    for i in range(half_segs):
        ang = 0.0 + math.pi * (i / half_segs)
        pts.append((r * math.cos(ang), half_len + r * math.sin(ang)))
    # Arco inferior: centro (0, -half_len), ângulo de pi a 2*pi
    for i in range(half_segs):
        ang = math.pi + math.pi * (i / half_segs)
        pts.append((r * math.cos(ang), -half_len + r * math.sin(ang)))
    return pts


def create_pin_mesh_data(
    name: str,
    connector_type: str,
    diameter: float,
    length: float,
    chamfer: float = 0.8,
    is_cavity: bool = False,
    clearance_side: float = 0.0,
    clearance_end: float = 0.0,
    segments: int = 32,
    capsule_length: float = 0.0,
) -> bpy.types.Mesh:
    """Cria uma malha sólida para o pino macho ou cavidade fêmea.
    
    Convenção de Folga:
    - Macho (is_cavity=False): diâmetro nominal exato, comprimento nominal, chanfro de entrada na ponta.
    - Cavidade (is_cavity=True): diâmetro nominal + 2 * clearance_side, comprimento nominal + clearance_end.
    - Cápsula: comprimento lateral ajustável, com folga uniforme em toda a periferia.
    """
    bm = bmesh.new()

    eff_radius = (diameter / 2.0) + (clearance_side if is_cavity else 0.0)
    eff_length = length + (clearance_end if is_cavity else 0.0)
    eff_chamfer = 0.0 if is_cavity else min(chamfer, eff_length * 0.4, eff_radius * 0.7)

    # Tolerância proporcional de sobreposição na base para garantir operação booleana não coplanar
    base_offset = min(eff_length * 0.05, eff_radius * 0.1)
    z_min = -base_offset
    z_max = eff_length
    z_shoulder = z_max - eff_chamfer

    base_verts = []
    shoulder_verts = []
    tip_verts = []

    if connector_type == 'CAPSULE':
        # Chave tipo cápsula / oblongo (anti-rotação e extensão lateral ajustável):
        w = eff_radius
        if capsule_length <= 0.0:
            eff_cap_len = diameter * 2.4
        else:
            eff_cap_len = max(diameter, capsule_length)
        half_len = (eff_cap_len - diameter) / 2.0

        prof = create_capsule_2d_profile(w, half_len, segments=segments)
        prof_tip = create_capsule_2d_profile(w, half_len, segments=segments, offset=eff_chamfer) if eff_chamfer > 0.0 else []

        for idx, (x, y) in enumerate(prof):
            base_verts.append(bm.verts.new((x, y, z_min)))
            shoulder_verts.append(bm.verts.new((x, y, z_shoulder)))
            if eff_chamfer > 0.0:
                tx, ty = prof_tip[idx]
                tip_verts.append(bm.verts.new((tx, ty, z_max)))

    else:
        # Padrão: Pino Cilíndrico
        tip_r = max(eff_radius * 0.2, eff_radius - eff_chamfer)

        for i in range(segments):
            ang = 2.0 * math.pi * i / segments
            cos_a = math.cos(ang)
            sin_a = math.sin(ang)

            base_verts.append(bm.verts.new((eff_radius * cos_a, eff_radius * sin_a, z_min)))
            shoulder_verts.append(bm.verts.new((eff_radius * cos_a, eff_radius * sin_a, z_shoulder)))
            if eff_chamfer > 0.0:
                tip_verts.append(bm.verts.new((tip_r * cos_a, tip_r * sin_a, z_max)))

    # Face inferior (reversed para apontar normal para -Z)
    bm.faces.new(reversed(base_verts))

    # Paredes laterais
    num_v = len(base_verts)
    for i in range(num_v):
        i_next = (i + 1) % num_v
        bm.faces.new((base_verts[i], base_verts[i_next], shoulder_verts[i_next], shoulder_verts[i]))
        if eff_chamfer > 0.0:
            bm.faces.new((shoulder_verts[i], shoulder_verts[i_next], tip_verts[i_next], tip_verts[i]))

    # Topo (fechamento superior)
    bm.faces.new(tip_verts if eff_chamfer > 0.0 else shoulder_verts)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    mesh_data = bpy.data.meshes.new(name)
    bm.to_mesh(mesh_data)
    bm.free()
    return mesh_data


def compute_connector_layout(
    target_mesh: bpy.types.Mesh,
    matrix_world: Matrix,
    plane_origin: Vector,
    plane_normal: Vector,
    distribution: str = 'CENTER',
    edge_margin_mm: float = 3.0,
    unit_scale: float = 1000.0,
    diameter_mm: float = 6.0,
    clearance_per_side_mm: float = 0.15,
) -> Dict[str, Any]:
    """Calcula posições, eixos de alinhamento e limites seguros para encaixes na interface de corte."""
    bm = bmesh.new()
    bm.from_mesh(target_mesh)
    bm.transform(matrix_world)

    norm = plane_normal.normalized()

    # Executa bisect_plane para obter as arestas exatas da seção de corte
    res = bmesh.ops.bisect_plane(
        bm,
        geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        plane_co=plane_origin,
        plane_no=norm,
        clear_outer=False,
        clear_inner=False,
    )

    cut_edges = [e for e in res.get("geom_cut", []) if isinstance(e, bmesh.types.BMEdge)]
    cut_pts = [v.co.copy() for e in cut_edges for v in e.verts]
    bm.free()

    ref_up = Vector((0, 0, 1)) if abs(norm.z) < 0.9 else Vector((0, 1, 0))
    u_axis = norm.cross(ref_up).normalized()
    v_axis = norm.cross(u_axis).normalized()

    if not cut_pts:
        return {
            "positions": [plane_origin.copy()],
            "major_axis": u_axis,
            "minor_axis": v_axis,
            "span_major_mm": diameter_mm * 2.0,
            "span_minor_mm": diameter_mm * 2.0,
            "min_pitch_mm": 0.0,
            "pitch_limit_mm": 1e9,
            "edge_limit_mm": diameter_mm * 2.0,
            "max_safe_lateral_mm": diameter_mm * 2.0,
        }

    # Projeta os pontos no sistema UV local
    u_coords = [(p - plane_origin).dot(u_axis) for p in cut_pts]
    v_coords = [(p - plane_origin).dot(v_axis) for p in cut_pts]

    min_u, max_u = min(u_coords), max(u_coords)
    min_v, max_v = min(v_coords), max(v_coords)

    center_u = (min_u + max_u) / 2.0
    center_v = (min_v + max_v) / 2.0
    span_u = max_u - min_u
    span_v = max_v - min_v

    margin_bu = edge_margin_mm / unit_scale
    avail_u = max(0.0, (span_u / 2.0) - margin_bu)
    avail_v = max(0.0, (span_v / 2.0) - margin_bu)

    positions = []
    if span_u >= span_v:
        major_axis = u_axis
        minor_axis = v_axis
        span_major = span_u
        span_minor = span_v
    else:
        major_axis = v_axis
        minor_axis = u_axis
        span_major = span_v
        span_minor = span_u

    if distribution == 'CENTER' or (avail_u < 1e-4 and avail_v < 1e-4):
        p = plane_origin + (u_axis * center_u) + (v_axis * center_v)
        positions.append(p)

    elif distribution == 'LINEAR_2':
        # Alinha ao longo do eixo de maior vão
        if span_u >= span_v:
            d_u = avail_u * 0.6
            p1 = plane_origin + (u_axis * (center_u - d_u)) + (v_axis * center_v)
            p2 = plane_origin + (u_axis * (center_u + d_u)) + (v_axis * center_v)
        else:
            d_v = avail_v * 0.6
            p1 = plane_origin + (u_axis * center_u) + (v_axis * (center_v - d_v))
            p2 = plane_origin + (u_axis * center_u) + (v_axis * (center_v + d_v))
        positions.extend([p1, p2])

    elif distribution == 'LINEAR_3':
        positions.append(plane_origin + (u_axis * center_u) + (v_axis * center_v))
        if span_u >= span_v:
            d_u = avail_u * 0.7
            p1 = plane_origin + (u_axis * (center_u - d_u)) + (v_axis * center_v)
            p2 = plane_origin + (u_axis * (center_u + d_u)) + (v_axis * center_v)
        else:
            d_v = avail_v * 0.7
            p1 = plane_origin + (u_axis * center_u) + (v_axis * (center_v - d_v))
            p2 = plane_origin + (u_axis * center_u) + (v_axis * (center_v + d_v))
        positions.extend([p1, p2])

    elif distribution == 'GRID_4':
        d_u = avail_u * 0.55
        d_v = avail_v * 0.55
        p1 = plane_origin + (u_axis * (center_u - d_u)) + (v_axis * (center_v - d_v))
        p2 = plane_origin + (u_axis * (center_u + d_u)) + (v_axis * (center_v - d_v))
        p3 = plane_origin + (u_axis * (center_u - d_u)) + (v_axis * (center_v + d_v))
        p4 = plane_origin + (u_axis * (center_u + d_u)) + (v_axis * (center_v + d_v))
        positions.extend([p1, p2, p3, p4])

    span_major_mm = span_major * unit_scale
    span_minor_mm = span_minor * unit_scale

    # Cálculo dos limites coerentes de tamanho lateral
    min_pitch_mm = 1e9
    if len(positions) >= 2:
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dist = (positions[i] - positions[j]).length * unit_scale
                if dist < min_pitch_mm:
                    min_pitch_mm = dist
        # Limite entre encaixes: deixa parede sólida mínima de 2.0 mm entre cavidades
        pitch_limit_mm = max(diameter_mm, min_pitch_mm - (2.0 * clearance_per_side_mm) - 2.0)
    else:
        min_pitch_mm = 0.0
        pitch_limit_mm = 1e9

    if len(positions) == 1:
        edge_limit_mm = max(diameter_mm, span_major_mm - (2.0 * edge_margin_mm))
    else:
        center_pos = sum(positions, Vector()) / len(positions)
        max_dist_center_mm = max((p - center_pos).length * unit_scale for p in positions)
        avail_outer_mm = (span_major_mm / 2.0) - max_dist_center_mm
        edge_limit_mm = max(diameter_mm, 2.0 * max(diameter_mm / 2.0, avail_outer_mm - edge_margin_mm))

    max_safe_lateral_mm = round(min(pitch_limit_mm, edge_limit_mm), 1)

    return {
        "positions": positions,
        "major_axis": major_axis,
        "minor_axis": minor_axis,
        "span_major_mm": span_major_mm,
        "span_minor_mm": span_minor_mm,
        "min_pitch_mm": min_pitch_mm,
        "pitch_limit_mm": pitch_limit_mm,
        "edge_limit_mm": edge_limit_mm,
        "max_safe_lateral_mm": max_safe_lateral_mm,
    }


def compute_connector_positions(
    target_mesh: bpy.types.Mesh,
    matrix_world: Matrix,
    plane_origin: Vector,
    plane_normal: Vector,
    distribution: str = 'CENTER',
    edge_margin_mm: float = 3.0,
    unit_scale: float = 1000.0,
) -> List[Vector]:
    """Calcula os pontos 3D na interface do corte para os encaixes (mantém compatibilidade)."""
    layout = compute_connector_layout(
        target_mesh=target_mesh,
        matrix_world=matrix_world,
        plane_origin=plane_origin,
        plane_normal=plane_normal,
        distribution=distribution,
        edge_margin_mm=edge_margin_mm,
        unit_scale=unit_scale,
    )
    return layout["positions"]


def validate_connectors(
    positions: List[Vector],
    diameter_mm: float,
    clearance_per_side_mm: float,
    unit_scale: float = 1000.0,
    connector_type: str = 'CYLINDER',
    capsule_length_mm: float = 0.0,
):
    """Verifica se há sobreposição entre múltiplos encaixes."""
    eff_length = capsule_length_mm if (connector_type == 'CAPSULE' and capsule_length_mm > diameter_mm) else diameter_mm
    min_dist_bu = (eff_length + 2.0 * clearance_per_side_mm) / unit_scale

    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            dist = (positions[i] - positions[j]).length
            if dist < min_dist_bu:
                dist_mm = dist * unit_scale
                req_mm = eff_length + 2.0 * clearance_per_side_mm
                raise ConnectorValidationError(
                    f"Sobreposição entre encaixes detectada: distância {dist_mm:.2f} mm < mínimo {req_mm:.2f} mm."
                )


def apply_connectors_boolean(
    obj_male: bpy.types.Object,
    obj_female: bpy.types.Object,
    plane_normal: Vector,
    positions: List[Vector],
    connector_type: str,
    diameter_mm: float,
    length_mm: float,
    chamfer_mm: float,
    clearance_side_mm: float,
    end_clearance_mm: float,
    unit_scale: float = 1000.0,
    capsule_length_mm: float = 0.0,
    major_axis: Optional[Vector] = None,
):
    """Executa as operações booleanas para unir os machos e subtrair as cavidades."""
    norm = plane_normal.normalized()

    # Determina o eixo maior (direção de alinhamento das cápsulas no plano de corte)
    if major_axis is None:
        if len(positions) >= 2:
            delta = positions[1] - positions[0]
            delta_proj = delta - norm * delta.dot(norm)
            if delta_proj.length > 1e-6:
                major_axis = delta_proj.normalized()
        if major_axis is None:
            ref_up = Vector((0, 0, 1)) if abs(norm.z) < 0.9 else Vector((0, 1, 0))
            major_axis = norm.cross(ref_up).normalized()

    # Constrói sistema ortonormal estável: local_z = norm, local_y = major_axis, local_x = local_y x local_z
    local_z = norm.normalized()
    local_y = (major_axis - local_z * major_axis.dot(local_z)).normalized()
    local_x = local_y.cross(local_z).normalized()
    rot_mat = Matrix((local_x, local_y, local_z)).transposed()
    pin_rot = rot_mat.to_euler()

    cutters_to_clean = []

    # Cria coleção temporária de corte se necessário
    temp_col = obj_male.users_collection[0] if obj_male.users_collection else bpy.context.scene.collection

    diam_bu = diameter_mm / unit_scale
    len_bu = length_mm / unit_scale
    chamf_bu = chamfer_mm / unit_scale
    clear_side_bu = clearance_side_mm / unit_scale
    clear_end_bu = end_clearance_mm / unit_scale
    cap_len_bu = (capsule_length_mm / unit_scale) if capsule_length_mm > 0 else 0.0

    # 1. Aplica machos (UNION) no obj_male
    for idx, pos in enumerate(positions):
        pin_mesh = create_pin_mesh_data(
            name=f"temp_pin_{idx}",
            connector_type=connector_type,
            diameter=diam_bu,
            length=len_bu,
            chamfer=chamf_bu,
            is_cavity=False,
            capsule_length=cap_len_bu,
        )
        pin_obj = bpy.data.objects.new(f"temp_pin_{idx}", pin_mesh)
        # Sincroniza materiais no pino para que a união booleana preserve o material
        for mat in obj_male.data.materials:
            pin_mesh.materials.append(mat)
        pin_obj.location = pos
        pin_obj.rotation_euler = pin_rot
        temp_col.objects.link(pin_obj)
        cutters_to_clean.append(pin_obj)

        mod_union = obj_male.modifiers.new(name=f"Pin_Union_{idx}", type='BOOLEAN')
        mod_union.operation = 'UNION'
        mod_union.solver = 'EXACT'
        mod_union.object = pin_obj

    # 2. Aplica cavidades (DIFFERENCE) no obj_female
    for idx, pos in enumerate(positions):
        cavity_mesh = create_pin_mesh_data(
            name=f"temp_cavity_{idx}",
            connector_type=connector_type,
            diameter=diam_bu,
            length=len_bu,
            chamfer=0.0,
            is_cavity=True,
            clearance_side=clear_side_bu,
            clearance_end=clear_end_bu,
            capsule_length=cap_len_bu,
        )
        cavity_obj = bpy.data.objects.new(f"temp_cavity_{idx}", cavity_mesh)
        # Sincroniza materiais na cavidade para que a diferença booleana herde o material
        for mat in obj_female.data.materials:
            cavity_mesh.materials.append(mat)
        cavity_obj.location = pos
        cavity_obj.rotation_euler = pin_rot
        temp_col.objects.link(cavity_obj)
        cutters_to_clean.append(cavity_obj)

        mod_diff = obj_female.modifiers.new(name=f"Cavity_Diff_{idx}", type='BOOLEAN')
        mod_diff.operation = 'DIFFERENCE'
        mod_diff.solver = 'EXACT'
        mod_diff.object = cavity_obj

    # Avalia os modificadores e consolida as malhas
    depsgraph = bpy.context.evaluated_depsgraph_get()

    for obj in (obj_male, obj_female):
        eval_obj = obj.evaluated_get(depsgraph)
        new_mesh = eval_obj.to_mesh()

        # Substitui a malha do objeto pelo resultado avaliado
        old_mesh = obj.data
        final_mesh = new_mesh.copy()
        obj.data = final_mesh
        eval_obj.to_mesh_clear()

        # Remove modificadores já processados
        obj.modifiers.clear()

        # Remove eventuais slots vazios (None) adicionados pela operação booleana
        empty_slots = [i for i, m in enumerate(obj.data.materials) if m is None]
        for i in reversed(empty_slots):
            obj.data.materials.pop(index=i)

        if old_mesh and old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh, do_unlink=True)

    # Limpa objetos e malhas auxiliares de corte
    for cutter in cutters_to_clean:
        c_mesh = cutter.data
        temp_col.objects.unlink(cutter)
        bpy.data.objects.remove(cutter, do_unlink=True)
        if c_mesh and c_mesh.users == 0:
            bpy.data.meshes.remove(c_mesh, do_unlink=True)
