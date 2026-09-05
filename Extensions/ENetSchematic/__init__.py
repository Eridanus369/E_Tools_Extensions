# __init__.py
bl_info = {
    "name": "ENetSchematic",
    "author": "Eridanus",
    "version": (1, 0, 0),
    "blender": (5, 2, 0),
    "description": "",
    "category": "Add Mesh",
}

from . import ENetSchematic

def register():
    ENetSchematic.register()

def unregister():
    ENetSchematic.unregister()
