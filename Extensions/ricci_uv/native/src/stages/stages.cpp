#include "stages/stages.h"
#include "embedding/embedding.h"
#include <fstream>
#include <iostream>
#include <filesystem>

namespace fs = std::filesystem;

namespace ricci {

// ---------- 曲率 ----------
bool CurvatureStage::run(Mesh& mesh, PipelineContext& ctx) {
    Curvature::computeGaussian(mesh);

    // 保存初始曲率
    ctx.initialCurvatures.resize(mesh.numVertices());
    for (int v = 0; v < mesh.numVertices(); ++v)
        ctx.initialCurvatures[v] = mesh.vertices[v].currentK;

    if (ctx.exportCurvatureHistogram) {
        fs::create_directories(ctx.outputDir);
        double minV, maxV;
        auto counts = Curvature::histogram(mesh, 32, minV, maxV);
        Visualizer::exportHistogramCSV(counts, minV, maxV,
            ctx.outputDir + "/histogram_initial.csv");
    }

    // 高斯-博内检查
    bool ok = Curvature::checkGaussBonnet(mesh, 1e-3);
    std::cout << "[Curvature] Gauss-Bonnet " << (ok ? "OK" : "FAIL")
              << "  (χ = " << mesh.eulerCharacteristic() << ")\n";
    return true;
}

// ---------- 和乐 ----------
bool HolonomyStage::run(Mesh& mesh, PipelineContext& ctx) {
    auto H = Holonomy::compute(mesh);
    ctx.holonomyErrors = H;

    double maxH = 0.0;
    for (double h : H) maxH = std::max(maxH, std::abs(h));
    std::cout << "[Holonomy] max |H| = " << maxH << "\n";
    return true;
}

// ---------- 锥点 ----------
bool ConeDetectStage::run(Mesh& mesh, PipelineContext& ctx) {
    ConeDetector::Options opt;
    opt.maxCones      = ctx.maxCones;
    opt.threshold     = ctx.coneThreshold;
    opt.allowBoundary = ctx.allowConeOnBoundary;

    auto cones = ConeDetector::detect(mesh, opt);

    ctx.coneVertices.clear();
    ctx.coneAngles.clear();
    for (auto& c : cones) {
        ctx.coneVertices.push_back(c.vertex);
        ctx.coneAngles.push_back(c.angle);
    }

    bool ok = ConeDetector::checkTargetGaussBonnet(mesh, 1e-3);
    std::cout << "[Cone] target Gauss-Bonnet " << (ok ? "OK" : "FAIL") << "\n";
    return true;
}

// ---------- Ricci 流 ----------
bool RicciFlowStage::run(Mesh& mesh, PipelineContext& ctx) {
    RicciFlow::Options opt;
    opt.maxIter = ctx.ricciMaxIter;
    opt.epsilon = ctx.ricciEpsilon;
    opt.tol     = ctx.ricciTol;
    opt.useNewton = ctx.useNewton;
    opt.dynamic = ctx.dynamicFlow;
    opt.dynamicInterval = ctx.dynamicCheckInterval;

    auto report = RicciFlow::solve(mesh, opt);

    std::cout << "[Ricci] iterations = " << report.iterations
              << "  finalError = " << report.finalError
              << "  converged = " << (report.converged ? "yes" : "no") << "\n";

    // 导出误差曲线
    if (!ctx.outputDir.empty()) {
        fs::create_directories(ctx.outputDir);
        std::ofstream out(ctx.outputDir + "/ricci_error.csv");
        out << "iter,error\n";
        for (size_t i = 0; i < report.errorHistory.size(); ++i)
            out << i << "," << report.errorHistory[i] << "\n";
    }
    return true;
}

// ---------- 扩展 VisualizeStage：加入 UV 可视化 ----------
bool VisualizeStage::run(Mesh& mesh, PipelineContext& ctx) {
    fs::create_directories(ctx.outputDir);

    if (ctx.exportCurvatureMap) {
        Visualizer::exportVertexCSV(mesh, ctx.outputDir + "/vertices.csv");
        Visualizer::exportMeshSVG(mesh, ctx.outputDir + "/mesh_curvature.svg", false);
        Visualizer::exportMeshSVG(mesh, ctx.outputDir + "/mesh_target.svg", true);

        // 若有 UV → 导出 UV 可视化
        if (!ctx.uv.empty()) {
            Visualizer::exportUVSVG(mesh, ctx.uv,
                                     ctx.outputDir + "/uv_curvature.svg", false);
            Visualizer::exportUVSVG(mesh, ctx.uv,
                                     ctx.outputDir + "/uv_target.svg", true);
        }
    }

    if (ctx.exportConeHeatmap) {
        Visualizer::exportHeatmapPNG(mesh,
            ctx.outputDir + "/heatmap_curvature.png", false, 1000, 1000);
        Visualizer::exportHeatmapPNG(mesh,
            ctx.outputDir + "/heatmap_target.png", true, 1000, 1000);

        if (!ctx.uv.empty()) {
            Visualizer::exportUVPNG(mesh, ctx.uv,
                ctx.outputDir + "/uv_curvature.png", false, 1000, 1000);
            Visualizer::exportUVPNG(mesh, ctx.uv,
                ctx.outputDir + "/uv_target.png", true, 1000, 1000);
        }
    }

    if (ctx.exportCurvatureHistogram) {
        double minV, maxV;
        auto counts = Curvature::histogram(mesh, 32, minV, maxV);
        Visualizer::exportHistogramCSV(counts, minV, maxV,
            ctx.outputDir + "/histogram_final.csv");
    }

    std::cout << "[Visualize] outputs -> " << ctx.outputDir << "\n";
    return true;
}

// ---------- 追加 EmbeddingStage ----------
bool EmbeddingStage::run(Mesh& mesh, PipelineContext& ctx) {
    Embedding::Options opt;
    opt.normalize = true;
    opt.padding   = 0.02;
    opt.verbose   = true;

    auto res = Embedding::embed(mesh, opt);

    if (!res.success) {
        std::cerr << "[Embed] FAILED: " << res.error << "\n";
        return false;
    }

    ctx.uv = std::move(res.uv);
    std::cout << "[Embed] " << res.numComponents << " component(s), "
              << res.numFlipped << " flipped triangle(s)\n";

    // 导出 UV 布局（如果开关打开）
    if (ctx.exportCurvatureMap) {
        fs::create_directories(ctx.outputDir);
        Visualizer::exportUVSVG(mesh, ctx.uv,
                                 ctx.outputDir + "/uv_layout.svg", false);
        Visualizer::exportOBJWithUV(mesh, ctx.uv,
                                     ctx.outputDir + "/unwrapped.obj");
    }
    return true;
}



// ---------- 自注册 ----------
REGISTER_STAGE(CurvatureStage, StageId::Curvature)
REGISTER_STAGE(HolonomyStage,  StageId::Holonomy)
REGISTER_STAGE(ConeDetectStage,StageId::ConeDetect)
REGISTER_STAGE(RicciFlowStage, StageId::RicciFlow)
REGISTER_STAGE(VisualizeStage, StageId::Visualize)
REGISTER_STAGE(EmbeddingStage, StageId::Embed)
} // namespace ricci