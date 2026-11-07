"""Serviço de preparação de corte, frame compartilhado e superfície de encaixe.

Implementa a separação de responsabilidades (Etapa B / Seção 5 do Plano):
1. prepare_split_candidates: extrai o corte sem pinos e constrói a CutInterface formal.
2. Frame único: conversões UV <-> Mundo montado <-> Espaço explodido sem divergência.
3. Raycast e picking precisos sobre a superfície física de contato.
4. Avaliação determinística por ID de cada conector manual.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import math

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .geometry_contract import CutInterface
from .diagnostic import get_scene_scale_to_mm


@dataclass
class PreparedSplit:
    """Dados preparados do corte sem pinos para edição e geração."""
    cut_signature: str
    configuration: tuple
    layout_key: tuple = field(default=None, init=False)
    layout: dict = field(default=None, init=False)
    target_name: str
    split_mode: str
    interface: CutInterface
    surface_origin: Vector
    surface_normal: Vector
    axis_u: Vector
    axis_v: Vector
    unit_scale: float
    male_side: str
    is_planar: bool = True
    contact_triangles_world: List[Tuple[Vector, Vector, Vector]] = field(default_factory=list)
    bvh_tree: Optional[BVHTree] = None

    def world_to_uv_mm(self, point_assembled_world: Vector) -> Tuple[float, float]:
        """Converte ponto montado 3D para UV da interface em milímetros."""
        u_bu, v_bu = self.interface.world_to_uv(point_assembled_world)
        return (u_bu * self.unit_scale, v_bu * self.unit_scale)

    def uv_mm_to_world(self, u_mm: float, v_mm: float) -> Vector:
        """Converte UV da interface em milímetros para ponto montado 3D."""
        u_bu = u_mm / self.unit_scale
        v_bu = v_mm / self.unit_scale
        from .geometry_contract import interface_point
        return interface_point(self.interface, u_bu, v_bu)


# Cache em memória do último corte preparado
_CACHED_PREPARED_SPLIT: Optional[PreparedSplit] = None


def compute_cut_signature(settings: Any, target: bpy.types.Object, scene=None) -> str:
    """Gera hash determinístico dos parâmetros que alteram a geometria do corte sem pinos."""
    from .input_state import cut_signature
    return cut_signature(settings, target, scene or bpy.context.scene)



def set_cached_prepared_split(prepared):
    global _CACHED_PREPARED_SPLIT
    _CACHED_PREPARED_SPLIT = prepared


def get_cached_prepared_split() -> Optional[PreparedSplit]:
    """Retorna o PreparedSplit em cache se disponível."""
    global _CACHED_PREPARED_SPLIT
    return _CACHED_PREPARED_SPLIT


def clear_prepared_split_cache():
    """Invalida o cache de corte preparado e a grade de posicionamento."""
    global _CACHED_PREPARED_SPLIT
    _CACHED_PREPARED_SPLIT = None
    try:
        from .gpu_drawing import clear_grid_cache
        clear_grid_cache()
    except Exception:
        pass


def prepare_split_candidates(context: bpy.types.Context, force_recompute: bool = False) -> PreparedSplit:
    """Prepara o corte sem encaixes, garantindo uma única CutInterface e superfície útil de contato.
    
    Compatível com PLANE, LOOP, MATERIAL e SOLID.
    Preserva a seleção de modo/arestas se o usuário estiver em Edit Mode.
    """
    global _CACHED_PREPARED_SPLIT
    settings = context.scene.chest_splitter
    target = getattr(settings, "target_object", None)
    from .scene_state import object_in_scene
    if not object_in_scene(target, context.scene, mesh=True):
        raise RuntimeError("Nenhum objeto alvo definido para o corte.")

    # Se estiver em Edit Mode, sincroniza dados para leitura sem alternar modo
    if target.mode == 'EDIT':
        target.update_from_editmode()

    sig = compute_cut_signature(settings, target, context.scene)
    if mode_has_modifiers := (settings.split_mode == 'PLANE' and any(m.show_viewport for m in target.modifiers)):
        from .input_state import cut_signature
        evaluated = target.evaluated_get(context.evaluated_depsgraph_get())
        try:
            evaluated_mesh = evaluated.to_mesh()
            sig = cut_signature(settings, target, context.scene, evaluated_mesh)
        finally:
            evaluated.to_mesh_clear()
    # The male side changes the outward normal used for picking and display.
    sig += ':' + settings.connector_male_part
    if not force_recompute and _CACHED_PREPARED_SPLIT is not None:
        if _CACHED_PREPARED_SPLIT.cut_signature == sig and _CACHED_PREPARED_SPLIT.target_name == target.name:
            return _CACHED_PREPARED_SPLIT

    unit_scale = get_scene_scale_to_mm(context.scene)
    if unit_scale <= 0.0:
        unit_scale = 1000.0

    mode = getattr(settings, "split_mode", "PLANE")
    male_side = getattr(settings, "connector_male_part", "A")

    cut_iface: Optional[CutInterface] = None
    if mode == 'PLANE':
        from .plane_state import resolve_plane_state
        from .geometry_plane import slice_mesh_by_plane
        plane_origin, plane_normal = resolve_plane_state(context.scene, settings)
        mesh_a = bpy.data.meshes.new('_chest_interface_a')
        mesh_b = bpy.data.meshes.new('_chest_interface_b')
        evaluated = None
        try:
            source_mesh = target.data
            if mode_has_modifiers:
                evaluated = target.evaluated_get(context.evaluated_depsgraph_get())
                source_mesh = evaluated.to_mesh()
            report = slice_mesh_by_plane(
                source_mesh, target.matrix_world, plane_origin, plane_normal,
                mesh_a, mesh_b, invert_sides=settings.invert_sides,
                unit_scale=unit_scale, plane_offset_mm=settings.plane_offset_mm,
                part_clearance_mm=settings.part_clearance_mm,
                part_clearance_apply_to=settings.part_clearance_apply_to,
            )
            cut_iface = report['interface']
        finally:
            if evaluated is not None:
                evaluated.to_mesh_clear()
            bpy.data.meshes.remove(mesh_a)
            bpy.data.meshes.remove(mesh_b)

    elif mode == 'SOLID':
        from .geometry_solid import slice_mesh_by_solid, validate_solid_cutter
        cutter = settings.solid_cutter_object
        validate_solid_cutter(cutter, target, unit_scale)
        mesh_a = bpy.data.meshes.new('_solid_interface_a')
        mesh_b = bpy.data.meshes.new('_solid_interface_b')
        evaluated = None
        try:
            source = target.data
            if any(m.show_viewport for m in target.modifiers):
                evaluated = target.evaluated_get(context.evaluated_depsgraph_get())
                source = evaluated.to_mesh()
            report = slice_mesh_by_solid(source, target.matrix_world, cutter, mesh_a, mesh_b,
                                        invert_sides=settings.invert_sides, unit_scale=unit_scale,
                                        part_clearance_mm=settings.part_clearance_mm,
                                        part_clearance_apply_to=settings.part_clearance_apply_to,
                                        interface_face_index=settings.solid_interface_face_index)
            cut_iface = report['interfaces'].get(male_side)
            if cut_iface is not None and settings.solid_interface_face_index < 0:
                settings.solid_interface_face_index = report['interface_face_index']
                from .input_state import cut_signature
                sig = cut_signature(settings, target, context.scene) + ':' + male_side
        finally:
            if evaluated is not None:
                evaluated.to_mesh_clear()
            bpy.data.meshes.remove(mesh_a)
            bpy.data.meshes.remove(mesh_b)
    elif mode == 'LOOP':
        from .geometry_loop import (
            slice_mesh_by_loop,
            slice_mesh_by_loop_extrude,
        )
        if target.mode == 'EDIT':
            target.update_from_editmode()

        indices = [int(i) for i in settings.loop_vertex_indices.split(',') if i.strip()]
        from .geometry_loop import validate_capture
        valid, reason = validate_capture(target, settings, context)
        if not valid:
            raise RuntimeError(reason)
        if settings.loop_seed_face_index < 0:
            raise RuntimeError("Defina a região a separar selecionando uma face semente no modo Loop.")

        behavior = settings.loop_behavior
        if behavior == 'AUTO':
            # Mesma resolução usada em splitter_generate_preview, para que a interface do
            # editor coincida com a interface real de contato (origem, normal e profundidade).
            from .geometry_loop import analyze_loop_region
            analysis = analyze_loop_region(target, indices, settings.loop_seed_face_index, context.scene)
            behavior = analysis["detected_mode"]
        loop_bottom_mm = (
            getattr(settings, "part_clearance_bottom_mm", 0.0)
            if getattr(settings, "part_clearance_bottom_enable", False) else None
        )
        if behavior == 'EXTRUDE':
            loop_res = slice_mesh_by_loop_extrude(
                target,
                target.name,
                indices,
                settings.loop_seed_face_index,
                depth_mm=settings.loop_extrude_depth_mm,
                through_cut=settings.loop_through_cut,
                scene=context.scene,
                part_clearance_mm=getattr(settings, "part_clearance_mm", 0.0),
                part_clearance_apply_to=getattr(settings, "part_clearance_apply_to", 'PART'),
                part_clearance_bottom_mm=loop_bottom_mm,
            )
        else:
            loop_res = slice_mesh_by_loop(
                target,
                target.name,
                indices,
                settings.loop_seed_face_index,
                context.scene,
                detach_add_base=settings.loop_detach_add_base,
                detach_base_depth_mm=settings.loop_detach_base_depth_mm,
                detach_base_clearance_mm=settings.loop_detach_base_clearance_mm,
                part_clearance_mm=getattr(settings, "part_clearance_mm", 0.0),
                part_clearance_apply_to=getattr(settings, "part_clearance_apply_to", 'PART'),
                part_clearance_bottom_mm=loop_bottom_mm,
            )

        bm_a, bm_b = loop_res[0], loop_res[1]
        bm_a.free()
        bm_b.free()

        cut_iface = getattr(loop_res, 'interface', None)
        if cut_iface:
            settings.loop_interface_origin = tuple(cut_iface.origin_world)
            settings.loop_interface_normal = tuple(cut_iface.normal_a_to_b_world)
            if getattr(cut_iface, "interface_triangles_world", None):
                contact_tris = list(cut_iface.interface_triangles_world)

    elif mode == 'MATERIAL':
        from .geometry_material import slice_mesh_by_material
        if not target.data.materials:
            raise RuntimeError("O objeto alvo não possui materiais para o modo Material.")

        mat_res = slice_mesh_by_material(
            target,
            material_index=settings.material_split_index,
            depth_mm=settings.material_extrude_depth_mm,
            scene=context.scene,
            region_index=settings.material_region_index,
            extraction_mode=getattr(settings, "material_extraction_mode", 'EXTRUDE'),
            interface_mat_mode=getattr(settings, "material_interface_mat_mode", 'SOURCE'),
            part_clearance_mm=getattr(settings, "part_clearance_mm", 0.0),
            part_clearance_apply_to=getattr(settings, "part_clearance_apply_to", 'PART'),
            part_clearance_bottom_mm=(
                getattr(settings, "part_clearance_bottom_mm", 0.0)
                if getattr(settings, "part_clearance_bottom_enable", False) else None
            ),
        )
        bm_a, bm_b = mat_res[0], mat_res[1]
        bm_a.free()
        bm_b.free()

        cut_iface = getattr(mat_res, 'interface', None)
        if cut_iface:
            settings.loop_interface_origin = tuple(cut_iface.origin_world)
            settings.loop_interface_normal = tuple(cut_iface.normal_a_to_b_world)
            if getattr(cut_iface, "interface_triangles_world", None):
                contact_tris = list(cut_iface.interface_triangles_world)

    return cache_prepared_interface(context, cut_iface, sig)


def cache_prepared_interface(context, cut_iface, sig=None):
    """Publish the same physical interface consumed by preview generation."""
    global _CACHED_PREPARED_SPLIT
    settings = context.scene.chest_splitter
    target = settings.target_object
    mode = settings.split_mode
    male_side = settings.connector_male_part
    unit_scale = get_scene_scale_to_mm(context.scene)
    sig = sig or compute_cut_signature(settings, target, context.scene) + ':' + male_side
    contact_tris = list(cut_iface.interface_triangles_world) if cut_iface else []
    bvh_tree = None
    if cut_iface is None:
        raise RuntimeError("Não foi possível preparar a interface de corte para o modelo.")
    if not cut_iface.outer_contours_uv:
        raise RuntimeError("Este corte não possui uma superfície comum para posicionar os pinos.")

    if getattr(cut_iface, 'clearance_applied', False):
        # Spatial clearance can split topology. Use the actual retained patch
        # on the selected pin side rather than shifting the nominal interface.
        # Keep the nominal UV frame: the patch origin is a mesh-derived anchor
        # (often a triangle centroid), and rebuilding the frame from it can
        # move stored manual UV coordinates sideways or rotate them on a flip.
        patch = getattr(cut_iface, 'final_contact_a' if male_side == 'A' else 'final_contact_b', None)
        if patch is None:
            from .localized_errors import LocalizedGeometryError
            raise LocalizedGeometryError('connectors.no_contact_patch')
        from .geometry_contract import build_cut_interface, orient_interface
        previous = cut_iface
        normal = previous.normal_a_to_b_world.normalized()
        reference_origin = getattr(previous, 'reference_origin_world', None)
        if reference_origin is None:
            reference_origin = previous.origin_world
        reference_axis_u = getattr(previous, 'reference_axis_u_world', None)
        if reference_axis_u is None:
            reference_axis_u = previous.axis_u_world
        patch_normal = patch['normal'].normalized()
        # Preserve the interface's A-to-B convention even when B is selected.
        if patch_normal.dot(normal) < 0.0:
            patch_normal = -patch_normal
        # Move the canonical origin only along the patch normal. This places
        # UV (0, 0) on the physical retained surface while preserving its
        # tangential coordinates across clearance changes and male-side flips.
        origin = reference_origin + patch_normal * (
            (patch['origin'] - reference_origin).dot(patch_normal)
        )
        cut_iface = build_cut_interface(
            origin, normal, patch['boundary'],
            interface_triangles=patch['triangles'],
            boundary_loops_world=patch.get('loops'),
            unit_scale=unit_scale, source_mode=previous.source_mode)
        cut_iface = orient_interface(cut_iface, reference_axis_u)
        # A retained patch can itself be locally planar while belonging to a
        # nonplanar nominal interface. Keep the source surface classification.
        cut_iface.is_planar = previous.is_planar
        cut_iface.deviation_mm = previous.deviation_mm
        # Keep the reference when this prepared interface is cached/reused.
        if hasattr(previous, 'reference_origin_world'):
            cut_iface.reference_origin_world = reference_origin.copy()
        if hasattr(previous, 'reference_axis_u_world'):
            cut_iface.reference_axis_u_world = reference_axis_u.copy()
        cut_iface.clearance_applied = True
        cut_iface.final_contact_a = previous.final_contact_a
        cut_iface.final_contact_b = previous.final_contact_b
        contact_tris = list(cut_iface.interface_triangles_world)
    elif mode == 'PLANE':
        from dataclasses import replace
        distance = max(0.0, settings.part_clearance_mm)/unit_scale
        fraction = (1.0 if settings.part_clearance_apply_to == ('PART' if male_side == 'A' else 'CAVITY')
                    else 0.5 if settings.part_clearance_apply_to == 'BOTH' else 0.0)
        shift = cut_iface.normal_a_to_b_world * distance*fraction * (-1 if male_side == 'A' else 1)
        cut_iface = replace(cut_iface, origin_world=cut_iface.origin_world+shift)
    elif mode == 'MATERIAL' and settings.material_extraction_mode == 'EXTRUDE':
        from dataclasses import replace
        bottom = settings.part_clearance_bottom_mm if settings.part_clearance_bottom_enable else settings.part_clearance_mm
        fraction = (1.0 if settings.part_clearance_apply_to == ('PART' if male_side == 'A' else 'CAVITY')
                    else 0.5 if settings.part_clearance_apply_to == 'BOTH' else 0.0)
        shift = cut_iface.normal_a_to_b_world * (bottom/unit_scale)*fraction*(-1 if male_side == 'A' else 1)
        cut_iface = replace(cut_iface, origin_world=cut_iface.origin_world+shift,
                            interface_triangles_world=[tuple(p+shift for p in tri) for tri in cut_iface.interface_triangles_world])
        contact_tris = cut_iface.interface_triangles_world
    elif mode == 'LOOP':
        from dataclasses import replace
        loop_beh = settings.loop_behavior
        if loop_beh == 'AUTO':
            loop_beh = getattr(settings, "loop_detected_mode", "DETACH") or "DETACH"
        if loop_beh == 'EXTRUDE' and not settings.loop_through_cut:
            bottom = settings.part_clearance_bottom_mm if settings.part_clearance_bottom_enable else settings.part_clearance_mm
        elif loop_beh == 'DETACH' and settings.loop_detach_add_base:
            bottom = settings.part_clearance_bottom_mm if settings.part_clearance_bottom_enable else settings.part_clearance_mm
        else:
            bottom = settings.part_clearance_mm
        fraction = (1.0 if settings.part_clearance_apply_to == ('PART' if male_side == 'A' else 'CAVITY')
                    else 0.5 if settings.part_clearance_apply_to == 'BOTH' else 0.0)
        shift = cut_iface.normal_a_to_b_world * (max(0.0, bottom)/unit_scale)*fraction*(-1 if male_side == 'A' else 1)
        shifted_tris = [tuple(p+shift for p in tri) for tri in cut_iface.interface_triangles_world] if cut_iface.interface_triangles_world else []
        cut_iface = replace(cut_iface, origin_world=cut_iface.origin_world+shift,
                            interface_triangles_world=shifted_tris)
        contact_tris = cut_iface.interface_triangles_world

    # Pin UVs belong to a selected region, never to whichever loop was used before.
    def _get_persistent_id(obj):
        if not obj:
            return ""
        pid = obj.get("chest_persistent_id")
        if not pid:
            import uuid
            pid = uuid.uuid4().hex[:12]
            obj["chest_persistent_id"] = pid
        return pid

    target_id = _get_persistent_id(target)
    cutter_id = _get_persistent_id(settings.solid_cutter_object) if (mode == 'SOLID' and settings.solid_cutter_object) else None
    binding = repr((target_id, mode,
                    settings.loop_vertex_indices if mode == 'LOOP' else None,
                    settings.loop_seed_face_index if mode == 'LOOP' else None,
                    (settings.material_split_index, settings.material_region_index) if mode == 'MATERIAL' else None,
                    (cutter_id, settings.solid_interface_face_index)
                    if mode == 'SOLID' else None))
    if settings.manual_binding and settings.manual_binding != binding:
        settings.manual_connectors.clear()
    settings.manual_binding = binding

    # Use exactly the deterministic basis of the geometry result. Never flip axes
    # without reprojecting the contours (that reflects asymmetric interfaces).
    axis_u = cut_iface.axis_u_world.copy()
    axis_v = cut_iface.axis_v_world.copy()

    # Define a normal na superfície de contato voltada para fora do macho
    if male_side == 'A':
        surface_normal = cut_iface.normal_a_to_b_world.normalized()
    else:
        surface_normal = -cut_iface.normal_a_to_b_world.normalized()

    # Constrói BVHTree para raycast se houver triângulos de contato
    if contact_tris:
        bvh_tree = BVHTree.FromPolygons(
            [v for tri in contact_tris for v in tri],
            [(i * 3, i * 3 + 1, i * 3 + 2) for i in range(len(contact_tris))]
        )

    from .input_state import editor_configuration
    prepared = PreparedSplit(
        cut_signature=sig,
        configuration=editor_configuration(settings, context.scene),
        target_name=target.name,
        split_mode=mode,
        interface=cut_iface,
        surface_origin=cut_iface.origin_world.copy(),
        surface_normal=surface_normal,
        axis_u=axis_u,
        axis_v=axis_v,
        unit_scale=unit_scale,
        male_side=male_side,
        is_planar=cut_iface.is_planar,
        contact_triangles_world=contact_tris,
        bvh_tree=bvh_tree,
    )
    _CACHED_PREPARED_SPLIT = prepared
    return prepared


def prepared_connector_layout(prepared, settings, target):
    """Cache placement work independently of GPU redraw frequency."""
    names = ('connector_distribution', 'connector_edge_margin_mm', 'connector_diameter_mm',
             'clearance_per_side_mm', 'connector_type', 'connector_capsule_length_mm',
             'adjust_to_valid_area')
    key = tuple(getattr(settings, name) for name in names)
    specs = None
    if settings.connector_distribution == 'MANUAL':
        specs = [dict(u_mm=c.u_mm, v_mm=c.v_mm, yaw_deg=c.yaw_deg) for c in settings.manual_connectors]
        key += tuple((c['u_mm'], c['v_mm'], c['yaw_deg']) for c in specs)
    if prepared.layout_key != key:
        from .geometry_connectors import compute_connector_layout
        prepared.layout = compute_connector_layout(
            target.data, target.matrix_world, prepared.surface_origin, prepared.surface_normal,
            settings.connector_distribution, settings.connector_edge_margin_mm, prepared.unit_scale,
            settings.connector_diameter_mm, settings.clearance_per_side_mm, prepared.interface,
            settings.connector_type, settings.connector_capsule_length_mm,
            settings.adjust_to_valid_area, specs)
        prepared.layout_key = key
    return prepared.layout


def get_explosion_display_offset(settings: Any, prepared: PreparedSplit) -> Vector:
    """Calcula o vetor de deslocamento da visão explodida para a superfície dos pinos."""
    # Durante a edição interativa de pinos, o usuário interage diretamente com o objeto alvo
    # montado em repouso. O deslocamento de explosão deve ser estritamente zero para não afastar
    # a grade de 5 mm e os marcadores no espaço vazio.
    if getattr(settings, "is_editing_connectors", False):
        return Vector((0.0, 0.0, 0.0))

    # No preview means the assembled target is displayed, regardless of slider value.
    from .constants import ROLE_PREVIEW_A, ROLE_PREVIEW_B
    role = ROLE_PREVIEW_A if prepared.male_side == 'A' else ROLE_PREVIEW_B
    scene = bpy.context.scene
    for obj in scene.objects:
        if (obj.get("chest_role") == role
                and obj.get("chest_session_id") == settings.session_id
                and obj.visible_get()):
            assembled = Vector(obj.get("chest_assembled_loc", (0, 0, 0)))
            return obj.matrix_world.translation - assembled
    return Vector((0.0, 0.0, 0.0))


def raycast_connector_surface(
    ray_origin: Vector,
    ray_dir: Vector,
    prepared: PreparedSplit,
    display_offset: Vector = Vector((0.0, 0.0, 0.0)),
) -> Optional[Tuple[Vector, float, float]]:
    """Projeta raio na superfície preparada e retorna (ponto_montado, u_mm, v_mm).
    
    Retorna None se o raio não interceptar a superfície física útil de contato,
    evitando posicionamento indevido de pinos no espaço vazio.
    """
    ray_dir = ray_dir.normalized()

    # 1. Se houver BVHTree da superfície de contato, testa interseção com malha real
    if prepared.bvh_tree is not None:
        local_ray_origin = ray_origin - display_offset
        hit_loc, hit_norm, hit_idx, hit_dist = prepared.bvh_tree.ray_cast(local_ray_origin, ray_dir)
        if hit_loc is not None:
            assembled_hit = hit_loc
            u_mm, v_mm = prepared.world_to_uv_mm(assembled_hit)
            return (assembled_hit, u_mm, v_mm)
        # Se há geometria real de contato e o raio errou a superfície, não há hit válido
        return None

    # 2. Interseção analítica raio-plano SOMENTE SE bvh_tree for None
    orig_disp = prepared.surface_origin + display_offset
    denom = ray_dir.dot(prepared.surface_normal)
    if abs(denom) < 1e-5:
        # Raio paralelo à interface
        return None

    t = (orig_disp - ray_origin).dot(prepared.surface_normal) / denom
    if t < 0.0:
        return None

    hit_disp = ray_origin + ray_dir * t
    assembled_hit = hit_disp - display_offset
    u_mm, v_mm = prepared.world_to_uv_mm(assembled_hit)

    # Valida se o ponto no plano cai dentro do contorno 2D útil da interface
    cut_iface = prepared.interface
    outer_polys = getattr(cut_iface, "outer_contours_uv", [])
    if outer_polys:
        from .geometry_connectors import point_in_polygon_2d
        u_bu = u_mm / prepared.unit_scale
        v_bu = v_mm / prepared.unit_scale
        if not any(point_in_polygon_2d(u_bu, v_bu, poly) for poly in outer_polys):
            return None
        if any(point_in_polygon_2d(u_bu, v_bu, poly)
               for poly in cut_iface.hole_contours_uv):
            return None
    else:
        return None

    return (assembled_hit, u_mm, v_mm)


def evaluate_connector_specs(prepared: PreparedSplit, settings: Any) -> List[Dict[str, Any]]:
    """Avalia individualmente cada conector manual quanto à margem, furos e colisões mútuas.
    
    Retorna lista de dicionários com chaves: index, id, is_valid, reason.
    """
    diam_mm = getattr(settings, "connector_diameter_mm", 4.0)
    clear_side_mm = getattr(settings, "clearance_per_side_mm", 0.15)
    margin_mm = getattr(settings, "connector_edge_margin_mm", 3.0)
    conn_type = getattr(settings, "connector_type", "CYLINDER")
    cap_len_mm = getattr(settings, "connector_capsule_length_mm", 6.0)

    unit_scale = prepared.unit_scale
    check_r = (diam_mm / 2.0 + clear_side_mm + margin_mm) / unit_scale
    half_len = max(0.0, (cap_len_mm - diam_mm) / 2.0) / unit_scale if conn_type == 'CAPSULE' else 0.0

    outer_polys = getattr(prepared.interface, "outer_contours_uv", []) or []
    hole_polys = getattr(prepared.interface, "hole_contours_uv", []) or []

    results = []
    connectors = list(settings.manual_connectors)
    n_conns = len(connectors)

    from .geometry_connectors import validate_connector_footprint

    # 1. Validação individual de footprint no domínio da interface
    for idx, conn in enumerate(connectors):
        u_bu = conn.u_mm / unit_scale
        v_bu = conn.v_mm / unit_scale
        yaw_rad = math.radians(getattr(conn, "yaw_deg", 0.0))

        if not outer_polys:
            is_ok, reason = False, "Interface de contato não preparada"
        else:
            is_ok, reason = validate_connector_footprint(
                u_p=u_bu,
                v_p=v_bu,
                check_r=check_r,
                outer_polys=outer_polys,
                hole_polys=hole_polys,
                edge_margin_mm=margin_mm,
                connector_type=conn_type,
                half_len=half_len,
                yaw_rad=yaw_rad,
            )

        results.append({
            "index": idx,
            "id": getattr(conn, "connector_id", "") or f"pin_{idx}",
            "is_valid": is_ok,
            "reason": reason,
        })

    # Exact capsule/disk separation; adjacent parallel capsules need not be
    # separated by their entire LENGTH in every direction.
    from .geometry_connectors import connector_center_segment, segment_distance_sq
    physical_half = max(0.0, (cap_len_mm - diam_mm) / 2.0) if conn_type == 'CAPSULE' else 0.0
    segments = [connector_center_segment(c.u_mm, c.v_mm, physical_half,
                                         math.radians(c.yaw_deg)) for c in connectors]
    min_gap_sq = (diam_mm + 2.0 * clear_side_mm + 1.0)**2
    for i in range(n_conns):
        for j in range(i + 1, n_conns):
            if segment_distance_sq(*segments[i], *segments[j]) < min_gap_sq:
                results[i].update(is_valid=False, reason=f"Colisão: muito próximo do pino #{j+1}")
                results[j].update(is_valid=False, reason=f"Colisão: muito próximo do pino #{i+1}")

    # Atualiza as propriedades no PropertyGroup
    for ev in results:
        idx = ev["index"]
        if idx < len(settings.manual_connectors):
            item = settings.manual_connectors[idx]
            item.is_valid = ev["is_valid"]
            item.status_reason = ev["reason"]
            item.validation_msg = ev["reason"]

    return results


def generate_positioning_grid_points(
    prepared: PreparedSplit,
    step_mm: float = 5.0,
    max_points: int = 25000,
) -> List[Tuple[float, float, Vector]]:
    """Gera pontos de referência da grade de 5 mm sobre a região útil de contato (Seção 4 e 5).
    
    Retorna lista de tuplas (u_mm, v_mm, world_point).
    - Ancoragem estável em (0, 0) da referência UV: P(i, j) = O + (i * s) * U + (j * s) * V.
    - Filtra estritamente por pertencimento à interface útil (suporte a formas côncavas, U e furos).
    - Omite grade se a superfície não for plana ou se exceder o limite defensivo de candidatos.
    """
    if prepared is None or not math.isfinite(step_mm) or step_mm <= 0 or max_points <= 0:
        return []

    # Se a superfície não for plana, omite a grade para não gerar falsa referência sobre curvatura (Seção 4.4)
    if not getattr(prepared, "is_planar", True):
        return []

    cut_iface = getattr(prepared, "interface", None)
    if cut_iface is None:
        return []

    outer_polys = getattr(cut_iface, "outer_contours_uv", []) or []
    hole_polys = getattr(cut_iface, "hole_contours_uv", []) or []
    if not outer_polys:
        return []

    unit_scale = prepared.unit_scale
    if unit_scale <= 0.0:
        unit_scale = 1000.0

    # Coleta limites envolventes em Blender Units e converte para mm
    all_u_bu = [pt[0] for poly in outer_polys for pt in poly]
    all_v_bu = [pt[1] for poly in outer_polys for pt in poly]
    if not all_u_bu or not all_v_bu:
        return []

    min_u_mm = min(all_u_bu) * unit_scale
    max_u_mm = max(all_u_bu) * unit_scale
    min_v_mm = min(all_v_bu) * unit_scale
    max_v_mm = max(all_v_bu) * unit_scale

    # Índices inteiros ancorados na origem estável (0, 0) da interface
    i_min = int(math.floor(min_u_mm / step_mm))
    i_max = int(math.ceil(max_u_mm / step_mm))
    j_min = int(math.floor(min_v_mm / step_mm))
    j_max = int(math.ceil(max_v_mm / step_mm))

    total_candidates = (i_max - i_min + 1) * (j_max - j_min + 1)
    if total_candidates > max_points:
        return []

    from .geometry_connectors import point_in_polygon_2d

    grid_points = []
    step_bu = step_mm / unit_scale

    for i in range(i_min, i_max + 1):
        u_mm = i * step_mm
        u_bu = i * step_bu
        for j in range(j_min, j_max + 1):
            v_mm = j * step_mm
            v_bu = j * step_bu

            # 1. Pertencimento ao interior de ao menos um contorno externo
            in_outer = any(point_in_polygon_2d(u_bu, v_bu, poly) for poly in outer_polys)
            if not in_outer:
                continue

            # 2. Exclusão de furos ou recortes internos
            in_hole = any(point_in_polygon_2d(u_bu, v_bu, h_poly) for h_poly in hole_polys)
            if in_hole:
                continue

            world_pos = prepared.uv_mm_to_world(u_mm, v_mm)
            grid_points.append((u_mm, v_mm, world_pos))

    return grid_points
