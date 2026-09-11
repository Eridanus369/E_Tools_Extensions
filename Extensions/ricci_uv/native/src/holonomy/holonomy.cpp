#include "holonomy/holonomy.h"
#include <cmath>
#include <algorithm>

namespace ricci {

std::vector<double> Holonomy::compute(const Mesh& mesh) {
    std::vector<double> H(mesh.numVertices(), 0.0);

    for (int v = 0; v < mesh.numVertices(); ++v) {
        // 独立累加：遍历出射半边，累加三角形内角
        double sum = 0.0;
        auto he = mesh.outgoingHalfEdges(v);
        for (int h : he) {
            // 三角形内角（在 v 处）
            int hPrev = mesh.halfedges[h].prev;
            double va = mesh.edgeLength(h);
            double vb = mesh.edgeLength(hPrev);
            double ab = mesh.edgeLength(mesh.halfedges[h].next);
            sum += triangleAngle(va, vb, ab);
        }
        H[v] = mesh.vertices[v].isBoundary ? (PI - sum) : (TWO_PI - sum);
    }
    return H;
}

double Holonomy::maxError(const Mesh& mesh) {
    auto H = compute(mesh);
    double e = 0.0;
    for (size_t i = 0; i < H.size(); ++i) {
        e = std::max(e, std::abs(H[i] - mesh.vertices[i].targetK));
    }
    return e;
}

std::vector<int> Holonomy::detectAnomalies(const Mesh& mesh,
                                            double threshold,
                                            bool includeBoundary) {
    auto H = compute(mesh);
    std::vector<int> out;
    for (int v = 0; v < mesh.numVertices(); ++v) {
        if (!includeBoundary && mesh.vertices[v].isBoundary) continue;
        if (std::abs(H[v]) > threshold) out.push_back(v);
    }
    return out;
}

} // namespace ricci