"""Operadores do Blender para o Chest Part Splitter."""

import bpy
from .constants import (
    COLLECTION_GUIDES_NAME,
    COLLECTION_PREVIEWS_NAME,
    WORK_COPY_SUFFIX,
)
from .diagnostic import analyze_target_mesh


def get_or_create_collection(scene: bpy.types.Scene, name: str) -> bpy.types.Collection:
    """Obtém ou cria uma coleção na cena ativa de forma segura."""
    for col in scene.collection.children_recursive:
        if col.name == name:
            return col
    new_col = bpy.data.collections.new(name)
    scene.collection.children.link(new_col)
    return new_col


class CHEST_OT_splitter_set_target(bpy.types.Operator):
    """Define o objeto selecionado como alvo para divisão em partes"""
    bl_idname = "chest.splitter_set_target"
    bl_label = "Usar objeto selecionado como alvo"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        settings = context.scene.chest_splitter
        obj = context.active_object

        # Preserva seleção e modo
        orig_mode = context.mode
        if orig_mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        settings.target_object = obj

        # Garante a existência das coleções do Splitter
        get_or_create_collection(context.scene, COLLECTION_GUIDES_NAME)
        get_or_create_collection(context.scene, COLLECTION_PREVIEWS_NAME)

        # Executa análise diagnóstica
        report = analyze_target_mesh(obj, context.scene)

        # Atualiza propriedades em cache
        settings.diag_dims_mm = report["dims_mm"]
        settings.diag_triangles = report["triangles"]
        settings.diag_faces = report["faces"]
        settings.diag_volume_mm3 = report["volume_mm3"]
        settings.diag_is_manifold = report["is_manifold"]
        settings.diag_non_manifold_edges = report["non_manifold_edges"]
        settings.diag_has_unapplied_scale = report["has_unapplied_scale"]
        settings.diag_is_non_uniform_scale = report["is_non_uniform_scale"]
        settings.diag_degenerate_faces = report["degenerate_faces"]

        settings.session_status = 'CONFIGURED'

        # Formata mensagem de status
        dims = report["dims_mm"]
        msg = f"Alvo definido: '{obj.name}' ({dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm, {report['triangles']} tris)"
        settings.last_status = msg
        settings.last_status_level = 'SUCCESS' if report["valid"] else 'WARNING'

        self.report({'INFO'}, msg)

        # Restaura modo se necessário
        if orig_mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode=orig_mode)

        return {'FINISHED'}


class CHEST_OT_splitter_clear_target(bpy.types.Operator):
    """Desassocia o alvo atual e limpa o diagnóstico da sessão"""
    bl_idname = "chest.splitter_clear_target"
    bl_label = "Limpar alvo"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.chest_splitter
        settings.target_object = None
        settings.session_status = 'EMPTY'
        settings.diag_dims_mm = (0.0, 0.0, 0.0)
        settings.diag_triangles = 0
        settings.diag_faces = 0
        settings.diag_volume_mm3 = 0.0
        settings.diag_is_manifold = True
        settings.diag_non_manifold_edges = 0
        settings.diag_has_unapplied_scale = False
        settings.diag_is_non_uniform_scale = False
        settings.diag_degenerate_faces = 0
        settings.last_status = "Alvo removido. Selecione um novo objeto."
        settings.last_status_level = 'INFO'

        return {'FINISHED'}


class CHEST_OT_splitter_create_work_copy(bpy.types.Operator):
    """Cria uma cópia de trabalho com escala e rotação aplicadas sem alterar o original"""
    bl_idname = "chest.splitter_create_work_copy"
    bl_label = "Criar cópia de trabalho com transformações aplicadas"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.chest_splitter
        return settings.target_object and settings.target_object.type == 'MESH'

    def execute(self, context):
        settings = context.scene.chest_splitter
        orig_obj = settings.target_object

        # Preserva contexto
        active_obj = context.active_object
        selected_objs = [o for o in context.selected_objects]

        # Duplica malha e objeto de forma limpa
        new_mesh = orig_obj.data.copy()
        new_obj = orig_obj.copy()
        new_obj.data = new_mesh
        new_obj.name = f"{orig_obj.name}{WORK_COPY_SUFFIX}"

        # Vincula na coleção de previews
        preview_col = get_or_create_collection(context.scene, COLLECTION_PREVIEWS_NAME)
        preview_col.objects.link(new_obj)

        # Oculta temporariamente o original na Viewport para não colidir
        orig_obj.hide_viewport = True

        # Seleciona e torna ativa a cópia de trabalho
        for o in context.selected_objects:
            o.select_set(False)
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj

        # Aplica rotação e escala na cópia
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

        # Atualiza alvo para a nova cópia de trabalho
        settings.target_object = new_obj

        # Re-analisa a cópia
        report = analyze_target_mesh(new_obj, context.scene)
        settings.diag_dims_mm = report["dims_mm"]
        settings.diag_triangles = report["triangles"]
        settings.diag_faces = report["faces"]
        settings.diag_volume_mm3 = report["volume_mm3"]
        settings.diag_is_manifold = report["is_manifold"]
        settings.diag_non_manifold_edges = report["non_manifold_edges"]
        settings.diag_has_unapplied_scale = report["has_unapplied_scale"]
        settings.diag_is_non_uniform_scale = report["is_non_uniform_scale"]
        settings.diag_degenerate_faces = report["degenerate_faces"]

        msg = f"Cópia de trabalho '{new_obj.name}' criada com transformações aplicadas. Original preservado."
        settings.last_status = msg
        settings.last_status_level = 'SUCCESS'
        self.report({'INFO'}, msg)

        return {'FINISHED'}


classes = (
    CHEST_OT_splitter_set_target,
    CHEST_OT_splitter_clear_target,
    CHEST_OT_splitter_create_work_copy,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
