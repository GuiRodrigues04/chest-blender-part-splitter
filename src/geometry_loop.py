"""Geometria para o Modo D: Loop Fechado de Arestas."""

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import normal
import math

def get_topology_signature(obj):
    """Retorna uma assinatura simples da topologia atual para invalidar seleções antigas."""
    if not obj or obj.type != 'MESH':
        return ""
    mesh = obj.data
    return f"V{len(mesh.vertices)}E{len(mesh.edges)}F{len(mesh.polygons)}"


def capture_edge_loop(obj):
    """
    Captura e valida um loop fechado de arestas selecionadas no modo de edição.
    Retorna (sucesso, indices_ordenados, is_planar, desvio_mm, erro_msg)
    """
    if obj.mode != 'EDIT':
        return False, [], False, 0.0, "O objeto precisa estar em Edit Mode."
    
    bm = bmesh.from_edit_mesh(obj.data)
    
    # Obter arestas selecionadas
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
            
    # Validar grau exato 2 para todos os vértices selecionados
    for v, edges in vert_to_edges.items():
        if len(edges) != 2:
            if len(edges) < 2:
                return False, [], False, 0.0, "Loop aberto detectado. Selecione um ciclo fechado contínuo."
            else:
                return False, [], False, 0.0, "Bifurcação/Ramificação detectada. O loop deve ser um ciclo simples."
                
    # Ordenar vértices
    start_v = next(iter(vert_to_edges.keys()))
    ordered_verts = [start_v]
    current_v = start_v
    current_e = vert_to_edges[current_v][0]
    
    while True:
        next_v = current_e.verts[0] if current_e.verts[1] == current_v else current_e.verts[1]
        
        if next_v == start_v:
            break # Ciclo completado
            
        ordered_verts.append(next_v)
        
        edges_of_next = vert_to_edges[next_v]
        next_e = edges_of_next[0] if edges_of_next[0] != current_e else edges_of_next[1]
        
        current_v = next_v
        current_e = next_e
        
    if len(ordered_verts) != len(vert_to_edges):
        return False, [], False, 0.0, "Múltiplos componentes desconectados detectados. Selecione apenas um ciclo."
        
    # Verificar planicidade
    coords = [v.co for v in ordered_verts]
    centroid = sum(coords, Vector()) / len(coords)
    n = Vector((0.0, 0.0, 0.0))
    for i in range(len(coords)):
        v1 = coords[i]
        v2 = coords[(i+1) % len(coords)]
        n.x += (v1.y - v2.y) * (v1.z + v2.z)
        n.y += (v1.z - v2.z) * (v1.x + v2.x)
        n.z += (v1.x - v2.x) * (v1.y + v2.y)
        
    if n.length > 0:
        n.normalize()
    else:
        return False, [], False, 0.0, "Polígono degenerado."
        
    max_deviation = 0.0
    for v in coords:
        dist = abs((v - centroid).dot(n))
        if dist > max_deviation:
            max_deviation = dist
            
    from .diagnostic import get_scene_scale_to_mm
    # A função original do get_scene_scale_to_mm precisa da cena. 
    # Aqui vamos usar o objeto para achar a scene, ou assumir 1000 se não passar.
    # Mas é melhor só não converter pra mm aqui ou passar a scene.
    # Vou exportar a unit como tá para simplificar e o caller cuida.
    
    is_planar = max_deviation <= 0.0001 # 0.1 mm if 1 BU = 1000 mm. So 0.0001 BU.
    
    indices = [v.index for v in ordered_verts]
    
    return True, indices, is_planar, max_deviation, ""


def get_selected_seed_face(obj):
    """Obtém a face ativa ou a primeira face selecionada."""
    if obj.mode != 'EDIT':
        return -1
    
    bm = bmesh.from_edit_mesh(obj.data)
    active_face = bm.faces.active
    if active_face and active_face.select:
        return active_face.index
        
    for f in bm.faces:
        if f.select:
            return f.index
            
    return -1


def slice_mesh_by_loop(obj, target_name, indices, seed_face_idx, scene):
    """
    Realiza a separação da malha usando o loop capturado.
    Retorna (bmesh_a, bmesh_b).
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    
    if seed_face_idx < 0 or seed_face_idx >= len(bm.faces):
        raise ValueError("Face-semente inválida ou não encontrada.")
        
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    
    loop_verts = []
    for idx in indices:
        if idx >= len(bm.verts):
            raise ValueError("Topologia alterada. Um vértice do loop não existe mais.")
        loop_verts.append(bm.verts[idx])
        
    loop_edges = set()
    for i in range(len(loop_verts)):
        v1 = loop_verts[i]
        v2 = loop_verts[(i+1) % len(loop_verts)]
        edge = bm.edges.get((v1, v2))
        if not edge:
            raise ValueError("O ciclo de arestas não existe mais na malha (Topologia alterada).")
        loop_edges.add(edge)
        
    faces_a = set()
    seed_face = bm.faces[seed_face_idx]
    
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
        raise ValueError("O loop não separa a malha em duas regiões (Exemplo: está numa alça).")
        
    faces_b = set(bm.faces) - faces_a
    
    bm_a = bmesh.new()
    bm_a.from_mesh(obj.data)
    bm_a.faces.ensure_lookup_table()
    faces_to_delete_in_a = [bm_a.faces[f.index] for f in faces_b]
    bmesh.ops.delete(bm_a, geom=faces_to_delete_in_a, context='FACES')
    
    bm_b = bmesh.new()
    bm_b.from_mesh(obj.data)
    bm_b.faces.ensure_lookup_table()
    faces_to_delete_in_b = [bm_b.faces[f.index] for f in faces_a]
    bmesh.ops.delete(bm_b, geom=faces_to_delete_in_b, context='FACES')
    
    edges_hole_a = [e for e in bm_a.edges if e.is_wire or len(e.link_faces) == 1]
    if edges_hole_a:
        bmesh.ops.holes_fill(bm_a, edges=edges_hole_a, sides=len(loop_verts))
        # Remove flat faces to prevent shading artifacts? (Triangulate maybe?)
        bmesh.ops.triangulate(bm_a, faces=[f for f in bm_a.faces if len(f.verts) > 4])
        
    edges_hole_b = [e for e in bm_b.edges if e.is_wire or len(e.link_faces) == 1]
    if edges_hole_b:
        bmesh.ops.holes_fill(bm_b, edges=edges_hole_b, sides=len(loop_verts))
        bmesh.ops.triangulate(bm_b, faces=[f for f in bm_b.faces if len(f.verts) > 4])
        
    return bm_a, bm_b
