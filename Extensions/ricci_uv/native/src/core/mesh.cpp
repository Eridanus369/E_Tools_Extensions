#include "core/mesh.h"

#include <fstream>
#include <sstream>
#include <iostream>
#include <algorithm>
#include <queue>

namespace ricci {

// ============================================================
// OBJ 加载 + 多边形三角化
// ============================================================
bool Mesh::loadOBJ(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        std::cerr << "[Mesh] cannot open " << path << "\n";
        return false;
    }

    std::vector<Vec3> positions;
    std::vector<std::array<int,3>> tris;
    std::string line;

    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream iss(line);
        std::string type;
        iss >> type;

        if (type == "v") {
            double x, y, z;
            iss >> x >> y >> z;
            positions.emplace_back(x, y, z);
        } else if (type == "f") {
            std::vector<int> idx;
            std::string tok;
            while (iss >> tok) {
                // 支持 v / v/vt / v//vn / v/vt/vn
                size_t slash = tok.find('/');
                std::string vstr = (slash == std::string::npos)
                                   ? tok : tok.substr(0, slash);
                int vi = std::stoi(vstr);
                if (vi < 0) vi = (int)positions.size() + vi;  // 相对索引
                else        vi -= 1;                          // OBJ 1-based
                idx.push_back(vi);
            }
            // 扇形三角化（保持顶点序）
            for (size_t i = 1; i + 1 < idx.size(); ++i) {
                tris.push_back({idx[0], idx[i], idx[i+1]});
            }
        }
    }

    vertices.clear();
    vertices.resize(positions.size());
    for (size_t i = 0; i < positions.size(); ++i) {
        vertices[i].pos        = positions[i];
        vertices[i].originalId = (int)i;
    }

    triangles = std::move(tris);
    buildHalfEdge();
    return true;
}

// ============================================================
// 半边构建
// ============================================================
void Mesh::buildHalfEdge() {
    halfedges.clear();
    faces.clear();

    for (auto& v : vertices) v.halfedge = -1;

    const int nF = (int)triangles.size();
    halfedges.reserve(nF * 3);
    faces.resize(nF);

    // 1. 为每个三角形生成 3 条半边
    for (int f = 0; f < nF; ++f) {
        int h0 = (int)halfedges.size();
        for (int i = 0; i < 3; ++i) {
            HalfEdge he;
            he.origin = triangles[f][i];
            he.face   = f;
            he.next   = h0 + (i + 1) % 3;
            he.prev   = h0 + (i + 2) % 3;
            halfedges.push_back(he);
        }
        faces[f].halfedge = h0;
        for (int i = 0; i < 3; ++i) {
            int v = triangles[f][i];
            if (vertices[v].halfedge == -1) vertices[v].halfedge = h0 + i;
        }
    }

    // 2. 匹配对偶半边
    std::unordered_map<uint64_t, int> edgeMap;
    edgeMap.reserve(halfedges.size() * 2);

    for (int h = 0; h < (int)halfedges.size(); ++h) {
        int a = halfedges[h].origin;
        int b = halfedges[halfedges[h].next].origin;
        uint64_t k = edgeKey(a, b);

        auto it = edgeMap.find(k);
        if (it != edgeMap.end()) {
            int h2 = it->second;
            halfedges[h].twin  = h2;
            halfedges[h2].twin = h;
            edgeMap.erase(it);
        } else {
            edgeMap[k] = h;
        }
    }

    // 3. 标记边界顶点
    for (int h = 0; h < (int)halfedges.size(); ++h) {
        if (halfedges[h].twin < 0) {
            vertices[halfedges[h].origin].isBoundary = true;
            vertices[dest(h)].isBoundary             = true;
        }
    }
}

// ============================================================
// Seam 标记
// ============================================================
void Mesh::markSeams(const std::vector<std::pair<int,int>>& seams) {
    seamSet_.clear();
    for (auto& s : seams) seamSet_.insert(edgeKey(s.first, s.second));
}

bool Mesh::isSeam(int v0, int v1) const {
    return seamSet_.count(edgeKey(v0, v1)) > 0;
}

// ============================================================
// 沿 seam 切割
//   核心思想：每个顶点周围的入射面被 seam 分成若干"扇区"，
//   每个扇区独立分配一个顶点副本（第一个扇区复用原始 id）。
// ============================================================
void Mesh::cutAlongSeams() {
    if (seamSet_.empty()) return;

    const int nHE = (int)halfedges.size();
    const int nV  = (int)vertices.size();

    // newOrigin[h]：半边 h 的起点在切割后对应的顶点 id
    std::vector<int> newOrigin(nHE, -1);

    // 为每个顶点构建"入射面扇区"
    // 环绕遍历：绕 v 旋转时，遇到 seam 边就断开
    for (int v = 0; v < nV; ++v) {
        if (vertices[v].halfedge < 0) continue;

        // 收集所有从 v 出发的半边
        // 环绕顺序：h -> twin(h) -> prev(twin(h)) ... 即下一面从 v 出发的半边
        // 这里用更直接的：收集所有 origin==v 的半边，然后按面邻接关系分组
        std::vector<int> outgoing;
        for (int h = 0; h < nHE; ++h)
            if (halfedges[h].origin == v) outgoing.push_back(h);
        if (outgoing.empty()) continue;

        // 按面分组：每个从 v 出发的半边对应一个面
        // 用 BFS 按"共享非 seam 边"连接相邻面
        std::unordered_map<int,int> faceToHE;  // face -> halfedge (origin=v)
        for (int h : outgoing) faceToHE[halfedges[h].face] = h;

        std::unordered_set<int> visited;
        std::vector<std::vector<int>> components;

        for (auto& [f0, h0] : faceToHE) {
            if (visited.count(f0)) continue;

            std::vector<int> comp;
            std::queue<int> Q;
            Q.push(f0);
            visited.insert(f0);

            while (!Q.empty()) {
                int f = Q.front(); Q.pop();
                comp.push_back(f);

                int h = faceToHE[f];
                // 该面在 v 处的两条邻边
                // h 的起点是 v，h->next 到下一个顶点，h->prev 从上个顶点到 v
                int hPrev = halfedges[h].prev;

                // 两条可能连接其他面的边：h 与 hPrev（共享另一顶点）
                // 从 h 出发：对偶 h->twin 的 face 若存在，且不是 seam
                for (int he : {h, hPrev}) {
                    int tw = halfedges[he].twin;
                    if (tw < 0) continue;
                    int nf = halfedges[tw].face;
                    if (nf < 0 || visited.count(nf)) continue;
                    int va = halfedges[he].origin;
                    int vb = dest(he);
                    if (isSeam(va, vb)) continue;  // seam 边 → 断开

                    visited.insert(nf);
                    Q.push(nf);
                }
            }
            components.push_back(std::move(comp));
        }

        // 为每个 component 分配顶点 id：第一个复用 v，其余创建副本
        for (size_t ci = 0; ci < components.size(); ++ci) {
            int vid;
            if (ci == 0) {
                vid = v;
            } else {
                vid = (int)vertices.size();
                Vertex nv = vertices[v];
                nv.halfedge       = -1;
                nv.isVirtualCopy  = true;
                vertices.push_back(nv);
            }
            for (int f : components[ci]) {
                newOrigin[faceToHE[f]] = vid;
            }
        }
    }

    // 应用顶点重映射
    for (int h = 0; h < nHE; ++h) {
        if (newOrigin[h] >= 0) {
            halfedges[h].origin = newOrigin[h];
            if (vertices[newOrigin[h]].halfedge < 0)
                vertices[newOrigin[h]].halfedge = h;
        }
    }

    // 重建 twin（原 seam 处的 twin 需断开）
    for (int h = 0; h < nHE; ++h) halfedges[h].twin = -1;
    std::unordered_map<uint64_t, int> edgeMap;
    for (int h = 0; h < nHE; ++h) {
        int a = halfedges[h].origin;
        int b = dest(h);
        uint64_t k = edgeKey(a, b);
        auto it = edgeMap.find(k);
        if (it != edgeMap.end()) {
            // 只有非 seam 边才配对；seam 已被切开成两条独立边
            if (!isSeam(vertices[a].originalId, vertices[b].originalId)) {
                int h2 = it->second;
                halfedges[h].twin  = h2;
                halfedges[h2].twin = h;
                edgeMap.erase(it);
                continue;
            }
        }
        edgeMap[k] = h;
    }

    // 更新边界标记
    for (auto& vtx : vertices) vtx.isBoundary = false;
    for (int h = 0; h < nHE; ++h) {
        if (halfedges[h].twin < 0) {
            vertices[halfedges[h].origin].isBoundary = true;
            vertices[dest(h)].isBoundary             = true;
        }
    }

    seamSet_.clear();
}

// ============================================================
// 查询工具
// ============================================================
std::array<int,3> Mesh::faceVertices(int f) const {
    int h0 = faces[f].halfedge;
    return { halfedges[h0].origin,
             halfedges[halfedges[h0].next].origin,
             halfedges[halfedges[h0].prev].origin };
}

int Mesh::dest(int h) const {
    if(h < 0 || h >= (int)halfedges.size()) return -1;
    int n = halfedges[h].next;
    if(n < 0 || n >= (int)halfedges.size()) return -1;
    return halfedges[n].origin;
}

double Mesh::edgeLength(int h) const {
    const Vec3& a = vertices[halfedges[h].origin].pos;
    const Vec3& b = vertices[dest(h)].pos;
    return (b - a).norm();
}

std::vector<int> Mesh::outgoingHalfEdges(int v) const {
    std::vector<int> out;
    if (vertices[v].halfedge < 0) return out;

    int h0 = vertices[v].halfedge;
    int h  = h0;
    do {
        out.push_back(h);
        // 逆时针旋转：twin->next
        int tw = halfedges[h].twin;
        if (tw < 0) {
            // 边界顶点：从 h->prev 的 twin 反向出发
            int hp = halfedges[h].prev;
            int tp = halfedges[hp].twin;
            if (tp < 0) break;
            h = tp;
        } else {
            h = halfedges[tw].next;
        }
    } while (h != h0 && h >= 0);
    return out;
}

std::vector<int> Mesh::adjacentFaces(int v) const {
    std::vector<int> fs;
    for (int h : outgoingHalfEdges(v)) {
        int f = halfedges[h].face;
        if (f >= 0) fs.push_back(f);
    }
    return fs;
}

double Mesh::computeAngleSum(int v) const {
    double sum = 0.0;
    for (int h : outgoingHalfEdges(v)) {
        int h_next = halfedges[h].next;
        int h_prev = halfedges[h].prev;
        // h: v -> a, h_prev: b -> v, 对边 h_next->next? 用边长
        // 角度在 v 处，夹在边 (v,a) 与 (v,b) 之间，对边 (a,b)
        double va = edgeLength(h);
        double vb = edgeLength(h_prev);
        double ab = edgeLength(h_next);  // h_next 起点 a，终点 b
        sum += triangleAngle(va, vb, ab);
    }
    return sum;
}

// ============================================================
// 由 u 更新边长（相交圆模型）
// ============================================================
void Mesh::updateEdgeLengths() {
    // 顶点半径 r_i = exp(u_i)
    // 边长 l_ij = sqrt(r_i^2 + r_j^2 + 2 r_i r_j cos(phi_ij))
    // 其中 phi 为交角，需要预先确定（初始取 pi/2，即 l = sqrt(r_i^2 + r_j^2)）
    // 实际 Chow-Luo 中 phi 由三角形内角决定，这里保留接口，
    // 在 ricci_flow.cpp 中用三角形角度精确计算。
    // 当前简化：仅存储边长到 halfedge.length（如需可扩展字段）。
    // 此处留空，下一轮实现 ricci_flow 时填充。
}

} // namespace ricci