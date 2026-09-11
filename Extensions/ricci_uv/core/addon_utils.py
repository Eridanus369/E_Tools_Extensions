"""
插件 / 扩展工具函数
"""
import bpy


def get_prefs(context=None):
    """
    获取插件偏好设置（兼容旧式插件与 4.2+ 扩展）

    返回 RICCI_AddonPreferences 实例，失败返回 None。
    """
    from .._constants import ADDON_ID

    if context is None:
        context = bpy.context

    addons = context.preferences.addons

    # 1. 精确匹配
    entry = addons.get(ADDON_ID)
    if entry is not None:
        return entry.preferences

    # 2. 兜底：模糊匹配（应对不同的安装方式）
    for key in addons.keys():
        if key == "ricci_uv" or key.endswith(".ricci_uv"):
            return addons[key].preferences

    return None


def get_prefs_required(context=None):
    """
    同 get_prefs，但若失败会抛出异常。
    用于操作符内部，避免静默 None。
    """
    prefs = get_prefs(context)
    if prefs is None:
        raise RuntimeError(
            "Ricci UV 偏好设置未加载。\n"
            "请确认扩展已启用，然后重新打开 Blender。"
        )
    return prefs