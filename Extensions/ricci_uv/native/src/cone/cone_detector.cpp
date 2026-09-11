#include "cone/cone_detector.h"
#include "curvature/curvature.h"
#include <algorithm>
#include <cmath>
#include <iostream>

namespace ricci {

std::vector<ConeDetector::Cone>
ConeDetector::detect(Mesh& mesh, const Options& opt) {
    // 0. 重置
    for (auto& v : mesh.vertices) {
        v.isCone  = false;
        v.targetK = 0.0;   // 默认平坦
    }

    // 1. 更新曲率
    Curvature::computeGaussian(mesh);

    // 2. 候选排序
    auto ranked = Curvature::rankByMagnitude(mesh);

    // 3. 筛选：阈值 + 边界策略 + 上限
    std::vector<Cone> cones;
    cones.reserve(opt.maxCones);

    for (int v : ranked) {
        if ((int)cones.size() >= opt.maxCones) break;
        if (mesh.vertices[v].isBoundary && !opt.allowBoundary) continue;
        // 边界顶点若允许：其目标曲率设为其初始 K（保持边界弯曲）
        double k = mesh.vertices[v].currentK;
        if (std::abs(k) < opt.threshold) continue;

        Cone c;
        c.vertex = v;
        c.angle  = k;      // 初始估计
        c.initK  = k;
        cones.push_back(c);
    }

    if (cones.empty()) {
        std::cerr << "[Cone] no cone detected (try lowering threshold)\n";
        return cones;
    }

    // 4. 拉格朗日最优分配
    //    目标：min Σ Θ_i²  s.t.  Σ Θ_i = 2π  (圆盘拓扑)
    //    解：Θ_i = 2π / n（均匀）
    //    若需按 |K| 加权：Θ_i ∝ 1/w_i，w_i = 1/|K_i|
    //    这里用加权：Θ_i = C / w_i，C 由约束求得
    double totalWeight = 0.0;
    for (auto& c : cones) {
        double w = 1.0 / std::max(std::abs(c.initK), 1e-6);
        totalWeight += w;
    }
    double C = TWO_PI / totalWeight;   // 圆盘拓扑：Σ Θ = 2π

    for (auto& c : cones) {
        double w = 1.0 / std::max(std::abs(c.initK), 1e-6);
        c.angle = C * w;
        // 若初始 K 为负，锥角保持负（凹锥）
        if (c.initK < 0) c.angle = -c.angle;
    }

    // 5. 写回
    for (auto& c : cones) {
        mesh.vertices[c.vertex].isCone  = true;
        mesh.vertices[c.vertex].targetK = c.angle;
    }

    std::cout << "[Cone] detected " << cones.size() << " cones\n";
    return cones;
}

bool ConeDetector::checkTargetGaussBonnet(const Mesh& mesh, double tol) {
    double sum = 0.0;
    for (const auto& v : mesh.vertices) sum += v.targetK;
    double expected = TWO_PI * double(mesh.eulerCharacteristic());
    return std::abs(sum - expected) < tol * std::max(1.0, std::abs(expected));
}

} // namespace ricci