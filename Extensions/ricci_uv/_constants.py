"""
常量定义 — 独立文件，避免循环导入

ADDON_ID 在 Blender 中的实际值：
  - 旧式插件安装:            'ricci_uv'
  - Blender 4.2+ 扩展安装:   'bl_ext.<repo>.<id>'，如 'bl_ext.user_default.ricci_uv'

通过 __package__ 自动获取当前真实包名，无需硬编码。
"""

# __package__ 在 ricci_uv/_constants.py 中的值就是顶层包名
ADDON_ID = __package__ if __package__ else "ricci_uv"