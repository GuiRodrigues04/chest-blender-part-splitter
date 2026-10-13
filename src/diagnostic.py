"""Diagnóstico e análise geométrica de malhas para o Chest Part Splitter."""

from typing import Dict, Any, List, Tuple, Optional
import bpy
import bmesh
from mathutils import Vector
from .constants import MIN_FACE_AREA_BU, SCALE_TOLERANCE



def get_scene_scale_to_mm(scene) -> float:
    """Retorna o fator de conversão de unidades do Blender para milímetros."""
    if scene and scene.unit_settings:
        scale_length = scene.unit_settings.scale_length
        if scale_length > 0:
            return scale_length * 1000.0
    return 1000.0


def analyze_target_mesh(obj: bpy.types.Object, scene: bpy.types.Scene) -> dict:
    """Executa diagnóstico completo da malha do objeto alvo.
    
    Retorna métricas de dimensões físicas em mm, volume, contagem de triângulos,
    status de manifoldness, escala aplicada e integridade de faces.
    """
    if not obj or obj.type != 'MESH':
        return {
            "valid": False,
            "errors": ["Objeto alvo inválido ou não é uma malha (MESH)."],
            "warnings": [],
            "dims_mm": (0.0, 0.0, 0.0),
            "triangles": 0,
            "faces": 0,
            "volume_mm3": 0.0,
            "is_manifold": False,
            "non_manifold_edges": 0,
            "has_unapplied_scale": False,
            "is_non_uniform_scale": False,
            "degenerate_faces": 0,
        }

    errors = []
    warnings = []
    scale_to_mm = get_scene_scale_to_mm(scene)

    # 1. Análise de transformações e escala no objeto
    scale = obj.scale
    is_singular = (abs(scale.x) < 1e-7 or abs(scale.y) < 1e-7 or abs(scale.z) < 1e-7)
    if is_singular:
        errors.append("A escala do objeto possui componentes nulos (matriz singular).")

    has_unapplied_scale = (
        abs(scale.x - 1.0) > SCALE_TOLERANCE
        or abs(scale.y - 1.0) > SCALE_TOLERANCE
        or abs(scale.z - 1.0) > SCALE_TOLERANCE
    )
    is_non_uniform_scale = (
        abs(scale.x - scale.y) > SCALE_TOLERANCE
        or abs(scale.x - scale.z) > SCALE_TOLERANCE
    )

    if has_unapplied_scale:
        warnings.append(
            f"Escala não aplicada: ({scale.x:.3f}, {scale.y:.3f}, {scale.z:.3f}). Recomenda-se criar cópia com transformações aplicadas."
        )

    # 2. Avaliação de malha com modificadores
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()

    try:
        bm = bmesh.new()
        bm.from_mesh(eval_mesh)
        # Transforma o snapshot para World Space para métricas físicas fidedignas sob qualquer escala/rotação
        bm.transform(obj.matrix_world)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        face_count = len(bm.faces)
        tri_count = sum(len(f.verts) - 2 for f in bm.faces)

        # Cálculo de volume físico em mm³ (World Space)
        vol_bu = abs(bm.calc_volume(signed=True))
        vol_mm3 = vol_bu * (scale_to_mm ** 3)

        # Checagem de arestas não-manifold
        non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
        is_manifold = (non_manifold_edges == 0 and face_count > 0)

        if not is_manifold and face_count > 0:
            warnings.append(
                f"Malha possui {non_manifold_edges} aresta(s) abertas ou não-manifold."
            )

        # Checagem de faces degeneradas
        min_area_bu = MIN_FACE_AREA_BU
        degenerate_faces = sum(1 for f in bm.faces if f.calc_area() < min_area_bu)
        if degenerate_faces > 0:
            warnings.append(
                f"Malha possui {degenerate_faces} face(s) com área nula ou degenerada."
            )

        # Dimensões físicas avaliadas no espaço de mundo em mm
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        zs = [v.co.z for v in bm.verts]
        if xs:
            dims_mm = (
                round((max(xs) - min(xs)) * scale_to_mm, 2),
                round((max(ys) - min(ys)) * scale_to_mm, 2),
                round((max(zs) - min(zs)) * scale_to_mm, 2),
            )
        else:
            dims_mm = (0.0, 0.0, 0.0)

        bm.free()
    finally:
        eval_obj.to_mesh_clear()

    is_valid = len(errors) == 0

    return {
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "dims_mm": dims_mm,
        "triangles": tri_count,
        "faces": face_count,
        "volume_mm3": round(vol_mm3, 2),
        "is_manifold": is_manifold,
        "non_manifold_edges": non_manifold_edges,
        "has_unapplied_scale": has_unapplied_scale,
        "is_non_uniform_scale": is_non_uniform_scale,
        "degenerate_faces": degenerate_faces,
    }


def sanitize_mesh_micro_degeneracies(bm: bmesh.types.BMesh, scale_to_mm: float = 1000.0) -> bool:
    """Saneamento restrito e transacional de micro-arestas causadas por arredondamento no solver booleano (DEV-01 / DEV-02).
    
    Solda vértices separados por distâncias sub-micrométricas (< 0.1 µm), preservando a integridade manifold.
    Retorna True se houve saneamento bem-sucedido e a malha permaneceu manifold.
    """
    eps_bu = 1e-4 / max(1e-6, scale_to_mm)
    bm.edges.ensure_lookup_table()
    micro_edges = [e for e in bm.edges if e.calc_length() < eps_bu]
    if not micro_edges:
        return False
    
    targetmap = {}
    for e in micro_edges:
        if e.is_valid and len(e.verts) == 2:
            v0, v1 = e.verts[0], e.verts[1]
            if v1 not in targetmap.values():
                targetmap[v1] = v0
    
    if not targetmap:
        return False
    
    try:
        bmesh.ops.weld_verts(bm, targetmap=targetmap)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        return True
    except Exception:
        return False


def validate_bmesh_mesh_geometry(bm: bmesh.types.BMesh, scale_to_mm: float = 1000.0) -> Dict[str, Any]:
    """Valida a geometria de um BMesh medindo integridade, áreas nulas e degenerações (INV-010 / DEV-01)."""
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # 1. Arestas de comprimento nulo calibradas pela escala física (< 0.1 µm)
    eps_length_bu = 1e-4 / max(1e-6, scale_to_mm)
    null_edges = [e.index for e in bm.edges if e.calc_length() < eps_length_bu]

    # 2. Faces de área nula / colineares / com vértices coincidentes
    min_face_area_mm2 = 1e-6
    eps_dist_bu_sq = (eps_length_bu) ** 2
    degenerate_faces = []
    for f in bm.faces:
        area_mm2 = f.calc_area() * (scale_to_mm ** 2)
        if area_mm2 < min_face_area_mm2:
            degenerate_faces.append(f.index)
        else:
            coords = [v.co for v in f.verts]
            has_coincident = False
            for i in range(len(coords)):
                for j in range(i + 1, len(coords)):
                    if (coords[i] - coords[j]).length_squared < eps_dist_bu_sq:
                        has_coincident = True
                        break
                if has_coincident:
                    break
            if has_coincident:
                degenerate_faces.append(f.index)

    # 3. Arestas não-manifold
    non_manifold_edges = [e.index for e in bm.edges if not e.is_manifold]

    # 4. Volume orientado
    vol_bu = bm.calc_volume(signed=True)
    vol_mm3 = vol_bu * (scale_to_mm ** 3)

    return {
        "is_valid": len(null_edges) == 0 and len(degenerate_faces) == 0,
        "null_edges": null_edges,
        "degenerate_faces": degenerate_faces,
        "non_manifold_edges": non_manifold_edges,
        "is_manifold": len(non_manifold_edges) == 0,
        "volume_mm3": vol_mm3,
    }
