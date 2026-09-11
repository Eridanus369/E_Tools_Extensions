#include "smooth/cone_smooth.h"
#include <unordered_set>
#include <cmath>
#include <algorithm>

namespace ricci {

void smoothConeUV(Mesh& mesh,
                   std::vector<Vec2>& uv,
                   const std::vector<int>& coneVertices,
                   int iterations,
                   double strength) {
    const int nV = mesh.numVertices();

    // 收集锥点邻域（锥点及其 1-ring 邻居）
    std::unordered_set<int> neighborhood;
    for (int c : coneVertices) {
        if (c < 0 || c >= nV) continue;
        neighborhood.insert(c);
        for (int h : mesh.outgoingHalfEdges(c)) {
            neighborhood.insert(mesh.dest(h));
        }
    }
    // 再扩一圈
    std::unordered_set<int> expanded = neighborhood;
    for (int v : neighborhood) {
        for (int h : mesh.outgoingHalfEdges(v)) {
            expanded.insert(mesh.dest(h));
        }
    }

    // 标记：锥点本身固定，不参与平滑
    std::unordered_set<int> fixed(coneVertices.begin(), coneVertices.end());

    // Laplacian 平滑
    for (int it = 0; it < iterations; ++it) {
        std::vector<Vec2> newUV = uv;

        for (int v : expanded) {
            if (fixed.count(v)) continue;  // 锥点固定

            // 收集邻居 UV 均值
            Vec2 sum(0.0, 0.0);
            int cnt = 0;
            for (int h : mesh.outgoingHalfEdges(v)) {
                int u = mesh.dest(h);
                sum += uv[u];
                cnt++;
            }
            if (cnt == 0) continue;
            Vec2 avg = sum / double(cnt);

            // 加权更新
            newUV[v] = uv[v] * (1.0 - strength) + avg * strength;
        }
        uv = std::move(newUV);
    }
}

} // namespace ricci