"""Scene membership checks shared by drawing, preparation and execution."""

import bpy


def uses_surface_region(settings):
    return bool((settings.split_mode == 'LOOP' and settings.loop_behavior == 'WHOLE')
                or (settings.split_mode == 'MATERIAL' and settings.material_extraction_mode == 'WHOLE'))


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


def activate_target_for_selection(context, target):
    """Reveal one target collection path, include it in local views, and activate it.

    Clearing object visibility alone does not undo collection selection locks or
    local-view exclusion. Other collection paths and object geometry stay intact.
    """
    if not object_in_scene(target, context.scene, mesh=True):
        raise RuntimeError('Objeto alvo não encontrado nesta cena.')
    if not target.is_editable:
        raise RuntimeError('O alvo está vinculado a uma biblioteca; torne-o local para editar.')
    if context.mode != 'OBJECT':
        raise RuntimeError('Não foi possível sair do modo de edição anterior.')
    paths = []

    def visit(layer, parents):
        path = parents + [layer]
        if layer.collection.objects.get(target.name) == target:
            paths.append(path)
        for child in layer.children:
            visit(child, path)

    visit(context.view_layer.layer_collection, [])
    if not paths:
        raise RuntimeError('O alvo não possui uma coleção nesta camada de visualização.')
    path = min(paths, key=lambda layers: sum(
        int(layer.exclude) + int(layer.hide_viewport) + int(layer.collection.hide_viewport)
        + int(layer.collection.hide_select) for layer in layers))
    for layer in path:
        if layer.exclude:
            layer.exclude = False
        layer.hide_viewport = False
        layer.collection.hide_viewport = False
        layer.collection.hide_select = False
    target.hide_viewport = False
    target.hide_select = False
    context.view_layer.update()
    target.hide_set(False, view_layer=context.view_layer)
    for area in context.screen.areas if context.screen else []:
        if area.type == 'VIEW_3D' and area.spaces.active.local_view:
            target.local_view_set(area.spaces.active, True)
    for obj in context.view_layer.objects:
        obj.select_set(False)
    target.select_set(True)
    context.view_layer.objects.active = target
    context.view_layer.update()
    if not target.select_get() or not target.visible_get(view_layer=context.view_layer):
        raise RuntimeError('O alvo continua oculto ou bloqueado nesta camada de visualização.')
