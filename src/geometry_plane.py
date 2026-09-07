"""Cálculos geométricos de corte por plano e fechamento de malhas (Domain/Core).

Este módulo não depende de seleção ativa nem de contexto de interface da Viewport,
permitindo execução determinística e testes automatizados headless.
"""

from typing import Dict, Any, Tuple, Optional
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


def cap_open_cut_boundaries(bm: bmesh.types.BMesh, cut_edges: Optional[list] = None) -> int:
    """Fecha bordas abertas resultantes do corte planar para garantir malha manifold.
    
    Tenta primeiro 'edgenet_fill' nas arestas de corte. Caso restem bordas abertas
    (por exemplo em geometrias com furos ou ilhas múltiplas), recorre a 'holes_fill'.
    Retorna o número de faces de fechamento geradas.
    """
    faces_created = 0

    # Coleta arestas que delimitam o corte
    target_edges = []
    if cut_edges:
        target_edges = [e for e in cut_edges if e.is_valid and e.is_boundary]
    if not target_edges:
        target_edges = [e for e in bm.edges if e.is_boundary]

    if not target_edges:
        return 0

    # 1. Tentativa com edgenet_fill
    try:
        res = bmesh.ops.edgenet_fill(bm, edges=target_edges)
        created = res.get("faces", [])
        faces_created += len(created)
    except Exception:
        pass

    # 2. Fallback: verifica se ainda há arestas abertas e usa holes_fill
    remaining_boundary = [e for e in bm.edges if e.is_boundary]
    if remaining_boundary:
        try:
            res_holes = bmesh.ops.holes_fill(bm, edges=remaining_boundary, sides=0)
            created_holes = res_holes.get("faces", [])
            faces_created += len(created_holes)
        except Exception:
            pass

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


def slice_mesh_by_plane(
    source_mesh: bpy.types.Mesh,
    matrix_world,
    plane_origin: Vector,
    plane_normal: Vector,
    target_mesh_a: bpy.types.Mesh,
    target_mesh_b: bpy.types.Mesh,
    invert_sides: bool = False,
    unit_scale: float = 1000.0,
) -> Dict[str, Any]:
    """Corta uma malha pelo plano dado, gerando Parte A e Parte B fechadas.
    
    A malha é processada no espaço global de coordenadas (World Space) para evitar
    distorções provocadas por escalas não uniformes ou rotações no objeto original.
    """
    norm = plane_normal.normalized()
    if norm.length < 1e-6:
        raise PlaneSliceError("Vetor normal do plano inválido (comprimento nulo).")

    # Inversão de lados A/B caso solicitada
    effective_normal_a = -norm if invert_sides else norm
    effective_normal_b = -effective_normal_a

    results = {}

    for side_key, cut_normal in [("A", effective_normal_a), ("B", effective_normal_b)]:
        bm = bmesh.new()
        bm.from_mesh(source_mesh)

        # Transforma para o espaço global de coordenadas
        bm.transform(matrix_world)

        # Executa corte bisect
        # clear_outer=True descarta a geometria na direção de cut_normal
        bisect_res = bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=plane_origin,
            plane_no=cut_normal,
            clear_outer=True,
            clear_inner=False,
        )

        cut_edges = [e for e in bisect_res.get("geom_cut", []) if isinstance(e, bmesh.types.BMEdge)]

        # Se a malha resultante ficou completamente vazia, o plano não cortou o modelo
        if len(bm.verts) == 0:
            bm.free()
            raise NoIntersectionError(
                f"O plano de corte não intersecta o modelo (lado {side_key} ficou vazio)."
            )

        # Fecha bordas abertas no plano de corte
        cap_open_cut_boundaries(bm, cut_edges=cut_edges)

        # Avalia métricas
        metrics = evaluate_bmesh_metrics(bm, unit_scale=unit_scale)
        results[side_key] = metrics

        # Escreve na malha de destino correspondente
        target_mesh = target_mesh_a if side_key == "A" else target_mesh_b
        target_mesh.clear_geometry()
        bm.to_mesh(target_mesh)
        target_mesh.update()
        bm.free()

    # Se um dos lados tiver volume nulo ou faces insuficientes, considerar sem interseção
    if results["A"]["verts"] == 0 or results["B"]["verts"] == 0:
        raise NoIntersectionError("O plano não cortou o objeto em duas partes distintas.")

    results["sum_volume_mm3"] = results["A"]["volume_mm3"] + results["B"]["volume_mm3"]
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
