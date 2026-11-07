"""Pacote principal do Chest Part Splitter."""

from . import translations
from . import properties
from . import operators
from . import ui
from . import gpu_drawing
from . import cache_fingerprint


def register():
    cache_fingerprint.register()
    translations.register_translations()
    properties.register()
    operators.register()
    ui.register()
    gpu_drawing.register_overlay()
    from . import history
    history.register()


def unregister():
    from . import history
    history.unregister()
    from . import connector_editor, connector_surface
    from .solid_tools import stop_solid_alignment
    stop_solid_alignment()
    connector_editor.stop_connector_editor()
    connector_surface.clear_prepared_split_cache()
    for scene in properties.bpy.data.scenes:
        if hasattr(scene, 'chest_splitter'):
            scene.chest_splitter.is_editing_connectors = False
    gpu_drawing.unregister_overlay()
    cache_fingerprint.unregister()
    ui.unregister()
    operators.unregister()
    properties.unregister()
    translations.unregister_translations()
