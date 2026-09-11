import bpy
from bpy.props import IntProperty, FloatProperty, BoolProperty
from .mesh_io import extract_mesh_data, apply_uv_to_object
from .native_loader import get_native


class RICCI_OT_unwrap(bpy.types.Operator):
    """Run Ricci flow UV unwrapping"""
    bl_idname = "ricci.unwrap"
    bl_label = "Ricci UV Unwrap"
    bl_options = {'REGISTER', 'UNDO'}

    max_cones: IntProperty(
        name="Max Cone Singularities",
        description="Upper limit on cone singularities",
        default=32, min=0, max=512)
    threshold: FloatProperty(
        name="Cone Threshold",
        description="Curvature magnitude threshold for cone detection (radians)",
        default=0.05, min=0.001, max=3.14159, precision=4)
    allow_boundary_cone: BoolProperty(
        name="Allow Boundary Cones",
        description="Allow boundary vertices to become cone singularities",
        default=False)
    max_iter: IntProperty(
        name="Max Iterations",
        description="Maximum Ricci flow iterations",
        default=5000, min=10, max=100000)
    tolerance: FloatProperty(
        name="Convergence Tolerance",
        description="Ricci flow convergence tolerance",
        default=1e-6, min=1e-10, max=1e-1, precision=10)

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None
                and context.active_object.type == 'MESH')

    def execute(self, context):
        obj = context.active_object
        native = get_native()

        # 1. 提取网格数据
        verts, tris, seams = extract_mesh_data(obj)
        self.report({'INFO'},
            f"Mesh: {verts.shape[0]} verts, {tris.shape[0]} tris, "
            f"{seams.shape[0]} seams")

        # 2. 构造原生输入
        mesh_input = native.MeshInput()
        mesh_input.vertices = verts
        mesh_input.triangles = tris
        mesh_input.seams = seams

        # 3. 构造选项
        options = {
            "max_cones": self.max_cones,
            "threshold": self.threshold,
            "allow_boundary_cone": self.allow_boundary_cone,
            "max_iter": self.max_iter,
            "tol": self.tolerance,
        }

        # 4. 调用原生模块
        try:
            result = native.unwrap(mesh_input, options)
        except Exception as e:
            self.report({'ERROR'}, f"Ricci unwrap failed: {e}")
            return {'CANCELLED'}

        # 5. 写回 UV
        apply_uv_to_object(obj, result.uv, verts.shape[0])

        # 6. 报告
        cone_count = int(result.is_cone.sum())
        self.report({'INFO'},
            f"Converged: {result.converged} | "
            f"Iter: {result.iterations} | "
            f"Error: {result.final_error:.2e} | "
            f"Cones: {cone_count}")

        return {'FINISHED'}


class RICCI_OT_analyze(bpy.types.Operator):
    """Quick curvature analysis without unwrapping"""
    bl_idname = "ricci.analyze"
    bl_label = "Ricci Analyze Curvature"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None
                and context.active_object.type == 'MESH')

    def execute(self, context):
        obj = context.active_object
        native = get_native()

        verts, tris, seams = extract_mesh_data(obj)
        mesh_input = native.MeshInput()
        mesh_input.vertices = verts
        mesh_input.triangles = tris
        mesh_input.seams = seams

        result = native.analyze(mesh_input, {})
        cur = result["curvature"]
        self.report({'INFO'},
            f"Curvature: min={cur.min():.4f} max={cur.max():.4f} "
            f"mean={cur.mean():.4f}")
        return {'FINISHED'}


# ---- 注册 ----
_classes = [RICCI_OT_unwrap, RICCI_OT_analyze]

def register():
    for cls in _classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)