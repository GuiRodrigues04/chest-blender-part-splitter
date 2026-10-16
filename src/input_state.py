"""Deterministic input fingerprints. No scene mutation or viewport drawing."""
import array
import hashlib

from .diagnostic import get_scene_scale_to_mm


CUT_PROPERTIES = (
    'split_mode', 'invert_sides', 'plane_offset_mm',
    'part_clearance_mm', 'part_clearance_apply_to',
    'part_clearance_bottom_enable', 'part_clearance_bottom_mm',
    'loop_vertex_indices', 'loop_seed_face_index', 'loop_behavior',
    'loop_extrude_depth_mm', 'loop_through_cut', 'loop_detach_add_base',
    'loop_detach_base_depth_mm', 'loop_detach_base_clearance_mm',
    'material_split_index', 'material_region_index', 'material_extraction_mode',
    'material_extrude_depth_mm', 'material_interface_mat_mode',
)


def update_mesh_hash(digest, mesh):
    """Hash geometry, face boundaries and materials in bulk (including same-count edits)."""
    digest.update(repr((len(mesh.vertices), len(mesh.edges), len(mesh.polygons))).encode())
    for elements, attribute, kind, width in (
        (mesh.vertices, 'co', 'f', 3), (mesh.edges, 'vertices', 'i', 2),
        (mesh.loops, 'vertex_index', 'i', 1),
        (mesh.polygons, 'loop_total', 'i', 1),
        (mesh.polygons, 'material_index', 'i', 1),
    ):
        values = array.array(kind, [0]) * (len(elements) * width)
        elements.foreach_get(attribute, values)
        digest.update(values.tobytes())
    digest.update(repr([m.name_full if m else None for m in mesh.materials]).encode())


def cut_signature(settings, target, scene, mesh=None):
    digest = hashlib.sha256()
    digest.update(repr((target.name_full, tuple(tuple(r) for r in target.matrix_world),
                        get_scene_scale_to_mm(scene))).encode())
    update_mesh_hash(digest, mesh if mesh is not None else target.data)
    digest.update(repr([(p, getattr(settings, p, None)) for p in CUT_PROPERTIES]).encode())
    if settings.split_mode == 'PLANE':
        from .plane_state import resolve_plane_state
        origin, normal = resolve_plane_state(scene, settings)
        digest.update(repr((tuple(origin), tuple(normal))).encode())
    return digest.hexdigest()


def editor_configuration(settings, scene):
    target = settings.target_object
    key = (tuple(getattr(settings, p, None) for p in CUT_PROPERTIES),
           settings.connector_male_part, get_scene_scale_to_mm(scene),
           tuple(tuple(r) for r in target.matrix_world) if target else None)
    if settings.split_mode == 'PLANE':
        from .plane_state import resolve_plane_state
        origin, normal = resolve_plane_state(scene, settings)
        key += (tuple(origin), tuple(normal))
    return key
