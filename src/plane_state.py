"""Fonte única da geometria do plano de corte (origem/normal em World Space).

Sem efeitos colaterais: não cria coleções nem escreve em settings, portanto é
seguro chamar de callbacks de desenho GPU.
"""
import bpy
from mathutils import Vector

from .constants import COLLECTION_GUIDES_NAME, PLANE_GUIDE_NAME


def resolve_plane_state(scene, settings):
    """Retorna (origem, normal) mundiais do plano, SEM offset (aplicado à parte).

    Prioriza o matrix_world atual do objeto guia; senão usa os valores em settings.
    A normal usa a inversa transposta da matriz 3x3 (correta sob escala não uniforme).
    """
    guide = None
    col = bpy.data.collections.get(COLLECTION_GUIDES_NAME)
    if col is not None:
        guide = col.objects.get(PLANE_GUIDE_NAME)
    if guide is not None:
        mw = guide.matrix_world
        origin = mw.translation.copy()
        try:
            normal = (mw.to_3x3().inverted_safe().transposed() @ Vector((0.0, 0.0, 1.0)))
        except Exception:
            normal = mw.to_3x3() @ Vector((0.0, 0.0, 1.0))
        if normal.length > 1e-9:
            return origin, normal.normalized()
    return Vector(settings.plane_origin), Vector(settings.plane_normal).normalized()
