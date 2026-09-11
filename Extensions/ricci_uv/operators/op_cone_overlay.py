# ============================================================
# 锥奇异点智能叠加判定
# ============================================================
import bpy
import numpy as np
from .uv_utils import extract_mesh_data
from . import uv_overlay
from ..core.native_loader import get_native


class RICCI_OT_cone_overlay(bpy.types.Operator):
    bl_idname = "ricci.cone_overlay"
    bl_label = "显示锥奇异点"
    bl_description = "在 3D 视图和 UV 视图中高亮显示锥奇异点"
    bl_options = {'REGISTER'}

    threshold: bpy.props.FloatProperty(
        name="检测阈值",
        default=0.05, min=0.001, max=3.14159,
        precision=4)

    show_in_3d: bpy.props.BoolProperty(
        name="3D 视图显示", default=True)

    show_in_uv: bpy.props.BoolProperty(
        name="UV 视图显示", default=True)

    _is_active = False
    _draw_handles = []

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        native = get_native()

        verts, tris, seams, _, _ = extract_mesh_data(obj)

        try:
            result = native.analyze(verts, tris, seams, {})
        except Exception as e:
            self.report({'ERROR'}, f"分析失败: {e}")
            return {'CANCELLED'}

        curv = np.array(result["curvature"])
        holonomy = np.array(result["holonomy"])

        # 锥点判定：|K| > threshold 的顶点
        cone_indices = np.where(np.abs(curv) > self.threshold)[0].tolist()
        # 也包含和乐异常点
        holo_indices = np.where(np.abs(holonomy) > self.threshold)[0].tolist()
        all_cones = sorted(set(cone_indices + holo_indices))

        uv_overlay.set_cone_points(all_cones)

        if self.show_in_3d:
            uv_overlay.register_3d_overlay()
        if self.show_in_uv:
            uv_overlay.register_uv_overlay()

        self.report({'INFO'},
            f"检测到 {len(all_cones)} 个锥奇异点 "
            f"(曲率: {len(cone_indices)}, 和乐: {len(holo_indices)})")

        return {'FINISHED'}


class RICCI_OT_cone_overlay_clear(bpy.types.Operator):
    bl_idname = "ricci.cone_overlay_clear"
    bl_label = "清除锥点叠加"
    bl_options = {'REGISTER'}

    def execute(self, context):
        uv_overlay.clear_all()
        uv_overlay.unregister_all_overlays()
        self.report({'INFO'}, "已清除锥点叠加")
        return {'FINISHED'}