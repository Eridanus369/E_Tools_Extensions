#pragma once
#include <Eigen/Core>
#include <cmath>
#include <algorithm>

namespace ricci {

using Vec3 = Eigen::Vector3d;
using Vec2 = Eigen::Vector2d;

constexpr double PI = 3.14159265358979323846;
constexpr double TWO_PI = 2.0 * PI;
constexpr double EPS = 1e-10;

inline double clampUnit(double x) {
    return std::max(-1.0, std::min(1.0, x));
}

inline double triangleAngle(double a, double b, double c) {
    double denom = 2.0 * a * b;
    if (denom < EPS) return 0.0;
    return std::acos(clampUnit((a*a + b*b - c*c) / denom));
}

inline double triangleArea3D(const Vec3& p0, const Vec3& p1, const Vec3& p2) {
    return 0.5 * (p1 - p0).cross(p2 - p0).norm();
}

inline double triangleArea2D(const Vec2& p0, const Vec2& p1, const Vec2& p2) {
    return 0.5 * ((p1.x()-p0.x())*(p2.y()-p0.y())
                - (p1.y()-p0.y())*(p2.x()-p0.x()));
}

inline double tangentCircleDist(double r_i, double r_j, double phi) {
    return std::sqrt(r_i*r_i + r_j*r_j + 2.0*r_i*r_j*std::cos(phi));
}


inline double inversePhi(double r_i, double r_j, double l) {
    double c = (l*l - r_i*r_i - r_j*r_j) / (2.0 * r_i * r_j);
    return std::acos(clampUnit(c));
}

}