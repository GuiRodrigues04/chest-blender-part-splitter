"""Diagnóstico e análise geométrica de malhas para o Chest Part Splitter."""

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
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        face_count = len(bm.faces)
        tri_count = sum(len(f.verts) - 2 for f in bm.faces)

        # Cálculo de volume físico em mm³
        vol_bu = bm.calc_volume(signed=False)
        vol_mm3 = vol_bu * (scale_to_mm ** 3)

        # Checagem de arestas não-manifold
        non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
        is_manifold = (non_manifold_edges == 0 and face_count > 0)

        if not is_manifold and face_count > 0:
            warnings.append(
                f"Malha possui {non_manifold_edges} aresta(s) abertas ou não-manifold."
            )

        # Checagem de faces degeneradas
        degenerate_faces = sum(1 for f in bm.faces if f.calc_area() < MIN_FACE_AREA_BU)
        if degenerate_faces > 0:
            warnings.append(
                f"Malha possui {degenerate_faces} face(s) com área nula ou degenerada."
            )

        # Dimensões físicas avaliadas em mm
        dims = eval_obj.dimensions * scale_to_mm
        dims_mm = (round(dims.x, 2), round(dims.y, 2), round(dims.z, 2))

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
