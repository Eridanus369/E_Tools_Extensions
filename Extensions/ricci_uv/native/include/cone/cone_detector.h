#pragma once
#include "core/mesh.h"
#include <vector>

namespace ricci {

/// 锥奇异点检测 + 自动角度优化
class ConeDetector {
public:
    struct Options {
        int    maxCones      = 32;     // 用户上限
        double threshold     = 0.05;   // |K| 入选阈值（弧度）
        bool   allowBoundary = false;  // 是否允许边界顶点成为锥点
    };

    struct Cone {
        int    vertex;
        double angle;   // 目标锥角 Θ（K̄ = Θ）
        double initK;   // 初始高斯曲率
    };

    /// 检测 + 优化
    /// 步骤：
    ///   1. 候选排序（|K| 降序）
    ///   2. 阈值过滤 + 上限截断
    ///   3. 拉格朗日分配锥角：min Σ Θ_i²  s.t.  Σ Θ_i = 2π
    ///   4. 写回 mesh.vertices[v].targetK 与 isCone
    static std::vector<Cone> detect(Mesh& mesh, const Options& opt);

    /// 高斯-博内约束检查：Σ targetK + Σ κ_g ≈ 2πχ
    static bool checkTargetGaussBonnet(const Mesh& mesh, double tol = 1e-6);
};

} // namespace ricci