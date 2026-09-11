"""
3D 视图 / UV 编辑器标题栏 Popover 面板

关键修复：
1. bl_options = {'INSTANCED'} 使面板可以作为 popover 弹出
2. VIEW_3D 和 IMAGE_EDITOR 各注册一个 Panel 类（bl_space_type 不同）
3. 偏好设置通过 addon_utils.get_prefs 获取，兼容扩展
"""
import bpy
from ..core.addon_utils import get_prefs


# ============================================================
# 共用 draw 逻辑
# ============================================================
def _draw_main_content(layout, context):
    """两个 Popover 共用的内容绘制"""
    layout.use_property_split = True
    layout.use_property_decorate = False

    prefs = get_prefs(context)
    if prefs is None:
        layout.label(text="偏好设置未加载，请重新启用扩展", icon='ERROR')
        return

    # ---- 展开 ----
    box = layout.box()
    col = box.column(align=True)
    col.label(text="展开", icon='UV_SYNC_SELECT')
    col.separator(factor=0.5)
    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator("ricci.unwrap", text="智能展开", icon='MOD_MESHDEFORM')
    col.prop(prefs, "default_max_cones", text="锥点上限")
    col.prop(prefs, "default_threshold", text="阈值")

    # ---- 曲率预览 ----
    box = layout.box()
    col = box.column(align=True)
    col.label(text="曲率预览", icon='IMAGE_ZDEPTH')
    col.separator(factor=0.5)
    row = col.row(align=True)
    row.operator("ricci.curvature_preview", text="预览")
    row.operator("ricci.curvature_export", text="", icon='EXPORT')

    # ---- 高级操作 ----
    box = layout.box()
    col = box.column(align=True)
    col.label(text="高级", icon='TOOL_SETTINGS')
    col.separator(factor=0.5)
    col.operator("ricci.decay_holonomy", icon='FORCE_MAGNETIC')
    col.operator("ricci.optimize_topology", icon='MESH_GRID')
    col.separator(factor=0.5)
    row = col.row(align=True)
    row.operator("ricci.cone_overlay", text="显示锥点", icon='PARTICLE_POINT')
    row.operator("ricci.cone_overlay_clear", text="", icon='X')
    col.operator("ricci.smooth_cone_uv", icon='SMOOTHCURVE')

    # ---- 底部路径 ----
    layout.separator(factor=0.5)
    layout.prop(prefs, "export_path", text="")


# ============================================================
# 3D 视图 Popover
# ============================================================
class RICCI_PT_popover_3d(bpy.types.Panel):
    bl_label = "Ricci UV"
    bl_idname = "RICCI_PT_popover_3d"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_options = {'INSTANCED'}
    bl_ui_units_x = 18

    def draw(self, context):
        _draw_main_content(self.layout, context)


# ============================================================
# UV 编辑器 Popover
# ============================================================
class RICCI_PT_popover_uv(bpy.types.Panel):
    bl_label = "Ricci UV"
    bl_idname = "RICCI_PT_popover_uv"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'
    bl_options = {'INSTANCED'}
    bl_ui_units_x = 18

    def draw(self, context):
        _draw_main_content(self.layout, context)


# ============================================================
# 标题栏按钮
# ============================================================
def draw_header_button_3d(self, context):
    self.layout.popover(
        panel="RICCI_PT_popover_3d",
        text="Ricci",
        icon='NODE_MATERIAL')


def draw_header_button_uv(self, context):
    self.layout.popover(
        panel="RICCI_PT_popover_uv",
        text="Ricci",
        icon='NODE_MATERIAL')


_classes = [RICCI_PT_popover_3d, RICCI_PT_popover_uv]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_HT_header.append(draw_header_button_3d)
    bpy.types.IMAGE_HT_header.append(draw_header_button_uv)


def unregister():
    bpy.types.VIEW3D_HT_header.remove(draw_header_button_3d)
    bpy.types.IMAGE_HT_header.remove(draw_header_button_uv)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)