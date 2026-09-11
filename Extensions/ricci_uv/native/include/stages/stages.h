#pragma once
#include "core/pipeline.h"
#include "curvature/curvature.h"
#include "holonomy/holonomy.h"
#include "cone/cone_detector.h"
#include "ricci/ricci_flow.h"
#include "embedding/embedding.h"
#include "visualize/visualizer.h"

namespace ricci {

class CurvatureStage : public IStage {
public:
    StageId id() const override { return StageId::Curvature; }
    bool run(Mesh& mesh, PipelineContext& ctx) override;
};

class HolonomyStage : public IStage {
public:
    StageId id() const override { return StageId::Holonomy; }
    bool run(Mesh& mesh, PipelineContext& ctx) override;
};

class ConeDetectStage : public IStage {
public:
    StageId id() const override { return StageId::ConeDetect; }
    bool run(Mesh& mesh, PipelineContext& ctx) override;
};

class RicciFlowStage : public IStage {
public:
    StageId id() const override { return StageId::RicciFlow; }
    bool run(Mesh& mesh, PipelineContext& ctx) override;
};

class EmbeddingStage : public IStage {
public:
    StageId id() const override { return StageId::Embed; }
    bool run(Mesh& mesh, PipelineContext& ctx) override;
};

class VisualizeStage : public IStage {
public:
    StageId id() const override { return StageId::Visualize; }
    bool run(Mesh& mesh, PipelineContext& ctx) override;
};

} // namespace ricci