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
from .constants import ROLE_PREVIEW_A, ROLE_PREVIEW_B

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

    from .geometry_loop import validate_capture
    is_valid, _reason = validate_capture(target, settings, context)
    if not is_valid:
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
            pts = [mw @ bm.verts[i].co for i in indices]
        else:
            mesh = target.data
            if not mesh or not mesh.vertices:
                return
            pts = [mw @ mesh.vertices[i].co for i in indices]
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


def _compute_cut_line_segments(mesh_or_bm, matrix_world: Matrix, plane_co: Vector, plane_no: Vector, is_bmesh: bool = False) -> List[Vector]:
    """Calcula segmentos de linha estritos da interseção entre o plano e cada triângulo/face da malha (C04 / C12 / V14).
    
    Garante que cada segmento pertença a uma única face, eliminando traços espúrios que cortam o vazio
    e detectando com precisão arestas coincidentes ou tangentes ao plano de corte.
    """
    segments = []
    norm = plane_no.normalized()

    if is_bmesh:
        bm = mesh_or_bm
        for f in bm.faces:
            if not f.is_valid or len(f.verts) < 3:
                continue
            v_coords = [matrix_world @ v.co for v in f.verts]
            n_v = len(v_coords)
            for i in range(1, n_v - 1):
                tri = (v_coords[0], v_coords[i], v_coords[i + 1])
                dists = [(p - plane_co).dot(norm) for p in tri]
                on_plane = [abs(d) <= 1e-6 for d in dists]
                num_on_plane = sum(on_plane)
                has_pos = any(d > 1e-6 for d in dists)
                has_neg = any(d < -1e-6 for d in dists)

                if not (has_pos and has_neg) and num_on_plane < 2:
                    continue

                inter_pts = []
                if num_on_plane == 2:
                    for v_idx in range(3):
                        if on_plane[v_idx]:
                            inter_pts.append(tri[v_idx])
                elif num_on_plane == 3:
                    continue
                else:
                    for e_idx in range(3):
                        p_a = tri[e_idx]
                        p_b = tri[(e_idx + 1) % 3]
                        d_a = dists[e_idx]
                        d_b = dists[(e_idx + 1) % 3]
                        if (d_a > 1e-6 and d_b < -1e-6) or (d_a < -1e-6 and d_b > 1e-6):
                            t = d_a / (d_a - d_b)
                            inter_pts.append(p_a + t * (p_b - p_a))
                        elif abs(d_a) <= 1e-6 and not any((p_a - ip).length_squared < 1e-10 for ip in inter_pts):
                            inter_pts.append(p_a)

                if len(inter_pts) == 2:
                    segments.append(inter_pts[0])
                    segments.append(inter_pts[1])
    else:
        mesh = mesh_or_bm
        if not mesh or not mesh.polygons or not mesh.vertices:
            return []
        mw = matrix_world
        verts_co = [mw @ v.co for v in mesh.vertices]
        for poly in mesh.polygons:
            p_verts = poly.vertices
            n_v = len(p_verts)
            if n_v < 3:
                continue
            v0_co = verts_co[p_verts[0]]
            d0 = (v0_co - plane_co).dot(norm)
            for i in range(1, n_v - 1):
                v1_co = verts_co[p_verts[i]]
                v2_co = verts_co[p_verts[i + 1]]
                d1 = (v1_co - plane_co).dot(norm)
                d2 = (v2_co - plane_co).dot(norm)

                dists = (d0, d1, d2)
                on_plane = (abs(d0) <= 1e-6, abs(d1) <= 1e-6, abs(d2) <= 1e-6)
                num_on_plane = sum(on_plane)
                has_pos = any(d > 1e-6 for d in dists)
                has_neg = any(d < -1e-6 for d in dists)

                if not (has_pos and has_neg) and num_on_plane < 2:
                    continue

                tri = (v0_co, v1_co, v2_co)
                inter_pts = []
                if num_on_plane == 2:
                    for v_idx in range(3):
                        if on_plane[v_idx]:
                            inter_pts.append(tri[v_idx])
                elif num_on_plane == 3:
                    continue
                else:
                    for e_idx in range(3):
                        p_a = tri[e_idx]
                        p_b = tri[(e_idx + 1) % 3]
                        d_a = dists[e_idx]
                        d_b = dists[(e_idx + 1) % 3]
                        if (d_a > 1e-6 and d_b < -1e-6) or (d_a < -1e-6 and d_b > 1e-6):
                            t = d_a / (d_a - d_b)
                            inter_pts.append(p_a + t * (p_b - p_a))
                        elif abs(d_a) <= 1e-6 and not any((p_a - ip).length_squared < 1e-10 for ip in inter_pts):
                            inter_pts.append(p_a)

                if len(inter_pts) == 2:
                    segments.append(inter_pts[0])
                    segments.append(inter_pts[1])

    return segments


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
    from .plane_state import resolve_plane_state
    origin, norm = resolve_plane_state(context.scene, settings)
    if norm.length < 1e-5:
        return

    # Origem lida do guia vivo (mesma fonte do corte); aplica deslocamento se houver
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
    cut_line_segments = []
    if show_cut_line:
        try:
            if target.mode == 'EDIT':
                import bmesh
                bm = bmesh.from_edit_mesh(target.data)
                cut_line_segments = _compute_cut_line_segments(bm, mw, origin, norm, is_bmesh=True)
            else:
                mesh = target.data
                cut_line_segments = _compute_cut_line_segments(mesh, mw, origin, norm, is_bmesh=False)
        except Exception:
            cut_line_segments = []

    is_exploded = (getattr(settings, "view_mode", "ASSEMBLED") == 'EXPLODED' and
                   getattr(settings, "session_status", "") in ('PREVIEW_VALID', 'PREVIEW_STALE'))

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

            # 1. Preenchimento translúcido do plano (apenas na vista montada para não flutuar no vazio - C04)
            if show_plane and not is_exploded:
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
            if show_cut_line and cut_line_segments:
                pairs = []
                if is_exploded:
                    # Na vista explodida, desenha o contorno projetado nas superfícies afastadas de A e B (C04 / P01)
                    from .operators import get_current_session_parts
                    parts = get_current_session_parts(context.scene)
                    obj_a = next((o for o in parts if o.get("chest_role") in (ROLE_PREVIEW_A, 'A', 'PART_A')), None)
                    obj_b = next((o for o in parts if o.get("chest_role") in (ROLE_PREVIEW_B, 'B', 'PART_B')), None)
                    offset_a = obj_a.location if obj_a else Vector((0, 0, 0))
                    offset_b = obj_b.location if obj_b else Vector((0, 0, 0))

                    if offset_a.length_squared > 1e-8 or offset_b.length_squared > 1e-8:
                        pairs.extend([p + offset_a for p in cut_line_segments])
                        pairs.extend([p + offset_b for p in cut_line_segments])
                    else:
                        pairs = cut_line_segments
                else:
                    pairs = cut_line_segments

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


def _draw_solid_overlay(context, settings):
    """Desenha as arestas reais do cortador sólido ativo em ciano na Viewport 3D (DEV-09)."""
    cutter = getattr(settings, "solid_cutter_object", None)
    if not cutter or cutter.name not in bpy.data.objects or cutter.type != 'MESH':
        return

    # Respeita visibilidade do cortador e modo
    if cutter.hide_viewport or cutter.hide_get():
        return

    # Não desenha se o corte já estiver confirmado
    if getattr(settings, "session_status", "") == 'COMMITTED':
        return

    mw = cutter.matrix_world
    pairs = []

    # Extrai arestas reais em World Space
    try:
        if cutter.mode == 'EDIT':
            import bmesh
            bm = bmesh.from_edit_mesh(cutter.data)
            for e in bm.edges:
                pairs.append(mw @ e.verts[0].co)
                pairs.append(mw @ e.verts[1].co)
        else:
            verts = cutter.data.vertices
            for e in cutter.data.edges:
                pairs.append(mw @ verts[e.vertices[0]].co)
                pairs.append(mw @ verts[e.vertices[1]].co)
    except Exception:
        return

    if not pairs:
        return

    # Eixo de penetração/orientação
    try:
        z_dir = (mw.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        cen = mw.translation
        arrow_len = max(0.02, cutter.dimensions.z * 0.4)
        arrow_tip = cen + z_dir * arrow_len
        pairs.append(cen)
        pairs.append(arrow_tip)
    except Exception:
        pass

    try:
        import gpu
        from gpu_extras.batch import batch_for_shader

        try:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        except Exception:
            shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

        prev_line_width = gpu.state.line_width_get() if hasattr(gpu.state, 'line_width_get') else None
        prev_depth_test = gpu.state.depth_test_get() if hasattr(gpu.state, 'depth_test_get') else None
        prev_blend = gpu.state.blend_get() if hasattr(gpu.state, 'blend_get') else None

        try:
            if hasattr(gpu.state, 'blend_set'):
                try:
                    gpu.state.blend_set('ALPHA')
                except Exception:
                    pass
            if hasattr(gpu.state, 'line_width_set'):
                try:
                    gpu.state.line_width_set(2.5)
                except Exception:
                    pass
            if hasattr(gpu.state, 'depth_test_set'):
                try:
                    gpu.state.depth_test_set('LESS_EQUAL')
                except Exception:
                    pass

            shader.bind()
            # Cor Ciano vibrante para destacar da seleção laranja do Blender (DEV-09)
            shader.uniform_float("color", (0.0, 0.9, 1.0, 0.85))
            batch = batch_for_shader(shader, 'LINES', {"pos": pairs})
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
            if hasattr(gpu.state, 'blend_set') and prev_blend is not None:
                try:
                    gpu.state.blend_set(prev_blend)
                except Exception:
                    pass
    except Exception:
        pass


def _generate_marker_lines(center, u_axis, v_axis, yaw_rad, radius, half_len, num_segments=16):
    """Gera pares de coordenadas 3D para desenhar o contorno do pino ou cápsula e sua cruz central."""
    u_c = (math.cos(yaw_rad) * u_axis + math.sin(yaw_rad) * v_axis).normalized()
    v_c = (-math.sin(yaw_rad) * u_axis + math.cos(yaw_rad) * v_axis).normalized()
    lines = []

    if half_len <= 1e-5:
        # Círculo
        pts = []
        for i in range(num_segments):
            angle = 2.0 * math.pi * i / num_segments
            pts.append(center + radius * (math.cos(angle) * u_c + math.sin(angle) * v_c))
        for i in range(num_segments):
            lines.append(pts[i])
            lines.append(pts[(i + 1) % num_segments])
    else:
        # Cápsula (estádio)
        c_left = center - half_len * u_c
        c_right = center + half_len * u_c
        # Lados retos
        lines.append(c_left + radius * v_c)
        lines.append(c_right + radius * v_c)
        lines.append(c_left - radius * v_c)
        lines.append(c_right - radius * v_c)
        # Semicírculo direito (-pi/2 a pi/2)
        half_segs = max(4, num_segments // 2)
        pts_r = []
        for i in range(half_segs + 1):
            angle = -math.pi / 2.0 + math.pi * i / half_segs
            pts_r.append(c_right + radius * (math.cos(angle) * u_c + math.sin(angle) * v_c))
        for i in range(len(pts_r) - 1):
            lines.append(pts_r[i])
            lines.append(pts_r[i + 1])
        # Semicírculo esquerdo (pi/2 a 3pi/2)
        pts_l = []
        for i in range(half_segs + 1):
            angle = math.pi / 2.0 + math.pi * i / half_segs
            pts_l.append(c_left + radius * (math.cos(angle) * u_c + math.sin(angle) * v_c))
        for i in range(len(pts_l) - 1):
            lines.append(pts_l[i])
            lines.append(pts_l[i + 1])

    # Cruz central
    cross_sz = radius * 0.75
    lines.append(center - cross_sz * u_c)
    lines.append(center + cross_sz * u_c)
    lines.append(center - cross_sz * v_c)
    lines.append(center + cross_sz * v_c)
    return lines


# Cache de batch e geometria da grade de posicionamento de 5 mm (Seção 5)
_GRID_CACHE = {
    "key": None,
    "batch": None,
    "points": None,
}


def clear_grid_cache():
    """Limpa o cache GPU da grade de posicionamento."""
    global _GRID_CACHE
    _GRID_CACHE["key"] = None
    _GRID_CACHE["batch"] = None
    _GRID_CACHE["points"] = None


def _get_or_create_grid_batch(shader, prep, disp_offset, target_name):
    """Retorna o batch GPU dos pontos da grade 5 mm em cache ou constrói um novo."""
    global _GRID_CACHE
    key = (prep.cut_signature, tuple(disp_offset), round(prep.unit_scale, 4), target_name)
    if _GRID_CACHE["key"] == key and _GRID_CACHE["batch"] is not None:
        return _GRID_CACHE["batch"]

    from .connector_surface import generate_positioning_grid_points
    grid_pts = generate_positioning_grid_points(prep)
    if not grid_pts:
        _GRID_CACHE["key"] = key
        _GRID_CACHE["batch"] = None
        _GRID_CACHE["points"] = None
        return None

    # Aplica deslocamento explodido preservando coordenadas físicas
    pts_3d = [item[2] + disp_offset for item in grid_pts]

    try:
        from gpu_extras.batch import batch_for_shader
        batch = batch_for_shader(shader, 'POINTS', {"pos": pts_3d})
        _GRID_CACHE["key"] = key
        _GRID_CACHE["batch"] = batch
        _GRID_CACHE["points"] = pts_3d
        return batch
    except Exception:
        return None


def _draw_connector_markers_overlay(context, settings):
    """Desenha os marcadores visuais de conectores na interface de corte (A05)."""
    if not getattr(settings, "connector_enabled", False):
        return

    mode = getattr(settings, "split_mode", "PLANE")
    if mode not in ('PLANE', 'LOOP', 'MATERIAL'):
        return

    if getattr(settings, "session_status", "") == 'COMMITTED':
        return

    target = getattr(settings, "target_object", None)
    if not target or target.name not in bpy.data.objects:
        return

    from .diagnostic import get_scene_scale_to_mm
    from .connector_surface import get_cached_prepared_split, get_explosion_display_offset
    from .connector_editor import get_editor_interaction_state

    prep = get_cached_prepared_split()
    unit_scale = get_scene_scale_to_mm(context.scene)
    if unit_scale <= 0.0:
        unit_scale = 1000.0

    disp_offset = Vector((0.0, 0.0, 0.0))
    if prep is not None:
        origin = prep.surface_origin
        normal = prep.surface_normal
        u_axis = prep.axis_u
        v_axis = prep.axis_v
        disp_offset = get_explosion_display_offset(settings, prep)
    else:
        from .plane_state import resolve_plane_state
        if mode == 'PLANE':
            origin, normal = resolve_plane_state(context.scene, settings)
        else:
            origin = Vector(getattr(settings, "loop_interface_origin", (0, 0, 0)))
            normal = Vector(getattr(settings, "loop_interface_normal", (0, 0, 1)))

        if normal.length < 1e-6:
            return
        normal = normal.normalized()
        u_axis, v_axis = _get_orthonormal_basis(normal)

    diam_mm = getattr(settings, "connector_diameter_mm", 4.0)
    radius_bu = (diam_mm / 2.0) / unit_scale
    clearance_bu = (getattr(settings, "clearance_per_side_mm", 0.15)) / unit_scale
    conn_type = getattr(settings, "connector_type", "CYLINDER")
    half_len_bu = 0.0
    if conn_type == 'CAPSULE':
        cap_mm = getattr(settings, "connector_capsule_length_mm", 6.0)
        half_len_bu = max(0.0, (cap_mm - diam_mm) / 2.0) / unit_scale

    dist = getattr(settings, "connector_distribution", "CENTER")
    markers = []  # list of tuples: (center_pos, yaw_rad, is_valid, is_sel)

    if dist == 'MANUAL':
        active_idx = getattr(settings, "manual_connector_index", 0)
        for i, item in enumerate(settings.manual_connectors):
            if prep is not None:
                pos = prep.uv_mm_to_world(item.u_mm, item.v_mm) + disp_offset
            else:
                pos = origin + (item.u_mm / unit_scale) * u_axis + (item.v_mm / unit_scale) * v_axis
            yaw_rad = math.radians(getattr(item, "yaw_deg", 0.0))
            is_valid = getattr(item, "is_valid", True)
            is_sel = (i == active_idx)
            markers.append((pos, yaw_rad, is_valid, is_sel))
    else:
        try:
            from .geometry_connectors import compute_connector_layout
            layout = compute_connector_layout(
                target_mesh=target.data,
                matrix_world=target.matrix_world,
                plane_origin=origin,
                plane_normal=normal,
                distribution=dist,
                edge_margin_mm=settings.connector_edge_margin_mm,
                unit_scale=unit_scale,
                diameter_mm=settings.connector_diameter_mm,
                clearance_per_side_mm=settings.clearance_per_side_mm,
                interface=prep.interface if prep else None,
                connector_type=conn_type,
                capsule_length_mm=settings.connector_capsule_length_mm,
                adjust_to_valid_area=getattr(settings, "adjust_to_valid_area", False),
            )
            is_valid = layout.get("valid", True)
            for pos in layout.get("positions", []):
                markers.append((pos + disp_offset, 0.0, is_valid, False))
        except Exception:
            pass

    editor_state = get_editor_interaction_state()
    has_ghost = editor_state.get("is_active") and (editor_state.get("hover_world") is not None)
    is_manual_editing = (
        editor_state.get("is_active", False)
        and getattr(settings, "is_editing_connectors", False)
        and dist == 'MANUAL'
    )

    if not markers and not has_ghost and not is_manual_editing:
        return

    # Categoriza linhas por estilo/cor:
    lines_valid = []
    lines_valid_clearance = []
    lines_invalid = []
    lines_selected = []
    lines_ghost = []

    for pos, yaw_rad, is_valid, is_sel in markers:
        pin_lines = _generate_marker_lines(pos, u_axis, v_axis, yaw_rad, radius_bu, half_len_bu)
        socket_lines = _generate_marker_lines(pos, u_axis, v_axis, yaw_rad, radius_bu + clearance_bu, half_len_bu)

        if is_valid:
            lines_valid.extend(pin_lines)
            lines_valid_clearance.extend(socket_lines)
        else:
            lines_invalid.extend(pin_lines)
            lines_invalid.extend(socket_lines)

        if is_sel:
            # Destaque de seleção em anel externo laranja, preservando cor de validade do pino (T20)
            sel_ring = _generate_marker_lines(pos, u_axis, v_axis, yaw_rad, radius_bu + clearance_bu * 1.6, half_len_bu)
            lines_selected.extend(sel_ring)

    if has_ghost:
        ghost_pos = editor_state["hover_world"]
        ghost_pin = _generate_marker_lines(ghost_pos, u_axis, v_axis, 0.0, radius_bu, half_len_bu)
        lines_ghost.extend(ghost_pin)

    try:
        import gpu
        from gpu_extras.batch import batch_for_shader

        try:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        except Exception:
            shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

        prev_line_width = gpu.state.line_width_get() if hasattr(gpu.state, 'line_width_get') else None
        prev_depth_test = gpu.state.depth_test_get() if hasattr(gpu.state, 'depth_test_get') else None
        prev_blend = gpu.state.blend_get() if hasattr(gpu.state, 'blend_get') else None

        try:
            if hasattr(gpu.state, 'blend_set'):
                try:
                    gpu.state.blend_set('ALPHA')
                except Exception:
                    pass
            if hasattr(gpu.state, 'depth_test_set'):
                try:
                    gpu.state.depth_test_set('ALWAYS')
                except Exception:
                    pass

            # 0. Grade de pontos 5 mm (visível exclusivamente durante a sessão manual ativa - Seção 1, 4 e 5)
            # Pinos e marcadores são desenhados DEPOIS para manter prioridade visual sobre os pontos
            if is_manual_editing and prep is not None and getattr(prep, "is_planar", True):
                grid_batch = _get_or_create_grid_batch(shader, prep, disp_offset, target.name)
                if grid_batch is not None:
                    ui_scale = 1.0
                    if context and hasattr(context, "preferences") and hasattr(context.preferences, "system"):
                        ui_scale = getattr(context.preferences.system, "ui_scale", 1.0)
                    pt_size = max(2.5, min(6.0, 3.2 * ui_scale))

                    if hasattr(gpu.state, 'point_size_set'):
                        try:
                            gpu.state.point_size_set(pt_size)
                        except Exception:
                            pass
                    if hasattr(gpu.state, 'depth_test_set'):
                        try:
                            gpu.state.depth_test_set('ALWAYS')
                        except Exception:
                            pass

                    shader.bind()
                    # Cor neutra com contraste discreto sobre cinza e verde: cinza claro suave
                    shader.uniform_float("color", (0.85, 0.88, 0.92, 0.80))
                    grid_batch.draw(shader)

                    if hasattr(gpu.state, 'point_size_set'):
                        try:
                            gpu.state.point_size_set(1.0)
                        except Exception:
                            pass
                    if hasattr(gpu.state, 'depth_test_set'):
                        try:
                            gpu.state.depth_test_set('ALWAYS')
                        except Exception:
                            pass

            # 1. Pinos Válidos (Verde vivo)
            if lines_valid:
                if hasattr(gpu.state, 'line_width_set'):
                    try:
                        gpu.state.line_width_set(2.5)
                    except Exception:
                        pass
                shader.bind()
                shader.uniform_float("color", (0.1, 0.95, 0.25, 0.95))
                batch = batch_for_shader(shader, 'LINES', {"pos": lines_valid})
                batch.draw(shader)

            # 2. Folgas / Cavidades (Verde translúcido)
            if lines_valid_clearance:
                if hasattr(gpu.state, 'line_width_set'):
                    try:
                        gpu.state.line_width_set(1.5)
                    except Exception:
                        pass
                shader.bind()
                shader.uniform_float("color", (0.1, 0.95, 0.25, 0.45))
                batch = batch_for_shader(shader, 'LINES', {"pos": lines_valid_clearance})
                batch.draw(shader)

            # 3. Pinos Inválidos (Vermelho vibrante)
            if lines_invalid:
                if hasattr(gpu.state, 'line_width_set'):
                    try:
                        gpu.state.line_width_set(2.5)
                    except Exception:
                        pass
                shader.bind()
                shader.uniform_float("color", (0.95, 0.15, 0.15, 0.95))
                batch = batch_for_shader(shader, 'LINES', {"pos": lines_invalid})
                batch.draw(shader)

            # 4. Pino Selecionado / Ativo (Anel Laranja de destaque)
            if lines_selected:
                if hasattr(gpu.state, 'line_width_set'):
                    try:
                        gpu.state.line_width_set(3.5)
                    except Exception:
                        pass
                shader.bind()
                shader.uniform_float("color", (1.0, 0.55, 0.05, 1.0))
                batch = batch_for_shader(shader, 'LINES', {"pos": lines_selected})
                batch.draw(shader)

            # 5. Pino Fantasma do Cursor (Azul ciano translúcido)
            if lines_ghost:
                if hasattr(gpu.state, 'line_width_set'):
                    try:
                        gpu.state.line_width_set(2.0)
                    except Exception:
                        pass
                shader.bind()
                shader.uniform_float("color", (0.2, 0.8, 1.0, 0.85))
                batch = batch_for_shader(shader, 'LINES', {"pos": lines_ghost})
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
            if hasattr(gpu.state, 'blend_set') and prev_blend is not None:
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

    # B01 / F01 / F02 / DEV-09: Isolamento estrito por modo
    if mode == 'LOOP':
        _draw_loop_overlay(context, settings)
    elif mode == 'PLANE':
        _draw_plane_overlay(context, settings)
    elif mode == 'SOLID':
        _draw_solid_overlay(context, settings)

    # Conectores overlay (A05)
    _draw_connector_markers_overlay(context, settings)


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
    clear_grid_cache()
    if _draw_handler is not None and hasattr(bpy.types, "SpaceView3D"):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        except Exception:
            pass
        _draw_handler = None
