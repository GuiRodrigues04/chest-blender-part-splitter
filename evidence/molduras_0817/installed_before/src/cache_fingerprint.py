"""Compact content signatures for viewport caches."""

from array import array
from hashlib import blake2b
from struct import pack
import bpy
from bpy.app.handlers import persistent


_MESH_REVISIONS = {}
_MESH_FINGERPRINTS = {}
_GEOMETRY_EPOCH = 0


@persistent
def invalidate_geometry_fingerprints(scene, depsgraph):
    """Only touch Python caches; evaluating or writing IDs in a handler is unsafe."""
    changed = set()
    for update in depsgraph.updates:
        if not update.is_updated_geometry:
            continue
        obj = update.id.original
        mesh = obj if isinstance(obj, bpy.types.Mesh) else getattr(obj, 'data', None)
        if isinstance(mesh, bpy.types.Mesh):
            changed.add(mesh.as_pointer())
    for pointer in changed:
        _MESH_REVISIONS[pointer] = _MESH_REVISIONS.get(pointer, 0) + 1
        for materials in (False, True):
            _MESH_FINGERPRINTS.pop((pointer, materials), None)


@persistent
def clear_geometry_fingerprints(*_):
    global _GEOMETRY_EPOCH
    _GEOMETRY_EPOCH += 1
    _MESH_REVISIONS.clear()
    _MESH_FINGERPRINTS.clear()


def geometry_revision(mesh):
    return _GEOMETRY_EPOCH, _MESH_REVISIONS.get(mesh.as_pointer(), 0)


def cached_mesh_geometry_fingerprint(mesh, include_materials=False):
    """Scan at most once per depsgraph geometry revision and cache variant."""
    key = mesh.as_pointer(), include_materials
    cached = _MESH_FINGERPRINTS.get(key)
    if cached is None:
        cached = mesh_geometry_fingerprint(mesh, include_materials)
        _MESH_FINGERPRINTS[key] = cached
    return cached


def register():
    clear_geometry_fingerprints()
    for handlers, callback in (
        (bpy.app.handlers.depsgraph_update_post, invalidate_geometry_fingerprints),
        (bpy.app.handlers.load_post, clear_geometry_fingerprints),
        (bpy.app.handlers.undo_post, clear_geometry_fingerprints),
        (bpy.app.handlers.redo_post, clear_geometry_fingerprints),
    ):
        if callback not in handlers:
            handlers.append(callback)


def unregister():
    for handlers, callback in (
        (bpy.app.handlers.depsgraph_update_post, invalidate_geometry_fingerprints),
        (bpy.app.handlers.load_post, clear_geometry_fingerprints),
        (bpy.app.handlers.undo_post, clear_geometry_fingerprints),
        (bpy.app.handlers.redo_post, clear_geometry_fingerprints),
    ):
        if callback in handlers:
            handlers.remove(callback)
    clear_geometry_fingerprints()


def mesh_geometry_fingerprint(mesh, include_materials=False):
    """Include coordinates and connectivity, also when topology counts are unchanged."""
    digest = blake2b(digest_size=20)

    def add(collection, attribute, typecode, width=1):
        # foreach_get copies RNA buffers in C; keep only a fixed-size digest in
        # the cache, and never allocate a Python object per vertex or loop.
        values = array(typecode, [0]) * (len(collection) * width)
        collection.foreach_get(attribute, values)
        digest.update(attribute.encode('ascii'))
        digest.update(pack('<Q', len(values)))
        digest.update(memoryview(values).cast('B'))

    add(mesh.vertices, 'co', 'f', 3)
    add(mesh.edges, 'vertices', 'i', 2)
    add(mesh.loops, 'vertex_index', 'i')
    add(mesh.polygons, 'loop_start', 'i')
    add(mesh.polygons, 'loop_total', 'i')
    if include_materials:
        add(mesh.polygons, 'material_index', 'i')
    return mesh.as_pointer(), digest.digest()


