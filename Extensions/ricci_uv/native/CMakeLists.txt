cmake_minimum_required(VERSION 3.16)
project(ricci_uv_native CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# ============================================================
# MSVC 源码编码修复
# 强制 MSVC 把源文件当 UTF-8 读取，避免中文注释/非 ASCII 字符被误解析
# ============================================================
if(MSVC)
    add_compile_options(/utf-8)
endif()
option(RICCI_BUILD_PYTHON "Build pybind11 Python module" ON)
option(RICCI_BUILD_CLI    "Build CLI test executable"    ON)

# ============================================================
# 源码根目录自动探测
# ============================================================
set(_native_dir "${CMAKE_CURRENT_SOURCE_DIR}")
set(_parent_dir "${CMAKE_CURRENT_SOURCE_DIR}/..")

if(EXISTS "${_native_dir}/src/core/mesh.cpp")
    set(RICCI_SRC_ROOT "${_native_dir}/src")
    set(RICCI_INC_ROOT "${_native_dir}/include")
    set(RICCI_LAYOUT "native/src")
elseif(EXISTS "${_parent_dir}/src/core/mesh.cpp")
    set(RICCI_SRC_ROOT "${_parent_dir}/src")
    set(RICCI_INC_ROOT "${_parent_dir}/include")
    set(RICCI_LAYOUT "parent/src")
else()
    message(FATAL_ERROR
        "找不到源码。已检查：\n"
        "  ${_native_dir}/src/core/mesh.cpp\n"
        "  ${_parent_dir}/src/core/mesh.cpp")
endif()

message(STATUS "源码布局: ${RICCI_LAYOUT}")
message(STATUS "源码根目录: ${RICCI_SRC_ROOT}")
message(STATUS "头文件根目录: ${RICCI_INC_ROOT}")

# ============================================================
# Blender Python 定位
# ============================================================
if(NOT DEFINED BLENDER_ROOT)
    if(WIN32)
        file(GLOB _bl_candidates
             "$ENV{ProgramFiles}/Blender Foundation/Blender 5.2"
             "$ENV{ProgramFiles}/Blender Foundation/Blender 5.*")
        list(SORT _bl_candidates)
        list(REVERSE _bl_candidates)
        list(LENGTH _bl_candidates _n)
        if(_n GREATER 0)
            list(GET _bl_candidates 0 BLENDER_ROOT)
        endif()
    elseif(APPLE)
        set(BLENDER_ROOT "/Applications/Blender.app/Contents/Resources/5.2")
    else()
        set(BLENDER_ROOT "/usr/share/blender")
    endif()
    message(STATUS "自动探测 BLENDER_ROOT: ${BLENDER_ROOT}")
endif()

if(NOT EXISTS "${BLENDER_ROOT}")
    message(FATAL_ERROR "BLENDER_ROOT 不存在: ${BLENDER_ROOT}")
endif()

set(_bl_ver "")
foreach(_v "5.2" "5.1" "5.0" "4.5" "4.4" "4.3" "4.2")
    if(EXISTS "${BLENDER_ROOT}/${_v}/python")
        set(_bl_ver "${_v}")
        break()
    endif()
endforeach()

if(_bl_ver STREQUAL "")
    if(EXISTS "${BLENDER_ROOT}/python")
        set(_bl_ver ".")
        set(_bl_python_root "${BLENDER_ROOT}/python")
    else()
        message(FATAL_ERROR "在 ${BLENDER_ROOT} 下找不到 python 目录")
    endif()
else()
    set(_bl_python_root "${BLENDER_ROOT}/${_bl_ver}/python")
endif()

message(STATUS "Blender Python root: ${_bl_python_root}")

if(WIN32)
    set(PYTHON_EXECUTABLE "${_bl_python_root}/bin/python.exe")
    set(PYTHON_INCLUDE_DIR "${_bl_python_root}/include")
    set(PYTHON_LIBRARY "${_bl_python_root}/libs/python313.lib")
elseif(APPLE)
    set(PYTHON_EXECUTABLE "${_bl_python_root}/bin/python3.13")
    set(PYTHON_INCLUDE_DIR "${_bl_python_root}/include/python3.13")
    set(PYTHON_LIBRARY "${_bl_python_root}/lib/libpython3.13.dylib")
else()
    set(PYTHON_EXECUTABLE "${_bl_python_root}/bin/python3.13")
    set(PYTHON_INCLUDE_DIR "${_bl_python_root}/include/python3.13")
    set(PYTHON_LIBRARY "${_bl_python_root}/lib/libpython3.13.so")
endif()

if(NOT EXISTS "${PYTHON_EXECUTABLE}")
    message(FATAL_ERROR "Blender Python 不存在: ${PYTHON_EXECUTABLE}")
endif()

execute_process(
    COMMAND "${PYTHON_EXECUTABLE}" -c
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    OUTPUT_VARIABLE _py_ver
    OUTPUT_STRIP_TRAILING_WHITESPACE)
message(STATUS "Blender Python 版本: ${_py_ver}")

find_package(Python3 COMPONENTS Interpreter Development QUIET)
find_package(Eigen3 3.3 REQUIRED NO_MODULE)

# ============================================================
# 源文件
# ============================================================
set(RICCI_SOURCES
    ${RICCI_SRC_ROOT}/core/geometry.cpp
    ${RICCI_SRC_ROOT}/core/mesh.cpp
    ${RICCI_SRC_ROOT}/core/pipeline.cpp            # ← 新增
    ${RICCI_SRC_ROOT}/curvature/curvature.cpp
    ${RICCI_SRC_ROOT}/holonomy/holonomy.cpp
    ${RICCI_SRC_ROOT}/cone/cone_detector.cpp
    ${RICCI_SRC_ROOT}/ricci/ricci_flow.cpp
    ${RICCI_SRC_ROOT}/embedding/embedding.cpp
    ${RICCI_SRC_ROOT}/smooth/cone_smooth.cpp
    ${RICCI_SRC_ROOT}/quad/quad_remesh.cpp
    ${RICCI_SRC_ROOT}/visualize/visualizer.cpp     # ← 新增
    ${RICCI_SRC_ROOT}/stages/stages.cpp            # ← 新增
)

foreach(_f ${RICCI_SOURCES})
    if(NOT EXISTS "${_f}")
        message(FATAL_ERROR "源文件不存在: ${_f}")
    endif()
endforeach()

set(RICCI_INCLUDE_DIRS
    ${RICCI_INC_ROOT}
    ${RICCI_SRC_ROOT})

# ============================================================
# 平台输出目录
# ============================================================
if(WIN32)
    set(RICCI_PLATFORM "win-x64")
elseif(APPLE)
    execute_process(COMMAND uname -m OUTPUT_VARIABLE _arch
                    OUTPUT_STRIP_TRAILING_WHITESPACE)
    if(_arch STREQUAL "arm64")
        set(RICCI_PLATFORM "macos-arm64")
    else()
        set(RICCI_PLATFORM "macos-x64")
    endif()
else()
    set(RICCI_PLATFORM "linux-x64")
endif()
set(RICCI_LIB_OUT "${_parent_dir}/lib/${RICCI_PLATFORM}")

# ============================================================
# 目标 1: pybind11 模块
# ============================================================
if(RICCI_BUILD_PYTHON)

    execute_process(
        COMMAND "${PYTHON_EXECUTABLE}" -c
                "import pybind11; print(pybind11.get_cmake_dir())"
        OUTPUT_VARIABLE _p11_dir
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET)
    if(_p11_dir AND EXISTS "${_p11_dir}")
        list(APPEND CMAKE_PREFIX_PATH "${_p11_dir}")
        message(STATUS "pybind11 (Blender Python): ${_p11_dir}")
    endif()

    if(EXISTS "${_native_dir}/third_party/pybind11/CMakeLists.txt")
        list(APPEND CMAKE_PREFIX_PATH
             "${_native_dir}/third_party/pybind11")
        message(STATUS "pybind11 (third_party): using local copy")
    endif()

    find_package(pybind11 QUIET)

    if(pybind11_FOUND)
        pybind11_add_module(ricci_core MODULE
            ${RICCI_SOURCES}
            ${_native_dir}/pybind_ricci.cpp)
        target_include_directories(ricci_core PRIVATE ${RICCI_INCLUDE_DIRS})
        target_link_libraries(ricci_core PRIVATE Eigen3::Eigen)

        set_target_properties(ricci_core PROPERTIES
            LIBRARY_OUTPUT_DIRECTORY "${RICCI_LIB_OUT}"
            RUNTIME_OUTPUT_DIRECTORY "${RICCI_LIB_OUT}"
            LIBRARY_OUTPUT_DIRECTORY_RELEASE "${RICCI_LIB_OUT}"
            RUNTIME_OUTPUT_DIRECTORY_RELEASE "${RICCI_LIB_OUT}"
            LIBRARY_OUTPUT_DIRECTORY_DEBUG "${RICCI_LIB_OUT}"
            RUNTIME_OUTPUT_DIRECTORY_DEBUG "${RICCI_LIB_OUT}")

        message(STATUS "✓ pybind11 模块启用 → ${RICCI_LIB_OUT}")
    else()
        message(WARNING "⚠ pybind11 未找到")
    endif()
endif()

# ============================================================
# 目标 2: CLI 可执行文件
# ============================================================
if(RICCI_BUILD_CLI)
    if(EXISTS "${RICCI_SRC_ROOT}/main.cpp")
        set(_main_cpp "${RICCI_SRC_ROOT}/main.cpp")
    elseif(EXISTS "${_native_dir}/main.cpp")
        set(_main_cpp "${_native_dir}/main.cpp")
    else()
        message(WARNING "找不到 main.cpp，跳过 CLI 构建")
        set(_main_cpp "")
    endif()

    if(NOT _main_cpp STREQUAL "")
        add_executable(ricci_cli
            ${RICCI_SOURCES}
            ${_main_cpp})
        target_include_directories(ricci_cli PRIVATE ${RICCI_INCLUDE_DIRS})
        target_link_libraries(ricci_cli PRIVATE Eigen3::Eigen)

        set_target_properties(ricci_cli PROPERTIES
            RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/Release"
            RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/Release"
            RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}/Debug")

        message(STATUS "✓ CLI 可执行文件启用")
    endif()
endif()

# ============================================================
# 诊断
# ============================================================
message(STATUS "========================================")
message(STATUS "Blender version:  ${_bl_ver}")
message(STATUS "Blender Python:   ${PYTHON_EXECUTABLE}")
message(STATUS "Python version:   ${_py_ver}")
message(STATUS "Platform:         ${RICCI_PLATFORM}")
message(STATUS "Lib output:       ${RICCI_LIB_OUT}")
message(STATUS "========================================")