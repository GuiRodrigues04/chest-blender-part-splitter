"""Cálculos geométricos de corte por plano e fechamento de malhas (Domain/Core).

Este módulo não depende de seleção ativa nem de contexto de interface da Viewport,
permitindo execução determinística e testes automatizados headless.
"""

from typing import Dict, Any, Tuple, Optional, List
import bpy
import bmesh
from mathutils import Vector


class PlaneSliceError(Exception):
    """Exceção base para falhas de corte por plano."""
    pass


class NoIntersectionError(PlaneSliceError):
    """Lançada quando o plano de corte não intersecta a geometria do modelo alvo."""
    pass


def count_mesh_islands(bm: bmesh.types.BMesh) -> int:
    """Conta a quantidade de componentes/ilhas desconexas na malha."""
    visited = set()
    islands = 0

    for face in bm.faces:
        if face in visited:
            continue
        islands += 1
        queue = [face]
        visited.add(face)

        while queue:
            curr = queue.pop(0)
            for edge in curr.edges:
                for linked_face in edge.link_faces:
                    if linked_face not in visited:
                        visited.add(linked_face)
                        queue.append(linked_face)

    return islands


def cap_open_cut_boundaries(
    bm: bmesh.types.BMesh,
    cut_edges: Optional[list] = None,
    plane_origin: Optional[Vector] = None,
    plane_normal: Optional[Vector] = None,
    coplanar_tol_bu: float = 1e-4,
) -> int:
    """Fecha bordas abertas resultantes do corte planar para garantir malha manifold.
    
    Restringe o fechamento às bordas realmente geradas pelo corte e ao domínio no plano (B11 / T38),
    impedindo o preenchimento de aberturas pré-existentes do modelo em outros locais.
    Retorna o número de faces de fechamento geradas.
    """
    faces_created = 0

    # Coleta arestas que delimitam o corte
    target_edges = []
    if cut_edges:
        target_edges = [e for e in cut_edges if e.is_valid and e.is_boundary]

    if not target_edges and plane_origin is not None and plane_normal is not None:
        norm = plane_normal.normalized()
        target_edges = [
            e for e in bm.edges
            if e.is_valid and e.is_boundary and
            abs((e.verts[0].co - plane_origin).dot(norm)) <= coplanar_tol_bu and
            abs((e.verts[1].co - plane_origin).dot(norm)) <= coplanar_tol_bu
        ]

    if not target_edges and cut_edges is None and plane_origin is None:
        target_edges = [e for e in bm.edges if e.is_valid and e.is_boundary]

    if not target_edges:
        return 0

    created_all = []
    # 1. Tentativa com edgenet_fill
    try:
        res = bmesh.ops.edgenet_fill(bm, edges=target_edges)
        created = res.get("faces", [])
        created_all.extend(created)
        faces_created += len(created)
    except Exception:
        pass

    # 2. Fallback: fecha arestas abertas remanescentes
    if plane_origin is not None and plane_normal is not None:
        norm = plane_normal.normalized()
        remaining_boundary = [
            e for e in bm.edges
            if e.is_valid and e.is_boundary and
            abs((e.verts[0].co - plane_origin).dot(norm)) <= coplanar_tol_bu and
            abs((e.verts[1].co - plane_origin).dot(norm)) <= coplanar_tol_bu
        ]
    else:
        remaining_boundary = [e for e in bm.edges if e.is_valid and e.is_boundary]

    if remaining_boundary:
        try:
            res_holes = bmesh.ops.holes_fill(bm, edges=remaining_boundary, sides=0)
            created_holes = res_holes.get("faces", [])
            created_all.extend(created_holes)
            faces_created += len(created_holes)
        except Exception:
            pass

    # Atribuição inteligente de material para as novas faces da tampa (interface de corte):
    if created_all:
        created_set = set(created_all)
        for f in created_all:
            adj_mats = []
            for e in f.edges:
                for lf in e.link_faces:
                    if lf not in created_set:
                        adj_mats.append(lf.material_index)
            if adj_mats:
                f.material_index = max(set(adj_mats), key=adj_mats.count)

    # Recalcula normais para garantir orientação exterior consistente
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return faces_created


def evaluate_bmesh_metrics(bm: bmesh.types.BMesh, unit_scale: float = 1000.0) -> Dict[str, Any]:
    """Calcula volume, dimensões, manifold e componentes de um BMesh."""
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    verts_count = len(bm.verts)
    faces_count = len(bm.faces)
    tris_count = sum(len(f.verts) - 2 for f in bm.faces)

    if verts_count == 0:
        return {
            "volume_mm3": 0.0,
            "dims_mm": (0.0, 0.0, 0.0),
            "triangles": 0,
            "faces": 0,
            "verts": 0,
            "is_manifold": False,
            "non_manifold_edges": 0,
            "components": 0,
        }

    # Bounding box
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    dims_bu = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    dims_mm = (dims_bu[0] * unit_scale, dims_bu[1] * unit_scale, dims_bu[2] * unit_scale)

    # Volume (bu³ -> mm³)
    vol_bu = bm.calc_volume()
    vol_mm3 = abs(vol_bu) * (unit_scale ** 3)

    # Manifold
    non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
    is_manifold = (len(non_manifold_edges) == 0 and verts_count >= 4 and faces_count >= 4)

    # Componentes desconectados
    components = count_mesh_islands(bm)

    return {
        "volume_mm3": vol_mm3,
        "dims_mm": dims_mm,
        "triangles": tris_count,
        "faces": faces_count,
        "verts": verts_count,
        "is_manifold": is_manifold,
        "non_manifold_edges": len(non_manifold_edges),
        "components": components,
    }


def reconstruct_boundary_loops(cut_edges: List[bmesh.types.BMEdge]) -> List[List[Vector]]:
    """Reconstrói ciclos ordenados e contínuos a partir das arestas de corte geradas por bisect.
    
    Remove vértices finais repetidos e duplicações consecutivas; valida fechamento,
    continuidade e ausência de ramificações, evitando diagonais e cruzamentos espúrios.
    """
    from collections import defaultdict
    vert_to_edges = defaultdict(list)
    for e in cut_edges:
        if e.is_valid:
            vert_to_edges[e.verts[0]].append(e)
            vert_to_edges[e.verts[1]].append(e)

    visited_edges = set()
    loops = []

    for e_start in cut_edges:
        if not e_start.is_valid or e_start in visited_edges:
            continue
        v_start = e_start.verts[0]
        curr_v = e_start.verts[1]
        visited_edges.add(e_start)
        loop_verts = [v_start, curr_v]
        curr_e = e_start
        closed = False

        while True:
            candidates = [e for e in vert_to_edges[curr_v] if e != curr_e and e not in visited_edges and e.is_valid]
            if not candidates:
                # Verifica se fechou no vértice inicial
                if curr_v == v_start or any(e == e_start for e in vert_to_edges[curr_v]):
                    closed = True
                break
            next_e = candidates[0]
            visited_edges.add(next_e)
            next_v = next_e.verts[0] if next_e.verts[1] == curr_v else next_e.verts[1]
            if next_v == v_start:
                closed = True
                break
            loop_verts.append(next_v)
            curr_v = next_v
            curr_e = next_e

        if closed and len(loop_verts) >= 3:
            pts = []
            for v in loop_verts:
                co = v.co.copy()
                if not pts or (co - pts[-1]).length > 1e-6:
                    pts.append(co)
            # Remove vértice final repetido se coincidir com o inicial
            if len(pts) > 1 and (pts[0] - pts[-1]).length < 1e-6:
                pts.pop()
            if len(pts) >= 3:
                loops.append(pts)

    return loops


def slice_mesh_by_plane(
    source_mesh: bpy.types.Mesh,
    matrix_world,
    plane_origin: Vector,
    plane_normal: Vector,
    target_mesh_a: bpy.types.Mesh,
    target_mesh_b: bpy.types.Mesh,
    invert_sides: bool = False,
    unit_scale: float = 1000.0,
    coplanar_tol_mm: float = 0.05,
    plane_offset_mm: float = 0.0,
    part_clearance_mm: float = 0.0,
    part_clearance_apply_to: str = 'PART',
) -> Dict[str, Any]:
    """Corta uma malha pelo plano dado, gerando Parte A e Parte B fechadas (B11 / P02 / P03).
    
    Elimina lâminas e películas coplanares espúrias em alinhamentos por face,
    aplica folga física calibrada entre peças (E01) e processa em World Space.
    """
    norm = plane_normal.normalized()
    if norm.length < 1e-6:
        raise PlaneSliceError("Vetor normal do plano inválido (comprimento nulo).")

    # Inversão de lados A/B caso solicitada
    effective_normal_a = -norm if invert_sides else norm
    effective_normal_b = -effective_normal_a

    # Deslocamento explícito do usuário (mm -> BU)
    base_origin = plane_origin.copy()
    if abs(plane_offset_mm) > 1e-7:
        base_origin += (plane_offset_mm / unit_scale) * norm

    coplanar_tol_bu = max(1e-6, coplanar_tol_mm / unit_scale)
    clearance_bu = max(0.0, part_clearance_mm / unit_scale)

    results = {}

    for side_key, cut_normal in [("A", effective_normal_a), ("B", effective_normal_b)]:
        # Calcula origem específica considerando folga entre peças (Etapa E / E01)
        side_origin = base_origin.copy()
        if clearance_bu > 1e-7:
            if part_clearance_apply_to == 'PART':
                if side_key == 'A':
                    side_origin -= (clearance_bu * effective_normal_a)
            elif part_clearance_apply_to == 'CAVITY':
                if side_key == 'B':
                    side_origin -= (clearance_bu * effective_normal_b)
            elif part_clearance_apply_to == 'BOTH':
                half_c = clearance_bu * 0.5
                if side_key == 'A':
                    side_origin -= (half_c * effective_normal_a)
                elif side_key == 'B':
                    side_origin -= (half_c * effective_normal_b)

        bm = bmesh.new()
        bm.from_mesh(source_mesh)
        bm.transform(matrix_world)

        # 1. Classificação pré-corte de faces coplanares para eliminar lâminas (B11 / P02 / P03)
        # Identifica se o plano de corte coincide com alguma face planar real do modelo
        coplanar_faces_pre = []
        for f in bm.faces:
            if f.calc_area() < 1e-8:
                continue
            dists = [(v.co - side_origin).dot(norm) for v in f.verts]
            if all(abs(d) <= coplanar_tol_bu for d in dists):
                dot_val = f.normal.dot(norm)
                if abs(dot_val) > 0.8:
                    coplanar_faces_pre.append((f.index, dot_val))

        has_coplanar = len(coplanar_faces_pre) > 0

        # 2. Executa corte bisect
        bisect_res = bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=side_origin,
            plane_no=cut_normal,
            clear_outer=True,
            clear_inner=False,
        )

        cut_edges = [e for e in bisect_res.get("geom_cut", []) if isinstance(e, bmesh.types.BMEdge) and e.is_valid]

        # 3. Eliminação estrita de lâminas coplanares da outra metade quando o corte for coplanar (B11 / P02 / P03)
        if has_coplanar:
            retained_positive_halfspace = (cut_normal.dot(norm) < 0)
            faces_to_remove = []
            for f in bm.faces:
                if not f.is_valid:
                    continue
                dists = [(v.co - side_origin).dot(norm) for v in f.verts]
                if all(abs(d) <= coplanar_tol_bu for d in dists):
                    dot_val = f.normal.dot(norm)
                    if retained_positive_halfspace and dot_val > 0.8:
                        # Face exterior do corpo inferior não deve virar tampa/lâmina na peça superior
                        faces_to_remove.append(f)
                    elif not retained_positive_halfspace and dot_val < -0.8:
                        faces_to_remove.append(f)
                    elif f.calc_area() < 1e-8:
                        faces_to_remove.append(f)

            if faces_to_remove:
                bmesh.ops.delete(bm, geom=faces_to_remove, context='FACES')
                loose_edges = [e for e in bm.edges if e.is_valid and not e.link_faces]
                if loose_edges:
                    bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
                loose_verts = [v for v in bm.verts if v.is_valid and not v.link_faces]
                if loose_verts:
                    bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
                cut_edges = [e for e in cut_edges if e.is_valid and e.is_boundary]

        # Se a malha resultante ficou completamente vazia, o plano não cortou o modelo
        if len(bm.verts) == 0:
            bm.free()
            raise NoIntersectionError(
                f"O plano de corte não intersecta o modelo (lado {side_key} ficou vazio)."
            )

        # 4. Fecha bordas abertas no plano de corte
        cap_open_cut_boundaries(bm, cut_edges=cut_edges)

        # Avalia métricas
        metrics = evaluate_bmesh_metrics(bm, unit_scale=unit_scale)
        results[side_key] = metrics

        # Coleta loops ordenados de borda do corte para construção da interface compartilhada
        if side_key == "A":
            interface_loops = reconstruct_boundary_loops(cut_edges)
            interface_points = [p for loop in interface_loops for p in loop] if interface_loops else [v.co.copy() for e in cut_edges if e.is_valid for v in e.verts]

        # Escreve na malha de destino correspondente
        target_mesh = target_mesh_a if side_key == "A" else target_mesh_b
        target_mesh.clear_geometry()
        target_mesh.materials.clear()
        for mat in source_mesh.materials:
            target_mesh.materials.append(mat)
        bm.to_mesh(target_mesh)
        target_mesh.update()
        bm.free()

    # Se um dos lados tiver volume nulo ou faces insuficientes, considerar sem interseção
    if results["A"]["verts"] == 0 or results["B"]["verts"] == 0:
        raise NoIntersectionError("O plano não cortou o objeto em duas partes distintas.")

    results["sum_volume_mm3"] = results["A"]["volume_mm3"] + results["B"]["volume_mm3"]

    # Constrói CutInterface formal para o corte planar
    from .geometry_contract import build_cut_interface
    cut_interface = build_cut_interface(
        origin_world=base_origin,
        normal_a_to_b=effective_normal_a,
        boundary_points_world=interface_points if 'interface_points' in locals() else [],
        boundary_loops_world=interface_loops if 'interface_loops' in locals() else None,
        unit_scale=unit_scale,
        source_mode="PLANE",
    )
    results["interface"] = cut_interface

    return results


def compute_explosion_offsets(
    plane_normal: Vector,
    explosion_distance_mm: float,
    unit_scale: float = 1000.0,
) -> Tuple[Vector, Vector]:
    """Calcula os vetores de deslocamento da visão explodida para as partes A e B.
    
    A distância é expressa em mm e convertida para unidades do Blender (BU).
    Parte A move-se na direção da normal (+), Parte B na direção oposta (-).
    """
    norm = plane_normal.normalized()
    dist_bu = (explosion_distance_mm / unit_scale) / 2.0
    offset_a = norm * dist_bu
    offset_b = -norm * dist_bu
    return offset_a, offset_b
