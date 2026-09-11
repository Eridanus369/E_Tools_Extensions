# ============================================================
# Ricci 智能 UV 展开
# 支持多选物体、区域约束求解
# ============================================================
import bpy
import numpy as np
from bpy.props import IntProperty, FloatProperty, BoolProperty
from .uv_utils import extract_mesh_data, apply_uv_to_object, get_uv_selected_verts
from ..core.native_loader import get_native


class RICCI_OT_unwrap(bpy.types.Operator):
    bl_idname = "ricci.unwrap"
    bl_label = "Ricci 智能展开"
    bl_description = "使用 Ricci 流进行 UV 展开（支持多选物体）"
    bl_options = {'REGISTER', 'UNDO'}

    max_cones: IntProperty(
        name="锥点上限",
        description="锥奇异点最大数量",
        default=32, min=0, max=512)

    threshold: FloatProperty(
        name="锥点阈值",
        description="曲率检测阈值（弧度）",
        default=0.05, min=0.001, max=3.14159,
        precision=4, step=0.01)

    allow_boundary_cone: BoolProperty(
        name="允许边界锥点",
        default=False)

    max_iter: IntProperty(
        name="最大迭代",
        default=5000, min=10, max=100000)

    tolerance: FloatProperty(
        name="收敛容差",
        default=1e-6, min=1e-10, max=1e-1,
        precision=10)

    use_region: BoolProperty(
        name="仅展开选中区域",
        description="仅对 UV 编辑器中选中的区域执行展开",
        default=False)

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        native = get_native()
        targets = [o for o in context.selected_objects if o.type == 'MESH']

        if not targets:
            self.report({'WARNING'}, "没有选中网格物体")
            return {'CANCELLED'}

        total_cones = 0

        for obj in targets:
            # 1. 提取网格
            verts, tris, seams, orig_idx, face_map = extract_mesh_data(obj)

            # 2. 区域约束
            region_verts = np.array([], dtype=np.int32)
            if self.use_region:
                region_verts = get_uv_selected_verts(obj)
                if len(region_verts) == 0:
                    self.report({'WARNING'},
                        f"{obj.name}: 未选中 UV 区域，跳过")
                    continue

            # 3. 构建选项
            options = {
                "max_cones": self.max_cones,
                "threshold": self.threshold,
                "allow_boundary_cone": self.allow_boundary_cone,
                "max_iter": self.max_iter,
                "tol": self.tolerance,
            }

            # 4. 调用原生模块
            try:
                result = native.unwrap(
                    verts, tris, seams, region_verts, options)
            except Exception as e:
                self.report({'ERROR'}, f"{obj.name}: Ricci 展开失败 — {e}")
                continue

            # 5. 写回 UV（处理 seam 切割新顶点）
            apply_uv_to_object(
                obj,
                result["uv"],
                result["orig_vertex_index"],
                face_map
            )

            n_cones = result["num_cones"]
            total_cones += n_cones

            self.report({'INFO'},
                f"{obj.name}: {result['iterations']} iter, "
                f"err={result['final_error']:.2e}, "
                f"{n_cones} cones, "
                f"{'收敛' if result['converged'] else '未收敛'}")

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "max_cones")
        col.prop(self, "threshold")
        col.prop(self, "allow_boundary_cone")
        col.separator()
        col.prop(self, "max_iter")
        col.prop(self, "tolerance")
        col.separator()
        col.prop(self, "use_region")