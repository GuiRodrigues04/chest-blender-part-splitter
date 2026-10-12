"""Chest Part Splitter Addon."""

bl_info = {
    "name": "Part Splitter 0.8.8",
    "author": "Chest Team",
    "version": (0, 8, 8),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > Chest > Part Splitter 0.8.8",
    "description": "Splits models into parts for 3D printing",
    "category": "3D View",
}

from . import src

def register():
    src.register()

def unregister():
    src.unregister()

if __name__ == "__main__":
    register()