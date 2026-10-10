"""Operadores do Blender para o Chest Part Splitter (Fase 1 - Corte por Plano)."""

import os
import uuid
import hashlib
import math
from typing import Optional, List, Dict, Any, Tuple
import bpy
from bpy.app.handlers import persistent
import bmesh
from mathutils import Vector, Matrix, Euler, Quaternion

from .constants import (
    COLLECTION_GUIDES_NAME,
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_WORK_NAME,
    COLLECTION_PARTS_NAME,
    PART_A_SUFFIX,
    PART_B_SUFFIX,
    WORK_COPY_SUFFIX,
    PLANE_GUIDE_NAME,
    SOLID_CUTTER_NAME,
    PREVIEW_A_NAME,
    PREVIEW_B_NAME,
    COLOR_PART_A,
    COLOR_PART_B,
    VOLUME_REL_TOLERANCE,
    CLEARANCE_PRESETS,
    SOLID_PRIMITIVE_TYPES,
    ROLE_WORK_COPY,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
    ROLE_PREVIEW_PART,
    ROLE_COMMITTED_PART,
    ROLE_SUBPART_MATERIAL,
)
from .diagnostic import analyze_target_mesh, get_scene_scale_to_mm

from .geometry_plane import (
    slice_mesh_by_plane,
    compute_explosion_offsets,
    evaluate_bmesh_metrics,
    NoIntersectionError,
    PlaneSliceError,
)
from .geometry_connectors import (
    compute_connector_positions,
    compute_connector_layout,
    validate_connectors,
    apply_connectors_boolean,
    ConnectorValidationError,
)
from .geometry_solid import (
    create_primitive_cutter_mesh,
    validate_solid_cutter,
    slice_mesh_by_solid,
    compute_solid_explosion_offsets,
    SolidCutterValidationError,
    SolidSliceError,
)



def find_collection(scene: bpy.types.Scene, name: str) -> Optional[bpy.types.Collection]:
    """Localiza uma coleção na cena ativa pelo nome."""
    for col in scene.collection.children_recursive:
        if col.name == name:
            return col
    return None


def get_or_create_collection(scene: bpy.types.Scene, name: str) -> bpy.types.Collection:
    """Obtém ou cria uma coleção na cena ativa de forma segura."""
    found = find_collection(scene, name)
    if found:
        return found
    new_col = bpy.data.collections.new(name)
    scene.collection.children.link(new_col)
    return new_col



def cleanup_collection_objects(
    collection: bpy.types.Collection,
    exclude_objects: Optional[set] = None,
    session_id: Optional[str] = None,
):
    """Remove de forma segura objetos temporários de prévia sem remover o alvo, cópias de trabalho ou objetos do usuário."""
    if not collection:
        return

    exclude_set = set(exclude_objects) if exclude_objects else set()
    exclude_names = {o.name if hasattr(o, "name") else str(o) for o in exclude_set}

    scene = bpy.context.scene if bpy.context else None
    target_obj = getattr(getattr(scene, "chest_splitter", None), "target_object", None) if scene else None
    if target_obj:
        exclude_names.add(target_obj.name)

    objs_to_process = list(collection.objects)
    for obj in objs_to_process:
        if obj.name in exclude_names:
            # Caso seja o alvo em uma coleção antiga (ex.: 0.8.4), migra com segurança para a coleção de trabalho
            if collection.name == COLLECTION_PREVIEWS_NAME:
                collection.objects.unlink(obj)
                if scene:
                    work_col = get_or_create_collection(scene, COLLECTION_WORK_NAME)
                    if obj.name not in work_col.objects:
                        work_col.objects.link(obj)
                obj["chest_role"] = ROLE_WORK_COPY
            continue

        # Nunca apaga cópias de trabalho ou objetos marcados com papel protegido
        role = obj.get("chest_role")
        if role == ROLE_WORK_COPY:
            if collection.name == COLLECTION_PREVIEWS_NAME:
                collection.objects.unlink(obj)
                if scene:
                    work_col = get_or_create_collection(scene, COLLECTION_WORK_NAME)
                    if obj.name not in work_col.objects:
                        work_col.objects.link(obj)
            continue

        # Se houver filtro de session_id, preserva objetos de outras sessões
        obj_sid = obj.get("chest_session_id")
        if session_id and obj_sid and obj_sid != session_id:
            continue

        # Identifica se é objeto de preview descartável
        # Antigas prévias (0.8.4) não tinham session_id, então excluímos por nome + coleção apenas se tiver certeza.
        # Mas para proteger objetos do usuário, exigimos que tenha o "chest_role" OU "chest_session_id" se o nome bater.
        is_preview_obj = False
        if role in (ROLE_PREVIEW_A, ROLE_PREVIEW_B, ROLE_PREVIEW_PART, ROLE_SUBPART_MATERIAL):
            is_preview_obj = True
        elif obj_sid and obj_sid == session_id:
            is_preview_obj = True
        elif not obj_sid and not role and obj.name in (PREVIEW_A_NAME, PREVIEW_B_NAME) and collection.name == COLLECTION_PREVIEWS_NAME:
            is_preview_obj = True

        if is_preview_obj:
            mesh_data = obj.data if obj.type == 'MESH' else None
            collection.objects.unlink(obj)
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh_data and mesh_data.users == 0:
                bpy.data.meshes.remove(mesh_data, do_unlink=True)
        else:
            # Não é prévia. Se está na coleção temporária, apenas desvincula da coleção.
            if collection.name == COLLECTION_PREVIEWS_NAME:
                collection.objects.unlink(obj)


def validate_printable_mesh(
    bm: bmesh.types.BMesh,
    part_name: str = "Peça",
    unit_scale: float = 1000.0,
    check_manifold: bool = True,
    min_volume_mm3: float = 1e-3,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Valida se uma malha atende aos critérios mínimos de solidez para impressão 3D."""
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    verts_count = len(bm.verts)
    faces_count = len(bm.faces)

    if verts_count < 4 or faces_count < 4:
        return False, f"{part_name}: contagem insuficiente de elementos ({faces_count} faces, {verts_count} vértices).", {}

    for v in bm.verts:
        if not (math.isfinite(v.co.x) and math.isfinite(v.co.y) and math.isfinite(v.co.z)):
            return False, f"{part_name}: contém coordenadas infinitas ou NaN.", {}

    vol_bu = abs(bm.calc_volume(signed=True))
    vol_mm3 = vol_bu * (unit_scale ** 3)
    if vol_mm3 < min_volume_mm3:
        return False, f"{part_name}: volume nulo ou desprezível ({vol_mm3:.4f} mm³).", {}

    non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
    if check_manifold and len(non_manifold_edges) > 0:
        return False, f"{part_name}: possui {len(non_manifold_edges)} aresta(s) não-manifold/abertas (não é um sólido fechado).", {}

    metrics = evaluate_bmesh_metrics(bm, unit_scale=unit_scale)
    return True, "OK", metrics



def get_target_bounds(obj: bpy.types.Object):
    """Calcula o centro e o raio aproximado do bounding box do objeto em coordenadas globais."""
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [c.x for c in bbox_corners]
    ys = [c.y for c in bbox_corners]
    zs = [c.z for c in bbox_corners]

    center = Vector(((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    if size < 1e-4:
        size = 1.0
    return center, size


def ensure_plane_guide(context: bpy.types.Context) -> bpy.types.Object:
    """Cria ou recupera o objeto guia de plano na coleção CHEST_SPLITTER_GUIDES."""
    col = get_or_create_collection(context.scene, COLLECTION_GUIDES_NAME)
    guide_obj = col.objects.get(PLANE_GUIDE_NAME)

    if not guide_obj or guide_obj.name not in bpy.data.objects:
        settings = context.scene.chest_splitter
        target = settings.target_object
        if target:
            center, size = get_target_bounds(target)
            guide_size = size * 1.4
        else:
            center = Vector((0.0, 0.0, 0.0))
            guide_size = 150.0

        # Cria malha do plano com subdivisão leve para visualização
        mesh = bpy.data.meshes.new(f"{PLANE_GUIDE_NAME}_Mesh")
        bm = bmesh.new()
        hs = guide_size / 2.0
        # Cria um quadrado no plano XY local (normal aponta para +Z)
        v1 = bm.verts.new((-hs, -hs, 0.0))
        v2 = bm.verts.new((hs, -hs, 0.0))
        v3 = bm.verts.new((hs, hs, 0.0))
        v4 = bm.verts.new((-hs, hs, 0.0))
        bm.faces.new((v1, v2, v3, v4))
        bm.to_mesh(mesh)
        bm.free()

        guide_obj = bpy.data.objects.new(PLANE_GUIDE_NAME, mesh)
        guide_obj.location = center
        guide_obj.display_type = 'WIRE'
        guide_obj.show_in_front = True
        col.objects.link(guide_obj)

    return guide_obj


def read_plane_geometry(context: bpy.types.Context) -> (Vector, Vector):
    """Lê a origem e a normal do plano a partir do objeto guia ou das propriedades."""
    col = get_or_create_collection(context.scene, COLLECTION_GUIDES_NAME)
    guide_obj = col.objects.get(PLANE_GUIDE_NAME)
    settings = context.scene.chest_splitter

    if guide_obj:
        origin = guide_obj.matrix_world.translation.copy()
        normal = (guide_obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        settings.plane_origin = origin
        settings.plane_normal = normal
        return origin, normal
    else:
        return Vector(settings.plane_origin), Vector(settings.plane_normal).normalized()


def compute_session_input_signature(context: bpy.types.Context) -> str:
    """Calcula uma assinatura hash determinística do estado do modelo alvo, cortador e parâmetros de corte."""
    if not context or not hasattr(context, "scene") or not hasattr(context.scene, "chest_splitter"):
        return ""
    settings = context.scene.chest_splitter
    target = settings.target_object
    if not target or target.type != 'MESH':
        return ""

    tokens = []
    # 1. Alvo e transformações
    tokens.append(f"target:{target.name}")
    tokens.append(f"target_loc:{target.location.x:.5f},{target.location.y:.5f},{target.location.z:.5f}")
    tokens.append(f"target_rot:{target.rotation_euler.x:.5f},{target.rotation_euler.y:.5f},{target.rotation_euler.z:.5f}")
    tokens.append(f"target_scale:{target.scale.x:.5f},{target.scale.y:.5f},{target.scale.z:.5f}")
    mw = [f"{v:.5f}" for row in target.matrix_world for v in row]
    tokens.append(f"target_mw:{','.join(mw)}")
    
    import array
    import hashlib
    h = hashlib.sha256()

    if target.data:
        m = target.data
        tokens.append(f"target_geom:{len(m.vertices)},{len(m.edges)},{len(m.polygons)}")
        h.update(str(tokens).encode('utf-8'))
        tokens.clear()
        
        if len(m.vertices) > 0:
            coords = array.array('f', [0.0] * (len(m.vertices) * 3))
            m.vertices.foreach_get("co", coords)
            h.update(coords.tobytes())
        if len(m.edges) > 0:
            edges = array.array('i', [0] * (len(m.edges) * 2))
            m.edges.foreach_get("vertices", edges)
            h.update(edges.tobytes())
        if len(m.polygons) > 0:
            mats = array.array('i', [0] * len(m.polygons))
            m.polygons.foreach_get("material_index", mats)
            h.update(mats.tobytes())
            
        mats_list = [mat.name if mat else "None" for mat in m.materials]
        tokens.append(f"target_mats_list:{','.join(mats_list)}")

    # 2. Modo e parâmetros de corte
    tokens.append(f"mode:{settings.split_mode}")
    tokens.append(f"unit_scale:{get_scene_scale_to_mm(context.scene):.5f}")
    tokens.append(f"clearance:{settings.clearance_per_side_mm:.4f}")

    if settings.split_mode == 'PLANE':
        po, pn = read_plane_geometry(context)
        tokens.append(f"plane_po:{po.x:.4f},{po.y:.4f},{po.z:.4f}")
        tokens.append(f"plane_pn:{pn.x:.4f},{pn.y:.4f},{pn.z:.4f}")
        tokens.append(f"invert:{settings.invert_sides}")

    elif settings.split_mode == 'SOLID':
        cutter = settings.solid_cutter_object
        if cutter and cutter.name in bpy.data.objects:
            tokens.append(f"cutter:{cutter.name}")
            tokens.append(f"cutter_loc:{cutter.location.x:.5f},{cutter.location.y:.5f},{cutter.location.z:.5f}")
            tokens.append(f"cutter_rot:{cutter.rotation_euler.x:.5f},{cutter.rotation_euler.y:.5f},{cutter.rotation_euler.z:.5f}")
            tokens.append(f"cutter_scale:{cutter.scale.x:.5f},{cutter.scale.y:.5f},{cutter.scale.z:.5f}")
            cmw = [f"{v:.5f}" for row in cutter.matrix_world for v in row]
            tokens.append(f"cutter_mw:{','.join(cmw)}")
            if cutter.data:
                cm = cutter.data
                tokens.append(f"cutter_geom:{len(cm.vertices)},{len(cm.edges)},{len(cm.polygons)}")
                h.update(str(tokens).encode('utf-8'))
                tokens.clear()
                if len(cm.vertices) > 0:
                    ccoords = array.array('f', [0.0] * (len(cm.vertices) * 3))
                    cm.vertices.foreach_get("co", ccoords)
                    h.update(ccoords.tobytes())
                if len(cm.edges) > 0:
                    cedges = array.array('i', [0] * (len(cm.edges) * 2))
                    cm.edges.foreach_get("vertices", cedges)
                    h.update(cedges.tobytes())

    elif settings.split_mode == 'LOOP':
        tokens.append(f"loop_indices:{settings.loop_vertex_indices}")
        tokens.append(f"loop_depth:{settings.loop_extrude_depth_mm:.4f}")
        tokens.append(f"loop_mode:{settings.loop_behavior}")
        tokens.append(f"loop_seed:{settings.loop_seed_face_index}")

    elif settings.split_mode == 'MATERIAL':
        tokens.append(f"mat_idx:{settings.material_split_index}")
        tokens.append(f"mat_region:{settings.material_region_index}")
        tokens.append(f"mat_depth:{settings.material_extrude_depth_mm:.4f}")

    # 3. Encaixes (apenas se ativos e suportados no modo)
    tokens.append(f"conn_enabled:{settings.connector_enabled}")
    if settings.connector_enabled and settings.split_mode not in ('SOLID', 'MATERIAL'):
        tokens.append(f"conn_type:{settings.connector_type}")
        tokens.append(f"conn_diam:{settings.connector_diameter_mm:.4f}")
        tokens.append(f"conn_len:{settings.connector_length_mm:.4f}")
        tokens.append(f"conn_cap_len:{settings.connector_capsule_length_mm:.4f}")
        tokens.append(f"conn_dist:{settings.connector_distribution}")
        tokens.append(f"conn_margin:{settings.connector_edge_margin_mm:.4f}")
        tokens.append(f"conn_male:{settings.connector_male_part}")

    if tokens:
        h.update("|".join(tokens).encode("utf-8"))
    return h.hexdigest()[:16]


def verify_preview_current(context: bpy.types.Context) -> Tuple[bool, str]:
    """Verifica se a prévia existente ainda reflete fielmente o estado atual da cena."""
    settings = context.scene.chest_splitter
    if settings.session_status != 'PREVIEW_VALID':
        return False, "Nenhuma prévia válida ativa na sessão."

    preview_col = find_collection(context.scene, COLLECTION_PREVIEWS_NAME)
    if not preview_col:
        return False, "Coleção de prévias não encontrada."

    curr_sid = settings.session_id
    if not curr_sid:
        return False, "Sessão inválida."

    parts = [
        o for o in preview_col.objects
        if o.type == 'MESH' and o.get("chest_session_id") == curr_sid
        and o.get("chest_role") in (ROLE_PREVIEW_A, ROLE_PREVIEW_B, ROLE_PREVIEW_PART, ROLE_SUBPART_MATERIAL)
    ]
    if not parts:
        return False, "Objetos de prévia da sessão atual não encontrados."

    curr_sig = compute_session_input_signature(context)
    if settings.session_input_signature and curr_sig != settings.session_input_signature:
        return False, "O modelo alvo, cortador ou parâmetros foram alterados após gerar a prévia."

    return True, ""


def get_current_session_parts(scene: bpy.types.Scene) -> List[bpy.types.Object]:
    """Retorna os objetos malha pertencentes estritamente à sessão ativa atual."""
    settings = scene.chest_splitter
    curr_sid = settings.session_id
    if not curr_sid:
        return []

    if settings.session_status == 'PREVIEW_VALID':
        preview_col = find_collection(scene, COLLECTION_PREVIEWS_NAME)
        if preview_col:
            res = [
                o for o in preview_col.objects
                if o.type == 'MESH' and o.get("chest_session_id") == curr_sid
                and o.get("chest_role") in (ROLE_PREVIEW_A, ROLE_PREVIEW_B, ROLE_PREVIEW_PART, ROLE_SUBPART_MATERIAL)
            ]
            if res:
                return res
        return []

    elif settings.session_status == 'COMMITTED':
        parts_col = find_collection(scene, COLLECTION_PARTS_NAME)
        if parts_col:
            res = [
                o for o in parts_col.objects
                if o.type == 'MESH' and (
                    o.get("chest_session_id") == curr_sid
                    or o.get("chest_splitter_session_id") == curr_sid
                )
                and o.get("chest_role") in (ROLE_COMMITTED_PART, ROLE_SUBPART_MATERIAL)
            ]
            if res:
                return res
            # Fallback seguro para migração de partes com id mas sem role, ou vice-versa
            res = [
                o for o in parts_col.objects
                if o.type == 'MESH' and (o.get("chest_session_id") == curr_sid or o.get("chest_splitter_session_id") == curr_sid)
            ]
            if res:
                return res
            
            # Fallback ultra conservador apenas se não houver NADA da sessão atual
            target = settings.target_object
            if target:
                base_name = target.name.replace(WORK_COPY_SUFFIX, "")
                res = [
                    o for o in parts_col.objects
                    if o.type == 'MESH' and o.name.startswith(base_name) and not o.get("chest_session_id")
                ]
                if res:
                    return res
        return []

    return []


def ensure_solid_cutter(context: bpy.types.Context) -> bpy.types.Object:
    """Cria ou recupera o objeto cortador sólido na coleção CHEST_SPLITTER_GUIDES."""

    col = get_or_create_collection(context.scene, COLLECTION_GUIDES_NAME)
    cutter_obj = col.objects.get(SOLID_CUTTER_NAME)
    settings = context.scene.chest_splitter
    target = settings.target_object

    if target:
        center, size = get_target_bounds(target)
        dims = Vector((size * 0.6, size * 0.6, size * 0.6))
    else:
        center = Vector((0.0, 0.0, 0.0))
        dims = Vector((50.0, 50.0, 50.0))

    prim_type = settings.solid_primitive_type

    if not cutter_obj or cutter_obj.name not in bpy.data.objects:
        mesh = create_primitive_cutter_mesh(
            name=f"{SOLID_CUTTER_NAME}_Mesh",
            primitive_type=prim_type,
            dims=dims,
        )
        cutter_obj = bpy.data.objects.new(SOLID_CUTTER_NAME, mesh)
        cutter_obj.location = center
        cutter_obj.display_type = 'WIRE'
        cutter_obj.show_in_front = True
        col.objects.link(cutter_obj)
    else:
        old_mesh = cutter_obj.data
        new_mesh = create_primitive_cutter_mesh(
            name=f"{SOLID_CUTTER_NAME}_Mesh",
            primitive_type=prim_type,
            dims=dims,
        )
        cutter_obj.data = new_mesh
        cutter_obj.location = center
        if old_mesh and old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh, do_unlink=True)

    settings.solid_cutter_object = cutter_obj
    return cutter_obj


def update_preview_positions(scene: bpy.types.Scene):
    """Atualiza a posição dos objetos de preview conforme modo montado ou explodido."""
    settings = scene.chest_splitter
    col = get_or_create_collection(scene, COLLECTION_PREVIEWS_NAME)
    obj_a = col.objects.get(PREVIEW_A_NAME)
    obj_b = col.objects.get(PREVIEW_B_NAME)

    if not obj_a or not obj_b:
        return

    unit_scale = get_scene_scale_to_mm(scene)

    if settings.view_mode == 'EXPLODED':
        if settings.split_mode == 'SOLID':
            offset_a, offset_b = compute_solid_explosion_offsets(
                obj_a,
                obj_b,
                settings.explosion_distance_mm,
                unit_scale=unit_scale,
            )
        elif settings.split_mode in ('LOOP', 'MATERIAL'):
            # Usa o vetor normal real da interface do loop para visão explodida fidedigna
            loop_norm = Vector(settings.loop_interface_normal)
            if loop_norm.length < 1e-6:
                loop_norm = Vector((0.0, 0.0, 1.0))
            loop_norm.normalize()
            dist_bu = (settings.explosion_distance_mm / unit_scale) / 2.0
            offset_a = -loop_norm * dist_bu
            offset_b = loop_norm * dist_bu
        else:
            plane_normal = Vector(settings.plane_normal).normalized()
            offset_a, offset_b = compute_explosion_offsets(
                plane_normal,
                settings.explosion_distance_mm,
                unit_scale=unit_scale,
            )
        obj_a.location = offset_a
        obj_b.location = offset_b
    else:
        obj_a.location = Vector((0.0, 0.0, 0.0))
        obj_b.location = Vector((0.0, 0.0, 0.0))


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

        # Garante coleções
        get_or_create_collection(context.scene, COLLECTION_GUIDES_NAME)
        get_or_create_collection(context.scene, COLLECTION_PREVIEWS_NAME)
        get_or_create_collection(context.scene, COLLECTION_PARTS_NAME)

        # Executa análise diagnóstica
        report = analyze_target_mesh(obj, context.scene)

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
        settings.session_id = ""

        # Garante criação e foco do guia de corte
        ensure_plane_guide(context)
        read_plane_geometry(context)

        dims = report["dims_mm"]
        msg = f"Alvo: '{obj.name}' ({dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm, {report['triangles']} tris)"
        settings.last_status = msg
        settings.last_status_level = 'SUCCESS' if report["valid"] else 'WARNING'
        self.report({'INFO'}, msg)

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
        orig_obj = settings.target_object
        if orig_obj and orig_obj.name in bpy.data.objects:
            orig_obj.hide_viewport = False

        # Limpa coleções auxiliares
        for col_name in (COLLECTION_PREVIEWS_NAME, COLLECTION_GUIDES_NAME):
            col = find_collection(context.scene, col_name)
            if col:
                cleanup_collection_objects(col)


        settings.target_object = None
        settings.session_status = 'EMPTY'
        settings.session_id = ""
        settings.session_input_signature = ""
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

        new_mesh = orig_obj.data.copy()
        new_obj = orig_obj.copy()
        new_obj.data = new_mesh
        new_obj.name = f"{orig_obj.name}{WORK_COPY_SUFFIX}"

        work_col = get_or_create_collection(context.scene, COLLECTION_WORK_NAME)
        work_col.objects.link(new_obj)

        new_obj["chest_role"] = ROLE_WORK_COPY
        new_obj["chest_original_target"] = orig_obj.name
        new_obj["chest_session_id"] = settings.session_id

        orig_obj.hide_viewport = True

        for o in context.selected_objects:
            o.select_set(False)
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj

        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


        settings.target_object = new_obj
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

        msg = f"Cópia de trabalho '{new_obj.name}' criada. Original preservado."
        settings.last_status = msg
        settings.last_status_level = 'SUCCESS'
        self.report({'INFO'}, msg)

        return {'FINISHED'}


class CHEST_OT_splitter_create_or_focus_guide(bpy.types.Operator):
    """Cria ou foca o plano guia na Viewport 3D para posicionamento do corte"""
    bl_idname = "chest.splitter_create_or_focus_guide"
    bl_label = "Posicionar / Focar Guia de Corte"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.chest_splitter.target_object is not None

    def execute(self, context):
        guide_obj = ensure_plane_guide(context)
        for o in context.selected_objects:
            o.select_set(False)
        guide_obj.select_set(True)
        context.view_layer.objects.active = guide_obj
        read_plane_geometry(context)
        return {'FINISHED'}


class CHEST_OT_splitter_align_plane(bpy.types.Operator):
    """Alinha a orientação do plano de corte por vista, cursor, face ou eixos principais"""
    bl_idname = "chest.splitter_align_plane"
    bl_label = "Alinhar Plano de Corte"
    bl_options = {'REGISTER', 'UNDO'}

    align_mode: bpy.props.EnumProperty(
        name="Modo de Alinhamento",
        items=[
            ('VIEW', "Vista", "Alinha o plano com a orientação da câmera/viewport"),
            ('CURSOR', "Cursor 3D", "Move a origem do plano para o Cursor 3D"),
            ('FACE', "Face Selecionada", "Alinha o plano à face selecionada"),
            ('X', "Eixo X", "Corte perpendicular ao eixo X (Normal +X)"),
            ('Y', "Eixo Y", "Corte perpendicular ao eixo Y (Normal +Y)"),
            ('Z', "Eixo Z", "Corte perpendicular ao eixo Z (Normal +Z)"),
        ],
        default='Z',
    )

    def execute(self, context):
        settings = context.scene.chest_splitter
        target = settings.target_object
        guide_obj = ensure_plane_guide(context)

        center = Vector(settings.plane_origin)
        if target:
            t_center, _ = get_target_bounds(target)
            center = t_center

        mode = self.align_mode

        if mode == 'CURSOR':
            guide_obj.location = context.scene.cursor.location
            settings.plane_origin = guide_obj.location

        elif mode == 'X':
            # Normal aponta para +X
            guide_obj.location = center
            guide_obj.rotation_euler = Euler((0.0, math.radians(90.0), 0.0))

        elif mode == 'Y':
            # Normal aponta para +Y
            guide_obj.location = center
            guide_obj.rotation_euler = Euler((math.radians(-90.0), 0.0, 0.0))

        elif mode == 'Z':
            # Normal aponta para +Z
            guide_obj.location = center
            guide_obj.rotation_euler = Euler((0.0, 0.0, 0.0))

        elif mode == 'VIEW':
            # Alinha com a visualização da Viewport 3D ativa
            r3d = None
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            r3d = space.region_3d
                            break
            if r3d:
                guide_obj.location = center
                guide_obj.rotation_euler = r3d.view_rotation.to_euler()

        elif mode == 'FACE':
            # Alinha com a face ativa do alvo se estiver em Edit Mode
            if target and target.mode == 'EDIT':
                bm = bmesh.from_edit_mesh(target.data)
                active_face = bm.faces.active
                if active_face:
                    # Sob escala não uniforme, normais devem ser transformadas pela inversa transposta
                    norm_matrix = target.matrix_world.to_3x3().inverted_safe().transposed()
                    face_normal_world = (norm_matrix @ active_face.normal).normalized()
                    face_center_world = target.matrix_world @ active_face.calc_center_median()
                    guide_obj.location = face_center_world
                    # Rotação que leva Vector(0,0,1) até face_normal_world
                    rot_quat = Vector((0.0, 0.0, 1.0)).rotation_difference(face_normal_world)
                    guide_obj.rotation_euler = rot_quat.to_euler()

        read_plane_geometry(context)
        msg = f"Plano alinhado por '{self.align_mode}'."
        settings.last_status = msg
        settings.last_status_level = 'INFO'
        self.report({'INFO'}, msg)

        return {'FINISHED'}


class CHEST_OT_splitter_create_or_focus_solid_cutter(bpy.types.Operator):
    """Cria ou foca o cortador sólido na Viewport 3D para posicionamento do corte"""
    bl_idname = "chest.splitter_create_or_focus_solid_cutter"
    bl_label = "Criar / Focar Cortador Sólido"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.chest_splitter.target_object is not None

    def execute(self, context):
        settings = context.scene.chest_splitter
        cutter_obj = ensure_solid_cutter(context)
        for o in context.selected_objects:
            o.select_set(False)
        cutter_obj.select_set(True)
        context.view_layer.objects.active = cutter_obj

        try:
            unit_scale = get_scene_scale_to_mm(context.scene)
            diag = validate_solid_cutter(cutter_obj, settings.target_object, unit_scale=unit_scale)
            settings.solid_cutter_is_manifold = diag["is_manifold"]
            settings.solid_cutter_triangles = diag["triangles"]
            settings.solid_cutter_volume_mm3 = diag["volume_mm3"]
        except Exception:
            pass

        self.report({'INFO'}, f"Cortador sólido '{settings.solid_primitive_type}' criado/focado. Use G/R/S para posicionar.")
        return {'FINISHED'}


class CHEST_OT_splitter_select_existing_cutter(bpy.types.Operator):
    """Define o objeto ativo na cena como cortador sólido"""
    bl_idname = "chest.splitter_select_existing_cutter"
    bl_label = "Usar Ativo como Cortador"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        settings = context.scene.chest_splitter
        return obj is not None and obj.type == 'MESH' and obj != settings.target_object

    def execute(self, context):
        settings = context.scene.chest_splitter
        obj = context.active_object
        settings.solid_cutter_object = obj

        try:
            unit_scale = get_scene_scale_to_mm(context.scene)
            diag = validate_solid_cutter(obj, settings.target_object, unit_scale=unit_scale)
            settings.solid_cutter_is_manifold = diag["is_manifold"]
            settings.solid_cutter_triangles = diag["triangles"]
            settings.solid_cutter_volume_mm3 = diag["volume_mm3"]
        except Exception as e:
            self.report({'WARNING'}, f"Aviso de cortador: {str(e)}")

        self.report({'INFO'}, f"Objeto '{obj.name}' definido como cortador sólido.")
        return {'FINISHED'}


class CHEST_OT_splitter_generate_preview(bpy.types.Operator):
    """Executa o corte planar ou volumétrico em cópia e gera a visualização prévia das partes A e B"""
    bl_idname = "chest.splitter_generate_preview"
    bl_label = "Gerar Preview do Corte"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.chest_splitter
        return settings.target_object is not None and settings.target_object.type == 'MESH'

    def execute(self, context):
        settings = context.scene.chest_splitter
        target = settings.target_object

        if not target or target.name not in bpy.data.objects or target.type != 'MESH':
            settings.session_status = 'PREVIEW_INVALID'
            self.report({'ERROR'}, "Objeto alvo inválido ou não encontrado.")
            return {'CANCELLED'}

        # Garante session_id exclusivo para cada novo corte/sessão
        if not settings.session_id or settings.session_id == "session_01" or settings.session_status == 'COMMITTED':
            settings.session_id = uuid.uuid4().hex[:12]

        preview_col = get_or_create_collection(context.scene, COLLECTION_PREVIEWS_NAME)

        # Migração segura para cenas legadas caso o alvo ou cópia esteja na coleção de prévias
        if target.name in preview_col.objects:
            preview_col.objects.unlink(target)
            work_col = get_or_create_collection(context.scene, COLLECTION_WORK_NAME)
            if target.name not in work_col.objects:
                work_col.objects.link(target)
            target["chest_role"] = ROLE_WORK_COPY

        # Limpa previews anteriores da sessão sem remover o alvo, cópias ou outros objetos
        cleanup_collection_objects(preview_col, exclude_objects={target}, session_id=settings.session_id)

        # Snapshot de malha avaliada para corte consistente com modificadores (Seção 7)
        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = target.evaluated_get(depsgraph)
        eval_mesh = None
        has_active_modifiers = any(m.show_viewport for m in target.modifiers)
        if has_active_modifiers and settings.split_mode in ('PLANE', 'SOLID'):
            try:
                eval_mesh = eval_obj.to_mesh()
            except Exception:
                eval_mesh = None

        source_mesh_to_cut = eval_mesh if eval_mesh else target.data

        # Prepara malhas de destino
        mesh_a = bpy.data.meshes.new(f"{target.name}_part_a_preview")
        mesh_b = bpy.data.meshes.new(f"{target.name}_part_b_preview")

        unit_scale = get_scene_scale_to_mm(context.scene)

        if settings.split_mode == 'SOLID':
            cutter = settings.solid_cutter_object
            if not cutter or cutter.name not in bpy.data.objects:
                col = find_collection(context.scene, COLLECTION_GUIDES_NAME)
                if col:
                    cutter = col.objects.get(SOLID_CUTTER_NAME)
                    if cutter:
                        settings.solid_cutter_object = cutter

            if not cutter or cutter.name not in bpy.data.objects:
                if eval_mesh:
                    eval_obj.to_mesh_clear()
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                msg = "Nenhum cortador sólido selecionado. Crie uma primitiva ou escolha um objeto existente."
                settings.last_status = msg
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}

            try:
                cutter_diag = validate_solid_cutter(cutter, target, unit_scale=unit_scale)
                settings.solid_cutter_is_manifold = cutter_diag["is_manifold"]
                settings.solid_cutter_triangles = cutter_diag["triangles"]
                settings.solid_cutter_volume_mm3 = cutter_diag["volume_mm3"]
            except SolidCutterValidationError as cve:
                if eval_mesh:
                    eval_obj.to_mesh_clear()
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Cortador inválido: {str(cve)}"
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, str(cve))
                return {'CANCELLED'}

            try:
                report = slice_mesh_by_solid(
                    source_mesh=source_mesh_to_cut,
                    matrix_world=target.matrix_world,
                    cutter_obj=cutter,
                    target_mesh_a=mesh_a,
                    target_mesh_b=mesh_b,
                    invert_sides=settings.invert_sides,
                    unit_scale=unit_scale,
                )
            except NoIntersectionError as e:
                if eval_mesh:
                    eval_obj.to_mesh_clear()
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)

                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Aviso de corte sólido: {str(e)}"
                settings.last_status_level = 'ERROR'
                self.report({'WARNING'}, str(e))
                return {'CANCELLED'}
            except Exception as e:
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Erro no corte sólido: {str(e)}"
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}

        elif settings.split_mode == 'LOOP':
            if not settings.loop_is_captured or not settings.loop_vertex_indices:
                settings.last_status = "Nenhum loop capturado."
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, settings.last_status)
                return {'CANCELLED'}
            if settings.loop_seed_face_index < 0:
                settings.last_status = "Nenhuma região definida."
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, settings.last_status)
                return {'CANCELLED'}
            
            indices = [int(i) for i in settings.loop_vertex_indices.split(',') if i]
            
            from .geometry_loop import slice_mesh_by_loop, slice_mesh_by_loop_extrude, analyze_loop_region
            try:
                # Decisão de comportamento de corte por contorno
                behavior = settings.loop_behavior
                if behavior == 'AUTO':
                    analysis = analyze_loop_region(target, indices, settings.loop_seed_face_index, context.scene)
                    effective_mode = analysis["detected_mode"]
                    settings.loop_detected_mode = effective_mode
                    settings.loop_auto_reason = analysis["reason"]
                else:
                    effective_mode = behavior

                if effective_mode == 'EXTRUDE':
                    loop_res = slice_mesh_by_loop_extrude(
                        target,
                        target.name,
                        indices,
                        settings.loop_seed_face_index,
                        depth_mm=settings.loop_extrude_depth_mm,
                        through_cut=settings.loop_through_cut,
                        scene=context.scene,
                    )
                else:
                    loop_res = slice_mesh_by_loop(target, target.name, indices, settings.loop_seed_face_index, context.scene)

                bm_a, bm_b = loop_res[0], loop_res[1]
                # Sincroniza materiais da malha fonte ANTES do to_mesh para preservar índices de materiais
                mesh_a.materials.clear()
                mesh_b.materials.clear()
                for mat in target.data.materials:
                    mesh_a.materials.append(mat)
                    mesh_b.materials.append(mat)
                bm_a.to_mesh(mesh_a)
                bm_b.to_mesh(mesh_b)
                bm_a.free()
                bm_b.free()
                
                cut_iface = getattr(loop_res, 'interface', None)
                if cut_iface:
                    plane_origin = cut_iface.origin_world
                    plane_normal = cut_iface.normal_a_to_b_world
                    settings.loop_interface_normal = tuple(plane_normal)
                    settings.loop_interface_origin = tuple(plane_origin)
                else:
                    plane_origin = Vector((0, 0, 0))
                    plane_normal = Vector((0, 0, 1))
                
                split_metrics = getattr(loop_res, 'split_result', None)
                report = {
                    "A": split_metrics.part_a_metrics if split_metrics else {},
                    "B": split_metrics.part_b_metrics if split_metrics else {},
                    "sum_volume_mm3": split_metrics.diagnostics_before_connectors.get("sum_volume_mm3", 0.0) if split_metrics else 0.0,
                    "interface": cut_iface,
                }
            except Exception as e:
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Erro no loop: {str(e)}"
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}
        elif settings.split_mode == 'MATERIAL':
            from .geometry_material import slice_mesh_by_material
            if not target.data.materials:
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = "O objeto alvo não possui nenhum material atribuído."
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, settings.last_status)
                return {'CANCELLED'}

            try:
                mat_res = slice_mesh_by_material(
                    target,
                    material_index=settings.material_split_index,
                    depth_mm=settings.material_extrude_depth_mm,
                    scene=context.scene,
                    region_index=settings.material_region_index,
                )
                bm_a, bm_b = mat_res[0], mat_res[1]
                # Sincroniza materiais da malha fonte antes de to_mesh para preservar índices de materiais (M1)
                mesh_a.materials.clear()
                mesh_b.materials.clear()
                for mat in target.data.materials:
                    mesh_a.materials.append(mat)
                    mesh_b.materials.append(mat)
                bm_a.to_mesh(mesh_a)
                bm_b.to_mesh(mesh_b)
                bm_a.free()
                bm_b.free()

                cut_iface = getattr(mat_res, 'interface', None)
                if cut_iface:
                    plane_origin = cut_iface.origin_world
                    plane_normal = cut_iface.normal_a_to_b_world
                    settings.loop_interface_normal = tuple(plane_normal)
                    settings.loop_interface_origin = tuple(plane_origin)
                else:
                    plane_origin = Vector((0, 0, 0))
                    plane_normal = Vector((0, 0, 1))

                split_metrics = getattr(mat_res, 'split_result', None)
                report = {
                    "A": split_metrics.part_a_metrics if split_metrics else {},
                    "B": split_metrics.part_b_metrics if split_metrics else {},
                    "sum_volume_mm3": split_metrics.diagnostics_before_connectors.get("sum_volume_mm3", 0.0) if split_metrics else 0.0,
                    "interface": cut_iface,
                }
            except Exception as e:
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Erro no corte por material: {str(e)}"
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}
        else:
            # Modo PLANAR
            plane_origin, plane_normal = read_plane_geometry(context)
            try:
                report = slice_mesh_by_plane(
                    source_mesh=source_mesh_to_cut,
                    matrix_world=target.matrix_world,
                    plane_origin=plane_origin,
                    plane_normal=plane_normal,
                    target_mesh_a=mesh_a,
                    target_mesh_b=mesh_b,
                    invert_sides=settings.invert_sides,
                    unit_scale=unit_scale,
                )
            except NoIntersectionError as e:
                if eval_mesh:
                    eval_obj.to_mesh_clear()
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Aviso de corte: {str(e)}"
                settings.last_status_level = 'ERROR'
                self.report({'WARNING'}, str(e))
                return {'CANCELLED'}
            except Exception as e:
                if eval_mesh:
                    eval_obj.to_mesh_clear()
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Erro no corte geométrico: {str(e)}"
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}

        # Limpa malha avaliada temporária após término das operações de corte
        if eval_mesh:
            try:
                eval_obj.to_mesh_clear()
            except Exception:
                pass

        # Validação geométrica estrita dos sólidos antes dos encaixes (Seção 6)
        bm_a_chk = bmesh.new()
        bm_a_chk.from_mesh(mesh_a)
        ok_a, msg_a, _ = validate_printable_mesh(bm_a_chk, part_name="Parte A", unit_scale=unit_scale)
        bm_a_chk.free()

        bm_b_chk = bmesh.new()
        bm_b_chk.from_mesh(mesh_b)
        ok_b, msg_b, _ = validate_printable_mesh(bm_b_chk, part_name="Parte B", unit_scale=unit_scale)
        bm_b_chk.free()

        if not ok_a or not ok_b:
            bpy.data.meshes.remove(mesh_a, do_unlink=True)
            bpy.data.meshes.remove(mesh_b, do_unlink=True)
            settings.session_status = 'PREVIEW_INVALID'
            err_msg = msg_a if not ok_a else msg_b
            settings.last_status = err_msg
            settings.last_status_level = 'ERROR'
            self.report({'ERROR'}, err_msg)
            return {'CANCELLED'}

        # Cria objetos de preview
        obj_a = bpy.data.objects.new(PREVIEW_A_NAME, mesh_a)
        obj_b = bpy.data.objects.new(PREVIEW_B_NAME, mesh_b)

        # Associa metadados de sessão e papel para isolamento de ciclo de vida (Seção 4)
        obj_a["chest_session_id"] = settings.session_id
        obj_a["chest_role"] = ROLE_PREVIEW_A
        obj_b["chest_session_id"] = settings.session_id
        obj_b["chest_role"] = ROLE_PREVIEW_B

        # Configura cores de visualização
        if settings.preview_color_mode == 'PARTS':
            obj_a.color = COLOR_PART_A
            obj_b.color = COLOR_PART_B
        else:
            # Em modo MATERIALS, cores do objeto ficam neutras para destacar os materiais reais
            obj_a.color = (1.0, 1.0, 1.0, 1.0)
            obj_b.color = (1.0, 1.0, 1.0, 1.0)

        preview_col.objects.link(obj_a)
        preview_col.objects.link(obj_b)
        # Determina qual parte está geometricamente no topo (maior Z médio no espaço de mundo)
        try:
            az = sum((obj_a.matrix_world @ Vector(c)).z for c in obj_a.bound_box) / 8.0
            bz = sum((obj_b.matrix_world @ Vector(c)).z for c in obj_b.bound_box) / 8.0
            settings.part_a_is_superior = (az >= bz)
        except Exception:
            settings.part_a_is_superior = True

        # Aplica encaixes (macho e cavidade) se ativados na sessão
        if settings.connector_enabled:
            if settings.split_mode in ('SOLID', 'MATERIAL'):
                self.report({'INFO'}, "Encaixes automáticos não são suportados no modo Cortador Sólido / Material.")
            else:
                if settings.split_mode == 'LOOP':
                    norm_a = plane_normal
                else:
                    norm_a = -plane_normal if settings.invert_sides else plane_normal

                if settings.connector_male_part == 'A':
                    male_obj = obj_a
                    female_obj = obj_b
                    norm = norm_a
                else:
                    male_obj = obj_b
                    female_obj = obj_a
                    norm = -norm_a

                try:
                    layout = compute_connector_layout(
                        target_mesh=target.data,
                        matrix_world=target.matrix_world,
                        plane_origin=plane_origin,
                        plane_normal=plane_normal,
                        distribution=settings.connector_distribution,
                        edge_margin_mm=settings.connector_edge_margin_mm,
                        unit_scale=unit_scale,
                        diameter_mm=settings.connector_diameter_mm,
                        clearance_per_side_mm=settings.clearance_per_side_mm,
                        interface=report.get("interface"),
                        connector_type=settings.connector_type,
                        capsule_length_mm=settings.connector_capsule_length_mm,
                    )
                    positions = layout["positions"]
                    major_axis = layout["major_axis"]
                    max_safe_lateral_mm = layout["max_safe_lateral_mm"]
                    settings.connector_max_safe_lateral_mm = max_safe_lateral_mm

                    cap_len = layout.get("adjusted_capsule_length_mm", settings.connector_capsule_length_mm)
                    if settings.connector_type == 'CAPSULE' and cap_len != settings.connector_capsule_length_mm:
                        self.report({'WARNING'}, f"Comprimento lateral ({settings.connector_capsule_length_mm:.1f} mm) ajustado para limite seguro: {cap_len:.1f} mm.")
                        settings.connector_capsule_length_mm = cap_len

                    validate_connectors(
                        positions=positions,
                        diameter_mm=settings.connector_diameter_mm,
                        clearance_per_side_mm=settings.clearance_per_side_mm,
                        unit_scale=unit_scale,
                        connector_type=settings.connector_type,
                        capsule_length_mm=cap_len,
                    )
                    apply_connectors_boolean(
                        obj_male=male_obj,
                        obj_female=female_obj,
                        plane_normal=norm,
                        positions=positions,
                        connector_type=settings.connector_type,
                        diameter_mm=settings.connector_diameter_mm,
                        length_mm=settings.connector_length_mm,
                        chamfer_mm=settings.connector_chamfer_mm,
                        clearance_side_mm=settings.clearance_per_side_mm,
                        end_clearance_mm=settings.end_clearance_mm,
                        unit_scale=unit_scale,
                        capsule_length_mm=cap_len,
                        major_axis=major_axis,
                    )
                except ConnectorValidationError as cve:
                    cleanup_collection_objects(preview_col, exclude_objects={target}, session_id=settings.session_id)
                    target.hide_viewport = False
                    settings.session_status = 'PREVIEW_INVALID'
                    settings.last_status = f"Aviso de encaixe: {str(cve)}"
                    settings.last_status_level = 'ERROR'
                    self.report({'ERROR'}, str(cve))
                    return {'CANCELLED'}
                except Exception as e:
                    cleanup_collection_objects(preview_col, exclude_objects={target}, session_id=settings.session_id)
                    target.hide_viewport = False
                    settings.session_status = 'PREVIEW_INVALID'
                    settings.last_status = f"Erro nos encaixes: {str(e)}"
                    settings.last_status_level = 'ERROR'
                    self.report({'ERROR'}, str(e))
                    return {'CANCELLED'}

        # Re-avalia diagnósticos atualizados e validação estrita final de A e B após encaixes
        for side, p_obj in (("A", obj_a), ("B", obj_b)):
            bm_res = bmesh.new()
            bm_res.from_mesh(p_obj.data)
            ok_res, msg_res, metrics = validate_printable_mesh(bm_res, part_name=f"Parte {side}", unit_scale=unit_scale)
            bm_res.free()
            if not ok_res:
                cleanup_collection_objects(preview_col, exclude_objects={target}, session_id=settings.session_id)
                target.hide_viewport = False
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Resultado inválido após encaixes ({msg_res})."
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, settings.last_status)
                return {'CANCELLED'}

            if side == "A":
                settings.part_a_volume_mm3 = metrics["volume_mm3"]
                settings.part_a_dims_mm = metrics["dims_mm"]
                settings.part_a_triangles = metrics["triangles"]
                settings.part_a_is_manifold = metrics["is_manifold"]
                settings.part_a_non_manifold_edges = metrics["non_manifold_edges"]
                settings.part_a_components = metrics["components"]
            else:
                settings.part_b_volume_mm3 = metrics["volume_mm3"]
                settings.part_b_dims_mm = metrics["dims_mm"]
                settings.part_b_triangles = metrics["triangles"]
                settings.part_b_is_manifold = metrics["is_manifold"]
                settings.part_b_non_manifold_edges = metrics["non_manifold_edges"]
                settings.part_b_components = metrics["components"]

        sum_vol = settings.part_a_volume_mm3 + settings.part_b_volume_mm3
        settings.part_sum_volume_mm3 = sum_vol

        orig_vol = settings.diag_volume_mm3
        if orig_vol > 0:
            diff_pct = abs(sum_vol - orig_vol) / orig_vol * 100.0
            settings.volume_diff_pct = diff_pct
        else:
            settings.volume_diff_pct = 0.0

        # Auto-ajuste inteligente da distância de explosão para pinos longos (Etapa 5)
        if settings.connector_enabled and settings.split_mode not in ('SOLID', 'MATERIAL'):
            min_explosion_needed = settings.connector_length_mm + settings.end_clearance_mm + 15.0
            if settings.explosion_distance_mm < min_explosion_needed:
                settings.explosion_distance_mm = round(min_explosion_needed, 1)
        # Modo Material: a peça extraída precisa sair totalmente da cavidade na vista explodida
        if settings.split_mode == 'MATERIAL':
            min_explosion_needed = settings.material_extrude_depth_mm + 15.0
            if settings.explosion_distance_mm < min_explosion_needed:
                settings.explosion_distance_mm = round(min_explosion_needed, 1)

        # Aplica posição (montado ou explodido)
        update_preview_positions(context.scene)

        # Oculta o objeto original da visualização
        target.hide_viewport = True

        settings.session_input_signature = compute_session_input_signature(context)
        settings.session_status = 'PREVIEW_VALID'
        conn_info = f" (+{settings.connector_distribution} encaixes)" if (settings.connector_enabled and settings.split_mode not in ('SOLID', 'MATERIAL')) else ""
        msg = (
            f"Preview gerado com sucesso{conn_info}! "
            f"Parte A: {settings.part_a_volume_mm3:,.0f} mm³ | "
            f"Parte B: {settings.part_b_volume_mm3:,.0f} mm³"
        )
        settings.last_status = msg
        settings.last_status_level = 'SUCCESS'
        self.report({'INFO'}, msg)

        return {'FINISHED'}




class CHEST_OT_splitter_invert_sides(bpy.types.Operator):
    """Inverte os papéis da Parte A e Parte B do corte"""
    bl_idname = "chest.splitter_invert_sides"
    bl_label = "Inverter Lados A / B"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "chest_splitter", None)
        return settings is not None and settings.session_status != 'COMMITTED'

    def execute(self, context):
        settings = context.scene.chest_splitter
        had_preview = settings.session_status in ('PREVIEW_VALID', 'PREVIEW_STALE')
        settings.invert_sides = not settings.invert_sides
        # Se preview já estiver ativo, regenera automaticamente
        if had_preview:
            bpy.ops.chest.splitter_generate_preview()
        return {'FINISHED'}


class CHEST_OT_splitter_invert_male_female(bpy.types.Operator):
    """Inverte qual parte recebe o macho e qual recebe a cavidade"""
    bl_idname = "chest.splitter_invert_male_female"
    bl_label = "Inverter Macho / Fêmea"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "chest_splitter", None)
        return settings is not None and settings.session_status != 'COMMITTED'

    def execute(self, context):
        settings = context.scene.chest_splitter
        had_preview = settings.session_status in ('PREVIEW_VALID', 'PREVIEW_STALE')
        settings.connector_male_part = 'B' if settings.connector_male_part == 'A' else 'A'
        
        is_top = (settings.connector_male_part == 'A' and settings.part_a_is_superior) or (settings.connector_male_part == 'B' and not settings.part_a_is_superior)
        pos_desc = "Parte Superior" if is_top else "Parte Inferior"
        msg = f"Encaixes invertidos! Pinos (macho) agora na {pos_desc} ({'Parte A' if settings.connector_male_part == 'A' else 'Parte B'})."
        settings.last_status = msg
        settings.last_status_level = 'INFO'
        self.report({'INFO'}, msg)
        if had_preview:
            bpy.ops.chest.splitter_generate_preview()
        return {'FINISHED'}


class CHEST_OT_splitter_apply_connector_preset(bpy.types.Operator):
    """Aplica uma folga recomendada pré-definida para os encaixes"""
    bl_idname = "chest.splitter_apply_connector_preset"
    bl_label = "Aplicar Preset de Folga"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "chest_splitter", None)
        return settings is not None and settings.session_status != 'COMMITTED'

    preset: bpy.props.EnumProperty(
        name="Preset",
        items=[
            ('TIGHT', "Justo", "0,10 mm"),
            ('NORMAL', "Normal", "0,15 mm"),
            ('EASY', "Fácil", "0,20 mm"),
            ('LOOSE', "Solto", "0,25 mm"),
        ],
        default='NORMAL',
    )

    def execute(self, context):
        settings = context.scene.chest_splitter
        had_preview = settings.session_status in ('PREVIEW_VALID', 'PREVIEW_STALE')
        settings.clearance_preset = self.preset
        settings.clearance_per_side_mm = CLEARANCE_PRESETS[self.preset]
        msg = f"Preset '{self.preset}' aplicado (folga por lado: {settings.clearance_per_side_mm:.2f} mm)."
        settings.last_status = msg
        settings.last_status_level = 'INFO'
        self.report({'INFO'}, msg)
        if had_preview:
            bpy.ops.chest.splitter_generate_preview()
        return {'FINISHED'}



class CHEST_OT_splitter_commit_parts(bpy.types.Operator):
    """Confirma o corte e move as partes finais para a coleção definitiva"""
    bl_idname = "chest.splitter_commit_parts"
    bl_label = "Confirmar Divisão (Criar Partes Finais)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.chest_splitter
        return settings.session_status == 'PREVIEW_VALID'

    def execute(self, context):
        settings = context.scene.chest_splitter
        target = settings.target_object

        # Validação de atualidade antes de confirmar (Seção 5)
        valid, reason = verify_preview_current(context)
        if not valid:
            settings.session_status = 'PREVIEW_STALE'
            settings.last_status = f"{reason} Atualize a prévia antes de criar as peças finais."
            settings.last_status_level = 'WARNING'
            self.report({'WARNING'}, settings.last_status)
            return {'CANCELLED'}

        preview_col = get_or_create_collection(context.scene, COLLECTION_PREVIEWS_NAME)
        parts_col = get_or_create_collection(context.scene, COLLECTION_PARTS_NAME)

        obj_a = preview_col.objects.get(PREVIEW_A_NAME)
        obj_b = preview_col.objects.get(PREVIEW_B_NAME)

        if not obj_a or not obj_b:
            self.report({'ERROR'}, "Objetos de preview não encontrados para confirmação.")
            return {'CANCELLED'}

        # Revalida geometria das partes (podem ter sido editadas no Edit Mode)
        unit_scale = get_scene_scale_to_mm(context.scene)
        check_solid = settings.split_mode != 'MATERIAL'
        
        preview_parts = get_current_session_parts(context.scene)
        for part_obj in preview_parts:
            bm_part = bmesh.new()
            bm_part.from_mesh(part_obj.data)
            is_valid, msg, _ = validate_printable_mesh(bm_part, part_name=part_obj.name, unit_scale=unit_scale, check_manifold=check_solid)
            bm_part.free()
            if not is_valid:
                settings.session_status = 'PREVIEW_STALE'
                settings.last_status = f"Erro de integridade na peça gerada: {msg}"
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, settings.last_status)
                return {'CANCELLED'}

        base_name = target.name.replace(WORK_COPY_SUFFIX, "")
        final_name_a = f"{base_name}{PART_A_SUFFIX}"
        final_name_b = f"{base_name}{PART_B_SUFFIX}"

        # Reseta localizações para posição montada original
        obj_a.location = Vector((0.0, 0.0, 0.0))
        obj_b.location = Vector((0.0, 0.0, 0.0))

        # Renomeia objetos e malhas
        obj_a.name = final_name_a
        obj_a.data.name = f"{final_name_a}_Mesh"
        obj_b.name = final_name_b
        obj_b.data.name = f"{final_name_b}_Mesh"

        # Adiciona metadados rastreáveis e isolamento por sessão (Seção 4)
        obj_a["chest_session_id"] = settings.session_id
        obj_a["chest_role"] = ROLE_COMMITTED_PART
        obj_a["chest_splitter_session_id"] = settings.session_id
        obj_a["chest_splitter_part"] = "A"

        obj_b["chest_session_id"] = settings.session_id
        obj_b["chest_role"] = ROLE_COMMITTED_PART
        obj_b["chest_splitter_session_id"] = settings.session_id
        obj_b["chest_splitter_part"] = "B"

        # Transfere para a coleção de partes finais
        preview_col.objects.unlink(obj_a)
        preview_col.objects.unlink(obj_b)
        parts_col.objects.link(obj_a)
        parts_col.objects.link(obj_b)

        # Oculta guias de corte
        guides_col = find_collection(context.scene, COLLECTION_GUIDES_NAME)
        if guides_col:
            for g_name in (PLANE_GUIDE_NAME, SOLID_CUTTER_NAME):
                guide_obj = guides_col.objects.get(g_name)
                if guide_obj:
                    guide_obj.hide_viewport = True

        settings.session_status = 'COMMITTED'
        msg = f"Corte confirmado! Peças finais criadas: '{final_name_a}' e '{final_name_b}'."
        settings.last_status = msg
        settings.last_status_level = 'SUCCESS'
        self.report({'INFO'}, msg)

        return {'FINISHED'}


class CHEST_OT_splitter_restore_original(bpy.types.Operator):
    """Descarta o preview e restaura a visualização do modelo original"""
    bl_idname = "chest.splitter_restore_original"
    bl_label = "Restaurar Original"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.chest_splitter
        return settings.target_object is not None

    def execute(self, context):
        settings = context.scene.chest_splitter
        target = settings.target_object

        # Limpa previews temporários da sessão atual sem apagar o alvo
        preview_col = find_collection(context.scene, COLLECTION_PREVIEWS_NAME)
        if preview_col:
            cleanup_collection_objects(preview_col, exclude_objects={target} if target else None, session_id=settings.session_id)

        # Restaura visibilidade do alvo e do original se for cópia de trabalho
        if target and target.name in bpy.data.objects:
            orig_name = target.get("chest_original_target")
            if orig_name and orig_name in bpy.data.objects:
                orig_obj = bpy.data.objects[orig_name]
                orig_obj.hide_viewport = False
                orig_obj.hide_set(False)
                settings.target_object = orig_obj
                # Limpa a cópia de trabalho da coleção de trabalho
                m = target.data
                bpy.data.objects.remove(target, do_unlink=True)
                if m and m.users == 0:
                    bpy.data.meshes.remove(m, do_unlink=True)
            else:
                target.hide_viewport = False
                target.hide_set(False)


        settings.session_status = 'CONFIGURED'
        msg = "Visualização do modelo original restaurada."
        settings.last_status = msg
        settings.last_status_level = 'INFO'
        self.report({'INFO'}, msg)

        return {'FINISHED'}


class CHEST_OT_splitter_redo_session(bpy.types.Operator):
    """Reabre uma sessão confirmada para ajustar novos cortes ou refazer"""
    bl_idname = "chest.splitter_redo_session"
    bl_label = "Refazer / Ajustar Sessão"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.chest_splitter
        guides_col = find_collection(context.scene, COLLECTION_GUIDES_NAME)
        if guides_col:
            for g_name in (PLANE_GUIDE_NAME, SOLID_CUTTER_NAME):
                guide_obj = guides_col.objects.get(g_name)
                if guide_obj:
                    guide_obj.hide_viewport = False

        target = settings.target_object
        if target and target.name in bpy.data.objects:
            target.hide_viewport = False

        settings.session_status = 'CONFIGURED'
        msg = "Sessão pronta para novo ajuste de corte."
        settings.last_status = msg
        settings.last_status_level = 'INFO'
        return {'FINISHED'}


class CHEST_OT_splitter_capture_loop(bpy.types.Operator):
    """Captura e valida um loop fechado de arestas no Modo D"""
    bl_idname = "chest.splitter_capture_loop"
    bl_label = "Capturar Loop Fechado"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.chest_splitter
        return settings.target_object is not None and settings.target_object.type == 'MESH' and context.active_object == settings.target_object

    def execute(self, context):
        settings = context.scene.chest_splitter
        obj = settings.target_object
        
        from .geometry_loop import capture_edge_loop, get_topology_signature
        
        success, indices, is_planar, dev_mm, err_msg = capture_edge_loop(obj)
        
        if not success:
            settings.loop_is_captured = False
            settings.last_status = f"Erro na captura: {err_msg}"
            settings.last_status_level = 'ERROR'
            self.report({'ERROR'}, err_msg)
            return {'CANCELLED'}
            
        settings.loop_is_captured = True
        settings.loop_vertex_count = len(indices)
        settings.loop_vertex_indices = ",".join(str(i) for i in indices)
        settings.loop_is_planar = is_planar
        settings.loop_planarity_deviation_mm = dev_mm
        settings.loop_topology_signature = get_topology_signature(obj)
        
        if not is_planar:
            msg = f"Aviso: Loop capturado com {len(indices)} vértices, mas NÃO é perfeitamente plano (desvio {dev_mm:.2f}mm). O corte planar direto pode ter gaps na tampa interna."
            settings.last_status = msg
            settings.last_status_level = 'WARNING'
            self.report({'WARNING'}, msg)
        else:
            msg = f"Sucesso: Loop planar capturado com {len(indices)} vértices."
            settings.last_status = msg
            settings.last_status_level = 'SUCCESS'
            self.report({'INFO'}, msg)
            
        return {'FINISHED'}


class CHEST_OT_splitter_define_seed_face(bpy.types.Operator):
    """Define a face semente (selecionada) que indica qual região será a Parte A"""
    bl_idname = "chest.splitter_define_seed_face"
    bl_label = "Definir Região a Separar"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.chest_splitter
        return settings.target_object is not None and settings.target_object.type == 'MESH' and context.active_object == settings.target_object

    def execute(self, context):
        settings = context.scene.chest_splitter
        obj = settings.target_object
        
        from .geometry_loop import get_selected_seed_face
        
        seed_idx = get_selected_seed_face(obj)
        if seed_idx < 0:
            settings.last_status = "Selecione pelo menos uma face em Edit Mode."
            settings.last_status_level = 'ERROR'
            self.report({'ERROR'}, settings.last_status)
            return {'CANCELLED'}
            
        settings.loop_seed_face_index = seed_idx
        
        msg = f"Sucesso: Face {seed_idx} definida como semente para a Parte A."
        settings.last_status = msg
        settings.last_status_level = 'SUCCESS'
        self.report({'INFO'}, msg)
            
        return {'FINISHED'}


class CHEST_OT_splitter_separate_by_material(bpy.types.Operator):
    """Separa as peças divididas em sub-objetos individuais por material/cor para impressão 3D multicolor"""
    bl_idname = "chest.splitter_separate_by_material"
    bl_label = "Separar Peças por Cores / Materiais"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.chest_splitter
        return settings.session_status == 'COMMITTED'

    def execute(self, context):
        settings = context.scene.chest_splitter

        objs_to_process = get_current_session_parts(context.scene)
        if not objs_to_process:
            self.report({'WARNING'}, "Nenhuma peça da sessão ativa encontrada para separação.")
            return {'CANCELLED'}

        parts_col = get_or_create_collection(context.scene, COLLECTION_PARTS_NAME)
        target_col = parts_col

        from .io_export import separate_object_by_material

        created_count = 0
        open_edge_count = 0
        for src_obj in objs_to_process:
            if len(src_obj.data.materials) > 1:
                sub_objs = separate_object_by_material(src_obj, target_col)
                if len(sub_objs) > 1:
                    created_count += len(sub_objs)
                    for sub in sub_objs:
                        sub["chest_session_id"] = settings.session_id
                        sub["chest_role"] = ROLE_SUBPART_MATERIAL
                        if sub.get("open_edges", 0) > 0:
                            open_edge_count += 1
                    if src_obj.name in target_col.objects:
                        target_col.objects.unlink(src_obj)

        if created_count > 0:
            if open_edge_count > 0:
                msg = (
                    f"{created_count} sub-peças por cor/material criadas na coleção '{target_col.name}'. "
                    f"Nota: {open_edge_count} gerada(s) como casca superficial aberta. "
                    "Para peças sólidas individuais, use o modo de corte 'Material' com Profundidade."
                )
                settings.last_status_level = 'WARNING'
                self.report({'WARNING'}, msg)
            else:
                msg = f"{created_count} sub-peças por cor/material criadas na coleção '{target_col.name}'."
                settings.last_status_level = 'SUCCESS'
                self.report({'INFO'}, msg)
            settings.last_status = msg
            return {'FINISHED'}
        else:
            msg = "As peças já possuem apenas 1 material ou não possuem múltiplos materiais."
            settings.last_status = msg
            settings.last_status_level = 'INFO'
            self.report({'INFO'}, msg)
            return {'FINISHED'}


class CHEST_OT_splitter_export_parts(bpy.types.Operator):
    """Exporta as partes cortadas nos formatos 3MF Multimaterial, STL por Material ou OBJ"""
    bl_idname = "chest.splitter_export_parts"
    bl_label = "Exportar Peças para Impressão 3D"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.chest_splitter
        return settings.session_status in ('PREVIEW_VALID', 'COMMITTED')

    def execute(self, context):
        settings = context.scene.chest_splitter

        if settings.session_status == 'PREVIEW_VALID':
            is_current, reason = verify_preview_current(context)
            if not is_current:
                settings.session_status = 'PREVIEW_STALE'
                settings.last_status = f"Prévia desatualizada ({reason}). Gere a prévia novamente antes de exportar."
                settings.last_status_level = 'WARNING'
                self.report({'WARNING'}, settings.last_status)
                return {'CANCELLED'}

        objects = get_current_session_parts(context.scene)
        if not objects:
            self.report({'ERROR'}, "Nenhuma peça da sessão ativa encontrada para exportação.")
            return {'CANCELLED'}

        # Validação estrita de integridade e existência das peças antes da exportação (Seção 6)
        unit_scale = get_scene_scale_to_mm(context.scene)
        check_solid = settings.export_format == 'STL_PARTS'
        
        for obj in objects:
            if not obj or obj.type != 'MESH' or not obj.data:
                self.report({'ERROR'}, "Um ou mais objetos da sessão foram removidos ou corrompidos.")
                return {'CANCELLED'}
                
            bm_part = bmesh.new()
            bm_part.from_mesh(obj.data)
            is_valid, msg, _ = validate_printable_mesh(bm_part, part_name=obj.name, unit_scale=unit_scale, check_manifold=check_solid)
            bm_part.free()
            
            if not is_valid:
                self.report({'ERROR'}, f"Geometria inválida ({msg}). Exporte falhou.")
                return {'CANCELLED'}

        raw_dir = settings.export_directory
        export_dir = bpy.path.abspath(raw_dir) if raw_dir else ""
        if not export_dir or export_dir in ("//", ""):
            if bpy.data.is_saved and bpy.data.filepath:
                export_dir = os.path.dirname(bpy.data.filepath)
            else:
                desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
                if os.path.exists(desktop_dir):
                    export_dir = desktop_dir
                else:
                    import tempfile
                    export_dir = tempfile.gettempdir()

        os.makedirs(export_dir, exist_ok=True)
        unit_scale = get_scene_scale_to_mm(context.scene)
        target = settings.target_object
        base_name = target.name if target else "Chest_Model"
        base_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-', '.')).rstrip('.')

        from .io_export import export_objects_to_3mf, export_objects_to_stl_by_material

        prev_selected = list(context.selected_objects) if context else []
        prev_active = context.view_layer.objects.active if context and context.view_layer else None
        prev_mode = context.active_object.mode if context and context.active_object else 'OBJECT'

        if context.active_object and context.active_object.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass

        loc_backup = {}
        # Na visualização explodida, restaura a posição montada canônica temporariamente para exportação (Seção 4)
        if settings.session_status == 'PREVIEW_VALID' and settings.view_mode == 'EXPLODED':
            for o in objects:
                loc_backup[o] = o.location.copy()
                o.location = Vector((0.0, 0.0, 0.0))
            context.view_layer.update()

        try:
            if settings.export_format == '3MF':
                out_path = os.path.join(export_dir, f"{base_name}__parts.3mf")
                export_objects_to_3mf(objects, out_path, unit_scale=unit_scale)
                msg = f"Arquivo 3MF Multimaterial exportado: '{out_path}'"
                settings.last_status = msg
                settings.last_status_level = 'SUCCESS'
                self.report({'INFO'}, msg)
                return {'FINISHED'}

            elif settings.export_format == 'STL_PER_MATERIAL':
                try:
                    exported = export_objects_to_stl_by_material(objects, export_dir, unit_scale=unit_scale)
                    msg = f"{len(exported)} arquivos STL por cor exportados em '{export_dir}'"
                    settings.last_status = msg
                except ValueError as ve:
                    self.report({'ERROR'}, str(ve))
                    return {'CANCELLED'}
                settings.last_status_level = 'SUCCESS'
                self.report({'INFO'}, msg)
                return {'FINISHED'}

            elif settings.export_format == 'STL_PARTS':
                exported = []
                for obj in objects:
                    safe_o = "".join(c for c in obj.name if c.isalnum() or c in ('_', '-', '.')).rstrip('.')
                    p = os.path.join(export_dir, f"{safe_o}.stl")
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                    if hasattr(bpy.ops.wm, "stl_export"):
                        res = bpy.ops.wm.stl_export(
                            filepath=p,
                            export_selected_objects=True,
                            global_scale=unit_scale,
                            use_scene_unit=False,
                            apply_modifiers=True,
                        )
                        if 'FINISHED' not in res:
                            raise RuntimeError(f"Falha ao exportar STL '{p}': {res}")
                    else:
                        bpy.ops.export_mesh.stl(
                            filepath=p,
                            use_selection=True,
                            global_scale=unit_scale,
                            use_scene_unit=False,
                        )
                    exported.append(p)
                msg = f"{len(exported)} peças STL exportadas em '{export_dir}'"
                settings.last_status = msg
                settings.last_status_level = 'SUCCESS'
                self.report({'INFO'}, msg)
                return {'FINISHED'}

            elif settings.export_format == 'OBJ':
                out_path = os.path.join(export_dir, f"{base_name}__parts.obj")
                bpy.ops.object.select_all(action='DESELECT')
                for o in objects:
                    o.select_set(True)
                if objects:
                    context.view_layer.objects.active = objects[0]
                if hasattr(bpy.ops.wm, "obj_export"):
                    res = bpy.ops.wm.obj_export(
                        filepath=out_path,
                        export_selected_objects=True,
                        export_materials=True,
                        global_scale=unit_scale,
                        apply_modifiers=True,
                    )
                    if 'FINISHED' not in res:
                        raise RuntimeError(f"Falha ao exportar OBJ '{out_path}': {res}")
                else:
                    bpy.ops.export_scene.obj(
                        filepath=out_path,
                        use_selection=True,
                        global_scale=unit_scale,
                    )
                msg = f"Arquivo OBJ com materiais exportado (escala mm): '{out_path}'"
                settings.last_status = msg
                settings.last_status_level = 'SUCCESS'
                self.report({'INFO'}, msg)
                return {'FINISHED'}

            else:
                self.report({'ERROR'}, f"Formato de exportação desconhecido: {settings.export_format}")
                return {'CANCELLED'}

        except Exception as e:
            msg = f"Falha na exportação: {str(e)}"
            settings.last_status = msg
            settings.last_status_level = 'ERROR'
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        finally:
            if loc_backup:
                for o, loc in loc_backup.items():
                    if o.name in bpy.data.objects:
                        o.location = loc
                context.view_layer.update()

            if context and hasattr(context, "view_layer"):
                for o in context.selected_objects:
                    o.select_set(False)
                for o in prev_selected:
                    if o.name in bpy.data.objects:
                        o.select_set(True)
                if prev_active and prev_active.name in bpy.data.objects:
                    context.view_layer.objects.active = prev_active
                if prev_mode != 'OBJECT' and prev_active and prev_active.name in bpy.data.objects:
                    try:
                        bpy.ops.object.mode_set(mode=prev_mode)
                    except Exception:
                        pass


class CHEST_OT_splitter_help(bpy.types.Operator):
    """Exibe ajuda contextual e dicas de uso detalhadas para iniciantes"""
    bl_idname = "chest.splitter_help"
    bl_label = "Ajuda"
    bl_options = {'INTERNAL'}

    topic: bpy.props.StringProperty(
        name="Tópico",
        default="target_model",
        options={'SKIP_SAVE'},
    )

    @classmethod
    def description(cls, context, properties):
        from .translations import get_help_tooltip
        return get_help_tooltip(properties.topic)

    def execute(self, context):
        from .translations import get_help_popup_content
        title, lines = get_help_popup_content(self.topic)

        if not bpy.app.background and hasattr(context, "window_manager") and context.window_manager:
            def draw_popup(self_menu, ctx):
                layout = self_menu.layout
                layout.label(text=title, icon='INFO')
                layout.separator()
                for line in lines:
                    layout.label(text=line)

            try:
                context.window_manager.popup_menu(draw_popup, title=title, icon='QUESTION')
            except Exception:
                pass
class CHEST_OT_splitter_select_split_material(bpy.types.Operator):
    """Seleciona o material (e a região) a ser isolado como Parte A"""
    bl_idname = "chest.splitter_select_split_material"
    bl_label = "Selecionar Material"
    bl_options = {'INTERNAL', 'UNDO'}

    material_index: bpy.props.IntProperty(name="Índice", default=0)
    region_index: bpy.props.IntProperty(name="Região", default=0)

    def execute(self, context):
        settings = context.scene.chest_splitter
        settings.material_split_index = self.material_index
        settings.material_region_index = self.region_index
        for area in context.screen.areas if context.screen else []:
            area.tag_redraw()
        return {'FINISHED'}


class CHEST_OT_splitter_pick_material_region(bpy.types.Operator):
    """Usa a face selecionada (Modo de Edição) para escolher a cor e a área a extrair"""
    bl_idname = "chest.splitter_pick_material_region"
    bl_label = "Usar Face Selecionada"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.chest_splitter
        target = settings.target_object
        if not target or target.type != 'MESH':
            self.report({'ERROR'}, "Defina um objeto alvo primeiro.")
            return {'CANCELLED'}
        was_edit = (target.mode == 'EDIT')
        if was_edit:
            target.update_from_editmode()
        face_idx = -1
        active = target.data.polygons.active
        if 0 <= active < len(target.data.polygons) and target.data.polygons[active].select:
            face_idx = active
        else:
            for p in target.data.polygons:
                if p.select:
                    face_idx = p.index
                    break
        if face_idx < 0:
            self.report({'ERROR'}, "Selecione uma face da área colorida no Modo de Edição.")
            return {'CANCELLED'}
        from .geometry_material import find_region_of_face
        mat_idx, reg_idx = find_region_of_face(target, face_idx)
        if mat_idx < 0 or reg_idx < 0:
            self.report({'ERROR'}, "Não foi possível identificar a área da face selecionada.")
            return {'CANCELLED'}
        settings.material_split_index = mat_idx
        settings.material_region_index = reg_idx
        self.report({'INFO'}, f"Área selecionada: material #{mat_idx}, região {reg_idx + 1}.")
        return {'FINISHED'}


classes = (
    CHEST_OT_splitter_set_target,
    CHEST_OT_splitter_clear_target,
    CHEST_OT_splitter_create_work_copy,
    CHEST_OT_splitter_create_or_focus_guide,
    CHEST_OT_splitter_align_plane,
    CHEST_OT_splitter_create_or_focus_solid_cutter,
    CHEST_OT_splitter_select_existing_cutter,
    CHEST_OT_splitter_generate_preview,
    CHEST_OT_splitter_invert_sides,
    CHEST_OT_splitter_invert_male_female,
    CHEST_OT_splitter_apply_connector_preset,
    CHEST_OT_splitter_commit_parts,
    CHEST_OT_splitter_restore_original,
    CHEST_OT_splitter_redo_session,
    CHEST_OT_splitter_capture_loop,
    CHEST_OT_splitter_define_seed_face,
    CHEST_OT_splitter_separate_by_material,
    CHEST_OT_splitter_export_parts,
    CHEST_OT_splitter_help,
    CHEST_OT_splitter_select_split_material,
    CHEST_OT_splitter_pick_material_region,
)



_in_depsgraph_handler = False


@persistent
def on_depsgraph_update_post(scene, depsgraph):
    """Monitora alterações no alvo, cortador ou cena para invalidar prévias obsoletas em tempo real."""
    global _in_depsgraph_handler
    if _in_depsgraph_handler:
        return
    if not scene or not hasattr(scene, "chest_splitter"):
        return
    settings = scene.chest_splitter
    if settings.session_status != 'PREVIEW_VALID':
        return

    target = settings.target_object
    cutter = None
    if settings.split_mode == 'SOLID':
        cutter = settings.solid_cutter_object
    elif settings.split_mode == 'PLANE':
        col = find_collection(scene, COLLECTION_GUIDES_NAME)
        cutter = col.objects.get(PLANE_GUIDE_NAME) if col else None

    relevant_objects = {o for o in (target, cutter) if o is not None}
    if not relevant_objects:
        return

    updated = False
    for update in depsgraph.updates:
        if update.id in relevant_objects or update.id == scene:
            updated = True
            break

    if not updated:
        return

    _in_depsgraph_handler = True
    try:
        curr_sig = compute_session_input_signature(bpy.context)
        if settings.session_input_signature and curr_sig != settings.session_input_signature:
            settings.session_status = 'PREVIEW_STALE'
            settings.last_status = "O modelo alvo ou cortador foi modificado. Atualize a prévia antes de continuar."
            settings.last_status_level = 'WARNING'
    except Exception:
        pass
    finally:
        _in_depsgraph_handler = False


def register_handlers():
    """Registra handlers de depsgraph no Blender."""
    if on_depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update_post)


def unregister_handlers():
    """Remove handlers de depsgraph do Blender."""
    if on_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update_post)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    register_handlers()


def unregister():
    unregister_handlers()
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

