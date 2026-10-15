"""Serviço de preparação de corte, frame compartilhado e superfície de encaixe.

Implementa a separação de responsabilidades (Etapa B / Seção 5 do Plano):
1. prepare_split_candidates: extrai o corte sem pinos e constrói a CutInterface formal.
2. Frame único: conversões UV <-> Mundo montado <-> Espaço explodido sem divergência.
3. Raycast e picking precisos sobre a superfície física de contato.
4. Avaliação determinística por ID de cada conector manual.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import math
import hashlib

import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

from .geometry_contract import CutInterface, build_cut_interface
from .diagnostic import get_scene_scale_to_mm


@dataclass
class PreparedSplit:
    """Dados preparados do corte sem pinos para edição e geração."""
    cut_signature: str
    target_name: str
    split_mode: str
    interface: CutInterface
    surface_origin: Vector
    surface_normal: Vector
    axis_u: Vector
    axis_v: Vector
    unit_scale: float
    male_side: str
    is_planar: bool = True
    contact_triangles_world: List[Tuple[Vector, Vector, Vector]] = field(default_factory=list)
    bvh_tree: Optional[BVHTree] = None

    def world_to_uv_mm(self, point_assembled_world: Vector) -> Tuple[float, float]:
        """Converte ponto montado 3D para UV da interface em milímetros."""
        u_bu, v_bu = self.interface.world_to_uv(point_assembled_world)
        return (u_bu * self.unit_scale, v_bu * self.unit_scale)

    def uv_mm_to_world(self, u_mm: float, v_mm: float) -> Vector:
        """Converte UV da interface em milímetros para ponto montado 3D."""
        u_bu = u_mm / self.unit_scale
        v_bu = v_mm / self.unit_scale
        return self.interface.uv_to_world(u_bu, v_bu)


# Cache em memória do último corte preparado
_CACHED_PREPARED_SPLIT: Optional[PreparedSplit] = None
_LAST_KNOWN_AXIS_U: Optional[Vector] = None
_LAST_KNOWN_AXIS_V: Optional[Vector] = None


def compute_cut_signature(settings: Any, target: bpy.types.Object) -> str:
    """Gera hash determinístico dos parâmetros que alteram a geometria do corte sem pinos."""
    h = hashlib.sha256()
    h.update(target.name.encode('utf-8'))
    h.update(str(target.matrix_world).encode('utf-8'))
    mode = getattr(settings, "split_mode", "PLANE")
    h.update(mode.encode('utf-8'))
    h.update(str(getattr(settings, "invert_sides", False)).encode('utf-8'))
    h.update(str(getattr(settings, "plane_offset_mm", 0.0)).encode('utf-8'))
    h.update(str(getattr(settings, "part_clearance_mm", 0.0)).encode('utf-8'))

    if mode == 'PLANE':
        h.update(str(getattr(settings, "plane_origin", (0, 0, 0))).encode('utf-8'))
        h.update(str(getattr(settings, "plane_normal", (0, 0, 1))).encode('utf-8'))
    elif mode == 'LOOP':
        h.update(str(getattr(settings, "loop_cut_mode", "KNIFE")).encode('utf-8'))
        h.update(str(getattr(settings, "loop_extrude_depth_mm", 0.0)).encode('utf-8'))
        h.update(str(getattr(settings, "loop_base_thick_mm", 0.0)).encode('utf-8'))
        h.update(str(getattr(settings, "loop_bridge_enable", False)).encode('utf-8'))
        h.update(str(getattr(settings, "loop_subdivide_edges", False)).encode('utf-8'))
    elif mode == 'MATERIAL':
        h.update(str(getattr(settings, "material_split_index", 0)).encode('utf-8'))
        h.update(str(getattr(settings, "material_extrude_depth_mm", 5.0)).encode('utf-8'))
        h.update(str(getattr(settings, "material_region_index", -1)).encode('utf-8'))
        h.update(str(getattr(settings, "material_extraction_mode", 'EXTRUDE')).encode('utf-8'))
        h.update(str(getattr(settings, "part_clearance_bottom_mm", 0.0)).encode('utf-8'))
        h.update(str(getattr(settings, "part_clearance_bottom_enable", False)).encode('utf-8'))

    return h.hexdigest()


def get_cached_prepared_split() -> Optional[PreparedSplit]:
    """Retorna o PreparedSplit em cache se disponível."""
    global _CACHED_PREPARED_SPLIT
    return _CACHED_PREPARED_SPLIT


def clear_prepared_split_cache():
    """Invalida o cache de corte preparado."""
    global _CACHED_PREPARED_SPLIT, _LAST_KNOWN_AXIS_U, _LAST_KNOWN_AXIS_V
    _CACHED_PREPARED_SPLIT = None


def prepare_split_candidates(context: bpy.types.Context, force_recompute: bool = False) -> PreparedSplit:
    """Prepara o corte sem encaixes, garantindo uma única CutInterface e superfície útil de contato.
    
    Compatível com os três modos (PLANE, LOOP e MATERIAL).
    Preserva a seleção de modo/arestas se o usuário estiver em Edit Mode.
    """
    global _CACHED_PREPARED_SPLIT, _LAST_KNOWN_AXIS_U, _LAST_KNOWN_AXIS_V
    settings = context.scene.chest_splitter
    target = getattr(settings, "target_object", None)
    if not target or target.name not in bpy.data.objects:
        raise RuntimeError("Nenhum objeto alvo definido para o corte.")

    # Se estiver em Edit Mode, sincroniza dados para leitura sem alternar modo
    if target.mode == 'EDIT':
        target.update_from_editmode()

    sig = compute_cut_signature(settings, target)
    if not force_recompute and _CACHED_PREPARED_SPLIT is not None:
        if _CACHED_PREPARED_SPLIT.cut_signature == sig and _CACHED_PREPARED_SPLIT.target_name == target.name:
            return _CACHED_PREPARED_SPLIT

    unit_scale = get_scene_scale_to_mm(context.scene)
    if unit_scale <= 0.0:
        unit_scale = 1000.0

    mode = getattr(settings, "split_mode", "PLANE")
    male_side = getattr(settings, "connector_male_part", "A")

    cut_iface: Optional[CutInterface] = None
    contact_tris: List[Tuple[Vector, Vector, Vector]] = []
    bvh_tree: Optional[BVHTree] = None

    if mode == 'PLANE':
        from .plane_state import resolve_plane_state
        plane_origin, plane_normal = resolve_plane_state(context.scene, settings)
        norm = plane_normal.normalized()
        offset_mm = getattr(settings, "plane_offset_mm", 0.0)
        offset_bu = (offset_mm / unit_scale)
        eff_origin = plane_origin + norm * offset_bu

        # Executa bisect temporário para extrair loops da interface
        bm = bmesh.new()
        bm.from_mesh(target.data)
        bm.transform(target.matrix_world)

        res = bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=eff_origin,
            plane_no=norm,
            clear_outer=False,
            clear_inner=False,
        )
        cut_edges = [e for e in res.get("geom_cut", []) if isinstance(e, bmesh.types.BMEdge)]
        from .geometry_plane import reconstruct_boundary_loops
        interface_loops = reconstruct_boundary_loops(cut_edges)
        interface_points = [p for loop in interface_loops for p in loop] if interface_loops else [v.co.copy() for e in cut_edges if e.is_valid for v in e.verts]

        # Constrói triângulos de preenchimento para raycast se possível
        try:
            # Preenche faces temporárias da interface para BVH
            fill_res = bmesh.ops.edgenet_fill(bm, edges=cut_edges)
            cap_faces = fill_res.get("faces", [])
            for f in cap_faces:
                for tri in f.calc_loop_triangles():
                    contact_tris.append((tri[0].vert.co.copy(), tri[1].vert.co.copy(), tri[2].vert.co.copy()))
        except Exception:
            pass

        bm.free()

        effective_normal_a = -norm if settings.invert_sides else norm
        cut_iface = build_cut_interface(
            origin_world=eff_origin,
            normal_a_to_b=effective_normal_a,
            boundary_points_world=interface_points,
            boundary_loops_world=interface_loops,
            unit_scale=unit_scale,
            source_mode="PLANE",
        )

    elif mode == 'LOOP':
        from .geometry_loop import (
            slice_mesh_by_loop,
            slice_mesh_by_loop_extrude,
        )
        if target.mode == 'EDIT':
            target.update_from_editmode()

        indices = [int(i) for i in settings.loop_vertex_indices.split(',') if i.strip()]
        if not indices or settings.loop_seed_face_index < 0:
            raise RuntimeError("Nenhum contorno (loop) capturado no modo Loop.")

        behavior = settings.loop_behavior
        if behavior == 'EXTRUDE':
            loop_res = slice_mesh_by_loop_extrude(
                target,
                target.name,
                indices,
                settings.loop_seed_face_index,
                depth_mm=settings.loop_extrude_depth_mm,
                through_cut=settings.loop_through_cut,
                scene=context.scene,
            )
        else:
            loop_res = slice_mesh_by_loop(
                target,
                target.name,
                indices,
                settings.loop_seed_face_index,
                context.scene,
                detach_add_base=settings.loop_detach_add_base,
                detach_base_depth_mm=settings.loop_detach_base_depth_mm,
                detach_base_clearance_mm=settings.loop_detach_base_clearance_mm,
            )

        bm_a, bm_b = loop_res[0], loop_res[1]
        bm_a.free()
        bm_b.free()

        cut_iface = getattr(loop_res, 'interface', None)
        if cut_iface:
            settings.loop_interface_origin = tuple(cut_iface.origin_world)
            settings.loop_interface_normal = tuple(cut_iface.normal_a_to_b_world)
            if getattr(cut_iface, "interface_triangles_world", None):
                contact_tris = list(cut_iface.interface_triangles_world)

    elif mode == 'MATERIAL':
        from .geometry_material import slice_mesh_by_material
        if not target.data.materials:
            raise RuntimeError("O objeto alvo não possui materiais para o modo Material.")

        mat_res = slice_mesh_by_material(
            target,
            material_index=settings.material_split_index,
            depth_mm=settings.material_extrude_depth_mm,
            scene=context.scene,
            region_index=settings.material_region_index,
            extraction_mode=getattr(settings, "material_extraction_mode", 'EXTRUDE'),
            interface_mat_mode=getattr(settings, "material_interface_mat_mode", 'SOURCE'),
            part_clearance_mm=getattr(settings, "part_clearance_mm", 0.0),
            part_clearance_apply_to=getattr(settings, "part_clearance_apply_to", 'PART'),
            part_clearance_bottom_mm=(
                getattr(settings, "part_clearance_bottom_mm", 0.0)
                if getattr(settings, "part_clearance_bottom_enable", False) else None
            ),
        )
        bm_a, bm_b = mat_res[0], mat_res[1]
        bm_a.free()
        bm_b.free()

        cut_iface = getattr(mat_res, 'interface', None)
        if cut_iface:
            settings.loop_interface_origin = tuple(cut_iface.origin_world)
            settings.loop_interface_normal = tuple(cut_iface.normal_a_to_b_world)
            if getattr(cut_iface, "interface_triangles_world", None):
                contact_tris = list(cut_iface.interface_triangles_world)

    if cut_iface is None:
        raise RuntimeError("Não foi possível preparar a interface de corte para o modelo.")

    # Estabilização dos eixos U/V contra inversão de sinal (T13 / Seção 5.2)
    axis_u = cut_iface.axis_u_world.copy()
    axis_v = cut_iface.axis_v_world.copy()
    if _LAST_KNOWN_AXIS_U is not None and _LAST_KNOWN_AXIS_V is not None:
        if axis_u.dot(_LAST_KNOWN_AXIS_U) < 0.0:
            axis_u = -axis_u
            axis_v = -axis_v
        if axis_v.dot(_LAST_KNOWN_AXIS_V) < 0.0:
            axis_v = -axis_v
        cut_iface.axis_u_world = axis_u
        cut_iface.axis_v_world = axis_v
    _LAST_KNOWN_AXIS_U = axis_u.copy()
    _LAST_KNOWN_AXIS_V = axis_v.copy()

    # Define a normal na superfície de contato voltada para fora do macho
    if male_side == 'A':
        surface_normal = cut_iface.normal_a_to_b_world.normalized()
    else:
        surface_normal = -cut_iface.normal_a_to_b_world.normalized()

    # Constrói BVHTree para raycast se houver triângulos de contato
    if contact_tris:
        bvh_tree = BVHTree.FromPolygons(
            [v for tri in contact_tris for v in tri],
            [(i * 3, i * 3 + 1, i * 3 + 2) for i in range(len(contact_tris))]
        )

    prepared = PreparedSplit(
        cut_signature=sig,
        target_name=target.name,
        split_mode=mode,
        interface=cut_iface,
        surface_origin=cut_iface.origin_world.copy(),
        surface_normal=surface_normal,
        axis_u=axis_u,
        axis_v=axis_v,
        unit_scale=unit_scale,
        male_side=male_side,
        is_planar=cut_iface.is_planar,
        contact_triangles_world=contact_tris,
        bvh_tree=bvh_tree,
    )
    _CACHED_PREPARED_SPLIT = prepared
    return prepared


def get_explosion_display_offset(settings: Any, prepared: PreparedSplit) -> Vector:
    """Calcula o vetor de deslocamento da visão explodida para a superfície dos pinos."""
    if getattr(settings, "view_mode", "EXPLODED") != 'EXPLODED':
        return Vector((0.0, 0.0, 0.0))

    dist_mm = getattr(settings, "explosion_distance_mm", 0.0)
    if abs(dist_mm) < 1e-6:
        return Vector((0.0, 0.0, 0.0))

    from .geometry_plane import compute_explosion_offsets
    invert = getattr(settings, "invert_explosion", False)
    offset_a, offset_b = compute_explosion_offsets(
        plane_normal=prepared.interface.normal_a_to_b_world,
        explosion_distance_mm=dist_mm,
        unit_scale=prepared.unit_scale,
        invert_direction=invert,
    )
    return offset_a if prepared.male_side == 'A' else offset_b


def raycast_connector_surface(
    ray_origin: Vector,
    ray_dir: Vector,
    prepared: PreparedSplit,
    display_offset: Vector = Vector((0.0, 0.0, 0.0)),
) -> Optional[Tuple[Vector, float, float]]:
    """Projeta raio na superfície preparada e retorna (ponto_montado, u_mm, v_mm).
    
    Desfaz qualquer deslocamento explodido para garantir que coordenadas persistidas
    sejam sempre no espaço montado (Seção 4.1).
    """
    ray_dir = ray_dir.normalized()

    # 1. Se houver BVHTree da superfície de contato, testa interseção com malha real
    if prepared.bvh_tree is not None:
        # Move o raio para o espaço local da superfície exibida
        local_ray_origin = ray_origin - display_offset
        hit_loc, hit_norm, hit_idx, hit_dist = prepared.bvh_tree.ray_cast(local_ray_origin, ray_dir)
        if hit_loc is not None:
            assembled_hit = hit_loc
            u_mm, v_mm = prepared.world_to_uv_mm(assembled_hit)
            return (assembled_hit, u_mm, v_mm)

    # 2. Interseção analítica raio-plano com a interface planar preparada
    orig_disp = prepared.surface_origin + display_offset
    denom = ray_dir.dot(prepared.surface_normal)
    if abs(denom) < 1e-5:
        # Raio paralelo à interface
        return None

    t = (orig_disp - ray_origin).dot(prepared.surface_normal) / denom
    if t < 0.0:
        return None

    hit_disp = ray_origin + ray_dir * t
    assembled_hit = hit_disp - display_offset
    u_mm, v_mm = prepared.world_to_uv_mm(assembled_hit)
    return (assembled_hit, u_mm, v_mm)


def evaluate_connector_specs(prepared: PreparedSplit, settings: Any) -> List[Dict[str, Any]]:
    """Avalia individualmente cada conector manual quanto à margem, furos e colisões mútuas.
    
    Retorna lista de dicionários com chaves: index, id, is_valid, reason.
    """
    diam_mm = getattr(settings, "connector_diameter_mm", 4.0)
    clear_side_mm = getattr(settings, "clearance_per_side_mm", 0.15)
    margin_mm = getattr(settings, "connector_edge_margin_mm", 3.0)
    conn_type = getattr(settings, "connector_type", "CYLINDER")
    cap_len_mm = getattr(settings, "connector_capsule_length_mm", 6.0)

    unit_scale = prepared.unit_scale
    check_r = (diam_mm / 2.0 + clear_side_mm + margin_mm) / unit_scale
    half_len = max(0.0, (cap_len_mm - diam_mm) / 2.0) / unit_scale if conn_type == 'CAPSULE' else 0.0

    outer_polys = getattr(prepared.interface, "outer_contours_uv", []) or []
    hole_polys = getattr(prepared.interface, "hole_contours_uv", []) or []

    results = []
    connectors = list(settings.manual_connectors)
    n_conns = len(connectors)

    from .geometry_connectors import validate_connector_footprint

    # 1. Validação individual de footprint no domínio da interface
    for idx, conn in enumerate(connectors):
        u_bu = conn.u_mm / unit_scale
        v_bu = conn.v_mm / unit_scale
        yaw_rad = math.radians(getattr(conn, "yaw_deg", 0.0))

        if not outer_polys:
            is_ok, reason = False, "Interface de contato não preparada"
        else:
            is_ok, reason = validate_connector_footprint(
                u_p=u_bu,
                v_p=v_bu,
                check_r=check_r,
                outer_polys=outer_polys,
                hole_polys=hole_polys,
                edge_margin_mm=margin_mm,
                connector_type=conn_type,
                half_len=half_len,
                yaw_rad=yaw_rad,
            )

        results.append({
            "index": idx,
            "id": getattr(conn, "connector_id", "") or f"pin_{idx}",
            "is_valid": is_ok,
            "reason": reason,
        })

    # 2. Validação de colisão entre pares de conectores (T19)
    # Raio de corpo físico do encaixe com folga e margem mínima entre pinos
    min_dist_centers_mm = diam_mm + 2.0 * clear_side_mm + 1.0
    for i in range(n_conns):
        if not results[i]["is_valid"]:
            continue
        c1 = connectors[i]
        for j in range(i + 1, n_conns):
            c2 = connectors[j]
            du = c1.u_mm - c2.u_mm
            dv = c1.v_mm - c2.v_mm
            dist_sq_mm = du * du + dv * dv
            # Se cápsula, considera também comprimento
            req_dist_mm = (cap_len_mm if conn_type == 'CAPSULE' else diam_mm) + 2.0 * clear_side_mm + 1.0
            if dist_sq_mm < (req_dist_mm * req_dist_mm):
                results[i]["is_valid"] = False
                results[i]["reason"] = f"Colisão: muito próximo do pino #{j + 1}"
                if results[j]["is_valid"]:
                    results[j]["is_valid"] = False
                    results[j]["reason"] = f"Colisão: muito próximo do pino #{i + 1}"

    # Atualiza as propriedades no PropertyGroup
    for ev in results:
        idx = ev["index"]
        if idx < len(settings.manual_connectors):
            item = settings.manual_connectors[idx]
            item.is_valid = ev["is_valid"]
            item.status_reason = ev["reason"]
            item.validation_msg = ev["reason"]

    return results
