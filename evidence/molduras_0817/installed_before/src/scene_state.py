"""Scene membership checks shared by drawing, preparation and execution."""

import bpy


def object_in_scene(obj, scene, mesh=False):
    try:
        return bool(
            obj is not None
            and scene is not None
            and scene.objects.get(obj.name) == obj
            and (not mesh or obj.type == "MESH")
        )
    except ReferenceError:
        return False
