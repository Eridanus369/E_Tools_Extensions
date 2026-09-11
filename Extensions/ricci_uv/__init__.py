bl_info = {
    "name": "Ricci UV",
    "author": "Your Name",
    "version": (0, 3, 1),
    "blender": (4, 2, 0),
    "location": "View3D Header / UV Editor Header / F7",
    "description": "Ricci flow UV unwrapping with cone singularity detection",
    "category": "UV",
}

import bpy

# ---- 模块导入 ----
from . import preferences
from . import ui
from . import operators


def register():
    # 1. 偏好设置（必须最先注册）
    preferences.register()

    # 2. UI 层
    ui.register()

    # 3. 操作符
    operators.register()


def unregister():
    # 3. 操作符
    operators.unregister()

    # 2. UI 层
    ui.unregister()

    # 1. 偏好设置
    preferences.unregister()


if __name__ == "__main__":
    register()