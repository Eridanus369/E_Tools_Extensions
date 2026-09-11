#include "core/mesh.h"
#include "core/pipeline.h"
#include <iostream>

int main() {
    using namespace ricci;

    // 构造单位立方体（12 三角形）
    Mesh m;
    // ... 手工填充顶点与三角形，验证半边构建与 seam 切割
    // 略（下一轮附完整测试）

    // 检查工厂
    auto& f = StageFactory::instance();
    (void)f;
    std::cout << "[test] skeleton OK\n";
    return 0;
}