# ============================================================
# 智能衰减合乐
# 模态操作：方向场叠加 + 区域迭代求解 + Esc 退出
# ============================================================
import bpy
import numpy as np
from .uv_utils import extract_mesh_data, apply_uv_to_object, get_uv_selected_verts
from . import uv_overlay
from ..core.native_loader import get_native


class RICCI_OT_decay_holonomy(bpy.types.Operator):
    bl_idname = "ricci.decay_holonomy"
    bl_label = "衰减合乐"
    bl_description = "曲率自适应 UV 密度衰减，生成方向场连续的全局共形 UV"
    bl_options = {'REGISTER', 'UNDO'}

    decay_rate: bpy.props.FloatProperty(
        name="衰减率",
        description="曲率自适应 UV 密度衰减强度",
        default=0.5, min=0.0, max=10.0)

    max_iter: bpy.props.IntProperty(
        name="最大迭代", default=3000, min=10)

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "请选中网格物体")
            return {'CANCELLED'}

        self._obj = obj
        self._overlay_active = False

        # 首次执行：全局求解 + 显示叠加
        self._solve_and_overlay(context)

        # 注册模态
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _solve_and_overlay(self, context):
        """执行求解并更新叠加绘制"""
        native = get_native()
        obj = self._obj

        verts, tris, seams, orig_idx, face_map = extract_mesh_data(obj)

        # 区域约束：若 UV 编辑器中有选中，则仅求解选中区域
        region_verts = get_uv_selected_verts(obj)

        options = {
            "max_cones": 64,
            "threshold": 0.01,
            "decay_rate": self.decay_rate,
            "max_iter": self.max_iter,
        }

        try:
            result = native.unwrap(
                verts, tris, seams, region_verts, options)
        except Exception as e:
            self.report({'ERROR'}, f"衰减合乐失败: {e}")
            return

        # 写回 UV
        apply_uv_to_object(
            obj, result["uv"],
            result["orig_vertex_index"], face_map)

        # 构建方向场箭头
        face_dirs = np.array(result["face_directions"])
        arrows_uv, arrows_3d = uv_overlay.build_field_arrows(obj, face_dirs)
        uv_overlay.set_field_arrows_uv(arrows_uv)
        uv_overlay.set_field_arrows_3d(arrows_3d)

        # 锥点/奇异点高亮（蓝色）
        is_cone = np.array(result["is_cone"])
        cone_verts = np.where(is_cone > 0)[0].tolist()
        uv_overlay.set_cone_points(cone_verts)

        # 注册叠加
        if not self._overlay_active:
            uv_overlay.register_3d_overlay()
            uv_overlay.register_uv_overlay()
            self._overlay_active = True
        else:
            uv_overlay._tag_redraw_all()

        self.report({'INFO'},
            f"衰减合乐: {result['iterations']} iter, "
            f"{result['num_cones']} 奇异点")

    def modal(self, context, event):
        if event.type == 'ESC':
            # 退出：清除叠加
            uv_overlay.clear_all()
            uv_overlay.unregister_all_overlays()
            self._overlay_active = False
            self.report({'INFO'}, "衰减合乐已退出")
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # 框选区域 → 迭代求解
            self._solve_and_overlay(context)
            return {'RUNNING_MODAL'}

        if event.type == 'MOUSEMOVE':
            return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    def cancel(self, context):
        uv_overlay.clear_all()
        uv_overlay.unregister_all_overlays()
        self._overlay_active = False