"""Layout recording checks for collapsed UI and expanded result ordering."""
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src
src.register()
from src.ui import draw_disclosure, VIEW3D_PT_chest_part_splitter


class Node:
    def __init__(self, kind, **kwargs):
        self.kind = kind
        self.kwargs = kwargs
        self.children = []


class RecordingLayout:
    def __init__(self, node=None, calls=None):
        self.node = node or Node("root")
        self.calls = calls if calls is not None else []
        self.alert = False

    def _child_layout(self, kind, **kwargs):
        self.calls.append((kind, kwargs))
        child = Node(kind, **kwargs)
        self.node.children.append(child)
        return RecordingLayout(child, self.calls)

    def row(self, **kwargs):
        return self._child_layout("row", **kwargs)

    def column(self, **kwargs):
        return self._child_layout("column", **kwargs)

    def box(self, **kwargs):
        return self._child_layout("box", **kwargs)

    def split(self, **kwargs):
        return self._child_layout("split", **kwargs)

    def grid_flow(self, **kwargs):
        return self._child_layout("grid_flow", **kwargs)

    def prop(self, settings, property_name, **kwargs):
        self.calls.append(("prop", property_name, kwargs))
        self.node.children.append(Node("prop", property_name=property_name, **kwargs))

    def label(self, **kwargs):
        self.node.children.append(Node("label", **kwargs))

    def operator(self, name, **kwargs):
        self.node.children.append(Node("operator", name=name, alert=self.alert, **kwargs))
        return SimpleNamespace()

    def separator(self, **kwargs):
        self.node.children.append(Node("separator", **kwargs))

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.node.children.append(Node(name, args=args, **kwargs))
            return self
        return record


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


class Settings:
    expanded = False


class TestUIDisclosures(bpy.types.Operator):
    bl_idname = "test.ui_disclosures"
    bl_label = "UI disclosure layout checks"

    def execute(self, context):
        layout = RecordingLayout()
        content = draw_disclosure(layout, Settings, "expanded", "Show data")
        assert content is None
        assert [call[0] for call in layout.calls] == ["row", "prop"]

        Settings.expanded = True
        layout = RecordingLayout()
        content = draw_disclosure(layout, Settings, "expanded", "Show data")
        assert content is not None and content.node.kind == "column"
        assert [call[0] for call in layout.calls] == ["row", "prop", "column"]

        self.assert_collapsed_panel_warning(context)
        self.assert_expanded_panel_result_order(context)
        self.assert_target_and_clearance(context)
        self.assert_loop_guidance(context)
        print("UI disclosure, visible volume warning, and panel ordering checks passed")
        return {'FINISHED'}

    def make_result_panel(self, context, expanded):
        bpy.ops.mesh.primitive_cube_add(size=0.04)
        settings = context.scene.chest_splitter
        settings.target_object = context.object
        settings.session_status = 'COMMITTED'
        settings.show_result_data = expanded
        settings.volume_diff_pct = 0.8
        root = RecordingLayout()
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=root), context)

        results = next(node for node in walk(root.node)
                       if node.kind == "box" and any(
                           child.kind == "label" and child.kwargs.get("text") in ("Resultados do Corte", "Cut Results")
                           for child in node.children))
        return results

    def assert_collapsed_panel_warning(self, context):
        results = self.make_result_panel(context, expanded=False)
        direct_labels = [child.kwargs.get("text", "") for child in results.children if child.kind == "label"]
        assert any(("Aviso: diferença de volume 0.80%" in label or
                    "Warning: volume difference 0.80%" in label) for label in direct_labels)
        assert not any(label.startswith(("Soma Volumes", "Total Volume")) for label in direct_labels)
        assert not any("Mesh:" in label or "Malha:" in label for label in direct_labels)

    def assert_expanded_panel_result_order(self, context):
        results = self.make_result_panel(context, expanded=True)
        part_card_indices = [i for i, child in enumerate(results.children)
                             if child.kind == "box" and any(
                                 grandchild.kind == "label" and grandchild.kwargs.get("text", "").startswith(("Parte A", "Parte B", "Part A", "Part B"))
                                 for grandchild in child.children)]
        sum_card = next(i for i, child in enumerate(results.children)
                        if child.kind == "box" and any(
                            grandchild.kind == "label" and grandchild.kwargs.get("text", "").startswith(("Soma Volumes", "Total Volume"))
                            for grandchild in child.children))
        assert len(part_card_indices) == 2
        assert max(part_card_indices) < sum_card

    def assert_target_and_clearance(self, context):
        settings = context.scene.chest_splitter
        settings.split_mode = 'LOOP'
        settings.loop_behavior = 'DETACH'
        settings.connector_enabled = True
        settings.show_mesh_diagnostics = False
        settings.clearance_use_general = True
        root = RecordingLayout()
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=root), context)
        props = [n.kwargs.get('property_name') for n in walk(root.node) if n.kind == 'prop']
        assert 'show_mesh_diagnostics' in props and 'show_target_data' not in props
        assert 'part_clearance_mm' in props and 'clearance_use_general' in props
        assert 'part_clearance_bottom_enable' not in props
        assert 'clearance_per_side_mm' not in props and 'end_clearance_mm' not in props
        settings.clearance_use_general = False
        settings.show_mesh_diagnostics = True
        root = RecordingLayout()
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=root), context)
        props = [n.kwargs.get('property_name') for n in walk(root.node) if n.kind == 'prop']
        assert 'part_clearance_bottom_enable' in props
        assert 'clearance_per_side_mm' in props and 'end_clearance_mm' in props
        assert any(n.kind == 'label' and n.kwargs.get('text', '').startswith(('Dimensões:', 'Dimensions:')) for n in walk(root.node))

    def assert_loop_guidance(self, context):
        settings = context.scene.chest_splitter
        settings.split_mode = 'LOOP'
        settings.loop_behavior = 'AUTO'
        settings.loop_is_captured = False
        root = RecordingLayout()
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=root), context)
        assert not any(n.kind == 'operator' and n.kwargs.get('name') == 'chest.splitter_define_seed_face' for n in walk(root.node))
        settings.loop_is_captured = True
        settings.loop_seed_face_index = -1
        settings.loop_auto_reason = ''
        root = RecordingLayout()
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=root), context)
        nodes = list(walk(root.node))
        seed = next(n for n in nodes if n.kind == 'operator' and n.kwargs.get('name') == 'chest.splitter_define_seed_face')
        assert seed.kwargs['alert']
        assert not any(n.kind == 'label' and n.kwargs.get('text', '').startswith(('Auto Detectado:', 'Auto Detected:')) for n in nodes)
        settings.loop_seed_face_index = 0
        root = RecordingLayout()
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=root), context)
        seed = next(n for n in walk(root.node) if n.kind == 'operator' and n.kwargs.get('name') == 'chest.splitter_define_seed_face')
        assert not seed.kwargs['alert']


bpy.utils.register_class(TestUIDisclosures)
bpy.ops.test.ui_disclosures()
bpy.utils.unregister_class(TestUIDisclosures)
