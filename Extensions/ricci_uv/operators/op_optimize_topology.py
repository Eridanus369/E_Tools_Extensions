# ============================================================
# Ricci 智能优化拓扑网格
# QuadriFlow 风格的四边形化重网格
# ============================================================
import bpy
import bmesh
import numpy as np
from bpy.props import IntProperty, BoolProperty
from .uv_utils import extract_mesh_data
from ..core.native_loader import get_native


class RICCI_OT_optimize_topology(bpy.types.Operator):
    bl_idname = "ricci.optimize_topology"
    bl_label = "Ricci 优化拓扑"
    bl_description = "在不破坏造型和 UV 的前提下，将网格优化为四边面"
    bl_options = {'REGISTER', 'UNDO'}

    target_faces: IntProperty(
        name="目标面数",
        description="四边形网格的目标面数",
        default=5000, min=100, max=500000)

    preserve_sharp: BoolProperty(
        name="保持锐边",
        default=True)

    smooth_iters: IntProperty(
        name="场平滑迭代",
        default=10, min=1, max=50)

    seed: IntProperty(
        name="随机种子",
        default=0, min=0, max=65535)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        native = get_native()

        # 1. 提取网格
        verts, tris, seams, _, _ = extract_mesh_data(obj)

        # 2. 保存原始 UV（用于插值）
        mesh = obj.data
        orig_uv = None
        if mesh.uv_layers:
            uv_layer = mesh.uv_layers.active
            n_loops = len(mesh.loops)
            uv_flat = np.empty(n_loops * 2, dtype=np.float64)
            uv_layer.data.foreach_get("uv", uv_flat)
            uv_flat = uv_flat.reshape(n_loops, 2)

            n_verts = len(mesh.vertices)
            orig_uv = np.zeros((n_verts, 2), dtype=np.float64)
            for poly in mesh.polygons:
                for li in poly.loop_indices:
                    vi = mesh.loops[li].vertex_index
                    orig_uv[vi] = uv_flat[li]

        # 3. 调用原生四边形化
        options = {
            "target_faces": self.target_faces,
            "preserve_sharp": self.preserve_sharp,
            "smooth_iters": self.smooth_iters,
            "seed": self.seed,
        }

        try:
            result = native.quad_remesh(verts, tris, options)
        except Exception as e:
            self.report({'ERROR'}, f"四边形化失败: {e}")
            return {'CANCELLED'}

        new_verts = np.array(result["vertices"])
        new_quads = np.array(result["quads"])
        new_uv = np.array(result["uv"])

        if len(new_quads) == 0:
            self.report({'WARNING'}, "四边形化未产生有效面")
            return {'CANCELLED'}

        # 4. 构建新网格
        new_mesh = bpy.data.meshes.new(f"{obj.name}_quad")

        n_v = len(new_verts)
        n_q = len(new_quads) // 4

        # 顶点
        new_mesh.vertices.add(n_v)
        new_mesh.vertices.foreach_set(
            "co", new_verts.flatten().tolist())

        # 面
        new_mesh.loops.add(n_q * 4)
        new_mesh.polygons.add(n_q)
        new_mesh.polygons.foreach_set(
            "loop_start", [i * 4 for i in range(n_q)])
        new_mesh.polygons.foreach_set(
            "loop_total", [4] * n_q)
        new_mesh.loops.foreach_set(
            "vertex_index", new_quads.tolist())
        new_mesh.update(calc_edges=True)

        # 5. 写入 UV
        uv_layer = new_mesh.uv_layers.new(name="RicciUV")
        uv_flat_out = np.zeros((n_q * 4, 2), dtype=np.float64)
        for qi in range(n_q):
            for j in range(4):
                vi = new_quads[qi * 4 + j]
                uv_flat_out[qi * 4 + j] = new_uv[vi]
        uv_layer.data.foreach_set("uv", uv_flat_out.flatten().tolist())

        # 6. 替换对象网格
        old_mesh = obj.data
        obj.data = new_mesh
        obj.name = f"{obj.name}_quad"

        # 清理
        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)

        new_mesh.update()

        self.report({'INFO'},
            f"四边形化完成: {n_v} 顶点, {n_q} 四边面 "
            f"(原 {len(tris)} 三角面)")

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "target_faces")
        col.prop(self, "preserve_sharp")
        col.separator()
        col.prop(self, "smooth_iters")
        col.prop(self, "seed")