"""Módulo de modelagem geométrica e posicionamento de encaixes (Fase 2).

Gera corpos sólidos de pinos macho (com chanfro de entrada) e cavidades fêmea
(com folga radial por lado e folga de fundo), executando uniões e diferenças
booleanas transacionais e robustas.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion, Euler
from mathutils.bvhtree import BVHTree

from .constants import (
    CLEARANCE_PRESETS,
)


class ConnectorValidationError(Exception):
    """Exceção para violações de limites geométricos de encaixes."""
    pass


def point_in_polygon_2d(x: float, y: float, poly: List[Tuple[float, float]]) -> bool:
    """Teste de inclusão de ponto 2D em polígono via Ray Casting (Teorema de Jordan)."""
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def create_capsule_2d_profile(w: float, half_len: float, segments: int = 32, offset: float = 0.0) -> List[Tuple[float, float]]:
    """Gera pontos 2D fechados e ordenados para o perfil de estádio/cápsula com suporte a offset uniforme.
    
    Inclui os pontos finais de tangência para que os lados retos sejam estritamente paralelos,
    garantindo folga perimetral uniforme sem segmentos diagonais indevidos.
    """
    half_segs = max(8, segments // 2)
    r = max(1e-5, w - offset)
    if half_len < 1e-6:
        # Círculo perfeito
        return [(r * math.cos(2.0 * math.pi * i / segments), r * math.sin(2.0 * math.pi * i / segments)) for i in range(segments)]

    pts = []
    # Arco superior: centro (0, half_len), ângulo de 0 a pi (incluindo extremos tangentes)
    for i in range(half_segs + 1):
        ang = math.pi * (i / half_segs)
        pts.append((r * math.cos(ang), half_len + r * math.sin(ang)))
    # Arco inferior: centro (0, -half_len), ângulo de pi a 2*pi (incluindo extremos tangentes)
    for i in range(half_segs + 1):
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
    
    Convenção Dimensional Estrita:
    - Macho (is_cavity=False): diâmetro D, comprimento lateral L, projeção útil length, chanfro na ponta.
    - Cavidade (is_cavity=True): diâmetro D + 2*clearance_side, comprimento L + 2*clearance_side,
      profundidade útil length + clearance_end, sem chanfro automático.
    - Separação entre centros dos semicírculos da cápsula: exatamente L - D em macho e cavidade.
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
        # Chave tipo cápsula / estádio
        w = eff_radius
        eff_cap_len = max(diameter, capsule_length) if capsule_length > 0.0 else (diameter * 2.4)
        # Centros dos semicírculos ficam separados por L - D
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

    # Face inferior (aponta para -Z)
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


def check_receiving_wall_thickness(
    obj_female: bpy.types.Object,
    positions: List[Vector],
    normal: Vector,
    required_depth_bu: float,
    min_wall_bu: float = 1e-4,
    cavity_radius_bu: float = 0.0,
) -> Tuple[bool, float]:
    """Verifica se a cavidade de inserção atravessaria a parede da peça receptora (Defeito C5).
    
    Amostra o centro e pontos perimétricos para detectar paredes inclinadas ou perfurações
    indesejadas em quinas e superfícies curvas.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj_female.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    try:
        bm = bmesh.new()
        bm.from_mesh(eval_mesh)
        bm.transform(obj_female.matrix_world)
        bvh = BVHTree.FromBMesh(bm)
        norm = normal.normalized()

        # Vetores perpendiculares no plano de corte para amostragem perimétrica
        ref = Vector((1.0, 0.0, 0.0))
        if abs(norm.dot(ref)) > 0.9:
            ref = Vector((0.0, 1.0, 0.0))
        u_dir = norm.cross(ref).normalized()
        v_dir = norm.cross(u_dir).normalized()

        sample_offsets = [Vector((0.0, 0.0, 0.0))]
        if cavity_radius_bu > 1e-5:
            r = cavity_radius_bu * 0.95
            sample_offsets.extend([
                u_dir * r,
                -u_dir * r,
                v_dir * r,
                -v_dir * r,
            ])

        min_found_depth = 1e9

        for pos in positions:
            for offset in sample_offsets:
                sample_p = pos + offset
                ray_start = sample_p + norm * 1e-4
                hit_loc, hit_norm, hit_idx, hit_dist = bvh.ray_cast(ray_start, norm)
                if hit_loc is None:
                    # Raio sem interseção: não há parede receptora na direção de inserção
                    bm.free()
                    return False, 0.0

                avail_depth = (hit_loc - sample_p).length
                if avail_depth < min_found_depth:
                    min_found_depth = avail_depth

                if avail_depth < (required_depth_bu + min_wall_bu):
                    bm.free()
                    return False, avail_depth

        bm.free()
        return True, min_found_depth if min_found_depth < 1e8 else 0.0
    finally:
        eval_obj.to_mesh_clear()



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
    interface: Optional[Any] = None,
    connector_type: str = 'CYLINDER',
    capsule_length_mm: float = 0.0,
) -> Dict[str, Any]:
    """Calcula posições, eixos de alinhamento e limites seguros para encaixes na interface de corte."""
    outer_polys = []
    hole_polys = []

    if interface is not None and getattr(interface, "outer_contours_uv", None) and interface.outer_contours_uv:
        plane_origin = interface.origin_world
        norm = interface.normal_a_to_b_world.normalized()
        u_axis = interface.axis_u_world
        v_axis = interface.axis_v_world
        outer_polys = interface.outer_contours_uv
        hole_polys = getattr(interface, "hole_contours_uv", []) or []
        u_coords = [pt[0] for poly in outer_polys for pt in poly]
        v_coords = [pt[1] for poly in outer_polys for pt in poly]
        cut_pts = [interface.uv_to_world(pt[0], pt[1]) for poly in outer_polys for pt in poly]
    else:
        bm = bmesh.new()
        bm.from_mesh(target_mesh)
        bm.transform(matrix_world)

        norm = plane_normal.normalized()

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
            raise ConnectorValidationError("Nenhuma interface de corte válida encontrada para posicionamento de encaixes.")

        u_coords = [(p - plane_origin).dot(u_axis) for p in cut_pts]
        v_coords = [(p - plane_origin).dot(v_axis) for p in cut_pts]

    min_u, max_u = min(u_coords), max(u_coords)
    min_v, max_v = min(v_coords), max(v_coords)

    center_u = (min_u + max_u) / 2.0
    center_v = (min_v + max_v) / 2.0
    span_u = max_u - min_u
    span_v = max_v - min_v

    if span_u >= span_v:
        major_axis = u_axis
        minor_axis = v_axis
        span_major = span_u
        span_minor = span_v
        center_major = center_u
        center_minor = center_v
    else:
        major_axis = v_axis
        minor_axis = u_axis
        span_major = span_v
        span_minor = span_u
        center_major = center_v
        center_minor = center_u

    span_major_mm = span_major * unit_scale
    span_minor_mm = span_minor * unit_scale

    # Validação de espaço mínimo admissível para o perfil base (Critério C1)
    cavity_diam_mm = diameter_mm + 2.0 * clearance_per_side_mm
    req_min_span_mm = cavity_diam_mm + 2.0 * edge_margin_mm

    if span_minor_mm < req_min_span_mm - 1e-3 or span_major_mm < req_min_span_mm - 1e-3:
        raise ConnectorValidationError(
            f"Falta de espaço: a interface ({span_major_mm:.1f}x{span_minor_mm:.1f} mm) não comporta o encaixe "
            f"com margem de {edge_margin_mm:.1f} mm (necessário ao menos {req_min_span_mm:.1f}x{req_min_span_mm:.1f} mm)."
        )

    margin_bu = edge_margin_mm / unit_scale
    avail_major = max(0.0, (span_major / 2.0) - margin_bu)
    avail_minor = max(0.0, (span_minor / 2.0) - margin_bu)

    positions = []

    # Validação de distribuições múltiplas (Critério C4: sem redução silenciosa)
    if distribution == 'CENTER':
        p = plane_origin + (u_axis * center_u) + (v_axis * center_v)
        positions.append(p)

    elif distribution == 'LINEAR_2':
        min_span_linear2 = 2.0 * cavity_diam_mm + 2.0 * edge_margin_mm + 2.0
        if span_major_mm < min_span_linear2:
            raise ConnectorValidationError(
                f"Falta de espaço: a distribuição LINEAR_2 requer vão de ao menos {min_span_linear2:.1f} mm "
                f"(disponível: {span_major_mm:.1f} mm). Reduza a quantidade ou medidas dos encaixes."
            )
        d_major = avail_major * 0.6
        p1 = plane_origin + (major_axis * (center_major - d_major)) + (minor_axis * center_minor)
        p2 = plane_origin + (major_axis * (center_major + d_major)) + (minor_axis * center_minor)
        positions.extend([p1, p2])

    elif distribution == 'LINEAR_3':
        min_span_linear3 = 3.0 * cavity_diam_mm + 2.0 * edge_margin_mm + 4.0
        if span_major_mm < min_span_linear3:
            raise ConnectorValidationError(
                f"Falta de espaço: a distribuição LINEAR_3 requer vão de ao menos {min_span_linear3:.1f} mm "
                f"(disponível: {span_major_mm:.1f} mm). Reduza a quantidade ou medidas dos encaixes."
            )
        p_mid = plane_origin + (major_axis * center_major) + (minor_axis * center_minor)
        d_major = avail_major * 0.7
        p1 = plane_origin + (major_axis * (center_major - d_major)) + (minor_axis * center_minor)
        p2 = plane_origin + (major_axis * (center_major + d_major)) + (minor_axis * center_minor)
        positions.extend([p_mid, p1, p2])

    elif distribution == 'GRID_4':
        min_grid_major = 2.0 * cavity_diam_mm + 2.0 * edge_margin_mm + 2.0
        min_grid_minor = 2.0 * cavity_diam_mm + 2.0 * edge_margin_mm + 2.0
        if span_major_mm < min_grid_major or span_minor_mm < min_grid_minor:
            raise ConnectorValidationError(
                f"Falta de espaço: a distribuição GRID_4 requer ao menos {min_grid_major:.1f}x{min_grid_minor:.1f} mm "
                f"(disponível: {span_major_mm:.1f}x{span_minor_mm:.1f} mm). Reduza a quantidade ou medidas dos encaixes."
            )
        d_u = (span_u / 2.0 - margin_bu) * 0.55
        d_v = (span_v / 2.0 - margin_bu) * 0.55
        p1 = plane_origin + (u_axis * (center_u - d_u)) + (v_axis * (center_v - d_v))
        p2 = plane_origin + (u_axis * (center_u + d_u)) + (v_axis * (center_v - d_v))
        p3 = plane_origin + (u_axis * (center_u - d_u)) + (v_axis * (center_v + d_v))
        p4 = plane_origin + (u_axis * (center_u + d_u)) + (v_axis * (center_v + d_v))
        positions.extend([p1, p2, p3, p4])

    # Cálculo dos limites laterais seguros para cápsula
    min_pitch_mm = 1e9
    if len(positions) >= 2:
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dist = (positions[i] - positions[j]).length * unit_scale
                if dist < min_pitch_mm:
                    min_pitch_mm = dist
        pitch_limit_mm = max(diameter_mm, min_pitch_mm - (2.0 * clearance_per_side_mm + 2.0))
    else:
        pitch_limit_mm = 1e9

    if len(positions) == 1:
        edge_limit_mm = max(diameter_mm, span_major_mm - (2.0 * edge_margin_mm + 2.0 * clearance_per_side_mm))
    else:
        center_pos = sum(positions, Vector()) / len(positions)
        max_dist_center_mm = max((p - center_pos).length * unit_scale for p in positions)
        avail_outer_mm = (span_major_mm / 2.0) - max_dist_center_mm
        edge_limit_mm = max(diameter_mm, 2.0 * max(diameter_mm / 2.0, avail_outer_mm - (edge_margin_mm + clearance_per_side_mm)))

    max_safe_lateral_mm = round(min(pitch_limit_mm, edge_limit_mm), 1)

    adjusted_cap_len_mm = capsule_length_mm
    capsule_was_adjusted = False
    if connector_type == 'CAPSULE':
        if capsule_length_mm <= 0.0 or capsule_length_mm > max_safe_lateral_mm:
            adjusted_cap_len_mm = max_safe_lateral_mm
            capsule_was_adjusted = (capsule_length_mm > 0.0 and adjusted_cap_len_mm != capsule_length_mm)

        cavity_cap_len_mm = adjusted_cap_len_mm + 2.0 * clearance_per_side_mm
        req_major_mm = cavity_cap_len_mm + 2.0 * edge_margin_mm
        if span_major_mm < req_major_mm - 1e-3:
            raise ConnectorValidationError(
                f"Falta de espaço: a interface ({span_major_mm:.1f} mm) não comporta a cápsula "
                f"com margem de {edge_margin_mm:.1f} mm (necessário ao menos {req_major_mm:.1f} mm)."
            )

    # Validação rigorosa de inclusão do perfil completo no domínio sólido da interface (B04/B05)
    if outer_polys:
        check_r = (diameter_mm / 2.0 + clearance_per_side_mm + edge_margin_mm) / unit_scale
        u_proj = major_axis.dot(u_axis)
        v_proj = major_axis.dot(v_axis)
        rot_ang = math.atan2(v_proj, u_proj)
        cos_rot = math.cos(rot_ang)
        sin_rot = math.sin(rot_ang)

        for idx, pos in enumerate(positions):
            u_p = (pos - plane_origin).dot(u_axis)
            v_p = (pos - plane_origin).dot(v_axis)

            test_pts = [(u_p, v_p)]
            if connector_type == 'CAPSULE':
                eff_cap = max(diameter_mm, adjusted_cap_len_mm) if adjusted_cap_len_mm > 0.0 else (diameter_mm * 2.4)
                half_len = max(0.0, (eff_cap - diameter_mm) / 2.0) / unit_scale
                prof = create_capsule_2d_profile(w=check_r, half_len=half_len, segments=24)
                # No perfil da cápsula: Y (ly) é o eixo de alongamento (major_axis) e X (lx) é a largura (minor_axis)
                # major_axis no plano UV é (cos_rot, sin_rot), minor_axis é (-sin_rot, cos_rot)
                for lx, ly in prof:
                    test_pts.append((
                        u_p + ly * cos_rot - lx * sin_rot,
                        v_p + ly * sin_rot + lx * cos_rot,
                    ))
            else:
                for ang_idx in range(16):
                    ang = 2.0 * math.pi * ang_idx / 16.0
                    test_pts.append((u_p + check_r * math.cos(ang), v_p + check_r * math.sin(ang)))

            for tp in test_pts:
                in_any_outer = any(point_in_polygon_2d(tp[0], tp[1], poly) for poly in outer_polys)
                if not in_any_outer:
                    raise ConnectorValidationError(
                        f"O encaixe #{idx+1} ultrapassa a margem de segurança de {edge_margin_mm:.1f} mm "
                        f"ou cai fora do domínio sólido da peça."
                    )
                for hole_poly in hole_polys:
                    if point_in_polygon_2d(tp[0], tp[1], hole_poly):
                        raise ConnectorValidationError(
                            f"O encaixe #{idx+1} invade um furo/vazio interno da interface."
                        )

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
        "adjusted_capsule_length_mm": adjusted_cap_len_mm,
        "capsule_was_adjusted": capsule_was_adjusted,
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
    """Calcula os pontos 3D na interface do corte para os encaixes (retrocompatibilidade)."""
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
    obj_female: Optional[bpy.types.Object] = None,
    normal: Optional[Vector] = None,
    length_mm: float = 0.0,
    end_clearance_mm: float = 0.0,
):
    """Valida distâncias entre encaixes e espessura de parede remanescente na peça receptora."""
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

    # Validação de espessura de parede da peça receptora (Critério C5)
    if obj_female is not None and normal is not None and length_mm > 0.0:
        req_depth_bu = (length_mm + end_clearance_mm) / unit_scale
        cavity_r_bu = ((diameter_mm / 2.0) + clearance_per_side_mm) / unit_scale
        ok, avail = check_receiving_wall_thickness(
            obj_female,
            positions,
            normal,
            req_depth_bu,
            cavity_radius_bu=cavity_r_bu,
        )
        if not ok:
            avail_mm = avail * unit_scale
            tot_depth_mm = length_mm + end_clearance_mm
            if avail <= 1e-6:
                raise ConnectorValidationError(
                    "Parede receptora inválida ou ausente: a cavidade não encontra corpo sólido suficiente "
                    "na direção de inserção. Verifique a orientação ou integridade da peça receptora."
                )
            else:
                raise ConnectorValidationError(
                    f"Parede fina: a cavidade de {tot_depth_mm:.1f} mm atravessaria a peça receptora "
                    f"(espessura disponível: {avail_mm:.1f} mm). Reduza o comprimento de inserção."
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
    """Executa as operações booleanas para unir os machos e subtrair as cavidades de forma transacional."""
    norm = plane_normal.normalized()

    # Validação prévia de espessura de parede da peça receptora
    validate_connectors(
        positions=positions,
        diameter_mm=diameter_mm,
        clearance_per_side_mm=clearance_side_mm,
        unit_scale=unit_scale,
        connector_type=connector_type,
        capsule_length_mm=capsule_length_mm,
        obj_female=obj_female,
        normal=norm,
        length_mm=length_mm,
        end_clearance_mm=end_clearance_mm,
    )

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
    modifiers_male_added = []
    modifiers_female_added = []

    temp_col = obj_male.users_collection[0] if obj_male.users_collection else bpy.context.scene.collection

    diam_bu = diameter_mm / unit_scale
    len_bu = length_mm / unit_scale
    chamf_bu = chamfer_mm / unit_scale
    clear_side_bu = clearance_side_mm / unit_scale
    clear_end_bu = end_clearance_mm / unit_scale
    cap_len_bu = (capsule_length_mm / unit_scale) if capsule_length_mm > 0 else 0.0

    try:
        # 1. Cria pinos para obj_male
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
            for mat in obj_male.data.materials:
                pin_mesh.materials.append(mat)
            pin_obj.location = pos
            pin_obj.rotation_euler = pin_rot
            temp_col.objects.link(pin_obj)
            cutters_to_clean.append(pin_obj)

            mod_name = f"Pin_Union_{idx}"
            mod_union = obj_male.modifiers.new(name=mod_name, type='BOOLEAN')
            mod_union.operation = 'UNION'
            mod_union.solver = 'EXACT'
            mod_union.object = pin_obj
            modifiers_male_added.append(mod_name)

        # 2. Cria cavidades para obj_female
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
            for mat in obj_female.data.materials:
                cavity_mesh.materials.append(mat)
            cavity_obj.location = pos
            cavity_obj.rotation_euler = pin_rot
            temp_col.objects.link(cavity_obj)
            cutters_to_clean.append(cavity_obj)

            mod_name = f"Cavity_Diff_{idx}"
            mod_diff = obj_female.modifiers.new(name=mod_name, type='BOOLEAN')
            mod_diff.operation = 'DIFFERENCE'
            mod_diff.solver = 'EXACT'
            mod_diff.object = cavity_obj
            modifiers_female_added.append(mod_name)

        # Atualiza a view layer para garantir avaliação correta
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()

        eval_male = obj_male.evaluated_get(depsgraph)
        new_male_mesh = eval_male.to_mesh()

        eval_female = obj_female.evaluated_get(depsgraph)
        new_female_mesh = eval_female.to_mesh()

        try:
            # Validação de integridade das malhas avaliadas
            if len(new_male_mesh.polygons) == 0 or len(new_female_mesh.polygons) == 0:
                raise RuntimeError("Operação booleana de encaixe gerou malha vazia ou corrompida.")

            # Transfere malhas avaliadas em definitivo
            old_mesh_male = obj_male.data
            final_male = new_male_mesh.copy()
            obj_male.data = final_male

            old_mesh_female = obj_female.data
            final_female = new_female_mesh.copy()
            obj_female.data = final_female
        finally:
            eval_male.to_mesh_clear()
            eval_female.to_mesh_clear()

        # Remove slots de material vazios
        for obj in (obj_male, obj_female):
            empty_slots = [i for i, m in enumerate(obj.data.materials) if m is None]
            for i in reversed(empty_slots):
                obj.data.materials.pop(index=i)

        if old_mesh_male and old_mesh_male.users == 0:
            bpy.data.meshes.remove(old_mesh_male, do_unlink=True)
        if old_mesh_female and old_mesh_female.users == 0:
            bpy.data.meshes.remove(old_mesh_female, do_unlink=True)

    finally:
        # Garante remoção dos modificadores adicionados (sem tocar nos modificadores do usuário)
        for mod_name in modifiers_male_added:
            mod = obj_male.modifiers.get(mod_name)
            if mod:
                obj_male.modifiers.remove(mod)

        for mod_name in modifiers_female_added:
            mod = obj_female.modifiers.get(mod_name)
            if mod:
                obj_female.modifiers.remove(mod)

        # Limpa objetos e malhas auxiliares de corte
        for cutter in cutters_to_clean:
            c_mesh = cutter.data
            if cutter.name in temp_col.objects:
                temp_col.objects.unlink(cutter)
            if cutter.name in bpy.data.objects:
                bpy.data.objects.remove(cutter, do_unlink=True)
            if c_mesh and c_mesh.users == 0:
                bpy.data.meshes.remove(c_mesh, do_unlink=True)
