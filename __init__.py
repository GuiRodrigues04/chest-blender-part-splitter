"""Splitter Addon."""

bl_info = {
    "name": "Splitter",
    "author": "Splitter Team",
    "version": (0, 9, 10),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > Splitter",
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
