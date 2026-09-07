"""Operadores do Blender para o Chest Part Splitter (Fase 1 - Corte por Plano)."""

import math
from typing import Optional
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler, Quaternion

from .constants import (
    COLLECTION_GUIDES_NAME,
    COLLECTION_PREVIEWS_NAME,
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



def cleanup_collection_objects(collection: bpy.types.Collection):
    """Remove de forma segura todos os objetos e dados de malha de uma coleção."""
    objs_to_remove = list(collection.objects)
    for obj in objs_to_remove:
        mesh_data = obj.data if obj.type == 'MESH' else None
        collection.objects.unlink(obj)
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data, do_unlink=True)


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

        preview_col = get_or_create_collection(context.scene, COLLECTION_PREVIEWS_NAME)
        preview_col.objects.link(new_obj)

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
                    face_normal_world = (target.matrix_world.to_3x3() @ active_face.normal).normalized()
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

        preview_col = get_or_create_collection(context.scene, COLLECTION_PREVIEWS_NAME)
        # Limpa previews anteriores sem deixar malhas órfãs
        cleanup_collection_objects(preview_col)

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
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Cortador inválido: {str(cve)}"
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, str(cve))
                return {'CANCELLED'}

            try:
                report = slice_mesh_by_solid(
                    source_mesh=target.data,
                    matrix_world=target.matrix_world,
                    cutter_obj=cutter,
                    target_mesh_a=mesh_a,
                    target_mesh_b=mesh_b,
                    invert_sides=settings.invert_sides,
                    unit_scale=unit_scale,
                )
            except NoIntersectionError as e:
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

        else:
            # Modo PLANAR
            plane_origin, plane_normal = read_plane_geometry(context)
            try:
                report = slice_mesh_by_plane(
                    source_mesh=target.data,
                    matrix_world=target.matrix_world,
                    plane_origin=plane_origin,
                    plane_normal=plane_normal,
                    target_mesh_a=mesh_a,
                    target_mesh_b=mesh_b,
                    invert_sides=settings.invert_sides,
                    unit_scale=unit_scale,
                )
            except NoIntersectionError as e:
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Aviso de corte: {str(e)}"
                settings.last_status_level = 'ERROR'
                self.report({'WARNING'}, str(e))
                return {'CANCELLED'}
            except Exception as e:
                bpy.data.meshes.remove(mesh_a, do_unlink=True)
                bpy.data.meshes.remove(mesh_b, do_unlink=True)
                settings.session_status = 'PREVIEW_INVALID'
                settings.last_status = f"Erro no corte geométrico: {str(e)}"
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}

        # Cria objetos de preview
        obj_a = bpy.data.objects.new(PREVIEW_A_NAME, mesh_a)
        obj_b = bpy.data.objects.new(PREVIEW_B_NAME, mesh_b)

        # Configura cores de visualização
        obj_a.color = COLOR_PART_A
        obj_b.color = COLOR_PART_B

        preview_col.objects.link(obj_a)
        preview_col.objects.link(obj_b)

        # Aplica encaixes (macho e cavidade) se ativados na sessão
        if settings.connector_enabled:
            if settings.split_mode == 'SOLID':
                self.report({'INFO'}, "Encaixes automáticos são suportados no modo Plano.")
            else:
                if settings.connector_male_part == 'A':
                    male_obj = obj_a
                    female_obj = obj_b
                    norm = plane_normal
                else:
                    male_obj = obj_b
                    female_obj = obj_a
                    norm = -plane_normal

            try:
                positions = compute_connector_positions(
                    target_mesh=target.data,
                    matrix_world=target.matrix_world,
                    plane_origin=plane_origin,
                    plane_normal=plane_normal,
                    distribution=settings.connector_distribution,
                    edge_margin_mm=settings.connector_edge_margin_mm,
                    unit_scale=unit_scale,
                )
                validate_connectors(
                    positions=positions,
                    diameter_mm=settings.connector_diameter_mm,
                    clearance_per_side_mm=settings.clearance_per_side_mm,
                    unit_scale=unit_scale,
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
                )
            except ConnectorValidationError as cve:
                settings.last_status = f"Aviso de encaixe: {str(cve)}"
                settings.last_status_level = 'WARNING'
                self.report({'WARNING'}, str(cve))
            except Exception as e:
                settings.last_status = f"Erro nos encaixes: {str(e)}"
                settings.last_status_level = 'ERROR'
                self.report({'ERROR'}, str(e))

        # Re-avalia diagnósticos atualizados de A e B após encaixes
        for side, p_obj in (("A", obj_a), ("B", obj_b)):
            bm_res = bmesh.new()
            bm_res.from_mesh(p_obj.data)
            metrics = evaluate_bmesh_metrics(bm_res, unit_scale=unit_scale)
            bm_res.free()
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

        # Aplica posição (montado ou explodido)
        update_preview_positions(context.scene)

        # Oculta o objeto original da visualização
        target.hide_viewport = True

        settings.session_status = 'PREVIEW_VALID'
        conn_info = f" (+{settings.connector_distribution} encaixes)" if settings.connector_enabled else ""
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

    def execute(self, context):
        settings = context.scene.chest_splitter
        settings.invert_sides = not settings.invert_sides
        # Se preview já estiver ativo, regenera automaticamente
        if settings.session_status == 'PREVIEW_VALID':
            bpy.ops.chest.splitter_generate_preview()
        return {'FINISHED'}


class CHEST_OT_splitter_invert_male_female(bpy.types.Operator):
    """Inverte qual parte recebe o macho e qual recebe a cavidade"""
    bl_idname = "chest.splitter_invert_male_female"
    bl_label = "Inverter Macho / Fêmea"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.chest_splitter
        settings.connector_male_part = 'B' if settings.connector_male_part == 'A' else 'A'
        msg = f"Macho agora na Parte {settings.connector_male_part} (Cavidade na Parte {'B' if settings.connector_male_part == 'A' else 'A'})."
        settings.last_status = msg
        settings.last_status_level = 'INFO'
        self.report({'INFO'}, msg)
        if settings.session_status == 'PREVIEW_VALID':
            bpy.ops.chest.splitter_generate_preview()
        return {'FINISHED'}


class CHEST_OT_splitter_apply_connector_preset(bpy.types.Operator):
    """Aplica uma folga recomendada pré-definida para os encaixes"""
    bl_idname = "chest.splitter_apply_connector_preset"
    bl_label = "Aplicar Preset de Folga"
    bl_options = {'REGISTER', 'UNDO'}

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
        settings.clearance_preset = self.preset
        settings.clearance_per_side_mm = CLEARANCE_PRESETS[self.preset]
        msg = f"Preset '{self.preset}' aplicado (folga por lado: {settings.clearance_per_side_mm:.2f} mm)."
        settings.last_status = msg
        settings.last_status_level = 'INFO'
        self.report({'INFO'}, msg)
        if settings.session_status == 'PREVIEW_VALID':
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
        preview_col = get_or_create_collection(context.scene, COLLECTION_PREVIEWS_NAME)
        parts_col = get_or_create_collection(context.scene, COLLECTION_PARTS_NAME)

        obj_a = preview_col.objects.get(PREVIEW_A_NAME)
        obj_b = preview_col.objects.get(PREVIEW_B_NAME)

        if not obj_a or not obj_b:
            self.report({'ERROR'}, "Objetos de preview não encontrados para confirmação.")
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

        # Adiciona metadados rastreáveis
        obj_a["chest_splitter_session_id"] = settings.session_id
        obj_a["chest_splitter_part"] = "A"
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

        # Limpa previews temporários
        preview_col = find_collection(context.scene, COLLECTION_PREVIEWS_NAME)
        if preview_col:
            cleanup_collection_objects(preview_col)

        # Restaura visibilidade do alvo
        if target and target.name in bpy.data.objects:
            target.hide_viewport = False

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
