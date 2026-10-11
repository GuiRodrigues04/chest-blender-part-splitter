"""Motor geométrico para divisão por materiais com contrato de sólidos estanques (Fase 4 / Etapa 6).

Implementa os requisitos da Seção 9 do plano:
1. Componentes fechados (manifold) já definidos por slots de materiais são separados
   diretamente em sólidos fechados (manifold) para impressão 3D.
2. Fronteiras de materiais em superfícies contínuas são identificadas via loops de contorno
   e convertidas em sólidos estanques através do motor de extração prismática com profundidade,
   deixando a cavidade correspondente na peça receptora.
3. Preservação estrita de slots de materiais e índices de faces (Critério M1).
"""

import bpy
import bmesh
from mathutils import Vector
from typing import List, Dict, Any, Tuple, Optional
from .geometry_contract import CutInterface, SplitResult
from .geometry_loop import create_loop_prism_cutter, LoopSliceResult
from .geometry_plane import evaluate_bmesh_metrics
from .diagnostic import get_scene_scale_to_mm


def get_material_regions(bm, material_index: int) -> List[List[int]]:
    """Agrupa as faces de um material em regiões conectadas (ilhas) por arestas compartilhadas.

    Retorna listas de índices de faces, ordenadas pelo menor índice de face (ordem estável).
    """
    bm.faces.ensure_lookup_table()
    visited = set()
    regions: List[List[int]] = []
    for f in bm.faces:
        if f.material_index != material_index or f.index in visited:
            continue
        stack = [f]
        visited.add(f.index)
        region = []
        while stack:
            cur = stack.pop()
            region.append(cur.index)
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf.material_index == material_index and nf.index not in visited:
                        visited.add(nf.index)
                        stack.append(nf)
        regions.append(sorted(region))
    regions.sort(key=lambda r: r[0])
    return regions


def _order_boundary_loops(boundary_edges):
    """Ordena arestas de fronteira em um ou mais ciclos fechados de vértices.

    Retorna None se houver bifurcações (vértice com número de arestas diferente de 2).
    """
    vert_to_edges: Dict[Any, List[Any]] = {}
    for e in boundary_edges:
        for v in e.verts:
            vert_to_edges.setdefault(v, []).append(e)
    if not vert_to_edges or any(len(es) != 2 for es in vert_to_edges.values()):
        return None

    loops = []
    used_edges = set()
    for start_v in list(vert_to_edges.keys()):
        if all(e in used_edges for e in vert_to_edges[start_v]):
            continue
        ordered = [start_v]
        curr_v = start_v
        curr_e = next(e for e in vert_to_edges[start_v] if e not in used_edges)
        while True:
            used_edges.add(curr_e)
            next_v = curr_e.other_vert(curr_v)
            if next_v == start_v:
                break
            ordered.append(next_v)
            es = vert_to_edges[next_v]
            curr_e = es[0] if es[1] == curr_e else es[1]
            curr_v = next_v
        loops.append(ordered)
    return loops


def list_material_regions(obj: bpy.types.Object, material_index: int) -> List[Dict[str, Any]]:
    """Resumo das regiões (ilhas) de um material, para exibição na interface."""
    if not obj or obj.type != 'MESH':
        return []
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    regions = get_material_regions(bm, material_index)
    bm.free()
    return [{"index": i, "face_count": len(r), "first_face": r[0]} for i, r in enumerate(regions)]


def find_region_of_face(obj: bpy.types.Object, face_index: int) -> Tuple[int, int]:
    """Retorna (material_index, region_index) da face informada, ou (-1, -1)."""
    if not obj or obj.type != 'MESH' or face_index < 0 or face_index >= len(obj.data.polygons):
        return (-1, -1)
    mat_idx = obj.data.polygons[face_index].material_index
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    regions = get_material_regions(bm, mat_idx)
    bm.free()
    for i, r in enumerate(regions):
        if face_index in r:
            return (mat_idx, i)
    return (mat_idx, -1)


def analyze_material_structure(obj: bpy.types.Object, material_index: int, region_index: int = 0) -> Dict[str, Any]:
    """Analisa a topologia de UMA região conectada (ilha) de faces de um material.

    Um mesmo material pode aparecer em várias áreas separadas do modelo (ex: dois quadrados
    rosa em lados diferentes). Cada área é tratada como uma região independente, com seu
    próprio contorno e direção de extração.
    """
    if not obj or obj.type != 'MESH':
        return {"valid": False, "error": "Objeto inválido."}

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    total_faces = len(bm.faces)
    regions = get_material_regions(bm, material_index)

    if not regions:
        bm.free()
        return {"valid": False, "error": f"Nenhuma face com o material #{material_index} encontrada.", "region_count": 0}

    region_count = len(regions)
    region_index = max(0, min(region_index, region_count - 1))
    region_faces = set(regions[region_index])

    if len(region_faces) == total_faces:
        bm.free()
        return {"valid": False, "error": "Todas as faces do modelo já utilizam este material.", "region_count": region_count}

    target_faces = [bm.faces[i] for i in region_faces]

    # Arestas de fronteira da região: uma face dentro e outra fora da região
    boundary_edges = []
    for e in bm.edges:
        inside = [f for f in e.link_faces if f.index in region_faces]
        if inside and len(inside) != len(e.link_faces):
            boundary_edges.append(e)

    base_info = {
        "region_count": region_count,
        "region_index": region_index,
        "region_face_indices": sorted(region_faces),
        "face_count": len(region_faces),
    }

    # Caso 1: região sem fronteira com outras faces -> componente fechado isolado
    if not boundary_edges:
        open_edges = [e for e in bm.edges
                      if any(f.index in region_faces for f in e.link_faces) and not e.is_manifold]
        is_manifold = len(open_edges) == 0
        bm.free()
        info = dict(base_info)
        info.update({
            "valid": True,
            "type": "CLOSED_COMPONENT",
            "description": "Componente 3D Fechado (Sólido estanque)",
            "is_manifold": is_manifold,
            "boundary_loops": [],
        })
        return info

    # Caso 2: região superficial com contorno
    loops = _order_boundary_loops(boundary_edges)
    if loops is None:
        bm.free()
        info = dict(base_info)
        info.update({
            "valid": False,
            "type": "COMPLEX_BOUNDARY",
            "error": "O contorno desta região tem bifurcações (cantos tocando outras regiões).",
        })
        return info

    if len(loops) > 1:
        bm.free()
        info = dict(base_info)
        info.update({
            "valid": False,
            "type": "BASE_REGION",
            "error": "Esta região é o corpo/base (envolve outras áreas). Escolha a cor da área menor.",
        })
        return info

    ordered_verts = loops[0]
    coords_world = [obj.matrix_world @ v.co for v in ordered_verts]
    centroid = sum(coords_world, Vector()) / len(coords_world)

    # Normal média do contorno via Newell
    n = Vector((0.0, 0.0, 0.0))
    n_pts = len(coords_world)
    for i in range(n_pts):
        v1 = coords_world[i]
        v2 = coords_world[(i + 1) % n_pts]
        n.x += (v1.y - v2.y) * (v1.z + v2.z)
        n.y += (v1.z - v2.z) * (v1.x + v2.x)
        n.z += (v1.x - v2.x) * (v1.y + v2.y)
    if n.length > 1e-6:
        n.normalize()
    else:
        n = Vector((0.0, 0.0, 1.0))

    # Direção para dentro a partir da média ponderada por área das normais da região
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    avg_norm = sum(((normal_matrix @ f.normal) * f.calc_area() for f in target_faces), Vector())
    if avg_norm.length > 1e-9:
        avg_norm.normalize()
    else:
        avg_norm = n
    inward_dir = -avg_norm

    bm.free()

    info = dict(base_info)
    info.update({
        "valid": True,
        "type": "SURFACE_PATCH",
        "description": "Fronteira na Superfície (Requer profundidade de extração)",
        "coords_world": coords_world,
        "centroid_world": centroid,
        "normal_world": n,
        "inward_dir_world": inward_dir,
    })
    return info


def create_material_patch_prism_cutter(
    obj: bpy.types.Object,
    region_face_indices: List[int],
    inward_dir: Vector,
    depth_bu: float,
    outward_ext_bu: float = 1e-3,
    name: str = "temp_mat_prism",
) -> bpy.types.Object:
    """Constrói um prisma 3D estanque a partir das faces exatas da região de material (B06).
    
    Preserva a tesselação e concavidades reais da região (ex: silhuetas em U ou reentrâncias),
    evitando tampas em n-gons planos que cruzam aberturas e geram películas/membranas espúrias.
    """
    bm_src = bmesh.new()
    bm_src.from_mesh(obj.data)
    bm_src.transform(obj.matrix_world)
    bm_src.verts.ensure_lookup_table()
    bm_src.edges.ensure_lookup_table()
    bm_src.faces.ensure_lookup_table()

    region_set = set(region_face_indices)
    region_faces = [bm_src.faces[i] for i in region_face_indices if i < len(bm_src.faces)]

    in_norm = inward_dir.normalized()
    bm_prism = bmesh.new()

    top_map = {}
    bot_map = {}
    used_verts = {v for f in region_faces for v in f.verts}

    for v in used_verts:
        top_map[v] = bm_prism.verts.new(v.co - outward_ext_bu * in_norm)
        bot_map[v] = bm_prism.verts.new(v.co + depth_bu * in_norm)

    bm_prism.verts.ensure_lookup_table()

    # Tampas superior e inferior preservando a tesselação exata das faces
    for f in region_faces:
        bm_prism.faces.new([top_map[v] for v in f.verts])
        bm_prism.faces.new(reversed([bot_map[v] for v in f.verts]))

    # Paredes laterais apenas nas arestas de fronteira da região
    for e in bm_src.edges:
        inc = [f for f in e.link_faces if f.index in region_set]
        if len(inc) == 1:
            f = inc[0]
            v1, v2 = e.verts[0], e.verts[1]
            f_v = list(f.verts)
            idx1 = f_v.index(v1)
            if f_v[(idx1 + 1) % len(f_v)] == v2:
                va, vb = v1, v2
            else:
                va, vb = v2, v1
            bm_prism.faces.new((top_map[vb], top_map[va], bot_map[va], bot_map[vb]))

    bm_src.free()

    bmesh.ops.triangulate(bm_prism, faces=bm_prism.faces[:])
    bmesh.ops.recalc_face_normals(bm_prism, faces=bm_prism.faces[:])

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm_prism.to_mesh(mesh)
    bm_prism.free()

    prism_obj = bpy.data.objects.new(name, mesh)
    prism_obj.hide_viewport = False
    prism_obj.hide_render = False
    bpy.context.scene.collection.objects.link(prism_obj)
    return prism_obj


def slice_mesh_by_material(
    obj: bpy.types.Object,
    material_index: int,
    depth_mm: float = 5.0,
    scene: Optional[bpy.types.Scene] = None,
    through_cut: bool = False,
    region_index: int = 0,
) -> LoopSliceResult:
    """Realiza a separação da malha com base em uma região do material selecionado.
    
    Garante peças sólidas 100% manifold em ambos os casos (componentes ou superfície).
    """
    actual_scene = scene if scene else bpy.context.scene
    scale_to_mm = get_scene_scale_to_mm(actual_scene)

    analysis = analyze_material_structure(obj, material_index, region_index)
    if not analysis["valid"]:
        raise ValueError(analysis.get("error", "Estrutura de material não suportada."))

    mat_type = analysis["type"]

    if mat_type == "CLOSED_COMPONENT":
        region_set = set(analysis["region_face_indices"])
        # Separação direta de componente estanque já fechado
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)

        bm_a = bm.copy()
        bm_a.faces.ensure_lookup_table()
        bmesh.ops.delete(bm_a, geom=[f for f in bm_a.faces if f.index not in region_set], context='FACES')

        bm_b = bm.copy()
        bm_b.faces.ensure_lookup_table()
        bmesh.ops.delete(bm_b, geom=[f for f in bm_b.faces if f.index in region_set], context='FACES')

        bm.free()

        # Direção de separação A->B: do centro do componente para o centro do corpo
        ca = sum((v.co for v in bm_a.verts), Vector()) / max(1, len(bm_a.verts))
        cb = sum((v.co for v in bm_b.verts), Vector()) / max(1, len(bm_b.verts))
        sep = cb - ca
        sep_norm = sep.normalized() if sep.length > 1e-9 else Vector((0.0, 0.0, -1.0))

        # Cria interface simbólica
        cut_iface = CutInterface(
            origin_world=ca.copy(),
            normal_a_to_b_world=sep_norm,
            axis_u_world=Vector((1.0, 0.0, 0.0)),
            axis_v_world=Vector((0.0, 1.0, 0.0)),
            outer_contours_uv=[],
            hole_contours_uv=[],
            interface_triangles_world=[],
            is_planar=True,
            deviation_mm=0.0,
            source_mode='MATERIAL',
        )

        metrics_a = evaluate_bmesh_metrics(bm_a, scale_to_mm)
        metrics_b = evaluate_bmesh_metrics(bm_b, scale_to_mm)

        split_res = SplitResult(
            part_a_metrics=metrics_a,
            part_b_metrics=metrics_b,
            interface=cut_iface,
            diagnostics_before_connectors={
                "part_a_volume_mm3": metrics_a["volume_mm3"],
                "part_b_volume_mm3": metrics_b["volume_mm3"],
                "sum_volume_mm3": metrics_a["volume_mm3"] + metrics_b["volume_mm3"],
            },
            success=True,
        )
        return LoopSliceResult(bm_a, bm_b, split_res)

    else:
        # Superfície com contorno: extrai com profundidade via prisma booleano
        inward_dir = analysis["inward_dir_world"]
        depth_bu = depth_mm / scale_to_mm
        outward_ext_bu = max(0.5 / scale_to_mm, 1.0 / scale_to_mm)

        prism_obj = create_material_patch_prism_cutter(
            obj=obj,
            region_face_indices=analysis["region_face_indices"],
            inward_dir=inward_dir,
            depth_bu=depth_bu,
            outward_ext_bu=outward_ext_bu,
            name=f"{obj.name}_mat_prism",
        )

        try:
            bpy.context.view_layer.update()

            temp_obj_a = obj.copy()
            temp_obj_a.data = obj.data.copy()
            temp_obj_a.hide_viewport = False
            temp_obj_a.hide_render = False
            actual_scene.collection.objects.link(temp_obj_a)
            mod_a = temp_obj_a.modifiers.new(name="Mat_Intersect", type='BOOLEAN')
            mod_a.operation = 'INTERSECT'
            mod_a.solver = 'EXACT'
            mod_a.object = prism_obj

            temp_obj_b = obj.copy()
            temp_obj_b.data = obj.data.copy()
            temp_obj_b.hide_viewport = False
            temp_obj_b.hide_render = False
            actual_scene.collection.objects.link(temp_obj_b)
            mod_b = temp_obj_b.modifiers.new(name="Mat_Difference", type='BOOLEAN')
            mod_b.operation = 'DIFFERENCE'
            mod_b.solver = 'EXACT'
            mod_b.object = prism_obj

            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()

            eval_a = temp_obj_a.evaluated_get(dg)
            mesh_a = eval_a.to_mesh()
            eval_b = temp_obj_b.evaluated_get(dg)
            mesh_b = eval_b.to_mesh()

            bm_a = bmesh.new()
            bm_a.from_mesh(mesh_a)
            bm_b = bmesh.new()
            bm_b.from_mesh(mesh_b)

            eval_a.to_mesh_clear()
            eval_b.to_mesh_clear()

            # Transforma para World Space
            bm_a.transform(obj.matrix_world)
            bm_b.transform(obj.matrix_world)

            cut_iface = CutInterface(
                origin_world=analysis["centroid_world"],
                normal_a_to_b_world=inward_dir,
                axis_u_world=Vector((1.0, 0.0, 0.0)),
                axis_v_world=Vector((0.0, 1.0, 0.0)),
                outer_contours_uv=[],
                hole_contours_uv=[],
                interface_triangles_world=[],
                is_planar=True,
                deviation_mm=0.0,
                source_mode='MATERIAL',
            )

            metrics_a = evaluate_bmesh_metrics(bm_a, scale_to_mm)
            metrics_b = evaluate_bmesh_metrics(bm_b, scale_to_mm)

            # Validação geométrica estrita para sólidos imprimíveis (Seção 6)
            if metrics_a["faces"] == 0 or metrics_b["faces"] == 0:
                raise RuntimeError("O corte por material resultou em uma peça vazia. Verifique a área ou profundidade selecionada.")
            if metrics_a["volume_mm3"] <= 1e-4 or metrics_b["volume_mm3"] <= 1e-4:
                raise RuntimeError("O corte por material gerou uma peça com volume nulo ou desprezível.")
            if not metrics_a["is_manifold"] or not metrics_b["is_manifold"]:
                raise RuntimeError(
                    f"O corte por material gerou peça não-manifold "
                    f"(arestas abertas: Parte A={metrics_a['non_manifold_edges']}, Parte B={metrics_b['non_manifold_edges']})."
                )

            split_res = SplitResult(
                part_a_metrics=metrics_a,
                part_b_metrics=metrics_b,
                interface=cut_iface,
                diagnostics_before_connectors={
                    "part_a_volume_mm3": metrics_a["volume_mm3"],
                    "part_b_volume_mm3": metrics_b["volume_mm3"],
                    "sum_volume_mm3": metrics_a["volume_mm3"] + metrics_b["volume_mm3"],
                },
                success=True,
            )
            return LoopSliceResult(bm_a, bm_b, split_res)


        finally:
            # Limpeza estrita de temporários
            if temp_obj_a.name in actual_scene.collection.objects:
                actual_scene.collection.objects.unlink(temp_obj_a)
            mesh_data_a = temp_obj_a.data
            bpy.data.objects.remove(temp_obj_a, do_unlink=True)
            if mesh_data_a:
                bpy.data.meshes.remove(mesh_data_a, do_unlink=True)

            if temp_obj_b.name in actual_scene.collection.objects:
                actual_scene.collection.objects.unlink(temp_obj_b)
            mesh_data_b = temp_obj_b.data
            bpy.data.objects.remove(temp_obj_b, do_unlink=True)
            if mesh_data_b:
                bpy.data.meshes.remove(mesh_data_b, do_unlink=True)

            if prism_obj.name in actual_scene.collection.objects:
                actual_scene.collection.objects.unlink(prism_obj)
            prism_mesh = prism_obj.data
            bpy.data.objects.remove(prism_obj, do_unlink=True)
            if prism_mesh:
                bpy.data.meshes.remove(prism_mesh, do_unlink=True)
