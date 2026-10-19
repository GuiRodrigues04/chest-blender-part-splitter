"""Interface de usuário para o Chest Part Splitter (Sidebar N > Chest > Part Splitter)."""

import bpy
from .constants import PANEL_TITLE
from .translations import localize_text, get_addon_locale


def draw_help_button(layout, topic: str):
    """Desenha botão compacto com ícone INFO para exibir ajuda e popup dinâmico."""
    row = layout.row(align=True)
    op = row.operator("chest.splitter_help", text=localize_text(""), icon='INFO', emboss=False)
_CACHED_UI_MAT_KEY = None
_CACHED_UI_MAT_REGIONS = []
_CACHED_UI_MAT_ANALYSIS = {}

def get_cached_material_ui_analysis(obj, mat_idx, region_idx):
    global _CACHED_UI_MAT_KEY, _CACHED_UI_MAT_REGIONS, _CACHED_UI_MAT_ANALYSIS
    if not obj or not obj.data:
        return [], {}
    key = (obj.name, len(obj.data.polygons), mat_idx, region_idx)
    if _CACHED_UI_MAT_KEY == key:
        return _CACHED_UI_MAT_REGIONS, _CACHED_UI_MAT_ANALYSIS
    from .geometry_material import list_material_regions, analyze_material_structure
    regions = list_material_regions(obj, mat_idx)
    analysis = analyze_material_structure(obj, mat_idx, region_idx)
    _CACHED_UI_MAT_KEY = key
    _CACHED_UI_MAT_REGIONS = regions
    _CACHED_UI_MAT_ANALYSIS = analysis
    return regions, analysis


class VIEW3D_PT_chest_part_splitter(bpy.types.Panel):
    """Painel principal do Chest Part Splitter na barra lateral da Viewport 3D"""
    bl_label = PANEL_TITLE
    bl_idname = "VIEW3D_PT_chest_part_splitter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Chest'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.chest_splitter
        obj = settings.target_object
        loc = get_addon_locale(context)

        # --- SEÇÃO 1: OBJETO ALVO ---
        box_target = layout.box()
        row_target_head = box_target.row(align=True)
        row_target_head.label(text=localize_text("1. Objeto Alvo"), icon='OBJECT_DATA')
        draw_help_button(row_target_head, "target_model")

        row_set = box_target.row(align=True)
        row_set.operator("chest.splitter_set_target", text=localize_text("Usar selecionado como alvo"), icon='EYEDROPPER')

        active_obj = context.active_object
        if active_obj and active_obj.type == 'MESH' and active_obj != obj:
            row_active = box_target.row(align=True)
            row_active.alert = True
            lbl_use_active = "Set Selected as Target" if loc == 'en_US' else "Definir Selecionado como Alvo"
            op = row_active.operator(
                "chest.splitter_set_target",
                text=f"{lbl_use_active}: {active_obj.name}",
                icon='CHECKMARK'
            )
            op.object_name = active_obj.name

        part_a_name = getattr(settings, "last_committed_part_a", "")
        part_b_name = getattr(settings, "last_committed_part_b", "")
        has_part_a = bool(part_a_name and (part_a_name in scene.objects or part_a_name in bpy.data.objects))
        has_part_b = bool(part_b_name and (part_b_name in scene.objects or part_b_name in bpy.data.objects))
        if has_part_a or has_part_b:
            row_parts = box_target.row(align=True)
            lbl_switch = "Switch Part:" if loc == 'en_US' else "Alternar Peça:"
            row_parts.label(text=lbl_switch, icon='SNAP_VOLUME')
            if has_part_a:
                lbl_pa = f"Part A ({part_a_name})" if loc == 'en_US' else f"Parte A ({part_a_name})"
                is_curr_a = bool(obj and obj.name == part_a_name)
                op_a = row_parts.operator(
                    "chest.splitter_set_target",
                    text=lbl_pa,
                    icon='CHECKMARK' if is_curr_a else 'BLANK1',
                    depress=is_curr_a
                )
                op_a.object_name = part_a_name
            if has_part_b:
                lbl_pb = f"Part B ({part_b_name})" if loc == 'en_US' else f"Parte B ({part_b_name})"
                is_curr_b = bool(obj and obj.name == part_b_name)
                op_b = row_parts.operator(
                    "chest.splitter_set_target",
                    text=lbl_pb,
                    icon='CHECKMARK' if is_curr_b else 'BLANK1',
                    depress=is_curr_b
                )
                op_b.object_name = part_b_name

        if obj:
            row_target_info = box_target.row(align=True)
            lbl_target = "Target" if loc == 'en_US' else "Alvo"
            row_target_info.label(text=f"{lbl_target}: {obj.name}", icon='CHECKMARK')
            row_target_info.operator("chest.splitter_edit_target", text=localize_text("Editar Alvo"), icon='EDITMODE_HLT')
            row_target_info.operator("chest.splitter_clear_target", text=localize_text(""), icon='X')

            # Métricas físicas e topológicas
            col_metrics = box_target.column(align=True)
            dims = settings.diag_dims_mm
            lbl_dims = "Dimensions" if loc == 'en_US' else "Dimensões"
            col_metrics.label(
                text=f"{lbl_dims}: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm",
                icon='CON_SIZELIMIT'
            )
            if loc == 'en_US':
                lbl_mesh = f"Mesh: {settings.diag_triangles:,} triangles ({settings.diag_faces:,} faces)"
            else:
                lbl_mesh = f"Malha: {settings.diag_triangles:,} triângulos ({settings.diag_faces:,} faces)"
            col_metrics.label(
                text=lbl_mesh,
                icon='MESH_DATA'
            )
            col_metrics.label(
                text=f"Volume: {settings.diag_volume_mm3:,.1f} mm³",
                icon='MOD_FLUIDSIM'
            )

            # Avisos preventivos
            if settings.diag_has_unapplied_scale:
                box_warn = box_target.box()
                box_warn.alert = True
                box_warn.label(text=localize_text("Aviso: Escala não aplicada!"), icon='ERROR')
                box_warn.label(text=localize_text("Cortes e folgas podem ser distorcidos."))
                box_warn.operator(
                    "chest.splitter_create_work_copy",
                    text=localize_text("Criar cópia com escala aplicada"),
                    icon='DUPLICATE'
                )

            if not settings.diag_is_manifold:
                box_mani = box_target.box()
                box_mani.alert = True
                lbl_mani = (
                    f"Warning: {settings.diag_non_manifold_edges} open/non-manifold edge(s)."
                    if loc == 'en_US'
                    else f"Aviso: {settings.diag_non_manifold_edges} aresta(s) abertas/não-manifold."
                )
                box_mani.label(
                    text=lbl_mani,
                    icon='ERROR'
                )

            if settings.diag_degenerate_faces > 0:
                lbl_deg = (
                    f"{settings.diag_degenerate_faces} degenerate face(s) detected."
                    if loc == 'en_US'
                    else f"{settings.diag_degenerate_faces} face(s) degeneradas detectadas."
                )
                box_target.label(
                    text=lbl_deg,
                    icon='INFO'
                )
        else:
            box_target.label(text=localize_text("Nenhum alvo selecionado. Selecione um objeto malha."), icon='INFO')

        layout.separator()

        # --- SEÇÃO 2: MÉTODO DE CORTE ---
        box_split = layout.box()
        box_split.label(text=localize_text("2. Método de Corte"), icon='MOD_BOOLEAN')

        col_mode = box_split.column()
        col_mode.prop(settings, "split_mode", expand=True)

        if not obj:
            box_split.label(text=localize_text("Defina um objeto alvo primeiro."), icon='INFO')
        elif settings.split_mode == 'PLANE':
            # --- Guia de Corte e Alinhamentos ---
            box_guide = box_split.box()
            row_guide_head = box_guide.row(align=True)
            row_guide_head.label(text=localize_text("Posicionamento do Plano"), icon='ORIENTATION_LOCAL')
            draw_help_button(row_guide_head, "split_plane")

            row_guide_btn = box_guide.row(align=True)
            row_guide_btn.operator("chest.splitter_create_or_focus_guide", text=localize_text("Focar Guia 3D"), icon='GIZMO')

            box_guide.label(text=localize_text("Alinhamentos Rápidos:"))
            row_align_view = box_guide.row(align=True)
            op_v = row_align_view.operator("chest.splitter_align_plane", text=localize_text("Vista"), icon='VIEW_CAMERA')
            op_v.align_mode = 'VIEW'
            op_c = row_align_view.operator("chest.splitter_align_plane", text=localize_text("Cursor"), icon='PIVOT_CURSOR')
            op_c.align_mode = 'CURSOR'
            op_f = row_align_view.operator("chest.splitter_align_plane", text=localize_text("Face"), icon='FACESEL')
            op_f.align_mode = 'FACE'

            row_align_axes = box_guide.row(align=True)
            op_x = row_align_axes.operator("chest.splitter_align_plane", text=localize_text("Eixo X"))
            op_x.align_mode = 'X'
            op_y = row_align_axes.operator("chest.splitter_align_plane", text=localize_text("Eixo Y"))
            op_y.align_mode = 'Y'
            op_z = row_align_axes.operator("chest.splitter_align_plane", text=localize_text("Eixo Z"))
            op_z.align_mode = 'Z'

            # Visualização do Plano (F02)
            col_plane_vis = box_guide.column(align=True)
            row_pvis = col_plane_vis.row(align=True)
            row_pvis.prop(settings, "show_plane_preview", text=localize_text("Mostrar Plano"))
            row_pvis.prop(settings, "show_plane_cut_line", text=localize_text("Linha de Corte"))
            if settings.show_plane_preview:
                col_plane_vis.prop(settings, "plane_preview_opacity", text=localize_text("Opacidade (%)"), slider=True)
            col_plane_vis.prop(settings, "plane_offset_mm", text=localize_text("Deslocamento (mm)"))

        elif settings.split_mode == 'LOOP':
            box_loop = box_split.box()
            row_loop_head = box_loop.row(align=True)
            row_loop_head.label(text=localize_text("Corte por Contorno (Loop)"), icon='MOD_EDGESPLIT')
            draw_help_button(row_loop_head, "split_loop")

            row_cap = box_loop.row(align=True)
            row_cap.scale_y = 1.2
            row_cap.operator("chest.splitter_capture_loop", text=localize_text("Capturar Contorno"), icon='VIEW_ORTHO')
            row_cap.operator("chest.splitter_capture_face_boundary", text=localize_text("Capturar das Faces"), icon='FACESEL')

            if settings.loop_is_captured:
                lbl_loop_vc = (
                    f"Boundary vertices: {settings.loop_vertex_count}"
                    if loc == 'en_US'
                    else f"Vértices no contorno: {settings.loop_vertex_count}"
                )
                box_loop.label(text=lbl_loop_vc, icon='VERTEXSEL')
                if settings.loop_is_planar:
                    lbl_planar = (
                        f"Status: Planar ({settings.loop_planarity_deviation_mm:.2f}mm dev)"
                        if loc == 'en_US'
                        else f"Status: Planar ({settings.loop_planarity_deviation_mm:.2f}mm desvio)"
                    )
                    box_loop.label(text=lbl_planar, icon='CHECKMARK')
                else:
                    lbl_non_planar = (
                        f"Warning: Non-planar ({settings.loop_planarity_deviation_mm:.2f}mm dev)"
                        if loc == 'en_US'
                        else f"Aviso: Não-planar ({settings.loop_planarity_deviation_mm:.2f}mm desvio)"
                    )
                    box_loop.label(text=lbl_non_planar, icon='ERROR')
                
                box_loop.prop(
                    settings, 
                    "show_loop_highlight", 
                    text=localize_text("Destacar Contorno no Viewport"), 
                    icon='RESTRICT_VIEW_OFF' if settings.show_loop_highlight else 'RESTRICT_VIEW_ON'
                )

            row_seed = box_loop.row(align=True)
            row_seed.scale_y = 1.2
            row_seed.operator("chest.splitter_define_seed_face", text=localize_text("Escolher Região"), icon='FACESEL')
            draw_help_button(row_seed, "loop_region")

            col_seed_hint = box_loop.column()
            col_seed_hint.scale_y = 0.8
            col_seed_hint.label(text=localize_text("Dica: Selecione apenas 1 face dentro da região desejada."), icon='INFO')

            if settings.loop_seed_face_index >= 0:
                lbl_seed = (
                    f"Reference Region: Face #{settings.loop_seed_face_index}"
                    if loc == 'en_US'
                    else f"Região de Referência: Face #{settings.loop_seed_face_index}"
                )
                box_loop.label(text=lbl_seed, icon='CHECKMARK')

            # --- TIPO DE CORTE (PELA BASE vs POR PROFUNDIDADE) ---
            box_behavior = box_loop.box()
            row_bh_title = box_behavior.row(align=True)
            row_bh_title.label(text=localize_text("Tipo de Corte:"), icon='MOD_SOLIDIFY')
            draw_help_button(row_bh_title, "loop_extrude")

            row_mode = box_behavior.row(align=True)
            row_mode.scale_y = 1.3
            row_mode.prop(settings, "loop_behavior", expand=True)

            if settings.loop_behavior == 'AUTO':
                box_dec = box_behavior.box()
                lbl_mode = localize_text("Pela Base") if settings.loop_detected_mode == 'DETACH' else localize_text("Profundidade")
                icon_mode = 'SNAP_FACE' if settings.loop_detected_mode == 'DETACH' else 'CON_SIZELIMIT'
                lbl_auto = f"Auto Detected: {lbl_mode}" if loc == 'en_US' else f"Auto Detectado: {lbl_mode}"
                box_dec.label(text=lbl_auto, icon=icon_mode)
                if settings.loop_auto_reason:
                    col_r = box_dec.column()
                    col_r.scale_y = 0.8
                    col_r.label(text=localize_text(settings.loop_auto_reason))

            show_depth = (settings.loop_behavior == 'EXTRUDE') or (
                settings.loop_behavior == 'AUTO' and settings.loop_detected_mode == 'EXTRUDE'
            )
            if show_depth:
                box_depth = box_behavior.box()
                row_depth_head = box_depth.row(align=True)
                row_depth_head.label(text=localize_text("Parâmetros de Profundidade:"), icon='CON_SIZELIMIT')
                box_depth.prop(settings, "loop_extrude_depth_mm", text=localize_text("Profundidade (mm)"))
                box_depth.prop(settings, "loop_through_cut", text=localize_text("Corte Passante"))

            show_detach_base = (settings.loop_behavior == 'DETACH') or (
                settings.loop_behavior == 'AUTO' and settings.loop_detected_mode == 'DETACH'
            )
            if show_detach_base:
                box_base = box_behavior.box()
                row_base_head = box_base.row(align=True)
                row_base_head.label(text=localize_text("Parâmetros do Corte pela Base:"), icon='SNAP_FACE')
                box_base.prop(settings, "loop_detach_add_base", text=localize_text("Adicionar base para encaixe"))
                if settings.loop_detach_add_base:
                    box_base.prop(settings, "loop_detach_base_depth_mm", text=localize_text("Profundidade da base (mm)"))
                    box_base.prop(settings, "loop_detach_base_clearance_mm", text=localize_text("Folga lateral (mm)"))

            if settings.loop_is_captured and settings.loop_is_planar:
                row_solid_loop = box_loop.row(align=True)
                row_solid_loop.operator("chest.splitter_create_cutter_from_selection", text=localize_text("Criar Cortador desta Seleção"), icon='MOD_SOLIDIFY')


        elif settings.split_mode == 'SOLID':
            box_solid = box_split.box()
            box_solid.label(text=localize_text("Configuração do Cortador Sólido"), icon='MESH_UVSPHERE')

            col_src = box_solid.column(align=True)
            col_src.prop(settings, "solid_source", expand=True)

            if settings.solid_source == 'PRIMITIVE':
                col_prim = box_solid.column(align=True)
                col_prim.prop(settings, "solid_primitive_type", text=localize_text("Formato"))
                row_prim_btn = box_solid.row(align=True)
                row_prim_btn.scale_y = 1.1
                row_prim_btn.operator("chest.splitter_create_solid_cutter", text=localize_text("Criar"), icon='ADD')
                row_prim_btn.operator("chest.splitter_focus_solid_cutter", text=localize_text("Focar"), icon='VIEW_ZOOM')
                row_prim_btn.operator("chest.splitter_reset_solid_cutter", text=localize_text("Reiniciar"), icon='FILE_REFRESH')
            else:
                col_exist = box_solid.column(align=True)
                col_exist.prop(settings, "solid_cutter_object", text=localize_text("Cortador"))
                row_pick = box_solid.row(align=True)
                row_pick.operator("chest.splitter_select_existing_cutter", text=localize_text("Usar Selecionado"), icon='EYEDROPPER')
                row_pick.operator("chest.splitter_copy_selected_as_cutter", text=localize_text("Copiar Selecionado"), icon='DUPLICATE')

            # Gerar Cortador da Malha (Faces / Quinas / Contorno)
            box_gen = box_solid.box()
            row_gen_head = box_gen.row(align=True)
            row_gen_head.label(text=localize_text("Gerar Cortador da Malha:"), icon='MOD_SOLIDIFY')
            row_gen_head.operator("chest.splitter_edit_target", text=localize_text("Editar Alvo"), icon='EDITMODE_HLT')

            row_gen_btns = box_gen.row(align=True)
            row_gen_btns.operator("chest.splitter_create_cutter_from_selection", text=localize_text("Desta Seleção"), icon='MOD_SOLIDIFY')
            row_gen_btns.operator("chest.splitter_create_corner_box_cutter", text=localize_text("Caixa para Quina"), icon='MESH_CUBE')

            # Ações e Alinhamento do Cortador
            cutter = settings.solid_cutter_object
            from .scene_state import object_in_scene
            if object_in_scene(cutter, context.scene, mesh=True):
                row_actions = box_solid.row(align=True)
                row_actions.operator("chest.splitter_duplicate_solid_cutter", text=localize_text("Duplicar Cortador"), icon='DUPLICATE')
                op_align = row_actions.operator("chest.splitter_align_solid_cutter", text=localize_text("Alinhar à Face"), icon='SNAP_FACE')
                op_align.align_mode = 'ACTIVE_FACE'
                op_align.anchor = 'SUPPORT_FACE'

                # Alinhamento por Vértices
                box_solid.operator("chest.splitter_align_solid_vertices", text=localize_text("Alinhar por Vértices"), icon='SNAP_VERTEX')

                # Dimensões físicas locais (mm)
                box_dims = box_solid.box()
                box_dims.label(text=localize_text("Dimensões Físicas Locais (mm):"), icon='CON_SIZELIMIT')
                col_dims = box_dims.column(align=True)
                col_dims.prop(settings, "solid_cutter_width_mm")
                col_dims.prop(settings, "solid_cutter_height_mm")
                col_dims.prop(settings, "solid_cutter_depth_mm")

                # Diagnóstico do Cortador Selecionado
                box_cutter_diag = box_solid.box()
                lbl_cutter_name = f"Cutter: '{cutter.name}'" if loc == 'en_US' else f"Cortador: '{cutter.name}'"
                box_cutter_diag.label(text=lbl_cutter_name, icon='OUTLINER_OB_MESH')
                if settings.solid_cutter_is_manifold:
                    lbl_cutter_mani = (
                        f"Status: Closed / 100% Manifold ({settings.solid_cutter_triangles:,} tris)"
                        if loc == 'en_US'
                        else f"Status: Fechado / 100% Manifold ({settings.solid_cutter_triangles:,} tris)"
                    )
                    box_cutter_diag.label(text=lbl_cutter_mani, icon='CHECKMARK')
                    box_cutter_diag.label(text=f"Volume: {settings.solid_cutter_volume_mm3:,.1f} mm³")
                else:
                    box_cutter_warn = box_cutter_diag.box()
                    box_cutter_warn.alert = True
                    lbl_cutter_err = (
                        f"Error: {settings.solid_cutter_non_manifold_edges} open edge(s)!"
                        if loc == 'en_US'
                        else f"Erro: {settings.solid_cutter_non_manifold_edges} aresta(s) abertas!"
                    )
                    box_cutter_warn.label(text=lbl_cutter_err, icon='ERROR')
                    box_cutter_warn.label(text=localize_text("Cortador precisa ser um sólido 3D estanque."))


        elif settings.split_mode == 'MATERIAL':
            box_mat = box_split.box()
            row_mat_head = box_mat.row(align=True)
            row_mat_head.label(text=localize_text("Divisão por Material (Fase 4)"), icon='MATERIAL')
            draw_help_button(row_mat_head, "split_material")

            mats = obj.data.materials if (obj and obj.data) else []
            if not mats:
                box_mat.label(text=localize_text("O modelo não possui materiais atribuídos."), icon='ERROR')
                box_mat.label(text=localize_text("Adicione slots de materiais na aba Material."))
            else:
                col_mat_list = box_mat.column(align=True)
                col_mat_list.label(text=localize_text("Escolha a cor/área a extrair (Parte A):"))
                for idx, m in enumerate(mats):
                    mat_name = m.name if m else f"Material #{idx}"
                    is_active = (settings.material_split_index == idx)
                    icon_btn = 'CHECKBOX_HLT' if is_active else 'CHECKBOX_DEHLT'
                    row_m = col_mat_list.row(align=True)
                    op_sel = row_m.operator("chest.splitter_select_split_material", text=f"{idx}: {mat_name}", icon=icon_btn)
                    op_sel.material_index = idx
                    op_sel.region_index = 0

                # Atalho: escolher pela face selecionada no Modo de Edição
                row_pick = box_mat.row(align=True)
                row_pick.operator("chest.splitter_pick_material_region", text=localize_text("Usar Face Selecionada (Edit Mode)"), icon='RESTRICT_SELECT_OFF')

                # Diagnóstico dinâmico do material selecionado com cache (COM-07)
                mat_idx = min(settings.material_split_index, len(mats) - 1)
                regions, analysis = get_cached_material_ui_analysis(obj, mat_idx, settings.material_region_index)
                if len(regions) > 1:
                    box_reg = box_mat.box()
                    lbl_color_areas = (
                        f"This color appears in {len(regions)} separate areas:"
                        if loc == 'en_US'
                        else f"Esta cor aparece em {len(regions)} áreas separadas:"
                    )
                    box_reg.label(text=lbl_color_areas, icon='STICKY_UVS_DISABLE')
                    col_reg = box_reg.column(align=True)
                    for r in regions:
                        is_r = (settings.material_region_index == r["index"])
                        area_word = "Area" if loc == 'en_US' else "Área"
                        faces_word = "faces" if loc == 'en_US' else "faces"
                        op_r = col_reg.operator(
                            "chest.splitter_select_split_material",
                            text=f"{area_word} {r['index'] + 1} ({r['face_count']} {faces_word})",
                            icon='RADIOBUT_ON' if is_r else 'RADIOBUT_OFF',
                        )
                        op_r.material_index = mat_idx
                        op_r.region_index = r["index"]

                box_diag_mat = box_mat.box()
                if analysis.get("valid"):
                    mat_type = analysis.get("type")
                    if mat_type == "CLOSED_COMPONENT":
                        box_diag_mat.label(text=localize_text("Tipo: Componente 3D Fechado (Sólido)"), icon='CHECKMARK')
                        lbl_mat_closed = (
                            f"Faces: {analysis['face_count']:,} | Water-tight mesh for slicer."
                            if loc == 'en_US'
                            else f"Faces: {analysis['face_count']:,} | Malha estanque para fatiador."
                        )
                        box_diag_mat.label(text=lbl_mat_closed)
                    else:
                        box_diag_mat.label(text=localize_text("Tipo: Região Superficial (Com Profundidade)"), icon='INFO')
                        lbl_mat_surf = (
                            f"Faces: {analysis['face_count']:,} | Continuous boundary."
                            if loc == 'en_US'
                            else f"Faces: {analysis['face_count']:,} | Fronteira contínua."
                        )
                        box_diag_mat.label(text=lbl_mat_surf)
                        box_mat_depth = box_mat.box()
                        row_md_head = box_mat_depth.row(align=True)
                        row_md_head.label(text=localize_text("Tipo de Corte da Região:"), icon='MOD_SOLIDIFY')

                        row_m_mode = box_mat_depth.row(align=True)
                        row_m_mode.scale_y = 1.3
                        row_m_mode.prop(settings, "material_extraction_mode", expand=True)

                        if settings.material_extraction_mode == 'EXTRUDE':
                            box_mat_depth.prop(settings, "material_extrude_depth_mm", text=localize_text("Profundidade (mm)"))
                        box_mat_depth.prop(settings, "material_interface_mat_mode", text=localize_text("Material da Interface"))
                else:
                    box_diag_mat.alert = True
                    warn_prefix = "Warning:" if loc == 'en_US' else "Aviso:"
                    box_diag_mat.label(text=f"{warn_prefix} {localize_text(analysis.get('error', 'Estrutura inválida'))}", icon='ERROR')

                row_sol_tools = box_mat.row(align=True)
                row_sol_tools.operator("chest.splitter_create_cutter_from_selection", text=localize_text("Criar Cortador Desta Seleção"), icon='MOD_SOLIDIFY')
                row_sol_tools.operator("chest.splitter_create_corner_box_cutter", text=localize_text("Caixa para Quina"), icon='MESH_CUBE')


        layout.separator()

        # --- SEÇÃO 3: ENCAIXES E FOLGAS (Antes da Prévia!) ---
        box_conn = layout.box()
        row_conn_head = box_conn.row(align=True)
        if settings.split_mode == 'SOLID':
            row_conn_head.label(text=localize_text("3. Folga da Interface"), icon='DRIVER_DISTANCE')
            draw_help_button(row_conn_head, "clearance")
        else:
            row_conn_head.label(text=localize_text("3. Encaixes & Folgas"), icon='SNAP_VERTEX')
            draw_help_button(row_conn_head, "connectors")

        # Folga Física entre Peças (E01)
        box_part_clearance = box_conn.box()
        box_part_clearance.label(text=localize_text("Folga da Interface entre Peças:"), icon='DRIVER_DISTANCE')
        if settings.split_mode in ('PLANE', 'MATERIAL', 'SOLID'):
            box_part_clearance.prop(settings, "part_clearance_mm", text=localize_text("Folga (mm)"), slider=True)
            if settings.part_clearance_mm > 0.0:
                box_part_clearance.prop(settings, "part_clearance_apply_to", text=localize_text("Aplicar em"))
            if settings.split_mode == 'MATERIAL':
                box_part_clearance.prop(settings, "part_clearance_bottom_enable", text=localize_text("Folga de fundo separada"))
                if settings.part_clearance_bottom_enable:
                    box_part_clearance.prop(settings, "part_clearance_bottom_mm", text=localize_text("Folga de fundo (mm)"))
        else:
            col_disabled = box_part_clearance.column()
            col_disabled.enabled = False
            col_disabled.prop(settings, "part_clearance_mm", text=localize_text("Folga (mm)"), slider=True)
            box_part_clearance.label(
                text=localize_text("Folga de interface disponível apenas nos modos Plano e Material."), 
                icon='INFO'
            )

        if settings.split_mode != 'SOLID':
            row_enable = box_conn.row(align=True)
            row_enable.prop(settings, "connector_enabled", text=localize_text("Ativar Encaixes"), toggle=True, icon='CHECKBOX_HLT' if settings.connector_enabled else 'CHECKBOX_DEHLT')

        if settings.split_mode != 'SOLID' and settings.connector_enabled:
            # Formato do Encaixe
            col_shape = box_conn.column(align=True)
            col_shape.label(text=localize_text("Formato do Encaixe:"))
            col_shape.prop(settings, "connector_type", expand=True)

            # Lado do Macho / Fêmea
            box_male = box_conn.box()
            box_male.label(text=localize_text("Posição dos Pinos (Macho):"), icon='SNAP_NORMAL')

            top_part = 'A' if settings.part_a_is_superior else 'B'
            is_top = (settings.connector_male_part == top_part)
            if loc == 'en_US':
                cur_desc = "Upper Part" if is_top else "Lower Part"
                btn_inv_text = f"Invert: Pins on {cur_desc}"
            else:
                cur_desc = "Parte Superior" if is_top else "Parte Inferior"
                btn_inv_text = f"Inverter: Pinos na {cur_desc}"

            row_male_pick = box_male.row(align=True)
            row_male_pick.prop(settings, "connector_male_part", expand=True)

            row_male_btn = box_male.row(align=True)
            row_male_btn.scale_y = 1.2
            row_male_btn.operator(
                "chest.splitter_invert_male_female",
                text=btn_inv_text,
                icon='ARROW_LEFTRIGHT'
            )

            # Dimensões Nominais do Macho
            box_dims = box_conn.box()
            box_dims.label(text=localize_text("Dimensões Nominais:"), icon='CON_SIZELIMIT')
            if settings.connector_type == 'CAPSULE':
                box_dims.prop(settings, "connector_diameter_mm", text=localize_text("Espessura / Diâmetro (mm)"), slider=True)
                box_dims.prop(settings, "connector_capsule_length_mm", text=localize_text("Comprimento Lateral (mm)"), slider=True)
                if settings.connector_max_safe_lateral_mm > 0:
                    lbl_safe_lim = (
                        f"Max Safe Limit: {settings.connector_max_safe_lateral_mm:.1f} mm (anti-collision)"
                        if loc == 'en_US'
                        else f"Limite Seguro Máx: {settings.connector_max_safe_lateral_mm:.1f} mm (anti-colisão)"
                    )
                    box_dims.label(
                        text=lbl_safe_lim,
                        icon='INFO',
                    )
            else:
                box_dims.prop(settings, "connector_diameter_mm", slider=True)
            box_dims.prop(settings, "connector_length_mm", text=localize_text("Profundidade de Inserção (mm)"), slider=True)
            box_dims.prop(settings, "connector_chamfer_mm", slider=True)

            # Folgas de Encaixe Físico
            box_clear = box_conn.box()
            row_clear_head = box_clear.row(align=True)
            row_clear_head.label(text=localize_text("Folgas Físicas de Montagem (FDM):"), icon='DRIVER')
            draw_help_button(row_clear_head, "clearance")

            # Botões rápidos de preset
            row_presets = box_clear.row(align=True)
            row_presets.label(text=localize_text("Presets:"))
            for p_code, p_lbl in [('TIGHT', "0.10"), ('NORMAL', "0.15"), ('EASY', "0.20"), ('LOOSE', "0.25")]:
                op_p = row_presets.operator("chest.splitter_apply_connector_preset", text=p_lbl)
                op_p.preset = p_code

            box_clear.prop(settings, "clearance_per_side_mm", slider=True)
            lbl_diam_clear = (
                f"Total diameter clearance: {settings.clearance_per_side_mm * 2:.2f} mm"
                if loc == 'en_US'
                else f"Folga total no diâmetro: {settings.clearance_per_side_mm * 2:.2f} mm"
            )
            box_clear.label(text=lbl_diam_clear, icon='INFO')
            box_clear.prop(settings, "end_clearance_mm", slider=True)

            # Distribuição
            box_dist = box_conn.box()
            box_dist.label(text=localize_text("Distribuição no Corte:"), icon='PARTICLE_DATA')
            box_dist.prop(settings, "connector_distribution", expand=True)
            box_dist.prop(settings, "connector_edge_margin_mm", slider=True)
            box_dist.prop(settings, "adjust_to_valid_area")

            if settings.connector_distribution == 'MANUAL':
                box_manual = box_conn.box()
                row_man_head = box_manual.row(align=True)
                row_man_head.label(text=localize_text("Posicionamento Manual:"), icon='RESTRICT_SELECT_OFF')

                from .connector_editor import get_editor_interaction_state
                ed_state = get_editor_interaction_state()
                is_editing = settings.is_editing_connectors and ed_state.get("is_active", False)

                if is_editing:
                    box_active = box_manual.box()
                    box_active.label(text=localize_text("Modo de Edição 3D Ativo"), icon='EDITMODE_HLT')
                    row_confirm = box_active.row(align=True)
                    row_confirm.scale_y = 1.35
                    row_confirm.operator(
                        "chest.splitter_confirm_manual_connectors",
                        text=localize_text("Confirmar Posições e Gerar Prévia"),
                        icon='CHECKMARK'
                    )
                    row_exit = box_active.row(align=True)
                    row_exit.operator(
                        "chest.splitter_finish_manual_connectors",
                        text=localize_text("Concluir Edição"),
                        icon='FILE_TICK'
                    )
                    row_exit.operator(
                        "chest.splitter_cancel_manual_connectors",
                        text=localize_text("Cancelar"),
                        icon='CANCEL'
                    )
                else:
                    has_preview = (settings.session_status in ('PREVIEW_VALID', 'PREVIEW_STALE'))
                    lbl_edit = localize_text("Editar Posições Novamente") if has_preview else localize_text("Editar Posições dos Pinos")
                    row_click = box_manual.row(align=True)
                    row_click.scale_y = 1.35
                    row_click.operator(
                        "chest.splitter_edit_manual_connectors",
                        text=lbl_edit,
                        icon='EDITMODE_HLT'
                    )

                row_view = box_manual.row(align=True)
                row_view.operator("chest.splitter_view_cut_face", text=localize_text("Alinhar Vista ao Corte (V)"), icon='VIEW_CAMERA')
                op_flip = row_view.operator("chest.splitter_view_cut_face", text=localize_text("Inverter Lado"), icon='ARROW_LEFTRIGHT')
                op_flip.flip_direction = True

                if is_editing:
                    box_mode = box_manual.box()
                    row_mode_head = box_mode.row(align=True)
                    row_mode_head.label(text=localize_text("Ação do Clique 3D no Modelo:"), icon='CURSOR')
                    row_sub = box_mode.row(align=True)
                    row_sub.prop(settings, "manual_editor_submode", expand=True)

                n_manual = len(settings.manual_connectors)
                row_actions = box_manual.row(align=True)
                row_actions.operator("chest.splitter_add_manual_connector", text=localize_text("Adicionar"), icon='ADD')
                row_rem = row_actions.row(align=True)
                row_rem.enabled = (n_manual > 0)
                row_rem.operator("chest.splitter_remove_manual_connector", text=localize_text("Remover"), icon='REMOVE')
                row_clr = row_actions.row(align=True)
                row_clr.enabled = (n_manual > 0)
                row_clr.operator("chest.splitter_clear_manual_connectors", text=localize_text("Limpar"), icon='TRASH')

                if n_manual == 0:
                    box_manual.label(text=localize_text("Nenhum pino posicionado. Clique em 'Editar Posições' para adicionar."), icon='INFO')
                else:
                    lbl_tot_pins = f"Total Pins: {n_manual}" if loc == 'en_US' else f"Total de Pinos: {n_manual}"
                    box_manual.label(text=lbl_tot_pins, icon='LAYER_ACTIVE')
                    box_edit = box_manual.box()
                    idx = settings.manual_connector_index
                    if 0 <= idx < n_manual:
                        active_conn = settings.manual_connectors[idx]
                        row_sel = box_edit.row(align=True)
                        lbl_pin_num = f"Pin #{idx + 1}" if loc == 'en_US' else f"Pino #{idx + 1}"
                        row_sel.prop(settings, "manual_connector_index", text=lbl_pin_num)
                        row_sel.operator("chest.splitter_remove_manual_connector", text=localize_text(""), icon='X')

                        row_coords = box_edit.row(align=True)
                        row_coords.prop(active_conn, "u_mm", text=localize_text("U (mm)"))
                        row_coords.prop(active_conn, "v_mm", text=localize_text("V (mm)"))
                        if settings.connector_type == 'CAPSULE':
                            box_edit.prop(active_conn, "yaw_deg", text=localize_text("Rotação Yaw (°)"), slider=True)

                        if not getattr(active_conn, "is_valid", True):
                            row_err = box_edit.row(align=True)
                            row_err.alert = True
                            reason = getattr(active_conn, "status_reason", "") or getattr(active_conn, "validation_msg", "") or "Posição fora do domínio / margem violada"
                            row_err.label(
                                text=localize_text(reason),
                                icon='CANCEL'
                            )
                        else:
                            box_edit.label(text=localize_text("Posição Válida"), icon='CHECKMARK')
                    else:
                        box_edit.prop(settings, "manual_connector_index", text=localize_text("Pino Ativo"))
            else:
                box_dist.operator(
                    "chest.splitter_convert_pattern_to_manual",
                    text=localize_text("Converter Padrão para Manual"),
                    icon='GREASEPENCIL'
                )
        layout.separator()

        # --- SEÇÃO 4: PRÉVIA E VISUALIZAÇÃO ---
        if obj and settings.split_mode in ('PLANE', 'SOLID', 'LOOP', 'MATERIAL'):
            box_preview = layout.box()
            box_preview.label(text=localize_text("4. Prévia do Corte"), icon='RESTRICT_VIEW_OFF')

            # Alerta de preview desatualizado (Critério U2)
            if settings.session_status == 'PREVIEW_STALE':
                box_stale = box_preview.box()
                box_stale.alert = True
                box_stale.label(
                    text=localize_text("Os ajustes mudaram. Atualize a prévia antes de criar as peças."),
                    icon='ERROR'
                )

            row_preview = box_preview.row(align=True)
            row_preview.scale_y = 1.3
            row_preview.operator("chest.splitter_generate_preview", text=localize_text("Gerar / Atualizar Prévia"), icon='PLAY')
            row_preview.operator("chest.splitter_remove_preview", text=localize_text("Remover Prévia"), icon='X')

            if settings.split_mode != 'SOLID' and settings.connector_enabled and settings.connector_distribution == 'MANUAL':
                row_reedit = box_preview.row(align=True)
                from .connector_editor import get_editor_interaction_state
                is_ed_active = settings.is_editing_connectors and get_editor_interaction_state().get("is_active", False)
                if not is_ed_active:
                    row_reedit.operator(
                        "chest.splitter_edit_manual_connectors",
                        text=localize_text("Editar Posições Novamente"),
                        icon='EDITMODE_HLT'
                    )
                else:
                    row_reedit.operator(
                        "chest.splitter_confirm_manual_connectors",
                        text=localize_text("Confirmar Posições dos Pinos"),
                        icon='CHECKMARK'
                    )

            if settings.split_mode in ('PLANE', 'SOLID'):
                row_inv = box_preview.row(align=True)
                if settings.split_mode == 'SOLID':
                    lbl_inv = localize_text("Inverter: A=Ext / B=Int") if settings.invert_sides else localize_text("Inverter: A=Int / B=Ext")
                else:
                    lbl_inv = localize_text("Inverter Lados (Ativo)") if settings.invert_sides else localize_text("Inverter Lados A / B")
                row_inv.operator("chest.splitter_invert_sides", text=lbl_inv, icon='ARROW_LEFTRIGHT')

            # Visualização Montada / Explodida e Cores
            if settings.session_status in ('PREVIEW_VALID', 'PREVIEW_STALE', 'COMMITTED'):
                box_view = box_preview.box()
                row_view_head = box_view.row(align=True)
                row_view_head.label(text=localize_text("Visualização & Cores:"), icon='VIEW3D')
                draw_help_button(row_view_head, "explosion")

                box_view.prop(settings, "view_mode", expand=True)

                if settings.view_mode == 'EXPLODED':
                    box_view.prop(settings, "explosion_distance_mm", slider=True)
                    box_view.prop(settings, "invert_explosion", toggle=True, icon='ARROW_LEFTRIGHT')

                box_view.prop(settings, "preview_color_mode", text=localize_text(""))

                # Diagnósticos de Partes A e B
                box_diag_parts = box_preview.box()
                box_diag_parts.label(text=localize_text("Resultados do Corte"), icon='CHECKMARK')

                lbl_tag_a = (" (Upper)" if loc == 'en_US' else " (Superior)") if settings.part_a_is_superior else (" (Lower)" if loc == 'en_US' else " (Inferior)")
                lbl_tag_b = (" (Lower)" if loc == 'en_US' else " (Inferior)") if settings.part_a_is_superior else (" (Upper)" if loc == 'en_US' else " (Superior)")

                part_word = "Part" if loc == 'en_US' else "Parte"
                dim_word = "Dimensions" if loc == 'en_US' else "Dimensões"
                island_word = "island(s)" if loc == 'en_US' else "ilha(s)"
                open_edges_word = "open edges" if loc == 'en_US' else "aresta(s) abertas"
                warn_word = "Warning" if loc == 'en_US' else "Aviso"

                col_a = box_diag_parts.box()
                col_a.label(text=f"{part_word} A{lbl_tag_a}", icon='MESH_CUBE')
                col_a.label(text=f"Volume: {settings.part_a_volume_mm3:,.1f} mm³")
                dims_a = settings.part_a_dims_mm
                col_a.label(text=f"{dim_word}: {dims_a[0]:.1f} x {dims_a[1]:.1f} x {dims_a[2]:.1f} mm")
                col_a.label(text=f"Mesh: {settings.part_a_triangles:,} tris | {settings.part_a_components} {island_word}" if loc == 'en_US' else f"Malha: {settings.part_a_triangles:,} tris | {settings.part_a_components} {island_word}")
                if not settings.part_a_is_manifold:
                    col_a.label(text=f"{warn_word}: {settings.part_a_non_manifold_edges} {open_edges_word}", icon='ERROR')

                col_b = box_diag_parts.box()
                col_b.label(text=f"{part_word} B{lbl_tag_b}", icon='MESH_CUBE')
                col_b.label(text=f"Volume: {settings.part_b_volume_mm3:,.1f} mm³")
                dims_b = settings.part_b_dims_mm
                col_b.label(text=f"{dim_word}: {dims_b[0]:.1f} x {dims_b[1]:.1f} x {dims_b[2]:.1f} mm")
                col_b.label(text=f"Mesh: {settings.part_b_triangles:,} tris | {settings.part_b_components} {island_word}" if loc == 'en_US' else f"Malha: {settings.part_b_triangles:,} tris | {settings.part_b_components} {island_word}")
                if not settings.part_b_is_manifold:
                    col_b.label(text=f"{warn_word}: {settings.part_b_non_manifold_edges} {open_edges_word}", icon='ERROR')

                # Balanço de Volume
                box_vol = box_diag_parts.box()
                vol_ok = settings.volume_diff_pct < 0.5
                icon_vol = 'CHECKMARK' if vol_ok else 'ERROR'
                lbl_sum_vol = (
                    f"Total Volume: {settings.part_sum_volume_mm3:,.1f} mm³ (diff: {settings.volume_diff_pct:.2f}%)"
                    if loc == 'en_US'
                    else f"Soma Volumes: {settings.part_sum_volume_mm3:,.1f} mm³ (dif: {settings.volume_diff_pct:.2f}%)"
                )
                box_vol.label(
                    text=lbl_sum_vol,
                    icon=icon_vol
                )

                # Ação rápida de separação por material/cor
                row_sep = box_diag_parts.row()
                row_sep.operator("chest.splitter_separate_by_material", text=localize_text("Separar por Cores / Materiais"), icon='COLOR')

            layout.separator()

            # --- SEÇÃO 5: CRIAR PEÇAS (CONFIRMAÇÃO) ---
            box_commit = layout.box()
            box_commit.label(text=localize_text("5. Criar Peças"), icon='MOD_SOLIDIFY')

            if settings.session_status == 'PREVIEW_VALID':
                row_choice = box_commit.row(align=True)
                row_choice.prop(settings, "commit_next_target", text=localize_text("Próximo Alvo"))

                row_commit = box_commit.row()
                row_commit.scale_y = 1.4
                row_commit.operator("chest.splitter_commit_parts", text=localize_text("Confirmar Divisão"), icon='CHECKMARK')

                row_rest = box_commit.row()
                row_rest.operator("chest.splitter_remove_preview", text=localize_text("Remover Prévia"), icon='X')

            elif settings.session_status == 'PREVIEW_STALE':
                box_warn_commit = box_commit.box()
                box_warn_commit.label(text=localize_text("Atualize a prévia antes de confirmar as peças."), icon='INFO')
                row_rest = box_commit.row()
                row_rest.operator("chest.splitter_remove_preview", text=localize_text("Remover Prévia"), icon='X')

            elif settings.session_status == 'COMMITTED':
                box_commit.label(text=localize_text("Peças finais geradas na coleção CHEST_SPLITTER_PARTS."), icon='CHECKMARK')
                row_cont = box_commit.row()
                row_cont.scale_y = 1.3
                row_cont.operator("chest.splitter_continue_on_receiver", text=localize_text("Continuar no corpo remanescente"), icon='FORWARD')
                row_revert = box_commit.row()
                row_revert.scale_y = 1.1
                row_revert.operator("chest.splitter_revert_cut", text=localize_text("Reverter este corte"), icon='LOOP_BACK')
                box_commit.operator("chest.splitter_redo_session", text=localize_text("Refazer / Novo Corte"), icon='FILE_REFRESH')

            elif settings.session_status == 'CONFIGURED':
                if loc == 'en_US':
                    hint_text = "Position the cutter and click 'Generate / Update Preview'." if settings.split_mode == 'SOLID' else "Position the plane or boundary and click 'Generate / Update Preview'."
                else:
                    hint_text = "Posicione o cortador e clique em 'Gerar / Atualizar Prévia'." if settings.split_mode == 'SOLID' else "Posicione o plano ou contorno e clique em 'Gerar / Atualizar Prévia'."
                box_commit.label(text=hint_text, icon='INFO')
                has_ops = bool(getattr(scene, "chest_operations", None) and any(rec.status == 'COMMITTED' for rec in scene.chest_operations))
                if has_ops:
                    row_revert = box_commit.row()
                    row_revert.scale_y = 1.1
                    row_revert.operator("chest.splitter_revert_cut", text=localize_text("Reverter último corte"), icon='LOOP_BACK')

        # --- SEÇÃO 6: EXPORTAÇÃO PARA IMPRESSÃO 3D ---
        from .operators import get_current_session_parts
        export_parts_list = get_current_session_parts(scene)
        can_export = (settings.session_status == 'PREVIEW_VALID') or (len(export_parts_list) >= 2)
        if can_export:
            layout.separator()
            box_exp = layout.box()
            box_exp.label(text=localize_text("6. Exportação para Fatiador (Bambu / Orca / Prusa)"), icon='EXPORT')

            col_exp_cfg = box_exp.column(align=True)
            col_exp_cfg.prop(settings, "export_format")
            col_exp_cfg.prop(settings, "export_directory")

            row_exp_act = box_exp.row()
            row_exp_act.scale_y = 1.3
            row_exp_act.operator("chest.splitter_export_parts", text=localize_text("Exportar Peças (A e B)"), icon='EXPORT')

        # --- FEEDBACK DE STATUS ---
        status_text = settings.get_localized_status() if hasattr(settings, "get_localized_status") else settings.last_status
        if status_text:
            status_text = localize_text(status_text)
            layout.separator()
            box_status = layout.box()
            icon_status = 'INFO'
            if settings.last_status_level == 'SUCCESS':
                icon_status = 'CHECKMARK'
            elif settings.last_status_level == 'WARNING':
                icon_status = 'ERROR'
                box_status.alert = True
            elif settings.last_status_level == 'ERROR':
                icon_status = 'CANCEL'
                box_status.alert = True

            import textwrap
            paragraphs = status_text.split('\n')
            for p_idx, para in enumerate(paragraphs):
                lines = textwrap.wrap(para, width=44) or [para]
                for l_idx, line in enumerate(lines):
                    if p_idx == 0 and l_idx == 0:
                        box_status.label(text=line, icon=icon_status)
                    else:
                        box_status.label(text=line)



def register():
    try:
        bpy.utils.register_class(VIEW3D_PT_chest_part_splitter)
    except ValueError:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(VIEW3D_PT_chest_part_splitter)
    except RuntimeError:
        pass
