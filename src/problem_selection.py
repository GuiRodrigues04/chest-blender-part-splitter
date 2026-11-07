"""Locate editable topology defects without changing coordinates or connectivity."""
import bpy
import bmesh
from bpy.props import EnumProperty


def publish_cutter_diagnostics(settings, obj, scene, evaluated=False):
    """Inspect a snapshot; keep cutter metrics separate from target diagnostics."""
    from .diagnostic import get_scene_scale_to_mm, validate_bmesh_mesh_geometry
    from .translations import report_msg
    scale = get_scene_scale_to_mm(scene)
    bm = bmesh.new()
    eval_obj = None
    try:
        if obj.mode == 'EDIT':
            obj.update_from_editmode()
        use_evaluated = evaluated and any(m.show_viewport for m in obj.modifiers)
        if use_evaluated:
            bpy.context.view_layer.update()
            eval_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            bm.from_mesh(eval_obj.to_mesh())
        elif obj.mode == 'EDIT':
            bm.free()
            bm = bmesh.from_edit_mesh(obj.data).copy()
        else:
            bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        bm.normal_update()
        report = validate_bmesh_mesh_geometry(bm, scale)
        counts = {
            'boundary': sum(e.is_boundary for e in bm.edges),
            'wire': sum(e.is_wire for e in bm.edges),
            'multiple': sum(len(e.link_faces)>2 for e in bm.edges),
            'winding': sum(e.is_manifold and not e.is_contiguous for e in bm.edges),
            'vertices': sum(not v.is_manifold for v in bm.verts),
            'degenerate': len(report['degenerate_faces']),
            'null': len(report['null_edges']),
        }
        valid_volume = bool(bm.faces) and abs(report['volume_mm3'])>1e-4
        settings.solid_cutter_non_manifold_edges = len(report['non_manifold_edges'])
        settings.solid_cutter_triangles = sum(len(f.verts)-2 for f in bm.faces)
        settings.solid_cutter_volume_mm3 = abs(report['volume_mm3'])
        settings.solid_cutter_dims_mm = tuple((max((v.co[i] for v in bm.verts),default=0)-min((v.co[i] for v in bm.verts),default=0))*scale for i in range(3))
        settings.solid_cutter_is_manifold = bool(bm.faces) and report['is_manifold']
        settings.solid_cutter_has_problems = any(counts.values()) or not valid_volume
        settings.solid_cutter_diag_evaluated = use_evaluated
        labels = {
            'boundary': ('bordas abertas', 'boundary edges'),
            'wire': ('arestas soltas', 'wire edges'),
            'multiple': ('arestas com mais de duas faces', 'edges with more than two faces'),
            'winding': ('arestas com orientação incompatível', 'edges with inconsistent winding'),
            'vertices': ('vértices não-manifold', 'non-manifold vertices'),
            'degenerate': ('faces degeneradas', 'degenerate faces'),
            'null': ('arestas de comprimento nulo', 'zero-length edges'),
        }
        summary = [report_msg(f'{count} {labels[key][0]}',f'{count} {labels[key][1]}') for key,count in counts.items() if count]
        if not valid_volume:
            summary.append(report_msg('sem volume fechado válido', 'no valid closed volume'))
        settings.solid_cutter_problem_summary = ' | '.join(summary)
        return settings.solid_cutter_has_problems
    finally:
        bm.free()
        if eval_obj is not None:
            eval_obj.to_mesh_clear()


def problem_elements(bm, matrix_world, unit_scale):
    from .diagnostic import validate_bmesh_mesh_geometry
    bm.verts.index_update();bm.edges.index_update();bm.faces.index_update()
    world = bm.copy()
    try:
        world.transform(matrix_world)
        report = validate_bmesh_mesh_geometry(world, unit_scale)
        degenerate = set(report['degenerate_faces'])
        null_edges = set(report['null_edges'])
    finally:
        world.free()
    edges = {e for e in bm.edges if not e.is_manifold or not e.is_contiguous or e.index in null_edges}
    faces = {f for f in bm.faces if f.index in degenerate}
    for face in faces:
        edges.update(face.edges)
    vertices = {v for e in edges for v in e.verts}
    vertices.update(v for v in bm.verts if not v.is_manifold)
    # Group nearby faulty elements, never flood through the healthy surface.
    remaining = set(vertices)
    groups = []
    while remaining:
        seed = remaining.pop();component = {seed};stack = [seed]
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other);component.add(other);stack.append(other)
        groups.append(component)
    groups.sort(key=lambda group: min(v.index for v in group))
    return vertices, edges, faces, groups


def focus_selection(context):
    """Use an actual 3D window when available; headless calls still select defects."""
    if not context.screen:
        return
    areas = [area for area in context.screen.areas if area.type == 'VIEW_3D']
    if context.area and context.area.type == 'VIEW_3D':
        areas = [context.area]
    for area in areas:
        space = area.spaces.active
        space.overlay.show_overlays = True
        space.shading.type = 'SOLID'
        space.shading.show_xray = True
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region:
            with context.temp_override(area=area, region=region):
                if bpy.ops.view3d.view_selected.poll():
                    bpy.ops.view3d.view_selected(use_all_regions=False)
        area.tag_redraw()


class CHEST_OT_splitter_locate_problems(bpy.types.Operator):
    bl_idname = 'chest.splitter_locate_problems'
    bl_label = 'Localizar problemas'
    bl_description = 'Seleciona falhas da malha no Modo de Edição e aproxima a vista, sem reparar a geometria'
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(items=[('ALL','Todos','Selecionar todas as regiões problemáticas'),
                              ('NEXT','Próximo','Focar uma região problemática por vez'),
                              ('CHECK','Atualizar diagnóstico','Reexaminar a malha sem mudar seleção ou modo')], default='ALL')
    subject: EnumProperty(items=[('TARGET','Alvo','Examinar o corpo principal'),
                                 ('CUTTER','Cortador','Examinar o sólido de corte')], default='TARGET')

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, 'chest_splitter', None)
        from .scene_state import object_in_scene
        return bool(settings and any(object_in_scene(obj,context.scene,mesh=True)
                    for obj in (settings.target_object,settings.solid_cutter_object)))

    def execute(self, context):
        from .diagnostic import get_scene_scale_to_mm, analyze_target_mesh
        from .translations import report_msg
        from .operators import CHEST_OT_splitter_repair_target_mesh
        settings = context.scene.chest_splitter
        from .scene_state import object_in_scene
        obj = settings.solid_cutter_object if self.subject == 'CUTTER' else settings.target_object
        if not object_in_scene(obj,context.scene,mesh=True):
            self.report({'WARNING'},report_msg('Selecione uma malha válida para examinar.','Select a valid mesh to inspect.'))
            return {'CANCELLED'}
        if self.mode == 'CHECK':
            if self.subject == 'CUTTER':
                issues = publish_cutter_diagnostics(settings,obj,context.scene,evaluated=True)
                message = settings.solid_cutter_problem_summary if issues else report_msg('Diagnóstico do cortador atualizado: nenhum defeito topológico encontrado.','Cutter diagnostics refreshed: no topology issues found.')
            else:
                if obj.mode == 'EDIT':obj.update_from_editmode()
                CHEST_OT_splitter_repair_target_mesh._publish_diagnostics(settings,analyze_target_mesh(obj,context.scene))
                issues = not settings.diag_is_manifold
                message = report_msg('Diagnóstico do alvo atualizado.','Target diagnostics refreshed.')
            settings.last_status = message
            settings.last_status_level = 'WARNING' if issues else 'INFO'
            self.report({'INFO'},message)
            return {'FINISHED'}
        if self.subject == 'CUTTER':
            from .solid_tools import reveal_cutter
            reveal_cutter(context,obj)
        if obj.mode != 'EDIT' or context.edit_object != obj:
            if context.object and context.object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            for item in context.selected_objects:
                item.select_set(False)
            obj.hide_viewport = False;obj.hide_set(False);obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(obj.data)
        vertices, edges, faces, groups = problem_elements(bm, obj.matrix_world, get_scene_scale_to_mm(context.scene))
        previous = {v for v in bm.verts if v.select}
        index = None
        if self.mode == 'NEXT' and groups:
            matched = [i for i, group in enumerate(groups) if previous.intersection(group)]
            index = (matched[0]+1)%len(groups) if len(matched) == 1 else 0
            vertices = groups[index]
            edges = {e for e in edges if all(v in vertices for v in e.verts)}
            faces = {f for f in faces if all(v in vertices for v in f.verts)}
        context.tool_settings.mesh_select_mode = (True, True, False)
        for face in bm.faces:face.select_set(False)
        for edge in bm.edges:edge.select_set(False)
        for vert in bm.verts:vert.select_set(False)
        bm.select_history.clear()
        for face in faces:face.hide_set(False)
        for edge in edges:edge.hide_set(False);edge.select_set(True)
        for vert in vertices:vert.hide_set(False);vert.select_set(True)
        if vertices:bm.select_history.add(min(vertices, key=lambda v:v.index))
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        # Refresh diagnostics after manual edits, including evaluated modifiers.
        obj.update_from_editmode()
        if self.subject == 'CUTTER':
            publish_cutter_diagnostics(settings,obj,context.scene,evaluated=True)
            has_issues = settings.solid_cutter_has_problems
        else:
            CHEST_OT_splitter_repair_target_mesh._publish_diagnostics(settings, analyze_target_mesh(obj, context.scene))
            has_issues = not settings.diag_is_manifold
        if vertices:
            group_text = (f'Região {index+1}/{len(groups)}' if index is not None else f'{len(groups)} região(ões)')
            group_en = (f'Region {index+1}/{len(groups)}' if index is not None else f'{len(groups)} region(s)')
            message = report_msg(
                f'{group_text}: {len(edges)} aresta(s) e {len(vertices)} vértice(s) destacados para correção manual.',
                f'{group_en}: {len(edges)} edge(s) and {len(vertices)} vertex/vertices highlighted for manual correction.')
            focus_selection(context)
        else:
            message = report_msg(
                'Nenhum problema topológico encontrado na malha editável.',
                'No topology issues found in the editable mesh.')
            if any(m.show_viewport for m in obj.modifiers) and has_issues:
                message += report_msg(
                    ' A falha está no resultado dos modificadores; inspecione esse resultado em uma cópia.',
                    ' The defect is in the modifier output; inspect that output on a copy.')
            elif self.subject == 'CUTTER' and has_issues:
                message += ' ' + settings.solid_cutter_problem_summary
        settings.last_status = message
        settings.last_status_level = 'WARNING' if vertices or has_issues else 'INFO'
        self.report({'INFO'}, message)
        return {'FINISHED'}
