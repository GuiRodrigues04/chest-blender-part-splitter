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

            # Avisos e diagnósticos preventivos
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

        # --- SEÇÃO 2: MODO DE DIVISÃO (Preview de Roadmap) ---
        box_mode = layout.box()
        box_mode.label(text="2. Divisão de Partes", icon='MOD_BOOLEAN')
        col_mode = box_mode.column()
        col_mode.prop(settings, "split_mode", expand=True)

        if settings.split_mode == 'PLANE':
            col_mode.label(text="Corte por plano orientado (Fase 1)", icon='INFO')
        elif settings.split_mode == 'SOLID':
            col_mode.label(text="Cortador sólido fechado (Fase 3)", icon='INFO')
        else:
            col_mode.label(text="Segmentação por materiais (Fase 4)", icon='INFO')

        layout.separator()

        # --- SEÇÃO 3: ENCAIXES E FOLGA (Preview de Roadmap) ---
        box_conn = layout.box()
        box_conn.label(text="3. Encaixes & Folgas (Fase 2)", icon='SNAP_VERTEX')
        box_conn.label(text="Pinos cilíndricos e cápsula com folga em mm.")

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
