# ============================================================
# UV 工具：网格数据提取 + UV 写回
# 关键约定：所有传给原生模块的 int 数组都是扁平 1D
# ============================================================
import bpy
import numpy as np
from mathutils import Vector


def extract_mesh_data(obj):
    """
    从对象提取三角网格 + seam + 顶点映射。

    返回:
        verts_np:    (N, 3) float64
        tris_np:     (3M,)  int32   ← 扁平 1D
        seams_np:    (2S,)  int32   ← 扁平 1D
        orig_index:  (N,)   int32
        face_map:    (M,)   int32
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()

    try:
        # ---- 1. 顶点坐标 (N, 3) 2D ----
        n_verts = len(mesh.vertices)
        verts_np = np.empty(n_verts * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", verts_np)
        verts_np = verts_np.reshape(n_verts, 3)

        # ---- 2. 三角面 → 扁平 1D (3M,) ----
        mesh.calc_loop_triangles()
        n_tris = len(mesh.loop_triangles)
        tris_np = np.empty(n_tris * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices", tris_np)
        # 不 reshape，保持 1D

        # ---- 3. 三角面 → 原始面映射 (M,) ----
        face_map_np = np.empty(n_tris, dtype=np.int32)
        mesh.loop_triangles.foreach_get("polygon_index", face_map_np)

        # ---- 4. Seam 边 → 扁平 1D (2S,) ----
        n_edges = len(mesh.edges)
        seam_flags = np.empty(n_edges, dtype=np.int32)
        mesh.edges.foreach_get("use_seam", seam_flags)

        edge_verts = np.empty(n_edges * 2, dtype=np.int32)
        mesh.edges.foreach_get("vertices", edge_verts)
        edge_verts = edge_verts.reshape(n_edges, 2)

        seam_indices = np.where(seam_flags > 0)[0]
        if len(seam_indices) > 0:
            seams_np = edge_verts[seam_indices].flatten().astype(np.int32)
        else:
            seams_np = np.zeros(0, dtype=np.int32)

        # ---- 5. 顶点映射 ----
        orig_index = np.arange(n_verts, dtype=np.int32)

        return verts_np, tris_np, seams_np, orig_index, face_map_np

    finally:
        eval_obj.to_mesh_clear()


def apply_uv_to_object(obj, uv_np, orig_vertex_index, face_map):
    """
    将原生模块返回的 UV 写回 Blender 对象。
    """
    mesh = obj.data

    if not mesh.uv_layers:
        mesh.uv_layers.new(name="RicciUV")
    uv_layer = mesh.uv_layers.active
    uv_layer.name = "RicciUV"

    n_orig = len(mesh.vertices)
    n_cut = uv_np.shape[0]

    if n_cut == n_orig:
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                vi = mesh.loops[li].vertex_index
                uv_layer.data[li].uv = (
                    float(uv_np[vi, 0]), float(uv_np[vi, 1]))
    else:
        orig_to_cut = {}
        for ci in range(n_cut):
            oi = int(orig_vertex_index[ci])
            orig_to_cut.setdefault(oi, []).append(ci)

        for poly in mesh.polygons:
            used_cuts = set()
            loop_assign = {}
            for li in poly.loop_indices:
                vi = mesh.loops[li].vertex_index
                candidates = orig_to_cut.get(vi, [vi])
                chosen = candidates[0]
                for c in candidates:
                    if c not in used_cuts:
                        chosen = c
                        break
                used_cuts.add(chosen)
                loop_assign[li] = chosen

            for li, ci in loop_assign.items():
                if ci < n_cut:
                    uv_layer.data[li].uv = (
                        float(uv_np[ci, 0]), float(uv_np[ci, 1]))

    mesh.update()


def get_uv_selected_verts(obj):
    """获取 UV 编辑器中框选的顶点对应的原始顶点索引。"""
    mesh = obj.data
    if not mesh.uv_layers:
        return np.array([], dtype=np.int32)

    uv_layer = mesh.uv_layers.active
    selected_verts = set()

    for poly in mesh.polygons:
        for li in poly.loop_indices:
            if uv_layer.data[li].select:
                selected_verts.add(mesh.loops[li].vertex_index)

    return np.array(sorted(selected_verts), dtype=np.int32)