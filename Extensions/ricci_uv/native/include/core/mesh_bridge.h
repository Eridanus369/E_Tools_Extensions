#pragma once
#include <Eigen/Core>
#include <vector>
#include <cstdint>

namespace ricci {

using Vec3 = Eigen::Vector3d;
using Vec2 = Eigen::Vector2d;

/// 原生模块 ↔ Python 之间的网格数据桥
/// 关键：当 seam 切割产生新顶点时，记录「切割后顶点 → 原始顶点」的映射，
///       以便 Python 侧将 UV 写回正确的 loop。
struct MeshBridgeInput {
    // 输入（Python → C++）
    std::vector<Vec3>   vertices;      // 顶点坐标
    std::vector<int>    triangles;     // 三角面索引（扁平，每3个一组）
    std::vector<int>    seams;         // seam 边（扁平，每2个一组）
    std::vector<int>    coneVertices;  // 用户手动指定的锥点
    std::vector<int>    regionVertices;// 用户框选区域（约束求解范围）

    int numVerts()  const { return (int)vertices.size(); }
    int numTris()   const { return (int)triangles.size() / 3; }
    int numSeams()  const { return (int)seams.size() / 2; }
};

struct MeshBridgeOutput {
    // 输出（C++ → Python）
    std::vector<Vec2>   uv;              // 每个顶点 UV
    std::vector<double> curvature;       // 高斯曲率
    std::vector<double> targetK;         // 目标曲率
    std::vector<int>    isCone;          // 是否锥奇异点 (0/1)
    std::vector<int>    origVertexIndex; // 切割后顶点 → 原始顶点索引

    // 每个面的方向场（用于衰减合乐的箭头绘制）
    // 每面 4 个 float: u_dir(2) + v_dir(2)
    std::vector<float>  faceDirections;

    // 统计
    double finalError  = 0.0;
    int    iterations  = 0;
    int    numCones    = 0;
    int    numFlipped  = 0;
    bool   converged   = false;
};

} // namespace ricci