"""Small viewport tools for picking cutter vertices and a mating face."""

import bpy
import bmesh
from bpy_extras import view3d_utils
from .geometry_solid import align_vertices
from .scene_state import object_in_scene
from .translations import localize_text


class CHEST_OT_splitter_capture_solid_face(bpy.types.Operator):
    """Selecione uma única face do cortador em Edit Mode e capture a face de encaixe"""

    bl_idname = "chest.splitter_capture_solid_face"
    bl_label = "Capturar Face de Encaixe"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.chest_splitter
        cutter = settings.solid_cutter_object
        if not object_in_scene(cutter, context.scene, mesh=True):
            self.report(
                {"ERROR"}, localize_text("Selecione um cortador existente na cena.")
            )
            return {"CANCELLED"}
        if cutter.mode != "EDIT":
            self.report(
                {"WARNING"},
                localize_text(
                    "Entre em Edit Mode no cortador e selecione uma única face."
                ),
            )
            return {"CANCELLED"}
        bm = bmesh.from_edit_mesh(cutter.data)
        selected = [f for f in bm.faces if f.select]
        if len(selected) != 1:
            self.report(
                {"WARNING"}, localize_text("Selecione exatamente uma face no cortador.")
            )
            return {"CANCELLED"}
        bm.faces.index_update()
        settings.solid_interface_face_index = selected[0].index
        cutter.update_from_editmode()
        self.report(
            {"INFO"},
            localize_text("Face capturada. Volte ao modo Objeto para editar os pinos."),
        )
        return {"FINISHED"}


class CHEST_OT_splitter_auto_solid_face(bpy.types.Operator):
    """Escolhe a maior face plana de contato na próxima preparação do corte"""

    bl_idname = "chest.splitter_auto_solid_face"
    bl_label = "Escolher Face Automaticamente"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.chest_splitter.solid_interface_face_index = -1
        from .connector_surface import clear_prepared_split_cache

        clear_prepared_split_cache()
        return {"FINISHED"}


class CHEST_OT_splitter_align_solid_vertices(bpy.types.Operator):
    """Clique em um vértice do cortador e depois em um vértice da peça; Esc cancela"""

    bl_idname = "chest.splitter_align_solid_vertices"
    bl_label = "Alinhar por Vértices"
    bl_options = {"REGISTER", "UNDO"}

    cutter_vertex: bpy.props.IntProperty(default=-1, options={"HIDDEN"})
    target_vertex: bpy.props.IntProperty(default=-1, options={"HIDDEN"})
    _handle = None
    _hover = None
    _stage = 0
    _orig_mode = "OBJECT"
    _orig_active = None
    _cutter_obj = None
    _target_obj = None

    @classmethod
    def poll(cls, context):
        s = getattr(context.scene, "chest_splitter", None)
        return (
            s
            and object_in_scene(s.solid_cutter_object, context.scene, mesh=True)
            and object_in_scene(s.target_object, context.scene, mesh=True)
        )

    def execute(self, context):
        settings = context.scene.chest_splitter
        cutter = settings.solid_cutter_object
        target = settings.target_object
        if not cutter or not target:
            self.report({"ERROR"}, localize_text("Cortador ou alvo inválido."))
            return {"CANCELLED"}
        try:
            align_vertices(
                cutter,
                target,
                self.cutter_vertex,
                self.target_vertex,
            )
            context.view_layer.update()
            from .connector_surface import clear_prepared_split_cache
            clear_prepared_split_cache()
            from .translations import report_msg
            msg = report_msg(
                "Cortador alinhado por vértice com sucesso.",
                "Solid cutter aligned by vertex successfully."
            )
            settings.last_status = msg
            settings.last_status_level = 'SUCCESS'
            self.report({'INFO'}, msg)
        except (ValueError, ReferenceError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}

    def invoke(self, context, event):
        if not context.area or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        s = getattr(context.scene, "chest_splitter", None)
        if not s:
            return {"CANCELLED"}
        cutter = s.solid_cutter_object
        target = s.target_object
        if not object_in_scene(cutter, context.scene, mesh=True) or not object_in_scene(target, context.scene, mesh=True):
            self.report({"ERROR"}, localize_text("Cortador ou alvo inválido."))
            return {"CANCELLED"}

        self._orig_mode = context.mode
        self._orig_active = context.active_object
        self._cutter_obj = cutter
        self._target_obj = target
        self._stage = 0
        self._hover = None

        # Garante que o cortador está visível e entra no Edit Mode do cortador
        cutter.hide_viewport = False
        if hasattr(cutter, "hide_set"):
            cutter.hide_set(False)

        try:
            if context.mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            cutter.select_set(True)
            context.view_layer.objects.active = cutter
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode='EDIT')
        except Exception:
            pass

        self._area = context.area
        self._region = next(r for r in context.area.regions if r.type == "WINDOW")
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw, (), "WINDOW", "POST_VIEW"
        )
        context.area.header_text_set(
            localize_text("Clique em um vértice do cortador. Esc cancela.")
        )
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _draw(self):
        if self._hover is None:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "POINTS", {"pos": [self._hover[1]]})
        # Do not leak GPU state into Blender or other extensions.
        size = (
            gpu.state.point_size_get() if hasattr(gpu.state, "point_size_get") else 1.0
        )
        depth = gpu.state.depth_test_get()
        try:
            gpu.state.depth_test_set("NONE")
            gpu.state.point_size_set(10.0)
            shader.bind()
            shader.uniform_float("color", (1.0, 0.45, 0.05, 1.0))
            batch.draw(shader)
        finally:
            gpu.state.point_size_set(size)
            gpu.state.depth_test_set(depth)

    def _cleanup(self, restore_mode: bool = False):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        self._hover = None
        if hasattr(self, "_area") and self._area:
            self._area.header_text_set(None)
            self._area.tag_redraw()
        if restore_mode:
            try:
                target = getattr(self, "_target_obj", None)
                if target and target.name in bpy.data.objects:
                    if bpy.context.mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
                        bpy.ops.object.mode_set(mode='OBJECT')
                    bpy.ops.object.select_all(action='DESELECT')
                    target.select_set(True)
                    bpy.context.view_layer.objects.active = target
                    orig_mode = getattr(self, "_orig_mode", "OBJECT")
                    if orig_mode in ('EDIT', 'EDIT_MESH') and bpy.ops.object.mode_set.poll():
                        bpy.ops.object.mode_set(mode='EDIT')
            except Exception:
                pass

    def cancel(self, context):
        self._cleanup(restore_mode=True)

    def modal(self, context, event):
        from .connector_editor import get_view3d_canvas_region

        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._cleanup(restore_mode=True)
            return {"CANCELLED"}

        obj = self._cutter_obj if self._stage == 0 else self._target_obj
        if not object_in_scene(obj, context.scene, mesh=True):
            self._cleanup(restore_mode=True)
            return {"CANCELLED"}

        region = get_view3d_canvas_region(self._area, event.mouse_x, event.mouse_y)
        if (
            region is None
            or event.type in {"MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE"}
            or event.alt
            or event.type.startswith("NUMPAD_")
        ):
            return {"PASS_THROUGH"}

        if event.type in {"MOUSEMOVE", "LEFTMOUSE"}:
            mouse = (event.mouse_x - region.x, event.mouse_y - region.y)
            rv3d = self._area.spaces.active.region_3d
            best_distance, self._hover = 16.0**2, None
            if obj.mode == 'EDIT':
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()
                verts_iter = [(v.index, obj.matrix_world @ v.co) for v in bm.verts]
            else:
                verts_iter = [(v.index, obj.matrix_world @ v.co) for v in obj.data.vertices]

            for idx, world in verts_iter:
                screen = view3d_utils.location_3d_to_region_2d(region, rv3d, world)
                if screen is None:
                    continue
                d = (screen.x - mouse[0]) ** 2 + (screen.y - mouse[1]) ** 2
                if d < best_distance:
                    best_distance, self._hover = d, (idx, world)
            self._area.tag_redraw()

        if event.type == "LEFTMOUSE" and event.value == "PRESS" and self._hover:
            if self._stage == 0:
                self.cutter_vertex = self._hover[0]
                self._stage = 1
                self._hover = None

                # Transição: sai do Edit Mode do sólido e entra no Edit Mode do objeto principal
                target = self._target_obj
                target.hide_viewport = False
                if hasattr(target, "hide_set"):
                    target.hide_set(False)
                try:
                    if context.mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
                        bpy.ops.object.mode_set(mode='OBJECT')
                    bpy.ops.object.select_all(action='DESELECT')
                    target.select_set(True)
                    context.view_layer.objects.active = target
                    if bpy.ops.object.mode_set.poll():
                        bpy.ops.object.mode_set(mode='EDIT')
                except Exception:
                    pass

                self._area.header_text_set(
                    localize_text("Agora clique em um vértice da peça. Esc cancela.")
                )
                self._area.tag_redraw()
            else:
                self.target_vertex = self._hover[0]
                self._cleanup(restore_mode=False)
                res = self.execute(context)
                try:
                    if context.view_layer.objects.active != self._target_obj:
                        bpy.ops.object.select_all(action='DESELECT')
                        self._target_obj.select_set(True)
                        context.view_layer.objects.active = self._target_obj
                    if context.mode != 'EDIT' and bpy.ops.object.mode_set.poll():
                        bpy.ops.object.mode_set(mode='EDIT')
                except Exception:
                    pass
                return res

        return {"RUNNING_MODAL"}
