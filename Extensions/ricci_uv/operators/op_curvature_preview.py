"""
曲率图叠加预览与输出
"""
import bpy
import os
import numpy as np
from bpy.props import EnumProperty, StringProperty
from .uv_utils import extract_mesh_data
from . import uv_overlay
from ..core.native_loader import get_native
from ..core.addon_utils import get_prefs


class RICCI_OT_curvature_preview(bpy.types.Operator):
    bl_idname = "ricci.curvature_preview"
    bl_label = "曲率预览"
    bl_description = "计算并预览 UV 展开后的曲率分布"
    bl_options = {'REGISTER'}

    display_mode: EnumProperty(
        name="显示模式",
        items=[
            ('GAUSSIAN', "高斯曲率", "显示高斯曲率分布"),
            ('TARGET',   "目标曲率", "显示目标曲率（锥点）"),
            ('HOLONOMY', "和乐",     "显示和乐角分布"),
        ],
        default='GAUSSIAN')

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None
                and context.active_object.type == 'MESH')

    def execute(self, context):
        obj = context.active_object
        native = get_native()

        verts, tris, seams, _, _ = extract_mesh_data(obj)

        try:
            result = native.analyze(verts, tris, seams, {})
        except Exception as e:
            self.report({'ERROR'}, f"分析失败: {e}")
            return {'CANCELLED'}

        if self.display_mode == 'GAUSSIAN':
            curv = result["curvature"]
        elif self.display_mode == 'HOLONOMY':
            curv = result["holonomy"]
        else:
            curv = result["curvature"]

        tri_data = uv_overlay.build_uv_curvature_data(obj, np.array(curv))
        uv_overlay.set_uv_curvature(tri_data)
        uv_overlay.register_uv_overlay()

        curv_np = np.array(curv)
        self.report({'INFO'},
            f"曲率: min={curv_np.min():.4f}, "
            f"max={curv_np.max():.4f}, "
            f"mean={curv_np.mean():.4f}")

        return {'FINISHED'}


class RICCI_OT_curvature_export(bpy.types.Operator):
    bl_idname = "ricci.curvature_export"
    bl_label = "导出曲率图"
    bl_description = "将曲率热力图导出为 PNG"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.png", options={'HIDDEN'})

    def execute(self, context):
        prefs = get_prefs(context)
        if prefs is None:
            self.report({'ERROR'}, "偏好设置未加载")
            return {'CANCELLED'}

        out_path = self.filepath or prefs.export_path

        if not out_path:
            self.report({'ERROR'}, "未设置导出路径")
            return {'CANCELLED'}

        os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

        self.report({'INFO'}, f"已导出到: {out_path}")
        return {'FINISHED'}

    def invoke(self, context, event):
        prefs = get_prefs(context)
        if prefs is not None:
            self.filepath = prefs.export_path
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}