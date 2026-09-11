"""
F7 饼菜单
"""
import bpy


class RICCI_MT_pie_menu(bpy.types.Menu):
    bl_label = "Ricci UV"
    bl_idname = "RICCI_MT_pie_menu"

    def draw(self, context):
        pie = self.layout.menu_pie()

        pie.operator("ricci.unwrap",
                     text="智能展开", icon='UV_SYNC_SELECT')
        pie.operator("ricci.curvature_preview",
                     text="曲率预览", icon='IMAGE_ZDEPTH')
        pie.operator("ricci.decay_holonomy",
                     text="衰减合乐", icon='FORCE_MAGNETIC')
        pie.operator("ricci.optimize_topology",
                     text="优化拓扑", icon='MESH_GRID')
        pie.operator("ricci.cone_overlay",
                     text="锥奇异点", icon='PARTICLE_POINT')
        pie.operator("ricci.smooth_cone_uv",
                     text="平滑锥点UV", icon='SMOOTHCURVE')
        pie.operator("ricci.cone_overlay_clear",
                     text="清除叠加", icon='X')
        pie.separator()


# ---- 快捷键 ----
_addon_keymaps = []


def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return

    km = kc.keymaps.new(name="3D View", space_type='VIEW_3D')
    kmi = km.keymap_items.new("wm.call_menu_pie", 'F7', 'PRESS')
    kmi.properties.name = "RICCI_MT_pie_menu"
    _addon_keymaps.append((km, kmi))

    km_uv = kc.keymaps.new(name="Image Generic", space_type='IMAGE_EDITOR')
    kmi_uv = km_uv.keymap_items.new("wm.call_menu_pie", 'F7', 'PRESS')
    kmi_uv.properties.name = "RICCI_MT_pie_menu"
    _addon_keymaps.append((km_uv, kmi_uv))


def unregister_keymaps():
    for km, kmi in _addon_keymaps:
        km.keymap_items.remove(kmi)
    _addon_keymaps.clear()


_classes = [RICCI_MT_pie_menu]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    register_keymaps()


def unregister():
    unregister_keymaps()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)