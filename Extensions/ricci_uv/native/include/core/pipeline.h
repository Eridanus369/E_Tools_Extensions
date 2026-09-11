#pragma once
#include "core/mesh.h"
#include <memory>
#include <string>
#include <vector>
#include <functional>

namespace ricci {

// ---------- 流水线状态 ----------
enum class StageId {
    Load,          // 加载网格
    Curvature,     // 高斯曲率 / 角度亏损
    Holonomy,      // 和乐
    ConeDetect,    // 锥奇异点检测 + 最优角度
    RicciFlow,     // Chow-Luo 流
    Embed,         // 平面嵌入 → UV
    Layout,        // 打包 + 逆映射
    Visualize      // 曲率直方图 / 热力图导出
};

inline const char* to_string(StageId s) {
    switch (s) {
        case StageId::Load:        return "Load";
        case StageId::Curvature:   return "Curvature";
        case StageId::Holonomy:    return "Holonomy";
        case StageId::ConeDetect:  return "ConeDetect";
        case StageId::RicciFlow:   return "RicciFlow";
        case StageId::Embed:       return "Embed";
        case StageId::Layout:      return "Layout";
        case StageId::Visualize:   return "Visualize";
    }
    return "?";
}

// ---------- 流水线上下文 ----------
struct PipelineContext {
    // 用户参数
    int    maxCones                = 32;    // 锥点上限
    double coneThreshold           = 0.05;  // 曲率集中度阈值（弧度）
    bool   allowConeOnBoundary     = false; // 边界可否为锥点
    int    ricciMaxIter            = 5000;
    double ricciEpsilon            = 0.1;
    double ricciTol                = 1e-6;
    bool   useNewton               = true;
    bool   dynamicFlow             = true;
    int    dynamicCheckInterval    = 50;

    // 可视化输出
    std::string outputDir          = "./ricci_out";
    bool   exportCurvatureHistogram = true;
    bool   exportConeHeatmap        = true;
    bool   exportCurvatureMap       = true;

    // 中间结果
    std::vector<int>    coneVertices;
    std::vector<double> coneAngles;
    std::vector<double> initialCurvatures;
    std::vector<double> holonomyErrors;

    // UV 结果
    std::vector<Vec2>   uv;
};

// ---------- 抽象基类：每个 Stage 实现一个 ----------
class IStage {
public:
    virtual ~IStage() = default;

    /// 执行阶段，返回是否成功
    virtual bool run(Mesh& mesh, PipelineContext& ctx) = 0;

    /// 阶段名称
    virtual StageId id() const = 0;
    virtual const char* name() const { return to_string(id()); }
};

// ---------- 工厂 ----------
class StageFactory {
public:
    using Creator = std::function<std::unique_ptr<IStage>()>;

    static StageFactory& instance();

    void registerStage(StageId id, Creator c);
    std::unique_ptr<IStage> create(StageId id) const;

private:
    std::unordered_map<int, Creator> creators_;
};

// 便捷宏：注册 Stage
#define REGISTER_STAGE(StageClass, StageIdEnum)                              \
    namespace {                                                              \
        struct StageClass##_Registrar {                                      \
            StageClass##_Registrar() {                                       \
                ::ricci::StageFactory::instance().registerStage(             \
                    StageIdEnum,                                             \
                    [](){ return std::make_unique<StageClass>(); });         \
            }                                                                \
        };                                                                   \
        static StageClass##_Registrar g_##StageClass##_registrar;            \
    }

// ---------- 状态机：驱动流水线 ----------
class Pipeline {
public:
    Pipeline() = default;

    void addStage(StageId id) { order_.push_back(id); }

    /// 依次执行，出错即停
    bool run(Mesh& mesh, PipelineContext& ctx);

    /// 单步调试
    bool step(Mesh& mesh, PipelineContext& ctx);

    size_t currentIndex() const { return cursor_; }

private:
    std::vector<StageId> order_;
    size_t cursor_ = 0;
};

} // namespace ricci