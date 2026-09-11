# Discrete Ricci Flow

**Author: Eridanus**

---

## Overview

This project implements conformal surface parameterization based on **Discrete Ricci Flow**. The core techniques include:

- Dynamic Delaunay triangulation
- Cotangent Newton method for fast convergence
- Region-constrained solving

### References

- Gu & Luo, *Combinatorial Ricci Flows on Surfaces* (2003)
- Gu et al., *Discrete Surface Ricci Flow* (2008)
- Springborn et al., *Discrete Conformal Equivalence* (2008)

---

## Directory Layout

    ricci_uv/
    ├── include/
    │   ├── core/
    │   │   ├── mesh.h
    │   │   └── geometry.h
    │   ├── curvature/
    │   │   └── curvature.h
    │   └── ricci/
    │       └── ricci_flow.h
    ├── src/
    │   └── ricci/
    │       └── ricci_flow.cpp
    ├── LICENSE
    └── README.md

---

## Dependencies

- C++17 or later
- Eigen3 (`Eigen/SparseCore`, `Eigen/SparseCholesky`)
- Internal headers: `core/mesh.h`, `curvature/curvature.h`

---

## Features

| Feature | Description |
|---------|-------------|
| Discrete Ricci Flow | Based on the intersecting-circle metric `l_ij = sqrt(r_i^2 + r_j^2)` |
| Newton Method | Solves `H·Δu = -F` using the Cotangent Hessian |
| Dynamic Delaunay | Flips edges when the cotangent weight becomes negative |
| Region Constraints | Restricts the flow to a subset of vertices with a decay weight |

---

## Quick Start

    #include "ricci/ricci_flow.h"

    int main() {
        ricci::Mesh mesh;
        // ... load the mesh, mark cone vertices (isCone), boundaries (isBoundary), etc. ...

        ricci::RicciFlow::Options opt;
        opt.maxIter         = 5000;
        opt.epsilon         = 0.1;
        opt.tol             = 1e-6;
        opt.useNewton       = true;
        opt.newtonStart     = 100;
        opt.dynamic         = true;
        opt.dynamicInterval = 50;

        auto report = ricci::RicciFlow::solve(mesh, opt);

        std::cout << "Converged: " << report.converged
                  << ", Error: "  << report.finalError
                  << ", Flips: "  << report.edgeFlips << std::endl;
        return 0;
    }

---

## API Summary

### RicciFlow::Options

| Field | Default | Description |
|-------|---------|-------------|
| `maxIter` | 5000 | Maximum number of iterations |
| `epsilon` | 0.1 | Initial step size for gradient descent |
| `tol` | 1e-6 | Convergence tolerance |
| `useNewton` | true | Enable the Newton method |
| `newtonStart` | 100 | Iteration index at which Newton is enabled |
| `dynamic` | false | Enable dynamic Delaunay edge flipping |
| `dynamicInterval` | 50 | Number of iterations between flips |

### RicciFlow::Report

| Field | Description |
|-------|-------------|
| `iterations` | Number of iterations performed |
| `finalError` | Final maximum curvature error |
| `converged` | Whether the solver converged |
| `errorHistory` | Error recorded at each iteration |
| `edgeFlips` | Total number of edge flips |

### Static Methods

- `initialize(Mesh&)` — Initialize vertex `u` values and target curvature
- `solve(Mesh&, const Options&)` — Main solver entry point
- `solveConstrained(Mesh&, const Options&, const std::vector<bool>&, double)` — Region-constrained solve
- `step(Mesh&, double)` — Single gradient step
- `maxError(const Mesh&)` — Current maximum error
- `computeCurvatureFromU(Mesh&)` — Compute curvature from `u`
- `cotanWeight(const Mesh&, int)` — Cotangent weight of a half-edge
- `buildHessian(Mesh&, Eigen::SparseMatrix<double>&)` — Build the Cotangent Hessian
- `newtonStep(Mesh&, const Options&, const std::vector<bool>*)` — One Newton step
- `flipEdgesToDelaunay(Mesh&)` — Dynamic Delaunay edge flipping

---

## Changelog

### 2026-09-11

- Fixed `C2059` syntax errors in `core/geometry.h` caused by `#define PI` / `#define TWO_PI`: replaced by `constexpr RICCI_PI` / `RICCI_TWO_PI` / `RICCI_EPS`.
- Fixed `C2976`, `C2511`, and `C2664` errors caused by a hand-written forward declaration of `Eigen::SparseMatrix` missing its default template parameters: replaced by a direct `#include <Eigen/SparseCore>`.

---

## Author

**Eridanus**

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
