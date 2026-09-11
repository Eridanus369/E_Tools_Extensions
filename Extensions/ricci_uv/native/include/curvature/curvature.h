#pragma once
#include "core/mesh.h"
#include <vector>

namespace ricci {

/// 离散高斯曲率 / 测地曲率 / 直方图
class Curvature {
public:
    /// 顶点角度和 → 高斯曲率（内点）或角度亏损（边界点为 π - Σθ）
    /// 结果写入 Vertex::angleSum 与 Vertex::currentK
    static void computeGaussian(Mesh& mesh);

    /// 边界顶点的测地曲率 κ_g = π - Σθ（用于高斯-博内验证）
    static void computeBoundaryGeodesic(Mesh& mesh);

    /// 高斯-博内定理验证：ΣK + Σκ_g ≈ 2πχ
    static bool checkGaussBonnet(const Mesh& mesh, double tol = 1e-6);

    /// 曲率直方图，返回 counts（size = bins）
    static std::vector<int> histogram(const Mesh& mesh, int bins,
                                      double& minV, double& maxV);

    /// 按 |K| 排序的顶点 id（降序）
    static std::vector<int> rankByMagnitude(const Mesh& mesh);
};

} // namespace ricci