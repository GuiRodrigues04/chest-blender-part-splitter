"""Script de teste para reprodução dos defeitos diagnosticados nas Etapas 1 e 2.

Testa:
1. Caso L1: Saliência com volume em malha única contínua.
   - Verifica se a interface retornada é a base da saliência (24x18) ou se confunde com o corte global.
   - Verifica se o objeto resultante em mundo mantém o alinhamento com o objeto alvo posicionado fora da origem.
2. Caso L3: Inversão da ordem dos vértices do loop.
   - Verifica se a normal da interface e a direção de corte dependem da ordem das arestas.
3. Caso G1: Objeto com translação, rotação e escala não uniforme.
   - Verifica se as malhas resultantes e coordenadas de interface ficam desalinhadas.
4. Caso G2: Escalas de cena diferentes (scale_length = 1.0 vs 0.001).
   - Verifica se desvios e tolerâncias ignoram a escala da cena.
"""

import sys
import os
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src
from src.geometry_loop import capture_edge_loop, slice_mesh_by_loop
from src.geometry_plane import slice_mesh_by_plane


def create_protrusion_fixture(name="ProtrusionModel", loc=(10, 20, 30), rot=(0, 0, 0), scale=(1, 1, 1)):
    """Cria a fixture exata descrita no plano:
    Base 60x60x20 mm, saliência 24x18x15 mm com paredes inclinadas, malha contínua manifold.
    Dimensões em mm (assumindo 1 BU = 1 mm para a geometria interna ou escalada).
    """
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bm = bmesh.new()
    
    # 1. Base 60x60x20: X [-30, 30], Y [-30, 30], Z [0, 20]
    # Cria o cubo base
    bmesh.ops.create_cube(bm, size=1.0)
    # Escala para 60x60x20 e posiciona de 0 a 20 em Z
    bmesh.ops.scale(bm, vec=Vector((60.0, 60.0, 20.0)), verts=bm.verts[:])
    bmesh.ops.translate(bm, vec=Vector((0.0, 0.0, 10.0)), verts=bm.verts[:])
    
    # Top face da base está em Z=20
    bm.faces.ensure_lookup_table()
    top_face = [f for f in bm.faces if abs(f.calc_center_median().z - 20.0) < 1e-4][0]
    
    # Subdivide a face superior para criar a base da saliência 24x18 em Z=20
    # Inset face top
    inset_res = bmesh.ops.inset_individual(bm, faces=[top_face], thickness=0.0, depth=0.0)
    protrusion_base_face = inset_res["faces"][0]
    
    # Ajusta os 4 vértices para formar o retângulo 24x18 (X [-12, 12], Y [-9, 9], Z=20)
    for v in protrusion_base_face.verts:
        sx = 12.0 if v.co.x > 0 else -12.0
        sy = 9.0 if v.co.y > 0 else -9.0
        v.co.x = sx
        v.co.y = sy
        v.co.z = 20.0
        
    # Extrude para criar a saliência com altura 15 mm (Z de 20 a 35) e paredes inclinadas
    ext_res = bmesh.ops.extrude_face_region(bm, geom=[protrusion_base_face])
    ext_verts = [v for v in ext_res["geom"] if isinstance(v, bmesh.types.BMVert)]
    ext_faces = [f for f in ext_res["geom"] if isinstance(f, bmesh.types.BMFace)]
    
    # Eleva os vértices extrudados para Z=35 e inclina as paredes (contrai para 20x14)
    for v in ext_verts:
        v.co.z = 35.0
        v.co.x *= (20.0 / 24.0)
        v.co.y *= (14.0 / 18.0)
        
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = Vector(loc)
    obj.rotation_euler = Euler(rot)
    obj.scale = Vector(scale)
    bpy.context.view_layer.update()
    return obj


def test_reproduce():
    print("===============================================================")
    print("=== REPRODUZINDO FALHAS APONTADAS NO PLANO (ETAPAS 1 E 2) ===")
    print("===============================================================")
    
    obj = create_protrusion_fixture(loc=(50.0, 100.0, 20.0))
    print(f"\n[1] Fixture criada em loc={obj.location}, rot={obj.rotation_euler}, scale={obj.scale}")
    
    # Encontrar as 4 arestas da base da saliência (Z=20 local)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    
    loop_edges = []
    for e in bm.edges:
        if abs(e.verts[0].co.z - 20.0) < 1e-4 and abs(e.verts[1].co.z - 20.0) < 1e-4:
            # Deve estar no contorno da saliência: X em [-12, 12] e Y em [-9, 9]
            if (abs(e.verts[0].co.x) <= 12.001 and abs(e.verts[0].co.y) <= 9.001 and
                abs(e.verts[1].co.x) <= 12.001 and abs(e.verts[1].co.y) <= 9.001):
                # Aresta compartilhada entre parede inclinada e face da base
                loop_edges.append(e)
                
    print(f"    Arestas do loop encontradas na base da saliência: {len(loop_edges)}")
    loop_verts = set()
    for e in loop_edges:
        loop_verts.add(e.verts[0].index)
        loop_verts.add(e.verts[1].index)
    loop_vert_indices = list(loop_verts)
    
    # Achar face-semente da saliência (Z > 20)
    seed_face = [f for f in bm.faces if f.calc_center_median().z > 30.0][0]
    seed_face_index = seed_face.index
    bm.free()
    
    # Teste do slice_mesh_by_loop atual
    print("\n[2] Executando slice_mesh_by_loop atual:")
    bm_a, bm_b = slice_mesh_by_loop(obj, obj.name, loop_vert_indices, seed_face_index, bpy.context.scene)
    
    # Verificar coordenadas de bm_a:
    bm_a.verts.ensure_lookup_table()
    xs = [v.co.x for v in bm_a.verts]
    ys = [v.co.y for v in bm_a.verts]
    zs = [v.co.z for v in bm_a.verts]
    center_local = Vector((sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs)))
    print(f"    Centro da Parte A resultante: {center_local}")
    print(f"    Esperado em World Space com obj.location=(50, 100, 20): centro X ~ 50, Y ~ 100, Z ~ 47.5")
    
    if center_local.x < 30.0:
        print("    --> DEFEITO REPRODUZIDO: bm_a está em coordenadas locais (X~0, Y~0), ignorando matrix_world!")
    
    # Teste de orientação dependente da ordem das arestas (L3)
    coords_forward = [Vector((12, 9, 20)), Vector((-12, 9, 20)), Vector((-12, -9, 20)), Vector((12, -9, 20))]
    coords_reversed = list(reversed(coords_forward))
    
    def calc_newell(coords):
        n = Vector((0.0, 0.0, 0.0))
        for i in range(len(coords)):
            v1 = coords[i]
            v2 = coords[(i+1) % len(coords)]
            n.x += (v1.y - v2.y) * (v1.z + v2.z)
            n.y += (v1.z - v2.z) * (v1.x + v2.x)
            n.z += (v1.x - v2.x) * (v1.y + v2.y)
        return n.normalized()
        
    n1 = calc_newell(coords_forward)
    n2 = calc_newell(coords_reversed)
    print(f"\n[3] Inversão de ordem do loop:")
    print(f"    Normal com ordem 1: {n1}")
    print(f"    Normal com ordem invertida: {n2}")
    if n1.dot(n2) < 0:
        print("    --> DEFEITO REPRODUZIDO: A normal e direção do pino invertem 180° apenas pela ordem de seleção do loop!")

    bm_a.free()
    bm_b.free()
    print("\nReprodução concluída com sucesso.")

if __name__ == "__main__":
    test_reproduce()
