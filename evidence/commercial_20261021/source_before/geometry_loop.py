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
from .localized_errors import LocalizedGeometryError
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
    
    # Draw handlers call validation too: never update Mesh datablocks here.
    # In Edit Mode read the live BMesh without switching mode or freeing it.
    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)
        v_count, e_count, f_count = len(bm.verts), len(bm.edges), len(bm.faces)
        edges = array.array('i', (v.index for e in bm.edges for v in e.verts))
        loops = array.array('i', (v.index for f in bm.faces for v in f.verts))
    else:
        mesh = obj.data
        v_count, e_count, f_count = len(mesh.vertices), len(mesh.edges), len(mesh.polygons)
        edges = array.array('i', [0]) * (e_count * 2)
        mesh.edges.foreach_get('vertices', edges)
        loops = array.array('i', [0]) * len(mesh.loops)
        mesh.loops.foreach_get('vertex_index', loops)
    h = hashlib.sha256()
    h.update(f"V{v_count}E{e_count}F{f_count}".encode('utf-8'))
    h.update(edges.tobytes())
    h.update(loops.tobytes())
    return f"V{v_count}E{e_count}F{f_count}H{h.hexdigest()[:8]}"



def clear_capture(settings: Any, reason: str = ""):
    """Limpa de forma atômica e segura todos os metadados de captura de loop."""
    if not settings:
        return
    settings.loop_is_captured = False
    settings.loop_vertex_count = 0
    settings.loop_vertex_indices = ""
    settings.loop_boundary_loops = ""
    settings.loop_region_face_indices = ""
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


def _capture_on_copy(obj, scene, capture):
    """Do not change the live Edit mesh until a repaired contour is valid."""
    live = bmesh.from_edit_mesh(obj.data)
    live.verts.index_update()
    live.edges.index_update()
    live.faces.index_update()
    work = live.copy()
    counts = (len(live.verts), len(live.edges), len(live.faces))
    try:
        result = capture(work, obj, scene)
        if result[0] and counts != (len(work.verts), len(work.edges), len(work.faces)):
            mesh = bpy.data.meshes.new('_splitter_validated_loop_capture')
            try:
                work.to_mesh(mesh)
                live.clear()
                live.from_mesh(mesh)
                live.verts.index_update()
                live.edges.index_update()
                live.faces.index_update()
                bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
            finally:
                bpy.data.meshes.remove(mesh)
        return result
    finally:
        work.free()


def _bridge_micro_selection_gaps(bm, selected_faces, obj, scale_to_mm):
    """Complete tiny omitted faces joining selected islands, without welding.

    Only an existing same-material patch <= 0.01 mm² and <= 0.05 mm wide
    may connect islands. Real separate bodies, large omissions and holes are
    still rejected by the usual single-cycle checks.
    """
    groups = {}
    group_count = 0
    for seed in sorted(selected_faces, key=lambda f: f.index):
        if seed in groups:
            continue
        group = group_count
        group_count += 1
        stack = [seed]
        groups[seed] = group
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for neighbor in edge.link_faces:
                    if neighbor in selected_faces and neighbor not in groups:
                        groups[neighbor] = group
                        stack.append(neighbor)
    if group_count <= 1:
        return selected_faces
    selected_materials = {f.material_index for f in selected_faces}
    candidates = {}
    for face in bm.faces:
        if face in selected_faces or face.material_index not in selected_materials:
            continue
        points = [obj.matrix_world @ v.co * scale_to_mm for v in face.verts]
        center = sum(points, Vector()) / len(points)
        area = sum(((a-center).cross(b-center) for a, b in zip(points, points[1:]+points[:1])), Vector()).length / 2
        longest = max((b-a).length for a, b in zip(points, points[1:]+points[:1]))
        if 0 < area <= .01 and longest > 0 and 2 * area / longest <= .05:
            candidates[face] = area
    remaining = set(candidates)
    completed = set(selected_faces)
    while remaining:
        seed = min(remaining, key=lambda f: f.index)
        remaining.remove(seed)
        patch = {seed}
        stack = [seed]
        touches = set()
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for neighbor in edge.link_faces:
                    if neighbor.material_index != seed.material_index:
                        continue
                    if neighbor in groups:
                        touches.add(groups[neighbor])
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        patch.add(neighbor)
                        stack.append(neighbor)
        if len(touches) >= 2 and sum(candidates[f] for f in patch) <= .01:
            completed.update(patch)
    return completed


def capture_edge_loop(obj: bpy.types.Object, scene: Optional[bpy.types.Scene] = None) -> Tuple[bool, List[int], bool, float, str]:
    """Captura e valida um loop fechado de arestas no modo de edição.
    
    Calcula desvio de planicidade no espaço de mundo em milímetros (mm).
    Retorna (sucesso, indices_ordenados, is_planar, desvio_mm, erro_msg).
    """
    if not obj or obj.mode != 'EDIT':
        return False, [], False, 0.0, "O objeto precisa estar em Edit Mode."

    return _capture_on_copy(obj, scene, _capture_edge_loop_bmesh)


def _capture_edge_loop_bmesh(bm, obj, scene):

    bm.verts.index_update()
    bm.edges.index_update()
    bm.faces.index_update()

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
    if any(len(edges) != 2 for edges in vert_to_edges.values()):
        actual_scene = scene if scene else (bpy.context.scene if hasattr(bpy.context, "scene") else None)
        scale_to_mm = get_scene_scale_to_mm(actual_scene)
        dist = 0.0001 / scale_to_mm
        v_before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
        v_after = len(bm.verts)
        if v_after < v_before:
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.verts.index_update()
            bm.edges.index_update()
            bm.faces.index_update()
            selected_edges = [e for e in bm.edges if e.select]
            if len(selected_edges) >= 3:
                vert_to_edges = {}
                for e in selected_edges:
                    for v in e.verts:
                        vert_to_edges.setdefault(v, []).append(e)

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

    return _capture_on_copy(obj, scene, _capture_face_boundary_bmesh)


class CapturedRegionBoundary(list):
    def __init__(self, outer, loops, faces):
        super().__init__(outer)
        self.boundary_loops = loops
        self.region_faces = faces


def _capture_face_boundary_bmesh(bm, obj, scene):
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.edges.index_update()
    bm.faces.index_update()

    selected_faces = set(f for f in bm.faces if f.select)
    if not selected_faces:
        return False, [], False, 0.0, -1, "Nenhuma face selecionada. Selecione as faces da área desejada."

    actual_scene = scene if scene else bpy.context.scene
    scale_to_mm = get_scene_scale_to_mm(actual_scene)
    selected_faces = _bridge_micro_selection_gaps(bm, selected_faces, obj, scale_to_mm)
    for face in selected_faces:
        face.select = True

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

    actual_scene = scene if scene else (bpy.context.scene if hasattr(bpy.context, "scene") else None)
    scale_to_mm = get_scene_scale_to_mm(actual_scene)
    dist = 0.0001 / scale_to_mm

    if len(visited) != len(selected_faces):
        # Auto-cura para modelos de IA / exportações com vértices desmembrados
        v_before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
        v_after = len(bm.verts)
        if v_after < v_before:
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.verts.index_update()
            bm.edges.index_update()
            bm.faces.index_update()
            # Welding can clear BMFace selection flags when vertex/edge flags
            # merge. Keep the user's faces, not the incidental post-weld flags.
            selected_faces = {f for f in selected_faces if f.is_valid}
            for face in bm.faces:
                face.select = face in selected_faces
            if selected_faces:
                if bm.faces.active and bm.faces.active in selected_faces:
                    seed_face_idx = bm.faces.active.index
                else:
                    seed_face_idx = next(iter(selected_faces)).index
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

    # Se houver vértice com grau != 2, tenta unificar vértices da malha caso ainda não tenha sido feito
    if any(len(edges) != 2 for edges in vert_to_edges.values()):
        v_before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
        v_after = len(bm.verts)
        if v_after < v_before:
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.verts.index_update()
            bm.edges.index_update()
            bm.faces.index_update()
            selected_faces = {f for f in selected_faces if f.is_valid}
            for face in bm.faces:
                face.select = face in selected_faces
            boundary_edges = [e for e in bm.edges if len([lf for lf in e.link_faces if lf in selected_faces]) == 1]
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
        from .geometry_material import _order_boundary_loops
        from .geometry_regions import region_support
        loops = _order_boundary_loops(boundary_edges)
        try:
            face_ids=sorted(f.index for f in selected_faces)
            support=region_support(obj,face_ids,scale_to_mm,_source_bm=bm)
        except ValueError as ex:
            return False, [], False, 0., -1, str(ex)
        def loop_area(loop):
            points=[obj.matrix_world @ v.co for v in loop]
            c=points[0]
            return sum(((a-c).cross(b-c) for a,b in zip(points,points[1:]+points[:1])),Vector()).length
        outer=max(loops,key=loop_area)
        captured=CapturedRegionBoundary([v.index for v in outer],[[v.index for v in lp] for lp in loops],face_ids)
        deviation=max(abs((obj.matrix_world @ v.co-support['origin']).dot(support['normal'])) for lp in loops for v in lp)*scale_to_mm
        return True,captured,deviation<=.1,deviation,seed_face_idx,""

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
    bm.faces.index_update()
    active_face = bm.faces.active
    if active_face and active_face.select:
        return active_face.index

    for f in bm.faces:
        if f.select:
            return f.index

    return -1


def captured_region_faces(obj, indices, seed, scene):
    """Resolve an explicitly captured multi-boundary selection, never flood a hole."""
    settings=getattr(scene,'chest_splitter',None)
    if not settings or settings.target_object!=obj or not settings.loop_is_captured:
        return None
    raw=getattr(settings,'loop_region_face_indices','')
    if not raw or list(indices)!=[int(i) for i in settings.loop_vertex_indices.split(',') if i.strip()]:
        return None
    import json
    faces=json.loads(raw)
    if seed not in faces:
        raise ValueError('A face escolhida não pertence à moldura capturada. Capture a região novamente.')
    if settings.loop_topology_signature!=get_topology_signature(obj):
        raise ValueError('A malha mudou; capture os contornos da moldura novamente.')
    return faces


def slice_mesh_by_loop(
    obj: bpy.types.Object,
    target_name: str,
    indices: List[int],
    seed_face_idx: int,
    scene: Optional[bpy.types.Scene] = None,
    detach_add_base: bool = False,
    detach_base_depth_mm: float = 0.0,
    detach_base_clearance_mm: float = 0.0,
    part_clearance_mm: float = 0.0,
    part_clearance_apply_to: str = 'PART',
    part_clearance_bottom_mm: Optional[float] = None,
    _override_step_depth_mm: Optional[float] = None,
) -> LoopSliceResult:
    """Realiza a separação da malha usando o contorno (loop) capturado.
    
    Processa a geometria inteiramente no espaço de mundo (World Space).
    Garante malhas manifold em Parte A e Parte B com interface compartilhada idêntica.
    Retorna LoopSliceResult(bm_a, bm_b, split_result).
    """
    actual_scene=scene if scene is not None else bpy.context.scene
    multi=captured_region_faces(obj,indices,seed_face_idx,actual_scene)
    if multi:
        from .geometry_regions import slice_surface_region
        return slice_surface_region(obj,multi,detach_base_depth_mm if detach_add_base else 0.,actual_scene,
                                    'EXTRUDE' if detach_add_base else 'BASE',part_clearance_mm,
                                    part_clearance_apply_to,part_clearance_bottom_mm,
                                    obj.data.polygons[seed_face_idx].material_index,source_mode='LOOP')
    scale_to_mm = get_scene_scale_to_mm(actual_scene)

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
    bm.normal_update()
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
    from .geometry_contract import boundary_normal
    n = boundary_normal(loop_coords_world)
    if n.length < 1e-12:
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

    stepped_res = None
    if max_dev_mm > 0.5:
        if _override_step_depth_mm is not None and _override_step_depth_mm > 0.0:
            req_step_bu = _override_step_depth_mm / scale_to_mm
        elif detach_add_base and detach_base_depth_mm > 0.0:
            req_step_bu = detach_base_depth_mm / scale_to_mm
        else:
            req_step_bu = None
        stepped_res = build_stepped_cap_triangles(loop_coords_world, step_depth_bu=req_step_bu)

    if stepped_res is not None:
        if detach_add_base and detach_base_depth_mm > 0.0:
            analysis = analyze_loop_region(obj, indices, seed_face_idx, scene=scene)
            max_avail_mm = analysis.get("max_avail_depth_mm", 0.0)
            if analysis.get("thickness_determined", False) and max_avail_mm > 0:
                if detach_base_depth_mm > (max_avail_mm + 1e-3):
                    bm_a.free()
                    bm_b.free()
                    raise LocalizedGeometryError('geometry.wall_thickness', depth=detach_base_depth_mm, available=max_avail_mm)

        all_pts = stepped_res["all_verts_3d"]
        cap_tris = stepped_res["triangles"]
        verts_a = list(loop_verts_a) + [bm_a.verts.new(pt) for pt in all_pts[n_loop:]]
        verts_b = list(loop_verts_b) + [bm_b.verts.new(pt) for pt in all_pts[n_loop:]]
        bm_a.verts.ensure_lookup_table()
        bm_b.verts.ensure_lookup_table()

        for i, j, k in cap_tris:
            va = (verts_a[i], verts_a[j], verts_a[k])
            try:
                fa = bm_a.faces.new(va)
                created_faces_a.append(fa)
            except ValueError:
                try:
                    fa = bm_a.faces.new((va[0], va[2], va[1]))
                    created_faces_a.append(fa)
                except Exception:
                    pass

            vb = (verts_b[i], verts_b[k], verts_b[j])
            try:
                fb = bm_b.faces.new(vb)
                created_faces_b.append(fb)
            except ValueError:
                try:
                    fb = bm_b.faces.new((vb[0], vb[2], vb[1]))
                    created_faces_b.append(fb)
                except Exception:
                    pass
    elif detach_add_base and detach_base_depth_mm > 0.0:
        analysis = analyze_loop_region(obj, indices, seed_face_idx, scene=scene)
        inward_dir = analysis["inward_dir_world"]
        max_avail_mm = analysis.get("max_avail_depth_mm", 0.0)
        if analysis.get("thickness_determined", False) and max_avail_mm > 0:
            if detach_base_depth_mm > (max_avail_mm + 1e-3):
                bm_a.free()
                bm_b.free()
                raise LocalizedGeometryError('geometry.wall_thickness', depth=detach_base_depth_mm, available=max_avail_mm)

        p_clear_mm = max(0.0, part_clearance_mm) if max(0.0, part_clearance_mm) > 0.0 else max(0.0, detach_base_clearance_mm)
        lat_a_mm = (
            p_clear_mm if part_clearance_apply_to == 'PART' else (0.5 * p_clear_mm if part_clearance_apply_to == 'BOTH' else 0.0)
        )
        lat_b_mm = (
            p_clear_mm if part_clearance_apply_to == 'CAVITY' else (0.5 * p_clear_mm if part_clearance_apply_to == 'BOTH' else 0.0)
        )
        bot_mm = max(0.0, part_clearance_bottom_mm) if part_clearance_bottom_mm is not None else p_clear_mm
        bot_a_mm = bot_mm if part_clearance_apply_to == 'PART' else (0.5 * bot_mm if part_clearance_apply_to == 'BOTH' else 0.0)
        bot_b_mm = bot_mm if part_clearance_apply_to == 'CAVITY' else (0.5 * bot_mm if part_clearance_apply_to == 'BOTH' else 0.0)

        if bot_a_mm > 0.0 and bot_a_mm >= detach_base_depth_mm - 0.1:
            bm_a.free()
            bm_b.free()
            raise LocalizedGeometryError('geometry.clearance_excessive')

        depth_a_bu = max(0.05 / scale_to_mm, (detach_base_depth_mm - bot_a_mm) / scale_to_mm)
        depth_b_bu = (detach_base_depth_mm + bot_b_mm) / scale_to_mm
        if analysis.get("thickness_determined", False) and max_avail_mm > 0 and depth_b_bu * scale_to_mm > (max_avail_mm + 1e-3):
            bm_a.free()
            bm_b.free()
            raise LocalizedGeometryError('geometry.clearance_excessive')

        # Folga (A04): aplicada na peca extraida A (fundo da base encolhido) e/ou cavidade B expandida.
        lat_a_bu = lat_a_mm / scale_to_mm
        lat_b_bu = lat_b_mm / scale_to_mm
        unit_offsets_3d = []
        if lat_a_bu > 1e-6 or lat_b_bu > 1e-6:
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
                unit_3d = (n_avg.x * u_vec + n_avg.y * v_vec) * scale_fac
                unit_offsets_3d.append(unit_3d)
        else:
            unit_offsets_3d = [Vector((0.0, 0.0, 0.0)) for _ in range(n_loop)]

        in_norm = inward_dir.normalized()
        n_out = -in_norm
        support = centroid_world + n_out * min((p - centroid_world).dot(n_out) for p in loop_coords_world)
        footprint_coords = [p - n_out * (p - support).dot(n_out) for p in loop_coords_world]
        unit_offsets_3d = [u - in_norm * u.dot(in_norm) for u in unit_offsets_3d]
        new_verts_a = [bm_a.verts.new(footprint_coords[i] + in_norm * depth_a_bu - unit_offsets_3d[i] * lat_a_bu) for i in range(n_loop)]
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

        new_verts_b = [bm_b.verts.new(footprint_coords[i] + in_norm * depth_b_bu + unit_offsets_3d[i] * lat_b_bu) for i in range(n_loop)]
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
        # Fechamento direto no plano do contorno (com fallback 3D wall-aware para contornos não-planares)
        if max_dev_mm > 0.5 and _has_wall_colliding_triangles(tri_indices, loop_verts_a, loop_verts_b, bm_a, bm_b):
            dp_tris = triangulate_loop_3d_wall_aware(loop_coords_world, loop_verts_a, loop_verts_b, bm_a, bm_b, n)
            if dp_tris:
                tri_indices = dp_tris

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
    from collections import Counter
    def inherit_generated(bm_part, created):
        created_set = set(created)
        old = [f.material_index for f in bm_part.faces if f not in created_set]
        mat = Counter(old).most_common(1)[0][0] if old else 0
        for f in created:
            if f.is_valid:
                f.material_index = mat
    inherit_generated(bm_a, created_faces_a)
    inherit_generated(bm_b, created_faces_b)

    def mark_contact_faces(bm_part, created):
        bm_part.faces.index_update()
        indices = [f.index for f in created if f.is_valid]
        layer = bm_part.faces.layers.int.get('splitter_contact_surface') or bm_part.faces.layers.int.new('splitter_contact_surface')
        bm_part.faces.ensure_lookup_table()
        faces = [bm_part.faces[i] for i in indices]
        for face in faces:
            face[layer] = 1
        return faces
    created_faces_a = mark_contact_faces(bm_a, created_faces_a)
    created_faces_b = mark_contact_faces(bm_b, created_faces_b)

    # Recalcula normais da Parte A e Parte B (garante orientação externa no sólido manifold)
    bmesh.ops.recalc_face_normals(bm_a, faces=bm_a.faces[:])
    bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces[:])

    # A closure is valid only while it stays inside the two source regions.
    # Nonadjacent BVH intersections mean the triangulated cap crosses retained
    # source faces and cannot be treated as a physical mating surface.
    from .geometry_clearance import cap_crossing_pairs
    crossing_a = cap_crossing_pairs(bm_a, created_faces_a, 0.0001 / scale_to_mm)
    crossing_b = cap_crossing_pairs(bm_b, created_faces_b, 0.0001 / scale_to_mm)
    if crossing_a or crossing_b:
        bm_a.free(); bm_b.free()
        part = 'A' if crossing_a else 'B'
        count = len(crossing_a) if crossing_a else len(crossing_b)
        raise LocalizedGeometryError('geometry.closing_intersection', part=part, count=count)

    # Determina a normal da interface que aponta DE A PARA B
    if stepped_res is not None:
        base_n = stepped_res["base_normal"]
        valid_caps = [f for f in created_faces_a if f.is_valid]
        avg_cap_norm = sum((f.normal * f.calc_area() for f in valid_caps), Vector()) if valid_caps else n
        ref_n = avg_cap_norm if avg_cap_norm.length > 1e-5 else n
        normal_a_to_b = base_n if base_n.dot(ref_n) >= 0 else -base_n
    elif detach_add_base and detach_base_depth_mm > 0.0:
        normal_a_to_b = inward_dir
    elif created_faces_a:
        valid_caps = [f for f in created_faces_a if f.is_valid]
        if valid_caps:
            avg_cap_norm = sum((f.normal * f.calc_area() for f in valid_caps), Vector())
            if avg_cap_norm.length > 1e-5:
                normal_a_to_b = n if n.dot(avg_cap_norm) >= 0 else -n
            else:
                normal_a_to_b = n
        else:
            normal_a_to_b = n
    else:
        normal_a_to_b = n

    # Aplica folga física de interface (part_clearance_mm) nos modos de fechamento direto e degrau 3D
    if max(part_clearance_mm, part_clearance_bottom_mm or 0.0) > 0.0 and (stepped_res is not None or not (detach_add_base and detach_base_depth_mm > 0.0)):
        n_ab = normal_a_to_b.normalized()
        if part_clearance_apply_to == 'PART':
            shift_a_mm, shift_b_mm = part_clearance_mm, 0.0
        elif part_clearance_apply_to == 'CAVITY':
            shift_a_mm, shift_b_mm = 0.0, part_clearance_mm
        elif part_clearance_apply_to == 'BOTH':
            shift_a_mm, shift_b_mm = 0.5 * part_clearance_mm, 0.5 * part_clearance_mm
        else:
            shift_a_mm, shift_b_mm = 0.0, 0.0

        projs_a = [v.co.dot(-n_ab) for v in bm_a.verts]
        span_a_mm = (max(projs_a) - min(projs_a)) * scale_to_mm if projs_a else 0.0
        projs_b = [v.co.dot(n_ab) for v in bm_b.verts]
        span_b_mm = (max(projs_b) - min(projs_b)) * scale_to_mm if projs_b else 0.0

        if shift_a_mm > 0.0 and shift_a_mm >= span_a_mm - 0.1:
            bm_a.free()
            bm_b.free()
            raise LocalizedGeometryError('geometry.clearance_excessive')
        if shift_b_mm > 0.0 and shift_b_mm >= span_b_mm - 0.1:
            bm_a.free()
            bm_b.free()
            raise LocalizedGeometryError('geometry.clearance_excessive')

        shift_a_bu = shift_a_mm / scale_to_mm
        shift_b_bu = shift_b_mm / scale_to_mm

        def _apply_cap_shift(bm_part, cap_v_list, shift_dir_vec, shift_bu, is_part_a):
            from .geometry_clearance import offset_contact_surface
            cap_faces = created_faces_a if is_part_a else created_faces_b
            bottom_mm = part_clearance_mm if part_clearance_bottom_mm is None else max(0.0, part_clearance_bottom_mm)
            fraction = 0.5 if part_clearance_apply_to == 'BOTH' else 1.0
            offset_contact_surface(
                bm_part, cap_faces, centroid_world, n_ab,
                shift_bu, bottom_mm * fraction / scale_to_mm,
                planar=stepped_res is None and max_dev_mm <= 0.15,
                inward=shift_dir_vec,
                unit_scale=scale_to_mm,
            )

        from .geometry_clearance import convex_contact_planes, convex_offset_from_planes, subtract_closed_region
        convex_planes = convex_contact_planes(bm_a, scale_to_mm) if stepped_res is None and max_dev_mm > 0.15 else None
        if convex_planes:
            bottom = (part_clearance_mm if part_clearance_bottom_mm is None else max(0.0,part_clearance_bottom_mm))/scale_to_mm
            factor_a = 1.0 if part_clearance_apply_to == 'PART' else (0.5 if part_clearance_apply_to == 'BOTH' else 0.0)
            factor_b = 1.0 if part_clearance_apply_to == 'CAVITY' else (0.5 if part_clearance_apply_to == 'BOTH' else 0.0)
            original_a = bm_a
            new_a = new_b = cutter = source = None
            try:
                if factor_a:
                    new_a = convex_offset_from_planes(original_a,convex_planes,n_ab,shift_a_bu,bottom*factor_a,-1,scale_to_mm)
                if factor_b:
                    cutter = convex_offset_from_planes(original_a,convex_planes,n_ab,shift_b_bu,bottom*factor_b,1,scale_to_mm,exterior_extension=0.001/scale_to_mm)
                    source = bmesh.new();source.from_mesh(obj.data);source.transform(matrix_world)
                    source.normal_update()
                    new_b = subtract_closed_region(source,cutter,scale_to_mm)
            except Exception:
                if new_a is not None:new_a.free()
                if new_b is not None:new_b.free()
                raise
            finally:
                if cutter is not None:cutter.free()
                if source is not None:source.free()
            if new_a is not None:
                bm_a.free();bm_a=new_a
            if new_b is not None:
                bm_b.free();bm_b=new_b
        else:
            cap_verts_a = verts_a if stepped_res is not None else loop_verts_a
            cap_verts_b = verts_b if stepped_res is not None else loop_verts_b
            if part_clearance_apply_to in ('PART', 'BOTH'):
                _apply_cap_shift(bm_a, cap_verts_a, -n_ab, shift_a_bu, True)
            if part_clearance_apply_to in ('CAVITY', 'BOTH'):
                _apply_cap_shift(bm_b, cap_verts_b, n_ab, shift_b_bu, False)

    # Constrói CutInterface formal em World Space
    # A03: com base adicional, a interface efetiva de contato é o fundo da base
    # (deslocado por inward_dir * profundidade), não o contorno original no topo.
    if stepped_res is not None:
        iface_origin = stepped_res["base_origin"]
        iface_loop_coords = stepped_res["base_boundary_3d"]
        iface_tris = stepped_res["base_triangles_3d"]
    else:
        iface_offset = Vector((0.0, 0.0, 0.0))
        if detach_add_base and detach_base_depth_mm > 0.0:
            iface_offset = inward_dir.normalized() * (detach_base_depth_mm / scale_to_mm)
        base_coords_for_iface = footprint_coords if (detach_add_base and detach_base_depth_mm > 0.0) else loop_coords_world
        iface_loop_coords = [Vector(c) + iface_offset for c in base_coords_for_iface]
        iface_origin = (sum(iface_loop_coords, Vector()) / len(iface_loop_coords)) if (detach_add_base and detach_base_depth_mm > 0.0) else (Vector(centroid_world) + iface_offset)
        iface_tris = [
            (iface_loop_coords[i], iface_loop_coords[j], iface_loop_coords[k])
            for i, j, k in tri_indices
        ] if tri_indices else None

    reference_origin_world = Vector(iface_origin).copy()
    reference_frame = build_cut_interface(
        origin_world=reference_origin_world,
        normal_a_to_b=normal_a_to_b,
        boundary_points_world=iface_loop_coords,
        interface_triangles=iface_tris,
        unit_scale=scale_to_mm,
        source_mode="LOOP",
    )
    reference_axis_u_world = reference_frame.axis_u_world.copy()

    # Connector placement uses the actual retained contact patch after clearance.
    final_a = final_b = None
    clearance_applied = max(part_clearance_mm, part_clearance_bottom_mm or 0.0) > 0.0
    if clearance_applied:
        from .geometry_clearance import final_contact_patch
        final_a = final_contact_patch(bm_a, normal_a_to_b, scale_to_mm)
        final_b = final_contact_patch(bm_b, -normal_a_to_b, scale_to_mm)
        if final_a:
            iface_origin = reference_origin_world if (detach_add_base and detach_base_depth_mm > 0.0 and stepped_res is None) else final_a['origin']
            iface_loop_coords = final_a['boundary']
            iface_tris = final_a['triangles']

    cut_interface = build_cut_interface(
        origin_world=iface_origin,
        normal_a_to_b=normal_a_to_b,
        boundary_loops_world=final_a['loops'] if final_a else None,
        boundary_points_world=iface_loop_coords,
        interface_triangles=iface_tris,
        unit_scale=scale_to_mm,
        source_mode="LOOP",
    )

    cut_interface.clearance_applied = clearance_applied
    cut_interface.final_contact_a = final_a
    cut_interface.final_contact_b = final_b
    cut_interface.reference_origin_world = reference_origin_world
    cut_interface.reference_axis_u_world = reference_axis_u_world

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
    actual_scene=scene if scene is not None else bpy.context.scene
    multi=captured_region_faces(obj,indices,seed_face_idx,actual_scene)
    if multi:
        from .geometry_regions import region_support
        support=region_support(obj,multi,get_scene_scale_to_mm(actual_scene))
        return dict(detected_mode='DETACH' if support['height']>.001 else 'EXTRUDE',
                    reason='Região com aberturas internas; o centro será preservado.',
                    region_face_indices=multi,centroid_world=support['origin'],
                    loop_normal_world=support['normal'],inward_dir_world=-support['normal'],
                    protrusion_height_mm=support['height'],is_planar_region=support['height']<=.001,
                    is_planar_loop=support['deviation']<=.1,has_holes=True)
    scale_to_mm = get_scene_scale_to_mm(actual_scene)
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

    from .geometry_contract import boundary_normal
    n = boundary_normal(loop_coords_world)
    if n.length < 1e-12:
        n = Vector((0.0, 0.0, 1.0))

    # Determina a direção para dentro do sólido
    normal_matrix = matrix_world.to_3x3().inverted().transposed()
    seed_norm_world = (normal_matrix @ seed_face.normal).normalized()

    # Prepara BVHTree no espaço de mundo para testar direção e espessura da parede
    bm_bvh = bm.copy()
    bm_bvh.transform(matrix_world)
    bm_bvh.normal_update()
    bvh = BVHTree.FromBMesh(bm_bvh)

    # Use the boundary support normal, oriented by the region's area-weighted
    # outward normal. A sloping seed face must not tilt an otherwise planar base.
    bm_bvh.faces.ensure_lookup_table()
    outward = sum((bm_bvh.faces[f.index].normal * bm_bvh.faces[f.index].calc_area()
                   for f in faces_a), Vector())
    reference = outward if outward.length > 1e-12 else seed_norm_world
    inward_dir = -n if n.dot(reference) >= 0.0 else n

    # Analisa relevo (altura) dos vértices da região A em relação ao plano do loop
    region_face_indices = sorted(f.index for f in faces_a)
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
    u_test, v_test = _get_orthonormal_basis(n)
    projected = [Vector(((p-centroid).dot(u_test), (p-centroid).dot(v_test)))
                 for p in loop_coords_world]
    triangles = triangulate_polygon_2d(projected)
    n_out = -inward_dir
    # Depth is below the lowest boundary support, including a nonplanar contour.
    support = centroid + n_out * min((p-centroid).dot(n_out) for p in loop_coords_world)
    test_points = []
    for i, j, k in triangles:
        q = (projected[i] + projected[j] + projected[k]) / 3.0
        test_points.append(support + q.x*u_test + q.y*v_test)
    for pt in test_points:
        hit_loc, hit_norm, hit_idx, hit_dist = bvh.ray_cast(pt + inward_dir*offset_bu, inward_dir)
        if hit_loc is not None and hit_norm.dot(inward_dir) > 0.0:
            dist = (hit_loc - pt).length
            sampled_hits += 1
            min_wall_depth_bu = min(min_wall_depth_bu, dist)

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

    # A non-planar selected patch can straddle its nominal closing cap.  In
    # AUTO mode that is a signal to use the user's configured extrusion depth,
    # not to force an invalid DETACH closure or silently alter that depth.  The
    # nominal loop operation does not call this analysis function, so the probe
    # is bounded and cannot recurse.  Preserve all other errors as-is.
    closure_crosses_source = False
    if detected_mode == 'DETACH':
        try:
            probe = slice_mesh_by_loop(
                obj, obj.name, indices, seed_face_idx, scene=scene,
            )
        except LocalizedGeometryError as error:
            from .localized_errors import MESSAGE_MARKER
            if error.payload.get(MESSAGE_MARKER) != 'geometry.closing_intersection':
                raise
            closure_crosses_source = True
            detected_mode = 'EXTRUDE'
            reason = (
                "O fechamento direto cruza a geometria existente; "
                "AUTO usará a profundidade de extração configurada."
            )
        else:
            for probe_part in probe:
                probe_part.free()

    from .localized_errors import message_payload
    if closure_crosses_source:
        reason_message = message_payload('diagnostic.closure_uses_depth')
        from .localized_errors import render_message
        reason = render_message(reason_message)
    elif is_planar_region:
        reason_message = message_payload('diagnostic.planar_region', height=span_h_mm)
    elif not can_close_loop and not is_planar_loop:
        reason_message = message_payload('diagnostic.non_planar_protrusion', deviation=max_dev_loop_mm)
    else:
        reason_message = message_payload('diagnostic.protrusion', height=span_h_mm)
    return {
        "reason_message": reason_message,
        "detected_mode": detected_mode,
        "closure_crosses_source": closure_crosses_source,
        "reason": reason,
        "protrusion_height_mm": max(0.0, max_h * scale_to_mm),
        "region_face_indices": region_face_indices,
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


def _point_in_poly_2d(pt: Vector, poly: List[Vector]) -> bool:
    """Retorna True se o ponto 2D estiver estritamente dentro do polígono."""
    inside = False
    n = len(poly)
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        if (p1.y > pt.y) != (p2.y > pt.y):
            denom = p2.y - p1.y
            if abs(denom) > 1e-12:
                x_int = p1.x + (pt.y - p1.y) * (p2.x - p1.x) / denom
                if pt.x < x_int:
                    inside = not inside
    return inside


def _is_simple_polygon_2d(poly: List[Vector], expected_ccw: bool, min_area: float) -> bool:
    """Verifica se o polígono 2D não possui auto-interseções e mantém orientação e área mínimas."""
    n = len(poly)
    if n < 3:
        return False
    area2 = 0.0
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        if (p2 - p1).length < 1e-6:
            return False
        area2 += p1.x * p2.y - p2.x * p1.y
    if (area2 > 0.0) != expected_ccw or (0.5 * abs(area2)) < min_area:
        return False

    def ccw_val(a: Vector, b: Vector, c: Vector) -> float:
        return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)

    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c = poly[j]
            d = poly[(j + 1) % n]
            d1 = ccw_val(a, b, c)
            d2 = ccw_val(a, b, d)
            d3 = ccw_val(c, d, a)
            d4 = ccw_val(c, d, b)
            if ((d1 > 1e-9 and d2 < -1e-9) or (d1 < -1e-9 and d2 > 1e-9)) and (
                (d3 > 1e-9 and d4 < -1e-9) or (d3 < -1e-9 and d4 > 1e-9)
            ):
                return True and False
    return True


def build_stepped_cap_triangles(
    loop_coords_world: List[Vector],
    step_depth_bu: Optional[float] = None,
    min_riser_slope: float = 0.45,
) -> Optional[Dict[str, Any]]:
    """Constrói uma superfície de partição 3D em degrau (Stepped Parting Surface) para loops não-planares.

    Quando um contorno envolve um sólido em um plano base dominante mas possui um ou mais degraus
    (excursões verticais ou inclinadas nas paredes laterais), a projeção 2D simples colapsa as
    paredes verticais e gera abas coplanares à parede externa ou rampas diagonais.
    Este algoritmo decompõe a interface em:
      - Base plana principal (P0)
      - Degraus ortogonais/regrados internos (prateleira superior, parede traseira e bochechas laterais)
    garantindo uma interface 100% manifold, estanque e complementar entre Parte A e Parte B.
    """
    n_loop = len(loop_coords_world)
    if n_loop < 6:
        return None

    edges_dir = []
    edges_len = []
    for i in range(n_loop):
        d = loop_coords_world[(i + 1) % n_loop] - loop_coords_world[i]
        l = d.length
        edges_len.append(l)
        edges_dir.append(d / l if l > 1e-9 else Vector((0.0, 0.0, 0.0)))

    total_perim = sum(edges_len)
    if total_perim < 1e-6:
        return None
    avg_edge = total_perim / n_loop
    plane_tol = max(1e-4, avg_edge * 0.05)

    best_normal = None
    best_origin = None
    best_score = -1.0

    candidates = []
    step_stride = max(1, n_loop // 20)
    for i in range(0, n_loop, step_stride):
        if edges_len[i] < 1e-6:
            continue
        for j in range(i + 1, n_loop, step_stride):
            if edges_len[j] < 1e-6:
                continue
            cp = edges_dir[i].cross(edges_dir[j])
            if cp.length > 0.15:
                n_cand = cp.normalized()
                for p_orig in (loop_coords_world[i], loop_coords_world[j]):
                    if abs((loop_coords_world[i] - loop_coords_world[j]).dot(n_cand)) <= plane_tol:
                        candidates.append((p_orig, n_cand))

    for p_orig, n_cand in candidates:
        score = 0.0
        for i in range(n_loop):
            d1 = abs((loop_coords_world[i] - p_orig).dot(n_cand))
            d2 = abs((loop_coords_world[(i + 1) % n_loop] - p_orig).dot(n_cand))
            if d1 <= plane_tol and d2 <= plane_tol:
                score += edges_len[i]
        if score > best_score:
            best_score = score
            best_normal = n_cand
            best_origin = p_orig

    if best_normal is None or best_score < 0.40 * total_perim or best_score > 0.995 * total_perim:
        return None

    from .geometry_contract import boundary_normal
    newell_n = boundary_normal(loop_coords_world)
    if best_normal.dot(newell_n) < 0:
        best_normal = -best_normal

    in_plane_mask = [abs((p - best_origin).dot(best_normal)) <= plane_tol for p in loop_coords_world]
    if all(in_plane_mask) or not any(in_plane_mask):
        return None

    base_pts = [loop_coords_world[i] for i in range(n_loop) if in_plane_mask[i]]
    base_origin = sum(base_pts, Vector()) / len(base_pts)
    heights = [(p - base_origin).dot(best_normal) for p in loop_coords_world]
    in_plane_mask = [abs(h) <= plane_tol for h in heights]

    start_idx = next((i for i, m in enumerate(in_plane_mask) if m), None)
    if start_idx is None:
        return None

    excursions = []
    i = 0
    while i < n_loop:
        curr = (start_idx + i) % n_loop
        if not in_plane_mask[curr]:
            exc_start_base = (curr - 1) % n_loop
            exc_verts = []
            while i < n_loop and not in_plane_mask[(start_idx + i) % n_loop]:
                exc_verts.append((start_idx + i) % n_loop)
                i += 1
            exc_end_base = (start_idx + i) % n_loop
            excursions.append((exc_start_base, exc_verts, exc_end_base))
        else:
            i += 1

    if not excursions:
        return None

    # Exige que pelo menos uma excursão possua subida/descida acentuada (degrau real)
    has_steep_riser = False
    for exc_start, exc_verts, exc_end in excursions:
        full_chain = [exc_start] + exc_verts + [exc_end]
        for k in range(len(full_chain) - 1):
            a_idx, b_idx = full_chain[k], full_chain[k + 1]
            seg = loop_coords_world[b_idx] - loop_coords_world[a_idx]
            if seg.length > 1e-6:
                slope = abs(seg.dot(best_normal)) / seg.length
                if slope >= min_riser_slope:
                    has_steep_riser = True
                    break
    if not has_steep_riser:
        return None

    u_vec, v_vec = _get_orthonormal_basis(best_normal)

    def proj_3d_to_base(p: Vector) -> Vector:
        return p - ((p - base_origin).dot(best_normal)) * best_normal

    def to_2d(p: Vector) -> Vector:
        d = p - base_origin
        return Vector((d.dot(u_vec), d.dot(v_vec)))

    footprint_2d = [to_2d(p) for p in loop_coords_world]
    area2 = 0.0
    for k in range(n_loop):
        p1, p2 = footprint_2d[k], footprint_2d[(k + 1) % n_loop]
        area2 += p1.x * p2.y - p2.x * p1.y
    if abs(area2) < 1e-8:
        return None
    is_ccw = area2 > 0.0
    orig_area_2d = 0.5 * abs(area2)

    # Polígono 2D simplificado do contorno original (sem pontos duplicados de risers verticais)
    dedup_footprint_2d = []
    riser_tol = max(1e-4, avg_edge * 0.15)
    for pt in footprint_2d:
        if not dedup_footprint_2d or (pt - dedup_footprint_2d[-1]).length > riser_tol:
            dedup_footprint_2d.append(pt)
    if len(dedup_footprint_2d) > 1 and (dedup_footprint_2d[0] - dedup_footprint_2d[-1]).length <= riser_tol:
        dedup_footprint_2d.pop()

    xs = [p.x for p in footprint_2d]
    ys = [p.y for p in footprint_2d]
    min_span = min(max(xs) - min(xs), max(ys) - min(ys))
    if min_span < 1e-5:
        return None

    for depth_scale in (1.0, 0.7, 0.5, 0.35, 0.2, 0.1):
        all_verts_3d = list(loop_coords_world)
        interior_step_meta = []
        step_tris = []
        excursion_replacements = {}
        valid_scale = True

        for exc_start, exc_verts, exc_end in excursions:
            full_chain = [exc_start] + exc_verts + [exc_end]
            avg_exc_h = sum(heights[v_idx] for v_idx in exc_verts) / max(1, len(exc_verts))
            exc_sign = 1.0 if avg_exc_h >= 0.0 else -1.0
            columns = []
            for v_idx in full_chain:
                q_pt = proj_3d_to_base(loop_coords_world[v_idx])
                if not columns:
                    columns.append([v_idx])
                else:
                    q_prev = proj_3d_to_base(loop_coords_world[columns[-1][0]])
                    if (q_pt - q_prev).length <= riser_tol:
                        columns[-1].append(v_idx)
                    else:
                        columns.append([v_idx])

            m_cols = len(columns)
            if m_cols < 2:
                valid_scale = False
                break

            max_exc_h = max(abs(heights[v_idx]) for v_idx in full_chain)
            if step_depth_bu is not None and step_depth_bu > 1e-5:
                base_d = min(step_depth_bu, 0.45 * min_span)
            else:
                base_d = min(max(avg_edge, 0.5 * max_exc_h), 0.25 * min_span)
            d_step = base_d * depth_scale

            col_2d = [to_2d(loop_coords_world[col[0]]) for col in columns]
            seg_normals_2d = []
            for k in range(m_cols - 1):
                t_vec = col_2d[k + 1] - col_2d[k]
                if t_vec.length < 1e-7:
                    valid_scale = False
                    break
                t_dir = t_vec.normalized()
                n_2d = Vector((-t_dir.y, t_dir.x)) if is_ccw else Vector((t_dir.y, -t_dir.x))
                seg_normals_2d.append(n_2d)
            if not valid_scale:
                break

            inward_vecs_3d = []
            for k in range(m_cols):
                if k == 0:
                    w_2d = seg_normals_2d[0]
                elif k == m_cols - 1:
                    w_2d = seg_normals_2d[-1]
                else:
                    n1 = seg_normals_2d[k - 1]
                    n2 = seg_normals_2d[k]
                    n_sum = n1 + n2
                    n_avg = n_sum.normalized() if n_sum.length > 1e-6 else n1
                    cos_half = max(0.5, n_avg.dot(n1))
                    scale_fac = min(2.0, 1.0 / cos_half)
                    w_2d = n_avg * scale_fac
                inward_3d = w_2d.x * u_vec + w_2d.y * v_vec
                inward_vecs_3d.append(inward_3d)

            col_base_idx = []
            col_enter_top_idx = []
            col_exit_top_idx = []

            for k, col in enumerate(columns):
                in_vec = inward_vecs_3d[k]
                q_base = proj_3d_to_base(loop_coords_world[col[0]])
                p_base_in = q_base + d_step * in_vec
                if len(dedup_footprint_2d) >= 3 and not _point_in_poly_2d(to_2d(p_base_in), dedup_footprint_2d):
                    valid_scale = False
                    break
                b_idx = len(all_verts_3d)
                all_verts_3d.append(p_base_in)
                interior_step_meta.append((in_vec, exc_sign, d_step))
                col_base_idx.append(b_idx)

                if k == 0:
                    if len(col) == 1:
                        col_enter_top_idx.append(b_idx)
                        col_exit_top_idx.append(b_idx)
                    else:
                        p_top_in = loop_coords_world[col[-1]] + d_step * in_vec
                        t_idx = len(all_verts_3d)
                        all_verts_3d.append(p_top_in)
                        interior_step_meta.append((in_vec, exc_sign, d_step))
                        col_enter_top_idx.append(b_idx)
                        col_exit_top_idx.append(t_idx)
                        for r_i in range(len(col) - 1):
                            u0, u1 = col[r_i], col[r_i + 1]
                            step_tris.append((u0, u1, b_idx) if is_ccw else (u0, b_idx, u1))
                        step_tris.append((col[-1], t_idx, b_idx) if is_ccw else (col[-1], b_idx, t_idx))
                elif k == m_cols - 1:
                    if len(col) == 1:
                        col_enter_top_idx.append(b_idx)
                        col_exit_top_idx.append(b_idx)
                    else:
                        p_top_in = loop_coords_world[col[0]] + d_step * in_vec
                        t_idx = len(all_verts_3d)
                        all_verts_3d.append(p_top_in)
                        interior_step_meta.append((in_vec, exc_sign, d_step))
                        col_enter_top_idx.append(t_idx)
                        col_exit_top_idx.append(b_idx)
                        step_tris.append((col[0], b_idx, t_idx) if is_ccw else (col[0], t_idx, b_idx))
                        for r_i in range(len(col) - 1):
                            u0, u1 = col[r_i], col[r_i + 1]
                            step_tris.append((u0, u1, b_idx) if is_ccw else (u0, b_idx, u1))
                else:
                    t_list = []
                    for v_idx in col:
                        p_top_in = loop_coords_world[v_idx] + d_step * in_vec
                        t_idx = len(all_verts_3d)
                        all_verts_3d.append(p_top_in)
                        interior_step_meta.append((in_vec, exc_sign, d_step))
                        t_list.append(t_idx)
                    col_enter_top_idx.append(t_list[0])
                    col_exit_top_idx.append(t_list[-1])
                    for r_i in range(len(col) - 1):
                        u0, u1 = col[r_i], col[r_i + 1]
                        v0, v1 = t_list[r_i], t_list[r_i + 1]
                        if is_ccw:
                            step_tris.append((u0, u1, v1))
                            step_tris.append((u0, v1, v0))
                            step_tris.append((v0, v1, b_idx))
                        else:
                            step_tris.append((u0, v1, u1))
                            step_tris.append((u0, v0, v1))
                            step_tris.append((v0, b_idx, v1))
            if not valid_scale:
                break

            for k in range(m_cols - 1):
                u0 = columns[k][-1]
                u1 = columns[k + 1][0]
                t0 = col_exit_top_idx[k]
                t1 = col_enter_top_idx[k + 1]
                b0 = col_base_idx[k]
                b1 = col_base_idx[k + 1]

                if is_ccw:
                    step_tris.append((u0, u1, t1))
                    step_tris.append((u0, t1, t0))
                else:
                    step_tris.append((u0, t1, u1))
                    step_tris.append((u0, t0, t1))

                if t0 != b0 and t1 != b1:
                    if is_ccw:
                        step_tris.append((t0, t1, b1))
                        step_tris.append((t0, b1, b0))
                    else:
                        step_tris.append((t0, b1, t1))
                        step_tris.append((t0, b0, b1))
                elif t0 == b0 and t1 != b1:
                    step_tris.append((b0, t1, b1) if is_ccw else (b0, b1, t1))
                elif t0 != b0 and t1 == b1:
                    step_tris.append((t0, b1, b0) if is_ccw else (t0, b0, b1))

            excursion_replacements[exc_start] = (exc_end, col_base_idx)

        if not valid_scale:
            continue

        base_poly_vert_indices = []
        idx_ptr = start_idx
        visited = 0
        while visited < n_loop:
            base_poly_vert_indices.append(idx_ptr)
            if idx_ptr in excursion_replacements:
                exc_end, inner_base_list = excursion_replacements[idx_ptr]
                base_poly_vert_indices.extend(inner_base_list)
                steps_advanced = (exc_end - idx_ptr) % n_loop
                visited += steps_advanced
                idx_ptr = exc_end
            else:
                idx_ptr = (idx_ptr + 1) % n_loop
                visited += 1

        base_poly_2d = [to_2d(all_verts_3d[idx]) for idx in base_poly_vert_indices]
        if not _is_simple_polygon_2d(base_poly_2d, is_ccw, 0.15 * orig_area_2d):
            continue

        base_tris_local = triangulate_polygon_2d(base_poly_2d)
        if not base_tris_local or len(base_tris_local) < len(base_poly_vert_indices) - 2:
            continue

        base_tris_3d = []
        for a, b, c in base_tris_local:
            ia, ib, ic = base_poly_vert_indices[a], base_poly_vert_indices[b], base_poly_vert_indices[c]
            tri = (ia, ib, ic) if is_ccw else (ia, ic, ib)
            step_tris.append(tri)
            base_tris_3d.append((all_verts_3d[tri[0]], all_verts_3d[tri[1]], all_verts_3d[tri[2]]))

        # Validação topológica estrita: cada aresta de fronteira tem grau 1 e cada aresta interna tem grau 2 oposto
        directed_edges = {}
        for a, b, c in step_tris:
            for u, v in ((a, b), (b, c), (c, a)):
                directed_edges[(u, v)] = directed_edges.get((u, v), 0) + 1

        topo_ok = True
        for i_b in range(n_loop):
            j_b = (i_b + 1) % n_loop
            if directed_edges.get((i_b, j_b), 0) + directed_edges.get((j_b, i_b), 0) != 1:
                topo_ok = False
                break
        if topo_ok:
            for (u, v), cnt in directed_edges.items():
                is_bound = (u < n_loop and v < n_loop and ((u + 1) % n_loop == v or (v + 1) % n_loop == u))
                if not is_bound and (cnt != 1 or directed_edges.get((v, u), 0) != 1):
                    topo_ok = False
                    break
        if not topo_ok:
            continue

        base_boundary_3d = [all_verts_3d[idx] for idx in base_poly_vert_indices]
        return {
            "all_verts_3d": all_verts_3d,
            "triangles": step_tris,
            "base_normal": best_normal,
            "base_origin": base_origin,
            "base_boundary_3d": base_boundary_3d,
            "base_triangles_3d": base_tris_3d,
            "interior_step_meta": interior_step_meta,
        }

    return None


def _has_wall_colliding_triangles(
    tri_indices: List[Tuple[int, int, int]],
    loop_verts_a: List[bmesh.types.BMVert],
    loop_verts_b: List[bmesh.types.BMVert],
    bm_a: bmesh.types.BMesh,
    bm_b: bmesh.types.BMesh,
) -> bool:
    """Detecta se a triangulação 2D gerou triângulos que colidem com faces existentes ou são coplanares à parede."""
    if not tri_indices:
        return True
    for i, j, k in tri_indices:
        va = (loop_verts_a[i], loop_verts_a[j], loop_verts_a[k])
        vb = (loop_verts_b[i], loop_verts_b[j], loop_verts_b[k])
        if bm_a.faces.get(va) is not None or bm_b.faces.get(vb) is not None:
            return True
        # Verifica se os 3 vértices pertencem a faces de parede externa coplanares
        p0, p1, p2 = va[0].co, va[1].co, va[2].co
        n_tri = (p1 - p0).cross(p2 - p0)
        if n_tri.length < 1e-9:
            return True
        n_tri.normalize()
        for v_set in (va, vb):
            common_normals = None
            for v in v_set:
                v_norms = [f.normal for f in v.link_faces if f.normal.length > 1e-6]
                if not v_norms:
                    common_normals = []
                    break
                if common_normals is None:
                    common_normals = v_norms
                else:
                    common_normals = [cn for cn in common_normals if any(cn.dot(vn) > 0.995 for vn in v_norms)]
            if common_normals and any(abs(n_tri.dot(cn)) > 0.985 for cn in common_normals):
                return True
    return False


def triangulate_loop_3d_wall_aware(
    loop_coords_world: List[Vector],
    loop_verts_a: List[bmesh.types.BMVert],
    loop_verts_b: List[bmesh.types.BMVert],
    bm_a: bmesh.types.BMesh,
    bm_b: bmesh.types.BMesh,
    ref_normal: Vector,
) -> List[Tuple[int, int, int]]:
    """Triangulação 3D de peso mínimo (Liepa 2003 DP) com penalização de colisão/coplanaridade com paredes externas."""
    n = len(loop_coords_world)
    if n < 3 or n > 96:
        return []

    def tri_cost(i: int, k: int, j: int) -> float:
        p0, p1, p2 = loop_coords_world[i], loop_coords_world[k], loop_coords_world[j]
        cp = (p1 - p0).cross(p2 - p0)
        area = 0.5 * cp.length
        if area < 1e-9:
            return 1e12
        va = (loop_verts_a[i], loop_verts_a[k], loop_verts_a[j])
        vb = (loop_verts_b[i], loop_verts_b[k], loop_verts_b[j])
        if bm_a.faces.get(va) is not None or bm_b.faces.get(vb) is not None:
            return 1e9 + area
        n_tri = cp.normalized()
        penalty = 1.0
        for v_set in (va, vb):
            common_normals = None
            for v in v_set:
                v_norms = [f.normal for f in v.link_faces if f.normal.length > 1e-6]
                if not v_norms:
                    common_normals = []
                    break
                if common_normals is None:
                    common_normals = v_norms
                else:
                    common_normals = [cn for cn in common_normals if any(cn.dot(vn) > 0.995 for vn in v_norms)]
            if common_normals and any(abs(n_tri.dot(cn)) > 0.985 for cn in common_normals):
                penalty += 1e6
        align = n_tri.dot(ref_normal)
        if align < 0.0:
            penalty += 5.0 * (1.0 - align)
        return area * penalty

    dp = [[0.0] * n for _ in range(n)]
    split = [[-1] * n for _ in range(n)]

    for length in range(2, n):
        for i in range(n - length):
            j = i + length
            best_w = 1e18
            best_k = -1
            for k in range(i + 1, j):
                w = dp[i][k] + dp[k][j] + tri_cost(i, k, j)
                if w < best_w:
                    best_w = w
                    best_k = k
            dp[i][j] = best_w
            split[i][j] = best_k

    tris = []
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        k = split[i][j]
        if k == -1:
            continue
        tris.append((i, k, j))
        stack.append((k, j))
        stack.append((i, k))
    return tris



def create_loop_prism_cutter(
    coords_world: List[Vector],
    inward_dir: Vector,
    depth_bu: float,
    outward_ext_bu: float = 1e-3,
    name: str = "temp_loop_prism",
    lateral_offset_bu: float = 0.0,
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
    ref_origin = sum(coords_world, Vector()) / max(1, n)
    u_vec, v_vec = _get_orthonormal_basis(in_norm)
    pts_2d = [Vector(((p - ref_origin).dot(u_vec), (p - ref_origin).dot(v_vec))) for p in coords_world]
    if abs(lateral_offset_bu) > 1e-9:
        from .geometry_material import offset_polygon_2d
        new_pts, ok = offset_polygon_2d(pts_2d, lateral_offset_bu)
        if not ok:
            scale_to_mm = get_scene_scale_to_mm(bpy.context.scene)
            bm.free()
            raise LocalizedGeometryError('geometry.clearance_excessive')
        coords_world = [ref_origin + q.x * u_vec + q.y * v_vec for q in new_pts]
        pts_2d = new_pts
        n = len(coords_world)

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

    from .geometry_solid import ensure_solid_outward_normals
    ensure_solid_outward_normals(bm)

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.hide_viewport = False
    obj.hide_render = False
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _selected_region_overhangs_footprint(obj, analysis, scale_to_mm):
    """Allow a projected fallback only when it covers the selected source shell.

    Test vertices and full visible triangle edges. Endpoints alone cannot detect
    an edge crossing a narrow concavity of the projected boundary.
    """
    coords = analysis['coords_world']
    center = analysis['centroid_world']
    u, v = _get_orthonormal_basis(analysis['inward_dir_world'])
    polygon = [Vector(((p-center).dot(u), (p-center).dot(v))) for p in coords]
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    tolerance = .001 / scale_to_mm

    def contains(point):
        if _point_in_poly_2d(point, polygon):
            return True
        for a, b in edges:
            edge = b-a
            factor = max(0.0, min(1.0, (point-a).dot(edge) / edge.length_squared)) if edge.length_squared else 0.0
            if (point - (a + factor*edge)).length <= tolerance:
                return True
        return False

    region = set(analysis['region_face_indices'])
    indices = {index for face in region for index in obj.data.polygons[face].vertices}
    projected = {}
    for index in indices:
        point = obj.matrix_world @ obj.data.vertices[index].co - center
        projected[index] = Vector((point.dot(u), point.dot(v)))
        if not contains(projected[index]):
            return True

    obj.data.calc_loop_triangles()
    selected_edges = {tuple(sorted((a, b)))
                      for tri in obj.data.loop_triangles if tri.polygon_index in region
                      for a, b in zip(tri.vertices, (*tri.vertices[1:], tri.vertices[0]))}
    def cross(a, b):
        return a.x*b.y - a.y*b.x
    for ia, ib in selected_edges:
        a, b = projected[ia], projected[ib]
        direction = b-a
        parameters = [0.0, 1.0]
        for c, d in edges:
            boundary = d-c
            denominator = cross(direction, boundary)
            if abs(denominator) <= 1e-20:
                continue
            t = cross(c-a, boundary) / denominator
            q = cross(c-a, direction) / denominator
            if 0.0 < t < 1.0 and -1e-8 <= q <= 1.0+1e-8:
                parameters.append(t)
        parameters.sort()
        if any(not contains(a + direction*((lo+hi)*.5))
               for lo, hi in zip(parameters, parameters[1:])):
            return True
    return False


def _triangulate_retained_source_faces(bm, source_obj, source_face_indices):
    """Split retained source faces along Blender's exact visible loop diagonals.

    ``bmesh.utils.face_split`` performs a native face split and carries face and
    corner custom data across it.  This avoids both an approximate ngon
    triangulation and rebuilding faces after deleting the original surface.
    """
    source_mesh = source_obj.data
    source_mesh.calc_loop_triangles()
    selected = set(source_face_indices)

    def coordinate_key(point):
        return tuple(round(float(value), 7) for value in point)

    expected_by_face = {}
    boundary_by_face = {}
    for tri in source_mesh.loop_triangles:
        if tri.polygon_index not in selected:
            continue
        polygon = source_mesh.polygons[tri.polygon_index]
        face_key = tuple(sorted(
            coordinate_key(source_obj.matrix_world @ source_mesh.vertices[index].co)
            for index in polygon.vertices
        ))
        triangle_keys = tuple(
            coordinate_key(source_obj.matrix_world @ source_mesh.vertices[index].co)
            for index in tri.vertices
        )
        expected_by_face.setdefault(face_key, set()).add(frozenset(triangle_keys))
        boundary_by_face[face_key] = {
            frozenset((coordinate_key(source_obj.matrix_world @ source_mesh.vertices[a].co),
                       coordinate_key(source_obj.matrix_world @ source_mesh.vertices[b].co)))
            for a, b in zip(polygon.vertices, (*polygon.vertices[1:], polygon.vertices[0]))
        }

    changed = 0
    for face in list(bm.faces):
        face_key = tuple(sorted(coordinate_key(vertex.co) for vertex in face.verts))
        expected = expected_by_face.get(face_key)
        if not expected or len(face.verts) <= 3:
            continue
        source_verts = {coordinate_key(vertex.co): vertex for vertex in face.verts}
        boundary_edges = boundary_by_face.get(face_key, set())
        target_edges = set()
        for triangle in expected:
            points = tuple(triangle)
            for index in range(3):
                edge_key = frozenset((points[index], points[(index + 1) % 3]))
                if edge_key not in boundary_edges:
                    target_edges.add(edge_key)

        # Only search fragments of this source polygon. A neighbouring polygon
        # can share the same vertices, and the whole mesh may be very large.
        fragments = [face]
        # Work in deterministic order. After each split, the next diagonal
        # belongs to exactly one of the resulting faces.
        for edge_key in sorted(target_edges, key=lambda edge: tuple(sorted(edge))):
            keys = tuple(sorted(edge_key))
            va, vb = (source_verts.get(key) for key in keys)
            if va is None or vb is None:
                raise RuntimeError('Could not map a source-visible diagonal to its retained BMesh face.')
            candidates = [candidate for candidate in fragments
                          if va in candidate.verts and vb in candidate.verts
                          and bm.edges.get((va, vb)) not in candidate.edges]
            if not candidates:
                # It may already be a diagonal introduced by an earlier split.
                if bm.edges.get((va, vb)) is not None:
                    continue
                raise RuntimeError('Could not find a retained face containing a source-visible diagonal.')
            new_face, _ = bmesh.utils.face_split(candidates[0], va, vb)
            fragments.append(new_face)
            changed += 1

    if changed:
        bm.normal_update()
    return changed

class LoopBooleanError(RuntimeError):
    """EXACT produced a non-manifold result; fallback to MANIFOLD when available."""


def slice_mesh_by_loop_extrude(*args, **kwargs):
    try:
        return _slice_mesh_by_loop_extrude(*args, **kwargs)
    except LoopBooleanError:
        solvers = [item.identifier for item in bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items]
        if 'MANIFOLD' in solvers and kwargs.get('_solver', 'EXACT') != 'MANIFOLD':
            return _slice_mesh_by_loop_extrude(*args, **kwargs, _solver='MANIFOLD')
        raise


def _slice_mesh_by_loop_extrude(
    obj: bpy.types.Object,
    target_name: str,
    indices: List[int],
    seed_face_idx: int,
    depth_mm: float,
    through_cut: bool = False,
    scene: Optional[bpy.types.Scene] = None,
    part_clearance_mm: float = 0.0,
    part_clearance_apply_to: str = 'PART',
    part_clearance_bottom_mm: Optional[float] = None,
    _solver: str = 'EXACT',
) -> LoopSliceResult:
    """Corta o modelo extraindo o volume delimitado pelo contorno até a profundidade especificada.

    Parte A preserva integralmente a região selecionada e a une ao trecho
    profundo do prisma quando necessário; o fallback projetado só é permitido
    quando contém por completo a superfície selecionada. Parte B é o restante.
    """
    actual_scene = scene if scene else bpy.context.scene
    multi=captured_region_faces(obj,indices,seed_face_idx,actual_scene)
    if multi:
        from .geometry_regions import slice_surface_region
        return slice_surface_region(obj,multi,depth_mm,actual_scene,'EXTRUDE',part_clearance_mm,
                                    part_clearance_apply_to,part_clearance_bottom_mm,
                                    obj.data.polygons[seed_face_idx].material_index,source_mode='LOOP',through_cut=through_cut)
    scale_to_mm = get_scene_scale_to_mm(actual_scene)

    analysis = analyze_loop_region(obj, indices, seed_face_idx, scene=actual_scene)
    max_avail_mm = analysis["max_avail_depth_mm"]
    coords = analysis['coords_world']
    center = analysis['centroid_world']
    inward_dir = analysis["inward_dir_world"]
    n_out = -inward_dir
    support = center + n_out * min((p-center).dot(n_out) for p in coords)
    # A planar support below the complete boundary produces a flat mating base.
    footprint = [p - n_out*(p-support).dot(n_out) for p in coords]
    # Validação de espessura (T09)
    if not analysis.get("thickness_determined", True) and not through_cut:
        raise ValueError(
            "Espessura da peça não pôde ser determinada no ponto selecionado. "
            "Defina a profundidade manualmente ou ative a opção 'Corte Passante'."
        )

    if depth_mm > (max_avail_mm + 1e-3) and not through_cut:
        raise LocalizedGeometryError('geometry.wall_thickness', depth=depth_mm, available=max_avail_mm)

    if not analysis.get("is_planar_region", False) and len(coords) >= 6:
        stepped_check = build_stepped_cap_triangles(coords, step_depth_bu=depth_mm / scale_to_mm)
        if stepped_check is not None:
            return slice_mesh_by_loop(
                obj,
                target_name,
                indices,
                seed_face_idx,
                scene=actual_scene,
                detach_add_base=False,
                part_clearance_mm=part_clearance_mm,
                part_clearance_apply_to=part_clearance_apply_to,
                part_clearance_bottom_mm=part_clearance_bottom_mm,
                _override_step_depth_mm=depth_mm,
            )

    has_protrusion = (not analysis.get("is_planar_region", False)) or (analysis.get("protrusion_height_mm", 0.0) >= 0.2)
    if has_protrusion and (not through_cut or depth_mm < max_avail_mm):
        try:
            return slice_mesh_by_loop(
                obj,
                target_name,
                indices,
                seed_face_idx,
                scene=actual_scene,
                detach_add_base=True,
                detach_base_depth_mm=depth_mm,
                detach_base_clearance_mm=0.0,
                part_clearance_mm=part_clearance_mm,
                part_clearance_apply_to=part_clearance_apply_to,
                part_clearance_bottom_mm=part_clearance_bottom_mm,
            )
        except LocalizedGeometryError as error:
            from .localized_errors import MESSAGE_MARKER
            if error.payload.get(MESSAGE_MARKER) != 'geometry.closing_intersection':
                raise
        except ValueError:
            pass
    if part_clearance_mm > 0.0 and not through_cut and part_clearance_bottom_mm is None:
        if part_clearance_mm >= depth_mm - 0.1:
            raise LocalizedGeometryError('geometry.clearance_excessive')

    coords_world = footprint
    inward_dir = analysis["inward_dir_world"]
    depth_bu = depth_mm / scale_to_mm

    protrusion_h_bu = analysis["protrusion_height_mm"] / scale_to_mm
    outward_ext_bu = max(0.5 / scale_to_mm, protrusion_h_bu + (center-support).length + 0.5 / scale_to_mm)

    if through_cut and depth_mm >= max_avail_mm:
        depth_bu = max(depth_bu, (max_avail_mm / scale_to_mm) + (1.0 / scale_to_mm))

    clearance_bu = (part_clearance_mm / scale_to_mm) if part_clearance_mm > 0.0 else 0.0
    if through_cut:
        bottom_bu = 0.0
    elif part_clearance_bottom_mm is None:
        bottom_bu = clearance_bu
    else:
        bottom_bu = max(0.0, part_clearance_bottom_mm) / scale_to_mm
        if bottom_bu * scale_to_mm >= depth_mm - 0.1:
            raise LocalizedGeometryError('geometry.clearance_excessive')

    if part_clearance_apply_to == 'PART':
        depth_a_bu = depth_bu if through_cut else max(0.05 / scale_to_mm, depth_bu - bottom_bu)
        depth_b_bu = depth_bu
        lat_off_a = clearance_bu
        lat_off_b = 0.0
    elif part_clearance_apply_to == 'CAVITY':
        depth_a_bu = depth_bu
        depth_b_bu = depth_bu if through_cut else (depth_bu + bottom_bu)
        lat_off_a = 0.0
        lat_off_b = -clearance_bu
    elif part_clearance_apply_to == 'BOTH':
        depth_a_bu = depth_bu if through_cut else max(0.05 / scale_to_mm, depth_bu - 0.5 * bottom_bu)
        depth_b_bu = depth_bu if through_cut else (depth_bu + 0.5 * bottom_bu)
        lat_off_a = 0.5 * clearance_bu
        lat_off_b = -0.5 * clearance_bu
    else:
        depth_a_bu = depth_bu
        depth_b_bu = depth_bu
        lat_off_a = 0.0
        lat_off_b = 0.0

    if not through_cut and depth_b_bu > depth_bu and (depth_b_bu * scale_to_mm) > (max_avail_mm + 1e-3):
        raise LocalizedGeometryError('geometry.clearance_excessive')

    prism_obj = None
    prism_b = None
    temp_obj_a = None
    temp_obj_b = None
    eval_obj_a = None
    eval_obj_b = None
    eval_a = None
    eval_b = None
    temp_obj_plug = None
    starter_bm_a = None
    starter_bm_b = None
    if has_protrusion and through_cut and depth_mm >= max_avail_mm and max_avail_mm > 0.4:
        starter_mm = min(1.0, max(0.2, 0.25 * max_avail_mm))
        try:
            starter_res = slice_mesh_by_loop(
                obj,
                target_name,
                indices,
                seed_face_idx,
                scene=actual_scene,
                detach_add_base=True,
                detach_base_depth_mm=starter_mm,
                detach_base_clearance_mm=0.0,
                part_clearance_mm=part_clearance_mm,
                part_clearance_apply_to=part_clearance_apply_to,
                part_clearance_bottom_mm=0.0,
            )
            starter_bm_a, starter_bm_b = starter_res[0], starter_res[1]
            outward_ext_bu = -0.5 * (starter_mm / scale_to_mm)
        except Exception:
            starter_bm_a = None
            starter_bm_b = None

    try:
        if starter_bm_a is None and _selected_region_overhangs_footprint(obj, analysis, scale_to_mm):
            raise LocalizedGeometryError('geometry.depth_region_overhang')
        prism_obj = create_loop_prism_cutter(
            coords_world=coords_world,
            inward_dir=inward_dir,
            depth_bu=depth_a_bu,
            outward_ext_bu=outward_ext_bu,
            name=f"{target_name}_loop_prism_a",
            lateral_offset_bu=lat_off_a,
        )

        for mat in obj.data.materials:
            prism_obj.data.materials.append(mat)
        source_mat = obj.data.polygons[seed_face_idx].material_index
        for face in prism_obj.data.polygons:
            face.material_index = source_mat
        bpy.context.view_layer.update()

        temp_obj_a = obj.copy()
        from .geometry_clearance import triangulated_source_mesh
        temp_obj_a.data = triangulated_source_mesh(obj.data)
        temp_obj_a.hide_viewport = False
        temp_obj_a.hide_render = False
        actual_scene.collection.objects.link(temp_obj_a)
        mod_a = temp_obj_a.modifiers.new(name="Extrude_Intersect", type='BOOLEAN')
        mod_a.operation = 'INTERSECT'
        mod_a.solver = _solver
        mod_a.object = prism_obj
        if starter_bm_a is not None and starter_bm_b is not None:
            from mathutils import Matrix
            m_plug = bpy.data.meshes.new(f"{target_name}_plug_mesh")
            for mat in obj.data.materials:
                m_plug.materials.append(mat)
            bpy.data.meshes.remove(m_plug, do_unlink=True)
            m_plug = triangulated_source_mesh(obj.data)
            for face in m_plug.polygons:
                face.material_index = source_mat
            temp_obj_plug = bpy.data.objects.new(f"{target_name}_plug_obj", m_plug)
            temp_obj_plug.matrix_world = obj.matrix_world.copy()
            actual_scene.collection.objects.link(temp_obj_plug)
            mod_p = temp_obj_plug.modifiers.new(name="Plug_Intersect", type='BOOLEAN')
            mod_p.operation = 'INTERSECT'
            mod_p.solver = _solver
            mod_p.object = prism_obj

            old_m_a = temp_obj_a.data
            m_top_a = bpy.data.meshes.new(f"{target_name}_top_a_mesh")
            for mat in obj.data.materials:
                m_top_a.materials.append(mat)
            _triangulate_retained_source_faces(
                starter_bm_a,
                obj,
                analysis.get('region_face_indices', ()),
            )
            starter_bm_a.to_mesh(m_top_a)
            temp_obj_a.data = m_top_a
            temp_obj_a.matrix_world = Matrix.Identity(4)
            if old_m_a and old_m_a.users == 0:
                bpy.data.meshes.remove(old_m_a, do_unlink=True)
            mod_a.operation = 'UNION'
            mod_a.object = temp_obj_plug

        # Independent operand for Part B cavity (with its own lateral/axial clearance and receiver material).
        prism_b = create_loop_prism_cutter(
            coords_world=coords_world,
            inward_dir=inward_dir,
            depth_bu=depth_b_bu,
            outward_ext_bu=outward_ext_bu,
            name=f"{target_name}_loop_prism_b",
            lateral_offset_bu=lat_off_b,
        )
        for mat in obj.data.materials:
            prism_b.data.materials.append(mat)
        from collections import Counter
        body_mats = [f.material_index for f in obj.data.polygons if f.index != seed_face_idx]
        body_mat = Counter(body_mats).most_common(1)[0][0] if body_mats else source_mat
        for face in prism_b.data.polygons:
            face.material_index = body_mat
        temp_obj_b = obj.copy()
        temp_obj_b.data = triangulated_source_mesh(obj.data)
        temp_obj_b.hide_viewport = False
        temp_obj_b.hide_render = False
        actual_scene.collection.objects.link(temp_obj_b)
        mod_b = temp_obj_b.modifiers.new(name="Extrude_Difference", type='BOOLEAN')
        mod_b.operation = 'DIFFERENCE'
        mod_b.solver = _solver
        mod_b.object = prism_b
        if starter_bm_b is not None:
            from mathutils import Matrix
            old_m_b = temp_obj_b.data
            m_body_b = bpy.data.meshes.new(f"{target_name}_body_b_mesh")
            for mat in obj.data.materials:
                m_body_b.materials.append(mat)
            starter_bm_b.to_mesh(m_body_b)
            temp_obj_b.data = m_body_b
            temp_obj_b.matrix_world = Matrix.Identity(4)
            if old_m_b and old_m_b.users == 0:
                bpy.data.meshes.remove(old_m_b, do_unlink=True)

        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()

        eval_obj_a = temp_obj_a.evaluated_get(dg)
        eval_a = eval_obj_a.to_mesh()

        eval_obj_b = temp_obj_b.evaluated_get(dg)
        eval_b = eval_obj_b.to_mesh()

        bm_a = bmesh.new()
        bm_a.from_mesh(eval_a)
        bm_a.transform(temp_obj_a.matrix_world)
        bm_a.normal_update()

        bm_b = bmesh.new()
        bm_b.from_mesh(eval_b)
        bm_b.transform(temp_obj_b.matrix_world)
        bm_b.normal_update()

        # EXACT may retain coincident intersection endpoints at coplanar source edges.
        # Collapse only connected edges below 0.0001 mm, then keep strict validation.
        from .geometry_clearance import weld_boolean_roundoff
        weld_boolean_roundoff(bm_a, scale_to_mm)
        weld_boolean_roundoff(bm_b, scale_to_mm)
        bmesh.ops.dissolve_degenerate(bm_a, edges=bm_a.edges[:], dist=max(0.0001 / scale_to_mm, 5e-7))
        bmesh.ops.dissolve_degenerate(bm_b, edges=bm_b.edges[:], dist=max(0.0001 / scale_to_mm, 5e-7))
        bm_a.normal_update()
        bm_b.normal_update()

        if any(not e.is_manifold for e in bm_a.edges) or any(not e.is_manifold for e in bm_b.edges):
            bm_a.free()
            bm_b.free()
            raise LoopBooleanError("A extração com profundidade gerou malha não-manifold.")

        if len(bm_a.verts) == 0 or len(bm_b.verts) == 0:
            bm_a.free()
            bm_b.free()
            raise RuntimeError("A extração com profundidade gerou malha vazia para uma das partes.")

        bmesh.ops.recalc_face_normals(bm_a, faces=bm_a.faces[:])
        bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces[:])

        iface_tris = None
        through_hole = through_cut and (depth_mm >= max_avail_mm - 1e-3)
        if through_hole:
            interface_origin = support
            interface_boundary = coords_world
        else:
            interface_origin = support + (depth_mm / scale_to_mm) * inward_dir
            interface_boundary = [p + (depth_mm / scale_to_mm) * inward_dir for p in coords_world]
            u_i, v_i = _get_orthonormal_basis(inward_dir)
            pts_i = [Vector(((p - interface_origin).dot(u_i), (p - interface_origin).dot(v_i))) for p in interface_boundary]
            tris_i = triangulate_polygon_2d(pts_i)
            if tris_i:
                iface_tris = [(interface_boundary[t[0]], interface_boundary[t[1]], interface_boundary[t[2]]) for t in tris_i]
        cut_interface = build_cut_interface(
            origin_world=interface_origin,
            normal_a_to_b=inward_dir,
            boundary_points_world=interface_boundary,
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

        for st_bm in (starter_bm_a, starter_bm_b):
            if st_bm is not None:
                try:
                    st_bm.free()
                except Exception:
                    pass
        for temp_o in (temp_obj_a, temp_obj_b, temp_obj_plug, prism_b):
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
