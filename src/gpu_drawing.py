"""Módulo de desenho GPU para sobreposição do contorno capturado (Loop) e guia do plano no Viewport.

Implementa F01 e F02 com integridade estrita de estado GPU:
- Salva e restaura blend, depth test e largura de linha dentro de bloco finally (B09).
- Visibilidade restrita ao modo ativo (B01): Loop só desenha em LOOP; Plano só desenha em PLANE.
- Coordenadas vivas em Edit Mode (T05).
- Prévia de corte translúcida e contorno de interseção para o modo Plano (F02).
"""

import bpy
from typing import Optional, List, Tuple
from mathutils import Vector, Matrix
import math

_draw_handler = None


def _get_orthonormal_basis(normal: Vector) -> Tuple[Vector, Vector]:
    """Retorna dois vetores unitários ortogonais à normal fornecida."""
    n = normal.normalized()
    if abs(n.z) < 0.9:
        u = n.cross(Vector((0.0, 0.0, 1.0))).normalized()
    else:
        u = n.cross(Vector((0.0, 1.0, 0.0))).normalized()
    v = n.cross(u).normalized()
    return u, v


def _draw_loop_overlay(context, settings):
    """Desenha a sobreposição ciano destacada do loop capturado na Viewport 3D."""
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

    mw = target.matrix_world

    # Coordenadas mundiais com suporte a BMesh vivo em Edit Mode (T05)
    pts = []
    try:
        if target.mode == 'EDIT':
            import bmesh
            bm = bmesh.from_edit_mesh(target.data)
            bm.verts.ensure_lookup_table()
            v_len = len(bm.verts)
            pts = [mw @ bm.verts[i].co for i in indices if 0 <= i < v_len]
        else:
            mesh = target.data
            if not mesh or not mesh.vertices:
                return
            v_len = len(mesh.vertices)
            pts = [mw @ mesh.vertices[i].co for i in indices if 0 <= i < v_len]
    except Exception:
        return

    if len(pts) < 2:
        return

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

        prev_blend = gpu.state.blend_get() if hasattr(gpu.state, 'blend_get') else 'NONE'
        prev_depth_test = gpu.state.depth_test_get() if hasattr(gpu.state, 'depth_test_get') else None
        prev_line_width = gpu.state.line_width_get() if hasattr(gpu.state, 'line_width_get') else None

        try:
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
            # Ciano vibrante
            shader.uniform_float("color", (0.0, 0.85, 1.0, 1.0))
            batch = batch_for_shader(shader, 'LINES', {"pos": line_coords})
            batch.draw(shader)
        finally:
            if hasattr(gpu.state, 'line_width_set') and prev_line_width is not None:
                try:
                    gpu.state.line_width_set(prev_line_width)
                except Exception:
                    pass
            if hasattr(gpu.state, 'depth_test_set') and prev_depth_test is not None:
                try:
                    gpu.state.depth_test_set(prev_depth_test)
                except Exception:
                    pass
            if hasattr(gpu.state, 'blend_set'):
                try:
                    gpu.state.blend_set(prev_blend)
                except Exception:
                    pass
    except Exception:
        pass


def _draw_plane_overlay(context, settings):
    """Desenha o retângulo translúcido e a linha de corte do plano na Viewport 3D (F02)."""
    show_plane = getattr(settings, "show_plane_preview", True)
    show_cut_line = getattr(settings, "show_plane_cut_line", True)

    if not show_plane and not show_cut_line:
        return

    target = getattr(settings, "target_object", None)
    if not target or target.name not in bpy.data.objects or target.type != 'MESH':
        return

    # Normal e Origem em World Space
    norm = Vector(getattr(settings, "plane_normal", (0.0, 0.0, 1.0))).normalized()
    if norm.length < 1e-5:
        return

    # Lê origem atual do corte considerando deslocamento se houver
    origin = Vector(getattr(settings, "plane_origin", (0.0, 0.0, 0.0)))
    offset_mm = getattr(settings, "plane_offset_mm", 0.0)
    if abs(offset_mm) > 1e-6:
        from .diagnostic import get_scene_scale_to_mm
        scale_to_mm = get_scene_scale_to_mm(context.scene)
        origin = origin + (offset_mm / scale_to_mm) * norm

    mw = target.matrix_world
    # Centro e raio envolvente do alvo em World Space
    try:
        corners = [mw @ Vector(corner) for corner in target.bound_box]
        bbox_center = sum(corners, Vector()) / len(corners)
        max_dist = max((c - bbox_center).length for c in corners)
        plane_size = max(0.05, max_dist * 1.3)
    except Exception:
        plane_size = 1.0
        bbox_center = origin

    # Projeta o centro da bounding box no plano para ancorar o retângulo visual
    proj_center = bbox_center - ((bbox_center - origin).dot(norm)) * norm
    u_vec, v_vec = _get_orthonormal_basis(norm)

    # 4 vértices do retângulo do plano
    p0 = proj_center - u_vec * plane_size - v_vec * plane_size
    p1 = proj_center + u_vec * plane_size - v_vec * plane_size
    p2 = proj_center + u_vec * plane_size + v_vec * plane_size
    p3 = proj_center - u_vec * plane_size + v_vec * plane_size

    quad_tris = [p0, p1, p2, p0, p2, p3]
    quad_border = [p0, p1, p1, p2, p2, p3, p3, p0]

    # Calcula linha de interseção (corte) se ativada
    cut_line_coords = []
    if show_cut_line:
        try:
            # Calcula interseção com as arestas da malha no espaço de mundo
            if target.mode == 'EDIT':
                import bmesh
                bm = bmesh.from_edit_mesh(target.data)
                edges = list(bm.edges)
                for e in edges:
                    co1 = mw @ e.verts[0].co
                    co2 = mw @ e.verts[1].co
                    d1 = (co1 - origin).dot(norm)
                    d2 = (co2 - origin).dot(norm)
                    if (d1 > 1e-6 and d2 < -1e-6) or (d1 < -1e-6 and d2 > 1e-6):
                        t = d1 / (d1 - d2)
                        p_int = co1 + t * (co2 - co1)
                        cut_line_coords.append(p_int)
            else:
                mesh = target.data
                if mesh and mesh.edges:
                    for e in mesh.edges:
                        co1 = mw @ mesh.vertices[e.vertices[0]].co
                        co2 = mw @ mesh.vertices[e.vertices[1]].co
                        d1 = (co1 - origin).dot(norm)
                        d2 = (co2 - origin).dot(norm)
                        if (d1 > 1e-6 and d2 < -1e-6) or (d1 < -1e-6 and d2 > 1e-6):
                            t = d1 / (d1 - d2)
                            p_int = co1 + t * (co2 - co1)
                            cut_line_coords.append(p_int)
        except Exception:
            cut_line_coords = []

    try:
        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        prev_blend = gpu.state.blend_get() if hasattr(gpu.state, 'blend_get') else 'NONE'
        prev_depth_test = gpu.state.depth_test_get() if hasattr(gpu.state, 'depth_test_get') else None
        prev_line_width = gpu.state.line_width_get() if hasattr(gpu.state, 'line_width_get') else None

        try:
            if hasattr(gpu.state, 'blend_set'):
                gpu.state.blend_set('ALPHA')

            # 1. Preenchimento translúcido do plano (Laranja suave com opacidade ajustável)
            if show_plane:
                opacity = max(0.0, min(1.0, getattr(settings, "plane_preview_opacity", 15.0) / 100.0))
                if opacity > 0.01:
                    if hasattr(gpu.state, 'depth_test_set'):
                        try:
                            gpu.state.depth_test_set('LESS_EQUAL')
                        except Exception:
                            pass

                    shader.bind()
                    shader.uniform_float("color", (1.0, 0.55, 0.1, opacity))
                    batch_plane = batch_for_shader(shader, 'TRIS', {"pos": quad_tris})
                    batch_plane.draw(shader)

                # Borda do retângulo
                if hasattr(gpu.state, 'line_width_set'):
                    try:
                        gpu.state.line_width_set(1.5)
                    except Exception:
                        pass
                shader.bind()
                shader.uniform_float("color", (1.0, 0.6, 0.15, min(1.0, opacity * 2.5 + 0.3)))
                batch_border = batch_for_shader(shader, 'LINES', {"pos": quad_border})
                batch_border.draw(shader)

            # 2. Linha de corte na geometria (Laranja contrastante / Amarelo ouro de alta visibilidade)
            if show_cut_line and len(cut_line_coords) >= 2:
                # Agrupa em pares de pontos para linhas
                pairs = []
                for i in range(0, len(cut_line_coords) - 1, 2):
                    pairs.append(cut_line_coords[i])
                    pairs.append(cut_line_coords[i + 1])

                if pairs:
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
                    shader.uniform_float("color", (1.0, 0.45, 0.0, 1.0))
                    batch_cut = batch_for_shader(shader, 'LINES', {"pos": pairs})
                    batch_cut.draw(shader)

        finally:
            if hasattr(gpu.state, 'line_width_set') and prev_line_width is not None:
                try:
                    gpu.state.line_width_set(prev_line_width)
                except Exception:
                    pass
            if hasattr(gpu.state, 'depth_test_set') and prev_depth_test is not None:
                try:
                    gpu.state.depth_test_set(prev_depth_test)
                except Exception:
                    pass
            if hasattr(gpu.state, 'blend_set'):
                try:
                    gpu.state.blend_set(prev_blend)
                except Exception:
                    pass
    except Exception:
        pass


def _draw_overlay_callback():
    """Callback mestre executado no espaço 3D (SpaceView3D)."""
    context = bpy.context
    if not context or not hasattr(context, "scene") or not hasattr(context.scene, "chest_splitter"):
        return

    settings = context.scene.chest_splitter
    mode = getattr(settings, "split_mode", "PLANE")

    # B01 / F01 / F02: Isolamento estrito por modo
    if mode == 'LOOP':
        _draw_loop_overlay(context, settings)
    elif mode == 'PLANE':
        _draw_plane_overlay(context, settings)


def register_overlay():
    """Registra o draw handler na visualização 3D."""
    global _draw_handler
    if _draw_handler is None and hasattr(bpy.types, "SpaceView3D"):
        try:
            _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                _draw_overlay_callback,
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
