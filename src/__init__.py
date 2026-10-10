"""Pacote principal do Chest Part Splitter."""

from . import translations
from . import properties
from . import operators
from . import ui


def register():
    translations.register_translations()
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()
    translations.unregister_translations()
