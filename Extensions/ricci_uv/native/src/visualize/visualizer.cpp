#define _USE_MATH_DEFINES
#include "visualize/visualizer.h"
#include "core/mesh.h"

#include <fstream>
#include <iostream>
#include <algorithm>
#include <cmath>
#include <sstream>
#include <initializer_list>

// stb_image_write 单头
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "../../third_party/stb_image_write.h"

constexpr double EPS = 1e-9;

namespace ricci {

std::vector<Vec2> Visualizer::projectIsometric(const Mesh& mesh) {
    // 等距投影：30° 视角
    const double c30 = std::cos(M_PI / 6.0);
    const double s30 = std::sin(M_PI / 6.0);
    std::vector<Vec2> raw(mesh.numVertices());
    double minX = 1e30, maxX = -1e30;
    double minY = 1e30, maxY = -1e30;
    for (int v = 0; v < mesh.numVertices(); ++v) {
        const Vec3& p = mesh.vertices[v].pos;
        double x = (p.x() - p.y()) * c30;
        double y = (p.x() + p.y()) * s30 - p.z();
        raw[v] = Vec2(x, y);
        minX = std::min(minX, x); maxX = std::max(maxX, x);
        minY = std::min(minY, y); maxY = std::max(maxY, y);
    }
    double spanX = std::max(maxX - minX, 1e-9);
    double spanY = std::max(maxY - minY, 1e-9);
    double span = std::max(spanX, spanY);
    std::vector<Vec2> out(mesh.numVertices());
    for (int v = 0; v < mesh.numVertices(); ++v) {
        double x = (raw[v].x() - minX) / span + (1.0 - spanX / span) * 0.5;
        double y = (raw[v].y() - minY) / span + (1.0 - spanY / span) * 0.5;
        out[v] = Vec2(x, 1.0 - y);   // 翻 Y
    }
    return out;
}

void Visualizer::jetColor(double t, unsigned char& r,
                          unsigned char& g, unsigned char& b) {
    t = std::max(0.0, std::min(1.0, t));
    // 简化 jet：蓝(0) → 青 → 绿 → 黄 → 红(1)
    auto lerp = [](double a, double b, double x) { return a + (b - a) * x; };
    double rr, gg, bb;
    if (t < 0.25) {
        rr = 0;                    gg = lerp(0, 255, t * 4);
        bb = 255;
    } else if (t < 0.5) {
        rr = 0;                    gg = 255;
        bb = lerp(255, 0, (t - 0.25) * 4);
    } else if (t < 0.75) {
        rr = lerp(0, 255, (t - 0.5) * 4); gg = 255; bb = 0;
    } else {
        rr = 255;                  gg = lerp(255, 0, (t - 0.75) * 4);
        bb = 0;
    }
    r = static_cast<unsigned char>(rr);
    g = static_cast<unsigned char>(gg);
    b = static_cast<unsigned char>(bb);
}

// ---------- CSV ----------
bool Visualizer::exportVertexCSV(const Mesh& mesh, const std::string& path) {
    std::ofstream out(path);
    if (!out) return false;
    out << "id,x,y,z,u,K,targetK,isCone,isBoundary\n";
    for (int v = 0; v < mesh.numVertices(); ++v) {
        const auto& V = mesh.vertices[v];
        out << v << ","
            << V.pos.x() << "," << V.pos.y() << "," << V.pos.z() << ","
            << V.u << "," << V.currentK << "," << V.targetK << ","
            << (V.isCone ? 1 : 0) << "," << (V.isBoundary ? 1 : 0) << "\n";
    }
    return true;
}

bool Visualizer::exportHistogramCSV(const std::vector<int>& counts,
                                    double minV, double maxV,
                                    const std::string& path) {
    std::ofstream out(path);
    if (!out) return false;
    out << "bin_lo,bin_hi,count\n";
    int bins = static_cast<int>(counts.size());
    double step = (maxV - minV) / std::max(1, bins - 1);
    for (int i = 0; i < bins; ++i) {
        double lo = minV + i * step;
        double hi = lo + step;
        out << lo << "," << hi << "," << counts[i] << "\n";
    }
    return true;
}

// ---------- SVG ----------
bool Visualizer::exportMeshSVG(const Mesh& mesh, const std::string& path,
                               bool colorByTarget, int W, int H) {
    auto proj = projectIsometric(mesh);
    double minV = 1e30, maxV = -1e30;
    for (const auto& v : mesh.vertices) {
        double val = colorByTarget ? v.targetK : v.currentK;
        minV = std::min(minV, val); maxV = std::max(maxV, val);
    }
    if (maxV - minV < EPS) maxV = minV + 1.0;
    std::ofstream out(path);
    if (!out) return false;
    out << "<?xml version=\"1.0\"?>\n";
    out << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << W
        << "\" height=\"" << H << "\" viewBox=\"0 0 1 1\">\n";
    out << "<rect width=\"1\" height=\"1\" fill=\"white\"/>\n";
    for (int f = 0; f < mesh.numFaces(); ++f) {
        auto vids = mesh.faceVertices(f);
        // 平均曲率
        double val = 0.0;
        for (int i = 0; i < 3; ++i) {
            val += colorByTarget ? mesh.vertices[vids[i]].targetK
                                 : mesh.vertices[vids[i]].currentK;
        }
        val /= 3.0;
        double t = (val - minV) / (maxV - minV);
        unsigned char r, g, b;
        jetColor(t, r, g, b);
        char hex[8];
        std::snprintf(hex, sizeof(hex), "#%02x%02x%02x", r, g, b);
        out << "<polygon points=\"";
        for (int i = 0; i < 3; ++i) {
            const Vec2& p = proj[vids[i]];
            out << p.x() << "," << p.y() << " ";
        }
        out << "\" fill=\"" << hex << "\" stroke=\"#222\" stroke-width=\"0.001\"/>\n";
    }
    out << "</svg>\n";
    return true;
}

// ---------- PNG 热力图 ----------
bool Visualizer::exportHeatmapPNG(const Mesh& mesh, const std::string& path,
                                  bool colorByTarget, int W, int H) {
    auto proj = projectIsometric(mesh);
    double minV = 1e30, maxV = -1e30;
    for (const auto& v : mesh.vertices) {
        double val = colorByTarget ? v.targetK : v.currentK;
        minV = std::min(minV, val); maxV = std::max(maxV, val);
    }
    if (maxV - minV < EPS) maxV = minV + 1.0;
    std::vector<unsigned char> img(W * H * 3, 255);  // 白底
    auto putPixel = [&](int x, int y, unsigned char r,
                        unsigned char g, unsigned char b) {
        if (x < 0 || y < 0 || x >= W || y >= H) return;
        int idx = (y * W + x) * 3;
        img[idx] = r; img[idx+1] = g; img[idx+2] = b;
    };
    for (int f = 0; f < mesh.numFaces(); ++f) {
        auto vids = mesh.faceVertices(f);
        // 三角形三个屏幕坐标
        double x0 = proj[vids[0]].x() * W, y0 = proj[vids[0]].y() * H;
        double x1 = proj[vids[1]].x() * W, y1 = proj[vids[1]].y() * H;
        double x2 = proj[vids[2]].x() * W, y2 = proj[vids[2]].y() * H;
        // 平均曲率 → 颜色
        double val = 0.0;
        for (int i = 0; i < 3; ++i)
            val += colorByTarget ? mesh.vertices[vids[i]].targetK
                                 : mesh.vertices[vids[i]].currentK;
        val /= 3.0;
        double t = (val - minV) / (maxV - minV);
        unsigned char r, g, b;
        jetColor(t, r, g, b);
        // 包围盒光栅化
        int minX = std::max(0, static_cast<int>(std::floor(std::min({x0,x1,x2}))));
        int maxX = std::min(W-1, static_cast<int>(std::ceil (std::max({x0,x1,x2}))));
        int minY = std::max(0, static_cast<int>(std::floor(std::min({y0,y1,y2}))));
        int maxY = std::min(H-1, static_cast<int>(std::ceil (std::max({y0,y1,y2}))));
        auto edgeFn = [](double ax, double ay, double bx, double by,
                         double px, double py) {
            return (bx - ax) * (py - ay) - (by - ay) * (px - ax);
        };
        double area = edgeFn(x0, y0, x1, y1, x2, y2);
        if (std::abs(area) < 1e-9) continue;
        for (int y = minY; y <= maxY; ++y) {
            for (int x = minX; x <= maxX; ++x) {
                double px = x + 0.5, py = y + 0.5;
                double w0 = edgeFn(x1, y1, x2, y2, px, py);
                double w1 = edgeFn(x2, y2, x0, y0, px, py);
                double w2 = edgeFn(x0, y0, x1, y1, px, py);
                if (area > 0) {
                    if (w0 >= 0 && w1 >= 0 && w2 >= 0) putPixel(x, y, r, g, b);
                } else {
                    if (w0 <= 0 && w1 <= 0 && w2 <= 0) putPixel(x, y, r, g, b);
                }
            }
        }
    }
    return stbi_write_png(path.c_str(), W, H, 3, img.data(), W * 3) != 0;
}

bool Visualizer::exportUVSVG(const Mesh& mesh,
                             const std::vector<Vec2>& uv,
                             const std::string& path,
                             bool colorByTarget,
                             int W, int H) {
    if (uv.size() != static_cast<size_t>(mesh.numVertices())) return false;
    double minV = 1e30, maxV = -1e30;
    for (const auto& v : mesh.vertices) {
        double val = colorByTarget ? v.targetK : v.currentK;
        minV = std::min(minV, val); maxV = std::max(maxV, val);
    }
    if (maxV - minV < EPS) maxV = minV + 1.0;
    std::ofstream out(path);
    if (!out) return false;
    out << "<?xml version=\"1.0\"?>\n";
    out << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << W
        << "\" height=\"" << H
        << "\" viewBox=\"0 0 1 1\" preserveAspectRatio=\"xMidYMid meet\">\n";
    out << "<rect width=\"1\" height=\"1\" fill=\"white\"/>\n";
    for (int f = 0; f < mesh.numFaces(); ++f) {
        auto vids = mesh.faceVertices(f);
        double val = 0.0;
        for (int i = 0; i < 3; ++i)
            val += colorByTarget ? mesh.vertices[vids[i]].targetK
                                 : mesh.vertices[vids[i]].currentK;
        val /= 3.0;
        double t = (val - minV) / (maxV - minV);
        unsigned char r, g, b;
        jetColor(t, r, g, b);
        char hex[8];
        std::snprintf(hex, sizeof(hex), "#%02x%02x%02x", r, g, b);
        out << "<polygon points=\"";
        for (int i = 0; i < 3; ++i) {
            // SVG y 轴向下，UV y 轴向上 → 翻转
            double x = uv[vids[i]].x();
            double y = 1.0 - uv[vids[i]].y();
            out << x << "," << y << " ";
        }
        out << "\" fill=\"" << hex
            << "\" stroke=\"#333\" stroke-width=\"0.0008\"/>\n";
    }
    out << "</svg>\n";
    return true;
}

// ============================================================
// UV PNG
// ============================================================
bool Visualizer::exportUVPNG(const Mesh& mesh,
                             const std::vector<Vec2>& uv,
                             const std::string& path,
                             bool colorByTarget,
                             int W, int H) {
    if (uv.size() != static_cast<size_t>(mesh.numVertices())) return false;
    double minV = 1e30, maxV = -1e30;
    for (const auto& v : mesh.vertices) {
        double val = colorByTarget ? v.targetK : v.currentK;
        minV = std::min(minV, val); maxV = std::max(maxV, val);
    }
    if (maxV - minV < EPS) maxV = minV + 1.0;
    std::vector<unsigned char> img(W * H * 3, 255);
    auto putPixel = [&](int x, int y,
                        unsigned char r, unsigned char g, unsigned char b) {
        if (x < 0 || y < 0 || x >= W || y >= H) return;
        int idx = (y * W + x) * 3;
        img[idx] = r; img[idx+1] = g; img[idx+2] = b;
    };
    for (int f = 0; f < mesh.numFaces(); ++f) {
        auto vids = mesh.faceVertices(f);
        // UV → 屏幕（翻转 y）
        double x0 = uv[vids[0]].x() * W, y0 = (1.0 - uv[vids[0]].y()) * H;
        double x1 = uv[vids[1]].x() * W, y1 = (1.0 - uv[vids[1]].y()) * H;
        double x2 = uv[vids[2]].x() * W, y2 = (1.0 - uv[vids[2]].y()) * H;
        double val = 0.0;
        for (int i = 0; i < 3; ++i)
            val += colorByTarget ? mesh.vertices[vids[i]].targetK
                                 : mesh.vertices[vids[i]].currentK;
        val /= 3.0;
        double t = (val - minV) / (maxV - minV);
        unsigned char r, g, b;
        jetColor(t, r, g, b);
        int minX = std::max(0, static_cast<int>(std::floor(std::min({x0,x1,x2}))));
        int maxX = std::min(W-1, static_cast<int>(std::ceil (std::max({x0,x1,x2}))));
        int minY = std::max(0, static_cast<int>(std::floor(std::min({y0,y1,y2}))));
        int maxY = std::min(H-1, static_cast<int>(std::ceil (std::max({y0,y1,y2}))));
        auto edgeFn = [](double ax, double ay, double bx, double by,
                         double px, double py) {
            return (bx - ax) * (py - ay) - (by - ay) * (px - ax);
        };
        double area = edgeFn(x0, y0, x1, y1, x2, y2);
        if (std::abs(area) < 1e-9) continue;
        for (int y = minY; y <= maxY; ++y) {
            for (int x = minX; x <= maxX; ++x) {
                double px = x + 0.5, py = y + 0.5;
                double w0 = edgeFn(x1, y1, x2, y2, px, py);
                double w1 = edgeFn(x2, y2, x0, y0, px, py);
                double w2 = edgeFn(x0, y0, x1, y1, px, py);
                bool inside = (area > 0)
                    ? (w0 >= 0 && w1 >= 0 && w2 >= 0)
                    : (w0 <= 0 && w1 <= 0 && w2 <= 0);
                if (inside) putPixel(x, y, r, g, b);
            }
        }
    }
    return stbi_write_png(path.c_str(), W, H, 3, img.data(), W * 3) != 0;
}

// ============================================================
// OBJ + UV 导出
// ============================================================
bool Visualizer::exportOBJWithUV(const Mesh& mesh,
                                 const std::vector<Vec2>& uv,
                                 const std::string& path) {
    if (uv.size() != static_cast<size_t>(mesh.numVertices())) return false;
    std::ofstream out(path);
    if (!out) return false;
    out << "# Ricci UV export\n";
    out << "# V=" << mesh.numVertices()
        << "  F=" << mesh.numFaces() << "\n";
    // 顶点
    for (int v = 0; v < mesh.numVertices(); ++v) {
        const Vec3& p = mesh.vertices[v].pos;
        out << "v " << p.x() << " " << p.y() << " " << p.z() << "\n";
    }
    // UV（与顶点 1:1）
    for (int v = 0; v < mesh.numVertices(); ++v) {
        out << "vt " << uv[v].x() << " " << uv[v].y() << "\n";
    }
    // 面：v/vt 索引 1-based，已切割 → 顶点与 UV 一一对应
    for (int f = 0; f < mesh.numFaces(); ++f) {
        auto vids = mesh.faceVertices(f);
        out << "f";
        for (int i = 0; i < 3; ++i) {
            int idx = vids[i] + 1;
            out << " " << idx << "/" << idx;
        }
        out << "\n";
    }
    return true;
}

} // namespace ricci
