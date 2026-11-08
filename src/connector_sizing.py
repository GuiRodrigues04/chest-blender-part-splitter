"""Conservative initial connector dimensions from the actual cut solids."""
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def solid_tree(part):
    """Parts are already in world space; use Blender's visible tessellation."""
    owned = not isinstance(part, bpy.types.Mesh)
    mesh = bpy.data.meshes.new('_connector_sizing') if owned else part
    try:
        if owned:
            part.to_mesh(mesh)
        mesh.calc_loop_triangles()
        return BVHTree.FromPolygons([v.co.copy() for v in mesh.vertices],
            [tuple(t.vertices) for t in mesh.loop_triangles], all_triangles=True)
    finally:
        if owned:
            bpy.data.meshes.remove(mesh)


def attach_sizing_solids(interface, a, b):
    if interface is not None:
        interface.sizing_trees = (solid_tree(a), solid_tree(b))


def solid_interval(tree, point, direction, scale):
    """First receiving interval, measured from the pin anchor in millimetres."""
    normal = direction.normalized()
    epsilon = max(.001/scale, max(abs(c) for c in point)*2e-7)
    hit, face_normal, _, _ = tree.ray_cast(point+normal*epsilon, normal)
    if hit is None:
        return None
    distance = (hit-point).dot(normal)
    if face_normal.dot(normal) > 1e-6:
        return 0., distance*scale
    if face_normal.dot(normal) >= -1e-6:
        return None
    entry = distance
    exit_point, exit_normal, _, _ = tree.ray_cast(hit+normal*epsilon, normal)
    if exit_point is None or exit_normal.dot(normal) <= 1e-6:
        return None
    return entry*scale, (exit_point-point).dot(normal)*scale


def recommend_dimensions(prepared, settings, target):
    from .geometry_connectors import (compute_connector_layout, create_capsule_2d_profile,
                                      ConnectorValidationError)
    if not prepared.sizing_trees:
        raise ValueError('Prepare o corte para calcular as dimensões dos pinos.')
    scale = prepared.unit_scale
    maximum = min(40., .2*min(prepared.interface.width_mm, prepared.interface.height_mm))
    if maximum < 1.:
        maximum = 1.
    start = max(1., math.floor((maximum+1e-5)*2)/2)
    candidates = sorted({max(1., math.floor(start*.8**i*2)/2) for i in range(24)}, reverse=True)
    manual = ([dict(u_mm=p.u_mm, v_mm=p.v_mm, yaw_deg=p.yaw_deg) for p in settings.manual_connectors]
              if settings.connector_distribution == 'MANUAL' else None)
    receiver = prepared.sizing_trees[1 if prepared.male_side == 'A' else 0]
    male = prepared.sizing_trees[0 if prepared.male_side == 'A' else 1]
    normal = prepared.surface_normal
    wall_mm = max(.4, float(settings.connector_edge_margin_mm))
    for diameter in candidates:
        capsule = math.floor(diameter*1.8*4)/4 if settings.connector_type == 'CAPSULE' else 0.
        try:
            layout = compute_connector_layout(target.data, target.matrix_world,
                prepared.surface_origin, normal, settings.connector_distribution,
                settings.connector_edge_margin_mm, scale, diameter, settings.clearance_per_side_mm,
                prepared.interface, settings.connector_type, capsule, settings.adjust_to_valid_area, manual)
        except (ValueError, RuntimeError, ConnectorValidationError):
            continue
        if not layout['positions'] or any(not p['is_valid'] for p in layout['manual_eval_results']):
            continue
        capsule = layout.get('adjusted_capsule_length_mm', capsule)
        radius = diameter/2+settings.clearance_per_side_mm
        half = max(0., capsule-diameter)/2 if settings.connector_type == 'CAPSULE' else 0.
        profile = create_capsule_2d_profile(radius/scale, half/scale, segments=16)
        available, entrance, embedded = [], [], []
        for point, rotation in zip(layout['positions'], layout['pin_rotations']):
            basis = rotation.to_matrix()
            offsets = [Vector()]+[basis@Vector((x,y,0.)) for x,y in profile]
            for offset in offsets:
                interval = solid_interval(receiver, point+offset, normal, scale)
                own = solid_interval(male, point+offset, -normal, scale)
                if interval is None or own is None:
                    available = []
                    break
                entrance.append(interval[0])
                available.append(interval[1])
                embedded.append(own[1])
            if not available:
                break
        if not available or min(embedded) < max(.2, diameter*.05)+.05:
            continue
        maximum_length = min(50., min(available)-wall_mm-settings.end_clearance_mm)
        desired = max(entrance)+1.5*diameter
        length = math.floor(min(desired, maximum_length)*4)/4
        if length < max(2., max(entrance)+1.):
            continue
        return dict(diameter_mm=diameter, length_mm=length, capsule_length_mm=capsule,
                    chamfer_mm=min(.8, diameter*.15, length*.1),
                    receiver_depth_mm=min(available), remaining_wall_mm=wall_mm,
                    positions=len(layout['positions']))
    raise ValueError('Não há espaço e profundidade suficientes para sugerir um pino de pelo menos 1 mm × 2 mm.')


_applying = set()


def apply_suggestion(context, only_defaults=False):
    from .connector_surface import prepare_split_candidates
    from .translations import report_msg
    settings = context.scene.chest_splitter
    if only_defaults and not defaults_untouched(settings):
        return None
    prepared = prepare_split_candidates(context, include_solids=True)
    result = recommend_dimensions(prepared, settings, settings.target_object)
    key = settings.as_pointer()
    _applying.add(key)
    try:
        settings.connector_diameter_mm = result['diameter_mm']
        settings.connector_length_mm = result['length_mm']
        settings.connector_chamfer_mm = result['chamfer_mm']
        if settings.connector_type == 'CAPSULE':
            settings.connector_capsule_length_mm = result['capsule_length_mm']
        settings.connector_dimensions_customized = False
    finally:
        _applying.discard(key)
    settings.connector_sizing_status = report_msg(
        f"Sugestão: Ø {result['diameter_mm']:g} × {result['length_mm']:g} mm; profundidade verificada.",
        f"Suggestion: Ø {result['diameter_mm']:g} × {result['length_mm']:g} mm; depth checked.")
    return result


def defaults_untouched(settings):
    if settings.connector_dimensions_customized:
        return False
    # Explicitly saved values belong to an existing file/user, even if they
    # happen to equal the old defaults. Never silently rewrite those values.
    return not any(settings.is_property_set(name) for name in (
        'connector_diameter_mm', 'connector_length_mm', 'connector_chamfer_mm',
        'connector_capsule_length_mm'))


class CHEST_OT_splitter_suggest_connector_dimensions(bpy.types.Operator):
    bl_idname = 'chest.splitter_suggest_connector_dimensions'
    bl_label = 'Sugerir dimensões'
    bl_description = 'Sugere dimensões de encaixe pelo contato e pela profundidade disponível'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, 'chest_splitter', None)
        return bool(settings and settings.target_object and settings.split_mode != 'SOLID'
                    and settings.session_status != 'COMMITTED')

    def execute(self, context):
        from .translations import report_msg
        from .geometry_connectors import ConnectorValidationError
        settings = context.scene.chest_splitter
        try:
            apply_suggestion(context)
        except (ValueError, RuntimeError, ConnectorValidationError):
            settings.connector_sizing_status = report_msg(
                'Não foi possível sugerir dimensões para este contato; ajuste ou escolha outro contato.',
                'Could not suggest dimensions for this contact; adjust or choose another contact.')
            self.report({'INFO'}, settings.connector_sizing_status)
            return {'CANCELLED'}
        self.report({'INFO'}, settings.connector_sizing_status)
        return {'FINISHED'}
