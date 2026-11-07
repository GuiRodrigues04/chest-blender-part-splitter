"""Keep replaced results out of Parts without losing operation references."""
import re
import bpy
from bpy.app.handlers import persistent
from .constants import COLLECTION_PARTS_NAME, ROLE_COMMITTED_PART

HISTORY_NAME = 'Histórico de cortes'


def archive_target(scene, target):
    from .lifecycle import get_or_create_collection, find_collection
    if not target or target.get('chest_role') != ROLE_COMMITTED_PART:
        return
    parts = find_collection(scene, COLLECTION_PARTS_NAME)
    if not parts or target.name not in parts.objects:
        return
    history = get_or_create_collection(scene, HISTORY_NAME)
    if target.name not in history.objects:
        history.objects.link(target)
    parts.objects.unlink(target)
    target['chest_archived'] = True
    target.hide_viewport = False
    target.hide_render = True
    target.hide_set(True)


def restore_target(scene, target):
    from .lifecycle import get_or_create_collection, find_collection
    if not target or not target.get('chest_archived'):
        return
    parts = get_or_create_collection(scene, COLLECTION_PARTS_NAME)
    if target.name not in parts.objects:
        parts.objects.link(target)
    history = find_collection(scene, HISTORY_NAME)
    if history and target.name in history.objects:
        history.objects.unlink(target)
    del target['chest_archived']


def organize_history(scene):
    settings = getattr(scene, 'chest_splitter', None)
    if not settings:
        return
    for record in scene.chest_operations:
        target = record.target_object
        if (record.status == 'COMMITTED' and target and
                target != settings.target_object and target.hide_viewport):
            archive_target(scene, target)


@persistent
def on_load(_):
    for scene in bpy.data.scenes:
        organize_history(scene)


def result_names(scene, target, work_suffix):
    name = target.name.replace(work_suffix, '')
    if target.get('chest_default_name') == target.name:
        name = target.get('chest_name_root', name)
    elif target.get('chest_role') == ROLE_COMMITTED_PART:
        # Migrate the legacy generated chain; leave manual names intact.
        name = re.sub(r'(?:__[AB])+(?:\.\d{3})?$', '', name)
    number = int(scene.get('chest_cut_number', 0)) + 1
    while any(f'{name} — {kind} {number:03d}' in bpy.data.objects for kind in ('Peça', 'Restante')):
        number += 1
    return name, number


def register():
    if on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load)
    # Blender restricts bpy.data while enabling an add-on. Organize the
    # existing scene after registration, never during that restricted phase.
    if hasattr(bpy.data, 'scenes'):
        on_load(None)
    elif not bpy.app.timers.is_registered(_after_register):
        bpy.app.timers.register(_after_register, first_interval=.1)


def _after_register():
    on_load(None)
    return None


def unregister():
    if bpy.app.timers.is_registered(_after_register):
        bpy.app.timers.unregister(_after_register)
    if on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load)
