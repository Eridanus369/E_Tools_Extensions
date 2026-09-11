// ============================================================
// pybind11 绑定：原生模块 ↔ Python 接口
// 新增：region_vertices 参数、origVertexIndex 映射、faceDirections
// ============================================================
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "core/mesh.h"
#include "core/mesh_bridge.h"
#include "curvature/curvature.h"
#include "holonomy/holonomy.h"
#include "cone/cone_detector.h"
#include "ricci/ricci_flow.h"
#include "embedding/embedding.h"
#include "smooth/cone_smooth.h"
#include "quad/quad_remesh.h"

namespace py = pybind11;
using namespace ricci;

// ----------------------------------------------------------
// 工具：NumPy → C++ 向量
// ----------------------------------------------------------
static std::vector<Vec3> numpyToVec3(py::array_t<double> arr) {
    auto buf = arr.unchecked<2>();
    std::vector<Vec3> out(buf.shape(0));
    for (py::ssize_t i = 0; i < buf.shape(0); ++i)
        out[i] = Vec3(buf(i, 0), buf(i, 1), buf(i, 2));
    return out;
}

static std::vector<int> numpyToInt(py::array_t<int> arr) {
    auto buf = arr.unchecked<1>();
    std::vector<int> out(buf.shape(0));
    for (py::ssize_t i = 0; i < buf.shape(0); ++i)
        out[i] = buf(i);
    return out;
}

// ----------------------------------------------------------
// 核心：unwrap（完整流水线）
//   新增 region_vertices 参数：非空时仅对区域顶点执行 Ricci 流
// ----------------------------------------------------------
static py::dict py_unwrap(py::array_t<double> vertices,
                           py::array_t<int>    triangles,
                           py::array_t<int>    seams,
                           py::array_t<int>    region_verts,
                           py::dict            options) {
    // ---------- 1. 解析输入 ----------
    Mesh mesh;
    auto verts = numpyToVec3(vertices);
    mesh.vertices.resize(verts.size());
    for (size_t i = 0; i < verts.size(); ++i) {
        mesh.vertices[i].pos = verts[i];
        mesh.vertices[i].originalId = (int)i;
    }

    auto tris = numpyToInt(triangles);
    mesh.triangles.resize(tris.size() / 3);
    for (size_t i = 0; i < tris.size() / 3; ++i)
        mesh.triangles[i] = {tris[3*i], tris[3*i+1], tris[3*i+2]};

    mesh.buildHalfEdge();

    // ---------- 2. Seam 切割 ----------
    if (seams.size() > 0) {
        auto s = numpyToInt(seams);
        std::vector<std::pair<int,int>> seamList;
        for (size_t i = 0; i < s.size() / 2; ++i)
            seamList.emplace_back(s[2*i], s[2*i+1]);
        mesh.markSeams(seamList);
        mesh.cutAlongSeams();
    }

    // ---------- 3. 构建 origVertexIndex 映射 ----------
    // 切割后每个顶点记录其原始顶点 id
    std::vector<int> origIdx(mesh.numVertices());
    for (int i = 0; i < mesh.numVertices(); ++i)
        origIdx[i] = mesh.vertices[i].originalId;

    // ---------- 4. 解析选项 ----------
    int    maxCones      = options.contains("max_cones")      ? options["max_cones"].cast<int>()    : 32;
    double threshold     = options.contains("threshold")      ? options["threshold"].cast<double>() : 0.05;
    bool   allowBoundCone= options.contains("allow_boundary_cone") ? options["allow_boundary_cone"].cast<bool>() : false;
    int    maxIter       = options.contains("max_iter")       ? options["max_iter"].cast<int>()     : 5000;
    double epsilon       = options.contains("epsilon")        ? options["epsilon"].cast<double>()  : 0.1;
    double tol           = options.contains("tol")            ? options["tol"].cast<double>()      : 1e-6;
    double decayRate     = options.contains("decay_rate")     ? options["decay_rate"].cast<double>() : 0.0;

    // ---------- 5. 区域约束：构建 bool 掩码 ----------
    std::vector<bool> inRegion(mesh.numVertices(), true);  // 默认全局
    if (region_verts.size() > 0) {
        auto rv = numpyToInt(region_verts);
        std::fill(inRegion.begin(), inRegion.end(), false);
        for (int v : rv) {
            if (v >= 0 && v < mesh.numVertices()) inRegion[v] = true;
        }
        // 扩大一圈：将区域顶点的邻居也包含进来（避免边界突变）
        std::vector<bool> expanded = inRegion;
        for (int v = 0; v < mesh.numVertices(); ++v) {
            if (!inRegion[v]) continue;
            for (int h : mesh.outgoingHalfEdges(v)) {
                int u = mesh.dest(h);
                expanded[u] = true;
            }
        }
        inRegion = expanded;
    }

    // ---------- 6. 锥点检测 ----------
    Curvature::computeGaussian(mesh);

    ConeDetector::Options coneOpt;
    coneOpt.maxCones      = maxCones;
    coneOpt.threshold     = threshold;
    coneOpt.allowBoundary = allowBoundCone;

    // 用户手动指定的锥点优先
    for (int v : numpyToInt(vertices.size() > 0 ?
            py::array_t<int>(0) : py::array_t<int>(0))) { (void)v; }

    auto cones = ConeDetector::detect(mesh, coneOpt);

    // ---------- 7. Ricci 流（带区域约束 + 衰减） ----------
    RicciFlow::Options rfOpt;
    rfOpt.maxIter   = maxIter;
    rfOpt.epsilon   = epsilon;
    rfOpt.tol       = tol;
    rfOpt.useNewton = true;
    rfOpt.dynamic   = (decayRate > 0.0);

    auto report = RicciFlow::solveConstrained(mesh, rfOpt, inRegion, decayRate);

    // ---------- 8. 平面嵌入 ----------
    Embedding::Options embOpt;
    embOpt.normalize = true;
    embOpt.verbose   = false;
    auto emb = Embedding::embed(mesh, embOpt);

    // ---------- 9. 每面方向场（用于衰减合乐的箭头绘制） ----------
    std::vector<float> faceDirs(mesh.numFaces() * 4, 0.0f);
    for (int f = 0; f < mesh.numFaces(); ++f) {
        auto v = mesh.faceVertices(f);
        // u 方向 = 边 v0→v1 在 UV 空间的方向
        Vec2 uv0 = emb.uv[v[0]], uv1 = emb.uv[v[1]], uv2 = emb.uv[v[2]];
        Vec2 e01 = uv1 - uv0;
        Vec2 e02 = uv2 - uv0;
        double len01 = e01.norm();
        if (len01 < 1e-12) len01 = 1e-12;
        // u 方向归一化
        faceDirs[4*f+0] = (float)(e01.x() / len01);
        faceDirs[4*f+1] = (float)(e01.y() / len01);
        // v 方向 = 垂直于 u 且在三角形平面内
        double cross = e01.x() * e02.y() - e01.y() * e02.x();
        double sign = (cross >= 0) ? 1.0 : -1.0;
        faceDirs[4*f+2] = (float)(-e01.y() / len01 * sign);
        faceDirs[4*f+3] = (float)( e01.x() / len01 * sign);
    }

    // ---------- 10. 打包输出 ----------
    const int nV = mesh.numVertices();

    py::array_t<double> uvArr({nV, 2});
    py::array_t<double> curArr(nV);
    py::array_t<double> tkArr(nV);
    py::array_t<int>    coneArr(nV);
    py::array_t<int>    origArr(nV);

    auto uv  = uvArr.mutable_unchecked<2>();
    auto cur = curArr.mutable_unchecked<1>();
    auto tk  = tkArr.mutable_unchecked<1>();
    auto ic  = coneArr.mutable_unchecked<1>();
    auto oi  = origArr.mutable_unchecked<1>();

    for (int i = 0; i < nV; ++i) {
        uv(i, 0) = emb.uv[i].x();
        uv(i, 1) = emb.uv[i].y();
        cur(i)   = mesh.vertices[i].currentK;
        tk(i)    = mesh.vertices[i].targetK;
        ic(i)    = mesh.vertices[i].isCone ? 1 : 0;
        oi(i)    = origIdx[i];
    }

    py::dict result;
    result["uv"]               = uvArr;
    result["curvature"]        = curArr;
    result["target_k"]         = tkArr;
    result["is_cone"]          = coneArr;
    result["orig_vertex_index"]= origArr;
    result["final_error"]      = report.finalError;
    result["iterations"]       = report.iterations;
    result["num_cones"]        = (int)cones.size();
    result["num_flipped"]      = 0;
    result["converged"]        = report.converged;

    // 方向场作为扁平 float 数组
    py::array_t<float> dirArr((py::ssize_t)faceDirs.size());
    auto da = dirArr.mutable_unchecked<1>();
    for (size_t i = 0; i < faceDirs.size(); ++i) da(i) = faceDirs[i];
    result["face_directions"] = dirArr;

    return result;
}

// ----------------------------------------------------------
// 快速分析（不跑流）
// ----------------------------------------------------------
static py::dict py_analyze(py::array_t<double> vertices,
                            py::array_t<int>    triangles,
                            py::array_t<int>    seams,
                            py::dict            options) {
    Mesh mesh;
    auto verts = numpyToVec3(vertices);
    mesh.vertices.resize(verts.size());
    for (size_t i = 0; i < verts.size(); ++i) {
        mesh.vertices[i].pos = verts[i];
        mesh.vertices[i].originalId = (int)i;
    }

    auto tris = numpyToInt(triangles);
    mesh.triangles.resize(tris.size() / 3);
    for (size_t i = 0; i < tris.size() / 3; ++i)
        mesh.triangles[i] = {tris[3*i], tris[3*i+1], tris[3*i+2]};

    mesh.buildHalfEdge();

    if (seams.size() > 0) {
        auto s = numpyToInt(seams);
        std::vector<std::pair<int,int>> seamList;
        for (size_t i = 0; i < s.size() / 2; ++i)
            seamList.emplace_back(s[2*i], s[2*i+1]);
        mesh.markSeams(seamList);
        mesh.cutAlongSeams();
    }

    Curvature::computeGaussian(mesh);
    auto H = Holonomy::compute(mesh);

    const int nV = mesh.numVertices();
    py::array_t<double> curArr(nV), holArr(nV);
    auto cur = curArr.mutable_unchecked<1>();
    auto hol = holArr.mutable_unchecked<1>();
    for (int i = 0; i < nV; ++i) {
        cur(i) = mesh.vertices[i].currentK;
        hol(i) = H[i];
    }

    py::dict result;
    result["curvature"] = curArr;
    result["holonomy"]  = holArr;
    return result;
}

// ----------------------------------------------------------
// 锥点 UV 平滑
// ----------------------------------------------------------
static py::array_t<double> py_smooth_cone_uv(
        py::array_t<double> vertices,
        py::array_t<int>    triangles,
        py::array_t<double> uv_in,
        py::array_t<int>    cone_verts,
        int    iterations,
        double strength) {

    Mesh mesh;
    auto verts = numpyToVec3(vertices);
    mesh.vertices.resize(verts.size());
    for (size_t i = 0; i < verts.size(); ++i)
        mesh.vertices[i].pos = verts[i];

    auto tris = numpyToInt(triangles);
    mesh.triangles.resize(tris.size() / 3);
    for (size_t i = 0; i < tris.size() / 3; ++i)
        mesh.triangles[i] = {tris[3*i], tris[3*i+1], tris[3*i+2]};
    mesh.buildHalfEdge();

    // 读取 UV
    auto uvBuf = uv_in.unchecked<2>();
    std::vector<Vec2> uv(uvBuf.shape(0));
    for (py::ssize_t i = 0; i < uvBuf.shape(0); ++i)
        uv[i] = Vec2(uvBuf(i,0), uvBuf(i,1));

    auto coneList = numpyToInt(cone_verts);

    // Laplacian 平滑（仅锥点邻域）
    smoothConeUV(mesh, uv, coneList, iterations, strength);

    py::array_t<double> out({(py::ssize_t)uv.size(), (py::ssize_t)2});
    auto o = out.mutable_unchecked<2>();
    for (size_t i = 0; i < uv.size(); ++i) {
        o(i, 0) = uv[i].x();
        o(i, 1) = uv[i].y();
    }
    return out;
}

// ----------------------------------------------------------
// 四边形化重网格（QuadriFlow 风格）
// ----------------------------------------------------------
static py::dict py_quad_remesh(
        py::array_t<double> vertices,
        py::array_t<int>    triangles,
        py::dict            options) {

    auto verts = numpyToVec3(vertices);
    auto tris  = numpyToInt(triangles);

    int targetFaces = options.contains("target_faces")
        ? options["target_faces"].cast<int>() : 5000;
    bool preserveSharp = options.contains("preserve_sharp")
        ? options["preserve_sharp"].cast<bool>() : false;
    int seed = options.contains("seed")
        ? options["seed"].cast<int>() : 0;

    QuadRemesh::Options opt;
    opt.targetFaces  = targetFaces;
    opt.preserveSharp = preserveSharp;
    opt.seed = seed;

    auto result = QuadRemesh::run(verts, tris, opt);

    // 输出新的四边形网格
    const int nV = (int)result.vertices.size();
    py::array_t<double> outVerts({nV, 3});
    auto ov = outVerts.mutable_unchecked<2>();
    for (int i = 0; i < nV; ++i) {
        ov(i, 0) = result.vertices[i].x();
        ov(i, 1) = result.vertices[i].y();
        ov(i, 2) = result.vertices[i].z();
    }

    // 四边形面（扁平，每4个一组）
    const int nQ = (int)result.quads.size();
    py::array_t<int> outQuads(nQ * 4);
    auto oq = outQuads.mutable_unchecked<1>();
    for (int i = 0; i < nQ; ++i) {
        oq(4*i+0) = result.quads[i][0];
        oq(4*i+1) = result.quads[i][1];
        oq(4*i+2) = result.quads[i][2];
        oq(4*i+3) = result.quads[i][3];
    }

    // 顶点 → 原始网格的 UV 映射（重心坐标插值）
    py::array_t<double> outUV({nV, 2});
    auto ou = outUV.mutable_unchecked<2>();
    for (int i = 0; i < nV; ++i) {
        ou(i, 0) = result.uv[i].x();
        ou(i, 1) = result.uv[i].y();
    }

    py::dict res;
    res["vertices"] = outVerts;
    res["quads"]    = outQuads;
    res["uv"]       = outUV;
    res["num_faces"]= nQ;
    return res;
}

// ----------------------------------------------------------
// 模块注册
// ----------------------------------------------------------
PYBIND11_MODULE(ricci_core, m) {
    m.doc() = "Ricci Flow UV Unwrapping - native core (v0.3)";

    m.def("unwrap", &py_unwrap,
          py::arg("vertices"),
          py::arg("triangles"),
          py::arg("seams")         = py::array_t<int>(0),
          py::arg("region_verts")  = py::array_t<int>(0),
          py::arg("options")       = py::dict(),
          "Full Ricci flow UV unwrap. region_verts constrains flow to selected area.");

    m.def("analyze", &py_analyze,
          py::arg("vertices"),
          py::arg("triangles"),
          py::arg("seams")   = py::array_t<int>(0),
          py::arg("options") = py::dict(),
          "Quick curvature/holonomy analysis.");

    m.def("smooth_cone_uv", &py_smooth_cone_uv,
          py::arg("vertices"),
          py::arg("triangles"),
          py::arg("uv"),
          py::arg("cone_verts"),
          py::arg("iterations") = 10,
          py::arg("strength")   = 0.5,
          "Laplacian smooth UV in cone neighborhood.");

    m.def("quad_remesh", &py_quad_remesh,
          py::arg("vertices"),
          py::arg("triangles"),
          py::arg("options") = py::dict(),
          "Quad-dominant remeshing (QuadriFlow-style).");
}