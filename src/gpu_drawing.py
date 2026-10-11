"""Módulo de desenho GPU para sobreposição do contorno capturado no Viewport (F01).

Exibe uma linha destacada e persistente ao longo do contorno de arestas capturado,
permitindo ao usuário selecionar a face semente ou inspecionar o modelo sem perder
a referência visual do corte.
"""

import bpy
from typing import Optional, List
from mathutils import Vector

_draw_handler = None


def _draw_loop_overlay_callback():
    """Callback de desenho executado no espaço 3D (SpaceView3D)."""
    context = bpy.context
    if not context or not hasattr(context, "scene") or not hasattr(context.scene, "chest_splitter"):
        return

    settings = context.scene.chest_splitter
    if not getattr(settings, "show_loop_highlight", True):
        return

    if not getattr(settings, "loop_is_captured", False):
        return

    target = getattr(settings, "target_object", None)
    if not target or target.name not in bpy.data.objects or target.type != 'MESH':
        return

    indices_str = getattr(settings, "loop_vertex_indices", "")
    if not indices_str:
        return

    try:
        indices = [int(i) for i in indices_str.split(',') if i.strip()]
    except ValueError:
        return

    if len(indices) < 2:
        return

    mesh = target.data
    if not mesh or not mesh.vertices:
        return

    max_idx = max(indices)
    if max_idx >= len(mesh.vertices):
        return

    mw = target.matrix_world
    # Coordenadas mundiais dos vértices
    try:
        pts = [mw @ mesh.vertices[i].co for i in indices]
    except Exception:
        return

    # Constrói segmentos de linha fechados (P0->P1, P1->P2, ..., Pn->P0)
    line_coords = []
    n = len(pts)
    for i in range(n):
        line_coords.append(pts[i])
        line_coords.append(pts[(i + 1) % n])

    if not line_coords:
        return

    try:
        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Configura estado GPU com restauração
        prev_blend = gpu.state.blend_get() if hasattr(gpu.state, 'blend_get') else 'NONE'
        if hasattr(gpu.state, 'blend_set'):
            gpu.state.blend_set('ALPHA')
        if hasattr(gpu.state, 'line_width_set'):
            try:
                gpu.state.line_width_set(3.0)
            except Exception:
                pass
        if hasattr(gpu.state, 'depth_test_set'):
            try:
                gpu.state.depth_test_set('LESS_EQUAL')
            except Exception:
                pass

        shader.bind()
        # Cor ciano vibrante para destacar sobre superfícies cinzas ou coloridas
        color = (0.0, 0.85, 1.0, 1.0)
        shader.uniform_float("color", color)

        batch = batch_for_shader(shader, 'LINES', {"pos": line_coords})
        batch.draw(shader)

        # Restaura estado
        if hasattr(gpu.state, 'line_width_set'):
            try:
                gpu.state.line_width_set(1.0)
            except Exception:
                pass
        if hasattr(gpu.state, 'blend_set'):
            gpu.state.blend_set(prev_blend)
    except Exception:
        # Falhas de desenho GPU nunca devem interromper o Blender
        pass


def register_overlay():
    """Registra o draw handler na visualização 3D."""
    global _draw_handler
    if _draw_handler is None and hasattr(bpy.types, "SpaceView3D"):
        try:
            _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                _draw_loop_overlay_callback,
                (),
                'WINDOW',
                'POST_VIEW',
            )
        except Exception:
            _draw_handler = None


def unregister_overlay():
    """Remove o draw handler da visualização 3D."""
    global _draw_handler
    if _draw_handler is not None and hasattr(bpy.types, "SpaceView3D"):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        except Exception:
            pass
        _draw_handler = None
