"""Conservative initial connector dimensions from the actual cut solids."""
import math
import json
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
    # Bound candidates by the usable contact span before asking the layout
    # validator to check its actual contour (including holes and concavities).
    # The nominal diameter must fit with both the printer clearance and the
    # requested edge margin on either side.
    clearance = max(0., float(settings.clearance_per_side_mm))
    edge_margin = max(.4, float(settings.connector_edge_margin_mm))
    maximum = min(40., min(prepared.interface.width_mm, prepared.interface.height_mm)
                  - 2.*(edge_margin+clearance))
    if maximum < 1.-1e-6:
        raise ValueError('O contato não comporta o pino mínimo de 1 mm com a folga e a margem da borda atuais.')
    start = max(1., math.floor((maximum+1e-6)*4)/4)
    candidates = [round(start - i*.25, 2) for i in range(int(math.floor((start-1.)/.25))+1)]
    # An empty manual layout has no coordinates to validate. Use a centered
    # candidate for sizing, while keeping the user's MANUAL distribution and
    # connector list untouched.
    manual = ([dict(u_mm=p.u_mm, v_mm=p.v_mm, yaw_deg=p.yaw_deg) for p in settings.manual_connectors]
              if settings.connector_distribution == 'MANUAL' and len(settings.manual_connectors) else None)
    manual_reference = settings.connector_distribution == 'MANUAL' and not manual
    distribution = ('CENTER' if settings.connector_distribution == 'MANUAL' and not manual
                    else settings.connector_distribution)
    interface_normal = prepared.interface.normal_a_to_b_world.normalized()
    wall_mm = max(.4, float(settings.connector_edge_margin_mm))
    for diameter in candidates:
        capsule = math.floor(diameter*1.8*4)/4 if settings.connector_type == 'CAPSULE' else 0.
        side_layouts = {}
        available, entrance, embedded = [], [], []
        footprint_valid = True
        radius = diameter/2+clearance
        # Verify both possible pin sides. A recommendation must remain safe
        # when the user flips the male/female parts after sizing.
        for side in ('A', 'B'):
            normal = interface_normal if side == 'A' else -interface_normal
            receiver = prepared.sizing_trees[1 if side == 'A' else 0]
            male = prepared.sizing_trees[0 if side == 'A' else 1]
            try:
                layout = compute_connector_layout(target.data, target.matrix_world,
                    prepared.surface_origin, normal, distribution,
                    edge_margin, scale, diameter, clearance,
                    prepared.interface, settings.connector_type, capsule, settings.adjust_to_valid_area, manual)
            except (ValueError, RuntimeError, ConnectorValidationError):
                footprint_valid = False
                break
            if not layout['positions'] or any(not p['is_valid'] for p in layout['manual_eval_results']):
                footprint_valid = False
                break
            side_layouts[side] = layout
            capsule = layout.get('adjusted_capsule_length_mm', capsule)
            half = max(0., capsule-diameter)/2 if settings.connector_type == 'CAPSULE' else 0.
            profile = create_capsule_2d_profile(radius/scale, half/scale, segments=16)
            for point, rotation in zip(layout['positions'], layout['pin_rotations']):
                basis = rotation.to_matrix()
                # Check the filled footprint at the receiver and male side, not
                # only its outline. Interior samples catch thin voids and pockets
                # that boundary-only rays can miss.
                local_samples = [Vector((0., 0., 0.))]
                for factor in (.5, .8, 1.):
                    local_samples.extend(Vector((x*factor, y*factor, 0.)) for x, y in profile)
                for sample in local_samples:
                    offset = basis@sample
                    interval = solid_interval(receiver, point+offset, normal, scale)
                    own = solid_interval(male, point+offset, -normal, scale)
                    if interval is None or own is None:
                        footprint_valid = False
                        break
                    entrance.append(interval[0])
                    available.append(interval[1])
                    embedded.append(own[1])
                if not footprint_valid:
                    break
            if not footprint_valid:
                break
        if (not footprint_valid or not available
                or min(embedded) < max(.2, diameter*.05)+.05):
            continue
        maximum_length = min(50., min(available)-wall_mm-settings.end_clearance_mm)
        desired = max(2., max(entrance)+1.5*diameter)
        length = math.floor(min(desired, maximum_length)*4)/4
        if length < max(2., max(entrance)+1.):
            continue
        return dict(diameter_mm=diameter, length_mm=length, capsule_length_mm=capsule,
                    chamfer_mm=min(.8, diameter*.15, length*.1),
                    receiver_depth_mm=min(available), remaining_wall_mm=wall_mm,
                    positions=len(side_layouts[settings.connector_male_part]['positions']),
                    manual_reference=manual_reference)
    if manual_reference:
        raise ValueError('O centro não comporta um pino seguro. Posicione um pino manual no contato e sugira novamente.')
    raise ValueError('Não há espaço contínuo no contorno e no receptor para sugerir um pino de pelo menos 1 mm × 2 mm.')


_applying = set()


def _sizing_configuration(settings):
    manual = tuple((round(float(p.u_mm), 4), round(float(p.v_mm), 4), round(float(p.yaw_deg), 3))
                   for p in settings.manual_connectors)
    return json.dumps({
        'type': settings.connector_type,
        'distribution': settings.connector_distribution,
        'edge_margin': round(float(settings.connector_edge_margin_mm), 5),
        'clearance': round(float(settings.clearance_per_side_mm), 5),
        'end_clearance': round(float(settings.end_clearance_mm), 5),
        'adjust': bool(settings.adjust_to_valid_area),
        'manual': manual,
    }, sort_keys=True, separators=(',', ':'))


def apply_suggestion(context, only_defaults=False):
    from .connector_surface import prepare_split_candidates
    from .translations import report_msg
    settings = context.scene.chest_splitter
    if only_defaults and not defaults_untouched(settings):
        return None
    previous_contact = getattr(settings, 'contact_patch_index', -1)
    prepared = None
    try:
        prepared = prepare_split_candidates(context, include_solids=True, auto_contact=True)
        result = recommend_dimensions(prepared, settings, settings.target_object)
    except Exception:
        if previous_contact < 0 and getattr(settings, 'contact_patch_index', -1) >= 0:
            settings.contact_patch_index = previous_contact
        raise
    key = settings.as_pointer()
    _applying.add(key)
    try:
        settings.connector_diameter_mm = result['diameter_mm']
        settings.connector_length_mm = result['length_mm']
        settings.connector_chamfer_mm = result['chamfer_mm']
        if settings.connector_type == 'CAPSULE':
            settings.connector_capsule_length_mm = result['capsule_length_mm']
        settings.connector_dimensions_customized = False
        settings['_connector_auto_sizing'] = json.dumps({
            'dimensions': [float(settings.connector_diameter_mm),
                           float(settings.connector_length_mm),
                           float(settings.connector_chamfer_mm),
                           float(settings.connector_capsule_length_mm)],
            'cut_signature': prepared.cut_signature,
            'sizing_configuration': _sizing_configuration(settings),
        }, separators=(',', ':'))
    finally:
        _applying.discard(key)
    manual_note = (' Centro usado como referência; valide as posições manuais.'
                   if result.get('manual_reference') else '')
    manual_note_en = (' Center used as a reference; validate manual positions.'
                      if result.get('manual_reference') else '')
    settings.connector_sizing_status = report_msg(
        f"Sugestão: Ø {result['diameter_mm']:g} × {result['length_mm']:g} mm; profundidade verificada.{manual_note}",
        f"Suggestion: Ø {result['diameter_mm']:g} × {result['length_mm']:g} mm; depth checked.{manual_note_en}")
    return result


def defaults_untouched(settings):
    if settings.connector_dimensions_customized:
        return False
    try:
        suggested = json.loads(settings.get('_connector_auto_sizing', '{}'))
        saved = suggested.get('dimensions', ())
        current = (settings.connector_diameter_mm, settings.connector_length_mm,
                   settings.connector_chamfer_mm, settings.connector_capsule_length_mm)
        if len(saved) == len(current) and all(abs(float(a)-float(b)) <= 1e-5
                                             for a, b in zip(saved, current)):
            return True
    except (ValueError, TypeError, AttributeError):
        pass
    # Older files serialize the historical defaults (Ø6 × 8 mm) as explicit
    # values. The edit callback is the provenance bit for user changes; when
    # it is false, treat saved values that still equal RNA defaults as untouched.
    # A non-default saved value remains protected for old files that predate
    # the provenance flag.
    names = (
        'connector_diameter_mm', 'connector_length_mm', 'connector_chamfer_mm',
        'connector_capsule_length_mm')
    for name in names:
        if not settings.is_property_set(name):
            continue
        default = settings.bl_rna.properties[name].default
        if abs(float(getattr(settings, name)) - float(default)) > 1e-5:
            return False
    return True


def automatic_suggestion_current(context):
    """True only when the last automatic dimensions still match this cut."""
    settings = context.scene.chest_splitter
    target = settings.target_object
    if not target:
        return False
    try:
        data = json.loads(settings.get('_connector_auto_sizing', '{}'))
        if not data.get('cut_signature'):
            return False
        from .connector_surface import compute_cut_signature
        signature = compute_cut_signature(settings, target, context.scene) + ':' + settings.connector_male_part
        return (data['cut_signature'] == signature
                and data.get('sizing_configuration') == _sizing_configuration(settings))
    except (ValueError, TypeError, AttributeError, RuntimeError):
        return False


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
        except (ValueError, RuntimeError, ConnectorValidationError) as exc:
            from .localized_errors import render_message
            reason = render_message(exc)
            settings.connector_sizing_status = report_msg(
                f'Não foi possível sugerir dimensões: {reason}',
                f'Could not suggest dimensions: {reason}')
            self.report({'INFO'}, settings.connector_sizing_status)
            return {'CANCELLED'}
        self.report({'INFO'}, settings.connector_sizing_status)
        return {'FINISHED'}
