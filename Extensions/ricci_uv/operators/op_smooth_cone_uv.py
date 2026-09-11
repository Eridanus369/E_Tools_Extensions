# ============================================================
# 智能平滑优化锥奇异点 UV
# ============================================================
import bpy
import numpy as np
from bpy.props import IntProperty, FloatProperty
from .uv_utils import extract_mesh_data
from ..core.native_loader import get_native


class RICCI_OT_smooth_cone_uv(bpy.types.Operator):
    bl_idname = "ricci.smooth_cone_uv"
    bl_label = "平滑锥点UV"
    bl_description = "对锥奇异点邻域执行 UV 平滑，消除拉伸"
    bl_options = {'REGISTER', 'UNDO'}

    iterations: IntProperty(
        name="迭代次数", default=10, min=1, max=100)

    strength: FloatProperty(
        name="平滑强度", default=0.5, min=0.0, max=1.0,
        precision=3)

    threshold: FloatProperty(
        name="锥点检测阈值", default=0.05, min=0.001,
        precision=4)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and obj.data.uv_layers)

    def execute(self, context):
        obj = context.active_object
        native = get_native()

        verts, tris, seams, _, _ = extract_mesh_data(obj)

        # 获取当前 UV
        mesh = obj.data
        uv_layer = mesh.uv_layers.active
        n_loops = len(mesh.loops)
        uv_flat = np.empty(n_loops * 2, dtype=np.float64)
        uv_layer.data.foreach_get("uv", uv_flat)
        uv_flat = uv_flat.reshape(n_loops, 2)

        # 按顶点构建 UV（取第一个 loop 的 UV）
        n_verts = len(mesh.vertices)
        vert_uv = np.zeros((n_verts, 2), dtype=np.float64)
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                vi = mesh.loops[li].vertex_index
                vert_uv[vi] = uv_flat[li]

        # 获取锥点列表
        try:
            analysis = native.analyze(verts, tris, seams, {})
        except Exception as e:
            self.report({'ERROR'}, f"分析失败: {e}")
            return {'CANCELLED'}

        curv = np.array(analysis["curvature"])
        cone_indices = np.where(np.abs(curv) > self.threshold)[0]
        cone_list = cone_indices.astype(np.int32)

        if len(cone_list) == 0:
            self.report({'WARNING'}, "未检测到锥奇异点")
            return {'CANCELLED'}

        # 调用原生平滑
        try:
            new_uv = native.smooth_cone_uv(
                verts, tris, vert_uv, cone_list,
                self.iterations, self.strength)
        except Exception as e:
            self.report({'ERROR'}, f"平滑失败: {e}")
            return {'CANCELLED'}

        new_uv = np.array(new_uv)

        # 写回 UV
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                vi = mesh.loops[li].vertex_index
                if vi < new_uv.shape[0]:
                    uv_layer.data[li].uv = (
                        float(new_uv[vi, 0]),
                        float(new_uv[vi, 1]))

        mesh.update()

        self.report({'INFO'},
            f"锥点 UV 平滑完成: {len(cone_list)} 个锥点, "
            f"{self.iterations} 次迭代")

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "iterations")
        col.prop(self, "strength")
        col.separator()
        col.prop(self, "threshold")