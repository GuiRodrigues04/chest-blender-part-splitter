"""Gerenciamento de ciclo de vida, snapshots e reversão de operações do Chest Part Splitter."""

import os
from typing import Optional, List, Dict, Any, Tuple, Set
import bpy
import bmesh
from mathutils import Vector, Matrix

from .constants import (
    COLLECTION_GUIDES_NAME,
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_WORK_NAME,
    COLLECTION_PARTS_NAME,
    COLLECTION_BACKUPS_NAME,
    ROLE_WORK_COPY,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
    ROLE_PREVIEW_PART,
    ROLE_COMMITTED_PART,
    ROLE_SUBPART_MATERIAL,
    ROLE_RESTORE_BACKUP,
)
from .diagnostic import analyze_target_mesh, get_scene_scale_to_mm
from .translations import _get_current_locale


def get_or_create_collection(scene: bpy.types.Scene, name: str) -> bpy.types.Collection:
    """Obtém ou cria uma coleção na cena ativa de forma segura."""
    for col in scene.collection.children_recursive:
        if col.name == name:
            return col
    new_col = bpy.data.collections.new(name)
    scene.collection.children.link(new_col)
    return new_col


def find_collection(scene: bpy.types.Scene, name: str) -> Optional[bpy.types.Collection]:
    """Localiza uma coleção na cena ativa pelo nome."""
    for col in scene.collection.children_recursive:
        if col.name == name:
            return col
    return None


def ensure_backups_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    """Cria ou obtém a coleção de backups ocultos para restauração e reversão."""
    col = get_or_create_collection(scene, COLLECTION_BACKUPS_NAME)
    col.hide_viewport = True
    col.hide_render = True
    return col


# -----------------------------------------------------------------------------
# Registro de Operações
# -----------------------------------------------------------------------------

def find_operation_record(scene: bpy.types.Scene, op_id: str) -> Optional[Any]:
    """Localiza um registro de operação pelo UUID na cena."""
    if not op_id or not hasattr(scene, "chest_operations"):
        return None
    for rec in scene.chest_operations:
        if rec.operation_id == op_id:
            return rec
    return None


def get_or_create_operation_record(
    scene: bpy.types.Scene,
    op_id: str,
    target: Optional[bpy.types.Object] = None,
    status: str = 'PREVIEW',
    parent_op_id: str = "",
) -> Any:
    """Obtém um registro existente ou cria um novo registro de operação persistente."""
    if not hasattr(scene, "chest_operations"):
        return None
    rec = find_operation_record(scene, op_id)
    if rec is not None:
        if target:
            rec.target_object = target
            rec.target_name = target.name
        if parent_op_id and not rec.parent_operation_id:
            rec.parent_operation_id = parent_op_id
        return rec

    rec = scene.chest_operations.add()
    rec.operation_id = op_id
    rec.status = status
    rec.parent_operation_id = parent_op_id
    if target:
        rec.target_object = target
        rec.target_name = target.name
        rec.target_hide_viewport = target.hide_viewport
        rec.target_hide_render = target.hide_render
    return rec


def record_created_object(op_record: Any, obj: bpy.types.Object, role: str):
    """Registra um objeto gerado pela operação para rastreamento inequívoco de propriedade."""
    if not op_record or not obj:
        return
    obj["chest_operation_id"] = op_record.operation_id
    obj["chest_role"] = role

    # Evita duplicação no registro
    for item in op_record.created_objects:
        if item.obj == obj or item.name == obj.name:
            item.obj = obj
            item.role = role
            return

    item = op_record.created_objects.add()
    item.obj = obj
    item.name = obj.name
    item.role = role


def record_unlinked_parent(op_record: Any, obj: bpy.types.Object):
    """Registra um objeto pai desvinculado (ex: durante separação por material)."""
    if not op_record or not obj:
        return
    for item in op_record.unlinked_parents:
        if item.obj == obj or item.name == obj.name:
            return
    item = op_record.unlinked_parents.add()
    item.obj = obj
    item.name = obj.name
    item.role = "UNLINKED_PARENT"


# -----------------------------------------------------------------------------
# Gerenciamento de Snapshots
# -----------------------------------------------------------------------------

def capture_target_snapshot(scene: bpy.types.Scene, op_record: Any, target: bpy.types.Object):
    """Cria ou atualiza transacionalmente o snapshot do alvo antes de ocultá-lo."""
    if not op_record or not target or target.type != 'MESH':
        return

    backups_col = ensure_backups_collection(scene)
    op_id = op_record.operation_id

    # Descarta snapshot anterior desta mesma operação se houver
    discard_target_snapshot(scene, op_record)

    # Cria cópia independente da malha base (sem depender de malha avaliada com modificadores)
    snap_mesh = target.data.copy()
    snap_mesh.name = f"_snap_mesh_{op_id[:8]}"

    snap_obj = target.copy()
    snap_obj.data = snap_mesh
    snap_obj.name = f"_snap_obj_{op_id[:8]}"
    snap_obj["chest_role"] = ROLE_RESTORE_BACKUP
    snap_obj["chest_operation_id"] = op_id

    backups_col.objects.link(snap_obj)

    op_record.snapshot_object = snap_obj
    op_record.snapshot_name = snap_obj.name
    op_record.target_object = target
    op_record.target_name = target.name
    op_record.target_hide_viewport = target.hide_viewport
    op_record.target_hide_render = target.hide_render


def discard_target_snapshot(scene: bpy.types.Scene, op_record: Any):
    """Descarta o snapshot de backup associado a uma operação de prévia."""
    if not op_record:
        return
    snap_obj = op_record.snapshot_object
    snap_name = op_record.snapshot_name

    backups_col = find_collection(scene, COLLECTION_BACKUPS_NAME)

    target_snap = snap_obj if (snap_obj and snap_obj.name in bpy.data.objects) else bpy.data.objects.get(snap_name)
    if target_snap:
        snap_mesh = target_snap.data
        if backups_col and target_snap.name in backups_col.objects:
            backups_col.objects.unlink(target_snap)
        if target_snap.name in bpy.data.objects:
            bpy.data.objects.remove(target_snap, do_unlink=True)
        if snap_mesh and snap_mesh.users == 0:
            bpy.data.meshes.remove(snap_mesh, do_unlink=True)

    op_record.snapshot_object = None
    op_record.snapshot_name = ""


# -----------------------------------------------------------------------------
# Resolução de Operação e Checagem de Dependências
# -----------------------------------------------------------------------------

def resolve_operation(context: bpy.types.Context) -> Optional[Any]:
    """Identifica de forma determinística e inequívoca a operação em foco."""
    scene = context.scene
    settings = getattr(scene, "chest_splitter", None)
    if not settings:
        return None

    # 1. Pelo objeto ativo
    act_obj = context.active_object
    if act_obj:
        op_id = act_obj.get("chest_operation_id")
        if op_id:
            rec = find_operation_record(scene, op_id)
            if rec:
                return rec

    # 2. Pelos objetos selecionados
    for o in context.selected_objects:
        op_id = o.get("chest_operation_id")
        if op_id:
            rec = find_operation_record(scene, op_id)
            if rec:
                return rec

    # 3. Pelo ID ativo na sessão
    active_op_id = getattr(settings, "active_operation_id", "") or getattr(settings, "session_id", "")
    if active_op_id:
        rec = find_operation_record(scene, active_op_id)
        if rec:
            return rec

    return None


def check_child_operations(scene: bpy.types.Scene, op_record: Any) -> Tuple[bool, str]:
    """Verifica se existem operações filhas ativas (confirmadas) que dependem desta operação."""
    if not op_record or not hasattr(scene, "chest_operations"):
        return False, ""

    parent_id = op_record.operation_id
    for other in scene.chest_operations:
        if other.operation_id != parent_id and other.parent_operation_id == parent_id:
            if other.status == 'COMMITTED':
                loc = _get_current_locale()
                msg = (
                    f"A operação possui cortes posteriores ativos (ID: {other.operation_id[:8]}). "
                    f"É necessário reverter primeiro o corte posterior antes de reverter o corte pai."
                    if loc == "pt_BR"
                    else f"The operation has active child cuts (ID: {other.operation_id[:8]}). "
                         f"You must revert the posterior cut before reverting this parent cut."
                )
                return True, msg
    return False, ""


# -----------------------------------------------------------------------------
# Remoção de Prévia
# -----------------------------------------------------------------------------

def remove_preview(context: bpy.types.Context, op_id: Optional[str] = None) -> Tuple[bool, str]:
    """Descarta a prévia atual e restaura a visualização e seleção do objeto alvo."""
    scene = context.scene
    settings = scene.chest_splitter
    loc = _get_current_locale()

    # Garante saída segura de Edit Mode
    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass

    op_record = find_operation_record(scene, op_id) if op_id else resolve_operation(context)
    if not op_record and settings.session_id:
        op_record = find_operation_record(scene, settings.session_id)

    curr_op_id = op_record.operation_id if op_record else settings.session_id

    # Identifica objetos de prévia vinculados
    preview_col = find_collection(scene, COLLECTION_PREVIEWS_NAME)
    objs_to_remove = set()

    if preview_col:
        for o in list(preview_col.objects):
            if o.type != 'MESH':
                continue
            # Verifica propriedade estrita
            o_op = o.get("chest_operation_id")
            o_sid = o.get("chest_session_id")
            o_role = o.get("chest_role")
            if curr_op_id and (o_op == curr_op_id or o_sid == curr_op_id):
                objs_to_remove.add(o)
            elif o_role in (ROLE_PREVIEW_A, ROLE_PREVIEW_B, ROLE_PREVIEW_PART, ROLE_SUBPART_MATERIAL):
                objs_to_remove.add(o)

    if op_record:
        for ref in op_record.created_objects:
            if ref.obj and ref.obj.name in bpy.data.objects and ref.role in (
                ROLE_PREVIEW_A, ROLE_PREVIEW_B, ROLE_PREVIEW_PART, ROLE_SUBPART_MATERIAL
            ):
                objs_to_remove.add(ref.obj)

    # Exclusão segura dos objetos de prévia
    for obj in objs_to_remove:
        mesh_data = obj.data if obj.type == 'MESH' else None
        if preview_col and obj.name in preview_col.objects:
            preview_col.objects.unlink(obj)
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data, do_unlink=True)

    # Restaura visibilidade e acessibilidade do alvo
    target = op_record.target_object if (op_record and op_record.target_object) else settings.target_object
    if target and target.name in bpy.data.objects:
        target.hide_viewport = False
        target.hide_set(False)

        # Seleciona e ativa o alvo
        try:
            bpy.ops.object.select_all(action='DESELECT')
            target.select_set(True)
            context.view_layer.objects.active = target
        except Exception:
            pass

        settings.target_object = target

    # Descarta snapshot de prévia
    if op_record:
        discard_target_snapshot(scene, op_record)
        op_record.status = 'REVERTED'

    # Limpa métricas e assinaturas da sessão
    settings.session_input_signature = ""
    settings.part_a_volume_mm3 = 0.0
    settings.part_b_volume_mm3 = 0.0
    settings.part_sum_volume_mm3 = 0.0
    settings.volume_diff_pct = 0.0

    if target and target.name in bpy.data.objects:
        settings.session_status = 'CONFIGURED'
    else:
        settings.session_status = 'EMPTY'

    msg = (
        "Prévia removida com sucesso. Retornado ao objeto alvo."
        if loc == "pt_BR"
        else "Preview successfully discarded. Returned to target object."
    )
    settings.last_status = msg
    settings.last_status_level = 'INFO'
    return True, msg


# -----------------------------------------------------------------------------
# Reversão de Corte Confirmado
# -----------------------------------------------------------------------------

def revert_committed_operation(context: bpy.types.Context, op_id: Optional[str] = None) -> Tuple[bool, str]:
    """Reverte um corte confirmado, restaura o alvo original e remove os resultados gerados."""
    scene = context.scene
    settings = scene.chest_splitter
    loc = _get_current_locale()

    # Garante saída segura de Edit Mode
    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass

    op_record = find_operation_record(scene, op_id) if op_id else resolve_operation(context)
    if not op_record and settings.session_id:
        op_record = find_operation_record(scene, settings.session_id)

    if not op_record:
        msg = (
            "Nenhuma operação confirmada identificada para reversão."
            if loc == "pt_BR"
            else "No committed operation found to revert."
        )
        return False, msg

    # Checagem de hierarquia (cortes filhos bloqueiam o pai)
    has_child, child_msg = check_child_operations(scene, op_record)
    if has_child:
        return False, child_msg

    curr_op_id = op_record.operation_id

    # 1. PREPARAÇÃO DA RESTAURAÇÃO DO ALVO (antes de excluir qualquer resultado)
    target = op_record.target_object
    target_exists = target and target.name in bpy.data.objects
    snap_obj = op_record.snapshot_object
    snap_name = op_record.snapshot_name
    backup_snap = snap_obj if (snap_obj and snap_obj.name in bpy.data.objects) else bpy.data.objects.get(snap_name)

    if not target_exists and not backup_snap:
        msg = (
            f"Não foi possível reverter: o objeto alvo original foi apagado e não há backup válido."
            if loc == "pt_BR"
            else "Cannot revert: original target object was deleted and no valid backup exists."
        )
        return False, msg

    if target_exists:
        # Alvo existe: preserva identidade e restaura dados a partir do snapshot
        if backup_snap:
            # Restaura malha base e slots de materiais
            old_mesh = target.data
            target.data = backup_snap.data.copy()
            if old_mesh and old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh, do_unlink=True)

            target.matrix_world = backup_snap.matrix_world.copy()
            target.location = backup_snap.location.copy()
            target.rotation_euler = backup_snap.rotation_euler.copy()
            target.scale = backup_snap.scale.copy()

        target.hide_viewport = op_record.target_hide_viewport
        target.hide_render = op_record.target_hide_render
        target.hide_set(False)
    else:
        # Alvo foi apagado pelo usuário: recupera novo objeto a partir do backup
        rec_name = op_record.target_name or "Restored_Target"
        rec_mesh = backup_snap.data.copy()
        recovered_obj = bpy.data.objects.new(rec_name, rec_mesh)
        recovered_obj.matrix_world = backup_snap.matrix_world.copy()

        # Vincula na coleção principal da cena
        scene.collection.objects.link(recovered_obj)
        target = recovered_obj
        op_record.target_object = target
        settings.target_object = target

    # 2. IDENTIFICAÇÃO E EXCLUSÃO SEGURA DOS RESULTADOS GERADOS
    parts_col = find_collection(scene, COLLECTION_PARTS_NAME)
    objs_to_remove = set()

    # Objetos registrados explicitamente
    for ref in op_record.created_objects:
        if ref.obj and ref.obj.name in bpy.data.objects:
            objs_to_remove.add(ref.obj)

    # Objetos na coleção de partes com identificação inequívoca
    if parts_col:
        for o in list(parts_col.objects):
            if o.type != 'MESH':
                continue
            o_op = o.get("chest_operation_id")
            o_sid = o.get("chest_session_id") or o.get("chest_splitter_session_id")
            if curr_op_id and (o_op == curr_op_id or o_sid == curr_op_id):
                objs_to_remove.add(o)

    # Restaura pais desvinculados em separação por material se aplicável
    for parent_ref in op_record.unlinked_parents:
        p_obj = parent_ref.obj if (parent_ref.obj and parent_ref.obj.name in bpy.data.objects) else bpy.data.objects.get(parent_ref.name)
        if p_obj and p_obj not in objs_to_remove:
            if parts_col and p_obj.name not in parts_col.objects:
                parts_col.objects.link(p_obj)

    # Exclui os resultados confirmados
    for obj in objs_to_remove:
        mesh_data = obj.data if obj.type == 'MESH' else None
        if parts_col and obj.name in parts_col.objects:
            parts_col.objects.unlink(obj)
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data, do_unlink=True)

    # Descarta snapshot de backup da operação revertida
    discard_target_snapshot(scene, op_record)

    # Marca operação como revertida
    op_record.status = 'REVERTED'

    # 3. REATIVAÇÃO DO ALVO E RECONCILIAÇÃO DA SESSÃO
    if target and target.name in bpy.data.objects:
        target.hide_viewport = False
        try:
            bpy.ops.object.select_all(action='DESELECT')
            target.select_set(True)
            context.view_layer.objects.active = target
        except Exception:
            pass

        # Recalcula diagnósticos do alvo restaurado
        diag = analyze_target_mesh(target, scene)
        settings.diag_dims_mm = diag["dims_mm"]
        settings.diag_triangles = diag["triangles"]
        settings.diag_faces = diag["faces"]
        settings.diag_volume_mm3 = diag["volume_mm3"]
        settings.diag_is_manifold = diag["is_manifold"]
        settings.diag_non_manifold_edges = diag["non_manifold_edges"]

        settings.session_status = 'CONFIGURED'
    else:
        settings.session_status = 'EMPTY'

    # Limpa métricas de corte da sessão
    settings.session_input_signature = ""
    settings.part_a_volume_mm3 = 0.0
    settings.part_b_volume_mm3 = 0.0
    settings.part_sum_volume_mm3 = 0.0
    settings.volume_diff_pct = 0.0

    msg = (
        f"Corte revertido com sucesso. O modelo '{target.name if target else ''}' foi restaurado."
        if loc == "pt_BR"
        else f"Cut successfully reverted. Model '{target.name if target else ''}' was restored."
    )
    settings.last_status = msg
    settings.last_status_level = 'INFO'
    return True, msg
