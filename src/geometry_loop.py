"""Geometria para o corte por contorno fechado de arestas (Loop).

Executa cortes determinísticos em coordenadas de mundo (World Space), garantindo:
- Malhas manifold fechadas para ambas as partes (Parte A = região selecionada, Parte B = restante).
- Orientação consistente do vetor normal de interface (sempre de A para B).
- Independência da ordem dos vértices selecionados no loop.
- Dimensões físicas reais da interface (sem confundir a interface local com a malha inteira).
"""

from typing import List, Tuple, Dict, Any, Optional
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .diagnostic import get_scene_scale_to_mm
from .geometry_contract import CutInterface, SplitResult, build_cut_interface
from .geometry_plane import evaluate_bmesh_metrics


class LoopSliceResult(tuple):
    """Tupla estendida (bm_a, bm_b) com acesso aos metadados formais do corte."""
    def __new__(cls, bm_a, bm_b, split_result=None):
        return super().__new__(cls, (bm_a, bm_b))

    def __init__(self, bm_a, bm_b, split_result=None):
        self.split_result = split_result
        self.interface = split_result.interface if split_result else None

    @property
    def bm_a(self):
        return self[0]

    @property
    def bm_b(self):
        return self[1]


import hashlib


def get_topology_signature(obj) -> str:
    """Retorna uma assinatura de integridade topológica do objeto."""
    if not obj or obj.type != 'MESH' or not obj.data:
        return ""
    import array
    
    mesh = obj.data
    v_count = len(mesh.vertices)
    e_count = len(mesh.edges)
    f_count = len(mesh.polygons)
    
    h = hashlib.sha256()
    h.update(f"V{v_count}E{e_count}F{f_count}".encode('utf-8'))
    
    if e_count > 0:
        edges = array.array('i', [0] * (e_count * 2))
        mesh.edges.foreach_get("vertices", edges)
        h.update(edges.tobytes())
        
    if len(mesh.loops) > 0:
        loops = array.array('i', [0] * len(mesh.loops))
        mesh.loops.foreach_get("vertex_index", loops)
        h.update(loops.tobytes())
        
    return f"V{v_count}E{e_count}F{f_count}H{h.hexdigest()[:8]}"


def clear_capture(settings: Any, reason: str = ""):
    """Limpa de forma atômica e segura todos os metadados de captura de loop."""
    if not settings:
        return
    settings.loop_is_captured = False
    settings.loop_vertex_count = 0
    settings.loop_vertex_indices = ""
    settings.loop_is_planar = False
    settings.loop_planarity_deviation_mm = 0.0
    settings.loop_seed_face_index = -1
    settings.loop_topology_signature = ""


def validate_capture(target: Any, settings: Any, context: Optional[bpy.types.Context] = None) -> Tuple[bool, str]:
    """Valida se o loop capturado é estritamente consistente com o objeto alvo atual.

    Retorna (is_valid: bool, reason: str).
    """
    if not settings or not getattr(settings, "loop_is_captured", False):
        return False, "Nenhum contorno capturado."

    if not target or target.type != 'MESH' or not target.data:
        return False, "Alvo inválido ou inexistente."

    indices_str = getattr(settings, "loop_vertex_indices", "")
    if not indices_str:
        return False, "Lista de índices do contorno está vazia."

    try:
        indices = [int(i) for i in indices_str.split(',') if i.strip()]
    except ValueError:
        return False, "Índices de vértices mal formatados."

    if len(indices) < 3:
        return False, "Contorno requer no mínimo 3 vértices."

    expected_sig = getattr(settings, "loop_topology_signature", "")
    current_sig = get_topology_signature(target)
    if expected_sig and current_sig and expected_sig != current_sig:
        return False, f"Assinatura topológica divergente: {current_sig} vs {expected_sig}."

    if target.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(target.data)
        bm.verts.ensure_lookup_table()
        v_count = len(bm.verts)
        for idx in indices:
            if idx < 0 or idx >= v_count:
                return False, f"Índice {idx} fora dos limites de vértices ({v_count})."

        n = len(indices)
        for i in range(n):
            v1 = bm.verts[indices[i]]
            v2 = bm.verts[indices[(i + 1) % n]]
            edge_exists = any(e.other_vert(v1) == v2 for e in v1.link_edges)
            if not edge_exists:
                return False, f"Vértices consecutivos ({indices[i]}, {indices[(i+1)%n]}) não formam uma aresta contígua."
    else:
        v_count = len(target.data.vertices)
        for idx in indices:
            if idx < 0 or idx >= v_count:
                return False, f"Índice {idx} fora dos limites de vértices ({v_count})."

        edge_keys = set(target.data.edge_keys)
        n = len(indices)
        for i in range(n):
            k = (min(indices[i], indices[(i + 1) % n]), max(indices[i], indices[(i + 1) % n]))
            if k not in edge_keys:
                return False, f"Vértices consecutivos ({indices[i]}, {indices[(i+1)%n]}) não formam uma aresta contígua na malha."

    return True, "Captura válida."


def capture_edge_loop(obj: bpy.types.Object, scene: Optional[bpy.types.Scene] = None) -> Tuple[bool, List[int], bool, float, str]:
    """Captura e valida um loop fechado de arestas no modo de edição.
    
    Calcula desvio de planicidade no espaço de mundo em milímetros (mm).
    Retorna (sucesso, indices_ordenados, is_planar, desvio_mm, erro_msg).
    """
    if not obj or obj.mode != 'EDIT':
        return False, [], False, 0.0, "O objeto precisa estar em Edit Mode."

    bm = bmesh.from_edit_mesh(obj.data)

    selected_edges = [e for e in bm.edges if e.select]
    if not selected_edges:
        return False, [], False, 0.0, "Nenhuma aresta selecionada."

    if len(selected_edges) < 3:
        return False, [], False, 0.0, "O loop deve ter no mínimo 3 arestas."

    # Mapear vértices para arestas selecionadas
    vert_to_edges = {}
    for e in selected_edges:
        for v in e.verts:
            if v not in vert_to_edges:
                vert_to_edges[v] = []
            vert_to_edges[v].append(e)

    # Validar grau exato 2 para todos os vértices selecionados (ciclo simples 1-manifold)
    for v, edges in vert_to_edges.items():
        if len(edges) != 2:
            if len(edges) < 2:
                return False, [], False, 0.0, "Loop aberto detectado. Selecione um ciclo fechado contínuo."
            else:
                return False, [], False, 0.0, "Bifurcação/Ramificação detectada. O loop deve ser um ciclo simples."

    # Ordenar vértices no ciclo
    start_v = next(iter(vert_to_edges.keys()))
    ordered_verts = [start_v]
    current_v = start_v
    current_e = vert_to_edges[current_v][0]

    while True:
        next_v = current_e.verts[0] if current_e.verts[1] == current_v else current_e.verts[1]
        if next_v == start_v:
            break
        ordered_verts.append(next_v)
        edges_of_next = vert_to_edges[next_v]
        next_e = edges_of_next[0] if edges_of_next[0] != current_e else edges_of_next[1]
        current_v = next_v
        current_e = next_e

    if len(ordered_verts) != len(vert_to_edges):
        return False, [], False, 0.0, "Múltiplos componentes desconectados detectados. Selecione apenas um ciclo."

    # Coordenadas em World Space para cálculo métrico real
    coords_world = [obj.matrix_world @ v.co for v in ordered_verts]
    centroid = sum(coords_world, Vector()) / len(coords_world)

    # Normal do plano médio via método de Newell
    n = Vector((0.0, 0.0, 0.0))
    n_pts = len(coords_world)
    for i in range(n_pts):
        v1 = coords_world[i]
        v2 = coords_world[(i + 1) % n_pts]
        n.x += (v1.y - v2.y) * (v1.z + v2.z)
        n.y += (v1.z - v2.z) * (v1.x + v2.x)
        n.z += (v1.x - v2.x) * (v1.y + v2.y)

    if n.length > 1e-7:
        n.normalize()
    else:
        return False, [], False, 0.0, "Polígono degenerado (área nula)."

    # Desvio máximo do plano em World Units (BU)
    max_deviation_bu = max(abs((v - centroid).dot(n)) for v in coords_world)

    # Conversão de escala da cena para mm
    actual_scene = scene if scene else (bpy.context.scene if hasattr(bpy.context, "scene") else None)
    scale_to_mm = get_scene_scale_to_mm(actual_scene)
    max_deviation_mm = max_deviation_bu * scale_to_mm

    # Tolerância física: desvio até 0.1 mm é considerado planar
    is_planar = max_deviation_mm <= 0.1

    indices = [v.index for v in ordered_verts]
    return True, indices, is_planar, max_deviation_mm, ""


def capture_face_boundary_loop(obj: bpy.types.Object, scene: Optional[bpy.types.Scene] = None) -> Tuple[bool, List[int], bool, float, int, str]:
    """Captura o perímetro (contorno de arestas) de uma seleção contígua de faces em Edit Mode (F02).
    
    Identifica arestas de fronteira com exatamente 1 face incidente selecionada.
    Valida um único ciclo fechado contínuo e sem furos ou bifurcações.
    Retorna (sucesso, indices_ordenados, is_planar, desvio_mm, seed_face_idx, erro_msg).
    """
    if not obj or obj.mode != 'EDIT':
        return False, [], False, 0.0, -1, "O objeto precisa estar em Edit Mode."

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    selected_faces = set(f for f in bm.faces if f.select)
    if not selected_faces:
        return False, [], False, 0.0, -1, "Nenhuma face selecionada. Selecione as faces da área desejada."

    # Determina a face semente da seleção
    if bm.faces.active and bm.faces.active in selected_faces:
        seed_face_idx = bm.faces.active.index
    else:
        seed_face_idx = next(iter(selected_faces)).index

    # Valida conectividade da região de faces selecionadas (ilha única)
    visited = set()
    start_f = next(f for f in selected_faces if f.index == seed_face_idx)
    queue = [start_f]
    visited.add(start_f)
    while queue:
        cur = queue.pop(0)
        for e in cur.edges:
            for nf in e.link_faces:
                if nf in selected_faces and nf not in visited:
                    visited.add(nf)
                    queue.append(nf)

    if len(visited) != len(selected_faces):
        return False, [], False, 0.0, -1, "A seleção contém múltiplas ilhas desconectadas. Selecione uma única região contígua."

    # Identifica arestas de contorno (exatamente 1 face selecionada incidente)
    boundary_edges = []
    for e in bm.edges:
        inc = [lf for lf in e.link_faces if lf in selected_faces]
        if len(inc) == 1:
            boundary_edges.append(e)
        elif len(inc) > 2:
            return False, [], False, 0.0, -1, "Aresta não-manifold detectada na seleção de faces."

    if not boundary_edges:
        return False, [], False, 0.0, -1, "A seleção não possui bordas abertas (toda a superfície fechada está selecionada)."

    # Mapeia vértices do contorno
    vert_to_edges = {}
    for e in boundary_edges:
        for v in e.verts:
            vert_to_edges.setdefault(v, []).append(e)

    for v, edges in vert_to_edges.items():
        if len(edges) != 2:
            if len(edges) > 2:
                return False, [], False, 0.0, -1, "Ramificação/bifurcação no perímetro (regiões tocando-se apenas por vértice ou auto-interseção)."
            else:
                return False, [], False, 0.0, -1, "Perímetro aberto na borda da malha. O contorno precisa ser um ciclo fechado."

    # Ordena o ciclo de vértices
    start_v = next(iter(vert_to_edges.keys()))
    ordered_verts = [start_v]
    current_v = start_v
    current_e = vert_to_edges[current_v][0]

    while True:
        next_v = current_e.verts[0] if current_e.verts[1] == current_v else current_e.verts[1]
        if next_v == start_v:
            break
        ordered_verts.append(next_v)
        edges_of_next = vert_to_edges[next_v]
        next_e = edges_of_next[0] if edges_of_next[0] != current_e else edges_of_next[1]
        current_v = next_v
        current_e = next_e

    if len(ordered_verts) != len(vert_to_edges):
        return False, [], False, 0.0, -1, "A seleção possui múltiplos ciclos ou furos internos. Selecione uma região contígua simples."

    coords_world = [obj.matrix_world @ v.co for v in ordered_verts]
    centroid = sum(coords_world, Vector()) / len(coords_world)

    # Normal via Newell
    n = Vector((0.0, 0.0, 0.0))
    n_pts = len(coords_world)
    for i in range(n_pts):
        v1 = coords_world[i]
        v2 = coords_world[(i + 1) % n_pts]
        n.x += (v1.y - v2.y) * (v1.z + v2.z)
        n.y += (v1.z - v2.z) * (v1.x + v2.x)
        n.z += (v1.x - v2.x) * (v1.y + v2.y)

    if n.length > 1e-7:
        n.normalize()
    else:
        return False, [], False, 0.0, -1, "Contorno degenerado (área nula)."

    max_deviation_bu = max(abs((v - centroid).dot(n)) for v in coords_world)
    actual_scene = scene if scene else (bpy.context.scene if hasattr(bpy.context, "scene") else None)
    scale_to_mm = get_scene_scale_to_mm(actual_scene)
    max_deviation_mm = max_deviation_bu * scale_to_mm
    is_planar = max_deviation_mm <= 0.1

    indices = [v.index for v in ordered_verts]
    return True, indices, is_planar, max_deviation_mm, seed_face_idx, ""


def get_selected_seed_face(obj: bpy.types.Object) -> int:
    """Obtém a face ativa ou a primeira face selecionada no modo de edição."""
    if not obj or obj.mode != 'EDIT':
        return -1

    bm = bmesh.from_edit_mesh(obj.data)
    active_face = bm.faces.active
    if active_face and active_face.select:
        return active_face.index

    for f in bm.faces:
        if f.select:
            return f.index

    return -1


def slice_mesh_by_loop(
    obj: bpy.types.Object,
    target_name: str,
    indices: List[int],
    seed_face_idx: int,
    scene: Optional[bpy.types.Scene] = None,
    detach_add_base: bool = False,
    detach_base_depth_mm: float = 0.0,
    detach_base_clearance_mm: float = 0.0,
) -> LoopSliceResult:
    """Realiza a separação da malha usando o contorno (loop) capturado.
    
    Processa a geometria inteiramente no espaço de mundo (World Space).
    Garante malhas manifold em Parte A e Parte B com interface compartilhada idêntica.
    Retorna LoopSliceResult(bm_a, bm_b, split_result).
    """
    scale_to_mm = get_scene_scale_to_mm(scene) if scene else 1000.0

    matrix_world = obj.matrix_world.copy()
    det = matrix_world.determinant()
    if abs(det) < 1e-9:
        raise ValueError("A matriz de transformação do objeto é singular (escala nula).")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    if seed_face_idx < 0 or seed_face_idx >= len(bm.faces):
        bm.free()
        raise ValueError("Face-semente inválida ou não encontrada.")

    for idx in indices:
        if idx < 0 or idx >= len(bm.verts):
            bm.free()
            raise ValueError("Topologia alterada. Um vértice do loop não existe mais.")

    # Mapeia as arestas do contorno
    loop_verts_local = [bm.verts[idx] for idx in indices]
    loop_edges = set()
    n_loop = len(loop_verts_local)
    for i in range(n_loop):
        v1 = loop_verts_local[i]
        v2 = loop_verts_local[(i + 1) % n_loop]
        edge = bm.edges.get((v1, v2))
        if not edge:
            bm.free()
            raise ValueError("O ciclo de arestas não existe mais na malha (Topologia alterada).")
        loop_edges.add(edge)

    # Valida integridade do modelo de entrada: não fecha aberturas prévias fora do loop (B03)
    pre_open_edges = [e for e in bm.edges if e.is_boundary and e not in loop_edges]
    if pre_open_edges:
        bm.free()
        raise ValueError(
            "O modelo de entrada possui aberturas/arestas não-manifold fora do contorno selecionado. "
            "Corrija a malha de entrada antes de realizar o corte por contorno."
        )

    # Flood fill para coletar todas as faces pertencentes à Parte A (região da semente)
    seed_face = bm.faces[seed_face_idx]
    faces_a = set()
    queue = [seed_face]
    faces_a.add(seed_face)

    while queue:
        curr_face = queue.pop(0)
        for edge in curr_face.edges:
            if edge in loop_edges:
                continue
            for adj_face in edge.link_faces:
                if adj_face not in faces_a:
                    faces_a.add(adj_face)
                    queue.append(adj_face)

    if len(faces_a) == len(bm.faces):
        bm.free()
        raise ValueError("O loop não separa a malha em duas regiões (Exemplo: está numa alça).")

    if len(faces_a) == 0:
        bm.free()
        raise ValueError("A região da Parte A ficou vazia.")

    faces_b = set(bm.faces) - faces_a

    # Coleta coordenadas mundiais originais dos vértices do loop
    loop_coords_world = [matrix_world @ v.co for v in loop_verts_local]

    # Transforma o snapshot para World Space uma única vez
    bm.transform(matrix_world)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Cria BMesh da Parte A
    bm_a = bm.copy()
    bm_a.verts.ensure_lookup_table()
    bm_a.faces.ensure_lookup_table()
    loop_verts_a = [bm_a.verts[idx] for idx in indices]
    faces_to_delete_in_a = [bm_a.faces[f.index] for f in faces_b]
    bmesh.ops.delete(bm_a, geom=faces_to_delete_in_a, context='FACES')

    # Cria BMesh da Parte B
    bm_b = bm.copy()
    bm_b.verts.ensure_lookup_table()
    bm_b.faces.ensure_lookup_table()
    loop_verts_b = [bm_b.verts[idx] for idx in indices]
    faces_to_delete_in_b = [bm_b.faces[f.index] for f in faces_a]
    bmesh.ops.delete(bm_b, geom=faces_to_delete_in_b, context='FACES')

    bm.free()

    centroid_world = sum(loop_coords_world, Vector()) / len(loop_coords_world)
    n = Vector((0.0, 0.0, 0.0))
    n_pts = len(loop_coords_world)
    for i in range(n_pts):
        v1 = loop_coords_world[i]
        v2 = loop_coords_world[(i + 1) % n_pts]
        n.x += (v1.y - v2.y) * (v1.z + v2.z)
        n.y += (v1.z - v2.z) * (v1.x + v2.x)
        n.z += (v1.x - v2.x) * (v1.y + v2.y)
    if n.length > 1e-7:
        n.normalize()
    else:
        n = Vector((0.0, 0.0, 1.0))

    max_dev_bu = max(abs((v - centroid_world).dot(n)) for v in loop_coords_world)
    max_dev_mm = max_dev_bu * scale_to_mm

    u_vec, v_vec = _get_orthonormal_basis(n)
    pts_2d = [Vector(((v - centroid_world).dot(u_vec), (v - centroid_world).dot(v_vec))) for v in loop_coords_world]

    # Constrói superfície única de interface compartilhada via ear clipping (INV-005 / B01-B05)
    tri_indices = []
    try:
        tri_indices = triangulate_polygon_2d(pts_2d)
    except Exception:
        tri_indices = []

    created_faces_a = []
    created_faces_b = []

    if detach_add_base and detach_base_depth_mm > 0.0:
        analysis = analyze_loop_region(obj, indices, seed_face_idx, scene=scene)
        inward_dir = analysis["inward_dir_world"]
        max_avail_mm = analysis.get("max_avail_depth_mm", 0.0)
        if analysis.get("thickness_determined", False) and max_avail_mm > 0:
            if detach_base_depth_mm > (max_avail_mm + 1e-3):
                bm_a.free()
                bm_b.free()
                raise ValueError(
                    f"A profundidade da base ({detach_base_depth_mm:.1f} mm) ultrapassa a espessura da parede "
                    f"({max_avail_mm:.1f} mm). Reduza a profundidade da base."
                )

        depth_bu = detach_base_depth_mm / scale_to_mm
        # Folga (A04): aplicada na peca extraida A (fundo da base encolhido), cavidade B nominal.
        # Boca sem folga; folga cresce com a profundidade, sem rebaixo (encaixe sem prender).
        clearance_bu = max(0.0, detach_base_clearance_mm) / scale_to_mm
        vert_offsets_3d = []
        if clearance_bu > 1e-6:
            area2 = sum(pts_2d[i].x * pts_2d[(i + 1) % n_loop].y - pts_2d[(i + 1) % n_loop].x * pts_2d[i].y for i in range(n_loop))
            is_ccw = area2 > 0
            for i in range(n_loop):
                p_prev = pts_2d[(i - 1) % n_loop]
                p_curr = pts_2d[i]
                p_next = pts_2d[(i + 1) % n_loop]
                d1 = (p_curr - p_prev).normalized() if (p_curr - p_prev).length > 1e-7 else Vector((1.0, 0.0))
                d2 = (p_next - p_curr).normalized() if (p_next - p_curr).length > 1e-7 else Vector((1.0, 0.0))
                n1 = Vector((d1.y, -d1.x)) if is_ccw else Vector((-d1.y, d1.x))
                n2 = Vector((d2.y, -d2.x)) if is_ccw else Vector((-d2.y, d2.x))
                n_sum = n1 + n2
                n_avg = n_sum.normalized() if n_sum.length > 1e-6 else n1
                cos_half = max(0.5, n_avg.dot(n1))
                scale_fac = min(2.0, 1.0 / cos_half)
                offset_3d = (n_avg.x * u_vec + n_avg.y * v_vec) * (clearance_bu * scale_fac)
                vert_offsets_3d.append(offset_3d)
        else:
            vert_offsets_3d = [Vector((0.0, 0.0, 0.0)) for _ in range(n_loop)]

        new_verts_a = [bm_a.verts.new(v.co + inward_dir * depth_bu - vert_offsets_3d[i]) for i, v in enumerate(loop_verts_a)]
        bm_a.verts.ensure_lookup_table()
        for i in range(n_loop):
            i_next = (i + 1) % n_loop
            try:
                fa = bm_a.faces.new((loop_verts_a[i], new_verts_a[i], new_verts_a[i_next], loop_verts_a[i_next]))
                created_faces_a.append(fa)
            except Exception:
                try:
                    fa = bm_a.faces.new((loop_verts_a[i], loop_verts_a[i_next], new_verts_a[i_next], new_verts_a[i]))
                    created_faces_a.append(fa)
                except Exception:
                    pass

        for i, j, k in tri_indices:
            try:
                fa = bm_a.faces.new((new_verts_a[i], new_verts_a[k], new_verts_a[j]))
                created_faces_a.append(fa)
            except ValueError:
                try:
                    fa = bm_a.faces.new((new_verts_a[i], new_verts_a[j], new_verts_a[k]))
                    created_faces_a.append(fa)
                except Exception:
                    pass

        new_verts_b = [bm_b.verts.new(v.co + inward_dir * depth_bu) for i, v in enumerate(loop_verts_b)]
        bm_b.verts.ensure_lookup_table()
        for i in range(n_loop):
            i_next = (i + 1) % n_loop
            try:
                fb = bm_b.faces.new((loop_verts_b[i], loop_verts_b[i_next], new_verts_b[i_next], new_verts_b[i]))
                created_faces_b.append(fb)
            except Exception:
                try:
                    fb = bm_b.faces.new((loop_verts_b[i], new_verts_b[i], new_verts_b[i_next], loop_verts_b[i_next]))
                    created_faces_b.append(fb)
                except Exception:
                    pass

        for i, j, k in tri_indices:
            try:
                fb = bm_b.faces.new((new_verts_b[i], new_verts_b[j], new_verts_b[k]))
                created_faces_b.append(fb)
            except ValueError:
                try:
                    fb = bm_b.faces.new((new_verts_b[i], new_verts_b[k], new_verts_b[j]))
                    created_faces_b.append(fb)
                except Exception:
                    pass
    else:
        # Fechamento direto no plano do contorno
        if tri_indices:
            for i, j, k in tri_indices:
                va = (loop_verts_a[i], loop_verts_a[j], loop_verts_a[k])
                try:
                    fa = bm_a.faces.new(va)
                    created_faces_a.append(fa)
                except ValueError:
                    try:
                        fa = bm_a.faces.new((va[0], va[2], va[1]))
                        created_faces_a.append(fa)
                    except Exception:
                        pass

                vb = (loop_verts_b[i], loop_verts_b[k], loop_verts_b[j])
                try:
                    fb = bm_b.faces.new(vb)
                    created_faces_b.append(fb)
                except ValueError:
                    try:
                        fb = bm_b.faces.new((vb[0], vb[2], vb[1]))
                        created_faces_b.append(fb)
                    except Exception:
                        pass

    # Fallback estrito apenas para arestas do contorno remanescentes
    bm_a.edges.ensure_lookup_table()
    bm_b.edges.ensure_lookup_table()
    rem_a = [e for e in bm_a.edges if e.is_boundary]
    rem_b = [e for e in bm_b.edges if e.is_boundary]

    if rem_a:
        res_a = bmesh.ops.holes_fill(bm_a, edges=rem_a, sides=len(rem_a))
        c_a = res_a.get("faces", [])
        if not c_a:
            res_a = bmesh.ops.edgenet_fill(bm_a, edges=rem_a)
            c_a = res_a.get("faces", [])
        created_faces_a.extend(c_a)

    if rem_b:
        res_b = bmesh.ops.holes_fill(bm_b, edges=rem_b, sides=len(rem_b))
        c_b = res_b.get("faces", [])
        if not c_b:
            res_b = bmesh.ops.edgenet_fill(bm_b, edges=rem_b)
            c_b = res_b.get("faces", [])
        created_faces_b.extend(c_b)

    # Verificação estrita de fechamento (B01 / B05): nunca publica peças com arestas abertas
    bm_a.edges.ensure_lookup_table()
    bm_b.edges.ensure_lookup_table()
    open_edges_a = [e for e in bm_a.edges if e.is_boundary]
    open_edges_b = [e for e in bm_b.edges if e.is_boundary]

    if open_edges_a or open_edges_b:
        n_open = max(len(open_edges_a), len(open_edges_b))
        bm_a.free()
        bm_b.free()
        raise ValueError(
            f"Não foi possível fechar o contorno do loop (restaram {n_open} arestas abertas). "
            f"O contorno possui desvio não-planar de {max_dev_mm:.2f} mm e não é compatível com fechamento direto. "
            f"Selecione um contorno planar ou na ligação da base."
        )

    # Herança de materiais (A10): faces novas sem vizinho antigo herdam por propagação
    # a partir das faces novas já resolvidas, evitando ficar no índice inicial.
    def _inherit_cap_materials(created):
        created = [f for f in created if f.is_valid]
        if not created:
            return
        created_set = set(created)
        resolved = set()
        for f in created:
            adj = [lf.material_index for e in f.edges for lf in e.link_faces if lf not in created_set]
            if adj:
                f.material_index = max(set(adj), key=adj.count)
                resolved.add(f)
        pending = [f for f in created if f not in resolved]
        while pending and resolved:
            progressed = False
            for f in list(pending):
                adj = [lf.material_index for e in f.edges for lf in e.link_faces
                       if lf in resolved]
                if adj:
                    f.material_index = max(set(adj), key=adj.count)
                    resolved.add(f)
                    pending.remove(f)
                    progressed = True
            if not progressed:
                break

    _inherit_cap_materials(created_faces_a)
    _inherit_cap_materials(created_faces_b)

    # Recalcula normais da Parte A e Parte B (garante orientação externa no sólido manifold)
    bmesh.ops.recalc_face_normals(bm_a, faces=bm_a.faces[:])
    bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces[:])

    # Determina a normal da interface que aponta DE A PARA B
    if detach_add_base and detach_base_depth_mm > 0.0:
        normal_a_to_b = inward_dir
    elif created_faces_a:
        valid_caps = [f for f in created_faces_a if f.is_valid]
        if valid_caps:
            avg_cap_norm = sum((f.normal for f in valid_caps), Vector()) / len(valid_caps)
            if avg_cap_norm.length > 1e-5:
                normal_a_to_b = avg_cap_norm.normalized()
            else:
                normal_a_to_b = n
        else:
            normal_a_to_b = n
    else:
        normal_a_to_b = n

    # Constrói CutInterface formal em World Space
    # A03: com base adicional, a interface efetiva de contato é o fundo da base
    # (deslocado por inward_dir * profundidade), não o contorno original no topo.
    iface_offset = Vector((0.0, 0.0, 0.0))
    if detach_add_base and detach_base_depth_mm > 0.0:
        iface_offset = inward_dir.normalized() * (detach_base_depth_mm / scale_to_mm)
    iface_loop_coords = [Vector(c) + iface_offset for c in loop_coords_world]
    iface_origin = Vector(centroid_world) + iface_offset
    iface_tris = [
        (iface_loop_coords[i], iface_loop_coords[j], iface_loop_coords[k])
        for i, j, k in tri_indices
    ] if tri_indices else None

    cut_interface = build_cut_interface(
        origin_world=iface_origin,
        normal_a_to_b=normal_a_to_b,
        boundary_points_world=iface_loop_coords,
        interface_triangles=iface_tris,
        unit_scale=scale_to_mm,
        source_mode="LOOP",
    )

    metrics_a = evaluate_bmesh_metrics(bm_a, unit_scale=scale_to_mm)
    metrics_b = evaluate_bmesh_metrics(bm_b, unit_scale=scale_to_mm)

    split_result = SplitResult(
        part_a_metrics=metrics_a,
        part_b_metrics=metrics_b,
        interface=cut_interface,
        diagnostics_before_connectors={
            "sum_volume_mm3": metrics_a["volume_mm3"] + metrics_b["volume_mm3"],
            "interface_width_mm": cut_interface.width_mm,
            "interface_height_mm": cut_interface.height_mm,
            "is_planar": cut_interface.is_planar,
            "deviation_mm": cut_interface.deviation_mm,
        },
        success=True,
    )

    return LoopSliceResult(bm_a, bm_b, split_result)


def analyze_loop_region(
    obj: bpy.types.Object,
    indices: List[int],
    seed_face_idx: int,
    scene: Optional[bpy.types.Scene] = None,
) -> Dict[str, Any]:
    """Analisa a região delimitada pelo loop para decisão automática entre DETACH e EXTRUDE."""
    scale_to_mm = get_scene_scale_to_mm(scene) if scene else 1000.0
    matrix_world = obj.matrix_world.copy()

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    if seed_face_idx < 0 or seed_face_idx >= len(bm.faces):
        bm.free()
        raise ValueError("Face-semente inválida ou não selecionada.")

    # Mapeia as arestas do contorno
    loop_verts_local = [bm.verts[idx] for idx in indices]
    loop_edges = set()
    n_loop = len(loop_verts_local)
    for i in range(n_loop):
        v1 = loop_verts_local[i]
        v2 = loop_verts_local[(i + 1) % n_loop]
        edge = bm.edges.get((v1, v2))
        if edge:
            loop_edges.add(edge)

    # Flood fill para coletar faces de A
    seed_face = bm.faces[seed_face_idx]
    faces_a = set()
    queue = [seed_face]
    faces_a.add(seed_face)

    while queue:
        curr_face = queue.pop(0)
        for edge in curr_face.edges:
            if edge in loop_edges:
                continue
            for adj_face in edge.link_faces:
                if adj_face not in faces_a:
                    faces_a.add(adj_face)
                    queue.append(adj_face)

    loop_coords_world = [matrix_world @ v.co for v in loop_verts_local]
    centroid = sum(loop_coords_world, Vector()) / len(loop_coords_world)

    # Normal média do loop via Newell
    n = Vector((0.0, 0.0, 0.0))
    n_pts = len(loop_coords_world)
    for i in range(n_pts):
        v1 = loop_coords_world[i]
        v2 = loop_coords_world[(i + 1) % n_pts]
        n.x += (v1.y - v2.y) * (v1.z + v2.z)
        n.y += (v1.z - v2.z) * (v1.x + v2.x)
        n.z += (v1.x - v2.x) * (v1.y + v2.y)
    if n.length > 1e-6:
        n.normalize()
    else:
        n = Vector((0.0, 0.0, 1.0))

    # Determina a direção para dentro do sólido
    normal_matrix = matrix_world.to_3x3().inverted().transposed()
    seed_norm_world = (normal_matrix @ seed_face.normal).normalized()

    # Prepara BVHTree no espaço de mundo para testar direção e espessura da parede
    bm_bvh = bm.copy()
    bm_bvh.transform(matrix_world)
    bvh = BVHTree.FromBMesh(bm_bvh)

    # Inward candidato primário: o oposto da normal externa da face semente
    cand_inward = -seed_norm_world
    hit_c1, _, _, _ = bvh.ray_cast(centroid + cand_inward * 1e-4, cand_inward)
    hit_c2, _, _, _ = bvh.ray_cast(centroid - cand_inward * 1e-4, -cand_inward)

    if hit_c1 is not None and hit_c2 is None:
        inward_dir = cand_inward
    elif hit_c2 is not None and hit_c1 is None:
        inward_dir = -cand_inward
    elif hit_c1 is not None and hit_c2 is not None:
        # Ambos intersectam: escolhe o que penetra no sólido a partir da face semente
        inward_dir = cand_inward
    else:
        inward_dir = cand_inward

    # Analisa relevo (altura) dos vértices da região A em relação ao plano do loop
    verts_a = set(v for f in faces_a for v in f.verts)
    coords_a_world = [matrix_world @ v.co for v in verts_a]
    outward_dir = -inward_dir
    heights = [(p - centroid).dot(outward_dir) for p in coords_a_world]
    max_h = max(heights) if heights else 0.0
    min_h = min(heights) if heights else 0.0
    span_h_bu = max_h - min_h
    span_h_mm = span_h_bu * scale_to_mm

    # Avalia espessura disponível na direção inward via BVHTree (E02 / E03)
    offset_bu = max(1e-7, 0.01 / scale_to_mm)
    min_wall_depth_bu = 1e9
    sampled_hits = 0
    test_points = [centroid] + loop_coords_world
    for pt in test_points:
        ray_start = pt + inward_dir * offset_bu
        hit_loc, hit_norm, hit_idx, hit_dist = bvh.ray_cast(ray_start, inward_dir)
        if hit_loc is not None:
            dist = (hit_loc - pt).length
            sampled_hits += 1
            if dist < min_wall_depth_bu:
                min_wall_depth_bu = dist

    bm_bvh.free()
    bm.free()

    thickness_determined = (min_wall_depth_bu < 1e8 and sampled_hits > 0)
    max_avail_depth_mm = (min_wall_depth_bu * scale_to_mm) if thickness_determined else 0.0
    thickness_status = "MEASURED" if thickness_determined else "INCONCLUSIVE"

    can_close_loop = True
    u_chk, v_chk = _get_orthonormal_basis(n)
    pts_2d_chk = [Vector(((v - centroid).dot(u_chk), (v - centroid).dot(v_chk))) for v in loop_coords_world]
    try:
        t_chk = triangulate_polygon_2d(pts_2d_chk)
        if not t_chk:
            can_close_loop = False
    except Exception:
        can_close_loop = False

    max_dev_loop_bu = max(abs((v - centroid).dot(n)) for v in loop_coords_world)
    max_dev_loop_mm = max_dev_loop_bu * scale_to_mm
    is_planar_loop = (max_dev_loop_mm <= 0.1)

    if span_h_mm < 0.2:
        detected_mode = 'EXTRUDE'
        reason = (
            f"Região plana detectada (desvio de relevo: {span_h_mm:.2f} mm). "
            f"Requer profundidade de extração para gerar peça sólida."
        )
        is_planar_region = True
    else:
        detected_mode = 'DETACH'
        if not can_close_loop and not is_planar_loop:
            reason = (
                f"Saliência 3D com contorno não-planar (desvio: {max_dev_loop_mm:.2f} mm). "
                f"Aviso: Fechamento direto não suportado para este contorno. "
                f"Recomenda-se selecionar um contorno na base plana."
            )
        else:
            reason = (
                f"Saliência 3D detectada (altura saliente: {span_h_mm:.2f} mm). "
                f"Destacando volume pela interface do contorno."
            )
        is_planar_region = False

    return {
        "detected_mode": detected_mode,
        "reason": reason,
        "protrusion_height_mm": max(0.0, max_h * scale_to_mm),
        "is_planar_region": is_planar_region,
        "inward_dir_world": inward_dir,
        "loop_normal_world": n,
        "centroid_world": centroid,
        "thickness_determined": thickness_determined,
        "thickness_status": thickness_status,
        "thickness_sampled_points": len(test_points),
        "thickness_hit_count": sampled_hits,
        "max_avail_depth_mm": max_avail_depth_mm,
        "coords_world": loop_coords_world,
    }


def _get_orthonormal_basis(normal: Vector) -> Tuple[Vector, Vector]:
    """Retorna dois vetores unitários ortogonais à normal fornecida."""
    n = normal.normalized()
    if abs(n.z) < 0.9:
        u = n.cross(Vector((0.0, 0.0, 1.0))).normalized()
    else:
        u = n.cross(Vector((0.0, 1.0, 0.0))).normalized()
    v = n.cross(u).normalized()
    return u, v


def triangulate_polygon_2d(pts_2d: List[Vector]) -> List[Tuple[int, int, int]]:
    """Triangulação estrita 2D via Constrained Delaunay Triangulation (CDT) e Ear Clipping (DEV-06 / B05 / V01).
    
    Garante que 100% dos triângulos fiquem dentro do domínio do polígono,
    inclusive em formas côncavas (L, U, etc.), eliminando triângulos degenerados (área zero)
    mesmo em contornos com vértices colineares intermediários (12, 20, 40+ vértices).
    """
    n = len(pts_2d)
    if n < 3:
        return []
    
    pts_vec = [Vector((p[0], p[1])) if not hasattr(p, 'x') else Vector((p.x, p.y)) for p in pts_2d]

    # 1. Área orientada via Shoelace
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts_vec[i].x * pts_vec[j].y - pts_vec[j].x * pts_vec[i].y
    area *= 0.5

    if abs(area) < 1e-12:
        return []

    if n == 3:
        return [(0, 1, 2)] if area > 0 else [(0, 2, 1)]

    is_ccw = (area > 0.0)

    # 2. Triangulação nativa restrita via mathutils.geometry.delaunay_2d_cdt (R1 / DEV-06)
    try:
        import mathutils
        edges = [(i, (i + 1) % n) for i in range(n)]
        face_poly = [list(range(n))] if is_ccw else [list(reversed(range(n)))]
        out_verts, out_edges, out_faces, orig_v, orig_e, orig_f = mathutils.geometry.delaunay_2d_cdt(
            pts_vec, edges, face_poly, 1, 1e-6
        )
        cdt_tris = []
        for f in out_faces:
            if len(f) != 3:
                continue
            idx0 = orig_v[f[0]][0] if orig_v[f[0]] else f[0]
            idx1 = orig_v[f[1]][0] if orig_v[f[1]] else f[1]
            idx2 = orig_v[f[2]][0] if orig_v[f[2]] else f[2]
            if idx0 == idx1 or idx1 == idx2 or idx2 == idx0:
                continue
            # A11: garante que índices mapeados estão estritamente dentro dos vértices da borda
            if idx0 >= n or idx1 >= n or idx2 >= n:
                continue
            p0, p1, p2 = pts_vec[idx0], pts_vec[idx1], pts_vec[idx2]
            tri_signed = 0.5 * ((p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y))
            if abs(tri_signed) < 1e-12:
                continue
            if is_ccw:
                tri = (idx0, idx1, idx2) if tri_signed > 0 else (idx0, idx2, idx1)
            else:
                tri = (idx0, idx2, idx1) if tri_signed > 0 else (idx0, idx1, idx2)
            cdt_tris.append(tri)
        # Validação estrita de cobertura integral de área do polígono (sem perdas nem Steiner externos)
        sum_cdt_area = sum(0.5 * abs((pts_vec[t[1]].x - pts_vec[t[0]].x) * (pts_vec[t[2]].y - pts_vec[t[0]].y) - (pts_vec[t[2]].x - pts_vec[t[0]].x) * (pts_vec[t[1]].y - pts_vec[t[0]].y)) for t in cdt_tris)
        if len(cdt_tris) >= (n - 2) and abs(sum_cdt_area - abs(area)) / abs(area) < 1e-3:
            return cdt_tris
    except Exception:
        pass

    # 3. Fallback: Ear Clipping com filtragem estrita de degenerações
    indices = list(range(n)) if is_ccw else list(reversed(range(n)))
    poly = [pts_vec[i] for i in indices]

    corners = []
    m_len = len(poly)
    for i in range(m_len):
        p_prev = poly[(i - 1) % m_len]
        p_curr = poly[i]
        p_next = poly[(i + 1) % m_len]

        v1 = p_curr - p_prev
        v2 = p_next - p_curr
        l1 = v1.length
        l2 = v2.length

        is_collinear = False
        if l1 > 1e-9 and l2 > 1e-9:
            cp = v1.x * v2.y - v1.y * v2.x
            dp = v1.x * v2.x + v1.y * v2.y
            if abs(cp) / (l1 * l2) < 1e-5 and dp > 0:
                is_collinear = True

        if not is_collinear:
            corners.append(i)

    if len(corners) < 3:
        corners = list(range(m_len))

    edge_intermediates = {}
    num_corners = len(corners)
    for c_i in range(num_corners):
        c_curr = corners[c_i]
        c_next = corners[(c_i + 1) % num_corners]

        inter = []
        if c_next > c_curr:
            for k in range(c_curr + 1, c_next):
                inter.append(indices[k])
        else:
            for k in range(c_curr + 1, m_len):
                inter.append(indices[k])
            for k in range(0, c_next):
                inter.append(indices[k])
        edge_intermediates[(indices[c_curr], indices[c_next])] = inter

    corner_indices = [indices[c] for c in corners]

    def is_point_in_tri(pt: Vector, a: Vector, b: Vector, c: Vector) -> bool:
        v0 = c - a
        v1 = b - a
        v2 = pt - a
        dot00 = v0.dot(v0)
        dot01 = v0.dot(v1)
        dot02 = v0.dot(v2)
        dot11 = v1.dot(v1)
        dot12 = v1.dot(v2)
        denom = dot00 * dot11 - dot01 * dot01
        if abs(denom) < 1e-12:
            return False
        inv_denom = 1.0 / denom
        u = (dot11 * dot02 - dot01 * dot12) * inv_denom
        v = (dot00 * dot12 - dot01 * dot02) * inv_denom
        return (u > 1e-5) and (v > 1e-5) and (u + v < 1.0 - 1e-5)

    def is_convex(p_prev: Vector, p_curr: Vector, p_next: Vector) -> bool:
        cp = (p_curr.x - p_prev.x) * (p_next.y - p_curr.y) - (p_curr.y - p_prev.y) * (p_next.x - p_curr.x)
        return cp > 1e-8

    cur_c_indices = list(corner_indices)
    corner_triangles = []
    it = 0
    max_it = len(cur_c_indices) * len(cur_c_indices) * 2

    while len(cur_c_indices) > 3 and it < max_it:
        it += 1
        ear_found = False
        cm = len(cur_c_indices)
        for i in range(cm):
            idx_prev = cur_c_indices[(i - 1) % cm]
            idx_curr = cur_c_indices[i]
            idx_next = cur_c_indices[(i + 1) % cm]

            p_prev = pts_vec[idx_prev]
            p_curr = pts_vec[idx_curr]
            p_next = pts_vec[idx_next]

            if not is_convex(p_prev, p_curr, p_next):
                continue

            has_pt = False
            for k in range(cm):
                if k in ((i - 1) % cm, i, (i + 1) % cm):
                    continue
                pt = pts_vec[cur_c_indices[k]]
                if is_point_in_tri(pt, p_prev, p_curr, p_next):
                    has_pt = True
                    break

            if not has_pt:
                corner_triangles.append((idx_prev, idx_curr, idx_next))
                cur_c_indices.pop(i)
                ear_found = True
                break

        if not ear_found:
            corner_triangles.append((cur_c_indices[0], cur_c_indices[1], cur_c_indices[2]))
            cur_c_indices.pop(1)

    if len(cur_c_indices) == 3:
        corner_triangles.append((cur_c_indices[0], cur_c_indices[1], cur_c_indices[2]))

    final_triangles = []
    for tri in corner_triangles:
        sub_tris = [tri]
        for e_pair, inter_pts in edge_intermediates.items():
            if not inter_pts:
                continue
            v_start, v_end = e_pair

            new_sub_tris = []
            for st in sub_tris:
                a, b, c = st
                found_edge = False
                for p1, p2, p_opp in ((a, b, c), (b, c, a), (c, a, b)):
                    if (p1 == v_start and p2 == v_end) or (p1 == v_end and p2 == v_start):
                        found_edge = True
                        chain = [p1] + (inter_pts if p1 == v_start else list(reversed(inter_pts))) + [p2]
                        for ch_i in range(len(chain) - 1):
                            new_sub_tris.append((chain[ch_i], chain[ch_i + 1], p_opp))
                        break
                if not found_edge:
                    new_sub_tris.append(st)
            sub_tris = new_sub_tris

        final_triangles.extend(sub_tris)

    # Filtra triângulos degenerados (área zero)
    valid_final = []
    for t in final_triangles:
        p0, p1, p2 = pts_vec[t[0]], pts_vec[t[1]], pts_vec[t[2]]
        t_area = 0.5 * abs((p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y))
        if t_area > 1e-12:
            valid_final.append(t)

    if not is_ccw:
        valid_final = [(t[0], t[2], t[1]) for t in valid_final]

    return valid_final


def create_loop_prism_cutter(
    coords_world: List[Vector],
    inward_dir: Vector,
    depth_bu: float,
    outward_ext_bu: float = 1e-3,
    name: str = "temp_loop_prism",
) -> bpy.types.Object:
    """Constrói um prisma 3D fechado e manifold a partir de um contorno de coordenadas mundiais (B05)."""
    bm = bmesh.new()
    in_norm = inward_dir.normalized()

    # Remove pontos colineares para evitar triângulos degenerados
    pts = list(coords_world)
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            p_prev, p, p_next = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            d1 = p - p_prev
            d2 = p_next - p
            if d1.length < 1e-9 or d2.length < 1e-9 or d1.normalized().cross(d2.normalized()).length < 1e-5:
                pts.pop(i)
                changed = True
                break
    coords_world = pts
    n = len(coords_world)

    # Projeta contorno para base 2D ortogonal para triangulação Ear Clipping
    u_vec, v_vec = _get_orthonormal_basis(in_norm)
    pts_2d = [Vector((p.dot(u_vec), p.dot(v_vec))) for p in coords_world]
    triangles_2d = triangulate_polygon_2d(pts_2d)

    top_verts = [bm.verts.new(p - outward_ext_bu * in_norm) for p in coords_world]
    bot_verts = [bm.verts.new(p + depth_bu * in_norm) for p in coords_world]
    bm.verts.ensure_lookup_table()

    # Paredes laterais
    for i in range(n):
        i_next = (i + 1) % n
        bm.faces.new((top_verts[i], top_verts[i_next], bot_verts[i_next], bot_verts[i]))

    # Tampas superior e inferior trianguladas estritamente dentro do domínio côncavo (B05)
    for t in triangles_2d:
        # Tampa superior: normal para fora (contra inward_dir)
        bm.faces.new((top_verts[t[2]], top_verts[t[1]], top_verts[t[0]]))
        # Tampa inferior: normal para fora (a favor de inward_dir)
        bm.faces.new((bot_verts[t[0]], bot_verts[t[1]], bot_verts[t[2]]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.hide_viewport = False
    obj.hide_render = False
    bpy.context.scene.collection.objects.link(obj)
    return obj


def slice_mesh_by_loop_extrude(
    obj: bpy.types.Object,
    target_name: str,
    indices: List[int],
    seed_face_idx: int,
    depth_mm: float,
    through_cut: bool = False,
    scene: Optional[bpy.types.Scene] = None,
) -> LoopSliceResult:
    """Corta o modelo extraindo o volume delimitado pelo contorno até a profundidade especificada.
    
    Parte A = volume extraído (prisma ∩ target)
    Parte B = restante do modelo (target \\ prisma)
    """
    actual_scene = scene if scene else bpy.context.scene
    scale_to_mm = get_scene_scale_to_mm(actual_scene)

    analysis = analyze_loop_region(obj, indices, seed_face_idx, scene=actual_scene)
    max_avail_mm = analysis["max_avail_depth_mm"]

    # Validação de espessura (T09)
    if not analysis.get("thickness_determined", True) and not through_cut:
        raise ValueError(
            "Espessura da peça não pôde ser determinada no ponto selecionado. "
            "Defina a profundidade manualmente ou ative a opção 'Corte Passante'."
        )

    if depth_mm > (max_avail_mm + 1e-3) and not through_cut:
        raise ValueError(
            f"A profundidade de extração ({depth_mm:.1f} mm) ultrapassa a espessura da peça "
            f"({max_avail_mm:.1f} mm). Reduza a profundidade ou ative a opção 'Corte Passante'."
        )

    coords_world = analysis["coords_world"]
    inward_dir = analysis["inward_dir_world"]
    depth_bu = depth_mm / scale_to_mm

    protrusion_h_bu = analysis["protrusion_height_mm"] / scale_to_mm
    outward_ext_bu = max(0.5 / scale_to_mm, protrusion_h_bu + 0.5 / scale_to_mm)

    if through_cut and depth_mm >= max_avail_mm:
        depth_bu = max(depth_bu, (max_avail_mm / scale_to_mm) + (1.0 / scale_to_mm))

    prism_obj = None
    temp_obj_a = None
    temp_obj_b = None
    eval_obj_a = None
    eval_obj_b = None
    eval_a = None
    eval_b = None

    try:
        prism_obj = create_loop_prism_cutter(
            coords_world=coords_world,
            inward_dir=inward_dir,
            depth_bu=depth_bu,
            outward_ext_bu=outward_ext_bu,
            name=f"{target_name}_loop_prism",
        )

        bpy.context.view_layer.update()

        temp_obj_a = obj.copy()
        temp_obj_a.data = obj.data.copy()
        temp_obj_a.hide_viewport = False
        temp_obj_a.hide_render = False
        actual_scene.collection.objects.link(temp_obj_a)
        mod_a = temp_obj_a.modifiers.new(name="Extrude_Intersect", type='BOOLEAN')
        mod_a.operation = 'INTERSECT'
        mod_a.solver = 'EXACT'
        mod_a.object = prism_obj

        temp_obj_b = obj.copy()
        temp_obj_b.data = obj.data.copy()
        temp_obj_b.hide_viewport = False
        temp_obj_b.hide_render = False
        actual_scene.collection.objects.link(temp_obj_b)
        mod_b = temp_obj_b.modifiers.new(name="Extrude_Difference", type='BOOLEAN')
        mod_b.operation = 'DIFFERENCE'
        mod_b.solver = 'EXACT'
        mod_b.object = prism_obj

        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()

        eval_obj_a = temp_obj_a.evaluated_get(dg)
        eval_a = eval_obj_a.to_mesh()

        eval_obj_b = temp_obj_b.evaluated_get(dg)
        eval_b = eval_obj_b.to_mesh()

        bm_a = bmesh.new()
        bm_a.from_mesh(eval_a)
        bm_a.transform(temp_obj_a.matrix_world)

        bm_b = bmesh.new()
        bm_b.from_mesh(eval_b)
        bm_b.transform(temp_obj_b.matrix_world)

        if len(bm_a.verts) == 0 or len(bm_b.verts) == 0:
            bm_a.free()
            bm_b.free()
            raise RuntimeError("A extração com profundidade gerou malha vazia para uma das partes.")

        bmesh.ops.recalc_face_normals(bm_a, faces=bm_a.faces[:])
        bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces[:])

        if through_cut:
            interface_origin = analysis["centroid_world"]
            interface_boundary = coords_world
        else:
            interface_origin = analysis["centroid_world"] + (depth_mm / scale_to_mm) * inward_dir
            interface_boundary = [p + (depth_mm / scale_to_mm) * inward_dir for p in coords_world]
        cut_interface = build_cut_interface(
            origin_world=interface_origin,
            normal_a_to_b=inward_dir,
            boundary_points_world=interface_boundary,
            unit_scale=scale_to_mm,
            source_mode="LOOP",
        )

        metrics_a = evaluate_bmesh_metrics(bm_a, unit_scale=scale_to_mm)
        metrics_b = evaluate_bmesh_metrics(bm_b, unit_scale=scale_to_mm)

        split_result = SplitResult(
            part_a_metrics=metrics_a,
            part_b_metrics=metrics_b,
            interface=cut_interface,
            diagnostics_before_connectors={
                "sum_volume_mm3": metrics_a["volume_mm3"] + metrics_b["volume_mm3"],
                "interface_width_mm": cut_interface.width_mm,
                "interface_height_mm": cut_interface.height_mm,
                "is_planar": True,
                "deviation_mm": 0.0,
            },
            success=True,
        )

        return LoopSliceResult(bm_a, bm_b, split_result)

    finally:
        # Liberação estrita no mesmo objeto avaliado que gerou o to_mesh (B03)
        if eval_obj_a and eval_a:
            try:
                eval_obj_a.to_mesh_clear()
            except Exception:
                pass
        if eval_obj_b and eval_b:
            try:
                eval_obj_b.to_mesh_clear()
            except Exception:
                pass

        for temp_o in (temp_obj_a, temp_obj_b):
            if temp_o:
                m_data = temp_o.data
                if temp_o.name in actual_scene.collection.objects:
                    actual_scene.collection.objects.unlink(temp_o)
                if temp_o.name in bpy.data.objects:
                    bpy.data.objects.remove(temp_o, do_unlink=True)
                if m_data and m_data.users == 0:
                    bpy.data.meshes.remove(m_data, do_unlink=True)

        if prism_obj:
            p_mesh = prism_obj.data
            if prism_obj.name in actual_scene.collection.objects:
                actual_scene.collection.objects.unlink(prism_obj)
            if prism_obj.name in bpy.data.objects:
                bpy.data.objects.remove(prism_obj, do_unlink=True)
            if p_mesh and p_mesh.users == 0:
                bpy.data.meshes.remove(p_mesh, do_unlink=True)
