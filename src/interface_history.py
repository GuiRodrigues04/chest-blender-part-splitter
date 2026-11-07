"""Preserve cavity provenance and recover legacy marks from actual ancestors."""
import array
import hashlib
from contextlib import contextmanager, ExitStack
from mathutils import Vector
from mathutils.bvhtree import BVHTree

CONTACT = 'splitter_contact_surface'
PREVIOUS = 'splitter_previous_interface'
_RECOVERED = {}


def archive_contact_marks(bm):
    current = bm.faces.layers.int.get(CONTACT)
    if current is None:
        return
    previous = bm.faces.layers.int.get(PREVIOUS) or bm.faces.layers.int.new(PREVIOUS)
    patch = bm.faces.layers.int.get('splitter_contact_patch')
    for face in bm.faces:
        if face[current]:
            face[previous] = 1
        face[current] = 0
        if patch is not None:
            face[patch] = 0


def _ancestor_sources(scene, obj):
    records = {r.operation_id:r for r in getattr(scene, 'chest_operations', ())}
    operation = obj.get('chest_operation_id', '')
    seen, sources, pointers = set(), [], {obj.as_pointer()}
    while operation and operation not in seen:
        seen.add(operation)
        record = records.get(operation)
        if record is None or record.status not in {'COMMITTED', 'PREVIEW'}:
            break
        snapshot = record.snapshot_object
        if (snapshot and snapshot.type == 'MESH' and
                snapshot.get('chest_role') == 'RESTORE_BACKUP' and
                snapshot.get('chest_operation_id') == operation and
                snapshot.as_pointer() not in pointers):
            sources.append(snapshot)
            pointers.add(snapshot.as_pointer())
        # Only the input explicitly recorded for this ancestor is eligible.
        target = record.target_object
        if target and target.type == 'MESH' and target.as_pointer() not in pointers:
            sources.append(target)
            pointers.add(target.as_pointer())
        operation = record.parent_operation_id
    return sources


@contextmanager
def _readable_mesh(obj):
    """Read geometry and face tags from the same edit-mode snapshot.

    Mesh.attributes can expose a named layer with zero RNA values in Edit Mode,
    even after update_from_editmode(). The authoritative tags live in BMesh.
    """
    if obj.mode != 'EDIT':
        yield obj.data
        return
    import bpy
    import bmesh
    mesh = bpy.data.meshes.new('_splitter_interface_history_read')
    bm = bmesh.from_edit_mesh(obj.data).copy()
    try:
        bm.to_mesh(mesh)
        yield mesh
    finally:
        bm.free()
        bpy.data.meshes.remove(mesh)


def recover_previous_interfaces(scene, obj):
    """Restore tags only, from coincident marked surfaces in this cut lineage.

    Unrelated objects, names, arbitrary backups and geometry heuristics cannot
    authorize an interface. No coordinates, material, selection or topology are
    edited. Without trustworthy historical surfaces the wall check stays strict.
    """
    if obj is None or obj.type != 'MESH':
        return 0
    editing = obj.mode == 'EDIT'
    if editing:
        if obj.data.users > 1:
            return 0
    sources = _ancestor_sources(scene, obj)
    if not sources:
        return 0
    with ExitStack() as stack:
        meshes = {item.as_pointer(): stack.enter_context(_readable_mesh(item))
                  for item in [obj] + sources}
        return _recover_previous_interfaces(scene, obj, sources, meshes, editing)


def _recover_previous_interfaces(scene, obj, sources, meshes, editing):
    from .input_state import update_mesh_hash
    digest = hashlib.sha256()
    for item in [obj] + sources:
        digest.update(str(item.as_pointer()).encode())
        readable = meshes[item.as_pointer()]
        update_mesh_hash(digest, readable)
        digest.update(repr(tuple(tuple(row) for row in item.matrix_world)).encode())
        for name in (CONTACT, PREVIOUS):
            attr = readable.attributes.get(name)
            if attr is not None and attr.domain == 'FACE' and attr.data_type == 'INT':
                values = array.array('i', [0]) * len(attr.data)
                attr.data.foreach_get('value', values)
                digest.update(name.encode() + values.tobytes())
    stamp = digest.digest()
    if _RECOVERED.get(obj.as_pointer()) == stamp:
        return 0
    vertices, triangles = [], []
    for source in sources:
        mesh = meshes[source.as_pointer()]
        markers = [mesh.attributes.get(n) for n in (CONTACT, PREVIOUS)]
        markers = [m for m in markers if m and m.domain == 'FACE' and m.data_type == 'INT']
        if not markers:
            continue
        mesh.calc_loop_triangles()
        base = len(vertices)
        vertices.extend(source.matrix_world @ v.co for v in mesh.vertices)
        reflected = source.matrix_world.determinant() < 0
        for tri in mesh.loop_triangles:
            if any(m.data[tri.polygon_index].value for m in markers):
                ids = list(tri.vertices)
                if reflected:
                    ids.reverse()
                triangles.append(tuple(base+i for i in ids))
    if not triangles:
        _RECOVERED[obj.as_pointer()] = stamp
        return 0
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    scale = scene.unit_settings.scale_length * 1000
    tolerance = .0001 / max(scale, 1e-6)
    matrix = obj.matrix_world
    if abs(matrix.determinant()) < 1e-12:
        return 0
    normal_matrix = matrix.to_3x3().inverted().transposed()
    mesh = meshes[obj.as_pointer()]
    mesh.calc_loop_triangles()
    centers = {}
    for tri in mesh.loop_triangles:
        centers.setdefault(tri.polygon_index, []).append(
            sum((matrix @ mesh.vertices[i].co for i in tri.vertices), Vector()) / 3)
    previous = mesh.attributes.get(PREVIOUS)
    current = mesh.attributes.get(CONTACT)
    matches = []
    for face in mesh.polygons:
        if ((previous and previous.data[face.index].value) or
                (current and current.data[face.index].value)):
            continue
        points = [matrix @ mesh.vertices[i].co for i in face.vertices]
        normal = (normal_matrix @ face.normal).normalized()
        # Edge/vertex normals are ambiguous at shared boundaries: require
        # position there, and orientation at face/interior triangle centers.
        interior = [sum(points, Vector()) / len(points)] + centers.get(face.index, [])
        boundary = points + [(a+b)/2 for a,b in zip(points, points[1:]+points[:1])]
        valid = True
        for point, oriented in [(p,False) for p in boundary] + [(p,True) for p in interior]:
            hit = tree.find_nearest(point)
            if (hit[0] is None or hit[3] > tolerance or
                    (oriented and hit[1].dot(normal) < .99)):
                valid = False
                break
        if valid:
            matches.append(face.index)
    if matches:
        mesh = obj.data
        # Do not change another object's shared mesh metadata as a side effect.
        if mesh.users > 1:
            obj.data = mesh.copy()
            mesh = obj.data
        if editing:
            import bmesh
            bm = bmesh.from_edit_mesh(mesh)
            bm.faces.ensure_lookup_table()
            layer = bm.faces.layers.int.get(PREVIOUS) or bm.faces.layers.int.new(PREVIOUS)
            for index in matches:
                bm.faces[index][layer] = 1
            bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
            obj.update_from_editmode()
        else:
            previous = mesh.attributes.get(PREVIOUS) or mesh.attributes.new(PREVIOUS, 'INT', 'FACE')
            for index in matches:
                previous.data[index].value = 1
            mesh.update()
        from .connector_surface import clear_prepared_split_cache
        clear_prepared_split_cache()
        # The stamp changed only in our own output tags. Recheck once on the
        # next call, then identical calls use the fast path above.
    else:
        _RECOVERED[obj.as_pointer()] = stamp
    return len(matches)


def clear_recovery_cache(*_):
    _RECOVERED.clear()
