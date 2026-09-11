"""
GPU 叠加绘制模块 — 修复 UV 编辑器坐标变换 + 偏好设置获取
"""
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
from ..core.addon_utils import get_prefs


_draw_handles = []
_overlay_data = {}


# ============================================================
# UV 编辑器坐标变换
# ============================================================
def _get_uv_screen_matrix(context):
    """
    获取 UV → 屏幕的变换矩阵。
    SpaceImageEditor.uv_editor 提供 zoom 等信息。
    """
    space = context.space_data
    region = context.region

    if not space or space.type != 'IMAGE_EDITOR':
        return None

    w, h = region.width, region.height

    # 读取缩放
    zoom = (1.0, 1.0)
    try:
        uv_ed = space.uv_editor
        if hasattr(uv_ed, 'zoom'):
            z = uv_ed.zoom
            if z[0] > 0 and z[1] > 0:
                zoom = (z[0], z[1])
    except Exception:
        pass

    zoom_x, zoom_y = zoom

    mat = Matrix.Identity(3)
    mat[0][0] = w * zoom_x
    mat[1][1] = h * zoom_y

    # 中心偏移
    offset_x = (w - w * zoom_x) * 0.5
    offset_y = (h - h * zoom_y) * 0.5
    mat[0][2] = offset_x
    mat[1][2] = offset_y

    return mat


def uv_to_screen(uv, mat):
    v = mat @ Vector((uv[0], uv[1], 1.0))
    return (v.x, v.y)


# ============================================================
# 3D 视图：锥奇异点标记
# ============================================================
def draw_cones_3d():
    if not _overlay_data.get('cone_points'):
        return

    context = bpy.context
    if not context.space_data or context.space_data.type != 'VIEW_3D':
        return

    prefs = get_prefs(context)
    if prefs is None:
        return

    color = prefs.cone_color
    opacity = prefs.overlay_opacity

    obj = context.active_object
    if not obj or not obj.data:
        return

    mw = obj.matrix_world
    positions = []
    for vi in _overlay_data['cone_points']:
        if vi < len(obj.data.vertices):
            co = mw @ obj.data.vertices[vi].co
            positions.append(tuple(co))

    if not positions:
        return

    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    shader.bind()
    shader.uniform_float("color", (color[0], color[1], color[2], opacity))

    gpu.state.point_size_set(12.0)
    gpu.state.blend_set('ALPHA')

    batch = batch_for_shader(shader, 'POINTS', {"pos": positions})
    batch.draw(shader)

    gpu.state.point_size_set(1.0)
    gpu.state.blend_set('NONE')


# ============================================================
# UV 视图：曲率热力图
# ============================================================
def draw_curvature_uv():
    if not _overlay_data.get('uv_curvature'):
        return

    context = bpy.context
    if context.space_data.type != 'IMAGE_EDITOR':
        return
    if not context.space_data.show_uvedit:
        return

    mat = _get_uv_screen_matrix(context)
    if mat is None:
        return

    uv_data = _overlay_data['uv_curvature']
    if not uv_data:
        return

    verts, colors = [], []
    for (uv0, uv1, uv2, col) in uv_data:
        verts.extend([
            uv_to_screen(uv0, mat),
            uv_to_screen(uv1, mat),
            uv_to_screen(uv2, mat),
        ])
        colors.extend([col, col, col])

    if not verts:
        return

    shader = gpu.shader.from_builtin('2D_FLAT_COLOR')
    shader.bind()
    gpu.state.blend_set('ALPHA')

    batch = batch_for_shader(
        shader, 'TRIS', {"pos": verts, "color": colors})
    batch.draw(shader)

    gpu.state.blend_set('NONE')


# ============================================================
# UV 视图：方向场箭头
# ============================================================
def draw_field_arrows_uv():
    if not _overlay_data.get('field_arrows'):
        return

    context = bpy.context
    if context.space_data.type != 'IMAGE_EDITOR':
        return

    prefs = get_prefs(context)
    if prefs is None:
        return
    color = prefs.field_color

    mat = _get_uv_screen_matrix(context)
    if mat is None:
        return

    arrows = _overlay_data['field_arrows']
    lines = []
    for (s, e) in arrows:
        lines.append(uv_to_screen(s, mat))
        lines.append(uv_to_screen(e, mat))

    if not lines:
        return

    shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
    shader.bind()
    shader.uniform_float("color", (color[0], color[1], color[2], color[3]))

    gpu.state.line_width_set(2.0)
    gpu.state.blend_set('ALPHA')

    batch = batch_for_shader(shader, 'LINES', {"pos": lines})
    batch.draw(shader)

    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


# ============================================================
# 3D 视图：方向场箭头
# ============================================================
def draw_field_arrows_3d():
    if not _overlay_data.get('field_arrows_3d'):
        return

    context = bpy.context
    if context.space_data.type != 'VIEW_3D':
        return

    prefs = get_prefs(context)
    if prefs is None:
        return
    color = prefs.field_color

    arrows = _overlay_data['field_arrows_3d']
    lines = []
    for (s, e) in arrows:
        lines.append(tuple(s))
        lines.append(tuple(e))

    if not lines:
        return

    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    shader.bind()
    shader.uniform_float("color", (color[0], color[1], color[2], color[3]))

    gpu.state.line_width_set(2.0)
    gpu.state.blend_set('ALPHA')

    batch = batch_for_shader(shader, 'LINES', {"pos": lines})
    batch.draw(shader)

    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


# ============================================================
# 句柄管理
# ============================================================
def register_3d_overlay():
    unregister_3d_overlay()
    h1 = bpy.types.SpaceView3D.draw_handler_add(
        draw_cones_3d, (), 'WINDOW', 'POST_VIEW')
    h2 = bpy.types.SpaceView3D.draw_handler_add(
        draw_field_arrows_3d, (), 'WINDOW', 'POST_VIEW')
    _draw_handles.append(('VIEW_3D', h1))
    _draw_handles.append(('VIEW_3D', h2))
    _tag_redraw_all()


def unregister_3d_overlay():
    global _draw_handles
    remaining = []
    for (space, handle) in _draw_handles:
        if space == 'VIEW_3D':
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
            except Exception:
                pass
        else:
            remaining.append((space, handle))
    _draw_handles = remaining
    _tag_redraw_all()


def register_uv_overlay():
    unregister_uv_overlay()
    h1 = bpy.types.SpaceImageEditor.draw_handler_add(
        draw_curvature_uv, (), 'WINDOW', 'POST_PIXEL')
    h2 = bpy.types.SpaceImageEditor.draw_handler_add(
        draw_field_arrows_uv, (), 'WINDOW', 'POST_PIXEL')
    _draw_handles.append(('IMAGE_EDITOR', h1))
    _draw_handles.append(('IMAGE_EDITOR', h2))
    _tag_redraw_all()


def unregister_uv_overlay():
    global _draw_handles
    remaining = []
    for (space, handle) in _draw_handles:
        if space == 'IMAGE_EDITOR':
            try:
                bpy.types.SpaceImageEditor.draw_handler_remove(handle, 'WINDOW')
            except Exception:
                pass
        else:
            remaining.append((space, handle))
    _draw_handles = remaining
    _tag_redraw_all()


def unregister_all_overlays():
    unregister_3d_overlay()
    unregister_uv_overlay()


def _tag_redraw_all():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in ('VIEW_3D', 'IMAGE_EDITOR'):
                area.tag_redraw()


# ============================================================
# 数据设置
# ============================================================
def set_cone_points(vertex_indices):
    _overlay_data['cone_points'] = list(vertex_indices)


def set_uv_curvature(tri_data):
    _overlay_data['uv_curvature'] = tri_data


def set_field_arrows_uv(arrows):
    _overlay_data['field_arrows'] = arrows


def set_field_arrows_3d(arrows):
    _overlay_data['field_arrows_3d'] = arrows


def clear_all():
    _overlay_data.clear()
    _tag_redraw_all()


def compute_jet_color(t):
    t = max(0.0, min(1.0, t))
    if t < 0.25:
        r, g, b = 0.0, t * 4.0, 1.0
    elif t < 0.5:
        r, g, b = 0.0, 1.0, 1.0 - (t - 0.25) * 4.0
    elif t < 0.75:
        r, g, b = (t - 0.5) * 4.0, 1.0, 0.0
    else:
        r, g, b = 1.0, 1.0 - (t - 0.75) * 4.0, 0.0
    return (r, g, b, 0.7)


def build_uv_curvature_data(obj, curvature_array):
    import numpy as np
    mesh = obj.data
    if not mesh.uv_layers:
        return []

    uv_layer = mesh.uv_layers.active

    if len(curvature_array) > 0:
        cmin = float(np.min(curvature_array))
        cmax = float(np.max(curvature_array))
        crange = max(cmax - cmin, 1e-6)
    else:
        cmin, crange = 0.0, 1.0

    tri_data = []
    for poly in mesh.polygons:
        if len(poly.loop_indices) < 3:
            continue
        loops = list(poly.loop_indices)
        avg_k = 0.0
        for li in loops:
            vi = mesh.loops[li].vertex_index
            if vi < len(curvature_array):
                avg_k += float(curvature_array[vi])
        avg_k /= len(loops)
        t = (avg_k - cmin) / crange
        color = compute_jet_color(t)

        for i in range(1, len(loops) - 1):
            uv0 = uv_layer.data[loops[0]].uv
            uv1 = uv_layer.data[loops[i]].uv
            uv2 = uv_layer.data[loops[i+1]].uv
            tri_data.append((
                (uv0[0], uv0[1]),
                (uv1[0], uv1[1]),
                (uv2[0], uv2[1]),
                color
            ))
    return tri_data


def build_field_arrows(obj, face_directions):
    mesh = obj.data
    if not mesh.uv_layers:
        return [], []

    uv_layer = mesh.uv_layers.active
    arrows_uv = []
    arrows_3d = []

    for f, poly in enumerate(mesh.polygons):
        if f * 4 + 3 >= len(face_directions):
            break

        cx_uv = cy_uv = 0.0
        cx_3d = cy_3d = cz_3d = 0.0
        n_loops = len(poly.loop_indices)

        for li in poly.loop_indices:
            uv = uv_layer.data[li].uv
            cx_uv += uv[0]; cy_uv += uv[1]
            vi = mesh.loops[li].vertex_index
            co = mesh.vertices[vi].co
            cx_3d += co[0]; cy_3d += co[1]; cz_3d += co[2]

        cx_uv /= n_loops; cy_uv /= n_loops
        cx_3d /= n_loops; cy_3d /= n_loops; cz_3d /= n_loops

        ux = face_directions[f*4+0]
        uy = face_directions[f*4+1]
        arrow_len = 0.01

        arrows_uv.append((
            (cx_uv, cy_uv),
            (cx_uv + ux * arrow_len, cy_uv + uy * arrow_len)
        ))

        loops = list(poly.loop_indices)
        if len(loops) >= 3:
            v0 = mesh.vertices[mesh.loops[loops[0]].vertex_index].co
            v1 = mesh.vertices[mesh.loops[loops[1]].vertex_index].co
            e = (v1 - v0).normalized()
            arrow_len_3d = (v1 - v0).length * 0.3
            center_3d = (cx_3d, cy_3d, cz_3d)
            end_3d = (
                cx_3d + e[0] * arrow_len_3d,
                cy_3d + e[1] * arrow_len_3d,
                cz_3d + e[2] * arrow_len_3d
            )
            arrows_3d.append((center_3d, end_3d))

    return arrows_uv, arrows_3d