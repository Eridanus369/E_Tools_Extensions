"""
插件偏好设置
"""
import bpy
from ._constants import ADDON_ID


class RICCI_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    # ---- 原生模块路径（新增） ----
    native_module_path: bpy.props.StringProperty(
        name="原生模块路径",
        description="ricci_core 编译输出目录（包含 .pyd/.so 文件）。\n"
                    "留空则自动搜索扩展目录和 lib/ 子目录。\n"
                    "例如：D:/dev/ricci_uv/native/build/Release",
        subtype='DIR_PATH',
        default="")

    # ---- 默认导出路径 ----
    export_path: bpy.props.StringProperty(
        name="默认导出路径",
        description="曲率图 PNG 的默认输出目录",
        subtype='DIR_PATH',
        default="//ricci_output/")

    # ---- 默认参数 ----
    default_max_cones: bpy.props.IntProperty(
        name="默认锥点上限",
        default=32, min=0, max=512)

    default_threshold: bpy.props.FloatProperty(
        name="默认锥点阈值",
        default=0.05, min=0.001, max=3.14159,
        precision=4)

    # ---- 颜色 ----
    cone_color: bpy.props.FloatVectorProperty(
        name="锥奇异点颜色",
        subtype='COLOR_GAMMA',
        size=4, min=0.0, max=1.0,
        default=(1.0, 0.0, 0.0, 0.8))

    field_color: bpy.props.FloatVectorProperty(
        name="方向场箭头颜色",
        subtype='COLOR_GAMMA',
        size=4, min=0.0, max=1.0,
        default=(0.2, 0.6, 1.0, 0.9))

    singular_color: bpy.props.FloatVectorProperty(
        name="奇异点高亮颜色",
        subtype='COLOR_GAMMA',
        size=4, min=0.0, max=1.0,
        default=(0.0, 0.4, 1.0, 1.0))

    overlay_opacity: bpy.props.FloatProperty(
        name="叠加不透明度",
        default=0.7, min=0.0, max=1.0,
        subtype='FACTOR')

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # ---- 原生模块 ----
        box = layout.box()
        col = box.column(align=True)
        col.label(text="原生模块", icon='PLUGIN')

        # 加载状态
        try:
            from .core.native_loader import get_loaded_path
            loaded = get_loaded_path()
        except Exception:
            loaded = None

        if loaded:
            col.label(text=f"已加载: {loaded.name}", icon='CHECKMARK')
            col.label(text=str(loaded.parent), icon='FILE_FOLDER')
        else:
            col.label(text="未加载（首次使用时自动搜索）", icon='INFO')

        col.separator(factor=0.5)
        col.prop(self, "native_module_path", text="")
        row = col.row(align=True)
        row.operator("ricci.reload_native",
                     text="重新加载原生模块", icon='FILE_REFRESH')

        # ---- 路径 ----
        col = layout.column(align=True)
        col.label(text="输出路径", icon='FILE_FOLDER')
        col.prop(self, "export_path")

        # ---- 默认参数 ----
        col = layout.column(align=True)
        col.label(text="默认参数", icon='PREFERENCES')
        col.prop(self, "default_max_cones")
        col.prop(self, "default_threshold")

        # ---- 颜色 ----
        col = layout.column(align=True)
        col.label(text="叠加绘制颜色", icon='COLOR')
        col.prop(self, "cone_color")
        col.prop(self, "field_color")
        col.prop(self, "singular_color")
        col.prop(self, "overlay_opacity")


class RICCI_OT_reload_native(bpy.types.Operator):
    """重新加载原生模块（修改 native_module_path 后使用）"""
    bl_idname = "ricci.reload_native"
    bl_label = "重新加载原生模块"
    bl_description = "强制重新加载 ricci_core 模块，用于开发调试"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            from .core.native_loader import reload_native
            module = reload_native()
            if module is None:
                self.report({'ERROR'}, "加载失败，请检查路径")
                return {'CANCELLED'}
            path = getattr(module, '__file__', '?')
            self.report({'INFO'}, f"已加载: {path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"加载失败: {e}")
            return {'CANCELLED'}


_classes = [RICCI_AddonPreferences, RICCI_OT_reload_native]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)