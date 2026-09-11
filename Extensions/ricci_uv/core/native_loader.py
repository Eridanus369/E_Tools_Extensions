"""
原生模块加载器 — 商业级

特性：
  - 直接用 ExtensionFileLoader 加载 .pyd/.so，绕过 sys.path 扫描（避免 UnicodeDecodeError）
  - 符号链接/junction 解析
  - 多平台（win-x64/linux-x64/macos-x64/macos-arm64）
  - Python ABI 版本校验
  - 五层搜索：lib/<platform> > 环境变量 > 偏好设置 > 开发目录 > 递归兜底
  - 完整诊断信息
"""
import sys
import os
import platform
import struct
import importlib
import importlib.util
from pathlib import Path
from importlib.machinery import ExtensionFileLoader, EXTENSION_SUFFIXES


# ============================================================
# 平台识别
# ============================================================
def get_platform_tag() -> str:
    """返回规范的平台标签"""
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Windows":
        bits = struct.calcsize("P") * 8
        return f"win-{'x64' if bits == 64 else 'x86'}"
    if system == "Darwin":
        return "macos-arm64" if machine in ("arm64", "aarch64") else "macos-x64"
    if system == "Linux":
        if machine in ("aarch64", "arm64"):
            return "linux-arm64"
        return "linux-x64"
    return f"{system.lower()}-{machine}"


def get_python_tag() -> str:
    """返回 Python ABI 标签，例如 cp313"""
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


# ============================================================
# 路径工具
# ============================================================
def resolve_link(p: Path) -> Path:
    """解析符号链接 / junction"""
    try:
        return p.resolve(strict=False)
    except Exception:
        return p


def get_addon_root() -> Path:
    """返回插件根目录（已解析符号链接）"""
    this_file = Path(__file__).resolve()
    return this_file.parent.parent


def get_extension_root() -> Path:
    """返回扩展目录（ricci_uv 的父目录）"""
    return get_addon_root().parent


# ============================================================
# 环境变量 / 偏好设置
# ============================================================
def _get_env_path():
    """环境变量指定的路径"""
    for var in ("RICCI_UV_NATIVE_PATH", "RICCI_NATIVE_PATH"):
        val = os.environ.get(var)
        if val:
            p = Path(val).expanduser()
            if p.exists():
                return p
    return None


def _get_prefs_path():
    """偏好设置中指定的路径"""
    try:
        import bpy
        if bpy.context is None:
            return None
        addons = bpy.context.preferences.addons
        for key in list(addons.keys()):
            if key == "ricci_uv" or key.endswith(".ricci_uv"):
                entry = addons.get(key)
                if entry is None:
                    continue
                prefs = entry.preferences
                if hasattr(prefs, "native_module_path"):
                    p = prefs.native_module_path
                    if p:
                        try:
                            import bpy as _b
                            p = _b.path.abspath(p)
                        except Exception:
                            pass
                        path = Path(p)
                        if path.exists():
                            return path
    except Exception:
        pass
    return None


# ============================================================
# 搜索目录列表
# ============================================================
def iter_search_dirs():
    """
    按优先级列出所有搜索目录。

    优先级：
      1. lib/<platform>/            发布版内置
      2. 环境变量                    部署/调试
      3. 偏好设置                    开发者
      4. native/build/Release|Debug  开发目录
      5. native/                     直接放置
      6. 递归扩展目录                兜底
    """
    seen = set()
    addon_root = get_addon_root()
    plat = get_platform_tag()

    def emit(p):
        if p is None:
            return None
        rp = resolve_link(p)
        key = str(rp).lower()
        if key in seen:
            return None
        if not rp.is_dir():
            return None
        seen.add(key)
        return rp

    # 1. lib/<platform>/
    r = emit(addon_root / "lib" / plat)
    if r:
        yield r

    # 2. 环境变量
    r = emit(_get_env_path())
    if r:
        yield r

    # 3. 偏好设置
    r = emit(_get_prefs_path())
    if r:
        yield r

    # 4. 开发目录常见位置
    for sub in ("native/build/Release",
                "native/build/RelWithDebInfo",
                "native/build/Debug",
                "native/build",
                "native"):
        r = emit(addon_root / sub)
        if r:
            yield r

    # 5. lib/ 无平台子目录（兜底）
    r = emit(addon_root / "lib")
    if r:
        yield r

    # 6. 递归扩展目录（限制深度 5，跳过无关目录）
    SKIP = {".git", "__pycache__", "CMakeFiles", ".vs", ".vscode",
            "third_party", "node_modules", "src", "include", "tests"}
    try:
        for root, dirs, files in os.walk(addon_root, followlinks=True):
            dirs[:] = [d for d in dirs if d not in SKIP]
            rp = resolve_link(Path(root))

            # 深度限制
            try:
                depth = len(rp.relative_to(addon_root).parts)
            except ValueError:
                continue
            if depth > 5:
                dirs.clear()
                continue

            # 该目录是否含 .pyd/.so
            has = any(
                f.startswith("ricci_core") and
                (f.endswith(".pyd") or f.endswith(".so") or f.endswith(".dylib"))
                for f in files
            )
            if has:
                r = emit(rp)
                if r:
                    yield r
    except Exception:
        pass


def find_module_file():
    """找到匹配当前 Python 版本的模块文件"""
    py_tag = get_python_tag()

    for d in iter_search_dirs():
        # 按优先级尝试多种文件名模式
        patterns = [
            f"ricci_core.{py_tag}*.pyd",            # cp313-win_amd64.pyd
            f"ricci_core.{py_tag}*.so",
            f"ricci_core.cpython-{py_tag[2:]}*.so", # cpython-313-x86_64-linux-gnu.so
            f"ricci_core*.pyd",
            f"ricci_core*.so",
            f"ricci_core*.dylib",
        ]
        for pat in patterns:
            try:
                for f in d.glob(pat):
                    if f.is_file() and f.suffix in ('.pyd', '.so', '.dylib'):
                        return f
            except Exception:
                continue
    return None


# ============================================================
# 加载（直接用 ExtensionFileLoader，绕过 sys.path 扫描）
# ============================================================
def _load_extension_direct(module_file: Path, module_name: str = "ricci_core"):
    """
    使用 ExtensionFileLoader 从指定文件加载 Python C 扩展。

    不通过 importlib.import_module，避免：
      1. sys.path 上其他同名 .py 文件导致的 UnicodeDecodeError
      2. 缓存模块名冲突
      3. 路径扫描阶段的意外错误
    """
    path_str = str(module_file)

    # 确认后缀是合法的扩展后缀
    matched_suffix = None
    for s in EXTENSION_SUFFIXES:
        if path_str.endswith(s):
            matched_suffix = s
            break

    if matched_suffix is None:
        raise ImportError(
            f"文件后缀不是 Python 扩展模块后缀: {module_file}\n"
            f"当前平台支持的扩展后缀: {EXTENSION_SUFFIXES}"
        )

    # 清理旧的模块缓存
    if module_name in sys.modules:
        del sys.modules[module_name]

    loader = ExtensionFileLoader(module_name, path_str)
    spec = importlib.util.spec_from_loader(
        module_name, loader, origin=path_str)

    if spec is None:
        raise ImportError(
            f"无法创建 spec: {module_file}\n"
            f"suffix={matched_suffix}"
        )

    module = importlib.util.module_from_spec(spec)

    # 提前注册到 sys.modules，方便扩展内部自引用
    sys.modules[module_name] = module

    try:
        loader.exec_module(module)
    except Exception:
        # 失败时清理
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise

    return module


def _validate(module, path: Path):
    """检查模块完整性"""
    required = ["unwrap", "analyze"]
    for name in required:
        if not hasattr(module, name):
            raise ImportError(
                f"模块 {path.name} 缺少必需函数: {name}\n"
                f"可能是旧版本或编译不完整。"
            )


# ============================================================
# 全局缓存
# ============================================================
_native = None
_loaded_path = None


def get_native():
    """获取原生模块（缓存）"""
    global _native, _loaded_path
    if _native is not None:
        return _native

    addon_root = get_addon_root()
    plat = get_platform_tag()
    expected_dir = addon_root / "lib" / plat

    module_file = find_module_file()

    if module_file is None:
        searched = list(iter_search_dirs())
        searched_str = "\n".join(f"  - {p}" for p in searched) \
            if searched else "  (无)"

        raise ImportError(
            f"找不到 ricci_core 原生模块。\n"
            f"\n"
            f"当前平台: {plat}\n"
            f"Python:   {sys.version.split()[0]}\n"
            f"扩展根目录: {addon_root}\n"
            f"\n"
            f"已搜索目录:\n{searched_str}\n"
            f"\n"
            f"期望位置:\n"
            f"  {expected_dir}\n"
            f"\n"
            f"编译命令（在 native 目录）:\n"
            f"  cmake -B build -DBLENDER_ROOT=\"<Blender安装路径>\"\n"
            f"  cmake --build build --config Release\n"
            f"产物会自动出现在 lib/{plat}/ 下。"
        )

    # 添加到 sys.path（保持兼容性，某些扩展内部可能依赖）
    module_dir = str(module_file.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

    importlib.invalidate_caches()

    # 唯一路径：直接加载，不走 import_module
    try:
        module = _load_extension_direct(module_file, "ricci_core")
        _validate(module, module_file)
        _native = module
        _loaded_path = module_file
        print(f"[Ricci UV] native loaded: {module_file}")
        return _native
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        raise ImportError(
            f"加载原生模块失败:\n"
            f"  文件: {module_file}\n"
            f"  错误: {type(e).__name__}: {e}\n"
            f"\n"
            f"完整堆栈:\n{tb}\n"
            f"\n"
            f"可能原因:\n"
            f"  1. Python 版本不匹配（编译 {get_python_tag()}，"
            f"Blender 内置 {sys.version_info.major}.{sys.version_info.minor}）\n"
            f"  2. 缺少 VC++ 运行时（Windows）→ 安装 MSVC Redistributable\n"
            f"  3. .pyd 依赖的其他 DLL 未找到\n"
            f"  4. .pyd 文件损坏（检查文件大小是否 > 100KB）\n"
        ) from e


def get_native_safe():
    """get_native 的安全版本，失败时返回 None 而不抛异常"""
    try:
        return get_native()
    except Exception as e:
        print(f"[Ricci UV] native load failed: {e}")
        return None


def reload_native():
    """强制重新加载（开发调试用）"""
    global _native, _loaded_path
    _native = None
    _loaded_path = None
    if "ricci_core" in sys.modules:
        del sys.modules["ricci_core"]
    importlib.invalidate_caches()
    return get_native()


def get_loaded_path():
    """返回已加载模块的路径（None 表示未加载）"""
    return _loaded_path


def get_diagnostics() -> dict:
    """返回诊断信息字典（用于 UI 显示）"""
    module_file = find_module_file()
    return {
        "platform": get_platform_tag(),
        "python": sys.version.split()[0],
        "addon_root": str(get_addon_root()),
        "search_dirs": [str(p) for p in iter_search_dirs()],
        "loaded_path": str(_loaded_path) if _loaded_path else None,
        "module_found": str(module_file) if module_file else None,
    }