#pragma once
#include "core/mesh.h"
#include <vector>

// 直接包含 Eigen；不要自己写前置声明（默认模板参数会丢）
#include <Eigen/SparseCore>

namespace ricci {

class RicciFlow {
public:
    struct Options {
        int    maxIter         = 5000;
        double epsilon         = 0.1;
        double tol             = 1e-6;
        bool   useNewton       = true;
        int    newtonStart     = 100;
        bool   dynamic         = false;
        int    dynamicInterval = 50;
    };

    struct Report {
        int    iterations   = 0;
        double finalError   = 0.0;
        bool   converged    = false;
        std::vector<double> errorHistory;
        int    edgeFlips    = 0;
    };

    static void   initialize(Mesh& mesh);
    static Report solve(Mesh& mesh, const Options& opt);
    static Report solveConstrained(Mesh& mesh, const Options& opt,
                                   const std::vector<bool>& inRegion,
                                   double decayRate);
    static double step(Mesh& mesh, double epsilon);
    static double maxError(const Mesh& mesh);
    static double metricLen(const Mesh& mesh, int h);
    static void   computeCurvatureFromU(Mesh& mesh);
    static double cotanWeight(const Mesh& mesh, int h);
    static void   buildHessian(Mesh& mesh, Eigen::SparseMatrix<double>& H);
    static bool   newtonStep(Mesh& mesh, const Options& opt,
                             const std::vector<bool>* inRegion);
    static int    flipEdgesToDelaunay(Mesh& mesh);
};

} // namespace ricci