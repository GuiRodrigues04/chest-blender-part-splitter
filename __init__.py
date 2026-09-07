"""Chest Part Splitter — Extensão para Blender 5.2+."""

bl_info = {
    "name": "Chest Part Splitter",
    "author": "Chest Team",
    "version": (0, 3, 0),

    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > Chest > Part Splitter",
    "description": "Divisão de modelos em peças com encaixes e folga controlada para impressão 3D",
    "category": "3D View",
}

from . import src


def register():
    src.register()


def unregister():
    src.unregister()


if __name__ == "__main__":
    register()
