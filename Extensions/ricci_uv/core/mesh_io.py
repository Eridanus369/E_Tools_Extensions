import bpy
import bmesh
import numpy as np
from mathutils import Vector

def extract_mesh_data(obj):
    """
    从选中对象提取三角网格 + seam 信息。
    返回 (vertices_np, triangles_np, seams_np)
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()

    bm = bmesh.new()
    bm.from_mesh(mesh)

    # 三角化（不修改原始网格）
    bmesh.ops.triangulate(
        bm,
        faces=bm.faces[:],
        quad_method='BEAUTY',
        ngon_method='BEAUTY'
    )

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # 顶点坐标
    n_verts = len(bm.verts)
    verts_np = np.empty(n_verts * 3, dtype=np.float64)
    bm.verts.foreach_get("co", verts_np)
    verts_np = verts_np.reshape(n_verts, 3)

    # 三角形索引
    n_faces = len(bm.faces)
    tris_np = np.empty(n_faces * 3, dtype=np.int32)
    bm.faces.foreach_get("verts", tris_np)
    tris_np = tris_np.reshape(n_faces, 3)

    # Seam 边
    seams = []
    for e in bm.edges:
        if e.seam:
            seams.append((e.verts[0].index, e.verts[1].index))
    seams_np = np.array(seams, dtype=np.int32) if seams else np.zeros((0, 2), dtype=np.int32)

    # 清理
    bm.free()
    eval_obj.to_mesh_clear()

    return verts_np, tris_np, seams_np


def apply_uv_to_object(obj, uv_np, original_vert_count):
    """
    将 UV 坐标写回 Blender 对象的 UV 层。
    uv_np: shape (N, 2)，N 可能因 seam 切割而大于原始顶点数。
    对于切割产生的额外顶点，按原始顶点索引回退映射。
    """
    mesh = obj.data
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="RicciUV")
    uv_layer = mesh.uv_layers.active
    uv_layer.name = "RicciUV"

    # 简化策略：按 loop 写入。
    # 若原生输出顶点数 == 原始顶点数，直接按顶点索引映射。
    # 若切割产生新顶点，需要原生侧返回原始索引映射表（见 P5 扩展）。
    n_loops = len(mesh.loops)
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            if vi < uv_np.shape[0]:
                uv_layer.data[li].uv = (uv_np[vi, 0], uv_np[vi, 1])

    mesh.update()