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


# Estado volátil de interação do editor para o drawing overlay
_EDITOR_STATE = {
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
    _rotating = False
    _rotate_start_mouse_x = 0
    _rotate_start_yaw = 0.0

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "chest_splitter", None)
        if not settings or not settings.target_object:
            return False
        return settings.split_mode in ('PLANE', 'LOOP', 'MATERIAL')

    def execute(self, context):
        settings = context.scene.chest_splitter
        settings.connector_distribution = 'MANUAL'
        settings.connector_enabled = True
        try:
            self._prepared = prepare_split_candidates(context, force_recompute=True)
            evaluate_connector_specs(self._prepared, settings)
        except Exception:
            pass
        return {'FINISHED'}

    def invoke(self, context, event):
        settings = context.scene.chest_splitter
        target = settings.target_object
        if not target:
            self.report({'WARNING'}, "Defina um objeto alvo antes de editar pinos.")
            return {'CANCELLED'}

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
            self.report({'ERROR'}, "Nenhuma área 3D Viewport encontrada.")
            return {'CANCELLED'}

        for r in area_3d.regions:
            if r.type == 'WINDOW':
                region_win = r
                break

        if not region_win:
            self.report({'ERROR'}, "Região WINDOW do Viewport não encontrada.")
            return {'CANCELLED'}

        self._area = area_3d
        self._region = region_win

        # Prepara a superfície de contato sem rodar booleanas (Etapa B / C)
        try:
            self._prepared = prepare_split_candidates(context, force_recompute=False)
        except Exception as e:
            self.report({'ERROR'}, f"Falha ao preparar superfície de encaixe: {e}")
            return {'CANCELLED'}

        # Ativa modo Manual e Encaixes
        settings.connector_distribution = 'MANUAL'
        settings.connector_enabled = True
        settings.is_editing_connectors = True

        # Salva snapshot dos conectores atuais para reversão com Cancelar/Esc
        self._snapshot = [
            {
                "connector_id": getattr(c, "connector_id", "") or f"pin_{idx}",
                "u_mm": c.u_mm,
                "v_mm": c.v_mm,
                "yaw_deg": c.yaw_deg,
            }
            for idx, c in enumerate(settings.manual_connectors)
        ]

        # Avalia estado inicial
        evaluate_connector_specs(self._prepared, settings)

        _EDITOR_STATE["is_active"] = True
        _EDITOR_STATE["is_dragging"] = False
        _EDITOR_STATE["drag_idx"] = -1
        _EDITOR_STATE["hover_world"] = None

        context.window_manager.modal_handler_add(self)
        self.report(
            {'INFO'},
            "Editor de Pinos: Clique para adicionar | G: mover | R: girar | X/Del: remover pino | Shift+X: limpar todos | Enter: confirmar | Esc: sair."
        )
        self._area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        settings = context.scene.chest_splitter

        # Se a extensão foi desativada ou target sumiu, encerra com segurança
        if not settings.is_editing_connectors or not self._prepared:
            return self._finish_cleanup(context, 'CANCELLED')

        # Redesenha a área do viewport para feedback responsivo
        if self._area:
            self._area.tag_redraw()

        # Verifica se o cursor está estritamente sobre o canvas 3D (excluindo painel N, barra de ferramentas e headers)
        canvas_region = get_view3d_canvas_region(self._area, event.mouse_x, event.mouse_y)
        in_canvas = (canvas_region is not None)

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
        if rv3d is not None:
            try:
                ray_orig = view3d_utils.region_2d_to_origin_3d(canvas_region, rv3d, coord_2d)
                ray_dir = view3d_utils.region_2d_to_vector_3d(canvas_region, rv3d, coord_2d)
                raycast_res = raycast_connector_surface(
                    ray_orig, ray_dir, self._prepared, display_offset=display_offset
                )
            except Exception:
                raycast_res = None

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
                if raycast_res is not None and 0 <= idx < len(settings.manual_connectors):
                    hit_world, hit_u, hit_v = raycast_res
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
            if raycast_res is not None:
                hit_world, hit_u, hit_v = raycast_res
                hit_pos_disp = hit_world + display_offset

                # Verifica se clicou sobre um marcador existente (distância em tela ou em UV)
                clicked_idx = -1
                min_dist_mm = 1e9
                pick_thresh_mm = max(
                    getattr(settings, "connector_diameter_mm", 4.0),
                    getattr(settings, "connector_capsule_length_mm", 6.0)
                ) * 0.75

                for i, c in enumerate(settings.manual_connectors):
                    du = c.u_mm - hit_u
                    dv = c.v_mm - hit_v
                    dist = math.hypot(du, dv)
                    if dist < pick_thresh_mm and dist < min_dist_mm:
                        min_dist_mm = dist
                        clicked_idx = i

                # Se clicou num marcador existente:
                if clicked_idx >= 0:
                    settings.manual_connector_index = clicked_idx
                    _EDITOR_STATE["is_dragging"] = True
                    _EDITOR_STATE["drag_idx"] = clicked_idx
                    _EDITOR_STATE["drag_start_u"] = settings.manual_connectors[clicked_idx].u_mm
                    _EDITOR_STATE["drag_start_v"] = settings.manual_connectors[clicked_idx].v_mm
                    return {'RUNNING_MODAL'}

                # Submodo ADICIONAR: adiciona um novo marcador na superfície útil
                if settings.manual_editor_submode == 'ADD':
                    item = settings.manual_connectors.add()
                    item.connector_id = f"pin_{len(settings.manual_connectors)}"
                    item.u_mm = round(hit_u, 2)
                    item.v_mm = round(hit_v, 2)
                    item.yaw_deg = 0.0
                    settings.manual_connector_index = len(settings.manual_connectors) - 1
                    evaluate_connector_specs(self._prepared, settings)
                    self.report({'INFO'}, f"Pino #{len(settings.manual_connectors)} posicionado em U={hit_u:.1f}, V={hit_v:.1f} mm.")
                    return {'RUNNING_MODAL'}

                # Se submodo for MOVE e clicou na superfície sem acertar pino, mantém estado
                return {'RUNNING_MODAL'}
            else:
                # Clicou fora da superfície de corte no canvas 3D: avisa o usuário e não cria pino solto
                if settings.manual_editor_submode == 'ADD':
                    self.report({'INFO'}, "Clique sobre a superfície destacada da peça para posicionar o pino.")
                return {'RUNNING_MODAL'}

        # 6. Atalhos de Teclado Operacionais
        if event.type == 'TAB' and event.value == 'PRESS':
            # Alterna submodo Adicionar / Mover
            settings.manual_editor_submode = 'MOVE' if settings.manual_editor_submode == 'ADD' else 'ADD'
            self.report({'INFO'}, f"Submodo: {'Adicionar Pinos' if settings.manual_editor_submode == 'ADD' else 'Mover / Selecionar'}")
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
            self.report({'INFO'}, "Todos os pinos foram limpos.")
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
                self.report({'INFO'}, "Pino removido.")
                return {'RUNNING_MODAL'}

        elif event.type == 'D' and event.value == 'PRESS' and event.shift:
            # Duplica o pino selecionado na posição do cursor
            idx = settings.manual_connector_index
            if 0 <= idx < len(settings.manual_connectors) and raycast_res is not None:
                orig_pin = settings.manual_connectors[idx]
                hit_world, hit_u, hit_v = raycast_res
                item = settings.manual_connectors.add()
                item.connector_id = f"pin_{len(settings.manual_connectors)}"
                item.u_mm = round(hit_u, 2)
                item.v_mm = round(hit_v, 2)
                item.yaw_deg = orig_pin.yaw_deg
                settings.manual_connector_index = len(settings.manual_connectors) - 1
                evaluate_connector_specs(self._prepared, settings)
                self.report({'INFO'}, f"Pino duplicado em U={hit_u:.1f}, V={hit_v:.1f} mm.")
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
        settings.is_editing_connectors = False
        _EDITOR_STATE["is_active"] = False
        _EDITOR_STATE["hover_world"] = None
        try:
            from .gpu_drawing import clear_grid_cache
            clear_grid_cache()
        except Exception:
            pass

        # Validação final dos conectores
        eval_res = evaluate_connector_specs(self._prepared, settings)
        has_invalid = any(not ev["is_valid"] for ev in eval_res)
        if has_invalid:
            self.report({'WARNING'}, "Atenção: há pinos inválidos ou colidindo. Corrija-os ou remova-os.")

        settings.session_status = 'PREVIEW_STALE'
        try:
            bpy.ops.chest.splitter_generate_preview()
            self.report({'INFO'}, "Posições confirmadas! Prévia gerada com sucesso.")
        except Exception as e:
            self.report({'ERROR'}, f"Erro ao gerar prévia com os encaixes: {e}")

        if self._area:
            self._area.tag_redraw()
        return {'FINISHED'}

    def _cancel_and_restore(self, context):
        """Restaura a lista anterior à entrada do editor."""
        settings = context.scene.chest_splitter
        settings.is_editing_connectors = False
        _EDITOR_STATE["is_active"] = False
        _EDITOR_STATE["hover_world"] = None
        try:
            from .gpu_drawing import clear_grid_cache
            clear_grid_cache()
        except Exception:
            pass

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
        self.report({'INFO'}, "Edição de posições cancelada. Marcadores restaurados.")
        return {'CANCELLED'}

    def _finish_cleanup(self, context, result_state):
        settings = context.scene.chest_splitter
        settings.is_editing_connectors = False
        _EDITOR_STATE["is_active"] = False
        _EDITOR_STATE["hover_world"] = None
        try:
            from .gpu_drawing import clear_grid_cache
            clear_grid_cache()
        except Exception:
            pass
        if self._area:
            self._area.tag_redraw()
        return {result_state}


class CHEST_OT_splitter_confirm_manual_connectors(bpy.types.Operator):
    """Aplica as posições manuais definidas e gera a prévia transacional com pinos (Seção 4.4)"""
    bl_idname = "chest.splitter_confirm_manual_connectors"
    bl_label = "Confirmar Posições e Gerar Prévia"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.chest_splitter

        # Prepara corte e avalia specs antes de fechar o editor
        prep = get_cached_prepared_split()
        if prep is None:
            try:
                prep = prepare_split_candidates(context)
            except Exception as e:
                self.report({'ERROR'}, f"Não foi possível preparar o corte: {e}")
                return {'CANCELLED'}

        eval_res = evaluate_connector_specs(prep, settings)
        has_invalid = any(not ev["is_valid"] for ev in eval_res)
        if has_invalid:
            first_err = next(ev["reason"] for ev in eval_res if not ev["is_valid"])
            self.report({'WARNING'}, f"Não é possível gerar prévia: {first_err}. Corrija a posição ou exclua o pino.")
            return {'CANCELLED'}

        settings.is_editing_connectors = False
        _EDITOR_STATE["is_active"] = False
        _EDITOR_STATE["hover_world"] = None
        try:
            from .gpu_drawing import clear_grid_cache
            clear_grid_cache()
        except Exception:
            pass

        settings.session_status = 'PREVIEW_STALE'
        try:
            bpy.ops.chest.splitter_generate_preview()
            self.report({'INFO'}, "Prévia com conectores gerada com sucesso.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Erro na geração da prévia: {e}")
            return {'CANCELLED'}


class CHEST_OT_splitter_view_cut_face(bpy.types.Operator):
    """Orienta a câmera perpendicularmente à superfície de encaixe e enquadra a área útil (Seção 4.1)"""
    bl_idname = "chest.splitter_view_cut_face"
    bl_label = "Ver Face de Encaixe"
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = context.scene.chest_splitter
        prep = get_cached_prepared_split()
        if prep is None:
            try:
                prep = prepare_split_candidates(context)
            except Exception as e:
                self.report({'WARNING'}, f"Superfície não disponível: {e}")
                return {'CANCELLED'}

        area_3d = None
        if context.area and context.area.type == 'VIEW_3D':
            area_3d = context.area
        else:
            for a in context.screen.areas:
                if a.type == 'VIEW_3D':
                    area_3d = a
                    break

        if not area_3d or not area_3d.spaces.active:
            return {'CANCELLED'}

        rv3d = area_3d.spaces.active.region_3d
        if not rv3d:
            return {'CANCELLED'}

        norm = prep.surface_normal.normalized()
        u_axis = prep.axis_u.normalized()
        v_axis = prep.axis_v.normalized()

        # Matriz de visualização alinhando Z da câmera oposto à normal e Y da câmera alinhado a V
        cam_z = norm
        cam_y = v_axis
        cam_x = cam_y.cross(cam_z).normalized()
        cam_rot_mat = Matrix((cam_x, cam_y, cam_z)).transposed()

        display_offset = get_explosion_display_offset(settings, prep)
        rv3d.view_rotation = cam_rot_mat.to_quaternion()
        rv3d.view_location = prep.surface_origin + display_offset

        # Enquadra distância com base na largura/altura útil
        span_max = max(prep.interface.width_mm, prep.interface.height_mm) / prep.unit_scale
        if span_max < 1e-4:
            span_max = 0.1
        rv3d.view_distance = span_max * 1.8

        area_3d.tag_redraw()
        self.report({'INFO'}, "Câmera alinhada à face de contato.")
        return {'FINISHED'}
