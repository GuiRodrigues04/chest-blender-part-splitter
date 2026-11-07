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
    gpu_drawing.unregister_overlay()
    ui.unregister()
    operators.unregister()
    properties.unregister()
    translations.unregister_translations()
