#include "core/pipeline.h"
#include <iostream>

namespace ricci {

StageFactory& StageFactory::instance() {
    static StageFactory f;
    return f;
}

void StageFactory::registerStage(StageId id, Creator c) {
    creators_[(int)id] = std::move(c);
}

std::unique_ptr<IStage> StageFactory::create(StageId id) const {
    auto it = creators_.find((int)id);
    if (it == creators_.end()) return nullptr;
    return it->second();
}

bool Pipeline::run(Mesh& mesh, PipelineContext& ctx) {
    for (; cursor_ < order_.size(); ++cursor_) {
        auto stage = StageFactory::instance().create(order_[cursor_]);
        if (!stage) {
            std::cerr << "[Pipeline] stage not registered: "
                      << to_string(order_[cursor_]) << "\n";
            return false;
        }
        std::cout << "[Pipeline] >> " << stage->name() << std::endl;
        if (!stage->run(mesh, ctx)) {
            std::cerr << "[Pipeline] stage failed: " << stage->name() << "\n";
            return false;
        }
    }
    return true;
}

bool Pipeline::step(Mesh& mesh, PipelineContext& ctx) {
    if (cursor_ >= order_.size()) return false;
    auto stage = StageFactory::instance().create(order_[cursor_]);
    if (!stage) return false;
    bool ok = stage->run(mesh, ctx);
    ++cursor_;
    return ok;
}

} // namespace ricci