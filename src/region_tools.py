"""Explicit surface capture and physical preview contact selection."""
import json
from .translations import localize_text
import bpy
import bmesh
from bpy.props import IntProperty, BoolProperty
from .geometry_region import mesh_signature, PATCH


class CHEST_OT_splitter_capture_region(bpy.types.Operator):
    bl_idname = 'chest.splitter_capture_region'
    bl_label = 'Capturar faces para separar'
    bl_options = {'REGISTER', 'UNDO'}
    use_material: BoolProperty(default=False, options={'HIDDEN'})

    def execute(self, context):
        s = context.scene.chest_splitter
        obj = s.target_object
        if not obj or obj.type != 'MESH' or (not self.use_material and context.edit_object != obj):
            self.report({'ERROR'}, localize_text('Use Editar alvo e selecione as faces da peça no modo de edição.'))
            return {'CANCELLED'}
        if obj.mode == 'EDIT':
            obj.update_from_editmode()
        if self.use_material:
            from .geometry_material import get_material_regions
            bm = bmesh.new()
            try:
                bm.from_mesh(obj.data)
                regions = get_material_regions(bm, s.material_split_index)
                if not 0 <= s.material_region_index < len(regions):
                    self.report({'ERROR'}, localize_text('Escolha uma região de material válida no alvo.'))
                    return {'CANCELLED'}
                selected = sorted(regions[s.material_region_index])
            finally:
                bm.free()
        else:
            if context.tool_settings.mesh_select_mode[2]:
                selected = [f.index for f in obj.data.polygons if f.select]
            else:
                bm=bmesh.from_edit_mesh(obj.data);bm.faces.index_update()
                border={e for e in bm.edges if e.select}
                verts={v for e in border for v in e.verts}
                if len(border)<3 or any(sum(e in border for e in v.link_edges)!=2 for v in verts):
                    self.report({'ERROR'}, localize_text('Selecione as faces da peça ou um contorno fechado sem bifurcações.'))
                    return {'CANCELLED'}
                remaining=set(bm.faces);components=[]
                while remaining:
                    first=remaining.pop();group={first};stack=[first]
                    while stack:
                        face=stack.pop()
                        for edge in face.edges:
                            if edge in border:continue
                            for other in edge.link_faces:
                                if other in remaining:
                                    remaining.remove(other);group.add(other);stack.append(other)
                    components.append(group)
                if len(components)!=2:
                    self.report({'ERROR'}, localize_text('O contorno deve separar duas regiões. Para outros casos, selecione as faces.'))
                    return {'CANCELLED'}
                if s.loop_is_captured and s.loop_seed_face_index>=0:
                    group=next((g for g in components if any(f.index==s.loop_seed_face_index for f in g)),None)
                else:
                    components.sort(key=lambda g:sum(f.calc_area() for f in g));group=components[0]
                    if sum(f.calc_area() for f in group)>.45*sum(f.calc_area() for f in bm.faces):
                        self.report({'ERROR'}, localize_text('Contorno ambíguo: indique uma face do lado desejado ou selecione as faces da peça.'))
                        return {'CANCELLED'}
                if not group:return {'CANCELLED'}
                selected=sorted(f.index for f in group)
        if not selected or len(selected) == len(obj.data.polygons):
            self.report({'ERROR'}, localize_text('Selecione somente a superfície da peça que deseja separar.'))
            return {'CANCELLED'}
        if any(m.show_viewport for m in obj.modifiers):
            self.report({'ERROR'}, localize_text('Aplique os modificadores em uma cópia antes de capturar.'))
            return {'CANCELLED'}
        s.region_target = obj
        s.region_face_indices = ','.join(map(str, selected))
        s.region_mesh_signature = mesh_signature(obj.data)
        s.contact_patch_index = -1
        s.contact_choices = '[]'
        s.connector_enabled = False
        # This operation explicitly starts an exact, zero-gap surface separation.
        s.assembly_clearance_preset = 'CUSTOM'
        s.part_clearance_mm = 0
        s.invert_sides = False
        s.split_mode = 'MATERIAL' if self.use_material else 'LOOP'
        if self.use_material:s.material_extraction_mode = 'WHOLE'
        else:s.loop_behavior = 'WHOLE'
        s.region_selection_enabled = True
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, localize_text('{count} faces capturadas. Folga entre peças: 0 mm. Gere a prévia.').format(count=len(selected)))
        return {'FINISHED'}


class CHEST_OT_splitter_choose_contact(bpy.types.Operator):
    bl_idname = 'chest.splitter_choose_contact'
    bl_label = 'Escolher contato para os pinos'
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty(default=-1)

    def execute(self, context):
        s = context.scene.chest_splitter
        if s.target_object and s.target_object.mode=='EDIT':s.target_object.update_from_editmode()
        if self.index == -2:
            s.contact_patch_index = -1
            s.connector_enabled = False
            s.contact_choices = '[]'
            self.report({'INFO'}, localize_text('Gere uma prévia sem pinos e escolha o novo contato.'))
            if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
            return bpy.ops.chest.splitter_generate_preview()
        from .input_state import cut_signature, contact_signature
        if not s.target_object or s.contact_input_signature != contact_signature(s, s.target_object, context.scene):
            self.report({'ERROR'}, localize_text('A geometria do corte mudou. Use Reescolher contato e gere a prévia novamente.'))
            return {'CANCELLED'}
        choices = json.loads(s.contact_choices or '[]')
        index = self.index
        if index < 0:
            obj = context.edit_object
            if not obj or obj.name not in ('SPLITTER_PREVIEW_A', 'SPLITTER_PREVIEW_B'):
                self.report({'ERROR'}, localize_text('Entre no modo de edição de uma prévia e selecione uma face do contato.'))
                return {'CANCELLED'}
            bm = bmesh.from_edit_mesh(obj.data)
            layer = bm.faces.layers.int.get(PATCH)
            selected=[f for f in bm.faces if f.select]
            labels = {f[layer]-1 for f in selected} if layer and selected and all(f[layer]>0 for f in selected) else set()
            index = next(iter(labels)) if len(labels)==1 else -1
        if not any(p['index']==index for p in choices):
            self.report({'ERROR'}, localize_text('Escolha uma superfície nova do corte, não uma face exterior da peça.'))
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        previous=s.contact_patch_index
        if previous!=index or s.session_status!='PREVIEW_VALID':
            s.contact_patch_index = index
            s.connector_enabled=False
            try:
                result=bpy.ops.chest.splitter_generate_preview()
            except RuntimeError:
                s.contact_patch_index=previous
                return {'CANCELLED'}
            if result!={'FINISHED'}:
                s.contact_patch_index=previous
                return {'CANCELLED'}
            s.manual_connectors.clear()
        # Highlight the generated planar seat, not an individual source triangle.
        for name in ('SPLITTER_PREVIEW_A', 'SPLITTER_PREVIEW_B'):
            obj = bpy.data.objects.get(name)
            if obj:
                obj.hide_set(False)
                attr = obj.data.attributes.get(PATCH)
                for face in obj.data.polygons:
                    face.select = bool(attr and attr.data[face.index].value==index+1)
        preview = bpy.data.objects.get('SPLITTER_PREVIEW_A')
        if preview:
            for obj in context.view_layer.objects:
                obj.select_set(False)
            preview.hide_set(False)
            preview.select_set(True)
            context.view_layer.objects.active = preview
            context.tool_settings.mesh_select_mode = (False, False, True)
            bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'}, localize_text('Contato {index} destacado. Ative os encaixes e atualize a prévia.').format(index=index+1))
        return {'FINISHED'}
