"""Pacote principal do Chest Part Splitter."""

from . import translations
from . import properties
from . import operators
from . import ui
from . import gpu_drawing


def register():
    translations.register_translations()
    properties.register()
    operators.register()
    ui.register()
    gpu_drawing.register_overlay()


def unregister():
    from . import connector_editor, connector_surface
    connector_editor.stop_connector_editor()
    connector_surface.clear_prepared_split_cache()
    for scene in properties.bpy.data.scenes:
        if hasattr(scene, 'chest_splitter'):
            scene.chest_splitter.is_editing_connectors = False
    gpu_drawing.unregister_overlay()
    ui.unregister()
    operators.unregister()
    properties.unregister()
    translations.unregister_translations()
