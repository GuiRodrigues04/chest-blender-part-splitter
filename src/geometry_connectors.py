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
) -> bpy.types.Mesh:
    """Cria uma malha sólida para o pino macho ou cavidade fêmea.
    
    Convenção de Folga:
    - Macho (is_cavity=False): diâmetro nominal exato, comprimento nominal, chanfro de entrada na ponta.
    - Cavidade (is_cavity=True): diâmetro nominal + 2 * clearance_side, comprimento nominal + clearance_end.
    """
    bm = bmesh.new()

    eff_radius = (diameter / 2.0) + (clearance_side if is_cavity else 0.0)
    eff_length = length + (clearance_end if is_cavity else 0.0)
    eff_chamfer = 0.0 if is_cavity else min(chamfer, eff_length * 0.4, eff_radius * 0.7)

    # Tolerância de sobreposição na base para garantir operação booleana não coplanar
    base_offset = 0.5  # milímetros para dentro/fora da interface
    z_min = -base_offset
    z_max = eff_length

    if connector_type == 'CAPSULE':
        # Chave tipo cápsula / oblongo (anti-rotação):
        # Largura = 2 * eff_radius, Comprimento = 3 * eff_radius
        w = eff_radius
        aspect = 1.8  # proporção oblonga
        half_len = w * aspect

        # Gera cilindro achatado ou prisma com extremidades arredondadas
        z_shoulder = z_max - eff_chamfer
        tip_r = max(0.2, w - eff_chamfer)

        # Base loop
        base_verts = []
        shoulder_verts = []
        tip_verts = []

        half_segs = segments // 2
        # Semicírculo positivo em Y
        for i in range(half_segs + 1):
            ang = -math.pi / 2.0 + math.pi * (i / half_segs)
            x = w * math.cos(ang)
            y = half_len + w * math.sin(ang)
            base_verts.append(bm.verts.new((x, y, z_min)))
            shoulder_verts.append(bm.verts.new((x, y, z_shoulder)))
            tip_verts.append(bm.verts.new((tip_r * math.cos(ang), half_len + tip_r * math.sin(ang), z_max)))

        # Semicírculo negativo em Y
        for i in range(half_segs + 1):
            ang = math.pi / 2.0 + math.pi * (i / half_segs)
            x = w * math.cos(ang)
            y = -half_len + w * math.sin(ang)
            base_verts.append(bm.verts.new((x, y, z_min)))
            shoulder_verts.append(bm.verts.new((x, y, z_shoulder)))
            tip_verts.append(bm.verts.new((tip_r * math.cos(ang), -half_len + tip_r * math.sin(ang), z_max)))

        # Fecha base e topo
        bm.faces.new(reversed(base_verts))
        num_v = len(base_verts)
        for i in range(num_v):
            i_next = (i + 1) % num_v
            bm.faces.new((base_verts[i], base_verts[i_next], shoulder_verts[i_next], shoulder_verts[i]))
            if eff_chamfer > 0.0:
                bm.faces.new((shoulder_verts[i], shoulder_verts[i_next], tip_verts[i_next], tip_verts[i]))
        bm.faces.new(tip_verts if eff_chamfer > 0.0 else shoulder_verts)

    else:
        # Padrão: Pino Cilíndrico
        z_shoulder = z_max - eff_chamfer
        tip_r = max(0.2, eff_radius - eff_chamfer)

        base_verts = []
        shoulder_verts = []
        tip_verts = []

        for i in range(segments):
            ang = 2.0 * math.pi * i / segments
            cos_a = math.cos(ang)
            sin_a = math.sin(ang)

            base_verts.append(bm.verts.new((eff_radius * cos_a, eff_radius * sin_a, z_min)))
            shoulder_verts.append(bm.verts.new((eff_radius * cos_a, eff_radius * sin_a, z_shoulder)))
            if eff_chamfer > 0.0:
                tip_verts.append(bm.verts.new((tip_r * cos_a, tip_r * sin_a, z_max)))

        # Face inferior
        bm.faces.new(reversed(base_verts))

        # Laterais cilíndricas
        for i in range(segments):
            i_next = (i + 1) % segments
            bm.faces.new((base_verts[i], base_verts[i_next], shoulder_verts[i_next], shoulder_verts[i]))

        # Chanfro e topo
        if eff_chamfer > 0.0:
            for i in range(segments):
                i_next = (i + 1) % segments
                bm.faces.new((shoulder_verts[i], shoulder_verts[i_next], tip_verts[i_next], tip_verts[i]))
            bm.faces.new(tip_verts)
        else:
            bm.faces.new(shoulder_verts)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    mesh_data = bpy.data.meshes.new(name)
    bm.to_mesh(mesh_data)
    bm.free()
    return mesh_data


def compute_connector_positions(
    target_mesh: bpy.types.Mesh,
    matrix_world: Matrix,
    plane_origin: Vector,
    plane_normal: Vector,
    distribution: str = 'CENTER',
    edge_margin_mm: float = 3.0,
    unit_scale: float = 1000.0,
) -> List[Vector]:
    """Calcula os pontos 3D na interface do corte para os encaixes.
    
    Distribuições suportadas:
    - 'CENTER': 1 conector no centro
    - 'LINEAR_2': 2 conectores alinhados
    - 'LINEAR_3': 3 conectores em linha
    - 'GRID_4': 4 conectores em grade 2x2
    """
    # Cria uma BMesh temporária para extrair os vértices na interface de corte
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

    if not cut_pts:
        return [plane_origin.copy()]


    # Cria base ortonormal no plano (tangente U e bitangente V)
    ref_up = Vector((0, 0, 1)) if abs(norm.z) < 0.9 else Vector((0, 1, 0))
    u_axis = norm.cross(ref_up).normalized()
    v_axis = norm.cross(u_axis).normalized()

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

    return positions


def validate_connectors(
    positions: List[Vector],
    diameter_mm: float,
    clearance_per_side_mm: float,
    unit_scale: float = 1000.0,
):
    """Verifica se há sobreposição entre múltiplos encaixes."""
    min_dist_bu = (diameter_mm + 2.0 * clearance_per_side_mm) / unit_scale

    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            dist = (positions[i] - positions[j]).length
            if dist < min_dist_bu:
                dist_mm = dist * unit_scale
                req_mm = diameter_mm + 2.0 * clearance_per_side_mm
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
):
    """Executa as operações booleanas para unir os machos e subtrair as cavidades."""
    norm = plane_normal.normalized()
    # Rotação para alinhar o eixo +Z do conector com a normal do plano de corte
    rot_quat = Vector((0.0, 0.0, 1.0)).rotation_difference(norm)

    cutters_to_clean = []

    # Cria coleção temporária de corte se necessário
    temp_col = obj_male.users_collection[0] if obj_male.users_collection else bpy.context.scene.collection

    diam_bu = diameter_mm / unit_scale
    len_bu = length_mm / unit_scale
    chamf_bu = chamfer_mm / unit_scale
    clear_side_bu = clearance_side_mm / unit_scale
    clear_end_bu = end_clearance_mm / unit_scale

    # 1. Aplica machos (UNION) no obj_male
    for idx, pos in enumerate(positions):
        pin_mesh = create_pin_mesh_data(
            name=f"temp_pin_{idx}",
            connector_type=connector_type,
            diameter=diam_bu,
            length=len_bu,
            chamfer=chamf_bu,
            is_cavity=False,
        )
        pin_obj = bpy.data.objects.new(f"temp_pin_{idx}", pin_mesh)
        pin_obj.location = pos
        pin_obj.rotation_euler = rot_quat.to_euler()
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
        )
        cavity_obj = bpy.data.objects.new(f"temp_cavity_{idx}", cavity_mesh)
        cavity_obj.location = pos
        cavity_obj.rotation_euler = rot_quat.to_euler()
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

        if old_mesh and old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh, do_unlink=True)

    # Limpa objetos e malhas auxiliares de corte
    for cutter in cutters_to_clean:
        c_mesh = cutter.data
        temp_col.objects.unlink(cutter)
        bpy.data.objects.remove(cutter, do_unlink=True)
        if c_mesh and c_mesh.users == 0:
            bpy.data.meshes.remove(c_mesh, do_unlink=True)
