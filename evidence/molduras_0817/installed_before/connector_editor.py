"""Editor interativo contínuo de pinos manuais no Viewport 3D (Etapas C e D).

Implementa:
- Ferramenta modal contínua com submodos Adicionar ('ADD') e Mover ('MOVE').
- Raycast preciso na janela WINDOW da área VIEW_3D sobre a superfície útil.
- Círculo/cápsula fantasma com feedback em tempo real de validade.
- Arraste contínuo, rotação individual de cápsula ('R'), remoção ('X'/DEL), duplicação.
- Esc cancela apenas o movimento em curso; segundo Esc cancela rascunho inteiro.
- Visualização direta e alinhamento de câmera à face de corte ('Ver Face de Encaixe').
- Nenhuma operação booleana durante a manipulação do mouse (zero lag).
"""

import math
import uuid
from typing import Optional, List, Dict, Any, Tuple

import bpy
from mathutils import Vector, Matrix, Euler
from bpy_extras import view3d_utils

from .connector_surface import (
    PreparedSplit,
    prepare_split_candidates,
    get_cached_prepared_split,
    raycast_connector_surface,
    evaluate_connector_specs,
    get_explosion_display_offset,
)
from .diagnostic import get_scene_scale_to_mm
from .translations import localize_text, report_msg


# Estado volátil de interação do editor para o drawing overlay
_EDITOR_STATE = {
    "generation": 0,
    "is_active": False,
    "hover_world": None,
    "hover_u_mm": 0.0,
    "hover_v_mm": 0.0,
    "hover_valid": True,
    "hover_reason": "OK",
    "is_dragging": False,
    "drag_idx": -1,
    "drag_start_u": 0.0,
    "drag_start_v": 0.0,
}


def get_editor_interaction_state() -> Dict[str, Any]:
    """Retorna o estado interativo volátil para desenho de overlay."""
    return _EDITOR_STATE


def stop_connector_editor(scene: Optional[bpy.types.Scene] = None):
    """Encerra com segurança o estado de edição interativa de conectores em qualquer cenário."""
    if scene is not None:
        settings = getattr(scene, "chest_splitter", None)
        if settings is not None:
            settings.is_editing_connectors = False
    _EDITOR_STATE["generation"] += 1
    _EDITOR_STATE["is_active"] = False
    _EDITOR_STATE["is_dragging"] = False
    _EDITOR_STATE["drag_idx"] = -1
    _EDITOR_STATE["hover_world"] = None
    try:
        from .gpu_drawing import clear_grid_cache
        clear_grid_cache()
    except Exception:
        pass
    try:
        wm = getattr(bpy.context, "window_manager", None)
        if wm:
            for window in wm.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
    except Exception:
        pass


def get_view3d_canvas_region(area: Optional[bpy.types.Area], mouse_x: int, mouse_y: int) -> Optional[bpy.types.Region]:
    """Retorna a região WINDOW da 3D Viewport apenas se o mouse estiver sobre o canvas 3D.
    
    Retorna None se o mouse estiver sobre a barra lateral (N-Panel UI), barra de ferramentas (TOOLS),
    cabeçalhos (HEADER / TOOL_HEADER) ou fora da área 3D. Isso garante que cliques em botões
    da extensão nunca sejam interceptados como comandos ou cliques no espaço 3D.
    """
    if not area or area.type != 'VIEW_3D':
        return None

    # Verifica se o cursor está dentro dos limites da área VIEW_3D
    if not (area.x <= mouse_x < area.x + area.width and area.y <= mouse_y < area.y + area.height):
        return None

    # Se estiver sobre qualquer região secundária (UI, TOOLS, HEADER, etc.), não é o canvas 3D
    for r in area.regions:
        if r.type != 'WINDOW':
            if (r.x <= mouse_x < r.x + r.width and r.y <= mouse_y < r.y + r.height):
                return None

    # Encontra a região WINDOW
    for r in area.regions:
        if r.type == 'WINDOW':
            return r

    return None


class CHEST_OT_splitter_edit_manual_connectors(bpy.types.Operator):
    """Abre o editor visual contínuo de pinos sobre a superfície real de corte (A05 / PM03)"""
    bl_idname = "chest.splitter_edit_manual_connectors"
    bl_label = "Editar Posições dos Pinos"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _region = None
    _area = None
    _prepared: Optional[PreparedSplit] = None
    _snapshot: List[Dict[str, float]] = []
    _last_snapshot: Optional[List[Dict[str, float]]] = None
    _rotating = False
    _rotate_start_mouse_x = 0
    _rotate_start_yaw = 0.0

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "chest_splitter", None)
        if not settings or not settings.target_object:
            return False
        return settings.split_mode in ('PLANE', 'LOOP', 'MATERIAL', 'SOLID')

    def _prepare_target_and_cleanup_previews(self, context):
        settings = context.scene.chest_splitter
        # Remove only this session, never whichever older operation is selected.
        if settings.session_id and settings.session_status != 'COMMITTED':
            from .lifecycle import remove_preview
            ok, reason = remove_preview(context, op_id=settings.session_id)
            if not ok:
                raise RuntimeError(reason)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Garante que o objeto alvo está visível e ativo no viewport
        target = settings.target_object
        if target and target.name in bpy.data.objects:
            target.hide_viewport = False
            try:
                target.hide_set(False)
                if context.view_layer:
                    context.view_layer.objects.active = target
                    target.select_set(True)
            except Exception:
                pass

    def _capture_snapshot(self, settings):
        self._snapshot = [
            {"connector_id": c.connector_id, "u_mm": c.u_mm,
             "v_mm": c.v_mm, "yaw_deg": c.yaw_deg}
            for c in settings.manual_connectors
        ]
        type(self)._last_snapshot = list(self._snapshot)

    def execute(self, context):
        # Script/headless entry point uses the same preparation and rollback rules.
        settings = context.scene.chest_splitter
        try:
            self._prepared = prepare_split_candidates(context, force_recompute=True)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._capture_snapshot(settings)
        self._prepare_target_and_cleanup_previews(context)
        from .connector_surface import set_cached_prepared_split
        set_cached_prepared_split(self._prepared)
        settings.connector_distribution = 'MANUAL'
        settings.connector_enabled = True
        settings.is_editing_connectors = True
        evaluate_connector_specs(self._prepared, settings)
        return {'FINISHED'}

    def invoke(self, context, event):
        settings = context.scene.chest_splitter
        target = settings.target_object
        if not target:
            self.report({'WARNING'}, localize_text("Defina um objeto alvo antes de editar pinos."))
            return {'CANCELLED'}

        if settings.is_editing_connectors:
            self.report({'WARNING'}, localize_text("O editor de pinos já está aberto."))
            return {'CANCELLED'}
        try:
            self._prepared = prepare_split_candidates(context, force_recompute=True)
        except Exception as exc:
            self.report({'ERROR'}, report_msg(f"Falha ao preparar superfície de encaixe: {exc}", f"Failed to prepare mating surface: {exc}"))
            return {'CANCELLED'}
        self._prepare_target_and_cleanup_previews(context)
        from .connector_surface import set_cached_prepared_split
        set_cached_prepared_split(self._prepared)

        # Se estiver em modo de edição, muda para modo Objeto para permitir seleção e cliques
        if context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass

        # Localiza área VIEW_3D e região WINDOW corretas (PM05)
        area_3d = None
        region_win = None
        if context.area and context.area.type == 'VIEW_3D':
            area_3d = context.area
        else:
            for a in context.screen.areas:
                if a.type == 'VIEW_3D':
                    area_3d = a
                    break

        if not area_3d:
            self.report({'ERROR'}, localize_text("Nenhuma área 3D Viewport encontrada."))
            return {'CANCELLED'}

        for r in area_3d.regions:
            if r.type == 'WINDOW':
                region_win = r
                break

        if not region_win:
            self.report({'ERROR'}, localize_text("Região WINDOW do Viewport não encontrada."))
            return {'CANCELLED'}

        self._area = area_3d
        self._region = region_win

        # Ativa modo Manual e Encaixes
        settings.connector_distribution = 'MANUAL'
        settings.connector_enabled = True
        settings.is_editing_connectors = True
        self._target = target
        from .input_state import editor_configuration
        self._configuration = editor_configuration(settings, context.scene)

        self._capture_snapshot(settings)
        self._binding = settings.manual_binding

        # Avalia estado inicial
        evaluate_connector_specs(self._prepared, settings)

        _EDITOR_STATE["is_active"] = True
        self._generation = _EDITOR_STATE["generation"]
        _EDITOR_STATE["is_dragging"] = False
        _EDITOR_STATE["drag_idx"] = -1
        _EDITOR_STATE["hover_world"] = None

        # Alinha automaticamente a visão da Viewport 3D à superfície de corte
        align_viewport_to_cut_surface(self._area, self._prepared, settings, target)

        context.window_manager.modal_handler_add(self)
        self.report(
            {'INFO'},
            localize_text("Editor de Pinos: Clique para adicionar/mover | G: mover | R: girar | V: alinhar vista | X/Del: remover pino | Shift+X: limpar todos | Enter: confirmar | Esc: sair.")
        )
        self._area.tag_redraw()
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        self._cancel_and_restore(context)

    def modal(self, context, event):
        try:
            return self._modal_impl(context, event)
        except Exception as e:
            print(f"[Chest Splitter] Erro no modal do editor de pinos: {e}")
            import traceback
            traceback.print_exc()
            return self._finish_cleanup(context, 'CANCELLED')

    def _modal_impl(self, context, event):
        # A button can finish and reopen editing before the old modal gets its
        # next event. Retire that old instance without stopping the new editor.
        if hasattr(self, '_generation') and self._generation != _EDITOR_STATE['generation']:
            if self._timer is not None:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
            return {'FINISHED', 'PASS_THROUGH'}
        if not hasattr(context.scene, 'chest_splitter'):
            return {'CANCELLED'}
        settings = context.scene.chest_splitter

        # Encerra imediatamente se:
        # 1. Edição foi desativada explicitamente
        # 2. Sessão foi confirmada ou finalizada (COMMITTED)
        # 3. Não está em Object Mode (ex: usuário entrou em Edit Mode ou Sculpt Mode)
        # 4. O objeto alvo foi ocultado, excluído ou trocado
        # 5. O preparador de corte não existe
        # 6. Conectores manuais foram desativados
        should_exit = (
            not getattr(settings, "is_editing_connectors", False)
            or (self._prepared and settings.split_mode != self._prepared.split_mode)
            or not self._prepared
            or getattr(settings, "session_status", "") == 'COMMITTED'
            or context.mode != 'OBJECT'
            or getattr(self, "_target", None) is None
            or self._target.name not in bpy.data.objects
            or getattr(settings, "target_object", None) != self._target
            or self._target.hide_viewport
            or self._target.hide_get()
            or not getattr(settings, "connector_enabled", False)
            or getattr(settings, "connector_distribution", "") != 'MANUAL'
        )
        if should_exit:
            res_state = 'FINISHED' if getattr(settings, "session_status", "") == 'COMMITTED' else 'CANCELLED'
            return self._finish_cleanup(context, res_state, pass_through=True)

        from .input_state import editor_configuration
        if (editor_configuration(settings, context.scene) != self._configuration
                or get_cached_prepared_split() is None):
            try:
                self._prepared = prepare_split_candidates(context, force_recompute=True)
                self._configuration = editor_configuration(settings, context.scene)
                if getattr(self, '_binding', settings.manual_binding) != settings.manual_binding:
                    self._capture_snapshot(settings)
                    self._binding = settings.manual_binding
                _EDITOR_STATE["hover_world"] = None
                _EDITOR_STATE["is_dragging"] = False
                evaluate_connector_specs(self._prepared, settings)
            except Exception as exc:
                self.report({'WARNING'}, str(exc))
                return self._finish_cleanup(context, 'FINISHED')

        # Redesenha a área do viewport para feedback responsivo
        if self._area:
            self._area.tag_redraw()

        # Verifica se o cursor está estritamente sobre o canvas 3D (excluindo painel N, barra de ferramentas e headers)
        canvas_region = get_view3d_canvas_region(self._area, event.mouse_x, event.mouse_y)
        in_canvas = (canvas_region is not None)

        # Mouse release belongs to the drag even outside the WINDOW region.
        if (_EDITOR_STATE['is_dragging'] and event.type == 'LEFTMOUSE'
                and event.value == 'RELEASE'):
            _EDITOR_STATE['is_dragging'] = False
            _EDITOR_STATE['drag_idx'] = -1
            evaluate_connector_specs(self._prepared, settings)
            return {'RUNNING_MODAL'}
        if event.alt and event.type in {'LEFTMOUSE', 'MIDDLEMOUSE'}:
            return {'PASS_THROUGH'}

        # Se o cursor estiver sobre o painel N (UI), cabeçalho ou outra área do Blender:
        if not in_canvas:
            _EDITOR_STATE["hover_world"] = None
            # Permite que todos os cliques de mouse, arrastes e scrolls passem direto para os botões do Blender
            if event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MOUSEMOVE'}:
                return {'PASS_THROUGH'}
            # Se for tecla ESC fora do canvas, permite cancelar a edição
            if event.type == 'ESC' and event.value == 'PRESS':
                return self._cancel_and_restore(context)
            # Permite digitação normal em campos de texto/número na interface
            return {'PASS_THROUGH'}

        # 1. Permite navegação padrão do Blender (MMB, Scroll, Numpad) sem interferência (T11)
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'NUMPAD_1', 'NUMPAD_3', 'NUMPAD_7'}:
            return {'PASS_THROUGH'}

        # 2. Converte coordenadas do mouse para raio 3D na região canvas WINDOW (PM05)
        coord_2d = (event.mouse_x - canvas_region.x, event.mouse_y - canvas_region.y)
        rv3d = self._area.spaces.active.region_3d if self._area.spaces.active else None

        display_offset = get_explosion_display_offset(settings, self._prepared)

        raycast_res = None
        plane_hit_uv = None
        if rv3d is not None:
            try:
                ray_orig = view3d_utils.region_2d_to_origin_3d(canvas_region, rv3d, coord_2d)
                ray_dir = view3d_utils.region_2d_to_vector_3d(canvas_region, rv3d, coord_2d)
                raycast_res = raycast_connector_surface(
                    ray_orig, ray_dir, self._prepared, display_offset=display_offset
                )
                # Interseção do raio com o plano contínuo da superfície de corte (deslocado por display_offset)
                orig_disp = self._prepared.surface_origin + display_offset
                denom = ray_dir.dot(self._prepared.surface_normal)
                if abs(denom) > 1e-5:
                    t = (orig_disp - ray_orig).dot(self._prepared.surface_normal) / denom
                    if t >= 0.0:
                        hit_plane = ray_orig + ray_dir * t - display_offset
                        plane_hit_uv = self._prepared.world_to_uv_mm(hit_plane)
            except Exception:
                raycast_res = None
                plane_hit_uv = None

        # Atualiza hover ghost apenas sobre a superfície física útil
        if raycast_res is not None:
            hit_world, hit_u, hit_v = raycast_res
            _EDITOR_STATE["hover_world"] = hit_world + display_offset
            _EDITOR_STATE["hover_u_mm"] = hit_u
            _EDITOR_STATE["hover_v_mm"] = hit_v
        else:
            _EDITOR_STATE["hover_world"] = None

        # 3. Rotação interativa de cápsula ('R')
        if self._rotating:
            if event.type == 'MOUSEMOVE':
                delta_x = event.mouse_x - self._rotate_start_mouse_x
                new_yaw = (self._rotate_start_yaw + delta_x * 0.5) % 360.0
                if new_yaw > 180.0:
                    new_yaw -= 360.0
                idx = settings.manual_connector_index
                if 0 <= idx < len(settings.manual_connectors):
                    settings.manual_connectors[idx].yaw_deg = round(new_yaw, 1)
                evaluate_connector_specs(self._prepared, settings)
                return {'RUNNING_MODAL'}
            elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
                self._rotating = False
                return {'RUNNING_MODAL'}
            elif event.type in {'RIGHTMOUSE', 'ESC'}:
                idx = settings.manual_connector_index
                if 0 <= idx < len(settings.manual_connectors):
                    settings.manual_connectors[idx].yaw_deg = self._rotate_start_yaw
                self._rotating = False
                evaluate_connector_specs(self._prepared, settings)
                return {'RUNNING_MODAL'}

        # 4. Arraste ativo de marcador
        if _EDITOR_STATE["is_dragging"]:
            idx = _EDITOR_STATE["drag_idx"]
            if event.type == 'MOUSEMOVE':
                # Usa UV da interseção no plano para arraste contínuo suave (inclusive permitindo resgatar pinos que caíram fora)
                drag_uv = plane_hit_uv if plane_hit_uv is not None else ((raycast_res[1], raycast_res[2]) if raycast_res else None)
                if drag_uv is not None and 0 <= idx < len(settings.manual_connectors):
                    hit_u, hit_v = drag_uv
                    conn = settings.manual_connectors[idx]
                    conn.u_mm = round(hit_u, 2)
                    conn.v_mm = round(hit_v, 2)
                    evaluate_connector_specs(self._prepared, settings)
                return {'RUNNING_MODAL'}

            elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                # Soltou o clique: finaliza arraste e mantém posição
                _EDITOR_STATE["is_dragging"] = False
                _EDITOR_STATE["drag_idx"] = -1
                evaluate_connector_specs(self._prepared, settings)
                return {'RUNNING_MODAL'}

            elif event.type in {'RIGHTMOUSE', 'ESC'}:
                # Cancela apenas o arraste atual e restaura posição anterior (T26)
                if 0 <= idx < len(settings.manual_connectors):
                    conn = settings.manual_connectors[idx]
                    conn.u_mm = _EDITOR_STATE["drag_start_u"]
                    conn.v_mm = _EDITOR_STATE["drag_start_v"]
                _EDITOR_STATE["is_dragging"] = False
                _EDITOR_STATE["drag_idx"] = -1
                evaluate_connector_specs(self._prepared, settings)
                return {'RUNNING_MODAL'}

        # 5. Detecção de clique no Viewport (Canvas 3D)
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # PRIMEIRO: Tenta selecionar um marcador existente (por tela 2D ou projeção no plano)
            clicked_idx = -1
            min_dist_px = 1e9

            # 1. Teste de proximidade na tela (2D viewport pixels) - raio de 24 pixels
            if rv3d is not None:
                for i, c in enumerate(settings.manual_connectors):
                    try:
                        pin_world = self._prepared.uv_mm_to_world(c.u_mm, c.v_mm) + display_offset
                        screen_pos = view3d_utils.location_3d_to_region_2d(canvas_region, rv3d, pin_world)
                        if screen_pos is not None:
                            d_px = math.hypot(coord_2d[0] - screen_pos[0], coord_2d[1] - screen_pos[1])
                            if d_px < 24.0 and d_px < min_dist_px:
                                min_dist_px = d_px
                                clicked_idx = i
                    except Exception:
                        pass

            # 2. Fallback de teste no plano UV caso tela não acerte
            if clicked_idx < 0 and plane_hit_uv is not None:
                hit_u, hit_v = plane_hit_uv
                min_dist_mm = 1e9
                pick_thresh_mm = max(
                    getattr(settings, "connector_diameter_mm", 4.0),
                    getattr(settings, "connector_capsule_length_mm", 6.0)
                ) * 0.9

                for i, c in enumerate(settings.manual_connectors):
                    du = c.u_mm - hit_u
                    dv = c.v_mm - hit_v
                    dist = math.hypot(du, dv)
                    if dist < pick_thresh_mm and dist < min_dist_mm:
                        min_dist_mm = dist
                        clicked_idx = i

            # Se clicou num marcador existente (VÁLIDO OU INVÁLIDO):
            if clicked_idx >= 0:
                settings.manual_connector_index = clicked_idx
                _EDITOR_STATE["is_dragging"] = True
                _EDITOR_STATE["drag_idx"] = clicked_idx
                _EDITOR_STATE["drag_start_u"] = settings.manual_connectors[clicked_idx].u_mm
                _EDITOR_STATE["drag_start_v"] = settings.manual_connectors[clicked_idx].v_mm
                return {'RUNNING_MODAL'}

            # Não clicou em marcador existente:
            # Submodo ADICIONAR: adiciona um novo marcador na superfície útil
            if settings.manual_editor_submode == 'ADD':
                if raycast_res is not None:
                    hit_world, hit_u, hit_v = raycast_res
                    item = settings.manual_connectors.add()
                    item.connector_id = "pin_" + uuid.uuid4().hex[:12]
                    item.u_mm = round(hit_u, 2)
                    item.v_mm = round(hit_v, 2)
                    item.yaw_deg = 0.0
                    settings.manual_connector_index = len(settings.manual_connectors) - 1
                    evaluate_connector_specs(self._prepared, settings)
                    self.report({'INFO'}, report_msg(f"Pino #{len(settings.manual_connectors)} posicionado em U={hit_u:.1f}, V={hit_v:.1f} mm.", f"Pin #{len(settings.manual_connectors)} placed at U={hit_u:.1f}, V={hit_v:.1f} mm."))
                    return {'RUNNING_MODAL'}
                else:
                    # Clicou fora da superfície de corte no canvas 3D: avisa o usuário e não cria pino solto
                    self.report({'INFO'}, localize_text("Clique sobre a superfície destacada da peça para posicionar o pino."))
                    return {'RUNNING_MODAL'}

            # Submodo MOVE e clicou fora de qualquer pino: mantém seleção
            return {'RUNNING_MODAL'}

        # 6. Atalhos de Teclado Operacionais
        if event.type == 'TAB' and event.value == 'PRESS':
            # Alterna submodo Adicionar / Mover
            settings.manual_editor_submode = 'MOVE' if settings.manual_editor_submode == 'ADD' else 'ADD'
            submode_pt = 'Adicionar Pinos' if settings.manual_editor_submode == 'ADD' else 'Mover / Selecionar'
            submode_en = 'Add Pins' if settings.manual_editor_submode == 'ADD' else 'Move / Select'
            self.report({'INFO'}, report_msg(f"Submodo: {submode_pt}", f"Submode: {submode_en}"))
            return {'RUNNING_MODAL'}

        elif event.type == 'R' and event.value == 'PRESS':
            # Inicia rotação da cápsula ativa
            idx = settings.manual_connector_index
            if 0 <= idx < len(settings.manual_connectors):
                self._rotating = True
                self._rotate_start_mouse_x = event.mouse_x
                self._rotate_start_yaw = settings.manual_connectors[idx].yaw_deg
        elif event.type in {'X', 'DEL'} and event.shift and event.value == 'PRESS':
            # Limpa todos os pinos no editor
            settings.manual_connectors.clear()
            settings.manual_connector_index = 0
            _EDITOR_STATE["is_dragging"] = False
            _EDITOR_STATE["drag_idx"] = -1
            self.report({'INFO'}, localize_text("Todos os pinos foram limpos."))
            return {'RUNNING_MODAL'}

        elif event.type in {'X', 'DEL'} and event.value == 'PRESS':
            # Remove o pino selecionado
            idx = settings.manual_connector_index
            if 0 <= idx < len(settings.manual_connectors):
                settings.manual_connectors.remove(idx)
                settings.manual_connector_index = max(0, min(idx, len(settings.manual_connectors) - 1))
                _EDITOR_STATE["is_dragging"] = False
                _EDITOR_STATE["drag_idx"] = -1
                evaluate_connector_specs(self._prepared, settings)
                self.report({'INFO'}, localize_text("Pino removido."))
                return {'RUNNING_MODAL'}

        elif event.type == 'D' and event.value == 'PRESS' and event.shift:
            # Duplica o pino selecionado na posição do cursor
            idx = settings.manual_connector_index
            if 0 <= idx < len(settings.manual_connectors) and raycast_res is not None:
                orig_pin = settings.manual_connectors[idx]
                hit_world, hit_u, hit_v = raycast_res
                item = settings.manual_connectors.add()
                item.connector_id = "pin_" + uuid.uuid4().hex[:12]
                item.u_mm = round(hit_u, 2)
                item.v_mm = round(hit_v, 2)
                item.yaw_deg = orig_pin.yaw_deg
                settings.manual_connector_index = len(settings.manual_connectors) - 1
                evaluate_connector_specs(self._prepared, settings)
                self.report({'INFO'}, report_msg(f"Pino duplicado em U={hit_u:.1f}, V={hit_v:.1f} mm.", f"Pin duplicated at U={hit_u:.1f}, V={hit_v:.1f} mm."))
                return {'RUNNING_MODAL'}

        elif event.type == 'G' and event.value == 'PRESS':
            # Inicia movimento do pino selecionado (atalho G tradicional)
            idx = settings.manual_connector_index
            if 0 <= idx < len(settings.manual_connectors):
                _EDITOR_STATE["is_dragging"] = True
                _EDITOR_STATE["drag_idx"] = idx
                _EDITOR_STATE["drag_start_u"] = settings.manual_connectors[idx].u_mm
                _EDITOR_STATE["drag_start_v"] = settings.manual_connectors[idx].v_mm
                return {'RUNNING_MODAL'}

        elif event.type == 'V' and event.value == 'PRESS':
            # Re-alinha a visualização 3D perpendicularmente ao corte (inverte 180° se Shift+V ou se já alinhado)
            flip = True if event.shift else None
            if align_viewport_to_cut_surface(self._area, self._prepared, settings, self._target, flip=flip):
                msg = "Visão invertida (180°)." if flip else "Visão alinhada à face de corte."
                self.report({'INFO'}, localize_text(msg))
                self._area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            # Confirma posições e dispara geração da prévia
            return self._confirm_and_generate(context)

        elif event.type == 'ESC' and event.value == 'PRESS':
            # Restaura snapshot de entrada e cancela edição (T26)
            return self._cancel_and_restore(context)

        # Deixa outros eventos passarem para o Blender
        return {'PASS_THROUGH'}

    def _confirm_and_generate(self, context):
        """Conclui a edição e gera a prévia com os pinos e cavidades."""
        settings = context.scene.chest_splitter
        try:
            self._prepared = prepare_split_candidates(context)
            eval_res = evaluate_connector_specs(self._prepared, settings)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'RUNNING_MODAL'}
        if any(not ev["is_valid"] for ev in eval_res):
            self.report({'WARNING'}, localize_text("Há pinos inválidos ou colidindo. Corrija-os ou remova-os."))
            return {'RUNNING_MODAL'}
        stop_connector_editor(context.scene)
        settings.session_status = 'PREVIEW_STALE'
        try:
            result = bpy.ops.chest.splitter_generate_preview()
            if 'FINISHED' in result:
                self.report({'INFO'}, localize_text("Posições confirmadas! Prévia gerada com sucesso."))
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
        if self._area:
            self._area.tag_redraw()
        # Keep placed markers on boolean failure; they can be edited again.
        return {'FINISHED'}

    def _cancel_and_restore(self, context):
        """Restaura a lista anterior à entrada do editor."""
        stop_connector_editor(context.scene)
        settings = context.scene.chest_splitter

        # Restaura snapshot de conectores
        settings.manual_connectors.clear()
        for sp in self._snapshot:
            item = settings.manual_connectors.add()
            item.connector_id = sp.get("connector_id", "")
            item.u_mm = sp.get("u_mm", 0.0)
            item.v_mm = sp.get("v_mm", 0.0)
            item.yaw_deg = sp.get("yaw_deg", 0.0)

        if self._area:
            self._area.tag_redraw()
        self.report({'INFO'}, localize_text("Edição de posições cancelada. Marcadores restaurados."))
        return {'CANCELLED'}

    def _finish_cleanup(self, context, result_state, pass_through=False):
        stop_connector_editor(context.scene)
        if getattr(self, "_area", None):
            try:
                self._area.tag_redraw()
            except Exception:
                pass
        try:
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
        except Exception:
            pass
        if pass_through:
            return {result_state, 'PASS_THROUGH'}
        return {result_state}


class CHEST_OT_splitter_finish_manual_connectors(bpy.types.Operator):
    """Conclui a edição manual de pinos mantendo as posições definidas sem gerar a prévia imediatamente."""
    bl_idname = "chest.splitter_finish_manual_connectors"
    bl_label = "Concluir Edição"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        stop_connector_editor(context.scene)
        settings = context.scene.chest_splitter
        settings.session_status = 'PREVIEW_STALE'
        self.report({'INFO'}, localize_text("Edição manual de pinos concluída."))
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class CHEST_OT_splitter_cancel_manual_connectors(bpy.types.Operator):
    """Cancela a edição manual e restaura os pinos para as posições anteriores à entrada no editor."""
    bl_idname = "chest.splitter_cancel_manual_connectors"
    bl_label = "Cancelar Edição"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.chest_splitter
        if not settings.is_editing_connectors:
            return {'CANCELLED'}
        stop_connector_editor(context.scene)

        if CHEST_OT_splitter_edit_manual_connectors._last_snapshot is not None:
            settings.manual_connectors.clear()
            for sp in CHEST_OT_splitter_edit_manual_connectors._last_snapshot:
                item = settings.manual_connectors.add()
                item.connector_id = sp.get("connector_id", "")
                item.u_mm = sp.get("u_mm", 0.0)
                item.v_mm = sp.get("v_mm", 0.0)
                item.yaw_deg = sp.get("yaw_deg", 0.0)

        self.report({'INFO'}, localize_text("Edição manual cancelada. Pinos restaurados."))
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class CHEST_OT_splitter_confirm_manual_connectors(bpy.types.Operator):
    """Aplica as posições manuais definidas e gera a prévia transacional com pinos (Seção 4.4)"""
    bl_idname = "chest.splitter_confirm_manual_connectors"
    bl_label = "Confirmar Posições e Gerar Prévia"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.chest_splitter

        # Prepara corte e avalia specs antes de fechar o editor
        try:
            prep = prepare_split_candidates(context)
        except Exception as e:
            self.report({'ERROR'}, report_msg(f"Não foi possível preparar o corte: {e}", f"Could not prepare cut: {e}"))
            return {'CANCELLED'}

        eval_res = evaluate_connector_specs(prep, settings)
        has_invalid = any(not ev["is_valid"] for ev in eval_res)
        if has_invalid:
            first_err = next(ev["reason"] for ev in eval_res if not ev["is_valid"])
            first_err_loc = localize_text(first_err)
            self.report({'WARNING'}, report_msg(f"Não é possível gerar prévia: {first_err_loc}. Corrija a posição ou exclua o pino.", f"Cannot generate preview: {first_err_loc}. Fix position or delete the pin."))
            return {'CANCELLED'}

        stop_connector_editor(context.scene)

        settings.session_status = 'PREVIEW_STALE'
        try:
            result = bpy.ops.chest.splitter_generate_preview()
            if 'FINISHED' not in result:
                return {'CANCELLED'}
            self.report({'INFO'}, localize_text("Prévia com conectores gerada com sucesso."))
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, report_msg(f"Erro na geração da prévia: {e}", f"Preview generation error: {e}"))
            return {'CANCELLED'}


def align_viewport_to_cut_surface(area, prepared, settings=None, target=None, flip: Optional[bool] = None) -> bool:
    """Orienta a câmera da Viewport 3D perpendicularmente à superfície de corte mantendo o horizonte nivelado (sem roll/inclinação).
    
    Detecta de forma inteligente qual lado da peça o usuário já está visualizando para que a câmera
    nunca pule inadvertidamente para trás do bloco. Se a câmera já estiver alinhada, pressionar novamente
    inverte a direção em 180° (comportamento de alternância idêntico aos atalhos numéricos do Blender).
    """
    if not area or not prepared:
        return False
    if not hasattr(area, "spaces") or not area.spaces.active:
        return False
    space = area.spaces.active
    if space.type != 'VIEW_3D':
        return False
    rv3d = getattr(space, "region_3d", None)
    if not rv3d:
        return False

    norm = getattr(prepared, "surface_normal", None)
    if not norm or norm.length < 1e-6:
        return False
    norm = norm.normalized()

    # Obter a direção atual de visão da câmera (vetor apontando do olho do observador para a cena)
    curr_mat = rv3d.view_rotation.to_matrix()
    curr_view_dir = -curr_mat.col[2]

    # As duas direções de alinhamento ortogonal são:
    # 1) Olhar na direção -norm (câmera situada no lado +norm, logo cam_z = +norm)
    # 2) Olhar na direção +norm (câmera situada no lado -norm, logo cam_z = -norm)
    dot_pos = curr_view_dir.dot(-norm)
    dot_neg = curr_view_dir.dot(norm)

    if flip is True:
        # Inversão explícita solicitada pelo usuário (ex: botão Inverter ou Shift+V)
        if dot_pos >= dot_neg:
            target_cam_z = -norm
        else:
            target_cam_z = norm
    elif flip is False:
        target_cam_z = norm
    else:
        # Modo inteligente (flip is None):
        # Se a câmera JÁ estiver praticamente alinhada com um dos lados (dot > 0.98),
        # alternar para o lado oposto (toggle 180°).
        if dot_pos > 0.98:
            target_cam_z = -norm
        elif dot_neg > 0.98:
            target_cam_z = norm
        else:
            # Usuário estava orbitando livremente: alinha ao lado mais próximo da visão atual,
            # impedindo terminantemente que a visão vá para as costas do bloco!
            if dot_pos >= dot_neg:
                target_cam_z = norm
            else:
                target_cam_z = -norm

    world_up = Vector((0.0, 0.0, 1.0))
    if abs(target_cam_z.z) > 0.999:
        if target_cam_z.z > 0:
            # Vista Superior (Top) - alinhada com eixos nativos do Blender
            cam_z = Vector((0.0, 0.0, 1.0))
            cam_y = Vector((0.0, 1.0, 0.0))
            cam_x = Vector((1.0, 0.0, 0.0))
        else:
            # Vista Inferior (Bottom) - alinhada com eixos nativos do Blender
            cam_z = Vector((0.0, 0.0, -1.0))
            cam_y = Vector((0.0, -1.0, 0.0))
            cam_x = Vector((1.0, 0.0, 0.0))
    else:
        # Horizonte estritamente nivelado com a gravidade global do Blender (zero roll):
        # cam_x é perpendicular a target_cam_z e ao eixo Z do mundo, garantindo cam_x.z == 0.0
        cam_z = target_cam_z
        cam_x = world_up.cross(cam_z).normalized()
        cam_y = cam_z.cross(cam_x).normalized()

    cam_rot_mat = Matrix((cam_x, cam_y, cam_z)).transposed()

    display_offset = get_explosion_display_offset(settings, prepared) if settings else Vector((0.0, 0.0, 0.0))
    rv3d.view_rotation = cam_rot_mat.to_quaternion()
    rv3d.view_location = prepared.surface_origin + display_offset

    span_max = 0.0
    if getattr(prepared, "interface", None):
        span_max = max(
            getattr(prepared.interface, "width_mm", 0.0),
            getattr(prepared.interface, "height_mm", 0.0)
        ) / getattr(prepared, "unit_scale", 1000.0)
    target_dim = 0.0
    if target and hasattr(target, "dimensions"):
        target_dim = max(target.dimensions.x, target.dimensions.y, target.dimensions.z)
    if span_max < 1e-4:
        span_max = target_dim if target_dim > 1e-4 else 0.1

    ref_dim = target_dim if target_dim > 1e-4 else span_max
    if ref_dim > 1e-4 and (0.3 * ref_dim < rv3d.view_distance < 6.0 * ref_dim):
        pass  # Mantém a distância confortável atual do usuário
    else:
        rv3d.view_distance = max(span_max * 1.8, 0.1)

    area.tag_redraw()
    return True


class CHEST_OT_splitter_view_cut_face(bpy.types.Operator):
    """Orienta a câmera perpendicularmente à superfície de corte ou inverte a direção de visão em 180°"""
    bl_idname = "chest.splitter_view_cut_face"
    bl_label = "Ver Face de Encaixe"
    bl_options = {'REGISTER'}

    flip_direction: bpy.props.BoolProperty(
        name="Inverter Lado da Vista",
        description="Inverte a direção da visão em 180°",
        default=False
    )

    def execute(self, context):
        settings = context.scene.chest_splitter
        prep = get_cached_prepared_split()
        if prep is None:
            try:
                prep = prepare_split_candidates(context)
            except Exception as e:
                self.report({'WARNING'}, report_msg(f"Superfície não disponível: {e}", f"Surface not available: {e}"))
                return {'CANCELLED'}

        area_3d = None
        if context.area and context.area.type == 'VIEW_3D':
            area_3d = context.area
        else:
            for a in context.screen.areas:
                if a.type == 'VIEW_3D':
                    area_3d = a
                    break

        if not area_3d:
            return {'CANCELLED'}

        flip = True if self.flip_direction else None
        if align_viewport_to_cut_surface(area_3d, prep, settings, settings.target_object, flip=flip):
            msg = "Visão invertida (180°)." if self.flip_direction else "Câmera alinhada à face de contato."
            self.report({'INFO'}, localize_text(msg))
            return {'FINISHED'}
        return {'CANCELLED'}
