"""Interface de usuário para o Chest Part Splitter (Sidebar N > Chest > Part Splitter)."""

import bpy


class VIEW3D_PT_chest_part_splitter(bpy.types.Panel):
    """Painel principal do Chest Part Splitter na barra lateral da Viewport 3D"""
    bl_label = "Part Splitter"
    bl_idname = "VIEW3D_PT_chest_part_splitter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Chest'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.chest_splitter
        obj = settings.target_object

        # --- SEÇÃO 1: OBJETO ALVO ---
        box_target = layout.box()
        box_target.label(text="1. Objeto Alvo", icon='OBJECT_DATA')

        row_set = box_target.row(align=True)
        row_set.operator("chest.splitter_set_target", text="Usar selecionado como alvo", icon='EYEDROPPER')

        if obj:
            row_target_info = box_target.row(align=True)
            row_target_info.label(text=f"Alvo: {obj.name}", icon='CHECKMARK')
            row_target_info.operator("chest.splitter_clear_target", text="", icon='X')

            # Métricas físicas e topológicas
            col_metrics = box_target.column(align=True)
            dims = settings.diag_dims_mm
            col_metrics.label(
                text=f"Dimensões: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm",
                icon='CON_SIZELIMIT'
            )
            col_metrics.label(
                text=f"Malha: {settings.diag_triangles:,} triângulos ({settings.diag_faces:,} faces)",
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
                box_warn.label(text="Aviso: Escala não aplicada!", icon='ERROR')
                box_warn.label(text="Cortes e folgas podem ser distorcidos.")
                box_warn.operator(
                    "chest.splitter_create_work_copy",
                    text="Criar cópia com escala aplicada",
                    icon='DUPLICATE'
                )

            if not settings.diag_is_manifold:
                box_mani = box_target.box()
                box_mani.alert = True
                box_mani.label(
                    text=f"Aviso: {settings.diag_non_manifold_edges} aresta(s) abertas/não-manifold.",
                    icon='ERROR'
                )

            if settings.diag_degenerate_faces > 0:
                box_target.label(
                    text=f"{settings.diag_degenerate_faces} face(s) degeneradas detectadas.",
                    icon='INFO'
                )
        else:
            box_target.label(text="Nenhum alvo selecionado. Selecione um objeto malha.", icon='INFO')

        layout.separator()

        # --- SEÇÃO 2: DIVISÃO DE PARTES ---
        box_split = layout.box()
        box_split.label(text="2. Divisão de Partes", icon='MOD_BOOLEAN')

        col_mode = box_split.column()
        col_mode.prop(settings, "split_mode", expand=True)

        if settings.split_mode == 'PLANE':
            if obj:
                # --- Guia de Corte e Alinhamentos ---
                box_guide = box_split.box()
                box_guide.label(text="Posicionamento do Plano", icon='ORIENTATION_LOCAL')

                row_guide_btn = box_guide.row(align=True)
                row_guide_btn.operator("chest.splitter_create_or_focus_guide", text="Focar Guia 3D", icon='GIZMO')

                box_guide.label(text="Alinhamentos Rápidos:")
                row_align_view = box_guide.row(align=True)
                op_v = row_align_view.operator("chest.splitter_align_plane", text="Vista", icon='VIEW_CAMERA')
                op_v.align_mode = 'VIEW'
                op_c = row_align_view.operator("chest.splitter_align_plane", text="Cursor", icon='PIVOT_CURSOR')
                op_c.align_mode = 'CURSOR'
                op_f = row_align_view.operator("chest.splitter_align_plane", text="Face", icon='FACESEL')
                op_f.align_mode = 'FACE'

                row_align_axes = box_guide.row(align=True)
                op_x = row_align_axes.operator("chest.splitter_align_plane", text="Eixo X")
                op_x.align_mode = 'X'
                op_y = row_align_axes.operator("chest.splitter_align_plane", text="Eixo Y")
                op_y.align_mode = 'Y'
                op_z = row_align_axes.operator("chest.splitter_align_plane", text="Eixo Z")
                op_z.align_mode = 'Z'

                # --- Botões de Ação de Preview ---
                box_preview_act = box_split.box()
                row_preview = box_preview_act.row(align=True)
                row_preview.scale_y = 1.3
                row_preview.operator("chest.splitter_generate_preview", text="Gerar / Atualizar Preview", icon='PLAY')

                row_inv = box_preview_act.row(align=True)
                lbl_inv = "Inverter Lados (Ativo)" if settings.invert_sides else "Inverter Lados A / B"
                row_inv.operator("chest.splitter_invert_sides", text=lbl_inv, icon='ARROW_LEFTRIGHT')

                # --- Visualização Montada / Explodida ---
                if settings.session_status in ('PREVIEW_VALID', 'COMMITTED'):
                    box_view = box_split.box()
                    box_view.label(text="Modo de Visualização", icon='RESTRICT_VIEW_OFF')
                    box_view.prop(settings, "view_mode", expand=True)

                    if settings.view_mode == 'EXPLODED':
                        box_view.prop(settings, "explosion_distance_mm", slider=True)

                    # --- Diagnósticos de Partes A e B ---
                    box_diag_parts = box_split.box()
                    box_diag_parts.label(text="Resultados do Corte", icon='CHECKMARK')

                    col_a = box_diag_parts.box()
                    col_a.label(text="Parte A (Azul)", icon='MESH_CUBE')
                    col_a.label(text=f"Volume: {settings.part_a_volume_mm3:,.1f} mm³")
                    dims_a = settings.part_a_dims_mm
                    col_a.label(text=f"Dimensões: {dims_a[0]:.1f} x {dims_a[1]:.1f} x {dims_a[2]:.1f} mm")
                    col_a.label(text=f"Malha: {settings.part_a_triangles:,} tris | {settings.part_a_components} ilha(s)")
                    if not settings.part_a_is_manifold:
                        col_a.label(text=f"Aviso: {settings.part_a_non_manifold_edges} aresta(s) abertas", icon='ERROR')

                    col_b = box_diag_parts.box()
                    col_b.label(text="Parte B (Laranja)", icon='MESH_CUBE')
                    col_b.label(text=f"Volume: {settings.part_b_volume_mm3:,.1f} mm³")
                    dims_b = settings.part_b_dims_mm
                    col_b.label(text=f"Dimensões: {dims_b[0]:.1f} x {dims_b[1]:.1f} x {dims_b[2]:.1f} mm")
                    col_b.label(text=f"Malha: {settings.part_b_triangles:,} tris | {settings.part_b_components} ilha(s)")
                    if not settings.part_b_is_manifold:
                        col_b.label(text=f"Aviso: {settings.part_b_non_manifold_edges} aresta(s) abertas", icon='ERROR')

                    # Balanço de Volume
                    box_vol = box_diag_parts.box()
                    vol_ok = settings.volume_diff_pct < 0.5
                    icon_vol = 'CHECKMARK' if vol_ok else 'ERROR'
                    box_vol.label(
                        text=f"Soma Volumes: {settings.part_sum_volume_mm3:,.1f} mm³ (dif: {settings.volume_diff_pct:.2f}%)",
                        icon=icon_vol
                    )

                # --- Confirmação e Restauração ---
                box_commit = box_split.box()
                if settings.session_status == 'PREVIEW_VALID':
                    row_commit = box_commit.row()
                    row_commit.scale_y = 1.4
                    row_commit.operator("chest.splitter_commit_parts", text="Confirmar Divisão", icon='CHECKMARK')

                    row_rest = box_commit.row()
                    row_rest.operator("chest.splitter_restore_original", text="Restaurar Original", icon='UNDO')

                elif settings.session_status == 'COMMITTED':
                    box_commit.label(text="Peças finais geradas na coleção CHEST_SPLITTER_PARTS.", icon='CHECKMARK')
                    box_commit.operator("chest.splitter_redo_session", text="Refazer / Novo Corte", icon='FILE_REFRESH')
                    box_commit.operator("chest.splitter_restore_original", text="Restaurar Original", icon='UNDO')

                elif settings.session_status == 'CONFIGURED':
                    box_commit.label(text="Posicione o plano e clique em 'Gerar Preview'.", icon='INFO')
            else:
                box_split.label(text="Defina um objeto alvo primeiro.", icon='INFO')

        elif settings.split_mode == 'SOLID':
            box_split.label(text="Cortador sólido fechado planejado para a Fase 3.", icon='INFO')
        else:
            box_split.label(text="Segmentação por materiais planejada para a Fase 4.", icon='INFO')

        layout.separator()

        # --- SEÇÃO 3: ENCAIXES E FOLGA (Fase 2) ---
        box_conn = layout.box()
        box_conn.label(text="3. Encaixes & Folgas (Fase 2)", icon='SNAP_VERTEX')
        box_conn.label(text="Pinos cilíndricos e cápsula com folga física em mm.")

        # --- FEEDBACK DE STATUS ---
        if settings.last_status:
            layout.separator()
            box_status = layout.box()
            icon_status = 'INFO'
            if settings.last_status_level == 'SUCCESS':
                icon_status = 'CHECKMARK'
            elif settings.last_status_level == 'WARNING':
                icon_status = 'ERROR'
            elif settings.last_status_level == 'ERROR':
                icon_status = 'CANCEL'
            box_status.label(text=settings.last_status, icon=icon_status)


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
